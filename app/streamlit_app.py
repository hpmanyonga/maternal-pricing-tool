import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
from engine.pricing_engine import PricingEngine
from engine.models import PatientProfile
from engine.coopland_engine import CooplandEngine, COOPLAND_FACTORS

OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs"

# ==============================
# PAGE CONFIG
# ==============================
st.set_page_config(
    page_title="Maternal Pricing Tool",
    page_icon="🏥",
    layout="wide",
)

st.title("Maternal Care Pricing Tool")
st.markdown("Discovery-aligned global fee pricing with additive risk loadings.")


# ==============================
# LOAD ENGINE
# ==============================
@st.cache_resource
def load_engine():
    return PricingEngine(outputs_dir=str(OUTPUTS_DIR))


@st.cache_data
def load_table(name):
    return pd.read_csv(OUTPUTS_DIR / name)


engine = load_engine()

# ==============================
# SIDEBAR – Patient Input
# ==============================
st.sidebar.header("Patient Profile")

plan_type = st.sidebar.selectbox(
    "Discovery Plan",
    options=["KEYCARE", "SMART", "COASTAL_ESSENTIAL", "CLASSIC", "EXECUTIVE"],
    format_func=lambda x: {
        "KEYCARE": "KeyCare (R48,000)",
        "SMART": "Smart (R50,000)",
        "COASTAL_ESSENTIAL": "Coastal & Essential (R52,000)",
        "CLASSIC": "Classic (R55,000)",
        "EXECUTIVE": "Executive (R58,000)",
    }[x],
    index=0,
)

enrollment_route = st.sidebar.radio(
    "Enrollment Window",
    options=["ANTN1A", "ANTN1B"],
    format_func=lambda x: {
        "ANTN1A": "Early (≤15+6 weeks) — ANTN1A",
        "ANTN1B": "Late (16+1 to 20 weeks) — ANTN1B",
    }[x],
    index=0,
)

st.sidebar.divider()
st.sidebar.subheader("Coopland Risk Assessment")

# Group factors by category for cleaner UI
FACTOR_GROUPS = {
    "Demographic": [
        "maternal_age_extremes", "teenage_pregnancy", "short_stature",
        "extreme_weight", "poor_socioeconomic_status",
    ],
    "Obstetric History": [
        "grand_multiparity", "primigravida", "previous_cs",
        "previous_stillbirth", "previous_preterm_delivery", "previous_pph",
        "previous_low_birth_weight", "previous_macrosomia", "history_of_infertility",
    ],
    "Medical Conditions": [
        "chronic_hypertension", "diabetes_mellitus", "cardiac_disease",
        "renal_disease", "epilepsy", "mental_illness", "hiv_positive",
        "anaemia", "rh_negative", "tb_or_recent_infection", "malaria",
    ],
    "Current Pregnancy": [
        "multiple_pregnancy", "abnormal_lie", "recurrent_uti",
        "poor_anc_attendance", "poor_nutrition",
    ],
    "Social / Behavioural": [
        "smoking_or_substance_use", "domestic_violence",
    ],
}

factors_present = {}
for group_name, factor_keys in FACTOR_GROUPS.items():
    with st.sidebar.expander(group_name):
        for key in factor_keys:
            weight = COOPLAND_FACTORS[key]
            label = key.replace("_", " ").title() + f" (+{weight})"
            factors_present[key] = st.checkbox(label, value=False, key=f"coop_{key}")

coopland_engine = CooplandEngine()
coopland_result = coopland_engine.score(factors_present)

risk_category = {
    "LOW": "BASE", "MEDIUM": "MEDIUM", "HIGH": "HIGH"
}[coopland_result.risk_band]

st.sidebar.divider()
st.sidebar.metric("Coopland Score", coopland_result.total_score)
st.sidebar.info(f"Risk band: **{coopland_result.risk_band}** → {coopland_result.extra_consults} extra consults, {coopland_result.extra_ultrasounds} extra scans")

delivery_mode = st.sidebar.selectbox(
    "Delivery Mode",
    options=["NVD", "CS"],
    format_func=lambda x: "Normal Vaginal (NVD)" if x == "NVD" else "Caesarean Section (CS)",
    index=0,
)

chronic_flag = st.sidebar.checkbox("Chronic Condition")
complication_flag = st.sidebar.checkbox("Complications")

# ==============================
# PRICING RESULT
# ==============================
profile = PatientProfile(
    plan_type=plan_type,
    enrollment_route=enrollment_route,
    risk_category=risk_category,
    delivery_mode=delivery_mode,
    chronic_flag=chronic_flag,
    complication_flag=complication_flag,
)

result = engine.price_patient(profile)

st.header("Pricing Result")

col1, col2, col3 = st.columns(3)
col1.metric("Global Fee", f"R {result.global_fee:,.0f}")
col2.metric("Total Add-ons", f"R {result.total_addons:,.0f}")
col3.metric("Final Price", f"R {result.final_price:,.0f}")

