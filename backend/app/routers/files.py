from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.server import Server
from app.schemas.server import FilePreviewResponse, FileSummary, FileTreeResponse
from app.services.file_content_service import FileContentService
from app.services.file_tree_service import FileTreeService
from app.services.monitor_service import MonitorService
from app.services.server_registry import get_server_registry_entry
from app.services.ssh_service import SSHExecutionError, SSHService


router = APIRouter(prefix="/files", tags=["files"])


@router.get("/tree", response_model=FileTreeResponse)
def get_server_file_tree(
    server_id: str = Query(...),
    path: str = Query(...),
    depth: int = Query(default=2, ge=1, le=4),
    db: Session = Depends(get_db),
) -> FileTreeResponse:
    server = db.query(Server).filter(Server.code == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return FileTreeService().get_tree(server, path, depth)


@router.get("/preview", response_model=FilePreviewResponse)
def get_server_file_preview(
    server_id: str = Query(...),
    path: str = Query(...),
    db: Session = Depends(get_db),
) -> FilePreviewResponse:
    server = db.query(Server).filter(Server.code == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return FileContentService().get_preview(server, path)


@router.get("/raw")
def get_server_file_raw(
    server_id: str = Query(...),
    path: str = Query(...),
    download: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> Response:
    server = db.query(Server).filter(Server.code == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    registry = get_server_registry_entry(server.code)
    normalized_path = FileTreeService().validate_path(path, registry)
    username = registry.username if registry else None

    try:
        content_stream, mime_type = SSHService().stream_remote_file(
            server.host,
            server.ssh_port,
            normalized_path,
            username=username,
        )
    except SSHExecutionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{PurePosixPath(normalized_path).name}"'
    return StreamingResponse(content_stream, media_type=mime_type, headers=headers)


@router.get("/{server_code}", response_model=FileSummary)
def get_server_files(server_code: str, db: Session = Depends(get_db)) -> FileSummary:
    server = db.query(Server).filter(Server.code == server_code).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return MonitorService().get_files(server)
