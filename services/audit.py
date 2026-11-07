from repositories.audit import AuditRepository


audit_repo = AuditRepository()


def log_action(actor_user_id: int | None, action: str, target_type: str | None = None, target_id: str | None = None, details: dict | None = None) -> None:
    audit_repo.log(actor_user_id, action, target_type, target_id, details)
