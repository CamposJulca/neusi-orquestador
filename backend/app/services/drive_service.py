from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePosixPath

from fastapi import HTTPException

from app.config import get_settings
from app.models.server import Server
from app.schemas.server import DriveTreeItem, DriveTreeResponse
from app.services.file_tree_service import FileTreeService
from app.services.server_registry import get_server_registry_entry
from app.services.ssh_service import SSHExecutionError, SSHService


class DriveService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.file_tree_service = FileTreeService()
        self.ssh_service = SSHService()

    def get_tree(
        self,
        servers: list[Server],
        scope: str,
        server_id: str | None = None,
        path: str | None = None,
    ) -> DriveTreeResponse:
        checked_at = datetime.now(timezone.utc)

        if scope == "root":
            return DriveTreeResponse(
                scope=scope,
                connected=True,
                items=self.build_root_nodes(servers),
                checked_at=checked_at,
            )

        if scope == "shared":
            return DriveTreeResponse(
                scope=scope,
                connected=True,
                items=self.build_shared_nodes(servers),
                checked_at=checked_at,
            )

        if scope != "server":
            raise HTTPException(status_code=400, detail="Invalid drive scope")

        if not server_id:
            raise HTTPException(status_code=400, detail="server_id is required")

        server = next((item for item in servers if item.code == server_id), None)
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")

        if not path:
            return DriveTreeResponse(
                scope=scope,
                server_id=server.code,
                connected=True,
                items=self.build_server_root_nodes(server),
                checked_at=checked_at,
            )

        return self.get_remote_path_tree(server, path, checked_at)

    def build_root_nodes(self, servers: list[Server]) -> list[DriveTreeItem]:
        backup_server = next((server for server in servers if server.code == self.settings.backup_server_id), None)
        items = [
            DriveTreeItem(
                id="drive:shared",
                name=self.settings.shared_drive_name,
                path=self.settings.shared_drive_path,
                type="directory",
                description=f"Carpeta comun entre {len(servers)} maquinas",
                scope="shared",
                expandable=True,
                children_loaded=False,
                children=[],
            ),
        ]

        if backup_server:
            items.append(
                DriveTreeItem(
                    id=f"drive:backup:{backup_server.code}:{self.settings.backup_drive_path}",
                    name=self.settings.backup_drive_name,
                    path=self.settings.backup_drive_path,
                    type="directory",
                    description=f"{backup_server.name} · {self.settings.backup_drive_path}",
                    scope="server",
                    server_id=backup_server.code,
                    server_name=backup_server.name,
                    expandable=True,
                    children_loaded=False,
                    children=[],
                )
            )

        for server in sorted(servers, key=lambda item: item.code):
            items.append(
                DriveTreeItem(
                    id=f"drive:server:{server.code}",
                    name=server.name,
                    type="directory",
                    description=f"{server.environment} · {server.host}:{server.ssh_port}",
                    scope="server",
                    server_id=server.code,
                    server_name=server.name,
                    expandable=True,
                    children_loaded=False,
                    children=[],
                )
            )

        return items

    def build_shared_nodes(self, servers: list[Server]) -> list[DriveTreeItem]:
        shared_path = self.settings.shared_drive_path
        items: list[DriveTreeItem] = []

        for server in sorted(servers, key=lambda item: item.code):
            items.append(
                DriveTreeItem(
                    id=f"drive:shared:{server.code}:{shared_path}",
                    name=server.name,
                    path=shared_path,
                    type="directory",
                    description=f"Ruta compartida · {shared_path}",
                    scope="server",
                    server_id=server.code,
                    server_name=server.name,
                    expandable=True,
                    children_loaded=False,
                    children=[],
                )
            )

        return items

    def build_server_root_nodes(self, server: Server) -> list[DriveTreeItem]:
        registry = get_server_registry_entry(server.code)
        items: list[DriveTreeItem] = []

        for path in self.file_tree_service.get_allowed_base_paths(registry):
            items.append(
                DriveTreeItem(
                    id=f"drive:path:{server.code}:{path}",
                    name=PurePosixPath(path).name or path,
                    path=path,
                    type="directory",
                    description=path,
                    scope="server",
                    server_id=server.code,
                    server_name=server.name,
                    expandable=True,
                    children_loaded=False,
                    children=[],
                )
            )

        return items

    def get_remote_path_tree(self, server: Server, path: str, checked_at: datetime) -> DriveTreeResponse:
        registry = get_server_registry_entry(server.code)
        normalized_path = self.file_tree_service.validate_path(path, registry)
        username = registry.username if registry else None

        if not self.ssh_service.is_enabled():
            return DriveTreeResponse(
                scope="server",
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
                1,
                username=username,
            )
            items = self.build_remote_nodes(server, normalized_path, lines)
            return DriveTreeResponse(
                scope="server",
                server_id=server.code,
                path=normalized_path,
                connected=True,
                items=items,
                message=None if items else "No se encontraron archivos en esta ruta.",
                checked_at=checked_at,
            )
        except SSHExecutionError as exc:
            return DriveTreeResponse(
                scope="server",
                server_id=server.code,
                path=normalized_path,
                connected=False,
                items=[],
                message=str(exc),
                checked_at=checked_at,
            )

    def build_remote_nodes(self, server: Server, base_path: str, lines: list[str]) -> list[DriveTreeItem]:
        nodes: dict[str, DriveTreeItem] = {}
        roots: list[DriveTreeItem] = []

        for line in lines:
            parts = line.split("|", 3)
            if len(parts) != 4:
                continue
            item_path, raw_type, raw_size, modified_at = parts
            is_directory = raw_type == "d"
            nodes[item_path] = DriveTreeItem(
                id=f"drive:item:{server.code}:{item_path}",
                name=PurePosixPath(item_path).name,
                path=item_path,
                type="directory" if is_directory else "file",
                size=self.file_tree_service.format_size(int(raw_size)) if raw_type == "f" else None,
                modified_at=modified_at or None,
                description=item_path,
                scope="server",
                server_id=server.code,
                server_name=server.name,
                expandable=is_directory,
                children_loaded=False if is_directory else True,
                children=[],
            )

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

    def sort_nodes(self, items: list[DriveTreeItem]) -> None:
        items.sort(key=lambda item: (item.type != "directory", item.name.lower()))
        for item in items:
            if item.children:
                self.sort_nodes(item.children)
