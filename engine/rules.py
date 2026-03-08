"""
Business rules for Discovery-aligned maternity pricing.
All loadings are ADDITIVE (separate line items), not multiplicative.
"""


def compute_stage_amounts(global_fee, enrollment_route,
                          stage_proportions, antn1b_discount=0.50):
    """
    Split a global fee into the three Discovery payment stages.

    Returns dict with antn1_amount, antn2_amount, delivery_amount, total_global.
    """
    antn1_full = global_fee * stage_proportions["ANTN1A"]
    if enrollment_route == "ANTN1A":
        antn1 = antn1_full
    else:
        antn1 = antn1_full * antn1b_discount

    antn2 = global_fee * stage_proportions["ANTN2"]
    delivery = global_fee * stage_proportions["DELIVERY"]

    return {
        "antn1_amount": antn1,
        "antn2_amount": antn2,
        "delivery_amount": delivery,
        "total_global": antn1 + antn2 + delivery,
    }


def compute_risk_addon(risk_category, consult_fee, scan_fee, risk_schedule):
    """
    Compute add-on cost for risk-based additional consultations and scans.
    """
    info = risk_schedule[risk_category]
    return (info["consults"] * consult_fee) + (info["scans"] * scan_fee)


def compute_chronic_addon(chronic_flag, consult_fee, extra_consults=1):
    """Compute add-on cost for chronic conditions."""
    return extra_consults * consult_fee if chronic_flag else 0.0


def compute_complication_addon(complication_flag, consult_fee, scan_fee,
                               extra_consults=1, extra_scans=1):
    """Compute add-on cost for complications."""
    if not complication_flag:
        return 0.0
    return (extra_consults * consult_fee) + (extra_scans * scan_fee)


def compute_cs_addon(delivery_mode, cs_differential=2000.0):
    """Compute CS delivery differential add-on."""
    return cs_differential if delivery_mode == "CS" else 0.0


def compute_private_room_addon(private_room, base_fee=4000.0, discount_pct=0):
    """Compute private room add-on with optional discount."""
    if not private_room:
        return 0.0
    return base_fee * (1 - discount_pct / 100)


def sum_addons(*addons):
    """Sum all add-on amounts."""
    return sum(addons)
