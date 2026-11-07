import secrets

from database import get_conn


class WebAuthTokensRepository:
    def create_token(self, admin_user_id: int, ttl_minutes: int = 15) -> str:
        token = secrets.token_urlsafe(32)
        with get_conn() as conn:
            conn.execute("DELETE FROM admin_web_auth_tokens WHERE admin_user_id = ?", (admin_user_id,))
            conn.execute(
                """
                INSERT INTO admin_web_auth_tokens(token, admin_user_id, expires_at)
                VALUES(?, ?, datetime('now', ?))
                """,
                (token, admin_user_id, f"+{ttl_minutes} minutes"),
            )
        return token

    def get_token(self, token: str):
        with get_conn() as conn:
            return conn.execute(
                "SELECT admin_user_id, expires_at FROM admin_web_auth_tokens WHERE token = ?",
                (token,),
            ).fetchone()

    def delete_token(self, token: str) -> None:
        with get_conn() as conn:
            conn.execute("DELETE FROM admin_web_auth_tokens WHERE token = ?", (token,))
