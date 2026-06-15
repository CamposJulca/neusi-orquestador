# Guía de inicio — Orquestador Neusi

Guía paso a paso para **clonar y usar el orquestador** (`neusi`) desde **Windows** o
**Linux**. Si solo quieres operar los nodos (conectarte por SSH, ver estado, subir/bajar
archivos), te basta el **cliente CLI**. El backend + dashboard web es opcional y se
explica al final.

---

## Índice

- [0. ¿Qué voy a instalar?](#0-qué-voy-a-instalar)
- [1. Requisitos comunes](#1-requisitos-comunes)
- [2. Clonar el repositorio](#2-clonar-el-repositorio)
- [3. Usar el CLI en Windows (PowerShell)](#3-usar-el-cli-en-windows-powershell)
- [4. Usar el CLI en Linux (bash)](#4-usar-el-cli-en-linux-bash)
- [5. Apuntar al backend (importante)](#5-apuntar-al-backend-importante)
- [6. El menú paso a paso](#6-el-menú-paso-a-paso)
- [7. (Opcional) Levantar backend + dashboard](#7-opcional-levantar-backend--dashboard)
- [8. Solución de problemas](#8-solución-de-problemas)

---

## 0. ¿Qué voy a instalar?

El proyecto tiene **dos piezas independientes**:

| Pieza | Para qué | ¿La necesito? |
|-------|----------|---------------|
| **CLI `neusi`** | Conectarte por SSH a los nodos, ver estado, subir/descargar archivos, refrescar puertos | **Sí** — es el orquestador |
| **Backend + dashboard** (Docker) | Vista web del estado y fuente de verdad de `host:puerto` | Opcional; suele correr en una sola máquina (la "central") |

> El CLI funciona aunque no tengas el backend al lado: en ese caso le indicas la URL
> del backend que corre en otra máquina (ver [paso 5](#5-apuntar-al-backend-importante)).

---

## 1. Requisitos comunes

En **cualquier** sistema necesitas:

1. **Git** — para clonar el repo.
2. **Cliente SSH** (`ssh` y `scp`) — para conectarte a los nodos.
3. **Tu llave privada SSH** (la misma autorizada en los nodos), en la carpeta `.ssh` de tu usuario:
   - Linux/macOS: `~/.ssh/id_ed25519`
   - Windows: `C:\Users\TuUsuario\.ssh\id_ed25519`

La instalación concreta de cada uno está en los pasos por sistema (3 y 4).

---

## 2. Clonar el repositorio

**Windows (PowerShell):**
```powershell
cd $env:USERPROFILE
git clone https://github.com/CamposJulca/neusi-orquestador.git
cd neusi-orquestador
```

**Linux/macOS (bash):**
```bash
cd ~
git clone https://github.com/CamposJulca/neusi-orquestador.git
cd neusi-orquestador
```

---

## 3. Usar el CLI en Windows (PowerShell)

### 3.1 Instalar requisitos

**Git** (si `git --version` falla):
```powershell
winget install Git.Git
```
(cierra y reabre PowerShell tras instalar)

**Cliente OpenSSH** (si `ssh -V` falla) — PowerShell **como Administrador**:
```powershell
Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
```

**Llave SSH** — copia tu `id_ed25519` a `C:\Users\TuUsuario\.ssh\` y ajusta permisos:
```powershell
icacls "$env:USERPROFILE\.ssh\id_ed25519" /inheritance:r /grant:r "$($env:USERNAME):(R)"
```

### 3.2 Ejecutar el orquestador

Desde la carpeta del repo:
```powershell
cd $env:USERPROFILE\neusi-orquestador\cli
powershell -ExecutionPolicy Bypass -File .\neusi.ps1
```

### 3.3 (Opcional) Comando `neusi` desde cualquier carpeta

```powershell
notepad $PROFILE
```
Agrega esta línea, guarda y reabre PowerShell:
```powershell
function neusi { & "$env:USERPROFILE\neusi-orquestador\cli\neusi.ps1" }
```
Ahora basta con escribir:
```powershell
neusi
```

> **No necesitas** WSL, bash ni Python: `neusi.ps1` es un puerto nativo a PowerShell.

---

## 4. Usar el CLI en Linux (bash)

### 4.1 Instalar requisitos

Casi siempre ya están. Si no:
```bash
# Debian/Ubuntu
sudo apt install -y git openssh-client python3 curl
# Arch/Manjaro
sudo pacman -S --needed git openssh python curl
```
Copia tu llave a `~/.ssh/id_ed25519` y dale permisos: `chmod 600 ~/.ssh/id_ed25519`.

### 4.2 Instalar los comandos

Desde la raíz del repo:
```bash
chmod +x cli/neusi cli/neusi-refresh
mkdir -p ~/.local/bin
ln -sf "$PWD/cli/neusi"         ~/.local/bin/neusi
ln -sf "$PWD/cli/neusi-refresh" ~/.local/bin/neusi-refresh
```
Asegúrate de que `~/.local/bin` esté en tu `PATH` (en bash):
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
```

### 4.3 Ejecutar

```bash
neusi
```

---

## 5. Apuntar al backend (importante)

El menú lee los puertos reales de los nodos desde el **backend del monitor**
(`GET /api/servers`). Por defecto busca `http://localhost:8070`.

- **Si el backend corre en ESTA máquina:** no hagas nada, ya funciona.
- **Si el backend corre en OTRA máquina** (lo normal para un cliente): indícale la URL
  **antes** de lanzar el menú.

**Windows (PowerShell):**
```powershell
$env:NEUSI_MONITOR_URL   = "http://IP-DEL-BACKEND:8070"
$env:NEUSI_DASHBOARD_URL = "http://IP-DEL-BACKEND:8080"
.\neusi.ps1
```

**Linux (bash):**
```bash
export NEUSI_MONITOR_URL="http://IP-DEL-BACKEND:8070"
export NEUSI_DASHBOARD_URL="http://IP-DEL-BACKEND:8080"
neusi
```

Cómo saber si funcionó: en la cabecera del menú,
- **`backend en vivo`** = está leyendo datos frescos. ✅
- **`fallback local`** = no alcanzó el backend y usa una tabla fija (puede estar
  desactualizada). Revisa la URL y que el backend esté arriba.

---

## 6. El menú paso a paso

Al ejecutar `neusi` verás:

```
1..6  Conectar por SSH a un nodo (produccion, desarrollo, pruebas, simulador1, camposjulca, cristhiamdaniel)
7     Ver infraestructura  (estado ONLINE/OFFLINE de los 6 nodos)
8     Refrescar puertos    (actualiza en el backend los puertos ngrok actuales)
9     Abrir dashboard web
10    Subir archivo a una maquina      (scp)
11    Descargar archivo de una maquina (scp)
0     Salir
```

- **Conectar (1–6):** abre una sesión SSH interactiva al nodo. Sales con `exit`.
  La primera vez te pedirá aceptar la huella del host (`yes`).
- **Subir/descargar (10/11):** te pide la máquina y las rutas de origen/destino.
- **Refrescar (8):** sincroniza los puertos ngrok con el backend. Requiere el
  `REGISTER_TOKEN` (ver nota abajo) y normalmente se ejecuta desde la máquina central.

> **Sobre el `REGISTER_TOKEN`:** la opción 8 / `neusi-refresh` necesita ese token, que
> vive en `backend/.env`. Ese archivo **no está en el repositorio** por seguridad. Si vas
> a refrescar desde un cliente, defínelo antes:
> ```powershell
> $env:REGISTER_TOKEN = "el-token-real"     # Windows
> ```
> ```bash
> export REGISTER_TOKEN="el-token-real"     # Linux
> ```

---

## 7. (Opcional) Levantar backend + dashboard

Solo en la máquina que hará de central. Requiere **Docker**.

**Linux:**
```bash
cd neusi-orquestador
cp backend/.env.example backend/.env   # y edita REGISTER_TOKEN y demás valores
docker compose up -d --build
```
- Dashboard: `http://localhost:8080`
- Backend (API): `http://localhost:8070`

**Windows:** instala **Docker Desktop**, abre PowerShell en la carpeta del repo y corre
los mismos comandos (`docker compose up -d --build`). Nota: el `docker-compose.yml` monta
`~/.ssh` y usa `network_mode: host`, pensado para Linux; en Windows puede requerir ajustes
(montar la ruta de la llave y mapear puertos). Para Windows lo recomendado es usar solo el
**cliente CLI** y apuntar al backend de la máquina central ([paso 5](#5-apuntar-al-backend-importante)).

> El archivo `backend/.env` no viene en el repo (contiene secretos). Créalo a partir de
> `backend/.env.example` antes del primer arranque.

---

## 8. Solución de problemas

| Síntoma | Causa probable / acción |
|---------|-------------------------|
| Cabecera dice `fallback local` | El menú no alcanza el backend. Revisa `NEUSI_MONITOR_URL` y que el backend esté arriba ([paso 5](#5-apuntar-al-backend-importante)). |
| `ssh.exe`/`scp.exe` no se reconoce (Windows) | Falta el cliente OpenSSH: `Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0`. |
| `.\neusi.ps1` no se ejecuta por política | Usa `powershell -ExecutionPolicy Bypass -File .\neusi.ps1` o `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`. |
| `Permission denied (publickey)` al conectar | Tu llave no está en `~/.ssh/id_ed25519` o no está autorizada en el nodo. |
| Un nodo sale OFFLINE pero está encendido | El puerto ngrok rotó. Refresca con la opción 8 o `neusi-refresh <code> <host> <port>`. |
| `neusi-refresh` falla con "No encontre REGISTER_TOKEN" | Define `REGISTER_TOKEN` (ver nota del [paso 6](#6-el-menú-paso-a-paso)) o créalo en `backend/.env`. |

---

¿Dudas sobre el detalle interno del CLI? Mira [`cli/README.md`](cli/README.md).
Documentación técnica del monitor/stack: [`README.md`](README.md).
