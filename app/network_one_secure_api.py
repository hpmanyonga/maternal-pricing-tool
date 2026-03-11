import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
import jwt
from jwt import InvalidTokenError, PyJWKClient
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from engine.network_one_icd10 import explain_icd10_matches
from engine.network_one_models import NetworkOneEpisodeInput
from engine.network_one_pricing import NetworkOneEpisodePricingEngine, build_default_quote
from engine.network_one_storage import NetworkOneStorage, resolve_database_url


logger = logging.getLogger("network_one_api")
logging.basicConfig(level=logging.INFO, format="%(message)s")

ROLE_QUOTE_READ = "quote:read"
ROLE_QUOTE_WRITE = "quote:write"
_storage: Optional[NetworkOneStorage] = None


def _db_required() -> bool:
    return os.getenv("NETWORK_ONE_DB_REQUIRED", "false").lower() == "true"


def _get_storage() -> Optional[NetworkOneStorage]:
    global _storage
    if _storage is not None:
        return _storage
    database_url = resolve_database_url()
    if not database_url:
        return None
    _storage = NetworkOneStorage(database_url=database_url)
    if os.getenv("NETWORK_ONE_DB_AUTO_CREATE", "false").lower() == "true":
        _storage.create_schema_for_dev()
    return _storage


def _load_tokens() -> Dict[str, dict]:
    raw = os.getenv("NETWORK_ONE_API_TOKENS_JSON", "{}")
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return {}
        return parsed
    except json.JSONDecodeError:
        return {}


def _jwt_auth_settings() -> Dict[str, str]:
    return {
        "jwks_url": os.getenv("NETWORK_ONE_JWKS_URL", "").strip(),
        "secret": os.getenv("NETWORK_ONE_JWT_SECRET", "").strip(),
        "algorithm": os.getenv("NETWORK_ONE_JWT_ALGORITHM", "HS256").strip(),
        "issuer": os.getenv("NETWORK_ONE_JWT_ISSUER", "").strip(),
        "audience": os.getenv("NETWORK_ONE_JWT_AUDIENCE", "").strip(),
        "roles_claim": os.getenv("NETWORK_ONE_JWT_ROLES_CLAIM", "roles").strip(),
        "actor_claim": os.getenv("NETWORK_ONE_JWT_ACTOR_CLAIM", "sub").strip(),
    }


def _jwt_auth_enabled() -> bool:
    cfg = _jwt_auth_settings()
    return bool(cfg["jwks_url"] or cfg["secret"])


def _extract_roles_from_claims(payload: Dict, roles_claim: str) -> list:
    roles = []
    rc = payload.get(roles_claim)
    if isinstance(rc, str):
        roles.extend([r.strip() for r in rc.replace(",", " ").split() if r.strip()])
    elif isinstance(rc, list):
        roles.extend([str(r).strip() for r in rc if str(r).strip()])

    scope = payload.get("scope")
    if isinstance(scope, str):
        roles.extend([s.strip() for s in scope.split() if s.strip()])
    return sorted(set(roles))


def _verify_jwt(token: str) -> Tuple[str, list]:
    cfg = _jwt_auth_settings()
    decode_kwargs = {
        "algorithms": [cfg["algorithm"]],
    }
    if cfg["issuer"]:
        decode_kwargs["issuer"] = cfg["issuer"]
    if cfg["audience"]:
        decode_kwargs["audience"] = cfg["audience"]

    if cfg["jwks_url"]:
        signing_key = PyJWKClient(cfg["jwks_url"]).get_signing_key_from_jwt(token).key
        payload = jwt.decode(token, signing_key, **decode_kwargs)
    elif cfg["secret"]:
        payload = jwt.decode(token, cfg["secret"], **decode_kwargs)
    else:
        raise InvalidTokenError("JWT auth not configured")

    roles = _extract_roles_from_claims(payload, cfg["roles_claim"])
    actor = str(payload.get(cfg["actor_claim"], payload.get("sub", "unknown")))
    return actor, roles


def _hash_patient_id(patient_id: str) -> str:
    salt = os.getenv("NETWORK_ONE_AUDIT_SALT", "dev-salt-change-me")
    digest = hmac.new(salt.encode("utf-8"), patient_id.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest


def _audit_log(actor: str, action: str, patient_id: Optional[str], result: str, detail: str) -> None:
    target_hash = _hash_patient_id(patient_id) if patient_id else None
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "action": action,
        "target": target_hash,
        "result": result,
        "detail": detail,
    }
    logger.info(json.dumps(event))
    storage = _get_storage()
    if not storage:
        return
    try:
        storage.save_audit_event(
            actor=actor,
            action=action,
            target_hash=target_hash,
            result=result,
            detail=detail,
        )
    except SQLAlchemyError as exc:
        if _db_required():
            raise RuntimeError("Failed to persist audit event") from exc


def _require_role(authorization: Optional[str], required_role: str) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    token = authorization.replace("Bearer ", "", 1).strip()
    if _jwt_auth_enabled():
        try:
            actor, roles = _verify_jwt(token)
        except InvalidTokenError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        if required_role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return actor

    token_map = _load_tokens()
    entry = token_map.get(token)
    if not entry:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    roles = entry.get("roles", [])
    if required_role not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return entry.get("actor", "unknown")