# ==============================
# COOPLAND SCORING DETAIL
# ==============================
if coopland_result.risk_drivers:
    st.subheader("Coopland Risk Factors")
    driver_rows = [
        {"Factor": d.replace("_", " ").title(), "Weight": COOPLAND_FACTORS[d]}
        for d in coopland_result.risk_drivers
    ]
    driver_rows.append({"Factor": "TOTAL", "Weight": coopland_result.total_score})
    st.dataframe(
        pd.DataFrame(driver_rows),
        use_container_width=True,
        hide_index=True,
    )

# ==============================
# LINE-ITEM BREAKDOWN
# ==============================
st.subheader("Line-Item Breakdown")

line_items = result.to_line_items()
line_df = pd.DataFrame(line_items)
st.dataframe(
    line_df.style.format({"amount": "R {:,.0f}"}),
    use_container_width=True,
    hide_index=True,
)

# ==============================
# PAYMENT STAGES
# ==============================
st.subheader("Payment Stages")

stage_df = pd.DataFrame([
    {"Stage": result.enrollment_route, "Amount": result.antn1_amount},
    {"Stage": "ANTN2", "Amount": result.antn2_amount},
    {"Stage": "Delivery", "Amount": result.delivery_amount},
])

st.dataframe(
    stage_df.style.format({"Amount": "R {:,.0f}"}),
    use_container_width=True,
    hide_index=True,
)

# ==============================
# ADD-ON BREAKDOWN
# ==============================
if result.total_addons > 0:
    st.subheader("Add-on Breakdown")
    addon_items = [
        {"Add-on": "Risk", "Amount": result.risk_addon},
        {"Add-on": "Chronic", "Amount": result.chronic_addon},
        {"Add-on": "Complication", "Amount": result.complication_addon},
        {"Add-on": "CS Differential", "Amount": result.cs_addon},
    ]
    addon_df = pd.DataFrame([a for a in addon_items if a["Amount"] > 0])
    st.dataframe(
        addon_df.style.format({"Amount": "R {:,.0f}"}),
        use_container_width=True,
        hide_index=True,
    )

# ==============================
# FEE SCHEDULE REFERENCE
# ==============================
st.header("Discovery Fee Schedule Reference")

tab1, tab2, tab3, tab4 = st.tabs([
    "Global Fees by Plan",
    "Risk Add-on Schedule",
    "Consult & Scan Fees",
    "Case Mix Distribution",
])

with tab1:
    fee_df = load_table("global_fee_schedule.csv")
    fmt = {c: "R {:,.0f}" for c in fee_df.columns if c != "plan_type"}
    st.dataframe(fee_df.style.format(fmt), use_container_width=True, hide_index=True)

with tab2:
    risk_df = load_table("risk_addon_schedule.csv")
    st.dataframe(risk_df.style.format({
        "addon_keycare": "R {:,.0f}",
        "addon_other": "R {:,.0f}",
    }), use_container_width=True, hide_index=True)

with tab3:
    consult_df = load_table("consult_fees.csv")
    st.dataframe(consult_df.style.format({
        "consult_fee": "R {:,.0f}",
        "scan_fee": "R {:,.0f}",
    }), use_container_width=True, hide_index=True)

with tab4:
    case_df = load_table("case_mix_distribution.csv")
    st.dataframe(case_df, use_container_width=True, hide_index=True)

# ==============================
# BATCH PRICING
# ==============================
st.header("Batch Pricing — All Plan/Risk Combinations")

plan_filter = st.multiselect(
    "Filter by plan",
    options=["KEYCARE", "SMART", "COASTAL_ESSENTIAL", "CLASSIC", "EXECUTIVE"],
    default=["KEYCARE", "SMART", "COASTAL_ESSENTIAL", "CLASSIC", "EXECUTIVE"],
)

rows = []
for plan in plan_filter:
    for route in ["ANTN1A", "ANTN1B"]:
        for risk in ["BASE", "MEDIUM", "HIGH"]:
            for delivery in ["NVD", "CS"]:
                for chronic in [False, True]:
                    for comp in [False, True]:
                        p = PatientProfile(plan, route, risk, delivery, chronic, comp)
                        r = engine.price_patient(p)
                        rows.append({
                            "Plan": plan,
                            "Route": route,
                            "Risk": risk,
                            "Delivery": delivery,
                            "Chronic": chronic,
                            "Complication": comp,
                            "Global Fee (R)": r.global_fee,
                            "Add-ons (R)": r.total_addons,
                            "Final Price (R)": r.final_price,
                        })

batch_df = pd.DataFrame(rows)
st.dataframe(
    batch_df.style.format({
        "Global Fee (R)": "R {:,.0f}",
        "Add-ons (R)": "R {:,.0f}",
        "Final Price (R)": "R {:,.0f}",
    }),
    use_container_width=True,
    hide_index=True,
)
