from dataclasses import dataclass, field
from typing import Dict, List


VALID_PAYER_TYPES = ("CASH", "MEDICAL_AID")
VALID_DELIVERY_TYPES = ("NVD", "CS", "UNKNOWN")


@dataclass
class NetworkOneEpisodeInput:
    """
    Input model for Early ANC -> Early PNC maternity episode pricing.
    """
    patient_id: str
    payer_type: str
    delivery_type: str = "UNKNOWN"
    chronic: bool = False
    pregnancy_medical: bool = False
    pregnancy_anatomical: bool = False
    risk_factor: bool = False
    unrelated_medical: bool = False
    unrelated_anatomical: bool = False
    icd10_codes: List[str] = field(default_factory=list)
    icd10_descriptions: List[str] = field(default_factory=list)
    base_price_zar: float = 51_000.0
    installment_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "booking_12_16w": 0.20,
            "mid_anc_20_24w": 0.20,
            "late_anc_28_32w": 0.20,
            "pre_delivery_34_36w": 0.15,
            "delivery_event": 0.20,
            "early_pnc_0_6w": 0.05,
        }
    )

    def validate(self) -> None:
        if not self.patient_id or not self.patient_id.strip():
            raise ValueError("patient_id is required")
        if self.payer_type not in VALID_PAYER_TYPES:
            raise ValueError(f"payer_type must be one of {VALID_PAYER_TYPES}")
        if self.delivery_type not in VALID_DELIVERY_TYPES:
            raise ValueError(f"delivery_type must be one of {VALID_DELIVERY_TYPES}")
        if self.base_price_zar <= 0:
            raise ValueError("base_price_zar must be > 0")
        if not isinstance(self.icd10_codes, list):
            raise ValueError("icd10_codes must be a list")
        if not isinstance(self.icd10_descriptions, list):
            raise ValueError("icd10_descriptions must be a list")
        if not self.installment_weights:
            raise ValueError("installment_weights cannot be empty")
        total = sum(self.installment_weights.values())
        if abs(total - 1.0) > 1e-9:
            raise ValueError("installment_weights must sum to 1.0")


@dataclass
class NetworkOneEpisodeQuote:
    patient_id: str
    payer_type: str
    complexity_score: float
    complexity_tier: str
    base_price_zar: float
    risk_adjusted_price_zar: float
    final_price_zar: float
    clinical_bucket_amounts: Dict[str, float]
    installment_amounts: Dict[str, float]
    rationale: Dict[str, str]
