import pandas as pd
from pathlib import Path


def load_series(filepath, index_col, value_col):
    """Load a two-column CSV as an indexed Series."""
    return pd.read_csv(filepath).set_index(index_col)[value_col]


def load_pricing_tables(outputs_dir="outputs"):
    """Load all Discovery-aligned pricing tables."""
    p = Path(outputs_dir)
    tables = {}

    for name, filename in [
        ("global_fee_schedule", "global_fee_schedule.csv"),
        ("risk_addon_schedule", "risk_addon_schedule.csv"),
        ("consult_fees", "consult_fees.csv"),
        ("delivery_mode_addon", "delivery_mode_addon.csv"),
        ("chronic_addon", "chronic_addon.csv"),
        ("complication_addon", "complication_addon.csv"),
        ("cost_summary", "cost_summary_by_plan.csv"),
        ("case_mix", "case_mix_distribution.csv"),
    ]:
        path = p / filename
        if path.exists():
            tables[name] = pd.read_csv(path)

    return tables
