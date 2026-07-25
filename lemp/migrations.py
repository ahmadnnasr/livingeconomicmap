from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
from .db import Database


class MigrationRunner:
    def __init__(self, database: Database, migrations_dir: str | Path) -> None:
        self.database = database
        self.migrations_dir = Path(migrations_dir)

    def apply_all(self) -> list[int]:
        applied = []
        with self.database.transaction() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )
            existing = {
                row["version"]
                for row in connection.execute(
                    "SELECT version FROM schema_migrations"
                )
            }

            for path in sorted(self.migrations_dir.glob("*.sql")):
                version_text, name = path.stem.split("_", 1)
                version = int(version_text)
                if version in existing:
                    continue
                connection.executescript(path.read_text())
                connection.execute(
                    """
                    INSERT INTO schema_migrations(version, name, applied_at)
                    VALUES (?, ?, ?)
                    """,
                    (
                        version,
                        name,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                applied.append(version)
        return applied
