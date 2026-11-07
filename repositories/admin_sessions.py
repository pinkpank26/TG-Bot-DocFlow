from database import get_conn


class AdminSessionsRepository:
    def save_auth_state(self, admin_user_id: int, phone: str, phone_code_hash: str, status: str, temp_session: str, expires_after_min: int = 10) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO admin_auth_states(admin_user_id, phone, phone_code_hash, status, temp_session_string, expires_at)
                VALUES(?, ?, ?, ?, ?, datetime('now', ?))
                ON CONFLICT(admin_user_id) DO UPDATE SET
                    phone = excluded.phone,
                    phone_code_hash = excluded.phone_code_hash,
                    status = excluded.status,
                    temp_session_string = excluded.temp_session_string,
                    attempts_count = 0,
                    expires_at = excluded.expires_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (admin_user_id, phone, phone_code_hash, status, temp_session, f"+{expires_after_min} minutes"),
            )

    def get_auth_state(self, admin_user_id: int):
        with get_conn() as conn:
            return conn.execute(
                "SELECT * FROM admin_auth_states WHERE admin_user_id = ?",
                (admin_user_id,),
            ).fetchone()

    def set_auth_status(self, admin_user_id: int, status: str, temp_session: str | None = None, attempts_inc: bool = False) -> None:
        with get_conn() as conn:
            if attempts_inc:
                conn.execute(
                    """
                    UPDATE admin_auth_states
                    SET status = ?,
                        attempts_count = attempts_count + 1,
                        temp_session_string = COALESCE(?, temp_session_string),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE admin_user_id = ?
                    """,
                    (status, temp_session, admin_user_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE admin_auth_states
                    SET status = ?,
                        temp_session_string = COALESCE(?, temp_session_string),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE admin_user_id = ?
                    """,
                    (status, temp_session, admin_user_id),
                )

    def save_authorized_account(
        self,
        admin_user_id: int,
        phone: str,
        telegram_user_id: int,
        username: str | None,
        first_name: str | None,
        encrypted_session: str,
    ) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO admin_telegram_accounts(
                    admin_user_id, phone, telegram_user_id, telegram_username, telegram_first_name, session_encrypted, session_status
                ) VALUES(?, ?, ?, ?, ?, ?, 'active')
                ON CONFLICT(admin_user_id) DO UPDATE SET
                    phone = excluded.phone,
                    telegram_user_id = excluded.telegram_user_id,
                    telegram_username = excluded.telegram_username,
                    telegram_first_name = excluded.telegram_first_name,
                    session_encrypted = excluded.session_encrypted,
                    session_status = 'active',
                    updated_at = CURRENT_TIMESTAMP
                """,
                (admin_user_id, phone, telegram_user_id, username, first_name, encrypted_session),
            )

    def get_account(self, admin_user_id: int):
        with get_conn() as conn:
            return conn.execute(
                "SELECT * FROM admin_telegram_accounts WHERE admin_user_id = ?",
                (admin_user_id,),
            ).fetchone()

    def delete_account(self, admin_user_id: int) -> None:
        with get_conn() as conn:
            conn.execute("DELETE FROM admin_telegram_accounts WHERE admin_user_id = ?", (admin_user_id,))
            conn.execute("DELETE FROM admin_auth_states WHERE admin_user_id = ?", (admin_user_id,))
