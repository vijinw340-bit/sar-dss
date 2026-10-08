"""Aircraft catalog endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.models import Aircraft, User
from app.schemas import AircraftCreate, AircraftOut

router = APIRouter(prefix="/aircraft", tags=["Aircraft"])


@router.get("", response_model=list[AircraftOut])
def list_aircraft(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List the aircraft catalog (search/assist aircraft)."""
    return db.query(Aircraft).order_by(Aircraft.name).all()


@router.post("", response_model=AircraftOut, status_code=status.HTTP_201_CREATED)
def create_aircraft(
    payload: AircraftCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Add an aircraft to the catalog (admin only)."""
    if (
        db.query(Aircraft)
        .filter(Aircraft.registration_number == payload.registration_number)
        .first()
    ):
        raise HTTPException(
            status_code=409, detail="Registration number already exists"
        )
    aircraft = Aircraft(**payload.model_dump())
    db.add(aircraft)
    db.commit()
    db.refresh(aircraft)
    return aircraft
