import math
from typing import Dict, List

from engine.models import (
    NOHCashProfile,
    NOHCashResult,
    NOH_PACKAGES,
    NOH_CS_CONVERSION_LEVY,
    NOH_ADDITIONAL_TESTS,
    NOH_CONSULT_FEE,
    NOH_CHRONIC_SCAN_FEE,
    PRIVATE_ROOM_FEE,
)


class NOHCashPricingEngine:
    """
    NOH Cash Maternity Programme pricing engine.
    Isolated from Discovery — uses own package codes and rules.
    """

    def classify_risk(self, profile: NOHCashProfile, coopland_risk_band: str) -> tuple:
        """
        Returns (risk_classification, risk_reason).
        Primigravida overrides Coopland to HIGH.
        """
        if profile.is_primigravida:
            return "HIGH", "Primigravida (automatic HIGH)"

        if coopland_risk_band == "HIGH":
            return "HIGH", "Coopland score HIGH"
        elif coopland_risk_band == "MEDIUM":
            return "HIGH", "Coopland score MEDIUM (mapped to HIGH)"
        else:
            return "LOW", "Coopland score LOW"

    def select_package(self, risk: str, delivery_mode: str) -> str:
        """Returns package key from NOH_PACKAGES."""
        if delivery_mode == "ELECTIVE_CS":
            if risk == "HIGH":
                return "Mat003"
            else:
                return "Mat002"
        else:  # NVD
            if risk == "HIGH":
                return "Mat001_HIGH"
            else:
                return "Mat001_LOW"

    def compute_payment_schedule(self, total_fee: float, booking_ga_weeks: float) -> tuple:
        """Returns (monthly_payment, months_remaining)."""
        weeks_remaining = max(0, 34 - booking_ga_weeks)
        months_remaining = max(1, math.ceil(weeks_remaining / 4))
        monthly_payment = total_fee / months_remaining
        return monthly_payment, months_remaining

    def price(
        self,
        profile: NOHCashProfile,
        coopland_risk_band: str = "LOW",
    ) -> NOHCashResult:

        # 1. Risk classification
        risk, reason = self.classify_risk(profile, coopland_risk_band)

        # 2. Package selection
        pkg_key = self.select_package(risk, profile.planned_delivery_mode)
        pkg = NOH_PACKAGES[pkg_key]

        # 3. Disease-related add-ons (clinician-chosen consults + scans)
        chronic_addon_amt = 0.0
        if profile.chronic_flag:
            chronic_addon_amt = (
                profile.chronic_consults * NOH_CONSULT_FEE
                + profile.chronic_scans * NOH_CHRONIC_SCAN_FEE
            )

        complication_addon_amt = 0.0
        if profile.complication_flag:
            complication_addon_amt = (
                profile.complication_consults * NOH_CONSULT_FEE
                + profile.complication_scans * NOH_CHRONIC_SCAN_FEE
            )

        # 4. CS conversion levy
        cs_levy = 0.0
        if profile.cs_conversion and profile.planned_delivery_mode == "NVD":
            cs_levy = NOH_CS_CONVERSION_LEVY

        # 5. Private room
        pvt_room = 0.0
        if profile.private_room:
            pvt_room = PRIVATE_ROOM_FEE * (1 - profile.private_room_discount / 100)

        # 7. Additional tests
        test_items = []
        total_tests = 0.0
        for test_key in profile.selected_tests:
            if test_key in NOH_ADDITIONAL_TESTS:
                t = NOH_ADDITIONAL_TESTS[test_key]
                test_items.append({"label": t["label"], "code": t["code"], "fee": t["fee"]})
                total_tests += t["fee"]

        # 7. Total
        total = (pkg["price"] + chronic_addon_amt + complication_addon_amt
                 + cs_levy + pvt_room + total_tests)

        # 8. Payment schedule
        monthly, months = self.compute_payment_schedule(total, profile.gestational_age_weeks)

        return NOHCashResult(
            package_key=pkg_key,
            package_code=pkg["code"],
            package_label=pkg["label"],
            package_price=pkg["price"],
            risk_classification=risk,
            risk_reason=reason,
            chronic_addon=chronic_addon_amt,
            complication_addon=complication_addon_amt,
            cs_conversion_levy=cs_levy,
            private_room_addon=pvt_room,
            test_items=test_items,
            total_tests=total_tests,
            total_price=total,
            monthly_payment=monthly,
            months_to_34_weeks=months,
        )


# ============================================================
# CLI test harness
# ============================================================

if __name__ == "__main__":
    engine = NOHCashPricingEngine()

    cases = [
        ("Primigravida NVD", NOHCashProfile(
            gravida=1, parity=0, gestational_age_weeks=14,
            planned_delivery_mode="NVD", baby_medical_aid_secured=True,
            selected_tests=["Path1_OGTT", "Path2_HIV_CD4"],
        ), "LOW"),
        ("Primigravida Elective CS", NOHCashProfile(
            gravida=1, parity=0, gestational_age_weeks=14,
            planned_delivery_mode="ELECTIVE_CS", baby_medical_aid_secured=True,
        ), "LOW"),
        ("Multiparous low-risk NVD", NOHCashProfile(
            gravida=3, parity=2, gestational_age_weeks=12,
            planned_delivery_mode="NVD", baby_medical_aid_secured=True,
            selected_tests=["Path1_OGTT"],
        ), "LOW"),
        ("NVD with CS conversion", NOHCashProfile(
            gravida=2, parity=1, gestational_age_weeks=10,
            planned_delivery_mode="NVD", baby_medical_aid_secured=True,
            cs_conversion=True,
        ), "LOW"),
        ("High-risk Elective CS", NOHCashProfile(
            gravida=2, parity=1, gestational_age_weeks=16,
            planned_delivery_mode="ELECTIVE_CS", baby_medical_aid_secured=True,
            selected_tests=["Path1_OGTT", "Path2_HIV_CD4", "Iron_Studies", "Mat010_NST"],
        ), "HIGH"),
    ]

    for label, profile, coopland_band in cases:
        result = engine.price(profile, coopland_band)
        print(f"--- {label} ---")
        print(f"  Risk: {result.risk_classification} ({result.risk_reason})")
        print(f"  Package: {result.package_code} — {result.package_label}: R{result.package_price:,.0f}")
        if result.test_items:
            print(f"  Tests: R{result.total_tests:,.2f}")
        if result.cs_conversion_levy > 0:
            print(f"  CS Levy: R{result.cs_conversion_levy:,.0f}")
        print(f"  TOTAL: R{result.total_price:,.2f}")
        print(f"  Payment: R{result.monthly_payment:,.0f}/month x {result.months_to_34_weeks} months")
        print()
