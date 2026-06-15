from sqlalchemy.orm import Session

from app.models.server import Server
from app.config.servers import SERVERS


DEFAULT_SERVERS = [
    {
        "code": server.id,
        "name": server.name,
        "host": server.host,
        "ssh_port": server.port,
        "environment": server.role,
    }
    for server in SERVERS
]


def seed_servers(db: Session) -> None:
    existing = {server.code: server for server in db.query(Server).all()}
    for payload in DEFAULT_SERVERS:
        server = existing.get(payload["code"])
        if server:
            # Solo metadatos estaticos. host/ssh_port son propiedad del auto-registro
            # (POST /api/servers/register) y NO se pisan en cada arranque, para no
            # revertir un endpoint ngrok ya actualizado por el nodo.
            server.name = payload["name"]
            server.environment = payload["environment"]
            server.is_active = True
            continue
        db.add(Server(**payload))
    db.commit()
