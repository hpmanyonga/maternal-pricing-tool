from typing import Dict, Tuple

from engine.network_one_config import load_network_one_config
from engine.network_one_icd10 import infer_indicators_from_icd10
from engine.network_one_models import NetworkOneEpisodeInput, NetworkOneEpisodeQuote


class NetworkOneEpisodePricingEngine:
    """
    Risk-rated pricing for the maternity episode from Early ANC to Early PNC.
    """

    def __init__(self, config_path: str = None):
        self.config = load_network_one_config(config_path)

    def compute_complexity_score(self, input_data: NetworkOneEpisodeInput) -> float:
        inferred_indicators, _ = infer_indicators_from_icd10(
            codes=input_data.icd10_codes,
            descriptions=input_data.icd10_descriptions,
        )
        score = 0.0
        for key, weight in self.config["risk_weights"].items():
            if getattr(input_data, key) or key in inferred_indicators:
                score += weight
        if input_data.delivery_type == "CS":
            score += 2.0
        return score

    def _score_components(self, input_data: NetworkOneEpisodeInput) -> Dict[str, float]:
        inferred_indicators, _ = infer_indicators_from_icd10(
            codes=input_data.icd10_codes,
            descriptions=input_data.icd10_descriptions,
        )
        components: Dict[str, float] = {}
        for key, weight in self.config["risk_weights"].items():
            if getattr(input_data, key) or key in inferred_indicators:
                components[key] = float(weight)
        if input_data.delivery_type == "CS":
            components["delivery_cs"] = 2.0
        return components

    @staticmethod
    def assign_tier(score: float) -> str:
        if score <= 2.0:
            return "TIER_1_LOW"
        if score <= 4.0:
            return "TIER_2_MODERATE"
        if score <= 6.0:
            return "TIER_3_HIGH"
        return "TIER_4_VERY_HIGH"

    @staticmethod
    def compute_installments(total_price: float, weights: Dict[str, float]) -> Dict[str, float]:
        return {k: round(total_price * w, 2) for k, w in weights.items()}

    @staticmethod
    def compute_clinical_buckets(total_price: float, proportions: Dict[str, float]) -> Dict[str, float]:
        return {k: round(total_price * w, 2) for k, w in proportions.items()}

    def apply_delivery_floor(
        self,
        final_price: float,
        delivery_type: str,
        bucket_proportions: Dict[str, float],
    ) -> float:
        floor = self.config["delivery_bucket_floor_zar"].get(
            delivery_type,
            self.config["delivery_bucket_floor_zar"]["UNKNOWN"],
        )
        delivery_share = float(bucket_proportions.get("delivery_admission_and_specialist", 0.0))
        if delivery_share <= 0:
            return final_price
        required_total_for_floor = floor / delivery_share
        return max(final_price, required_total_for_floor)

    def clamp_price(self, value: float) -> float:
        floor = self.config["price_floor_zar"]
        cap = self.config["price_cap_zar"]
        if value < floor:
            return floor
        if value > cap:
            return cap
        return value

    def compute_multiplier_from_score(self, score: float) -> float:
        # Piecewise linear interpolation across tier anchors to avoid discontinuous price jumps.
        anchors = [
            (0.0, float(self.config["tier_multipliers"]["TIER_1_LOW"])),
            (2.0, float(self.config["tier_multipliers"]["TIER_2_MODERATE"])),
            (4.0, float(self.config["tier_multipliers"]["TIER_3_HIGH"])),
            (6.0, float(self.config["tier_multipliers"]["TIER_4_VERY_HIGH"])),
        ]
        if score <= anchors[0][0]:
            return anchors[0][1]
        for i in range(len(anchors) - 1):
            x0, y0 = anchors[i]
            x1, y1 = anchors[i + 1]
            if x0 <= score <= x1:
                t = (score - x0) / (x1 - x0) if x1 != x0 else 0.0
                return y0 + t * (y1 - y0)
        # extrapolate above highest anchor with last segment slope
        x0, y0 = anchors[-2]
        x1, y1 = anchors[-1]
        slope = (y1 - y0) / (x1 - x0)
        return y1 + slope * (score - x1)

    def quote(self, input_data: NetworkOneEpisodeInput) -> NetworkOneEpisodeQuote:
        input_data.validate()

        inferred_indicators, trace = infer_indicators_from_icd10(
            codes=input_data.icd10_codes,
            descriptions=input_data.icd10_descriptions,
        )
        score_components = self._score_components(input_data)
        score = round(sum(score_components.values()), 4)
        tier = self.assign_tier(score)
        multiplier = self.compute_multiplier_from_score(score)
        risk_adjusted = input_data.base_price_zar * multiplier
        delivery_addon = self.config["delivery_addon"][input_data.delivery_type]
        bucket_proportions = self.config["clinical_bucket_proportions"].get(
            input_data.delivery_type,
            self.config["clinical_bucket_proportions"]["UNKNOWN"],
        )
        final_price_pre_floor = self.clamp_price(risk_adjusted + delivery_addon)
        final_price_with_floor = self.apply_delivery_floor(
            final_price=final_price_pre_floor,
            delivery_type=input_data.delivery_type,
            bucket_proportions=bucket_proportions,
        )
        final_price = self.clamp_price(final_price_with_floor)
        installments = self.compute_installments(final_price, input_data.installment_weights)
        clinical_buckets = self.compute_clinical_buckets(final_price, bucket_proportions)

        rationale = {
            "tier_multiplier": f"{multiplier:.4f}",
            "delivery_addon_zar": f"{delivery_addon:.2f}",
            "price_floor_zar": f"{self.config['price_floor_zar']:.2f}",
            "price_cap_zar": f"{self.config['price_cap_zar']:.2f}",
            "delivery_bucket_floor_zar": f"{self.config['delivery_bucket_floor_zar'].get(input_data.delivery_type, self.config['delivery_bucket_floor_zar']['UNKNOWN']):.2f}",
            "icd10_inferred_indicators": ",".join(sorted(inferred_indicators)),
            "icd10_match_trace": ";".join(trace[:20]),
            "bucket_basis": "Funder dataset proportions (Data 2 period split)",
            "score_components": ",".join(f"{k}:{v}" for k, v in sorted(score_components.items())),
            "multiplier_method": "piecewise_linear_by_score",
        }

        return NetworkOneEpisodeQuote(
            patient_id=input_data.patient_id,
            payer_type=input_data.payer_type,
            complexity_score=score,
            complexity_tier=tier,
            base_price_zar=round(input_data.base_price_zar, 2),
            risk_adjusted_price_zar=round(risk_adjusted, 2),
            final_price_zar=round(final_price, 2),
            clinical_bucket_amounts=clinical_buckets,
            installment_amounts=installments,
            rationale=rationale,
        )


def build_default_quote(payload: dict) -> Tuple[NetworkOneEpisodeInput, NetworkOneEpisodeQuote]:
    engine = NetworkOneEpisodePricingEngine()
    payload = payload.copy()
    if "base_price_zar" not in payload:
        payload["base_price_zar"] = engine.config["base_price_zar"]
    if "installment_weights" not in payload:
        payload["installment_weights"] = engine.config["installment_weights"]
    input_data = NetworkOneEpisodeInput(**payload)
    return input_data, engine.quote(input_data)
