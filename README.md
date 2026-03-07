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
