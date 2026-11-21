from fastapi import APIRouter

from app.schemas.health import HealthOut
from app.services.health import check_health

router = APIRouter()


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    """Service status and database connectivity."""
    return check_health()
