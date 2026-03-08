from engine.eligibility_engine import EligibilityResult


class NOHCashEligibilityEngine:
    """
    NOH Cash Programme eligibility rules.
    Separate from Discovery — internal governance only.
    """

    def evaluate(
        self,
        *,
        booking_weeks: float,
        baby_medical_aid_secured: bool,
        has_full_clinical_record: bool = False,
        has_complications: bool = False,
    ) -> EligibilityResult:

        # 1. Booking cut-off: 30 weeks
        if booking_weeks > 30:
            return EligibilityResult(
                eligible_for_global_fee=False,
                exclusion_reason="Booking after 30 weeks gestation",
                requires_authorisation=False,
                authorisation_type=None,
                potential_delivery_carveouts=[],
            )

        # 2. Late booking (26-30 weeks) requires full clinical record + no complications
        if booking_weeks > 26:
            if not has_full_clinical_record or has_complications:
                reason = (
                    "Booking 26-30 weeks requires full clinical record "
                    "and no complications"
                )
                return EligibilityResult(
                    eligible_for_global_fee=False,
                    exclusion_reason=reason,
                    requires_authorisation=False,
                    authorisation_type=None,
                    potential_delivery_carveouts=[],
                )

        # 3. Baby medical aid mandatory
        if not baby_medical_aid_secured:
            return EligibilityResult(
                eligible_for_global_fee=False,
                exclusion_reason="Baby medical aid not secured — required for programme entry",
                requires_authorisation=False,
                authorisation_type=None,
                potential_delivery_carveouts=[],
            )

        # 4. Eligible
        return EligibilityResult(
            eligible_for_global_fee=True,
            exclusion_reason=None,
            requires_authorisation=False,  # no external auth for NOH Cash
            authorisation_type=None,
            potential_delivery_carveouts=[],
        )


# ============================================================
# CLI test harness
# ============================================================

if __name__ == "__main__":
    engine = NOHCashEligibilityEngine()

    cases = [
        {"booking_weeks": 14, "baby_medical_aid_secured": True},
        {"booking_weeks": 32, "baby_medical_aid_secured": True},
        {"booking_weeks": 28, "baby_medical_aid_secured": True,
         "has_full_clinical_record": False},
        {"booking_weeks": 28, "baby_medical_aid_secured": True,
         "has_full_clinical_record": True, "has_complications": False},
        {"booking_weeks": 14, "baby_medical_aid_secured": False},
    ]

    for i, case in enumerate(cases, 1):
        result = engine.evaluate(**case)
        print(f"Case {i}: booking={case['booking_weeks']}w, "
              f"babyMA={case['baby_medical_aid_secured']}")
        print(f"  Eligible: {result.eligible_for_global_fee}")
        if result.exclusion_reason:
            print(f"  Reason: {result.exclusion_reason}")
        print()
