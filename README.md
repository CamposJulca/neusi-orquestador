# Neusi Infra Monitor

Aplicativo web local para visualizar el estado operativo de las maquinas 100 a 105 en una sola pantalla.

## CLI de operaciones (`neusi`)

El proyecto incluye un CLI de terminal (`cli/neusi`) **unificado con el monitor**: usa el
MISMO backend que el dashboard web como fuente de verdad de `host:puerto` de cada nodo.

```bash
neusi                       # menu interactivo (conectar por SSH, ver estado, refrescar, abrir dashboard)
neusi-refresh               # AUTO: lee el ngrok de produccion y actualiza .10/.11/.12 en el backend
neusi-refresh 104 4.tcp.ngrok.io 29531   # MANUAL: refresca un nodo auxiliar (103/104/105)
```

- Los comandos viven en `cli/` y se exponen como symlinks en `~/.local/bin/`.
- El menu lee los endpoints de `GET /api/servers`; si el backend no responde, usa un fallback local.
- Como los puertos ngrok son efimeros, cuando roten:
  - `.10/.11/.12` (los expone el ngrok de produccion) -> `neusi-refresh` los actualiza solos.
  - `.13/.14/.105` (auxiliares, su tunel no sale de produccion) -> refresco manual con `neusi-refresh <code> <host> <port>`.

Instalar / reinstalar los symlinks:

```bash
ln -sf "$PWD/cli/neusi"         ~/.local/bin/neusi
ln -sf "$PWD/cli/neusi-refresh" ~/.local/bin/neusi-refresh
```

## Levantar todo

```bash
docker compose up -d --build
```

O con el script de arranque:

```bash
./monitor.sh
```

Acceso local:

- Frontend: `http://localhost:8080`
- Backend: `http://localhost:8070`

## Script de monitoreo

```bash
chmod +x monitor.sh
./monitor.sh up
./monitor.sh status
./monitor.sh logs
./monitor.sh down
./monitor.sh rebuild
```

## Ver logs

```bash
docker compose logs -f
```

## Detener

```bash
docker compose down
```

## Rebuild

```bash
docker compose up -d --build
```

## Autenticacion SSH (por LLAVE)

El monitor se conecta a los nodos usando **autenticacion por llave** (`~/.ssh/id_ed25519`),
no por password. La llave se monta dentro del contenedor (`docker-compose.yml`) y la config
vive en `backend/.env` (`SSH_PRIVATE_KEY_PATH`, sin `SSH_PASSWORD`).

Aprovisionar / verificar la llave en los nodos:

```bash
./provision_key.sh --check                 # ver que nodos tienen la llave
./provision_key.sh                          # instalar la llave en todos
./provision_key.sh camposjulca 8.tcp.ngrok.io <PUERTO>   # un nodo (p.ej. 104 con su puerto nuevo)
docker compose up -d --force-recreate backend            # recargar tras aprovisionar
```

> Los puertos ngrok son efimeros: cuando un nodo reinicie su tunel, actualiza el puerto en
> `backend/app/config/servers.py` y en la tabla de `provision_key.sh`.

## Auto-registro de endpoints ngrok

Los puertos ngrok son **efimeros**: cambian cada vez que el nodo reinicia su tunel.
Para que el monitor no quede con puertos obsoletos, cada nodo **publica su endpoint
actual** al backend y la base de datos pasa a ser la **fuente de verdad** de host/puerto.

Flujo:

1. En cada nodo corre `neusi-agent.sh`, que lee el endpoint TCP de ngrok desde su API
   local (`http://127.0.0.1:4040/api/tunnels`) y hace `POST /api/servers/register`.
2. El backend actualiza `host`/`ssh_port` de ese nodo en la DB e invalida la cache,
   reconectando al endpoint nuevo en el siguiente ciclo.
3. El `seed_servers` de arranque ya **no** pisa host/puerto: solo siembra nodos nuevos
   y refresca metadatos estaticos. Un reinicio del backend no revierte lo registrado.

### Backend

`backend/.env` define el token compartido:

```env
REGISTER_TOKEN=<token-secreto>
```

Endpoint (requiere cabecera `X-Register-Token`):

```bash
curl -X POST http://MONITOR/api/servers/register \
  -H "Content-Type: application/json" \
  -H "X-Register-Token: $REGISTER_TOKEN" \
  -d '{"code":"104","host":"8.tcp.ngrok.io","ssh_port":27504}'
```

### Agente en cada nodo

