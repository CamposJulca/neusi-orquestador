from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePosixPath

from fastapi import HTTPException

from app.models.server import Server
from app.config import get_settings
from app.schemas.server import FileTreeItem, FileTreeResponse
from app.services.server_registry import ServerRegistryEntry, get_server_registry_entry
from app.services.ssh_service import SSHExecutionError, SSHService


STATIC_ALLOWED_BASE_PATHS = ["/srv", "/opt", "/var/www"]


class FileTreeService:
    def __init__(self) -> None:
        self.ssh_service = SSHService()
        self.settings = get_settings()

    def get_tree(self, server: Server, path: str, depth: int) -> FileTreeResponse:
        registry = get_server_registry_entry(server.code)
        normalized_path = self.validate_path(path, registry)
        checked_at = datetime.now(timezone.utc)
        username = registry.username if registry else None

        if not self.ssh_service.is_enabled():
            return FileTreeResponse(
                server_id=server.code,
                path=normalized_path,
                connected=False,
                items=[],
                message="No conectado",
                checked_at=checked_at,
            )

        try:
            lines = self.ssh_service.collect_file_tree(
                server.host,
                server.ssh_port,
                normalized_path,
                depth,
                username=username,
            )
            items = self.build_tree(normalized_path, lines)
            return FileTreeResponse(
                server_id=server.code,
                path=normalized_path,
                connected=True,
                items=items,
                message=None if items else "No se encontraron archivos en esta ruta.",
                checked_at=checked_at,
            )
        except SSHExecutionError as exc:
            return FileTreeResponse(
                server_id=server.code,
                path=normalized_path,
                connected=False,
                items=[],
                message=str(exc),
                checked_at=checked_at,
            )

    @staticmethod
    def get_allowed_base_paths(registry: ServerRegistryEntry | None) -> list[str]:
        settings = get_settings()
        return [
            "/home",
            *STATIC_ALLOWED_BASE_PATHS,
            *settings.extra_allowed_file_paths,
        ]

    def validate_path(self, path: str, registry: ServerRegistryEntry | None) -> str:
        normalized = str(PurePosixPath(path))
        allowed_roots = self.get_allowed_base_paths(registry)
        if not any(normalized == root or normalized.startswith(f"{root}/") for root in allowed_roots):
            raise HTTPException(status_code=400, detail="Path not allowed")
        return normalized

    def build_tree(self, base_path: str, lines: list[str]) -> list[FileTreeItem]:
        nodes: dict[str, FileTreeItem] = {}
        roots: list[FileTreeItem] = []

        for line in lines:
            parts = line.split("|", 3)
            if len(parts) != 4:
                continue
            item_path, raw_type, raw_size, modified_at = parts
            node = FileTreeItem(
                name=PurePosixPath(item_path).name,
                path=item_path,
                type="directory" if raw_type == "d" else "file",
                size=self.format_size(int(raw_size)) if raw_type == "f" else None,
                modified_at=modified_at or None,
                children=[],
            )
            nodes[item_path] = node

        for item_path in sorted(nodes.keys()):
            node = nodes[item_path]
            parent_path = str(PurePosixPath(item_path).parent)
            if parent_path == base_path:
                roots.append(node)
                continue
            parent = nodes.get(parent_path)
            if parent:
                parent.children.append(node)
            else:
                roots.append(node)

        self.sort_nodes(roots)
        return roots

    def sort_nodes(self, items: list[FileTreeItem]) -> None:
        items.sort(key=lambda item: (item.type != "directory", item.name.lower()))
        for item in items:
            if item.children:
                self.sort_nodes(item.children)

    @staticmethod
    def format_size(size_bytes: int) -> str:
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(size_bytes)
        unit_index = 0
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        return f"{size:.1f} {units[unit_index]}"
