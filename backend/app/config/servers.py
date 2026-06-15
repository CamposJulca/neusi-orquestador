from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServerConfig:
    id: str
    name: str
    role: str
    user: str
    host: str
    port: int
    real_ip: str


SERVERS = [
    ServerConfig(
        id="100",
        name="Maquina 10",
        role="Produccion",
        user="produccion",
        host="4.tcp.ngrok.io",
        port=12385,
        real_ip="192.168.0.100",
    ),
    ServerConfig(
        id="101",
        name="Maquina 11",
        role="Desarrollo",
        user="desarrollo",
        host="8.tcp.ngrok.io",
        port=21457,
        real_ip="192.168.0.101",
    ),
    ServerConfig(
        id="102",
        name="Maquina 12",
        role="Testing",
        user="pruebas",
        host="8.tcp.ngrok.io",
        port=17803,
        real_ip="192.168.0.102",
    ),
    ServerConfig(
        id="103",
        name="Maquina 13",
        role="Simulador",
        user="simulador1",
        host="8.tcp.ngrok.io",
        port=10849,
        real_ip="192.168.0.103",
    ),
    ServerConfig(
        id="104",
        name="Maquina 14",
        role="Storage Node",
        user="camposjulca",
        host="8.tcp.ngrok.io",
        port=27504,
        real_ip="192.168.0.104",
    ),
    ServerConfig(
        id="105",
        name="Maquina 15",
        role="Nodo Auxiliar",
        user="cristhiamdaniel",
        host="8.tcp.ngrok.io",
        port=11636,
        real_ip="192.168.0.105",
    ),
]
