# Network One Episode Pricing Approach (Early ANC -> Early PNC)

## Recommended approach
Implement a secure, configurable episode-pricing service with:
- Base market anchor price (`R51,000`, configurable).
- ICD-10 and burden-based complexity scoring.
- Tiered risk multipliers for transparent payer negotiation.
- Installment schedule tied to clinical milestones.
- Outlier protection floor/cap and governance override controls.

### Why this is the recommended approach
- Aligns with observed claims signal (mean around `R50k` for the target episode).
- Supports both cash and medical aid workflows.
- Enables transparent pricing rationale for funders and patients.
- Scales into a production pricing app with API-first architecture.

## Fallback approach
If payers require simpler rollout:
- Launch `2-tier` model only (`Standard` / `High Risk`).
- Keep same API and scoring framework.
- Recalibrate to 4 tiers after 6-12 months of data.

## Pricing model v1
Episode scope: `2_Early antenatal` + `3_Late antenatal` + `4_Delivery` + `5_Early Postnatal`.

### Complexity score factors
- Chronic (`+2.0`)
- Pregnancy medical (`+2.0`)
- Pregnancy anatomical (`+1.0`)
- Risk factor (`+1.0`)
- Unrelated medical (`+0.5`)
- Unrelated anatomical (`+0.5`)
- CS indicator (`+2.0`)

### Tier mapping
- Tier 1 Low: `score <= 2.0`
- Tier 2 Moderate: `2.0 < score <= 4.0`
- Tier 3 High: `4.0 < score <= 6.0`
- Tier 4 Very High: `score > 6.0`

### Price equation
`Final = clamp(BasePrice * TierMultiplier + DeliveryAddon, Floor, Cap)`

Default parameters:
- BasePrice: `R51,000`
- TierMultiplier: `0.88, 1.00, 1.18, 1.38`
- DeliveryAddon: `NVD=0, CS=R6,000, UNKNOWN=R2,500`
- Floor/Cap: `R42,000` to `R85,000`

### Installments
- Booking (12-16w): `20%`
- Mid ANC (20-24w): `20%`
- Late ANC (28-32w): `20%`
- Pre-delivery (34-36w): `15%`
- Delivery event: `20%`
- Early PNC (0-6w): `5%`

## System architecture (production target)
- Mobile/Web app: patient enrollment + quote preview + consent.
- API service: risk scoring, pricing, installments, governance workflows.
- Data store: encrypted relational DB for quotes, contracts, and event logs.
- Audit stream: append-only PHI access/mutation events.
- Notification service: installment reminders and follow-up tasks.
- CI/CD: automated tests, security checks, controlled releases.

## Threat model (high-level)
Assets:
- PHI, ICD-10 history, quote outputs, payer pricing contracts, consent records.

Actors:
- Care coordinator, clinician, finance admin, payer user, system admin.

Main threats and mitigations:
- Unauthorized PHI access -> strong authn + RBAC + least privilege.
- API abuse -> rate limiting + WAF + input validation.
- Data leakage in logs -> patient ID hashing + safe error responses.
- Tampering with quotes -> immutable audit trail + signed quote IDs.
- Credential compromise -> key rotation + short token TTL + monitoring alerts.

## Security and governance controls
- POPIA purpose limitation: only process fields needed for care and pricing.
- Data minimization: store derived risk features where possible.
- Encryption:
  - In transit: TLS 1.2+.
  - At rest: managed key encryption for DB and backups.
- Access control:
  - `quote:read`, `quote:write`, `admin` roles.
  - Segregate clinical vs pricing operations.
- Audit logging:
  - Actor, action, target hash, timestamp, result.
- Clinical governance:
  - Manual override allowed with reason, approver, and expiry window.

## Repo-ready deliverables implemented
- Pricing logic: `engine/network_one_pricing.py`
- Input/output models: `engine/network_one_models.py`
- Secure API skeleton: `app/network_one_secure_api.py`
- Postgres persistence layer: `engine/network_one_storage.py`
- Postgres migrations: `migrations/postgres/`
- Migration runner: `scripts/migrate_postgres.py`
- Core tests: `tests/test_network_one_pricing.py`

## Setup and run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests
```

Run API:
```bash
export NETWORK_ONE_AUDIT_SALT='replace-with-random-secret'
export NETWORK_ONE_API_TOKENS_JSON='{"demo-writer":{"actor":"pricing-admin","roles":["quote:read","quote:write"]},"demo-reader":{"actor":"auditor","roles":["quote:read"]}}'
export NETWORK_ONE_DATABASE_URL='postgresql://user:pass@localhost:5432/network_one_pricing'
python scripts/migrate_postgres.py
uvicorn app.network_one_secure_api:app --host 0.0.0.0 --port 8000
```

Supabase integration options:
- Use `SUPABASE_DB_URL` directly, or
- Set `SUPABASE_URL` + `SUPABASE_DB_PASSWORD` and let the API derive a pooled Postgres URL.

## Deployment checklist
- Provision managed Postgres with encrypted storage.
- Store secrets in secret manager (not env files in git).
- Enable centralized log shipping and retention policy.
- Enable backup policy and restore drill cadence.
- Enable SAST/DAST in CI before production deployment.
- Document incident response and clinical escalation contacts.
