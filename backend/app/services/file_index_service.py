from datetime import datetime, timezone

from app.schemas.server import FileSummary
from app.services.ssh_service import SSHExecutionError, SSHService


MOCK_FILE_INDEX = {
    "100": (["/srv/apps", "/var/log", "/data/backups"], 18324),
    "101": (["/srv/api", "/etc/nginx", "/var/log"], 14782),
    "102": (["/opt/services", "/var/lib/postgresql", "/tmp"], 22109),
    "103": (["/srv/front", "/var/log", "/home/deploy"], 13240),
    "104": (["/data/ml", "/var/log", "/mnt/archive"], 40983),
    "105": (["/srv/etl", "/var/log", "/data/raw"], 25441),
}


class FileIndexService:
    def __init__(self) -> None:
        self.ssh_service = SSHService()

    def get_summary(self, server_code: str, host: str, port: int) -> FileSummary:
        source = "mock"
        try:
            payload = self.ssh_service.collect_file_summary(host, port)
            indexed_paths = [path for path in str(payload.get("indexed_paths", "")).split("|") if path]
            total_files = int(str(payload.get("total_files", "0")))
            source = "ssh"
        except SSHExecutionError:
            if self.ssh_service.is_enabled() and not self.ssh_service.settings.ssh_fallback_to_mock:
                raise
            indexed_paths, total_files = MOCK_FILE_INDEX[server_code]
            if self.ssh_service.is_enabled():
                source = "mock-fallback"

        return FileSummary(
            server_code=server_code,
            indexed_paths=indexed_paths,
            total_files=total_files,
            last_scan=datetime.now(timezone.utc),
            source=source,
        )
