import pandas as pd
from pathlib import Path
from engine.models import PatientProfile, PricingResult
from engine.rules import (
    compute_stage_amounts,
    compute_risk_addon,
    compute_chronic_addon,
    compute_complication_addon,
    compute_cs_addon,
    compute_private_room_addon,
    sum_addons,
)


class PricingEngine:
    """
    Discovery-aligned pricing engine for maternity care.
    Uses plan-based global fees with additive risk/chronic/complication loadings.
    """

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

    RISK_ADDONS = {
        "BASE":   {"consults": 0, "scans": 0},
        "MEDIUM": {"consults": 2, "scans": 1},
        "HIGH":   {"consults": 4, "scans": 2},
    }

    CONSULT_FEE = {
        "KEYCARE": 1_689,
        "SMART": 2_300,
        "COASTAL_ESSENTIAL": 2_300,
        "CLASSIC": 2_300,
        "EXECUTIVE": 2_300,
    }

    SCAN_FEE = 1_800
    CS_ADDON = 2_000
    PRIVATE_ROOM_FEE = 4_000
    CHRONIC_EXTRA_CONSULTS = 1
    COMPLICATION_EXTRA_CONSULTS = 1
    COMPLICATION_EXTRA_SCANS = 1

    def __init__(self, outputs_dir="outputs"):
        self.outputs_dir = Path(outputs_dir)

    def price_patient(self, profile):
        """Price a single patient. Accepts a PatientProfile or keyword args."""
        if isinstance(profile, dict):
            profile = PatientProfile(**profile)
        profile.validate()

        plan = profile.plan_type
        global_fee = self.GLOBAL_FEES[plan]
        consult_fee = self.CONSULT_FEE[plan]

        # Stage breakdown
        stages = compute_stage_amounts(
            global_fee, profile.enrollment_route,
            self.STAGE_PROPORTIONS, self.ANTN1B_DISCOUNT,
        )

        # Add-ons
        risk_addon = compute_risk_addon(
            profile.risk_category, consult_fee, self.SCAN_FEE, self.RISK_ADDONS,
        )
        chronic_addon = compute_chronic_addon(
            profile.chronic_flag, consult_fee, self.CHRONIC_EXTRA_CONSULTS,
        )
        complication_addon = compute_complication_addon(
            profile.complication_flag, consult_fee, self.SCAN_FEE,
            self.COMPLICATION_EXTRA_CONSULTS, self.COMPLICATION_EXTRA_SCANS,
        )
        cs_addon = compute_cs_addon(profile.delivery_mode, self.CS_ADDON)
        private_room_addon = compute_private_room_addon(
            profile.private_room, self.PRIVATE_ROOM_FEE, profile.private_room_discount,
        )

        total_addons = sum_addons(risk_addon, chronic_addon, complication_addon, cs_addon, private_room_addon)
        final_price = stages["total_global"] + total_addons

        return PricingResult(
            plan_type=plan,
            enrollment_route=profile.enrollment_route,
            global_fee=stages["total_global"],
            antn1_amount=stages["antn1_amount"],
            antn2_amount=stages["antn2_amount"],
            delivery_amount=stages["delivery_amount"],
            risk_category=profile.risk_category,
            risk_addon=risk_addon,
            chronic_addon=chronic_addon,
            complication_addon=complication_addon,
            cs_addon=cs_addon,
            private_room_addon=private_room_addon,
            total_addons=total_addons,
            final_price=round(final_price, 0),
        )


# CLI test harness
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from engine.models import PatientProfile

    engine = PricingEngine()

    test_cases = [
        PatientProfile("KEYCARE", "ANTN1A", "BASE", "NVD", False, False),
        PatientProfile("KEYCARE", "ANTN1B", "BASE", "NVD", False, False),
        PatientProfile("SMART", "ANTN1A", "MEDIUM", "NVD", True, False),
        PatientProfile("CLASSIC", "ANTN1A", "HIGH", "CS", True, True),
        PatientProfile("EXECUTIVE", "ANTN1A", "HIGH", "CS", True, True),
    ]

    for profile in test_cases:
        result = engine.price_patient(profile)
        label = (f"{profile.plan_type}/{profile.enrollment_route}/"
                 f"{profile.risk_category}/{profile.delivery_mode}/"
                 f"chronic={profile.chronic_flag}/comp={profile.complication_flag}")
        print(f"  {label}")
        print(f"    Global fee: R {result.global_fee:,.0f}  "
              f"Add-ons: R {result.total_addons:,.0f}  "
              f"→ TOTAL: R {result.final_price:,.0f}")
        print()
