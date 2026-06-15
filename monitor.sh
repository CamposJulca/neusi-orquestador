#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

FRONTEND_URL="http://localhost:8080"
BACKEND_URL="http://localhost:8070"

require_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "Error: Docker no esta instalado o no esta en el PATH."
    exit 1
  fi
}

print_urls() {
  echo
  echo "Frontend: $FRONTEND_URL"
  echo "Backend:  $BACKEND_URL"
}

up() {
  echo "Levantando Neusi Infra Monitor..."
  docker compose up -d --build
  print_urls
}

down() {
  echo "Deteniendo Neusi Infra Monitor..."
  docker compose down
}

logs() {
  docker compose logs -f
}

status() {
  docker compose ps
  print_urls
}

rebuild() {
  echo "Reconstruyendo y reiniciando Neusi Infra Monitor..."
  docker compose up -d --build --force-recreate
  print_urls
}

help() {
  cat <<'EOF'
Uso:
  ./monitor.sh up        Levanta backend y frontend
  ./monitor.sh down      Detiene los servicios
  ./monitor.sh logs      Muestra logs en vivo
  ./monitor.sh status    Muestra estado de contenedores
  ./monitor.sh rebuild   Reconstruye e inicia de nuevo
  ./monitor.sh help      Muestra esta ayuda

Si no indicas un comando, se usa: up
EOF
}

main() {
  require_docker

  local command="${1:-up}"
  case "$command" in
    up)
      up
      ;;
    down)
      down
      ;;
    logs)
      logs
      ;;
    status)
      status
      ;;
    rebuild)
      rebuild
      ;;
    help|-h|--help)
      help
      ;;
    *)
      echo "Comando no reconocido: $command"
      echo
      help
      exit 1
      ;;
  esac
}

main "$@"
