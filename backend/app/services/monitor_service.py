from __future__ import annotations

from datetime import datetime, timezone
import logging

from app.config import get_settings
from app.models.server import Server
from app.schemas.server import DashboardResponse, DiskSnapshot, FileSummary, HealthSnapshot, ProjectSummary, ServerResponse, StatusReason, StorageSnapshot
from app.services.server_registry import get_server_registry_entry
from app.services.ssh_service import SSHExecutionError, SSHService


logger = logging.getLogger(__name__)


class MonitorService:
    CRITICAL_CPU_THRESHOLD = 95.0
    WARNING_CPU_THRESHOLD = 85.0
    CRITICAL_MEMORY_THRESHOLD = 92.0
    WARNING_MEMORY_THRESHOLD = 80.0
    CRITICAL_DISK_THRESHOLD = 92.0
    WARNING_DISK_THRESHOLD = 85.0

    def __init__(self) -> None:
        self.settings = get_settings()
        self.ssh_service = SSHService()

    def compute_dashboard_entry(self, server: Server) -> DashboardResponse:
        server_response = self.build_server_response(server)
        now = datetime.now(timezone.utc)
        registry = get_server_registry_entry(server.code)
        username = registry.username if registry else None

        if self.ssh_service.is_enabled():
            try:
                snapshot = self.ssh_service.collect_runtime_snapshot(server.host, server.ssh_port, username=username)
                storage = self.try_collect_storage(server, now, username=username)
                return DashboardResponse(
                    server=server_response,
                    health=self.build_live_health(server.code, snapshot, now, storage=storage),
                    files=self.build_dashboard_files(server.code, now),
                    projects=self.build_dashboard_projects(server.code, now),
                )
            except SSHExecutionError as exc:
                return DashboardResponse(
                    server=server_response,
                    health=self.build_offline_health(server.code, now, str(exc)),
                    files=self.build_offline_files(server.code, now),
                    projects=self.build_offline_projects(server.code, now),
                )

        return DashboardResponse(
            server=server_response,
            health=self.build_offline_health(server.code, now, "SSH deshabilitado"),
            files=self.build_offline_files(server.code, now),
            projects=self.build_offline_projects(server.code, now),
        )

    def get_dashboard_entry(self, server: Server) -> DashboardResponse:
        return self.compute_dashboard_entry(server)

    def get_health(self, server: Server) -> HealthSnapshot:
        return self.compute_dashboard_entry(server).health

    def get_files(self, server: Server) -> FileSummary:
        now = datetime.now(timezone.utc)
        registry = get_server_registry_entry(server.code)
        username = registry.username if registry else None
        if self.ssh_service.is_enabled():
            return self.build_live_files(server, now, username=username)
        return self.build_offline_files(server.code, now)

    def get_projects(self, server: Server) -> ProjectSummary:
        now = datetime.now(timezone.utc)
        registry = get_server_registry_entry(server.code)
        username = registry.username if registry else None
        if self.ssh_service.is_enabled():
            return self.build_live_projects(server, now, username=username)
        return self.build_offline_projects(server.code, now)

    def get_storage(self, server: Server) -> StorageSnapshot:
        now = datetime.now(timezone.utc)
        registry = get_server_registry_entry(server.code)
        username = registry.username if registry else None
        return self.try_collect_storage(server, now, username=username)

    def build_error_dashboard_entry(self, server: Server, error: str) -> DashboardResponse:
        server_response = self.build_server_response(server)
        now = datetime.now(timezone.utc)
        return DashboardResponse(
            server=server_response,
            health=self.build_offline_health(server.code, now, error),
            files=self.build_offline_files(server.code, now),
            projects=self.build_offline_projects(server.code, now),
        )

    @staticmethod
    def build_server_response(server: Server) -> ServerResponse:
        registry = get_server_registry_entry(server.code)
        # host/ssh_port/name/environment = fuente de verdad la DB (alimentada por
        # auto-registro). El registry (servers.py) solo aporta metadatos que la DB
        # no tiene: real_ip, usuario SSH y rol.
        return ServerResponse(
            id=server.id,
            code=server.code,
            name=server.name,
            host=server.host,
            ssh_port=server.ssh_port,
            environment=server.environment,
            is_active=server.is_active,
            real_ip=registry.real_ip if registry else None,
            ssh_username=registry.username if registry else None,
            role=registry.role if registry else server.environment,
            created_at=server.created_at,
            updated_at=server.updated_at,
        )

    def build_live_health(
        self,
        server_code: str,
        snapshot: dict[str, object],
        checked_at: datetime,
        storage: StorageSnapshot | None = None,
    ) -> HealthSnapshot:
        cpu_usage = self.parse_optional_float(snapshot.get("cpu")) or 0.0
        memory_usage = self.parse_optional_float(snapshot.get("memory")) or 0.0
        disks = self.parse_disk_snapshots(snapshot.get("disks"))
        root_disk = next((disk for disk in disks if disk.mount == "/"), None)
        disk_usage = root_disk.usage_percent if root_disk else (self.parse_optional_float(snapshot.get("disk")) or 0.0)
        latency_ms = int(snapshot["latency"])
        temperature_c = self.parse_optional_float(snapshot.get("temperature"))
        docker_containers = [str(item) for item in snapshot.get("docker_containers", [])]
        running_services = [str(item) for item in snapshot.get("running_services", [])]
        open_ports = [str(item) for item in snapshot.get("open_ports", [])]
        status, status_reasons = self.classify_health(cpu_usage, memory_usage, disks, storage)

        return HealthSnapshot(
            server_code=server_code,
            status=status,
            status_reasons=status_reasons,
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            disk_usage=disk_usage,
            disks=disks,
            temperature_c=temperature_c,
            temperature_label=f"{temperature_c:.1f} C" if temperature_c is not None else "No disponible",
            uptime=str(snapshot.get("uptime", "No disponible")),
            latency_ms=latency_ms,
            latency_label=f"{latency_ms} ms",
            connection_status="online",
            connection_message="Conectado",
            ssh_status="online",
            docker_containers=docker_containers,
            docker_count=len(docker_containers),
            running_services=running_services,
            services_count=len(running_services),
            open_ports=open_ports,
            ports_count=len(open_ports),
            storage=storage,
            checked_at=checked_at,
            source="ssh",
        )

    @staticmethod
    def build_offline_health(server_code: str, checked_at: datetime, error: str) -> HealthSnapshot:
        return HealthSnapshot(
            server_code=server_code,
            status="offline",
            status_reasons=[],
            cpu_usage=None,
            memory_usage=None,
            disk_usage=None,
            disks=[],
            temperature_c=None,
            temperature_label="No disponible",
            uptime="No disponible",
            latency_ms=None,
            latency_label="timeout",
            connection_status="offline",
            connection_message="No conectado",
            ssh_status="offline",
            last_error=error,
            docker_containers=[],
            docker_count=0,
            running_services=[],
            services_count=0,
            open_ports=[],
            ports_count=0,
            storage=None,
            checked_at=checked_at,
            source="ssh-offline",
        )

    def build_live_files(self, server: Server, checked_at: datetime, username: str | None = None) -> FileSummary:
        try:
            payload = self.ssh_service.collect_file_summary(server.host, server.ssh_port, username=username)
            indexed_paths = [item for item in str(payload.get("indexed_paths", "")).split("|") if item]
            total_files = int(str(payload.get("total_files", "0")))
            return FileSummary(
                server_code=server.code,
                indexed_paths=indexed_paths,
                total_files=total_files,
                last_scan=checked_at,
                source="ssh",
            )
        except SSHExecutionError as exc:
            logger.warning("SSH file summary failed server=%s error=%s", server.code, exc)
            return self.build_offline_files(server.code, checked_at)

    def build_dashboard_files(self, server_code: str, checked_at: datetime) -> FileSummary:
        indexed_paths = list(self.settings.monitored_file_paths)
        if server_code == self.settings.backup_server_id and self.settings.storage_mount_path not in indexed_paths:
            indexed_paths.append(self.settings.storage_mount_path)
        return FileSummary(
            server_code=server_code,
            indexed_paths=indexed_paths,
            total_files=0,
            last_scan=checked_at,
            source="dashboard-static",
        )

    @staticmethod
    def build_offline_files(server_code: str, checked_at: datetime) -> FileSummary:
        return FileSummary(
            server_code=server_code,
            indexed_paths=[],
            total_files=0,
            last_scan=checked_at,
            source="offline",
        )

    def build_live_projects(self, server: Server, checked_at: datetime, username: str | None = None) -> ProjectSummary:
        try:
            payload = self.ssh_service.collect_project_summary(server.host, server.ssh_port, username=username)
            projects, stacks = self.parse_project_markers(payload.get("project_markers", []))
            return ProjectSummary(
                server_code=server.code,
                projects=projects,
                detected_stacks=stacks,
                last_scan=checked_at,
                source="ssh",
            )
        except SSHExecutionError as exc:
            logger.warning("SSH project summary failed server=%s error=%s", server.code, exc)
            return self.build_offline_projects(server.code, checked_at)

    @staticmethod
    def build_dashboard_projects(server_code: str, checked_at: datetime) -> ProjectSummary:
        return ProjectSummary(
            server_code=server_code,
            projects=[],
            detected_stacks=[],
            last_scan=checked_at,
            source="dashboard-static",
        )

    @staticmethod
    def build_offline_projects(server_code: str, checked_at: datetime) -> ProjectSummary:
        return ProjectSummary(
            server_code=server_code,
            projects=[],
            detected_stacks=[],
            last_scan=checked_at,
            source="offline",
        )

    def try_collect_storage(
        self,
        server: Server,
        checked_at: datetime,
        username: str | None = None,
    ) -> StorageSnapshot | None:
        if server.code != self.settings.backup_server_id:
            return None

        try:
            payload = self.ssh_service.collect_storage_snapshot(
                server.host,
                server.ssh_port,
                self.settings.storage_mount_path,
                username=username,
            )
            mounted = payload.get("mounted") == "yes"
            usage_percent = self.parse_optional_float(payload.get("usage_percent"))
            return StorageSnapshot(
                server_code=server.code,
                mount_path=self.settings.storage_mount_path,
                mounted=mounted,
                filesystem=payload.get("filesystem"),
                total=payload.get("total"),
                used=payload.get("used"),
                free=payload.get("free"),
                usage_percent=usage_percent,
                usage_label=f"{usage_percent:.1f}%" if usage_percent is not None else "No disponible",
                checked_at=checked_at,
                source="ssh",
                message="Montado" if mounted else "No montado",
            )
        except SSHExecutionError as exc:
            logger.warning("SSH storage summary failed server=%s error=%s", server.code, exc)
            return StorageSnapshot(
                server_code=server.code,
                mount_path=self.settings.storage_mount_path,
                mounted=False,
                usage_label="No conectado",
                checked_at=checked_at,
                source="ssh-offline",
                message=str(exc),
            )

    def classify_health(
        self,
        cpu_usage: float,
        memory_usage: float,
        disks: list[DiskSnapshot],
        storage: StorageSnapshot | None = None,
    ) -> tuple[str, list[StatusReason]]:
        critical_reasons: list[StatusReason] = []
        warning_reasons: list[StatusReason] = []

        if cpu_usage >= self.CRITICAL_CPU_THRESHOLD:
            critical_reasons.append(self.build_reason("critical", "cpu", "CPU", cpu_usage, self.CRITICAL_CPU_THRESHOLD, "CPU supera el umbral critical"))
        elif cpu_usage >= self.WARNING_CPU_THRESHOLD:
            warning_reasons.append(self.build_reason("warning", "cpu", "CPU", cpu_usage, self.WARNING_CPU_THRESHOLD, "CPU supera el umbral warning"))

        if memory_usage >= self.CRITICAL_MEMORY_THRESHOLD:
            critical_reasons.append(self.build_reason("critical", "memory", "RAM", memory_usage, self.CRITICAL_MEMORY_THRESHOLD, "La memoria supera el umbral critical"))
        elif memory_usage >= self.WARNING_MEMORY_THRESHOLD:
            warning_reasons.append(self.build_reason("warning", "memory", "RAM", memory_usage, self.WARNING_MEMORY_THRESHOLD, "La memoria supera el umbral warning"))

        for disk in disks:
            if disk.usage_percent >= self.CRITICAL_DISK_THRESHOLD:
                critical_reasons.append(
                    self.build_reason(
                        "critical",
                        "disk",
                        disk.mount,
                        disk.usage_percent,
                        self.CRITICAL_DISK_THRESHOLD,
                        f"La particion {disk.mount} supera el umbral critical",
                    )
                )
            elif disk.usage_percent >= self.WARNING_DISK_THRESHOLD:
                warning_reasons.append(
                    self.build_reason(
                        "warning",
                        "disk",
                        disk.mount,
                        disk.usage_percent,
                        self.WARNING_DISK_THRESHOLD,
                        f"La particion {disk.mount} supera el umbral warning",
                    )
                )

        if storage and storage.usage_percent is not None:
            if storage.usage_percent >= self.CRITICAL_DISK_THRESHOLD:
                critical_reasons.append(
                    self.build_reason(
                        "critical",
                        "storage",
                        storage.mount_path,
                        storage.usage_percent,
                        self.CRITICAL_DISK_THRESHOLD,
                        f"El storage {storage.mount_path} supera el umbral critical",
                    )
                )
            elif storage.usage_percent >= self.WARNING_DISK_THRESHOLD:
                warning_reasons.append(
                    self.build_reason(
                        "warning",
                        "storage",
                        storage.mount_path,
                        storage.usage_percent,
                        self.WARNING_DISK_THRESHOLD,
                        f"El storage {storage.mount_path} supera el umbral warning",
                    )
                )

        if critical_reasons:
            return "critical", critical_reasons + warning_reasons
        if warning_reasons:
            return "warning", warning_reasons
        return "healthy", []

    @staticmethod
    def build_reason(level: str, metric: str, target: str, value: float, threshold: float, message: str) -> StatusReason:
        return StatusReason(
            level=level,
            metric=metric,
            target=target,
            value=round(value, 1),
            threshold=threshold,
            message=message,
        )

    @staticmethod
    def parse_optional_float(value: object) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(str(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def parse_disk_snapshots(value: object) -> list[DiskSnapshot]:
        if not isinstance(value, list):
            return []

        disks: list[DiskSnapshot] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            try:
                disks.append(DiskSnapshot(**item))
            except Exception:
                logger.debug("Ignoring invalid disk snapshot payload: %s", item)
        return disks

    @staticmethod
    def parse_project_markers(markers: list[object]) -> tuple[list[str], list[str]]:
        projects: set[str] = set()
        stacks: set[str] = set()
        for marker in markers:
            raw = str(marker)
            if "|" not in raw:
                continue
            project_path, marker_name = raw.split("|", 1)
            projects.add(project_path)
            lowered = marker_name.lower()
            if lowered == "package.json":
                stacks.add("node")
            elif lowered == "pyproject.toml":
                stacks.add("python")
            elif lowered == "requirements.txt":
                stacks.add("python")
            elif lowered == "dockerfile":
                stacks.add("docker")
            elif lowered == "docker-compose.yml":
                stacks.add("docker-compose")
            elif lowered == ".git":
                stacks.add("git")
        return sorted(projects), sorted(stacks)
