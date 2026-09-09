"""Validate the ordered, immutable Supabase migration ledger."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
CHECKSUMS_PATH = MIGRATIONS_DIR / "checksums.sha256"
MIGRATION_NAME = re.compile(r"^\d{14}_[a-z][a-z0-9_]*\.sql$")


def check_migrations() -> None:
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    names = [migration.name for migration in migration_files]
    if not names:
        raise ValueError("no migration files found")
    if any(MIGRATION_NAME.fullmatch(name) is None for name in names):
        raise ValueError("migration names must use YYYYMMDDHHMMSS_lowercase_name.sql")
    if len(names) != len(set(names)):
        raise ValueError("migration names must be unique")

    checksum_lines = CHECKSUMS_PATH.read_text(encoding="utf-8").splitlines()
    recorded: dict[str, str] = {}
    for line in checksum_lines:
        digest, separator, name = line.partition("  ")
        if not separator or len(digest) != 64:
            raise ValueError("invalid migration checksum ledger")
        recorded[name] = digest

    if list(recorded) != names:
        raise ValueError("migration checksum ledger is missing, extra, or out of order")
    for migration in migration_files:
        digest = hashlib.sha256(migration.read_bytes()).hexdigest()
        if recorded[migration.name] != digest:
            raise ValueError(f"migration was edited after being recorded: {migration.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    parser.parse_args()
    check_migrations()


if __name__ == "__main__":
    main()
