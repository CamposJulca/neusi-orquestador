# Backend

## Ejecutar local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Variables iniciales

- `DATABASE_URL`: por defecto `sqlite:///./neusi_infra_monitor.db`
- `USE_MOCK_DATA`: por defecto `true`
- `SSH_ENABLED`: activa conexion real por SSH cuando `USE_MOCK_DATA=false`
- `SSH_USERNAME`: usuario Linux usado para conectarse
- `SSH_PRIVATE_KEY_PATH` o `SSH_PASSWORD`: credencial de acceso
- `SSH_FALLBACK_TO_MOCK`: si falla SSH, mantiene el dashboard operativo con datos mock
- `MONITORED_FILE_PATHS` y `MONITORED_PROJECT_PATHS`: listas JSON con rutas remotas a escanear

## Endpoints principales

- `GET /health`
- `GET /api/servers`
- `GET /api/servers/dashboard/summary`
- `GET /api/metrics/{server_code}`
- `GET /api/files/{server_code}`
- `GET /api/projects/{server_code}`
