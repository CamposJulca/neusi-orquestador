from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_SSH_KEY_PATH = Path.home() / ".ssh" / "id_rsa"


class Settings(BaseSettings):
    app_name: str = "Neusi Infra Monitor API"
    api_prefix: str = "/api"
    database_url: str = "sqlite:///./neusi_infra_monitor.db"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]
    ssh_enabled: bool = True
    ssh_timeout_seconds: int = Field(
        default=8,
        validation_alias=AliasChoices("SSH_TIMEOUT_SECONDS", "SSH_TIMEOUT"),
    )
    ssh_username: str = "desarrollo"
    ssh_password: str | None = None
    ssh_private_key_path: str | None = Field(
        default=str(DEFAULT_SSH_KEY_PATH) if DEFAULT_SSH_KEY_PATH.exists() else None,
        validation_alias=AliasChoices("SSH_PRIVATE_KEY_PATH", "SSH_PRIVATE_KEY"),
    )
    ssh_look_for_keys: bool = True
    ssh_allow_agent: bool = True
    ssh_fallback_to_mock: bool = False
    register_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("REGISTER_TOKEN", "NEUSI_REGISTER_TOKEN"),
    )
    monitored_file_paths: list[str] = ["/srv", "/opt", "/var/log"]
    monitored_project_paths: list[str] = ["/srv", "/opt", "/home"]
    extra_allowed_file_paths: list[str] = ["/mnt"]
    shared_drive_name: str = "Compartido"
    shared_drive_path: str = "/srv/neusi-shared"
    backup_drive_name: str = "Backup 104"
    backup_server_id: str = "104"
    backup_drive_path: str = "/mnt/storage"
    storage_mount_path: str = "/mnt/storage"
    file_scan_max_depth: int = 2
    project_scan_max_depth: int = 3
    use_mock_data: bool = False
    dashboard_refresh_interval_seconds: int = 30
    dashboard_refresh_max_workers: int = 6

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
