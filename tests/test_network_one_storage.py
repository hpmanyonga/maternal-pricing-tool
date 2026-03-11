import unittest
import os

from engine.network_one_models import NetworkOneEpisodeInput
from engine.network_one_pricing import NetworkOneEpisodePricingEngine
from engine.network_one_storage import (
    AuditLogRecord,
    InstallmentRecord,
    NetworkOneStorage,
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
