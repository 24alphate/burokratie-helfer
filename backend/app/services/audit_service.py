import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog, AuditAction


class AuditService:
    def log(
        self,
        db: Session,
        case_id: str,
        action: AuditAction,
        metadata: dict | None = None,
    ) -> None:
        """
        Write an audit log entry.
        metadata MUST NOT contain raw personal answers — only field_key, template_id, etc.
        """
        entry = AuditLog(
            case_id=case_id,
            action=action.value,
            action_metadata=json.dumps(metadata) if metadata else None,
            created_at=datetime.now(timezone.utc),
        )
        db.add(entry)
        db.flush()


audit_service = AuditService()
