import unittest
import os

from engine.network_one_models import NetworkOneEpisodeInput
from engine.network_one_pricing import NetworkOneEpisodePricingEngine
from engine.network_one_storage import (
    AuditLogRecord,
    InstallmentRecord,
    NetworkOneStorage,
    QuoteRequestRecord,
    QuoteRecord,
    resolve_database_url,
)


class NetworkOneStorageTests(unittest.TestCase):
    def setUp(self):
        self.storage = NetworkOneStorage("sqlite+pysqlite:///:memory:")
        self.storage.create_schema_for_dev()
        self.engine = NetworkOneEpisodePricingEngine()
        self._env_backup = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_save_quote_and_installments(self):
        quote = self.engine.quote(
            NetworkOneEpisodeInput(
                patient_id="Mother 123",
                payer_type="MEDICAL_AID",
                delivery_type="CS",
                chronic=True,
                pregnancy_medical=True,
            )
        )
        quote_id = self.storage.save_quote(
            quote=quote,
            patient_hash="hash123",
            delivery_type="CS",
        )

        with self.storage.session_factory() as session:
            quote_row = session.query(QuoteRecord).filter_by(id=quote_id).first()
            self.assertIsNotNone(quote_row)
            self.assertEqual(quote_row.patient_hash, "hash123")

            installment_rows = session.query(InstallmentRecord).filter_by(quote_id=quote_id).all()
            self.assertEqual(len(installment_rows), len(quote.installment_amounts))

    def test_save_audit_event(self):
        event_id = self.storage.save_audit_event(
            actor="pricing-admin",
            action="quote_episode",
            target_hash="hash_abc",
            result="success",
            detail="tier=TIER_2_MODERATE",
        )
        with self.storage.session_factory() as session:
            event = session.query(AuditLogRecord).filter_by(id=event_id).first()
            self.assertIsNotNone(event)
            self.assertEqual(event.actor, "pricing-admin")
            self.assertEqual(event.result, "success")

    def test_save_and_list_quote_requests(self):
        quote = self.engine.quote(
            NetworkOneEpisodeInput(
                patient_id="Mother 123",
                payer_type="CASH",
                delivery_type="UNKNOWN",
            )
        )
        quote_id = self.storage.save_quote(
            quote=quote,
            patient_hash="hash123",
            delivery_type="UNKNOWN",
        )
        request_id = self.storage.save_quote_request(
            quote_id=quote_id,
            full_name="Jane Doe",
            mobile="+27821234567",
            email="jane@example.com",
            preferred_contact="WhatsApp",
            notes="Please call after 5pm",
            payer_type="CASH",
            delivery_type="UNKNOWN",
            gestation_group="Under 12 weeks",
            estimate_low_zar=45000.0,
            estimate_high_zar=52000.0,
            estimate_mid_zar=48500.0,
            installment_count=7,
            installment_low_zar=6400.0,
            installment_high_zar=7400.0,
            selected_factors=["Long-term health conditions"],
        )

        with self.storage.session_factory() as session:
            row = session.query(QuoteRequestRecord).filter_by(id=request_id).first()
            self.assertIsNotNone(row)
            self.assertEqual(row.mobile, "+27821234567")

        requests = self.storage.list_quote_requests(limit=10)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["id"], request_id)
        self.assertEqual(requests[0]["quote_id"], quote_id)
        self.assertEqual(requests[0]["selected_factors"], ["Long-term health conditions"])

    def test_resolve_database_url_prefers_supabase_db_url(self):
        os.environ.pop("NETWORK_ONE_DATABASE_URL", None)
        os.environ["SUPABASE_DB_URL"] = "postgresql://u:p@h:5432/db"
        self.assertEqual(resolve_database_url(), "postgresql://u:p@h:5432/db")

    def test_resolve_database_url_builds_from_supabase_url(self):
        os.environ.pop("NETWORK_ONE_DATABASE_URL", None)
        os.environ.pop("SUPABASE_DB_URL", None)
        os.environ.pop("DATABASE_URL", None)
        os.environ["SUPABASE_URL"] = "https://zcjodsewjugovlmocgrz.supabase.co"
        os.environ["SUPABASE_DB_PASSWORD"] = "secret"
        url = resolve_database_url()
        self.assertIn("postgres.zcjodsewjugovlmocgrz:secret", url)
        self.assertIn("pooler.supabase.com:6543/postgres?sslmode=require", url)


if __name__ == "__main__":
    unittest.main()
