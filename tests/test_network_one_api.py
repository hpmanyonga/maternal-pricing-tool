import os
import unittest

from fastapi.testclient import TestClient
import jwt

os.environ["NETWORK_ONE_AUDIT_SALT"] = "unit-test-salt"
os.environ["NETWORK_ONE_API_TOKENS_JSON"] = (
    '{"writer-token":{"actor":"pricing-admin","roles":["quote:read","quote:write"]},'
    '"reader-token":{"actor":"auditor","roles":["quote:read"]}}'
)

from app.network_one_secure_api import app  # noqa: E402


class NetworkOneAPITests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_requires_auth(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 401)

    def test_health_with_reader_role(self):
        response = self.client.get("/health", headers={"Authorization": "Bearer reader-token"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_quote_requires_write_role(self):
        payload = {
            "patient_id": "Mother 99",
            "payer_type": "MEDICAL_AID",
            "delivery_type": "NVD",
        }
        response = self.client.post(
            "/v1/episodes/quote",
            json=payload,
            headers={"Authorization": "Bearer reader-token"},
        )
        self.assertEqual(response.status_code, 403)

    def test_quote_success(self):
        payload = {
            "patient_id": "Mother 100",
            "payer_type": "MEDICAL_AID",
            "delivery_type": "CS",
            "chronic": True,
            "pregnancy_medical": True,
            "pregnancy_anatomical": True,
        }
        response = self.client.post(
            "/v1/episodes/quote",
            json=payload,
            headers={"Authorization": "Bearer writer-token"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("final_price_zar", body)
        self.assertIn("clinical_bucket_amounts", body)
        self.assertGreater(body["final_price_zar"], 54000)
        self.assertEqual(body["complexity_tier"], "TIER_4_VERY_HIGH")

    def test_quote_with_icd10_inputs(self):
        payload = {
            "patient_id": "Mother 200",
            "payer_type": "MEDICAL_AID",
            "delivery_type": "NVD",
            "icd10_codes": ["O14.1", "I10"],
            "icd10_descriptions": ["Preeclampsia in pregnancy"],
        }
        response = self.client.post(
            "/v1/episodes/quote",
            json=payload,
            headers={"Authorization": "Bearer writer-token"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertGreater(body["complexity_score"], 0)
        self.assertIn("icd10_inferred_indicators", body["rationale"])

    def test_jwt_auth_health_and_quote(self):
        os.environ["NETWORK_ONE_JWT_SECRET"] = "unit-test-jwt-secret-minimum-32-bytes"
        try:
            token = jwt.encode(
                {
                    "sub": "jwt-user",
                    "roles": ["quote:read", "quote:write"],
                },
                "unit-test-jwt-secret-minimum-32-bytes",
                algorithm="HS256",
            )
            health = self.client.get("/health", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(health.status_code, 200)

            payload = {
                "patient_id": "Mother 300",
                "payer_type": "MEDICAL_AID",
                "delivery_type": "NVD",
            }
            quote = self.client.post(
                "/v1/episodes/quote",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(quote.status_code, 200)
        finally:
            os.environ.pop("NETWORK_ONE_JWT_SECRET", None)

    def test_icd10_explain_requires_auth(self):
        response = self.client.post("/v1/episodes/icd10-explain", json={})
        self.assertEqual(response.status_code, 401)

    def test_icd10_explain_with_reader_role(self):
        payload = {
            "icd10_codes": ["O14.1", "I10"],
            "icd10_descriptions": ["Severe preeclampsia with hypertension"],
            "delivery_type": "NVD",
        }
        response = self.client.post(
            "/v1/episodes/icd10-explain",
            json=payload,
            headers={"Authorization": "Bearer reader-token"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("explanation", body)
        self.assertIn("preview", body)
        self.assertIn("inferred_indicators", body["explanation"])
        self.assertIn("pregnancy_medical", body["explanation"]["inferred_indicators"])
        self.assertIn("chronic", body["explanation"]["inferred_indicators"])


if __name__ == "__main__":
    unittest.main()
