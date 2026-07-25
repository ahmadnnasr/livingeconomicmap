from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Optional, Any


class DependencyError(RuntimeError):
    pass


@dataclass
class PostgresConfig:
    dsn: str
    minimum_pool_size: int = 1
    maximum_pool_size: int = 10
    timeout_seconds: float = 10.0


class PostgresDatabase:
    """
    Thin wrapper around psycopg 3 and psycopg_pool.

    Imports are delayed so unit tests can validate SQL and control flow without
    requiring a running PostgreSQL server.
    """

    def __init__(self, config: PostgresConfig) -> None:
        self.config = config
        self._pool = None

    def open(self) -> None:
        try:
            from psycopg_pool import ConnectionPool
        except ImportError as exc:
            raise DependencyError(
                "Install psycopg[binary] and psycopg_pool for PostgreSQL runtime."
            ) from exc

        self._pool = ConnectionPool(
            conninfo=self.config.dsn,
            min_size=self.config.minimum_pool_size,
            max_size=self.config.maximum_pool_size,
            timeout=self.config.timeout_seconds,
            kwargs={"autocommit": False},
        )
        self._pool.open()

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()

    @contextmanager
    def connection(self):
        if self._pool is None:
            raise RuntimeError("Database pool is not open.")
        with self._pool.connection() as conn:
            yield conn

    @contextmanager
    def transaction(self):
        with self.connection() as conn:
            with conn.transaction():
                yield conn
