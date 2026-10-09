"""Apply unapplied SQL migrations to the local Compose PostgreSQL service."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "db" / "migrations"
PSQL = [
    "docker", "compose", "exec", "-T", "db", "sh", "-c",
    'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atq',
]


def sql(statement: str) -> str:
    result = subprocess.run(
        PSQL, input=statement, text=True, capture_output=True, cwd=ROOT, check=False
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def main() -> int:
    migrations = sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql"))
    if not migrations:
        raise RuntimeError("No SQL migrations found")

    exists = sql("SELECT to_regclass('public.schema_migration') IS NOT NULL;") == "t"
    applied = set(sql("SELECT version FROM schema_migration;").splitlines()) if exists else set()

    for migration in migrations:
        if migration.stem in applied:
            print(f"Already applied: {migration.stem}")
            continue
        sql(migration.read_text())
        print(f"Applied: {migration.stem}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, OSError) as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        sys.exit(1)
