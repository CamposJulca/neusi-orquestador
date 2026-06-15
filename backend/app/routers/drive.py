from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.server import Server
from app.schemas.server import DriveTreeResponse
from app.services.drive_service import DriveService


router = APIRouter(prefix="/drive", tags=["drive"])


@router.get("/tree", response_model=DriveTreeResponse)
def get_drive_tree(
    scope: str = Query(default="root"),
    server_id: str | None = Query(default=None),
    path: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> DriveTreeResponse:
    servers = db.query(Server).filter(Server.is_active.is_(True)).order_by(Server.code.asc()).all()
    return DriveService().get_tree(servers, scope=scope, server_id=server_id, path=path)
