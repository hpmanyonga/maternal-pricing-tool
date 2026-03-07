from dataclasses import dataclass
from typing import Dict, List


# =====================================================
# Canonical Coopland risk factor weights
# Source: NOH Coopland Risk Classification tables
# =====================================================

COOPLAND_FACTORS: Dict[str, int] = {
    # Demographic
    "maternal_age_extremes": 2,        # <16 or >35
    "teenage_pregnancy": 2,            # <18
    "short_stature": 1,                # <1.52m
    "extreme_weight": 1,               # <45kg or >90kg
    "poor_socioeconomic_status": 1,

    # Obstetric history
    "grand_multiparity": 2,            # >4
    "primigravida": 1,
    "previous_cs": 2,
    "previous_stillbirth": 2,
    "previous_preterm_delivery": 2,
    "previous_pph": 2,
    "previous_low_birth_weight": 1,
    "previous_macrosomia": 1,
    "history_of_infertility": 1,

    # Medical conditions
    "chronic_hypertension": 3,
    "diabetes_mellitus": 3,
    "cardiac_disease": 3,
    "renal_disease": 2,
    "epilepsy": 2,
    "mental_illness": 2,
    "hiv_positive": 2,
    "anaemia": 2,                      # Hb < 10
    "rh_negative": 2,
    "tb_or_recent_infection": 2,
    "malaria": 2,

    # Current pregnancy
    "multiple_pregnancy": 2,
    "abnormal_lie": 1,
    "recurrent_uti": 1,
    "poor_anc_attendance": 2,
    "poor_nutrition": 1,

    # Social / behavioural
    "smoking_or_substance_use": 1,
    "domestic_violence": 2,
}


# =====================================================
# Data structure for result
# =====================================================

@dataclass
class CooplandResult:
    total_score: int
    risk_band: str
    risk_drivers: List[str]
    extra_consults: int
    extra_ultrasounds: int


# =====================================================
# Core Coopland scoring engine
# =====================================================

class CooplandEngine:
    """
    Deterministic Coopland scoring engine.
    Faithful to NOH / Discovery operational documents.
    """

    LOW_MAX = 3
    MEDIUM_MAX = 6

    def score(self, factors_present: Dict[str, bool]) -> CooplandResult:
        """
        factors_present: dict mapping factor_name -> True/False
        """

        total_score = 0
        drivers: List[str] = []

        for factor, is_present in factors_present.items():
            if is_present:
                weight = COOPLAND_FACTORS.get(factor, 0)
                total_score += weight
                drivers.append(factor)

        # Determine risk band
        if total_score <= self.LOW_MAX:
            risk_band = "LOW"
            extra_consults = 0
            extra_ultrasounds = 0
        elif total_score <= self.MEDIUM_MAX:
            risk_band = "MEDIUM"
            extra_consults = 2
            extra_ultrasounds = 1
        else:
            risk_band = "HIGH"
            extra_consults = 4
            extra_ultrasounds = 2

        return CooplandResult(
            total_score=total_score,
            risk_band=risk_band,
            risk_drivers=drivers,
            extra_consults=extra_consults,
            extra_ultrasounds=extra_ultrasounds,
        )


# =====================================================
# CLI test harness
# =====================================================

if __name__ == "__main__":
    engine = CooplandEngine()

    example_patient = {
        "maternal_age_extremes": True,
        "previous_cs": True,
        "anaemia": True,
        "smoking_or_substance_use": False,
    }

    result = engine.score(example_patient)

    print("Coopland Score:", result.total_score)
    print("Risk Band:", result.risk_band)
    print("Risk Drivers:", result.risk_drivers)
    print("Extra Consults:", result.extra_consults)
    print("Extra Ultrasounds:", result.extra_ultrasounds)
