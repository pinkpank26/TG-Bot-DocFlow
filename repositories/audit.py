import json
from typing import Any

from database import get_conn


class AuditRepository:
    def log(self, actor_user_id: int | None, action: str, target_type: str | None = None, target_id: str | None = None, details: dict[str, Any] | None = None) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO audit_log(actor_user_id, action, target_type, target_id, details_json)
                VALUES(?, ?, ?, ?, ?)
                """,
                (actor_user_id, action, target_type, target_id, json.dumps(details or {}, ensure_ascii=False)),
            )
