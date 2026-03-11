CREATE TABLE IF NOT EXISTS quote_requests (
  id UUID PRIMARY KEY,
  quote_id UUID NULL REFERENCES episode_quotes(id) ON DELETE SET NULL,
  full_name VARCHAR(160) NOT NULL,
  mobile VARCHAR(32) NOT NULL,
  email VARCHAR(160) NULL,
  preferred_contact VARCHAR(32) NOT NULL,
  notes VARCHAR(1024) NULL,
  payer_type VARCHAR(32) NOT NULL,
  delivery_type VARCHAR(32) NOT NULL,
  gestation_group VARCHAR(32) NOT NULL,
  estimate_low_zar DOUBLE PRECISION NOT NULL,
  estimate_high_zar DOUBLE PRECISION NOT NULL,
  estimate_mid_zar DOUBLE PRECISION NOT NULL,
  installment_count INTEGER NULL,
  installment_low_zar DOUBLE PRECISION NULL,
  installment_high_zar DOUBLE PRECISION NULL,
  selected_factors JSONB NOT NULL DEFAULT '[]'::jsonb,
  status VARCHAR(32) NOT NULL DEFAULT 'NEW',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quote_requests_quote_id ON quote_requests (quote_id);
CREATE INDEX IF NOT EXISTS idx_quote_requests_mobile ON quote_requests (mobile);
CREATE INDEX IF NOT EXISTS idx_quote_requests_email ON quote_requests (email);
CREATE INDEX IF NOT EXISTS idx_quote_requests_status ON quote_requests (status);
CREATE INDEX IF NOT EXISTS idx_quote_requests_created_at ON quote_requests (created_at);
