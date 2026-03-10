"""Zápis do audit logu – kdo a kdy změnil entitu."""
from sqlalchemy.orm import Session

from app.models import AuditLog


def log(db: Session, entity_type: str, entity_id: int, user_id: int | None, action: str, details: str | None = None) -> None:
    """Přidá záznam do audit logu."""
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        action=action,
        details=details,
    )
    db.add(entry)
