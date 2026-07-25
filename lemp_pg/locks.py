from __future__ import annotations
from contextlib import contextmanager
import hashlib

from .db import PostgresDatabase


def advisory_lock_key(namespace: str, resource: str) -> int:
    digest = hashlib.sha256(f"{namespace}:{resource}".encode()).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


class AdvisoryLockManager:
    def __init__(self, db: PostgresDatabase) -> None:
        self.db = db

    @contextmanager
    def try_lock(self, namespace: str, resource: str):
        key = advisory_lock_key(namespace, resource)
        with self.db.connection() as conn:
            acquired = conn.execute(
                "SELECT pg_try_advisory_lock(%s)",
                (key,),
            ).fetchone()[0]
            try:
                yield bool(acquired)
            finally:
                if acquired:
                    conn.execute(
                        "SELECT pg_advisory_unlock(%s)",
                        (key,),
                    )
