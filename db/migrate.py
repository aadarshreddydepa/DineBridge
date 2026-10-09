"""Apply unapplied SQL migrations to local or hosted PostgreSQL."""

import os
from pathlib import Path
import sys

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "db" / "migrations"
load_dotenv(ROOT / ".env", override=False)


def connection_options():
    if os.environ.get("DATABASE_URL"):
        return {"conninfo": os.environ["DATABASE_URL"]}
    return {
        "host": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "port": int(os.environ.get("POSTGRES_PORT", "5432")),
        "dbname": os.environ.get("POSTGRES_DB", "dinebridge"),
        "user": os.environ.get("POSTGRES_USER", "dinebridge"),
        "password": os.environ["POSTGRES_PASSWORD"],
    }


def main() -> int:
    migrations = sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql"))
    if not migrations:
        raise RuntimeError("No SQL migrations found")

    with psycopg.connect(autocommit=True, **connection_options()) as conn:
        exists = conn.execute("SELECT to_regclass('public.schema_migration') IS NOT NULL").fetchone()[0]
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migration")} if exists else set()
        for migration in migrations:
            if migration.stem in applied:
                print(f"Already applied: {migration.stem}")
                continue
            conn.execute(migration.read_text())
            print(f"Applied: {migration.stem}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, OSError, psycopg.Error) as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        sys.exit(1)
