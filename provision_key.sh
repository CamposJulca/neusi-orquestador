#!/usr/bin/env bash
#
# provision_key.sh — Fix de raiz: deja cada nodo con autenticacion por LLAVE.
#
# Instala la llave publica ~/.ssh/id_ed25519.pub en authorized_keys de los
# nodos y verifica que el login por llave funcione (sin password).
#
# Uso:
#   ./provision_key.sh                 # aprovisiona TODOS los nodos de la tabla
#   ./provision_key.sh <user> <host> <port>   # un solo nodo (p.ej. 104 con su puerto nuevo)
#   ./provision_key.sh --check         # solo verifica (no instala) login por llave
#
# La primera vez ssh-copy-id pedira el password del nodo. Despues ya no.

set -uo pipefail

KEY="${HOME}/.ssh/id_ed25519"
PUB="${KEY}.pub"

GREEN="\e[32m"; RED="\e[31m"; YELLOW="\e[33m"; CYAN="\e[36m"; RESET="\e[0m"

# Tabla de nodos:  "user host port"
# Manten estos puertos sincronizados con backend/app/config/servers.py
NODES=(
  "produccion       4.tcp.ngrok.io 12385"
  "desarrollo       8.tcp.ngrok.io 21457"
  "pruebas          8.tcp.ngrok.io 17803"
  "simulador1       8.tcp.ngrok.io 10849"
  "camposjulca      8.tcp.ngrok.io 27504"
  "cristhiamdaniel  8.tcp.ngrok.io 11636"
)

CHECK_ONLY=0
SINGLE=()

case "${1:-}" in
  --check) CHECK_ONLY=1 ;;
  "") ;;
  *)
    if [ "$#" -ne 3 ]; then
      echo -e "${RED}Uso: $0 [<user> <host> <port>] | --check${RESET}"; exit 1
    fi
    SINGLE=("$1 $2 $3")
    ;;
esac

if [ ! -f "$PUB" ]; then
  echo -e "${RED}No existe la llave publica $PUB${RESET}"
  echo -e "${YELLOW}Generala con:  ssh-keygen -t ed25519${RESET}"
  exit 1
fi

# Comprueba si el login por llave ya funciona (BatchMode = sin password)
key_works() {
  local user="$1" host="$2" port="$3"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=6 \
      -o PreferredAuthentications=publickey -i "$KEY" -p "$port" \
      "$user@$host" 'exit 0' >/dev/null 2>&1
}

provision_one() {
  local user="$1" host="$2" port="$3"
  printf "%-16s %s:%s  " "$user" "$host" "$port"

  if key_works "$user" "$host" "$port"; then
    echo -e "${GREEN}OK (llave ya autorizada)${RESET}"
    return 0
  fi

  if [ "$CHECK_ONLY" -eq 1 ]; then
    echo -e "${YELLOW}sin llave (no instalada)${RESET}"
    return 1
  fi

  # Verifica primero que el puerto responde para no colgarse en tuneles caidos
  if ! timeout 6 bash -c "cat </dev/null >/dev/tcp/$host/$port" 2>/dev/null; then
    echo -e "${RED}OFFLINE (tunel caido / puerto cerrado)${RESET}"
    return 2
  fi

  echo -e "${CYAN}instalando llave...${RESET}"
  if ssh-copy-id -i "$PUB" -o StrictHostKeyChecking=no -p "$port" "$user@$host" >/dev/null 2>&1; then
    if key_works "$user" "$host" "$port"; then
      printf "%-16s %s:%s  ${GREEN}LLAVE INSTALADA Y VERIFICADA${RESET}\n" "$user" "$host" "$port"
      return 0
    fi
  fi
  printf "%-16s %s:%s  ${RED}fallo al instalar (revisa password/usuario)${RESET}\n" "$user" "$host" "$port"
  return 1
}

echo -e "${CYAN}=== Aprovisionamiento de llave SSH ($([ $CHECK_ONLY -eq 1 ] && echo verificar || echo instalar)) ===${RESET}"
TARGETS=("${NODES[@]}")
[ "${#SINGLE[@]}" -gt 0 ] && TARGETS=("${SINGLE[@]}")

rc=0
for entry in "${TARGETS[@]}"; do
  # shellcheck disable=SC2086
  provision_one $entry || rc=1
done

echo ""
echo -e "${YELLOW}Tras aprovisionar, recarga el monitor:  docker compose up -d --force-recreate backend${RESET}"
exit $rc
