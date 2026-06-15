from datetime import datetime, timezone

from app.schemas.server import HealthSnapshot
from app.services.ssh_service import SSHExecutionError, SSHService


MOCK_HEALTH = {
    "100": {"status": "healthy", "cpu": 34.5, "memory": 61.2, "disk": 70.8, "uptime": "12d 04h", "latency": 18},
    "101": {"status": "healthy", "cpu": 48.1, "memory": 55.9, "disk": 68.3, "uptime": "8d 21h", "latency": 24},
    "102": {"status": "warning", "cpu": 72.0, "memory": 81.4, "disk": 77.0, "uptime": "19d 13h", "latency": 39},
    "103": {"status": "healthy", "cpu": 29.3, "memory": 49.8, "disk": 52.4, "uptime": "4d 08h", "latency": 15},
    "104": {"status": "critical", "cpu": 91.6, "memory": 88.2, "disk": 94.1, "uptime": "31d 02h", "latency": 65},
    "105": {"status": "healthy", "cpu": 37.4, "memory": 58.6, "disk": 63.7, "uptime": "6d 17h", "latency": 21},
}


class HealthService:
    def __init__(self) -> None:
        self.ssh_service = SSHService()

    def get_health(self, server_code: str, host: str, port: int) -> HealthSnapshot:
        now = datetime.now(timezone.utc)
        source = "mock"
        try:
            raw_payload = self.ssh_service.collect_health(host, port)
            cpu_usage = float(str(raw_payload["cpu"]))
            memory_usage = float(str(raw_payload["memory"]))
            disk_usage = float(str(raw_payload["disk"]))
            payload = {
                "status": self.classify_status(cpu_usage, memory_usage, disk_usage),
                "cpu": cpu_usage,
                "memory": memory_usage,
                "disk": disk_usage,
                "uptime": self.format_uptime(int(str(raw_payload["uptime_seconds"]))),
                "latency": int(raw_payload["latency"]),
            }
            source = "ssh"
        except SSHExecutionError:
            if self.ssh_service.is_enabled() and not self.ssh_service.settings.ssh_fallback_to_mock:
                raise
            payload = MOCK_HEALTH[server_code]
            if self.ssh_service.is_enabled():
                source = "mock-fallback"

        return HealthSnapshot(
            server_code=server_code,
            status=payload["status"],
            cpu_usage=payload["cpu"],
            memory_usage=payload["memory"],
            disk_usage=payload["disk"],
            uptime=payload["uptime"],
            latency_ms=payload["latency"],
            checked_at=now,
            source=source,
        )

    @staticmethod
    def classify_status(cpu_usage: float, memory_usage: float, disk_usage: float) -> str:
        if max(cpu_usage, memory_usage, disk_usage) >= 90:
            return "critical"
        if max(cpu_usage, memory_usage, disk_usage) >= 75:
            return "warning"
        return "healthy"

    @staticmethod
    def format_uptime(uptime_seconds: int) -> str:
        days, remainder = divmod(uptime_seconds, 86400)
        hours, _ = divmod(remainder, 3600)
        return f"{days}d {hours:02}h"
