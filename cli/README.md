# Neusi CLI

CLI de operaciones de terminal para la infraestructura Neusi, **unificado con el
Neusi Infra Monitor**: usa el MISMO backend que el dashboard web como fuente de
verdad de `host:puerto` de cada nodo. Así, cuando un puerto ngrok rota, no hay que
editar ningún script: se actualiza el backend y todo (menú, estado y dashboard) lo refleja.

## Componentes

| Archivo | Qué hace | Plataforma |
|---------|----------|------------|
| `neusi` | Menú interactivo: conectar por SSH, ver estado, refrescar puertos, abrir dashboard. | Linux/macOS (bash) |
| `neusi-refresh` | Actualiza en el backend los puertos ngrok actuales (modo auto y manual). | Linux/macOS (bash) |
| `neusi.ps1` | Misma funcionalidad que `neusi`, puerto nativo a PowerShell. | Windows (PowerShell) |
| `neusi-refresh.ps1` | Misma funcionalidad que `neusi-refresh`, puerto nativo a PowerShell. | Windows (PowerShell) |

En Linux/macOS los scripts bash se exponen como comandos vía symlinks en `~/.local/bin/`.
En Windows se usan los `.ps1` (ver [Uso en Windows (PowerShell)](#uso-en-windows-powershell)).

## Instalación / reinstalación

Desde la raíz del repo (`neusi-infra-monitor/`):

```bash
ln -sf "$PWD/cli/neusi"         ~/.local/bin/neusi
ln -sf "$PWD/cli/neusi-refresh" ~/.local/bin/neusi-refresh
```

Requisitos: `bash` (4+), `python3`, `curl`, `ssh`, y `~/.local/bin` en el `PATH`.

## Uso

### `neusi` — menú interactivo

```bash
neusi
```

Opciones del menú:

```
1..6  Conectar por SSH a un nodo (produccion, desarrollo, pruebas, simulador1, camposjulca, cristhiamdaniel)
7     Ver infraestructura  (estado ONLINE/OFFLINE de los 6 nodos)
8     Refrescar puertos (auto: produccion + auxiliares desde pruebas)  -> llama a neusi-refresh
9     Abrir dashboard web                          -> abre el frontend del monitor
0     Salir
```

La cabecera indica la fuente de los endpoints: **`backend en vivo`** o
**`fallback local`** (si el backend del monitor no responde).

### `neusi-refresh` — actualizar puertos en el backend

```bash
# AUTO (2 pasadas):
#  1) entra a produccion por SSH (llave, vía ngrok), lee su ngrok local y
#     actualiza .10 (produccion), .11 (pruebas) y .12 (desarrollo).
#  2) con el host:port de pruebas recién obtenido, entra por SSH a pruebas y
#     lee su ngrok para actualizar los auxiliares .103/.104/.105.
neusi-refresh

# MANUAL: refresco puntual de cualquier nodo si rota fuera de las pasadas auto.
neusi-refresh 103 6.tcp.ngrok.io 28249   # simulador1
neusi-refresh 104 4.tcp.ngrok.io 29531   # camposjulca
neusi-refresh 105 8.tcp.ngrok.io 27504   # cristhiamdaniel
```

## Uso en Windows (PowerShell)

Los `.ps1` son un puerto nativo: **no requieren bash, WSL ni python3**. Aprovechan
`Invoke-RestMethod` (JSON nativo), `Test-NetConnection`/`TcpClient` para el estado
y el cliente OpenSSH (`ssh.exe`/`scp.exe`) que ya trae Windows.

### Requisitos

1. **Windows 10 1809+ o Windows 11** (PowerShell 5.1 incluido; PowerShell 7 también sirve).
2. **Cliente OpenSSH** (`ssh.exe` / `scp.exe`). Comprueba con `ssh -V`. Si falta:
   ```powershell
   Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
   ```
3. **Tu llave privada** en `%USERPROFILE%\.ssh\id_ed25519` (la misma que usas en Linux).

### Ejecutar

```powershell
# Desde la carpeta cli\ del repo:
powershell -ExecutionPolicy Bypass -File .\neusi.ps1

# o, si permites scripts en tu sesión:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\neusi.ps1
```

`neusi-refresh.ps1` funciona igual que su versión bash (auto y manual):

```powershell
.\neusi-refresh.ps1                          # AUTO: produccion + auxiliares desde pruebas
.\neusi-refresh.ps1 103 6.tcp.ngrok.io 28249 # MANUAL: un nodo puntual
```

> Atajo opcional: para invocar `neusi` desde cualquier carpeta, añade un alias en tu
> perfil de PowerShell (`notepad $PROFILE`):
> `function neusi { & "C:\ruta\al\repo\cli\neusi.ps1" }`

### Diferencias respecto al bash

- El estado ONLINE/OFFLINE usa un socket TCP con timeout (no `/dev/tcp`).
- El dashboard se abre con `Start-Process` (no `xdg-open`).
- El parseo de `/api/servers` y `/api/tunnels` es nativo (`ConvertFrom-Json`), sin `python3`.
- Las variables de entorno y rutas (`~` → `%USERPROFILE%`) siguen las convenciones de Windows.

## Mapa de nodos

| code (backend) | maq (menú) | usuario | rol | túnel servido por |
|----------------|------------|---------|-----|-------------------|
| 100 | 10  | produccion | Producción | ngrok de produccion |
| 101 | 12  | desarrollo | Desarrollo | ngrok de produccion |
| 102 | 11  | pruebas | Testing | ngrok de produccion |
| 103 | 13  | simulador1 | Simulador | ngrok de pruebas |
| 104 | 14  | camposjulca | Nodo auxiliar | ngrok de pruebas |
| 105 | 105 | cristhiamdaniel | Nodo auxiliar | ngrok de pruebas |

> La clave de unión entre menú y backend es el **usuario**, no el número
> (la numeración del menú y la del backend difieren).

## Cómo se mantienen frescos los puertos (sin agentes)

Los puertos ngrok son efímeros (cambian al reiniciar el túnel). En lugar de
agentes en cada nodo (no viable en esta topología: los nodos no alcanzan al
backend en la laptop), `neusi-refresh` (auto) los descubre por SSH en **dos
pasadas encadenadas**:

- **produccion** (octetos `.10/.11/.12`, túneles `ssh-prod/test/dev`) los expone
  un único ngrok; la pasada 1 los descubre y actualiza de un golpe.
- **pruebas** expone los auxiliares (túneles `ssh-103/104/105`, octetos internos
  `.13/.14/.105`); con el host:port de pruebas obtenido en la pasada 1, la pasada 2
  entra por SSH a pruebas y los actualiza.

El code de cada nodo se resuelve primero por el **nombre del túnel** `ssh-<code>`
(como hace pruebas) y, si no, por el **octeto interno** (`IP2CODE`, como produccion).
Si algún nodo rota fuera de esas lecturas, refréscalo puntual con
`neusi-refresh <code> <host> <port>`.

## Configuración (variables de entorno)

| Variable | Default | Usado por |
|----------|---------|-----------|
| `NEUSI_MONITOR_URL` | `http://localhost:8070` | `neusi`, `neusi-refresh` (backend) |
| `NEUSI_DASHBOARD_URL` | `http://localhost:8080` | `neusi` (opción 9) |
| `NEUSI_ENV_FILE` | `~/InfraNeusi/neusi-infra-monitor/backend/.env` | `neusi-refresh` (lee `REGISTER_TOKEN`) |
| `REGISTER_TOKEN` | (del `.env`) | `neusi-refresh` (auth del endpoint `/register`) |
| `PROD_SSH_USER` / `PROD_SSH_HOST` / `PROD_SSH_PORT` | `produccion` / `4.tcp.ngrok.io` / `12385` | `neusi-refresh` (auto, pasada 1) |
| `PRUEBAS_SSH_USER` | `pruebas` | `neusi-refresh` (auto, pasada 2; host/puerto se toman de la pasada 1) |

## Solución de problemas

| Síntoma | Causa probable / acción |
|---------|-------------------------|
| Cabecera dice `fallback local` | El backend del monitor no responde. Levántalo: `./monitor.sh up`. |
| Un nodo sale OFFLINE pero la máquina está viva | El puerto ngrok rotó. `neusi-refresh` (auto: principales desde produccion, auxiliares desde pruebas) o manual puntual. |
| `neusi-refresh` auto falla al leer produccion | Revisa que el SSH por llave a produccion funcione y que ngrok corra ahí. |
| Conexión SSH a desarrollo (.12) "Connection closed" | La máquina `192.168.40.12` está apagada/sin red, no es el CLI. |
