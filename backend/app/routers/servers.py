from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.server import Server
from app.schemas.server import (
    DashboardResponse,
    HealthSnapshot,
    ServerRegisterRequest,
    ServerResponse,
    StorageSnapshot,
)
from app.services.dashboard_cache_service import dashboard_cache_service
from app.services.monitor_service import MonitorService
from app.services.server_registry import get_server_registry_entry


router = APIRouter(prefix="/servers", tags=["servers"])


@router.post("/register", response_model=ServerResponse)
def register_server(
    payload: ServerRegisterRequest,
    x_register_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> ServerResponse:
    """Auto-registro de endpoint ngrok por un nodo. Actualiza host/puerto en la DB."""
    settings = get_settings()
    if not settings.register_token or x_register_token != settings.register_token:
        raise HTTPException(status_code=401, detail="Token de registro invalido")

    server = db.query(Server).filter(Server.code == payload.code).first()
    if server:
        server.host = payload.host
        server.ssh_port = payload.ssh_port
        server.is_active = True
    else:
        registry = get_server_registry_entry(payload.code)
        server = Server(
            code=payload.code,
            name=payload.name or (registry.name if registry else f"Maquina {payload.code}"),
            host=payload.host,
            ssh_port=payload.ssh_port,
            environment=payload.environment or (registry.role if registry else "internal"),
            is_active=True,
        )
        db.add(server)

    db.commit()
    db.refresh(server)
    dashboard_cache_service.invalidate(payload.code)
    return MonitorService().build_server_response(server)


@router.get("", response_model=list[ServerResponse])
def list_servers(db: Session = Depends(get_db)) -> list[ServerResponse]:
    monitor_service = MonitorService()
    servers = db.query(Server).filter(Server.is_active.is_(True)).order_by(Server.code.asc()).all()
    return [monitor_service.build_server_response(server) for server in servers]


@router.get("/dashboard/summary", response_model=list[DashboardResponse])
def get_dashboard_summary(db: Session = Depends(get_db)) -> list[DashboardResponse]:
    servers = db.query(Server).filter(Server.is_active.is_(True)).order_by(Server.code.asc()).all()
    return dashboard_cache_service.get_summary(servers)


@router.get("/{server_code}/health", response_model=HealthSnapshot)
def get_server_health(server_code: str, db: Session = Depends(get_db)) -> HealthSnapshot:
    server = db.query(Server).filter(Server.code == server_code).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return MonitorService().get_health(server)


@router.get("/104/storage", response_model=StorageSnapshot)
def get_storage_104(db: Session = Depends(get_db)) -> StorageSnapshot:
    server = db.query(Server).filter(Server.code == "104").first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return MonitorService().get_storage(server)


@router.get("/{server_code}", response_model=ServerResponse)
def get_server(server_code: str, db: Session = Depends(get_db)) -> ServerResponse:
    server = db.query(Server).filter(Server.code == server_code).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return MonitorService().build_server_response(server)
