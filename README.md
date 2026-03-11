# Maternal Pricing Tool

Discovery Health-aligned pricing engine for maternity care packages.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install pandas pyarrow streamlit numpy
```

## Pipeline

```bash
# 1. Generate synthetic dataset (15,409 records)
python analytics/step3_generate_synthetic_mother_dataset.py

# 2. Generate pricing tables
python analytics/step4_generate_tables.py

# 3. Test pricing engine
python engine/pricing_engine.py

# 4. Launch dashboard
streamlit run app/streamlit_app.py
```

## Pricing Model

Based on Discovery Health's maternity global fee structure:

**Global fees by plan (ANTN1A route):**

| Plan | ANTN1A | ANTN2 | Delivery | Total |
|------|--------|-------|----------|-------|
| KeyCare | R12,000 | R9,600 | R26,400 | R48,000 |
| Smart | R12,500 | R10,000 | R27,500 | R50,000 |
| Coastal & Essential | R13,000 | R10,400 | R28,600 | R52,000 |
| Classic | R13,750 | R11,000 | R30,250 | R55,000 |
| Executive | R14,500 | R11,600 | R31,900 | R58,000 |

**Additive risk loadings** (Coopland score):
- Base (≤3): No add-ons
- Medium (4–6): +2 consults, +1 scan
- High (≥7): +4 consults, +2 scans

**Formula:**
```
Final Price = Global Fee (route-adjusted) + Risk Add-on + Chronic Add-on + Complication Add-on + CS Differential
```

## Project Structure

```
maternal-pricing-tool/
├── data/                          # Parquet dataset
├── analytics/
│   ├── step3_generate_synthetic_mother_dataset.py
│   └── step4_generate_tables.py
├── outputs/                       # Pricing CSVs
├── engine/
│   ├── models.py                  # PatientProfile, PricingResult
│   ├── loaders.py                 # CSV loading
│   ├── rules.py                   # Additive pricing rules
│   └── pricing_engine.py          # Core engine
├── app/
│   └── streamlit_app.py           # Dashboard
└── README.md
```

## Network One Episode Pricing (Secure v1)

Risk-rated pricing for the episode from early ANC to early PNC (including delivery), with secure API scaffolding.

### Run tests

```bash
python -m unittest discover -s tests
```

### Run secure API

```bash
export NETWORK_ONE_AUDIT_SALT='replace-with-random-secret'
export NETWORK_ONE_API_TOKENS_JSON='{"demo-writer":{"actor":"pricing-admin","roles":["quote:read","quote:write"]},"demo-reader":{"actor":"auditor","roles":["quote:read"]}}'
export NETWORK_ONE_DATABASE_URL='postgresql://user:pass@localhost:5432/network_one_pricing'
python scripts/migrate_postgres.py
uvicorn app.network_one_secure_api:app --host 0.0.0.0 --port 8000
```

API docs: `http://localhost:8000/docs`

If you require database writes for quotes/audits, enforce it:

```bash
export NETWORK_ONE_DB_REQUIRED='true'
```

JWT/OIDC-ready auth (optional, replaces static token map when enabled):

```bash
# HS256 shared-secret mode (simple)
export NETWORK_ONE_JWT_SECRET='replace-with-strong-secret'
export NETWORK_ONE_JWT_ALGORITHM='HS256'
export NETWORK_ONE_JWT_ROLES_CLAIM='roles'
export NETWORK_ONE_JWT_ACTOR_CLAIM='sub'

# Or OIDC JWKS mode
# export NETWORK_ONE_JWKS_URL='https://issuer/.well-known/jwks.json'
# export NETWORK_ONE_JWT_ISSUER='https://issuer/'
# export NETWORK_ONE_JWT_AUDIENCE='network-one-pricing-api'
```

Supabase-compatible DB env options (choose one):

```bash
# Option A: direct
export SUPABASE_DB_URL='postgresql://postgres.<project-ref>:<password>@<pooler-host>:6543/postgres?sslmode=require'

# Option B: derived from standard Supabase URL
export SUPABASE_URL='https://<project-ref>.supabase.co'
export SUPABASE_DB_PASSWORD='<db-password>'
# optional overrides:
# export SUPABASE_DB_USER='postgres'
# export SUPABASE_DB_NAME='postgres'
# export SUPABASE_POOLER_PORT='6543'
# export SUPABASE_SSLMODE='require'
```

Detailed approach and governance notes:
- `docs/network_one_episode_pricing_approach.md`

### Run Network One Streamlit screen

```bash
streamlit run app/network_one_streamlit.py
```

### Run CLI quote

```bash
python scripts/quote_network_one.py --input data/network_one_sample_quote_input.json
```

The quote payload can include:
- `icd10_codes` (e.g. `["O14.1","I10"]`)
- `icd10_descriptions` (free-text diagnosis descriptions)

New API endpoint:
- `POST /v1/episodes/icd10-explain`
  Returns ICD10-to-indicator match details and a preview complexity tier/price.

Streamlit now includes an `Explain ICD10` tab with:
- code and description matching
- inferred indicators
- preview score/tier/price

Clinical cost buckets are now explicitly surfaced in outputs:
- `early_anc`
- `mid_anc`
- `delivery_admission_and_specialist`
- `early_pnc`

Default proportions are calibrated from your funder dataset period split, with delivery as the dominant cost locus.
Delivery bucket floors are also enforced by mode (configurable) to prevent implausibly low delivery-period amounts.
