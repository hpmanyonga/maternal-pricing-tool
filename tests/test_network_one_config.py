import unittest

from engine.network_one_config import load_network_one_config
from engine.network_one_pricing import build_default_quote


class NetworkOneConfigTests(unittest.TestCase):
    def test_config_loads_required_keys(self):
        config = load_network_one_config()
        self.assertIn("risk_weights", config)
        self.assertIn("tier_multipliers", config)
        self.assertIn("base_price_zar", config)
        self.assertIn("installment_weights", config)

    def test_build_default_quote_uses_config_defaults(self):
        payload = {
            "patient_id": "Mother 200",
            "payer_type": "CASH",
            "delivery_type": "UNKNOWN",
        }
        input_data, quote = build_default_quote(payload)
        config = load_network_one_config()
        self.assertEqual(input_data.base_price_zar, config["base_price_zar"])
        self.assertEqual(input_data.installment_weights, config["installment_weights"])
        self.assertGreater(quote.final_price_zar, 0)


if __name__ == "__main__":
    unittest.main()
