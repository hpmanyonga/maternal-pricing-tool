CREATE TABLE IF NOT EXISTS episode_quotes (
  id UUID PRIMARY KEY,
  patient_hash VARCHAR(128) NOT NULL,
  payer_type VARCHAR(32) NOT NULL,
  delivery_type VARCHAR(32) NOT NULL,
  complexity_score DOUBLE PRECISION NOT NULL,
  complexity_tier VARCHAR(32) NOT NULL,
  base_price_zar DOUBLE PRECISION NOT NULL,
  risk_adjusted_price_zar DOUBLE PRECISION NOT NULL,
  final_price_zar DOUBLE PRECISION NOT NULL,
  clinical_bucket_amounts JSONB NOT NULL,
  installment_amounts JSONB NOT NULL,
  rationale JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_episode_quotes_patient_hash ON episode_quotes (patient_hash);
CREATE INDEX IF NOT EXISTS idx_episode_quotes_complexity_tier ON episode_quotes (complexity_tier);
CREATE INDEX IF NOT EXISTS idx_episode_quotes_final_price ON episode_quotes (final_price_zar);

CREATE TABLE IF NOT EXISTS installment_schedules (
  id UUID PRIMARY KEY,
  quote_id UUID NOT NULL REFERENCES episode_quotes(id) ON DELETE CASCADE,
  stage_key VARCHAR(64) NOT NULL,
  stage_sequence INTEGER NOT NULL,
  amount_zar DOUBLE PRECISION NOT NULL,
  weight DOUBLE PRECISION NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'PLANNED',
  due_date TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_installment_schedules_quote_id ON installment_schedules (quote_id);
CREATE INDEX IF NOT EXISTS idx_installment_schedules_status ON installment_schedules (status);

CREATE TABLE IF NOT EXISTS audit_logs (
  id UUID PRIMARY KEY,
  actor VARCHAR(128) NOT NULL,
  action VARCHAR(128) NOT NULL,
  target_hash VARCHAR(128) NULL,
  result VARCHAR(32) NOT NULL,
  detail VARCHAR(512) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs (actor);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_result ON audit_logs (result);
CREATE INDEX IF NOT EXISTS idx_audit_logs_target_hash ON audit_logs (target_hash);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs (created_at);
