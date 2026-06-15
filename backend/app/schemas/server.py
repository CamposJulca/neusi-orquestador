from datetime import datetime

from pydantic import BaseModel, Field


class ServerBase(BaseModel):
    code: str
    name: str
    host: str
    ssh_port: int
    environment: str
    is_active: bool
    real_ip: str | None = None
    ssh_username: str | None = None
    role: str | None = None


class ServerResponse(ServerBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ServerRegisterRequest(BaseModel):
    code: str
    host: str
    ssh_port: int = Field(ge=1, le=65535)
    name: str | None = None
    environment: str | None = None


class StorageSnapshot(BaseModel):
    server_code: str
    mount_path: str
    mounted: bool
    filesystem: str | None = None
    total: str | None = None
    used: str | None = None
    free: str | None = None
    usage_percent: float | None = None
    usage_label: str = "No conectado"
    checked_at: datetime
    source: str
    message: str | None = None


class DiskSnapshot(BaseModel):
    mount: str
    filesystem: str
    size: str
    used: str
    available: str
    usage_percent: float


class StatusReason(BaseModel):
    level: str
    metric: str
    target: str
    value: float
    threshold: float
    message: str


class HealthSnapshot(BaseModel):
    server_code: str
    status: str
    status_reasons: list[StatusReason] = Field(default_factory=list)
    cpu_usage: float | None
    memory_usage: float | None
    disk_usage: float | None
    disks: list[DiskSnapshot] = Field(default_factory=list)
    temperature_c: float | None = None
    temperature_label: str = "No disponible"
    uptime: str
    latency_ms: int | None
    latency_label: str
    connection_status: str
    connection_message: str
    ssh_status: str
    last_error: str | None = None
    docker_containers: list[str] = Field(default_factory=list)
    docker_count: int = 0
    running_services: list[str] = Field(default_factory=list)
    services_count: int = 0
    open_ports: list[str] = Field(default_factory=list)
    ports_count: int = 0
    storage: StorageSnapshot | None = None
    checked_at: datetime
    source: str


class FileSummary(BaseModel):
    server_code: str
    indexed_paths: list[str]
    total_files: int
    last_scan: datetime
    source: str


class FileTreeItem(BaseModel):
    name: str
    path: str
    type: str
    size: str | None
    modified_at: str | None
    children: list["FileTreeItem"] = Field(default_factory=list)


class FileTreeResponse(BaseModel):
    server_id: str
    path: str
    connected: bool
    items: list[FileTreeItem]
    message: str | None = None
    checked_at: datetime


class FilePreviewResponse(BaseModel):
    server_id: str
    path: str
    connected: bool
    name: str
    type: str
    mime_type: str
    size: str | None
    modified_at: str | None
    preview_kind: str
    text_content: str | None = None
    message: str | None = None
    checked_at: datetime


class DriveTreeItem(BaseModel):
    id: str
    name: str
    path: str | None = None
    type: str
    size: str | None = None
    modified_at: str | None = None
    description: str | None = None
    scope: str
    server_id: str | None = None
    server_name: str | None = None
    expandable: bool = False
    children_loaded: bool = False
    children: list["DriveTreeItem"] = Field(default_factory=list)


class DriveTreeResponse(BaseModel):
    scope: str
    server_id: str | None = None
    path: str | None = None
    connected: bool
    items: list[DriveTreeItem]
    message: str | None = None
    checked_at: datetime


class ProjectSummary(BaseModel):
    server_code: str
    projects: list[str]
    detected_stacks: list[str]
    last_scan: datetime
    source: str


class MetricPoint(BaseModel):
    recorded_at: datetime
    cpu_usage: float | None = None
    memory_usage: float | None = None
    disk_usage: float | None = None
    latency_ms: int | None = None
    status: str


class SnapshotRecord(BaseModel):
    id: int
    server_code: str
    snapshot_type: str
    status: str
    cpu_usage: float | None = None
    memory_usage: float | None = None
    disk_usage: float | None = None
    latency_ms: int | None = None
    payload: dict
    created_at: datetime


class HistoricalSeriesResponse(BaseModel):
    server_code: str
    points: list[MetricPoint]
    latest_snapshot: SnapshotRecord | None = None


class HttpHealthcheckResult(BaseModel):
    name: str
    url: str
    status: str
    status_code: int | None = None
    response_time_ms: int | None = None
    message: str | None = None


class ServiceUptimeSnapshot(BaseModel):
    name: str
    active_state: str
    sub_state: str
    entered_at: str | None = None
    uptime_hint: str | None = None


class DockerContainerSnapshot(BaseModel):
    name: str
    image: str
    status: str
    running_for: str


class DatabaseHealthSnapshot(BaseModel):
    engine: str
    status: str
    version: str | None = None
    metric_label: str | None = None
    metric_value: str | None = None
    message: str | None = None


class FileSearchResult(BaseModel):
    path: str
    size: str | None = None
    modified_at: str | None = None


class DuplicateFileGroup(BaseModel):
    fingerprint: str
    size: str
    files: list[str]


class FileSearchResponse(BaseModel):
    server_code: str
    query: str
    base_path: str
    connected: bool
    results: list[FileSearchResult]
    checked_at: datetime
    message: str | None = None


class DuplicateFileResponse(BaseModel):
    server_code: str
    base_path: str
    connected: bool
    groups: list[DuplicateFileGroup]
    checked_at: datetime
    message: str | None = None


class ObservabilityOverviewResponse(BaseModel):
    server: ServerResponse
    health: HealthSnapshot
    http_checks: list[HttpHealthcheckResult]
    service_uptime: list[ServiceUptimeSnapshot]
    docker_containers: list[DockerContainerSnapshot]
    databases: list[DatabaseHealthSnapshot]
    latest_snapshot: SnapshotRecord | None = None


class DashboardResponse(BaseModel):
    server: ServerResponse
    health: HealthSnapshot
    files: FileSummary
    projects: ProjectSummary
