from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.server import Server
from app.schemas.server import DashboardResponse
from app.services.dashboard_cache_service import dashboard_cache_service


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/health", response_model=list[DashboardResponse])
def get_dashboard_health(db: Session = Depends(get_db)) -> list[DashboardResponse]:
    servers = db.query(Server).filter(Server.is_active.is_(True)).order_by(Server.code.asc()).all()
    return dashboard_cache_service.get_summary(servers)
