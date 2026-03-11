import json
from pathlib import Path
from typing import Dict


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "network_one_pricing_config.json"


def load_network_one_config(path: str = None) -> Dict:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with config_path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    required_keys = [
        "risk_weights",
        "tier_multipliers",
        "delivery_addon",
        "price_floor_zar",
        "price_cap_zar",
        "base_price_zar",
        "installment_weights",
        "clinical_bucket_proportions",
        "delivery_bucket_floor_zar",
    ]
    missing = [k for k in required_keys if k not in config]
    if missing:
        raise ValueError(f"Missing required config keys: {missing}")
    return config
