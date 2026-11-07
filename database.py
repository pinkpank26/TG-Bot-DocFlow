import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from config import settings


MIGRATIONS_DIR = Path(__file__).parent / "migrations"


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.db_path, check_same_thread=False, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def apply_migrations() -> None:
    with get_conn() as conn:
        _ensure_migrations_table(conn)
        applied = {row["name"] for row in conn.execute("SELECT name FROM schema_migrations").fetchall()}
        for file_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if file_path.name in applied:
                continue
            sql = file_path.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.execute("INSERT INTO schema_migrations(name) VALUES (?)", (file_path.name,))


def init_database() -> None:
    apply_migrations()
