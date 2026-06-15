from __future__ import annotations

from dataclasses import dataclass

from app.config.servers import SERVERS as CONFIG_SERVERS


@dataclass(frozen=True)
class ServerRegistryEntry:
    code: str
    name: str
    host: str
    port: int
    username: str
    real_ip: str
    role: str


SERVERS = [
    ServerRegistryEntry(
        code=server.id,
        name=server.name,
        host=server.host,
        port=server.port,
        username=server.user,
        real_ip=server.real_ip,
        role=server.role,
    )
    for server in CONFIG_SERVERS
]

SERVER_MAP = {server.code: server for server in SERVERS}


def get_server_registry_entry(server_code: str) -> ServerRegistryEntry | None:
    return SERVER_MAP.get(server_code)
