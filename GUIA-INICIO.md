# Guía de inicio — Orquestador Neusi (paso a paso)

Esta guía te lleva de **cero a funcionando**. Antes de cualquier comando, lee el
[paso 0](#paso-0-define-tu-rol): según tu rol haces **una** de las dos rutas.

---

## Paso 0: Define tu rol

El proyecto tiene **dos partes**. Tienes que decidir cuál vas a montar en ESTA máquina:

| Si quieres… | Tu rol | Qué levantas | Sistema recomendado | Ve a |
|-------------|--------|--------------|---------------------|------|
| El servidor web + la base de datos que conoce los nodos | **CENTRAL** | Backend + dashboard (Docker) | **Linux** | [Ruta A](#ruta-a-levantar-la-central-back--dashboard) |
| Solo conectarte/operar los nodos desde tu equipo | **CLIENTE** | Nada — solo usas el CLI `neusi` | Windows o Linux | [Ruta B](#ruta-b-usar-el-cli-cliente) |

> **Regla simple:** la CENTRAL se levanta **una sola vez** en una máquina (la que tiene
> Docker y la llave SSH a todos los nodos). Todos los demás son CLIENTES que apuntan a esa
> central. Si solo abriste tu Windows para conectarte a los servidores → eres **CLIENTE**,
> ve directo a la [Ruta B](#ruta-b-usar-el-cli-cliente).

Ambas rutas empiezan clonando el repo (si aún no lo hiciste):

```bash
git clone https://github.com/CamposJulca/neusi-orquestador.git
cd neusi-orquestador
```

---

## Ruta A: Levantar la CENTRAL (backend + dashboard)

> Esto es lo que llamas "levantar el proyecto": deja corriendo la API (`:8070`) y el
> dashboard web (`:8080`). **Recomendado en Linux** (el `docker-compose.yml` monta `~/.ssh`
> y usa la red del host). En Windows requiere ajustes; si tu central es Windows, avísame.

### A.1 — Instalar Docker

```bash
docker --version
docker compose version
```
- Si ambos responden una versión → sigue.
- Si no: instala Docker. En Debian/Ubuntu: `sudo apt install -y docker.io docker-compose-plugin`
  y luego `sudo usermod -aG docker $USER` (cierra y reabre sesión).

### A.2 — Crear el archivo de configuración `backend/.env`

El repo **no** trae el `.env` (tiene secretos). Créalo a partir del ejemplo:

```bash
cp backend/.env.example backend/.env
```

Ahora **edita `backend/.env`** y revisa/añade estas claves:

```env
USE_MOCK_DATA=false
SSH_ENABLED=true
SSH_USERNAME=desarrollo               # usuario SSH por defecto de los nodos
SSH_PRIVATE_KEY_PATH=/root/.ssh/id_ed25519   # ruta DENTRO del contenedor (no la cambies)
SSH_TIMEOUT_SECONDS=5
SSH_FALLBACK_TO_MOCK=false

# >>> AÑADE esta línea (no viene en el .example y es OBLIGATORIA) <<<
REGISTER_TOKEN=pega-aqui-un-token-secreto
```

Genera un token seguro para `REGISTER_TOKEN`:
```bash
openssl rand -hex 24
```
Copia el resultado en `REGISTER_TOKEN=`. **Apunta ese token**: los nodos (agentes) y el
comando `neusi-refresh` deben usar exactamente el mismo.

### A.3 — Tener la llave SSH lista

El backend se conecta a los nodos por **llave** (no password). Debe existir tu llave
privada en `~/.ssh/id_ed25519` (el `docker-compose.yml` la monta dentro del contenedor):
```bash
ls -l ~/.ssh/id_ed25519
```
Si no está, copia ahí la llave autorizada en los nodos y dale permisos:
`chmod 600 ~/.ssh/id_ed25519`.

### A.4 — Levantar 🚀

Con el script de arranque (la forma fácil):
```bash
chmod +x monitor.sh
./monitor.sh up
```
…o directamente con Docker:
```bash
docker compose up -d --build
```

**Qué debe salir:** al terminar verás
```
Frontend: http://localhost:8080
Backend:  http://localhost:8070
```

### A.5 — Verificar que quedó arriba

```bash
./monitor.sh status     # los contenedores deben decir "Up"
curl http://localhost:8070/health   # debe responder algo tipo {"status":"ok"}
```
Y abre en el navegador: **http://localhost:8080** → deberías ver el dashboard.

### A.6 — Comandos del día a día

```bash
./monitor.sh logs      # ver logs en vivo (Ctrl+C para salir)
./monitor.sh status    # estado de los contenedores
./monitor.sh down      # apagar todo
./monitor.sh rebuild   # reconstruir tras cambios
```

> Si la central NO está en `localhost` para tus clientes (otra máquina), comparte su
> dirección: `http://IP-DE-LA-CENTRAL:8070` (backend) y `:8080` (dashboard). Los nodos y
> clientes deben poder alcanzar esa IP/puerto.

Una vez arriba la central, en tu equipo de trabajo usa el CLI → [Ruta B](#ruta-b-usar-el-cli-cliente).

---

## Ruta B: Usar el CLI (CLIENTE)

Aquí **no levantas nada**: el CLI `neusi` se conecta por SSH a los nodos y lee el estado
desde la central. Elige tu sistema.

### B-Windows (PowerShell o CMD)

#### B.1 — Instalar el cliente SSH

Abre **PowerShell** y prueba:
```powershell
ssh -V
```
- Responde versión → sigue.
- Falla → abre **PowerShell como Administrador** y corre:
  ```powershell
  Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
  ```

#### B.2 — Colocar tu llave SSH

Tu llave privada debe estar en `C:\Users\TuUsuario\.ssh\id_ed25519`. Verifica:
```powershell
dir $env:USERPROFILE\.ssh
```
Si no está, cópiala ahí (la misma autorizada en los nodos) y ajusta permisos:
```powershell
icacls "$env:USERPROFILE\.ssh\id_ed25519" /inheritance:r /grant:r "$($env:USERNAME):(R)"
```

#### B.3 — Entrar a la carpeta del CLI

```powershell
cd $env:USERPROFILE\neusi-orquestador\cli
```
(verifica con `dir` que ves `neusi.ps1`)

#### B.4 — (Solo si la central NO está en esta PC) indicar su URL

```powershell
$env:NEUSI_MONITOR_URL   = "http://IP-DE-LA-CENTRAL:8070"
$env:NEUSI_DASHBOARD_URL = "http://IP-DE-LA-CENTRAL:8080"
```
Si no lo sabes, sáltalo: arrancará en modo `fallback local`.

#### B.5 — Ejecutar 🚀

```powershell
powershell -ExecutionPolicy Bypass -File .\neusi.ps1
```

> **Atajo recomendado (un solo paso):** en vez de los pasos B.4 + B.5, ejecuta el
> lanzador `neusi-cliente.cmd` (incluido en `cli\`). Ya trae configurada la URL de la
> central y abre el menú directo. Puedes hacerle **doble clic** o, desde CMD:
> ```cmd
> cd %USERPROFILE%\neusi-orquestador\cli
> neusi-cliente.cmd
> ```
> Si la laptop-central cambia de IP, pásala como argumento: `neusi-cliente.cmd 192.168.10.25`.
> Para editar la IP por defecto, abre `neusi-cliente.cmd` y cambia la línea `set "CENTRAL=..."`.

> **¿Abriste CMD en vez de PowerShell?** Funciona igual; desde CMD el paso 4 es
> `set NEUSI_MONITOR_URL=http://IP:8070` y el arranque es exactamente el mismo comando
> `powershell -ExecutionPolicy Bypass -File neusi.ps1`.

#### B.6 — (Opcional) atajo `neusi`

```powershell
notepad $PROFILE
```
Pega y guarda; reabre PowerShell:
```powershell
function neusi { & "$env:USERPROFILE\neusi-orquestador\cli\neusi.ps1" }
```
Luego basta escribir `neusi`.

---

### B-Linux (bash)

#### B.1 — Instalar dependencias (si faltan)

```bash
# Debian/Ubuntu
sudo apt install -y git openssh-client python3 curl
# Arch/Manjaro
sudo pacman -S --needed git openssh python curl
```
Llave en `~/.ssh/id_ed25519` con permisos `chmod 600 ~/.ssh/id_ed25519`.

#### B.2 — Instalar los comandos (symlinks)

Desde la raíz del repo:
```bash
chmod +x cli/neusi cli/neusi-refresh
mkdir -p ~/.local/bin
ln -sf "$PWD/cli/neusi"         ~/.local/bin/neusi
ln -sf "$PWD/cli/neusi-refresh" ~/.local/bin/neusi-refresh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
```

#### B.3 — (Solo si la central NO está aquí) indicar su URL

```bash
export NEUSI_MONITOR_URL="http://IP-DE-LA-CENTRAL:8070"
export NEUSI_DASHBOARD_URL="http://IP-DE-LA-CENTRAL:8080"
```

#### B.4 — Ejecutar 🚀

```bash
neusi
```

---

## El menú (igual en Windows y Linux)

```
1..6  Conectar por SSH a un nodo
7     Ver infraestructura (ONLINE/OFFLINE de los 6 nodos)
8     Refrescar puertos (sincroniza los puertos ngrok con la central)
9     Abrir dashboard web
10    Subir archivo a una maquina (scp)
11    Descargar archivo de una maquina (scp)
0     Salir
```

Mira la **cabecera** del menú:
- **`backend en vivo`** → está leyendo datos frescos de la central. ✅
- **`fallback local`** → no alcanzó la central; usa una tabla fija (puede estar
  desactualizada). Revisa la URL del paso "indicar su URL".

> La opción **8 (refrescar)** necesita el `REGISTER_TOKEN` (el del `backend/.env`).
> Normalmente se ejecuta en la central. Para hacerlo desde un cliente, define el token antes:
> Windows `($env:REGISTER_TOKEN="...")`, Linux `export REGISTER_TOKEN=...`.

---

## Solución de problemas

| Síntoma | Acción |
|---------|--------|
| Cabecera dice `fallback local` | La central no responde. Verifica que esté arriba (`./monitor.sh status`) y la URL `NEUSI_MONITOR_URL`. |
| `docker: command not found` (Ruta A) | Instala Docker ([paso A.1](#a1--instalar-docker)). |
| El backend no levanta / error de `.env` | ¿Creaste `backend/.env` y añadiste `REGISTER_TOKEN`? ([paso A.2](#a2--crear-el-archivo-de-configuración-backendenv)). |
| `ssh`/`scp` no se reconoce (Windows) | Instala OpenSSH ([paso B.1](#b1--instalar-el-cliente-ssh)). |
| `.\neusi.ps1` bloqueado por política | Usa `powershell -ExecutionPolicy Bypass -File .\neusi.ps1`. |
| `Permission denied (publickey)` al conectar | Tu llave no está en `.ssh/id_ed25519` o no está autorizada en el nodo. |
| Un nodo sale OFFLINE pero está encendido | Su puerto ngrok rotó → opción 8, o `neusi-refresh <code> <host> <port>`. |

---

Detalle interno del CLI: [`cli/README.md`](cli/README.md) · Documentación técnica del
backend/stack: [`README.md`](README.md).
