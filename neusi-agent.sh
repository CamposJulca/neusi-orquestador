#!/usr/bin/env bash
#
# neusi-agent.sh — corre EN CADA NODO (100..105).
#
# Lee el endpoint TCP actual de ngrok desde su API local (127.0.0.1:4040) y lo
# publica al monitor via POST /api/servers/register. Asi el backend siempre sabe
# en que host:puerto esta el nodo, aunque ngrok rote el puerto al reiniciar.
#
# Configuracion (por variables de entorno o editando los defaults de abajo):
#   NEUSI_CODE       codigo del nodo en el monitor (p.ej. 104)
#   MONITOR_URL      URL base del monitor          (p.ej. https://monitor.tudominio.ngrok.app)
#   REGISTER_TOKEN   token compartido (igual al de backend/.env)
#   NGROK_API        API local de ngrok            (default http://127.0.0.1:4040/api/tunnels)
#   INTERVAL         segundos entre publicaciones  (default 60; usa --once para 1 sola vez)
#
# Uso:
#   NEUSI_CODE=104 MONITOR_URL=https://... REGISTER_TOKEN=... ./neusi-agent.sh
#   ./neusi-agent.sh --once

set -uo pipefail

NEUSI_CODE="${NEUSI_CODE:-}"
MONITOR_URL="${MONITOR_URL:-}"
REGISTER_TOKEN="${REGISTER_TOKEN:-}"
NGROK_API="${NGROK_API:-http://127.0.0.1:4040/api/tunnels}"
INTERVAL="${INTERVAL:-60}"

ONCE=0
[ "${1:-}" = "--once" ] && ONCE=1

log() { echo "[$(date '+%F %T')] $*"; }

if [ -z "$NEUSI_CODE" ] || [ -z "$MONITOR_URL" ] || [ -z "$REGISTER_TOKEN" ]; then
  echo "ERROR: define NEUSI_CODE, MONITOR_URL y REGISTER_TOKEN." >&2
  exit 1
fi

# Extrae host y puerto del tunel TCP de ngrok -> imprime "host puerto"
read_ngrok_endpoint() {
  local json
  json=$(curl -fsS --max-time 5 "$NGROK_API" 2>/dev/null) || return 1

  if command -v python3 >/dev/null 2>&1; then
    python3 - "$json" <<'PY'
import json, sys, re
try:
    data = json.loads(sys.argv[1])
except Exception:
    sys.exit(1)
for t in data.get("tunnels", []):
    url = t.get("public_url", "")
    m = re.match(r"tcp://([^:]+):(\d+)", url)
    if m:
        print(m.group(1), m.group(2))
        sys.exit(0)
sys.exit(1)
PY
  else
    # Fallback sin python: parseo con grep/sed
    echo "$json" | grep -oE 'tcp://[^"]+' | head -1 | sed -E 's#tcp://([^:]+):([0-9]+)#\1 \2#'
  fi
}

publish() {
  local host port resp code
  if ! read -r host port < <(read_ngrok_endpoint); then
    log "no pude leer el endpoint de ngrok ($NGROK_API). Esta ngrok corriendo?"
    return 1
  fi
  [ -z "${host:-}" ] || [ -z "${port:-}" ] && { log "endpoint ngrok vacio"; return 1; }

  resp=$(curl -fsS --max-time 8 -X POST "$MONITOR_URL/api/servers/register" \
    -H "Content-Type: application/json" \
    -H "X-Register-Token: $REGISTER_TOKEN" \
    -d "{\"code\":\"$NEUSI_CODE\",\"host\":\"$host\",\"ssh_port\":$port}" \
    -w $'\n%{http_code}' 2>/dev/null)
  code="${resp##*$'\n'}"

  if [ "$code" = "200" ]; then
    log "registrado OK  code=$NEUSI_CODE -> $host:$port"
  else
    log "fallo al registrar (HTTP ${code:-?}) host=$host port=$port"
    return 1
  fi
}

log "neusi-agent iniciado  code=$NEUSI_CODE monitor=$MONITOR_URL once=$ONCE"
if [ "$ONCE" -eq 1 ]; then
  publish
  exit $?
fi

while true; do
  publish || true
  sleep "$INTERVAL"
done
