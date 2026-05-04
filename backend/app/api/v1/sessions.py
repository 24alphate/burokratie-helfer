import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.session import SessionCreate, SessionRead

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionRead, status_code=201)
def create_session(payload: SessionCreate, db: Session = Depends(get_db)):
    token = str(uuid.uuid4())
    user = User(
        session_token=token,
        preferred_language=payload.preferred_language,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return SessionRead(
        session_token=user.session_token,
        user_id=user.id,
        preferred_language=user.preferred_language,
    )


@router.get("/me", response_model=SessionRead)
def get_me(user: User = Depends(get_current_user)):
    return SessionRead(
        session_token=user.session_token,
        user_id=user.id,
        preferred_language=user.preferred_language,
    )
