"""User administration endpoints (admin only)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.core.security import hash_password
from app.models import User
from app.schemas import UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """List all registered users."""
    return db.query(User).order_by(User.created_at.desc()).all()


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Update a user's profile / role / active state / credentials."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="You cannot disable your own account")
    data = payload.model_dump(exclude_unset=True)
    # Credential rotation: username must stay unique, password is
    # never stored raw - only its bcrypt hash.
    new_username = data.pop("username", None)
    new_password = data.pop("password", None)
    if new_username and new_username != user.username:
        taken = db.query(User).filter(User.username == new_username).first()
        if taken:
            raise HTTPException(status_code=409, detail="Username already taken")
        user.username = new_username
    if new_password:
        user.hashed_password = hash_password(new_password)
    for field, value in data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user
