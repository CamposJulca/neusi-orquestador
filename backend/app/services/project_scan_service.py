from datetime import datetime, timezone

from app.schemas.server import ProjectSummary
from app.services.ssh_service import SSHExecutionError, SSHService


MOCK_PROJECTS = {
    "100": (["finanzapp-neusi", "infra-batch"], ["Django", "Celery", "PostgreSQL"]),
    "101": (["api-clientes", "api-reportes"], ["FastAPI", "Redis"]),
    "102": (["warehouse-sync", "analytics-core"], ["Python", "dbt", "PostgreSQL"]),
    "103": (["portal-operaciones"], ["React", "Nginx"]),
    "104": (["motor-ia", "vector-indexer"], ["Python", "Docker", "Qdrant"]),
    "105": (["etl-documental", "ocr-pipeline"], ["Airflow", "Python", "MinIO"]),
}


class ProjectScanService:
    STACK_MARKERS = {
        "package.json": "Node.js",
        "pyproject.toml": "Python",
        "requirements.txt": "Python",
        ".git": "Git",
        "Dockerfile": "Docker",
        "docker-compose.yml": "Docker Compose",
    }

    def __init__(self) -> None:
        self.ssh_service = SSHService()

    def get_summary(self, server_code: str, host: str, port: int) -> ProjectSummary:
        source = "mock"
        try:
            payload = self.ssh_service.collect_project_summary(host, port)
            projects, stacks = self._build_project_summary(payload["project_markers"])
            source = "ssh"
        except SSHExecutionError:
            if self.ssh_service.is_enabled() and not self.ssh_service.settings.ssh_fallback_to_mock:
                raise
            projects, stacks = MOCK_PROJECTS[server_code]
            if self.ssh_service.is_enabled():
                source = "mock-fallback"

        return ProjectSummary(
            server_code=server_code,
            projects=projects,
            detected_stacks=stacks,
            last_scan=datetime.now(timezone.utc),
            source=source,
        )

    def _build_project_summary(self, markers: list[str]) -> tuple[list[str], list[str]]:
        project_names: list[str] = []
        detected_stacks: list[str] = []
        seen_projects: set[str] = set()
        seen_stacks: set[str] = set()

        for marker_line in markers:
            if "|" not in marker_line:
                continue
            directory, marker = marker_line.split("|", 1)
            project_name = directory.rstrip("/").split("/")[-1] or directory
            if project_name not in seen_projects:
                seen_projects.add(project_name)
                project_names.append(project_name)
            stack_name = self.STACK_MARKERS.get(marker)
            if stack_name and stack_name not in seen_stacks:
                seen_stacks.add(stack_name)
                detected_stacks.append(stack_name)

        return project_names[:12], detected_stacks[:12]
