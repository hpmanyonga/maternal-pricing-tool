import os
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Optional

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from engine.network_one_models import NetworkOneEpisodeQuote


Base = declarative_base()


class QuoteRecord(Base):
    __tablename__ = "episode_quotes"

    id = Column(String(36), primary_key=True)
    patient_hash = Column(String(128), nullable=False, index=True)
    payer_type = Column(String(32), nullable=False)
    delivery_type = Column(String(32), nullable=False)
    complexity_score = Column(Float, nullable=False)
    complexity_tier = Column(String(32), nullable=False, index=True)
    base_price_zar = Column(Float, nullable=False)
    risk_adjusted_price_zar = Column(Float, nullable=False)
    final_price_zar = Column(Float, nullable=False, index=True)
    clinical_bucket_amounts = Column(JSON, nullable=False)
    installment_amounts = Column(JSON, nullable=False)
    rationale = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    installments = relationship("InstallmentRecord", back_populates="quote", cascade="all, delete-orphan")


class InstallmentRecord(Base):
    __tablename__ = "installment_schedules"

    id = Column(String(36), primary_key=True)
    quote_id = Column(String(36), ForeignKey("episode_quotes.id"), nullable=False, index=True)
    stage_key = Column(String(64), nullable=False)
    stage_sequence = Column(Integer, nullable=False)
    amount_zar = Column(Float, nullable=False)
    weight = Column(Float, nullable=False)
    status = Column(String(32), nullable=False, default="PLANNED")
    due_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    quote = relationship("QuoteRecord", back_populates="installments")


class AuditLogRecord(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True)
    actor = Column(String(128), nullable=False, index=True)
    action = Column(String(128), nullable=False, index=True)
    target_hash = Column(String(128), nullable=True, index=True)
    result = Column(String(32), nullable=False, index=True)
    detail = Column(String(512), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)


def resolve_database_url() -> Optional[str]:
    # Preferred explicit overrides
    if os.getenv("NETWORK_ONE_DATABASE_URL"):
        return os.getenv("NETWORK_ONE_DATABASE_URL")
    if os.getenv("SUPABASE_DB_URL"):
        return os.getenv("SUPABASE_DB_URL")
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")

    # Build Supabase pooled Postgres URL from standard Supabase envs
    # Expected:
    # - SUPABASE_URL=https://<project-ref>.supabase.co
    # - SUPABASE_DB_PASSWORD=<db_password>
    # Optional:
    # - SUPABASE_DB_USER (default: postgres)
    # - SUPABASE_DB_NAME (default: postgres)
    # - SUPABASE_POOLER_PORT (default: 6543)
    # - SUPABASE_SSLMODE (default: require)
    supabase_url = os.getenv("SUPABASE_URL")
    db_password = os.getenv("SUPABASE_DB_PASSWORD")
    if not supabase_url or not db_password:
        return None

    parsed = urlparse(supabase_url)
    host = parsed.netloc or supabase_url
    project_ref = host.split(".")[0]
    if not project_ref:
        return None

    db_user = os.getenv("SUPABASE_DB_USER", "postgres")
    db_name = os.getenv("SUPABASE_DB_NAME", "postgres")
    pooler_port = os.getenv("SUPABASE_POOLER_PORT", "6543")
    sslmode = os.getenv("SUPABASE_SSLMODE", "require")

    return (
        f"postgresql://{db_user}.{project_ref}:{db_password}"
        f"@aws-0-eu-west-1.pooler.supabase.com:{pooler_port}/{db_name}"
        f"?sslmode={sslmode}"
    )


class NetworkOneStorage:
    def __init__(self, database_url: str):
        if not database_url:
            raise ValueError("database_url is required")
        self.engine = create_engine(database_url, future=True, pool_pre_ping=True)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)

    def create_schema_for_dev(self) -> None:
        Base.metadata.create_all(self.engine)

    def save_audit_event(
        self,
        actor: str,
        action: str,
        target_hash: Optional[str],
        result: str,
        detail: str,
    ) -> str:
        event_id = str(uuid.uuid4())
        record = AuditLogRecord(
            id=event_id,
            actor=actor,
            action=action,
            target_hash=target_hash,
            result=result,
            detail=detail,
        )
        with self.session_factory() as session:
            try:
                session.add(record)
                session.commit()
            except SQLAlchemyError:
                session.rollback()
                raise
        return event_id

    def save_quote(
        self,
        quote: NetworkOneEpisodeQuote,
        patient_hash: str,
        delivery_type: str,
    ) -> str:
        quote_id = str(uuid.uuid4())
        quote_record = QuoteRecord(
            id=quote_id,
            patient_hash=patient_hash,
            payer_type=quote.payer_type,
            delivery_type=delivery_type,
            complexity_score=quote.complexity_score,
            complexity_tier=quote.complexity_tier,
            base_price_zar=quote.base_price_zar,
            risk_adjusted_price_zar=quote.risk_adjusted_price_zar,
            final_price_zar=quote.final_price_zar,
            clinical_bucket_amounts=quote.clinical_bucket_amounts,
            installment_amounts=quote.installment_amounts,
            rationale=quote.rationale,
        )

        total = quote.final_price_zar if quote.final_price_zar else 1.0
        installments = []
        for idx, (stage_key, amount) in enumerate(quote.installment_amounts.items(), start=1):
            installments.append(
                InstallmentRecord(
                    id=str(uuid.uuid4()),
                    quote_id=quote_id,
                    stage_key=stage_key,
                    stage_sequence=idx,
                    amount_zar=float(amount),
                    weight=round(float(amount) / float(total), 8),
                    status="PLANNED",
                )
            )

        with self.session_factory() as session:
            try:
                session.add(quote_record)
                session.add_all(installments)
                session.commit()
            except SQLAlchemyError:
                session.rollback()
                raise
        return quote_id
