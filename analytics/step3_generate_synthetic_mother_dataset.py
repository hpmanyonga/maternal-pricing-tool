"""
Step 3 – Generate a synthetic mother-level dataset aligned with Discovery Health
global fee structure.

Outputs:
    data/mother_level_analytic_dataset.parquet
"""

import numpy as np
import pandas as pd
from pathlib import Path

# ==============================
# CONFIGURATION
# ==============================
POPULATION_SIZE = 15_409
PRICING_YEAR = 2026
DATA_VERSION = "discovery_aligned_v2"
SOURCE_TYPE = "synthetic"

np.random.seed(42)

# ==============================
# DISCOVERY FEE SCHEDULE
# ==============================
GLOBAL_FEES = {
    "KEYCARE":           48_000,
    "SMART":             50_000,
    "COASTAL_ESSENTIAL": 52_000,
    "CLASSIC":           55_000,
    "EXECUTIVE":         58_000,
}

STAGE_PROPORTIONS = {
    "ANTN1A":   0.25,
    "ANTN2":    0.20,
    "DELIVERY": 0.55,
}

ANTN1B_DISCOUNT = 0.50

RISK_ADDONS = {
    "BASE":   {"consults": 0, "scans": 0},
    "MEDIUM": {"consults": 2, "scans": 1},
    "HIGH":   {"consults": 4, "scans": 2},
}

CONSULT_FEE = {
    "KEYCARE": 1_689,
    "SMART": 2_300,
    "COASTAL_ESSENTIAL": 2_300,
    "CLASSIC": 2_300,
    "EXECUTIVE": 2_300,
}

SCAN_FEE = 1_800

CS_ADDON = 2_000
CHRONIC_EXTRA_CONSULTS = 1
COMPLICATION_EXTRA_CONSULTS = 1
COMPLICATION_EXTRA_SCANS = 1


# ==============================
# MAIN
# ==============================
def main():
    base_dir = Path(".")
    data_dir = base_dir / "data"
    data_dir.mkdir(exist_ok=True)

    n = POPULATION_SIZE

    # --------------------------
    # Plan type distribution
    # --------------------------
    plan_names = list(GLOBAL_FEES.keys())
    plan_weights = [0.25, 0.20, 0.20, 0.20, 0.15]
    plan_types = np.random.choice(plan_names, size=n, p=plan_weights)

    # --------------------------
    # Enrollment route: ~80% early, ~20% late
    # --------------------------
    enrollment_route = np.where(
        np.random.rand(n) < 0.80, "ANTN1A", "ANTN1B"
    )

    # --------------------------
    # Coopland score → risk category
    # --------------------------
    coopland_score = np.clip(
        np.random.poisson(lam=2.5, size=n), 0, 15
    ).astype(int)

    risk_category = np.where(
        coopland_score <= 3, "BASE",
        np.where(coopland_score <= 6, "MEDIUM", "HIGH")
    )

    # --------------------------
    # Clinical flags
    # --------------------------
    delivery_mode = np.where(np.random.rand(n) < 0.65, "NVD", "CS")
    chronic_flag = np.random.binomial(1, 0.35, n).astype(bool)
    complication_flag = np.random.binomial(1, 0.25, n).astype(bool)

    # --------------------------
    # Compute costs
    # --------------------------
    global_fee_full = np.array([GLOBAL_FEES[p] for p in plan_types], dtype=float)

    # Stage allocations
    antn1_full = global_fee_full * STAGE_PROPORTIONS["ANTN1A"]
    antn1_amount = np.where(
        enrollment_route == "ANTN1A",
        antn1_full,
        antn1_full * ANTN1B_DISCOUNT,
    )
    antn2_amount = global_fee_full * STAGE_PROPORTIONS["ANTN2"]
    delivery_amount = global_fee_full * STAGE_PROPORTIONS["DELIVERY"]

    # Route-adjusted global fee
    total_global_fee = antn1_amount + antn2_amount + delivery_amount

    # Risk add-ons
    consult_fee = np.array([CONSULT_FEE[p] for p in plan_types], dtype=float)
    extra_consults = np.array([RISK_ADDONS[r]["consults"] for r in risk_category])
    extra_scans = np.array([RISK_ADDONS[r]["scans"] for r in risk_category])
    risk_addon_cost = (extra_consults * consult_fee) + (extra_scans * SCAN_FEE)

    # Chronic add-on
    chronic_addon = np.where(chronic_flag, CHRONIC_EXTRA_CONSULTS * consult_fee, 0.0)

    # Complication add-on
    complication_addon = np.where(
        complication_flag,
        COMPLICATION_EXTRA_CONSULTS * consult_fee + COMPLICATION_EXTRA_SCANS * SCAN_FEE,
        0.0,
    )

    # CS delivery differential
    cs_addon = np.where(delivery_mode == "CS", CS_ADDON, 0.0)

    # Total
    total_cost = total_global_fee + risk_addon_cost + chronic_addon + complication_addon + cs_addon

    # --------------------------
    # Assemble dataset
    # --------------------------
    df = pd.DataFrame({
        "mother_id": range(1, n + 1),
        "plan_type": plan_types,
        "enrollment_route": enrollment_route,
        "coopland_score": coopland_score,
        "risk_category": risk_category,
        "delivery_mode": delivery_mode,
        "chronic_flag": chronic_flag,
        "complication_flag": complication_flag,
        "global_fee": total_global_fee,
        "antn1_amount": antn1_amount,
        "antn2_amount": antn2_amount,
        "delivery_amount": delivery_amount,
        "risk_addon_cost": risk_addon_cost,
        "chronic_addon": chronic_addon,
        "complication_addon": complication_addon,
        "cs_addon": cs_addon,
        "total_cost": total_cost,
        "pricing_year": PRICING_YEAR,
        "source_type": SOURCE_TYPE,
        "data_version": DATA_VERSION,
    })

    out_path = data_dir / "mother_level_analytic_dataset.parquet"
    df.to_parquet(out_path, index=False)
    print(f"✅ Step‑3 complete: {len(df):,} rows → {out_path}")
    print(f"   Mean total cost: R {df['total_cost'].mean():,.0f}")
    print(f"   Min: R {df['total_cost'].min():,.0f}  Max: R {df['total_cost'].max():,.0f}")


if __name__ == "__main__":
    main()