def require_quote_write(authorization: Optional[str] = Header(default=None)) -> str:
    return _require_role(authorization, ROLE_QUOTE_WRITE)


def require_quote_read(authorization: Optional[str] = Header(default=None)) -> str:
    return _require_role(authorization, ROLE_QUOTE_READ)


class QuoteRequest(BaseModel):
    patient_id: str = Field(min_length=1, max_length=128)
    payer_type: str = Field(pattern="^(CASH|MEDICAL_AID)$")
    delivery_type: str = Field(default="UNKNOWN", pattern="^(NVD|CS|UNKNOWN)$")
    chronic: bool = False
    pregnancy_medical: bool = False
    pregnancy_anatomical: bool = False
    risk_factor: bool = False
    unrelated_medical: bool = False
    unrelated_anatomical: bool = False
    icd10_codes: list[str] = Field(default_factory=list)
    icd10_descriptions: list[str] = Field(default_factory=list)
    base_price_zar: Optional[float] = Field(default=None, gt=0)


class ICDExplainRequest(BaseModel):
    icd10_codes: list[str] = Field(default_factory=list)
    icd10_descriptions: list[str] = Field(default_factory=list)
    delivery_type: str = Field(default="UNKNOWN", pattern="^(NVD|CS|UNKNOWN)$")
    chronic: bool = False
    pregnancy_medical: bool = False
    pregnancy_anatomical: bool = False
    risk_factor: bool = False
    unrelated_medical: bool = False
    unrelated_anatomical: bool = False
    base_price_zar: Optional[float] = Field(default=None, gt=0)


app = FastAPI(title="Network One Secure Pricing API", version="1.0.0")


@app.middleware("http")
async def secure_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
def healthcheck(actor: str = Depends(require_quote_read)):
    try:
        _audit_log(actor=actor, action="healthcheck", patient_id=None, result="success", detail="ok")
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return {"status": "ok", "service": "network-one-secure-pricing-api"}


@app.post("/v1/episodes/quote")
def quote_episode(payload: QuoteRequest, actor: str = Depends(require_quote_write)):
    try:
        _, quote = build_default_quote(payload.model_dump(exclude_none=True))
    except ValueError as exc:
        try:
            _audit_log(
                actor=actor,
                action="quote_episode",
                patient_id=payload.patient_id,
                result="validation_error",
                detail="invalid payload",
            )
        except RuntimeError:
            pass
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    storage = _get_storage()
    quote_id = None
    if storage:
        try:
            quote_id = storage.save_quote(
                quote=quote,
                patient_hash=_hash_patient_id(payload.patient_id),
                delivery_type=payload.delivery_type,
            )
        except SQLAlchemyError as exc:
            if _db_required():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Failed to persist quote",
                ) from exc

    try:
        _audit_log(
            actor=actor,
            action="quote_episode",
            patient_id=payload.patient_id,
            result="success",
            detail=f"tier={quote.complexity_tier}",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return {
        "quote_id": quote_id,
        "patient_id": quote.patient_id,
        "payer_type": quote.payer_type,
        "complexity_score": quote.complexity_score,
        "complexity_tier": quote.complexity_tier,
        "base_price_zar": quote.base_price_zar,
        "risk_adjusted_price_zar": quote.risk_adjusted_price_zar,
        "final_price_zar": quote.final_price_zar,
        "clinical_bucket_amounts": quote.clinical_bucket_amounts,
        "installment_amounts": quote.installment_amounts,
        "rationale": quote.rationale,
    }


@app.post("/v1/episodes/icd10-explain")
def explain_icd10(payload: ICDExplainRequest, actor: str = Depends(require_quote_read)):
    explanation = explain_icd10_matches(
        codes=payload.icd10_codes,
        descriptions=payload.icd10_descriptions,
    )

    engine = NetworkOneEpisodePricingEngine()
    input_data = NetworkOneEpisodeInput(
        patient_id="EXPLAIN_PREVIEW",
        payer_type="MEDICAL_AID",
        delivery_type=payload.delivery_type,
        chronic=payload.chronic,
        pregnancy_medical=payload.pregnancy_medical,
        pregnancy_anatomical=payload.pregnancy_anatomical,
        risk_factor=payload.risk_factor,
        unrelated_medical=payload.unrelated_medical,
        unrelated_anatomical=payload.unrelated_anatomical,
        icd10_codes=payload.icd10_codes,
        icd10_descriptions=payload.icd10_descriptions,
        base_price_zar=payload.base_price_zar or engine.config["base_price_zar"],
        installment_weights=engine.config["installment_weights"],
    )
    preview_quote = engine.quote(input_data)

    _audit_log(
        actor=actor,
        action="icd10_explain",
        patient_id=None,
        result="success",
        detail=f"indicators={','.join(explanation['inferred_indicators'])}",
    )

    return {
        "explanation": explanation,
        "preview": {
            "complexity_score": preview_quote.complexity_score,
            "complexity_tier": preview_quote.complexity_tier,
            "final_price_zar": preview_quote.final_price_zar,
        },
    }
