from __future__ import annotations
from pathlib import Path

from .db import PostgresDatabase
from .locks import AdvisoryLockManager


class PostgresMigrationRunner:
    def __init__(
        self,
        db: PostgresDatabase,
        migration_dir: str | Path,
    ) -> None:
        self.db = db
        self.migration_dir = Path(migration_dir)
        self.locks = AdvisoryLockManager(db)

    def apply_all(self) -> list[int]:
        applied: list[int] = []
        with self.locks.try_lock("lemp", "schema_migrations") as acquired:
            if not acquired:
                raise RuntimeError("Another migration process holds the lock.")

            with self.db.transaction() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations(
                        version BIGINT PRIMARY KEY,
                        name TEXT NOT NULL,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                existing = {
                    row[0]
                    for row in conn.execute(
                        "SELECT version FROM schema_migrations"
                    ).fetchall()
                }

                for path in sorted(self.migration_dir.glob("*.sql")):
                    version_text, name = path.stem.split("_", 1)
                    version = int(version_text)
                    if version in existing:
                        continue
                    conn.execute(path.read_text())
                    conn.execute(
                        """
                        INSERT INTO schema_migrations(version, name)
                        VALUES (%s, %s)
                        """,
                        (version, name),
                    )
                    applied.append(version)
        return applied
