from __future__ import annotations

import json
import shlex
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.observability import ObservabilitySnapshot
from app.models.server import Server
from app.schemas.server import (
    DatabaseHealthSnapshot,
    DashboardResponse,
    DockerContainerSnapshot,
    DuplicateFileGroup,
    DuplicateFileResponse,
    FileSearchResponse,
    FileSearchResult,
    HealthSnapshot,
    HistoricalSeriesResponse,
    HttpHealthcheckResult,
    MetricPoint,
    ObservabilityOverviewResponse,
    ServiceUptimeSnapshot,
    SnapshotRecord,
)
from app.services.file_tree_service import FileTreeService
from app.services.monitor_service import MonitorService
from app.services.server_registry import get_server_registry_entry
from app.services.ssh_service import SSHExecutionError, SSHService


HTTP_CHECKS: dict[str, list[tuple[str, str]]] = {
    "100": [("SSH landing", "http://127.0.0.1:4040")],
    "101": [
        ("Neusi Web", "http://127.0.0.1:8070/health"),
        ("DevOps Neusi", "http://127.0.0.1:8076"),
        ("Dashboard SRNI", "http://127.0.0.1:8085"),
        ("Finanzapp Backend", "http://127.0.0.1:8090"),
    ],
    "102": [("Ngrok API", "http://127.0.0.1:4040/api/tunnels")],
    "103": [("SSH landing", "http://127.0.0.1:4040")],
    "104": [("SSH landing", "http://127.0.0.1:4040")],
    "105": [("SSH landing", "http://127.0.0.1:4040")],
}

SERVICE_CATALOG = [
    "ssh.service",
    "docker.service",
    "nginx.service",
    "postgresql.service",
    "mongod.service",
    "neusi-backend.service",
    "neusi-frontend.service",
]


