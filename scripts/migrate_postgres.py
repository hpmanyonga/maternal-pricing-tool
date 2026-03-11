#!/usr/bin/env python3
import os
from pathlib import Path

import psycopg


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations" / "postgres"


def run():
    database_url = os.getenv("NETWORK_ONE_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("Set NETWORK_ONE_DATABASE_URL or DATABASE_URL before running migrations")

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        print("No migration files found")
        return

    with psycopg.connect(database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                  filename VARCHAR(255) PRIMARY KEY,
                  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

            for migration in migration_files:
                cur.execute("SELECT 1 FROM schema_migrations WHERE filename = %s", (migration.name,))
                if cur.fetchone():
                    print(f"skip {migration.name}")
                    continue

                sql_text = migration.read_text(encoding="utf-8")
                cur.execute(sql_text)
                cur.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (migration.name,))
                print(f"applied {migration.name}")


if __name__ == "__main__":
    run()
