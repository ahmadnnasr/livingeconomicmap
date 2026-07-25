
from contextlib import contextmanager
from urllib.parse import urlparse
from app.settings import get_settings


def is_postgres() -> bool:
    return get_settings().database_url.startswith(("postgres://", "postgresql://"))

@contextmanager
def connection():
    url = get_settings().database_url
    if is_postgres():
        import psycopg
        conn = psycopg.connect(url)
    else:
        import sqlite3
        path = url.replace("sqlite:///", "")
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def fetch_all(sql: str, params=()):
    with connection() as conn:
        cur=conn.cursor(); cur.execute(sql, params)
        cols=[d[0] for d in cur.description] if cur.description else []
        return [dict(zip(cols,row)) for row in cur.fetchall()]


def execute(sql: str, params=()):
    with connection() as conn:
        cur=conn.cursor(); cur.execute(sql, params); conn.commit()
