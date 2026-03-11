import unittest

from engine.network_one_models import NetworkOneEpisodeInput
from engine.network_one_pricing import NetworkOneEpisodePricingEngine


class NetworkOnePricingTests(unittest.TestCase):
    def setUp(self):
        self.engine = NetworkOneEpisodePricingEngine()

    def test_tier_two_quote_in_anchor_range(self):
        payload = NetworkOneEpisodeInput(
            patient_id="Mother 100",
            payer_type="MEDICAL_AID",
            delivery_type="UNKNOWN",
            pregnancy_medical=True,
            pregnancy_anatomical=True,
        )
        quote = self.engine.quote(payload)
        self.assertEqual(quote.complexity_tier, "TIER_2_MODERATE")
        self.assertGreater(quote.final_price_zar, quote.base_price_zar)

    def test_cs_high_complexity_prices_higher(self):
        low = self.engine.quote(
            NetworkOneEpisodeInput(
                patient_id="Mother 1",
                payer_type="CASH",
                delivery_type="NVD",
            )
        )
        high = self.engine.quote(
            NetworkOneEpisodeInput(
                patient_id="Mother 2",
                payer_type="MEDICAL_AID",
                delivery_type="CS",
                chronic=True,
                pregnancy_medical=True,
                pregnancy_anatomical=True,
                unrelated_medical=True,
                unrelated_anatomical=True,
            )
        )
        self.assertGreater(high.final_price_zar, low.final_price_zar)
        self.assertEqual(high.complexity_tier, "TIER_4_VERY_HIGH")

    def test_multiplier_changes_smoothly_with_score(self):
        q1 = self.engine.quote(
            NetworkOneEpisodeInput(
                patient_id="S1",
                payer_type="MEDICAL_AID",
                delivery_type="NVD",
                pregnancy_anatomical=True,  # +1
            )
        )
        q2 = self.engine.quote(
            NetworkOneEpisodeInput(
                patient_id="S2",
                payer_type="MEDICAL_AID",
                delivery_type="NVD",
                pregnancy_anatomical=True,
                risk_factor=True,  # +1 more
            )
        )
        self.assertGreater(q2.final_price_zar, q1.final_price_zar)

    def test_installments_sum_to_total(self):
        quote = self.engine.quote(
            NetworkOneEpisodeInput(
                patient_id="Mother 3",
                payer_type="CASH",
                delivery_type="UNKNOWN",
                chronic=True,
            )
        )
        total_installments = round(sum(quote.installment_amounts.values()), 2)
        self.assertEqual(total_installments, round(quote.final_price_zar, 2))

    def test_invalid_installment_weights_raise(self):
        bad = NetworkOneEpisodeInput(
            patient_id="Mother 4",
            payer_type="MEDICAL_AID",
            installment_weights={"booking_12_16w": 0.6, "delivery_event": 0.6},
        )
        with self.assertRaises(ValueError):
            self.engine.quote(bad)

    def test_icd10_inference_impacts_score(self):
        manual = self.engine.quote(
            NetworkOneEpisodeInput(
                patient_id="Mother 5",
                payer_type="MEDICAL_AID",
                delivery_type="NVD",
            )
        )
        inferred = self.engine.quote(
            NetworkOneEpisodeInput(
                patient_id="Mother 6",
                payer_type="MEDICAL_AID",
                delivery_type="NVD",
                icd10_codes=["O14.1", "I10"],
                icd10_descriptions=["Severe preeclampsia with hypertension"],
            )
        )
        self.assertGreater(inferred.complexity_score, manual.complexity_score)
        self.assertIn("pregnancy_medical", inferred.rationale["icd10_inferred_indicators"])
        self.assertIn("chronic", inferred.rationale["icd10_inferred_indicators"])

    def test_delivery_bucket_is_majority_share(self):
        nvd = self.engine.quote(
            NetworkOneEpisodeInput(
                patient_id="Mother 7",
                payer_type="MEDICAL_AID",
                delivery_type="NVD",
            )
        )
        cs = self.engine.quote(
            NetworkOneEpisodeInput(
                patient_id="Mother 8",
                payer_type="MEDICAL_AID",
                delivery_type="CS",
            )
        )
        nvd_share = nvd.clinical_bucket_amounts["delivery_admission_and_specialist"] / nvd.final_price_zar
        cs_share = cs.clinical_bucket_amounts["delivery_admission_and_specialist"] / cs.final_price_zar
        self.assertGreaterEqual(nvd_share, 0.65)
        self.assertGreaterEqual(cs_share, 0.60)

    def test_cs_delivery_floor_enforced(self):
        cs = self.engine.quote(
            NetworkOneEpisodeInput(
                patient_id="Mother 9",
                payer_type="MEDICAL_AID",
                delivery_type="CS",
                base_price_zar=42000,
            )
        )
        self.assertGreaterEqual(
            cs.clinical_bucket_amounts["delivery_admission_and_specialist"],
            38000.0,
        )
        self.assertGreater(cs.final_price_zar, 42000.0)


if __name__ == "__main__":
    unittest.main()
