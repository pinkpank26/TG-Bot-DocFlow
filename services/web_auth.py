from datetime import datetime, timezone

from repositories.web_auth_tokens import WebAuthTokensRepository


class WebAuthService:
    def __init__(self):
        self.repo = WebAuthTokensRepository()

    def create_link_token(self, admin_user_id: int) -> str:
        return self.repo.create_token(admin_user_id)

    def resolve_token(self, token: str) -> int | None:
        row = self.repo.get_token(token)
        if not row:
            return None
        if datetime.fromisoformat(row["expires_at"]).replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            self.repo.delete_token(token)
            return None
        return row["admin_user_id"]

    def invalidate(self, token: str) -> None:
        self.repo.delete_token(token)


web_auth_service = WebAuthService()
