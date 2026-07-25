
from pathlib import Path
from app.db import connection, is_postgres

def main():
    folder=Path("migrations/deploy")
    files=sorted(folder.glob("*.sql"))
    with connection() as conn:
        cur=conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cur.execute("SELECT version FROM schema_migrations")
        done={r[0] for r in cur.fetchall()}
        for file in files:
            if file.name in done: continue
            sql=file.read_text()
            if not is_postgres():
                print(f"Skipping PostgreSQL migration {file.name} in SQLite mode")
                continue
            cur.execute(sql)
            cur.execute("INSERT INTO schema_migrations(version) VALUES (%s)",(file.name,))
            print(f"Applied {file.name}")
        conn.commit()
if __name__=="__main__": main()
