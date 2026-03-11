import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.network_one_models import NetworkOneEpisodeInput
from engine.network_one_pricing import NetworkOneEpisodePricingEngine


st.set_page_config(page_title="NOH QuickQuote", page_icon="🤰", layout="wide")
st.title("NOH QuickQuote")
st.caption("Get a rough estimate for your maternity care in under a minute.")

st.markdown(
    """
    <style>
      .stApp {
        background: radial-gradient(circle at top right, #eef7ff 0%, #ffffff 35%, #ffffff 100%);
      }
      .noh-card {
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 18px 20px;
        background: #ffffff;
        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.05);
      }
      .noh-kicker {
        font-size: 0.85rem;
        color: #486581;
        letter-spacing: 0.02em;
        text-transform: uppercase;
      }
      .noh-price {
        font-size: 2rem;
        font-weight: 700;
        color: #102a43;
        line-height: 1.15;
        margin: 0.2rem 0 0.4rem 0;
      }
      .noh-note {
        color: #486581;
        font-size: 0.92rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

engine = NetworkOneEpisodePricingEngine()
config = engine.config

left_col, right_col = st.columns([1.25, 1], gap="large")

with left_col:
    st.subheader("Your Estimate Inputs")
    payer_ui = st.segmented_control(
        "How are you paying?",
        options=["Medical aid", "Cash"],
        default="Medical aid",
    )
    delivery_ui = st.segmented_control(
        "Planned delivery type",
        options=["Vaginal birth", "Caesarean birth", "Not sure yet"],
        default="Not sure yet",
    )
    timing_ui = st.segmented_control(
        "Timing",
        options=["Planning pregnancy", "Pregnant now"],
        default="Pregnant now",
    )

    gestation_group = "Under 12 weeks"
    if timing_ui == "Pregnant now":
        gestation_group = st.select_slider(
            "How far along are you?",
            options=["Under 12 weeks", "12 to 20 weeks", "20 to 28 weeks", "28+ weeks"],
            value="Under 12 weeks",
        )

    st.subheader("Health factors that affect price")
    st.caption("Select any that apply.")

    chronic = st.toggle("Long-term health conditions")
    with st.expander("Examples"):
        st.write("HIV, diabetes, thyroid disease, epilepsy, hypertension")

    pregnancy_medical = st.toggle("Pregnancy-related medical problems")
    with st.expander("Examples", expanded=False):
        st.write("Gestational diabetes, gestational hypertension, severe vomiting")

    pregnancy_anatomical = st.toggle("Pregnancy-related anatomical problems")
    with st.expander("Examples ", expanded=False):
        st.write("Placenta previa, vasa previa, fibroids in pregnancy")

    risk_factor = st.toggle("Important risk factors")
    with st.expander("Examples  ", expanded=False):
        st.write("First pregnancy, obesity, previous caesarean, previous stillbirth/premature baby")

    unrelated_medical = st.toggle("Other medical conditions")
    with st.expander("Examples   ", expanded=False):
        st.write("Any non-pregnancy medical condition")

    unrelated_anatomical = st.toggle("Other anatomical conditions")
    with st.expander("Examples    ", expanded=False):
        st.write("Any non-pregnancy anatomical issue")


def _round_to_100(value: float) -> int:
    return int(round(value / 100.0) * 100)


payer_map = {"Medical aid": "MEDICAL_AID", "Cash": "CASH"}
delivery_map = {"Vaginal birth": "NVD", "Caesarean birth": "CS", "Not sure yet": "UNKNOWN"}
payer_factor = {"MEDICAL_AID": 1.0, "CASH": 0.94}
timing_factor = {
    "Planning pregnancy": 0.98,
    "Under 12 weeks": 1.00,
    "12 to 20 weeks": 1.03,
    "20 to 28 weeks": 1.07,
    "28+ weeks": 1.12,
}

payer_type = payer_map[payer_ui]
delivery_type = delivery_map[delivery_ui]
base_anchor = float(config["base_price_zar"])
base_price_zar = base_anchor * payer_factor[payer_type] * timing_factor.get(gestation_group, 1.0)

profile = NetworkOneEpisodeInput(
    patient_id="PUBLIC_QUICKQUOTE",
    payer_type=payer_type,
    delivery_type=delivery_type,
    chronic=chronic,
    pregnancy_medical=pregnancy_medical,
    pregnancy_anatomical=pregnancy_anatomical,
    risk_factor=risk_factor,
    unrelated_medical=unrelated_medical,
    unrelated_anatomical=unrelated_anatomical,
    base_price_zar=base_price_zar,
    installment_weights=config["installment_weights"],
)
quote = engine.quote(profile)

active_factors = sum(
    [chronic, pregnancy_medical, pregnancy_anatomical, risk_factor, unrelated_medical, unrelated_anatomical]
)
uncertainty = 0.08
if delivery_type == "UNKNOWN":
    uncertainty += 0.05
if gestation_group in ("20 to 28 weeks", "28+ weeks"):
    uncertainty += 0.03
uncertainty += min(active_factors * 0.01, 0.05)
uncertainty = min(uncertainty, 0.20)

estimate_mid = quote.final_price_zar
estimate_low = _round_to_100(estimate_mid * (1 - uncertainty))
estimate_high = _round_to_100(estimate_mid * (1 + uncertainty))
monthly_from = _round_to_100(estimate_mid / 12.0)

tier_label_map = {
    "TIER_1_LOW": "Lower-complexity maternity estimate",
    "TIER_2_MODERATE": "Standard-complexity maternity estimate",
    "TIER_3_HIGH": "Higher-complexity maternity estimate",
    "TIER_4_VERY_HIGH": "High-support maternity estimate",
}
likely_category = tier_label_map.get(quote.complexity_tier, "Maternity estimate")

price_drivers = []
if delivery_type == "CS":
    price_drivers.append("Caesarean delivery")
elif delivery_type == "UNKNOWN":
    price_drivers.append("Delivery method still undecided")
if timing_ui == "Pregnant now" and gestation_group in ("20 to 28 weeks", "28+ weeks"):
    price_drivers.append("Later pregnancy stage")
if active_factors > 0:
    price_drivers.append("Health risk factors selected")
if not price_drivers:
    price_drivers.append("Standard maternity pathway")

with right_col:
    st.markdown('<div class="noh-card">', unsafe_allow_html=True)
    st.markdown('<div class="noh-kicker">Estimated Price</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="noh-price">R {estimate_low:,.0f} to R {estimate_high:,.0f}</div>',
        unsafe_allow_html=True,
    )
    st.write(f"**Likely category:** {likely_category}")
    st.markdown(
        '<div class="noh-note">Based on your answers. Final quote follows clinical review.</div>',
        unsafe_allow_html=True,
    )
    st.write("")
    st.write("**What usually pushes price up**")
    for item in price_drivers:
        st.write(f"- {item}")
    st.write("")
    st.write("**Typical inclusions**")
    st.write("- Antenatal care")
    st.write("- Delivery care")
    st.write("- Early postnatal care")
    st.write("")
    st.write(f"Possible from **R {monthly_from:,.0f} per month**")
    if st.button("Request my exact quote", type="primary", use_container_width=True):
        st.success("Thanks. A care team member can now contact you for a personalised quote.")
    st.markdown("</div>", unsafe_allow_html=True)

with st.expander("What affects this estimate?"):
    st.write(
        "The estimate changes based on payer type, delivery plan, pregnancy stage, and selected health factors."
    )
