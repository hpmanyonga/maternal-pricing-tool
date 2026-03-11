import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.network_one_icd10 import explain_icd10_matches
from engine.network_one_models import NetworkOneEpisodeInput
from engine.network_one_pricing import NetworkOneEpisodePricingEngine


st.set_page_config(page_title="Network One Episode Pricing", page_icon="🏥", layout="centered")
st.title("Network One Episode Pricing")
st.caption("Early ANC to Early PNC (including delivery)")

engine = NetworkOneEpisodePricingEngine()
config = engine.config

patient_id = st.text_input("Patient ID", value="Mother 100")
payer_type = st.selectbox("Payer Type", options=["MEDICAL_AID", "CASH"])
delivery_type = st.selectbox("Delivery Type", options=["UNKNOWN", "NVD", "CS"])

st.subheader("Complexity Indicators")
chronic = st.checkbox("Chronic")
pregnancy_medical = st.checkbox("Pregnancy medical")
pregnancy_anatomical = st.checkbox("Pregnancy anatomical")
risk_factor = st.checkbox("Risk factor")
unrelated_medical = st.checkbox("Unrelated medical")
unrelated_anatomical = st.checkbox("Unrelated anatomical")

base_price_zar = st.number_input(
    "Base price (ZAR)",
    min_value=1.0,
    value=float(config["base_price_zar"]),
    step=500.0,
)

icd10_codes_text = st.text_area(
    "ICD10 Codes (comma or newline separated)",
    value="",
)
icd10_descriptions_text = st.text_area(
    "ICD10 Descriptions (one per line)",
    value="",
)
st.caption("ICD10 fields are optional. Leave blank to price from manual indicators only.")


def _parse_lines(raw: str):
    items = []
    for part in raw.replace(",", "\n").splitlines():
        cleaned = part.strip()
        if cleaned:
            items.append(cleaned)
    return items


parsed_codes = _parse_lines(icd10_codes_text)
parsed_desc = _parse_lines(icd10_descriptions_text)

quote_tab, explain_tab = st.tabs(["Quote", "Explain ICD10"])

with quote_tab:
    if st.button("Generate Quote"):
        profile = NetworkOneEpisodeInput(
            patient_id=patient_id,
            payer_type=payer_type,
            delivery_type=delivery_type,
            chronic=chronic,
            pregnancy_medical=pregnancy_medical,
            pregnancy_anatomical=pregnancy_anatomical,
            risk_factor=risk_factor,
            unrelated_medical=unrelated_medical,
            unrelated_anatomical=unrelated_anatomical,
            icd10_codes=parsed_codes,
            icd10_descriptions=parsed_desc,
            base_price_zar=base_price_zar,
            installment_weights=config["installment_weights"],
        )
        quote = engine.quote(profile)

        col1, col2, col3 = st.columns(3)
        col1.metric("Complexity Score", f"{quote.complexity_score:.1f}")
        col2.metric("Tier", quote.complexity_tier.replace("_", " "))
        col3.metric("Final Price", f"R {quote.final_price_zar:,.2f}")

        st.subheader("Installments")
        for stage, amount in quote.installment_amounts.items():
            st.write(f"- {stage}: R {amount:,.2f}")

        st.subheader("Clinical Cost Buckets")
        for bucket, amount in quote.clinical_bucket_amounts.items():
            share = (amount / quote.final_price_zar) * 100 if quote.final_price_zar else 0
            st.write(f"- {bucket}: R {amount:,.2f} ({share:.1f}%)")

        st.subheader("Rationale")
        st.json(quote.rationale)

with explain_tab:
    if st.button("Explain ICD10"):
        explanation = explain_icd10_matches(
            codes=parsed_codes,
            descriptions=parsed_desc,
        )
        preview_profile = NetworkOneEpisodeInput(
            patient_id=patient_id or "EXPLAIN_PREVIEW",
            payer_type=payer_type,
            delivery_type=delivery_type,
            chronic=chronic,
            pregnancy_medical=pregnancy_medical,
            pregnancy_anatomical=pregnancy_anatomical,
            risk_factor=risk_factor,
            unrelated_medical=unrelated_medical,
            unrelated_anatomical=unrelated_anatomical,
            icd10_codes=parsed_codes,
            icd10_descriptions=parsed_desc,
            base_price_zar=base_price_zar,
            installment_weights=config["installment_weights"],
        )
        preview_quote = engine.quote(preview_profile)

        col1, col2, col3 = st.columns(3)
        col1.metric("Preview Score", f"{preview_quote.complexity_score:.1f}")
        col2.metric("Preview Tier", preview_quote.complexity_tier.replace("_", " "))
        col3.metric("Preview Price", f"R {preview_quote.final_price_zar:,.2f}")

        st.subheader("Inferred Indicators")
        st.write(", ".join(explanation["inferred_indicators"]) or "None")

        st.subheader("Code Matches")
        st.json(explanation["code_matches"])

        st.subheader("Description Matches")
        st.json(explanation["description_matches"])

        with st.expander("Match Trace"):
            for line in explanation["trace"]:
                st.write(f"- {line}")