```bash
# En el nodo (p.ej. el 104):
NEUSI_CODE=104 \
MONITOR_URL=https://tu-monitor.ngrok.app \
REGISTER_TOKEN=<token-secreto> \
./neusi-agent.sh            # bucle cada 60s (o --once para una sola publicacion)
```

Como servicio permanente con systemd (recomendado), crea
`/etc/systemd/system/neusi-agent.service`:

```ini
[Unit]
Description=Neusi node agent (publica endpoint ngrok al monitor)
After=network-online.target

[Service]
Environment=NEUSI_CODE=104
Environment=MONITOR_URL=https://tu-monitor.ngrok.app
Environment=REGISTER_TOKEN=<token-secreto>
ExecStart=/ruta/a/neusi-agent.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now neusi-agent
```

> **Importante (rendezvous):** los nodos deben poder *alcanzar* el backend. Como el
> monitor corre en una maquina sin IP publica fija, lo mas robusto es exponer el backend
> con un **dominio reservado de ngrok** (URL estable) y usar esa URL como `MONITOR_URL`.
> Si los nodos y el monitor estan en la misma red, basta `http://<ip-del-monitor>:8070`.

## App movil (PWA)

El dashboard es una **PWA instalable** en el celular (Android/iOS) — se agrega a la
pantalla de inicio y corre a pantalla completa, reusando el mismo frontend.

Artefactos (en `frontend/public/`): `manifest.webmanifest`, `sw.js` (service worker)
e iconos. El service worker cachea el app shell y guarda la ultima respuesta de la API
(network-first), asi el movil muestra el ultimo estado conocido aun sin conexion.

Instalar en el celular:

1. Servir el frontend por **HTTPS** (requisito para instalar PWA y registrar el SW).
   En LAN por `http://` NO funciona la instalacion; la via mas simple es exponer el
   puerto 8080 con un tunel HTTPS:

   ```bash
   ngrok http 8080            # entrega una URL https://... estable si usas dominio reservado
   ```

2. Abrir esa URL `https://...` en Chrome/Safari del celular.
3. **Android (Chrome):** menu -> "Instalar app" / "Agregar a pantalla de inicio".
   **iOS (Safari):** Compartir -> "Agregar a inicio".

> Nota: el celular debe poder alcanzar el backend (mismo "rendezvous" del monitor).
> Al exponerlo a internet, conviene endurecer la seguridad (auth en la API, HTTPS).

## Stack

- Backend: FastAPI
- Frontend: React + Vite (PWA instalable)
- Base de datos inicial: SQLite
- Lenguaje principal: Python
- Arquitectura: modular por routers, servicios, modelos y schemas

## Funcionalidad actual

- Dashboard unico con las maquinas 100, 101, 102, 103, 104 y 105
- Estado de salud por servidor: CPU, memoria, disco, latencia y uptime
- Resumen de archivos indexados por maquina
- Resumen de proyectos detectados y stacks asociados
- Integracion SSH real para Linux con fallback a mock por servicio cuando falle la conexion

## Estructura

```bash
neusi-infra-monitor/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── routers/
│   │   └── database.py
│   ├── requirements.txt
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── App.jsx
│   └── package.json
└── docker-compose.yml
```

## Ejecutar local sin Docker

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Variables para Fase 2

Crear `backend/.env` con una base como esta:

```env
USE_MOCK_DATA=false
SSH_ENABLED=true
SSH_USERNAME=monitor
SSH_PRIVATE_KEY_PATH=/ruta/a/tu/llave_privada
SSH_TIMEOUT_SECONDS=5
SSH_FALLBACK_TO_MOCK=true
MONITORED_FILE_PATHS=["/srv","/opt","/var/log"]
MONITORED_PROJECT_PATHS=["/srv","/opt","/home"]
FILE_SCAN_MAX_DEPTH=2
PROJECT_SCAN_MAX_DEPTH=3
```

Si prefieres autenticacion por password:

```env
SSH_PASSWORD=tu_password
```

## Ejecutar con Docker Compose

```bash
docker compose up -d --build
```

## Endpoints principales

- `GET /health`
- `GET /api/servers`
- `GET /api/servers/dashboard/summary`
- `GET /api/metrics/{server_code}`
- `GET /api/files/{server_code}`
- `GET /api/projects/{server_code}`

## Siguiente fase recomendada

1. Incorporar credenciales por servidor en lugar de una sola credencial global.
2. Guardar historicos de metricas en PostgreSQL.
3. Agregar chequeos de servicios Linux concretos con `systemctl`.
4. Incorporar alertas visuales, filtros por entorno y polling configurable.