class ObservabilityService:
    def __init__(self) -> None:
        self.ssh_service = SSHService()
        self.monitor_service = MonitorService()
        self.file_tree_service = FileTreeService()

    def get_overview(self, db: Session, server: Server) -> ObservabilityOverviewResponse:
        server_response = self.monitor_service.build_server_response(server)
        latest_snapshot = self.get_latest_snapshot(db, server.code)
        dashboard_entry = self._restore_dashboard_entry(latest_snapshot) if latest_snapshot else None
        if dashboard_entry is None:
            dashboard_entry = self.monitor_service.compute_dashboard_entry(server)

        return ObservabilityOverviewResponse(
            server=server_response,
            health=dashboard_entry.health,
            http_checks=self.build_http_checks_from_health(server.code, dashboard_entry.health.open_ports),
            service_uptime=self.build_service_uptime_from_health(dashboard_entry.health.running_services),
            docker_containers=self.build_docker_from_health(dashboard_entry.health.docker_containers),
            databases=self.build_database_health_from_ports(dashboard_entry.health.open_ports),
            latest_snapshot=latest_snapshot,
        )

    def capture_snapshot(self, db: Session, server: Server, snapshot_type: str = "manual") -> SnapshotRecord:
        entry = self.monitor_service.compute_dashboard_entry(server)
        snapshot = self.record_dashboard_entry_snapshot(db, entry, snapshot_type=snapshot_type)
        return self.snapshot_to_schema(snapshot)

    def record_dashboard_entry_snapshot(self, db: Session, entry, snapshot_type: str = "auto") -> SnapshotRecord:
        payload = entry.model_dump(mode="json")
        snapshot = ObservabilitySnapshot(
            server_code=entry.server.code,
            snapshot_type=snapshot_type,
            status=entry.health.status,
            cpu_usage=entry.health.cpu_usage,
            memory_usage=entry.health.memory_usage,
            disk_usage=entry.health.disk_usage,
            latency_ms=entry.health.latency_ms,
            payload_json=json.dumps(payload, ensure_ascii=True),
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        return self.snapshot_to_schema(snapshot)

    def get_latest_snapshot(self, db: Session, server_code: str) -> SnapshotRecord | None:
        snapshot = (
            db.query(ObservabilitySnapshot)
            .filter(ObservabilitySnapshot.server_code == server_code)
            .order_by(ObservabilitySnapshot.created_at.desc())
            .first()
        )
        if snapshot is None:
            return None
        return self.snapshot_to_schema(snapshot)

    def get_history(self, db: Session, server_code: str, limit: int = 48) -> HistoricalSeriesResponse:
        snapshots = self.list_snapshot_models(db, server_code, limit)
        snapshots.reverse()
        points = [
            MetricPoint(
                recorded_at=snapshot.created_at,
                cpu_usage=snapshot.cpu_usage,
                memory_usage=snapshot.memory_usage,
                disk_usage=snapshot.disk_usage,
                latency_ms=snapshot.latency_ms,
                status=snapshot.status,
            )
            for snapshot in snapshots
        ]
        latest_snapshot = self.snapshot_to_schema(snapshots[-1]) if snapshots else None
        return HistoricalSeriesResponse(server_code=server_code, points=points, latest_snapshot=latest_snapshot)

    def list_snapshots(self, db: Session, server_code: str, limit: int = 20) -> list[SnapshotRecord]:
        return [self.snapshot_to_schema(snapshot) for snapshot in self.list_snapshot_models(db, server_code, limit)]

    def search_files(self, server: Server, query: str, base_path: str = "/home") -> FileSearchResponse:
        registry = get_server_registry_entry(server.code)
        normalized_path = self.file_tree_service.validate_path(base_path, registry)
        checked_at = datetime.now(timezone.utc)
        username = registry.username if registry else None
        sanitized_query = query.strip()

        if not sanitized_query:
            return FileSearchResponse(
                server_code=server.code,
                query=query,
                base_path=normalized_path,
                connected=True,
                results=[],
                checked_at=checked_at,
                message="Ingresa un termino de busqueda.",
            )

        command = f"""
export QUERY={shlex.quote(sanitized_query.lower())}
export BASE={shlex.quote(normalized_path)}
find "$BASE" -type f -printf '%p|%s|%TY-%Tm-%Td %TH:%TM\\n' 2>/dev/null | \
python3 - <<'PY'
import os
import sys

query = os.environ["QUERY"]
results = []
for line in sys.stdin:
    line = line.rstrip("\\n")
    if not line:
        continue
    path, size, modified = line.split("|", 2)
    if query in path.lower():
        results.append(f"{path}|{size}|{modified}")
    if len(results) >= 120:
        break
print("\\n".join(results))
PY
"""
        try:
            output = self.ssh_service.run_remote_command(server.host, server.ssh_port, command, username=username)
            results = []
            for line in output.splitlines():
                parts = line.split("|", 2)
                if len(parts) != 3:
                    continue
                path, raw_size, modified = parts
                results.append(
                    FileSearchResult(
                        path=path,
                        size=self.file_tree_service.format_size(int(raw_size)) if raw_size.isdigit() else None,
                        modified_at=modified or None,
                    )
                )
            return FileSearchResponse(
                server_code=server.code,
                query=sanitized_query,
                base_path=normalized_path,
                connected=True,
                results=results,
                checked_at=checked_at,
                message=None if results else "No se encontraron archivos.",
            )
        except SSHExecutionError as exc:
            return FileSearchResponse(
                server_code=server.code,
                query=sanitized_query,
                base_path=normalized_path,
                connected=False,
                results=[],
                checked_at=checked_at,
                message=str(exc),
            )

    def find_duplicates(self, server: Server, base_path: str = "/home") -> DuplicateFileResponse:
        registry = get_server_registry_entry(server.code)
        normalized_path = self.file_tree_service.validate_path(base_path, registry)
        checked_at = datetime.now(timezone.utc)
        username = registry.username if registry else None
        command = f"""
export BASE={shlex.quote(normalized_path)}
python3 - <<'PY'
from collections import defaultdict
import hashlib
import json
import os

base = os.environ["BASE"]
files_by_size = defaultdict(list)
seen = 0
for root, _, files in os.walk(base):
    for name in files:
        path = os.path.join(root, name)
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        files_by_size[size].append(path)
        seen += 1
        if seen >= 2500:
            break
    if seen >= 2500:
        break

groups = []
for size, paths in files_by_size.items():
    if len(paths) < 2:
        continue
    digests = defaultdict(list)
    for path in paths:
        try:
            digest = hashlib.sha256()
            with open(path, "rb") as fh:
                while True:
                    chunk = fh.read(1024 * 128)
                    if not chunk:
                        break
                    digest.update(chunk)
        except OSError:
            continue
        digests[digest.hexdigest()].append(path)
    for digest, dup_paths in digests.items():
        if len(dup_paths) > 1:
            groups.append({"fingerprint": digest[:12], "size": size, "files": sorted(dup_paths)})
groups = sorted(groups, key=lambda item: (-item["size"], item["fingerprint"]))[:40]
for group in groups:
    print(json.dumps(group))
PY
"""
        try:
            output = self.ssh_service.run_remote_command(server.host, server.ssh_port, command, username=username)
            groups = []
            for line in output.splitlines():
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                raw_size = int(payload.get("size", 0))
                groups.append(
                    DuplicateFileGroup(
                        fingerprint=str(payload.get("fingerprint", "")),
                        size=self.file_tree_service.format_size(raw_size),
                        files=[str(item) for item in payload.get("files", [])],
                    )
                )
            return DuplicateFileResponse(
                server_code=server.code,
                base_path=normalized_path,
                connected=True,
                groups=groups,
                checked_at=checked_at,
                message=None if groups else "No se detectaron duplicados.",
            )
        except SSHExecutionError as exc:
            return DuplicateFileResponse(
                server_code=server.code,
                base_path=normalized_path,
                connected=False,
                groups=[],
                checked_at=checked_at,
                message=str(exc),
            )

    def collect_http_checks(self, server: Server, username: str | None = None) -> list[HttpHealthcheckResult]:
        checks = HTTP_CHECKS.get(server.code, [])
        if not checks:
            return []
        encoded_checks = "\\n".join(f"{name}|{url}" for name, url in checks)
        command = f"""
printf '%s\n' {shlex.quote(encoded_checks)} | while IFS='|' read -r NAME URL; do
  if [ -z "$NAME" ]; then
    continue
  fi
  START=$(python3 - <<'PY'
import time
print(int(time.time() * 1000))
PY
)
  STATUS=$(curl -k -L -s -o /dev/null -w '%{{http_code}}' --max-time 4 "$URL" 2>/dev/null || echo 000)
  END=$(python3 - <<'PY'
import time
print(int(time.time() * 1000))
PY
)
  ELAPSED=$((END - START))
  if [ "$STATUS" = "000" ]; then
    echo "$NAME|$URL|offline||$ELAPSED|Sin respuesta"
  elif [ "$STATUS" -ge 400 ] 2>/dev/null; then
    echo "$NAME|$URL|warning|$STATUS|$ELAPSED|HTTP error"
  else
    echo "$NAME|$URL|online|$STATUS|$ELAPSED|OK"
  fi
done
"""
        try:
            output = self.ssh_service.run_remote_command(server.host, server.ssh_port, command, username=username)
        except SSHExecutionError:
            return []

        results = []
        for line in output.splitlines():
            parts = line.split("|", 5)
            if len(parts) != 6:
                continue
            name, url, status, raw_code, raw_time, message = parts
            results.append(
                HttpHealthcheckResult(
                    name=name,
                    url=url,
                    status=status,
                    status_code=int(raw_code) if raw_code.isdigit() else None,
                    response_time_ms=int(raw_time) if raw_time.isdigit() else None,
                    message=message or None,
                )
            )
        return results

    def build_http_checks_from_health(self, server_code: str, open_ports: list[str]) -> list[HttpHealthcheckResult]:
        checks = []
        open_port_numbers = {self.extract_port(item) for item in open_ports}
        for name, url in HTTP_CHECKS.get(server_code, []):
            port = self.extract_port(url)
            is_online = port in open_port_numbers if port is not None else False
            checks.append(
                HttpHealthcheckResult(
                    name=name,
                    url=url,
                    status="online" if is_online else "warning",
                    status_code=None,
                    response_time_ms=None,
                    message="Detectado por puerto abierto" if is_online else "Puerto no detectado en snapshot",
                )
            )
        return checks

    @staticmethod
    def build_service_uptime_from_health(running_services: list[str]) -> list[ServiceUptimeSnapshot]:
        return [
            ServiceUptimeSnapshot(
                name=service,
                active_state="active",
                sub_state="running",
                entered_at=None,
                uptime_hint="Detectado en snapshot de salud",
            )
            for service in running_services[:20]
        ]

    @staticmethod
    def build_docker_from_health(docker_containers: list[str]) -> list[DockerContainerSnapshot]:
        return [
            DockerContainerSnapshot(
                name=container,
                image="No capturada",
                status="running",
                running_for="Detectado en snapshot",
            )
            for container in docker_containers[:20]
        ]

    def build_database_health_from_ports(self, open_ports: list[str]) -> list[DatabaseHealthSnapshot]:
        ports = {self.extract_port(item) for item in open_ports}
        return [
            DatabaseHealthSnapshot(
                engine="postgres",
                status="online" if 5432 in ports else "unavailable",
                version=None,
                metric_label="port",
                metric_value="5432" if 5432 in ports else "cerrado",
                message="Puerto PostgreSQL detectado" if 5432 in ports else "Puerto PostgreSQL no detectado",
            ),
            DatabaseHealthSnapshot(
                engine="mongo",
                status="online" if 27017 in ports else "unavailable",
                version=None,
                metric_label="port",
                metric_value="27017" if 27017 in ports else "cerrado",
                message="Puerto Mongo detectado" if 27017 in ports else "Puerto Mongo no detectado",
            ),
        ]

    def collect_service_uptime(self, server: Server, username: str | None = None) -> list[ServiceUptimeSnapshot]:
        services_arg = " ".join(shlex.quote(service) for service in SERVICE_CATALOG)
        command = f"""
for SERVICE in {services_arg}; do
  if systemctl list-unit-files "$SERVICE" >/dev/null 2>&1; then
    ACTIVE=$(systemctl show "$SERVICE" -p ActiveState --value 2>/dev/null)
    SUB=$(systemctl show "$SERVICE" -p SubState --value 2>/dev/null)
    ENTERED=$(systemctl show "$SERVICE" -p ActiveEnterTimestamp --value 2>/dev/null)
    echo "$SERVICE|${{ACTIVE:-unknown}}|${{SUB:-unknown}}|${{ENTERED:-}}"
  fi
done
"""
        try:
            output = self.ssh_service.run_remote_command(server.host, server.ssh_port, command, username=username)
        except SSHExecutionError:
            return []

        snapshots = []
        for line in output.splitlines():
            parts = line.split("|", 3)
            if len(parts) != 4:
                continue
            name, active_state, sub_state, entered_at = parts
            snapshots.append(
                ServiceUptimeSnapshot(
                    name=name,
                    active_state=active_state,
                    sub_state=sub_state,
                    entered_at=entered_at or None,
                    uptime_hint="Activo" if active_state == "active" else "No activo",
                )
            )
        return snapshots

    def collect_docker_containers(self, server: Server, username: str | None = None) -> list[DockerContainerSnapshot]:
        command = "docker ps --format '{{.Names}}|{{.Image}}|{{.Status}}|{{.RunningFor}}' 2>/dev/null | head -n 30"
        try:
            output = self.ssh_service.run_remote_command(server.host, server.ssh_port, command, username=username)
        except SSHExecutionError:
            return []

        containers = []
        for line in output.splitlines():
            parts = line.split("|", 3)
            if len(parts) != 4:
                continue
            name, image, status, running_for = parts
            containers.append(
                DockerContainerSnapshot(
                    name=name,
                    image=image,
                    status=status,
                    running_for=running_for,
                )
            )
        return containers

    def collect_database_health(self, server: Server, username: str | None = None) -> list[DatabaseHealthSnapshot]:
        command = """
if command -v pg_isready >/dev/null 2>&1; then
  if pg_isready -q 2>/dev/null; then
    VER=$(psql -Atqc "show server_version" postgres 2>/dev/null | head -n 1)
    CONN=$(psql -Atqc "select count(*) from pg_stat_activity" postgres 2>/dev/null | head -n 1)
    echo "postgres|online|${VER:-}|connections|${CONN:-ready}|OK"
  else
    echo "postgres|warning||availability|not-ready|pg_isready reporta no listo"
  fi
else
  echo "postgres|unavailable|||availability|n/a|Cliente no instalado"
fi

if command -v mongosh >/dev/null 2>&1; then
  OUT=$(mongosh --quiet --eval 'const s=db.serverStatus(); print((s.version||"")+"|"+String((s.connections&&s.connections.current)||0))' 2>/dev/null | head -n 1)
  if [ -n "$OUT" ]; then
    VER=${OUT%%|*}
    CONN=${OUT#*|}
    echo "mongo|online|${VER:-}|connections|${CONN:-0}|OK"
  else
    echo "mongo|warning||availability|query-failed|mongosh sin respuesta"
  fi
else
  echo "mongo|unavailable|||availability|n/a|Cliente no instalado"
fi
"""
        try:
            output = self.ssh_service.run_remote_command(server.host, server.ssh_port, command, username=username)
        except SSHExecutionError:
            return []

        results = []
        for line in output.splitlines():
            parts = line.split("|", 5)
            if len(parts) != 6:
                continue
            engine, status, version, metric_label, metric_value, message = parts
            results.append(
                DatabaseHealthSnapshot(
                    engine=engine,
                    status=status,
                    version=version or None,
                    metric_label=metric_label or None,
                    metric_value=metric_value or None,
                    message=message or None,
                )
            )
        return results

    @staticmethod
    def extract_port(value: str) -> int | None:
        candidate = value.rsplit(":", 1)[-1].strip()
        return int(candidate) if candidate.isdigit() else None

    @staticmethod
    def snapshot_to_schema(snapshot: ObservabilitySnapshot) -> SnapshotRecord:
        try:
            payload = json.loads(snapshot.payload_json)
        except json.JSONDecodeError:
            payload = {}
        return SnapshotRecord(
            id=snapshot.id,
            server_code=snapshot.server_code,
            snapshot_type=snapshot.snapshot_type,
            status=snapshot.status,
            cpu_usage=snapshot.cpu_usage,
            memory_usage=snapshot.memory_usage,
            disk_usage=snapshot.disk_usage,
            latency_ms=snapshot.latency_ms,
            payload=payload,
            created_at=snapshot.created_at,
        )

    @staticmethod
    def _restore_dashboard_entry(snapshot: SnapshotRecord | None) -> DashboardResponse | None:
        if snapshot is None:
            return None
        payload = snapshot.payload
        if not isinstance(payload, dict):
            return None
        try:
            return DashboardResponse(**payload)
        except Exception:
            return None

    @staticmethod
    def list_snapshot_models(db: Session, server_code: str, limit: int) -> list[ObservabilitySnapshot]:
        return (
            db.query(ObservabilitySnapshot)
            .filter(ObservabilitySnapshot.server_code == server_code)
            .order_by(ObservabilitySnapshot.created_at.desc())
            .limit(limit)
            .all()
        )
