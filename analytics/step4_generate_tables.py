"""
Step 4 – Generate pricing tables aligned with Discovery Health global fee structure.

Reads:
    data/mother_level_analytic_dataset.parquet

Outputs (CSV):
    outputs/global_fee_schedule.csv
    outputs/risk_addon_schedule.csv
    outputs/consult_fees.csv
    outputs/delivery_mode_addon.csv
    outputs/chronic_addon.csv
    outputs/complication_addon.csv
    outputs/cost_summary_by_plan.csv
    outputs/case_mix_distribution.csv
"""

import pandas as pd
from pathlib import Path

# ==============================
# DISCOVERY FEE SCHEDULE (deterministic)
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

CONSULT_FEE = {
    "KEYCARE": 1_689,
    "SMART": 2_300,
    "COASTAL_ESSENTIAL": 2_300,
    "CLASSIC": 2_300,
    "EXECUTIVE": 2_300,
}

SCAN_FEE = 1_800
CS_ADDON = 2_000


# ==============================
# MAIN
# ==============================
def main():
    base_dir = Path(".")
    data_path = base_dir / "data" / "mother_level_analytic_dataset.parquet"
    out_dir = base_dir / "outputs"
    out_dir.mkdir(exist_ok=True)

    df = pd.read_parquet(data_path)

    # --------------------------
    # 1. Global fee schedule (deterministic)
    # --------------------------
    rows = []
    for plan, total in GLOBAL_FEES.items():
        antn1a = total * STAGE_PROPORTIONS["ANTN1A"]
        antn1b = antn1a * ANTN1B_DISCOUNT
        antn2 = total * STAGE_PROPORTIONS["ANTN2"]
        delivery = total * STAGE_PROPORTIONS["DELIVERY"]
        rows.append({
            "plan_type": plan,
            "antn1a_fee": antn1a,
            "antn1b_fee": antn1b,
            "antn2_fee": antn2,
            "delivery_fee": delivery,
            "total_antn1a_route": total,
            "total_antn1b_route": antn1b + antn2 + delivery,
        })
    pd.DataFrame(rows).to_csv(out_dir / "global_fee_schedule.csv", index=False)

    # --------------------------
    # 2. Risk add-on schedule (deterministic)
    # --------------------------
    risk_rows = []
    for risk, info in [("BASE", {"consults": 0, "scans": 0}),
                       ("MEDIUM", {"consults": 2, "scans": 1}),
                       ("HIGH", {"consults": 4, "scans": 2})]:
        addon_keycare = info["consults"] * CONSULT_FEE["KEYCARE"] + info["scans"] * SCAN_FEE
        addon_other = info["consults"] * CONSULT_FEE["SMART"] + info["scans"] * SCAN_FEE
        risk_rows.append({
            "risk_category": risk,
            "coopland_range": {"BASE": "0-3", "MEDIUM": "4-6", "HIGH": "7+"}[risk],
            "extra_consults": info["consults"],
            "extra_scans": info["scans"],
            "addon_keycare": addon_keycare,
            "addon_other": addon_other,
        })
    pd.DataFrame(risk_rows).to_csv(out_dir / "risk_addon_schedule.csv", index=False)

    # --------------------------
    # 3. Consult fees by plan (deterministic)
    # --------------------------
    consult_rows = [
        {"plan_type": plan, "consult_fee": fee, "scan_fee": SCAN_FEE}
        for plan, fee in CONSULT_FEE.items()
    ]
    pd.DataFrame(consult_rows).to_csv(out_dir / "consult_fees.csv", index=False)

    # --------------------------
    # 4. Delivery mode add-on (deterministic)
    # --------------------------
    pd.DataFrame([
        {"delivery_mode": "NVD", "addon": 0},
        {"delivery_mode": "CS", "addon": CS_ADDON},
    ]).to_csv(out_dir / "delivery_mode_addon.csv", index=False)

    # --------------------------
    # 5. Chronic add-on (deterministic)
    # --------------------------
    chronic_rows = []
    for flag in [False, True]:
        chronic_rows.append({
            "chronic_flag": flag,
            "addon_consults": 1 if flag else 0,
            "addon_keycare": CONSULT_FEE["KEYCARE"] if flag else 0,
            "addon_other": CONSULT_FEE["SMART"] if flag else 0,
        })
    pd.DataFrame(chronic_rows).to_csv(out_dir / "chronic_addon.csv", index=False)

    # --------------------------
    # 6. Complication add-on (deterministic)
    # --------------------------
    comp_rows = []
    for flag in [False, True]:
        comp_rows.append({
            "complication_flag": flag,
            "addon_consults": 1 if flag else 0,
            "addon_scans": 1 if flag else 0,
            "addon_keycare": (CONSULT_FEE["KEYCARE"] + SCAN_FEE) if flag else 0,
            "addon_other": (CONSULT_FEE["SMART"] + SCAN_FEE) if flag else 0,
        })
    pd.DataFrame(comp_rows).to_csv(out_dir / "complication_addon.csv", index=False)

    # --------------------------
    # 7. Cost summary by plan (from synthetic data)
    # --------------------------
    df.groupby("plan_type").agg(
        n_mothers=("mother_id", "count"),
        mean_global_fee=("global_fee", "mean"),
        mean_risk_addon=("risk_addon_cost", "mean"),
        mean_chronic_addon=("chronic_addon", "mean"),
        mean_complication_addon=("complication_addon", "mean"),
        mean_cs_addon=("cs_addon", "mean"),
        mean_total_cost=("total_cost", "mean"),
    ).round(0).reset_index().to_csv(out_dir / "cost_summary_by_plan.csv", index=False)

    # --------------------------
    # 8. Case-mix distribution (from synthetic data)
    # --------------------------
    df.groupby(
        ["plan_type", "enrollment_route", "risk_category",
         "delivery_mode", "chronic_flag", "complication_flag"]
    ).size().reset_index(name="count") \
     .to_csv(out_dir / "case_mix_distribution.csv", index=False)

    print("✅ Step‑4 complete: pricing tables written to outputs/")


if __name__ == "__main__":
    main()
