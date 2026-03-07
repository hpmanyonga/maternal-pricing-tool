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
        items.append({"item": "TOTAL", "amount": self.final_price})
        return items
