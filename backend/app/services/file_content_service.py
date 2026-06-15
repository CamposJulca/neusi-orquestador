from __future__ import annotations

import mimetypes
from datetime import datetime, timezone
from pathlib import PurePosixPath

from app.models.server import Server
from app.schemas.server import FilePreviewResponse
from app.services.file_tree_service import FileTreeService
from app.services.server_registry import get_server_registry_entry
from app.services.ssh_service import SSHExecutionError, SSHService


TEXT_PREVIEW_LIMIT = 200_000
TEXT_EXTENSIONS = {
    ".md",
    ".markdown",
    ".txt",
    ".log",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".yml",
    ".yaml",
    ".xml",
    ".html",
    ".css",
    ".sh",
    ".sql",
    ".env",
    ".cfg",
    ".conf",
    ".ini",
}


class FileContentService:
    def __init__(self) -> None:
        self.ssh_service = SSHService()
        self.file_tree_service = FileTreeService()

    def get_preview(self, server: Server, path: str) -> FilePreviewResponse:
        registry = get_server_registry_entry(server.code)
        normalized_path = self.file_tree_service.validate_path(path, registry)
        checked_at = datetime.now(timezone.utc)
        username = registry.username if registry else None

        if not self.ssh_service.is_enabled():
            return self.build_offline_preview(server.code, normalized_path, checked_at)

        try:
            metadata = self.ssh_service.read_remote_file_metadata(
                server.host,
                server.ssh_port,
                normalized_path,
                username=username,
            )
            mime_type = self.normalize_mime_type(normalized_path, metadata["mime_type"])
            preview_kind = self.resolve_preview_kind(mime_type)
            text_content = None
            if preview_kind == "text":
                text_content = self.ssh_service.read_remote_text_preview(
                    server.host,
                    server.ssh_port,
                    normalized_path,
                    TEXT_PREVIEW_LIMIT,
                    username=username,
                )
            return FilePreviewResponse(
                server_id=server.code,
                path=normalized_path,
                connected=True,
                name=PurePosixPath(normalized_path).name,
                type=metadata["type"],
                mime_type=mime_type,
                size=metadata["size"],
                modified_at=metadata["modified_at"],
                preview_kind=preview_kind,
                text_content=text_content,
                checked_at=checked_at,
            )
        except SSHExecutionError as exc:
            return self.build_offline_preview(server.code, normalized_path, checked_at, str(exc))

    def build_offline_preview(
        self,
        server_code: str,
        path: str,
        checked_at: datetime,
        message: str = "No conectado",
    ) -> FilePreviewResponse:
        return FilePreviewResponse(
            server_id=server_code,
            path=path,
            connected=False,
            name=PurePosixPath(path).name,
            type="file",
            mime_type="application/octet-stream",
            size=None,
            modified_at=None,
            preview_kind="offline",
            message=message,
            checked_at=checked_at,
        )

    @staticmethod
    def resolve_preview_kind(mime_type: str) -> str:
        if mime_type.startswith("image/"):
            return "image"
        if mime_type.startswith("video/"):
            return "video"
        if mime_type.startswith("text/") or mime_type in {
            "application/json",
            "application/xml",
            "application/javascript",
        }:
            return "text"
        return "unsupported"

    @staticmethod
    def normalize_mime_type(path: str, detected_mime_type: str) -> str:
        suffix = PurePosixPath(path).suffix.lower()
        if suffix in TEXT_EXTENSIONS:
            if suffix in {".md", ".markdown"}:
                return "text/markdown"
            if suffix in {".yml", ".yaml"}:
                return "text/yaml"
            if suffix == ".json":
                return "application/json"
            return "text/plain"

        mime_type = detected_mime_type or FileContentService.guess_mime_type(path)
        return mime_type or "application/octet-stream"

    @staticmethod
    def guess_mime_type(path: str) -> str:
        mime_type, _ = mimetypes.guess_type(path)
        return mime_type or "application/octet-stream"
