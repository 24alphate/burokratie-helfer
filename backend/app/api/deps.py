from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User


def get_current_user(
    x_session_token: str = Header(..., alias="X-Session-Token"),
    db: Session = Depends(get_db),
) -> User:
    user = db.query(User).filter(User.session_token == x_session_token).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token.",
        )
    return user
