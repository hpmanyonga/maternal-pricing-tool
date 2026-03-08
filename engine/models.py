from dataclasses import dataclass, field
from typing import Optional


VALID_PLAN_TYPES = ("KEYCARE", "SMART", "COASTAL_ESSENTIAL", "CLASSIC", "EXECUTIVE")
VALID_ENROLLMENT_ROUTES = ("ANTN1A", "ANTN1B")
VALID_RISK_CATEGORIES = ("BASE", "MEDIUM", "HIGH")
VALID_DELIVERY_MODES = ("NVD", "CS")


@dataclass
class PatientProfile:
    """Input to the pricing engine."""
    plan_type: str
    enrollment_route: str
    risk_category: str
    delivery_mode: str
    chronic_flag: bool
    complication_flag: bool
    coopland_score: Optional[int] = None
    private_room: bool = False
    private_room_discount: int = 0   # 0, 10, or 15 percent

    def validate(self):
        if self.plan_type not in VALID_PLAN_TYPES:
            raise ValueError(
                f"plan_type must be one of {VALID_PLAN_TYPES}, got '{self.plan_type}'"
            )
        if self.enrollment_route not in VALID_ENROLLMENT_ROUTES:
            raise ValueError(
                f"enrollment_route must be one of {VALID_ENROLLMENT_ROUTES}, "
                f"got '{self.enrollment_route}'"
            )
        if self.risk_category not in VALID_RISK_CATEGORIES:
            raise ValueError(
                f"risk_category must be one of {VALID_RISK_CATEGORIES}, "
                f"got '{self.risk_category}'"
            )
        if self.delivery_mode not in VALID_DELIVERY_MODES:
            raise ValueError(
                f"delivery_mode must be one of {VALID_DELIVERY_MODES}, "
                f"got '{self.delivery_mode}'"
            )

    @classmethod
    def from_coopland(cls, plan_type, enrollment_route, coopland_score,
                      delivery_mode, chronic_flag, complication_flag):
        """Construct profile deriving risk_category from Coopland score."""
        if coopland_score <= 3:
            risk = "BASE"
        elif coopland_score <= 6:
            risk = "MEDIUM"
        else:
            risk = "HIGH"
        return cls(
            plan_type=plan_type,
            enrollment_route=enrollment_route,
            risk_category=risk,
            delivery_mode=delivery_mode,
            chronic_flag=chronic_flag,
            complication_flag=complication_flag,
            coopland_score=coopland_score,
        )


@dataclass
class PricingResult:
    """Output from the pricing engine -- line-item breakdown."""
    plan_type: str
    enrollment_route: str
    global_fee: float
    antn1_amount: float
    antn2_amount: float
    delivery_amount: float
    risk_category: str
    risk_addon: float
    chronic_addon: float
    complication_addon: float
    cs_addon: float
    private_room_addon: float
    total_addons: float
    final_price: float

    @property
    def addon_percentage(self) -> float:
        if self.global_fee == 0:
            return 0.0
        return (self.total_addons / self.global_fee) * 100

    def to_line_items(self) -> list:
        route_label = "ANTN1A" if self.enrollment_route == "ANTN1A" else "ANTN1B"
        items = [
            {"item": f"{route_label} (ANC Enrollment)", "amount": self.antn1_amount},
            {"item": "ANTN2 (Late ANC)", "amount": self.antn2_amount},
            {"item": "Delivery", "amount": self.delivery_amount},
        ]
        if self.risk_addon > 0:
            items.append({"item": f"Risk Add-on ({self.risk_category})", "amount": self.risk_addon})
        if self.chronic_addon > 0:
            items.append({"item": "Chronic Condition Add-on", "amount": self.chronic_addon})
        if self.complication_addon > 0:
            items.append({"item": "Complication Add-on", "amount": self.complication_addon})
        if self.cs_addon > 0:
            items.append({"item": "CS Delivery Differential", "amount": self.cs_addon})
        if self.private_room_addon > 0:
            items.append({"item": "Private Room", "amount": self.private_room_addon})
        items.append({"item": "TOTAL", "amount": self.final_price})
        return items


# ============================================================
# NOH Cash Programme models
# ============================================================

VALID_NOH_DELIVERY_MODES = ("NVD", "ELECTIVE_CS")

NOH_PACKAGES = {
    "Mat001_LOW": {"code": "Mat001", "label": "NVD (multiparous, low-risk)", "price": 29_900},
    "Mat001_HIGH": {"code": "Mat001", "label": "NVD (high-risk / primigravida)", "price": 46_000},
    "Mat002": {"code": "Mat002", "label": "Elective C/S", "price": 58_650},
    "Mat003": {"code": "Mat003", "label": "High Risk C/S", "price": 64_000},
}

NOH_CS_CONVERSION_LEVY = 7_500  # MAT004
NOH_EPIDURAL_FEE = 5_500
PRIVATE_ROOM_FEE = 4_000  # shared across both programmes

NOH_ADDITIONAL_TESTS = {
    "Path1_OGTT": {"label": "OGTT", "code": "Path1", "fee": 173.00},
    "Path2_HIV_CD4": {"label": "HIV CD4 & Viral Load", "code": "Path2", "fee": 1_253.50},
    "Iron_Studies": {"label": "Iron Studies", "code": "Iron", "fee": 402.50},
    "Mat010_NST": {"label": "Non Stress Test", "code": "Mat010", "fee": 250.00},
}


@dataclass
class NOHCashProfile:
    """Input for NOH Cash Programme pricing."""
    gravida: int
    parity: int
    gestational_age_weeks: float
    planned_delivery_mode: str        # NVD or ELECTIVE_CS
    baby_medical_aid_secured: bool
    chronic_flag: bool = False
    complication_flag: bool = False
    cs_conversion: bool = False       # planned NVD → emergency CS
    epidural: bool = False
    private_room: bool = False
    private_room_discount: int = 0    # 0, 10, or 15 percent
    selected_tests: list = field(default_factory=list)  # keys from NOH_ADDITIONAL_TESTS

    @property
    def is_primigravida(self) -> bool:
        return self.gravida == 1


@dataclass
class NOHCashResult:
    """Output from NOH Cash Programme pricing."""
    package_key: str
    package_code: str
    package_label: str
    package_price: float
    risk_classification: str          # LOW / HIGH
    risk_reason: str
    chronic_addon: float
    complication_addon: float
    cs_conversion_levy: float
    epidural_fee: float
    private_room_addon: float
    test_items: list                  # [{"label": ..., "code": ..., "fee": ...}]
    total_tests: float
    total_price: float
    monthly_payment: float
    months_to_34_weeks: int

    def to_line_items(self) -> list:
        items = [
            {"item": f"{self.package_code} — {self.package_label}", "amount": self.package_price},
        ]
        if self.chronic_addon > 0:
            items.append({"item": "Chronic Condition Add-on", "amount": self.chronic_addon})
        if self.complication_addon > 0:
            items.append({"item": "Complication Add-on", "amount": self.complication_addon})
        for t in self.test_items:
            items.append({"item": f"{t['code']}: {t['label']}", "amount": t["fee"]})
        if self.cs_conversion_levy > 0:
            items.append({"item": "MAT004 — CS Conversion Levy", "amount": self.cs_conversion_levy})
        if self.epidural_fee > 0:
            items.append({"item": "Epidural", "amount": self.epidural_fee})
        if self.private_room_addon > 0:
            items.append({"item": "Private Room", "amount": self.private_room_addon})
        items.append({"item": "TOTAL", "amount": self.total_price})
        return items
