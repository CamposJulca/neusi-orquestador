from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.server import Server
from app.schemas.server import ProjectSummary
from app.services.monitor_service import MonitorService


router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/{server_code}", response_model=ProjectSummary)
def get_server_projects(server_code: str, db: Session = Depends(get_db)) -> ProjectSummary:
    server = db.query(Server).filter(Server.code == server_code).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return MonitorService().get_projects(server)
