from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.server import Server
from app.schemas.server import HealthSnapshot
from app.services.monitor_service import MonitorService


router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/{server_code}", response_model=HealthSnapshot)
def get_server_metrics(server_code: str, db: Session = Depends(get_db)) -> HealthSnapshot:
    server = db.query(Server).filter(Server.code == server_code).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return MonitorService().get_health(server)
