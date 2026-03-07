from dataclasses import dataclass
from typing import List, Optional


# ============================================================
# Result object
# ============================================================

@dataclass
class EligibilityResult:
    eligible_for_global_fee: bool
    exclusion_reason: Optional[str]
    requires_authorisation: bool
    authorisation_type: Optional[str]
    potential_delivery_carveouts: List[str]


# ============================================================
# Eligibility & carve‑out rules engine
# ============================================================

class EligibilityEngine:
    """
    Discovery / NOH eligibility and carve‑out rules engine.

    This engine enforces:
    - booking window eligibility
    - upfront exclusions
    - Coopland‑based exclusions
    - authorisation triggers
    - delivery‑time carve‑outs (FFS reversion)
    """

    def evaluate(
        self,
        *,
        coopland_score: int,
        maternal_age: int,
        multiple_pregnancy: bool,
        uncontrolled_chronic_disease: bool,
        booking_weeks: float,
    ) -> EligibilityResult:

        # ----------------------------------------------------
        # 1. Booking window exclusion
        # ----------------------------------------------------
        if booking_weeks > 20:
            return EligibilityResult(
                eligible_for_global_fee=False,
                exclusion_reason="Booking after 20 weeks gestation",
                requires_authorisation=False,
                authorisation_type=None,
                potential_delivery_carveouts=[],
            )

        # ----------------------------------------------------
        # 2. Up‑front clinical carve‑outs
        # ----------------------------------------------------
        if multiple_pregnancy:
            return EligibilityResult(
                eligible_for_global_fee=False,
                exclusion_reason="Multiple pregnancy (twin or higher)",
                requires_authorisation=False,
                authorisation_type=None,
                potential_delivery_carveouts=[],
            )

        if maternal_age > 40:
            return EligibilityResult(
                eligible_for_global_fee=False,
                exclusion_reason="Maternal age > 40 years",
                requires_authorisation=False,
                authorisation_type=None,
                potential_delivery_carveouts=[],
            )

        if uncontrolled_chronic_disease:
            return EligibilityResult(
                eligible_for_global_fee=False,
                exclusion_reason="Uncontrolled chronic medical condition",
                requires_authorisation=False,
                authorisation_type=None,
                potential_delivery_carveouts=[],
            )

        # ----------------------------------------------------
        # 3. Coopland‑based exclusion
        # ----------------------------------------------------
        if coopland_score >= 7:
            return EligibilityResult(
                eligible_for_global_fee=False,
                exclusion_reason="High risk (Coopland score >= 7)",
                requires_authorisation=True,
                authorisation_type="HRANTN",
                potential_delivery_carveouts=[],
            )

        # ----------------------------------------------------
        # 4. Authorisation rules
        # ----------------------------------------------------
        requires_authorisation = coopland_score >= 4

        # ----------------------------------------------------
        # 5. Delivery‑time carve‑outs (FFS reversion)
        #    These are conditions that, if they arise at
        #    delivery, cause the delivery component to revert
        #    to fee‑for‑service billing outside the global fee.
        # ----------------------------------------------------
        carveouts: List[str] = []

        if coopland_score >= 4:
            carveouts.append("Emergency CS for fetal distress")
            carveouts.append("Postpartum haemorrhage requiring intervention")

        if maternal_age >= 35:
            carveouts.append("Induction of labour beyond 41 weeks")

        # Universal delivery carve-outs (always flagged)
        carveouts.append("NICU admission (billed separately)")
        carveouts.append("Blood transfusion")
        carveouts.append("Hysterectomy")
        carveouts.append("ICU admission")

        # ----------------------------------------------------
        # 6. Eligible — return result
        # ----------------------------------------------------
        return EligibilityResult(
            eligible_for_global_fee=True,
            exclusion_reason=None,
            requires_authorisation=requires_authorisation,
            authorisation_type="HRANTN" if requires_authorisation else None,
            potential_delivery_carveouts=carveouts,
        )


# ============================================================
# CLI test harness
# ============================================================

if __name__ == "__main__":
    engine = EligibilityEngine()

    test_cases = [
        {"coopland_score": 2, "maternal_age": 28, "multiple_pregnancy": False,
         "uncontrolled_chronic_disease": False, "booking_weeks": 12},
        {"coopland_score": 5, "maternal_age": 36, "multiple_pregnancy": False,
         "uncontrolled_chronic_disease": False, "booking_weeks": 14},
        {"coopland_score": 8, "maternal_age": 32, "multiple_pregnancy": False,
         "uncontrolled_chronic_disease": False, "booking_weeks": 10},
        {"coopland_score": 2, "maternal_age": 25, "multiple_pregnancy": True,
         "uncontrolled_chronic_disease": False, "booking_weeks": 8},
        {"coopland_score": 1, "maternal_age": 30, "multiple_pregnancy": False,
         "uncontrolled_chronic_disease": False, "booking_weeks": 22},
    ]

    for i, case in enumerate(test_cases, 1):
        result = engine.evaluate(**case)
        print(f"Case {i}: Coopland={case['coopland_score']}, "
              f"Age={case['maternal_age']}, "
              f"Booking={case['booking_weeks']}w")
        print(f"  Eligible: {result.eligible_for_global_fee}")
        if result.exclusion_reason:
            print(f"  Exclusion: {result.exclusion_reason}")
        if result.requires_authorisation:
            print(f"  Auth required: {result.authorisation_type}")
        if result.potential_delivery_carveouts:
            print(f"  Carve-outs: {len(result.potential_delivery_carveouts)}")
        print()
