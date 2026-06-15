from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.server import Server
from app.schemas.server import (
    DuplicateFileResponse,
    FileSearchResponse,
    HistoricalSeriesResponse,
    ObservabilityOverviewResponse,
    SnapshotRecord,
)
from app.services.observability_service import ObservabilityService


router = APIRouter(prefix="/observability", tags=["observability"])


def get_server_or_404(db: Session, server_code: str) -> Server:
    server = db.query(Server).filter(Server.code == server_code).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server


@router.get("/{server_code}", response_model=ObservabilityOverviewResponse)
def get_observability_overview(server_code: str, db: Session = Depends(get_db)) -> ObservabilityOverviewResponse:
    return ObservabilityService().get_overview(db, get_server_or_404(db, server_code))


@router.get("/{server_code}/history", response_model=HistoricalSeriesResponse)
def get_observability_history(
    server_code: str,
    limit: int = Query(default=48, ge=1, le=240),
    db: Session = Depends(get_db),
) -> HistoricalSeriesResponse:
    get_server_or_404(db, server_code)
    return ObservabilityService().get_history(db, server_code, limit=limit)


@router.get("/{server_code}/snapshots", response_model=list[SnapshotRecord])
def list_observability_snapshots(
    server_code: str,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[SnapshotRecord]:
    get_server_or_404(db, server_code)
    return ObservabilityService().list_snapshots(db, server_code, limit=limit)


@router.post("/{server_code}/snapshots", response_model=SnapshotRecord)
def capture_observability_snapshot(server_code: str, db: Session = Depends(get_db)) -> SnapshotRecord:
    return ObservabilityService().capture_snapshot(db, get_server_or_404(db, server_code))


@router.get("/{server_code}/files/search", response_model=FileSearchResponse)
def search_observability_files(
    server_code: str,
    q: str = Query(default=""),
    path: str = Query(default="/home"),
    db: Session = Depends(get_db),
) -> FileSearchResponse:
    return ObservabilityService().search_files(get_server_or_404(db, server_code), q, base_path=path)


@router.get("/{server_code}/files/duplicates", response_model=DuplicateFileResponse)
def get_observability_duplicates(
    server_code: str,
    path: str = Query(default="/home"),
    db: Session = Depends(get_db),
) -> DuplicateFileResponse:
    return ObservabilityService().find_duplicates(get_server_or_404(db, server_code), base_path=path)
