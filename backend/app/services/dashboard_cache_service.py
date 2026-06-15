from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import monotonic

from app.config import get_settings
from app.database import SessionLocal
from app.models.server import Server
from app.schemas.server import DashboardResponse
from app.services.monitor_service import MonitorService
from app.services.observability_service import ObservabilityService


logger = logging.getLogger(__name__)


class DashboardCacheService:
    OFFLINE_GRACE_REFRESHES = 2

    def __init__(self) -> None:
        self.settings = get_settings()
        self.monitor_service = MonitorService()
        self.observability_service = ObservabilityService()
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._refreshing = False
        self._entries: dict[str, DashboardResponse] = {}
        self._last_refresh_started_at = 0.0
        self._last_refresh_completed_at = 0.0

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, name="dashboard-cache-refresh", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2)

    def get_summary(self, servers: list[Server]) -> list[DashboardResponse]:
        server_codes = [server.code for server in servers]

        if self._has_missing_entries(server_codes):
            self.refresh_now(servers)
        elif self._is_stale():
            self.refresh_async()

        with self._lock:
            cached_entries = {code: self._entries.get(code) for code in server_codes}

        missing_servers = [server for server in servers if cached_entries.get(server.code) is None]
        if missing_servers:
            self.refresh_now(missing_servers)
            with self._lock:
                cached_entries = {code: self._entries.get(code) for code in server_codes}

        return [cached_entries[code] for code in server_codes if cached_entries.get(code) is not None]

    def invalidate(self, code: str) -> None:
        """Descarta la entrada cacheada de un nodo para forzar reconexion al endpoint nuevo."""
        with self._lock:
            self._entries.pop(code, None)

    def refresh_async(self) -> None:
        with self._lock:
            if self._refreshing:
                return
            self._refreshing = True
        threading.Thread(target=self._refresh_worker, name="dashboard-cache-refresh-now", daemon=True).start()

    def refresh_now(self, servers: list[Server] | None = None) -> None:
        self._refresh_worker(servers=servers)

    def _run(self) -> None:
        self.refresh_async()
        while not self._stop_event.wait(self.settings.dashboard_refresh_interval_seconds):
            self.refresh_async()

    def _refresh_worker(self, servers: list[Server] | None = None) -> None:
        try:
            if servers is None:
                servers = self._load_active_servers()
            if not servers:
                return

            started_at = monotonic()
            entries = self._build_entries(servers)
            self._store_snapshots(entries)
            with self._lock:
                for entry in entries:
                    self._entries[entry.server.code] = self._merge_entry(entry)
                self._last_refresh_started_at = started_at
                self._last_refresh_completed_at = monotonic()
            logger.info("Dashboard cache refreshed servers=%s duration_ms=%s", len(entries), int((monotonic() - started_at) * 1000))
        except Exception:
            logger.exception("Dashboard cache refresh failed")
        finally:
            with self._lock:
                self._refreshing = False

    def _build_entries(self, servers: list[Server]) -> list[DashboardResponse]:
        max_workers = max(1, min(self.settings.dashboard_refresh_max_workers, len(servers)))
        entries_by_code: dict[str, DashboardResponse] = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(self.monitor_service.compute_dashboard_entry, server): server
                for server in servers
            }
            for future in as_completed(future_map):
                server = future_map[future]
                try:
                    entries_by_code[server.code] = future.result()
                except Exception as exc:
                    logger.exception("Dashboard entry refresh failed server=%s", server.code)
                    entries_by_code[server.code] = self.monitor_service.build_error_dashboard_entry(server, str(exc))

        return [entries_by_code[server.code] for server in servers if server.code in entries_by_code]

    def _load_active_servers(self) -> list[Server]:
        db = SessionLocal()
        try:
            return db.query(Server).filter(Server.is_active.is_(True)).order_by(Server.code.asc()).all()
        finally:
            db.close()

    def _has_missing_entries(self, server_codes: list[str]) -> bool:
        with self._lock:
            return any(code not in self._entries for code in server_codes)

    def _is_stale(self) -> bool:
        with self._lock:
            if self._last_refresh_completed_at == 0:
                return True
            age_seconds = monotonic() - self._last_refresh_completed_at
            return age_seconds >= self.settings.dashboard_refresh_interval_seconds

    def _store_snapshots(self, entries: list[DashboardResponse]) -> None:
        if not entries:
            return

        db = SessionLocal()
        try:
            for entry in entries:
                self.observability_service.record_dashboard_entry_snapshot(db, entry, snapshot_type="auto")
        except Exception:
            db.rollback()
            logger.exception("Failed to persist observability snapshots")
        finally:
            db.close()

    def _merge_entry(self, new_entry: DashboardResponse) -> DashboardResponse:
        existing_entry = self._entries.get(new_entry.server.code)
        if existing_entry is None:
            return new_entry

        if self._should_keep_existing_online(existing_entry, new_entry):
            logger.warning(
                "Keeping previous online dashboard entry server=%s after transient offline refresh",
                new_entry.server.code,
            )
            return existing_entry

        return new_entry

    def _should_keep_existing_online(self, existing_entry: DashboardResponse, new_entry: DashboardResponse) -> bool:
        if existing_entry.health.connection_status != "online":
            return False
        if new_entry.health.connection_status != "offline":
            return False
        if self._last_refresh_completed_at == 0:
            return False

        grace_window_seconds = self.settings.dashboard_refresh_interval_seconds * self.OFFLINE_GRACE_REFRESHES
        age_seconds = monotonic() - self._last_refresh_completed_at
        return age_seconds <= grace_window_seconds


dashboard_cache_service = DashboardCacheService()
