"""Compatibility shim for main.py's admin-session lookups.

Admin Telegram accounts are connected through the web auth flow
(web/server.py + services/admin_sessions.py), not a separate Telegram bot.
This module just exposes the two accessors main.py expects, backed by the
same admin_telegram_accounts table.
"""

from database import get_conn
from services.security import decrypt_session


def get_admin_session(user_id: int):
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT phone, session_encrypted, telegram_first_name
            FROM admin_telegram_accounts
            WHERE admin_user_id = ? AND session_status = 'active'
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return None
    session_string = decrypt_session(row["session_encrypted"])
    return row["phone"], session_string, row["telegram_first_name"]


def get_all_active_admins():
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT admin_user_id, phone, telegram_first_name
            FROM admin_telegram_accounts
            WHERE session_status = 'active'
            """,
        ).fetchall()
    return [(row["admin_user_id"], row["phone"], row["telegram_first_name"]) for row in rows]
