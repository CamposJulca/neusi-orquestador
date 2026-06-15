<#
  neusi.ps1 — NEUSI OPERATIONS CLI (version PowerShell para Windows)

  Puerto nativo de cli/neusi (bash). Corre desde PowerShell 5.1+ o PowerShell 7
  en Windows 10 1809+ / Windows 11. Usa el MISMO backend que el dashboard web
  como fuente de verdad de host:puerto de cada nodo:
    - Menu SSH y estado: leen GET /api/servers del backend del monitor.
    - Refrescar puertos:  delega en neusi-refresh.ps1 (auto: produccion + pruebas).
    - Dashboard web:      abre el frontend del monitor en el navegador.
  Si el backend no responde, el menu usa el fallback local de abajo.

  Requisitos en Windows:
    - Cliente OpenSSH (ssh.exe / scp.exe). Viene con Windows 10 1809+; si falta:
        Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
    - Tu llave privada en %USERPROFILE%\.ssh (id_ed25519), igual que en Linux.

  Config (variables de entorno):
    NEUSI_MONITOR_URL    backend del monitor   (default http://localhost:8070)
    NEUSI_DASHBOARD_URL  frontend del monitor  (default http://localhost:8080)

  Uso:
    powershell -ExecutionPolicy Bypass -File .\neusi.ps1
#>

$ErrorActionPreference = 'Stop'

$MonitorUrl   = if ($env:NEUSI_MONITOR_URL)   { $env:NEUSI_MONITOR_URL }   else { 'http://localhost:8070' }
$DashboardUrl = if ($env:NEUSI_DASHBOARD_URL) { $env:NEUSI_DASHBOARD_URL } else { 'http://localhost:8080' }
$SelfDir      = Split-Path -Parent $MyInvocation.MyCommand.Path

# Catalogo de maquinas (codigo de pantalla, usuario SSH, rol). Misma lista que el bash.
$Machines = @(
    [pscustomobject]@{ Name = '10';  User = 'produccion';      Role = 'Produccion'    }
    [pscustomobject]@{ Name = '12';  User = 'desarrollo';      Role = 'Desarrollo'    }
    [pscustomobject]@{ Name = '11';  User = 'pruebas';         Role = 'Testing'       }
    [pscustomobject]@{ Name = '13';  User = 'simulador1';      Role = 'Simulador'     }
    [pscustomobject]@{ Name = '14';  User = 'camposjulca';     Role = 'Nodo auxiliar' }
    [pscustomobject]@{ Name = '105'; User = 'cristhiamdaniel'; Role = 'Nodo auxiliar' }
)

# Endpoints por usuario: @{ user = @{ Host = '...'; Port = NNN } }. Se llena en Load-Servers.
$script:Endpoints = @{}
$script:Source    = ''

function Set-Fallback {
    $script:Endpoints = @{
        produccion      = @{ Host = '4.tcp.ngrok.io'; Port = 12385 }
        desarrollo      = @{ Host = '8.tcp.ngrok.io'; Port = 21457 }
        pruebas         = @{ Host = '8.tcp.ngrok.io'; Port = 17803 }
        simulador1      = @{ Host = '6.tcp.ngrok.io'; Port = 28249 }
        camposjulca     = @{ Host = '4.tcp.ngrok.io'; Port = 29531 }
        cristhiamdaniel = @{ Host = '8.tcp.ngrok.io'; Port = 27504 }
    }
}

function Load-Servers {
    Set-Fallback
    $script:Source = 'fallback local (backend no disponible)'
    try {
        $data = Invoke-RestMethod -Uri "$MonitorUrl/api/servers" -TimeoutSec 4 -ErrorAction Stop
    } catch {
        return
    }
    if (-not $data) { return }
    foreach ($s in $data) {
        $u = $s.ssh_username; $h = $s.host; $p = $s.ssh_port
        if ($u -and $h -and $p) {
            $script:Endpoints[$u] = @{ Host = [string]$h; Port = [int]$p }
        }
    }
    $script:Source = "backend en vivo ($MonitorUrl)"
}

function Get-Endpoint([string]$User) { return $script:Endpoints[$User] }

# Prueba de puerto TCP con timeout (equivalente a /dev/tcp + timeout del bash).
function Test-Port([string]$TargetHost, [int]$Port, [int]$TimeoutMs = 3000) {
    if (-not $TargetHost -or -not $Port) { return $false }
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect($TargetHost, $Port, $null, $null)
        if ($iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false) -and $client.Connected) {
            $client.EndConnect($iar); return $true
        }
        return $false
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Require-Ssh {
    if (-not (Get-Command ssh.exe -ErrorAction SilentlyContinue)) {
        Write-Host "No encontre ssh.exe. Instala el cliente OpenSSH:" -ForegroundColor Red
        Write-Host "  Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0" -ForegroundColor Yellow
        return $false
    }
    return $true
}

function Pause-Menu { Write-Host ''; Read-Host 'Presiona ENTER para volver al menu' | Out-Null }

function Connect-Ssh([string]$Name, [string]$User) {
    if (-not (Require-Ssh)) { Pause-Menu; return }
    $ep = Get-Endpoint $User
    Clear-Host
    Write-Host '=================================' -ForegroundColor Blue
    Write-Host "     CONECTANDO A $Name"          -ForegroundColor Blue
    Write-Host '=================================' -ForegroundColor Blue
    Write-Host ''
    Write-Host "Usuario: $User"            -ForegroundColor Cyan
    Write-Host "Host:    $($ep.Host)"      -ForegroundColor Cyan
    Write-Host "Puerto:  $($ep.Port)"      -ForegroundColor Cyan
    Write-Host ''
    if (-not $ep -or -not $ep.Host -or -not $ep.Port) {
        Write-Host "No hay endpoint para '$User' (ni en backend ni en fallback)." -ForegroundColor Red
    } else {
        & ssh.exe "$User@$($ep.Host)" -p $ep.Port
    }
    Write-Host ''
    Write-Host 'Conexion cerrada.' -ForegroundColor Yellow
    Pause-Menu
}

function Show-Infra {
    Load-Servers
    Clear-Host
    Write-Host '============================================================' -ForegroundColor Blue
    Write-Host '                 NEUSI INFRAESTRUCTURA'                        -ForegroundColor Blue
    Write-Host '============================================================' -ForegroundColor Blue
    Write-Host "Fuente de endpoints: $($script:Source)"
    Write-Host ''
    Write-Host ('{0,-8} {1,-18} {2,-24} {3,-10} {4,-16}' -f 'MAQ','USUARIO','ENDPOINT','ESTADO','ROL')
    Write-Host ('-' * 80)
    foreach ($m in $Machines) {
        $ep = Get-Endpoint $m.User
        $endpoint = if ($ep) { "$($ep.Host):$($ep.Port)" } else { ':' }
        $online   = if ($ep) { Test-Port $ep.Host $ep.Port } else { $false }
        Write-Host ('{0,-8} {1,-18} {2,-24} ' -f $m.Name, $m.User, $endpoint) -NoNewline
        if ($online) { Write-Host ('{0,-10}' -f 'ONLINE')  -ForegroundColor Green -NoNewline }
        else         { Write-Host ('{0,-10}' -f 'OFFLINE') -ForegroundColor Red   -NoNewline }
        Write-Host (' {0,-16}' -f $m.Role)
    }
    Pause-Menu
}

function Invoke-Refresh {
    Clear-Host
    Write-Host '============================================================' -ForegroundColor Blue
    Write-Host '        REFRESCAR PUERTOS NGROK -> BACKEND'                    -ForegroundColor Blue
    Write-Host '============================================================' -ForegroundColor Blue
    Write-Host ''
    $refresh = Join-Path $SelfDir 'neusi-refresh.ps1'
    if (Test-Path $refresh) {
        & $refresh
    } else {
        Write-Host "No encontre 'neusi-refresh.ps1' en $SelfDir." -ForegroundColor Red
    }
    Pause-Menu
}

# Selector de maquina reutilizable para subir/descargar. Devuelve el objeto maquina o $null.
function Select-Machine([string]$Verbo) {
    Write-Host "Elige la maquina de $Verbo:"
    for ($i = 0; $i -lt $Machines.Count; $i++) {
        $m = $Machines[$i]
        Write-Host ("{0}. Maquina {1,-4} - {2,-13} ({3})" -f ($i + 1), $m.Name, $m.Role, $m.User)
    }
    Write-Host '0. Cancelar'
    Write-Host ''
    $sel = Read-Host 'Maquina'
    if ($sel -eq '0' -or [string]::IsNullOrWhiteSpace($sel)) { return $null }
    $idx = 0
    if ([int]::TryParse($sel, [ref]$idx) -and $idx -ge 1 -and $idx -le $Machines.Count) {
        return $Machines[$idx - 1]
    }
    Write-Host 'Opcion invalida.' -ForegroundColor Red
    Start-Sleep -Seconds 1
    return $null
}

function Upload-File {
    if (-not (Require-Ssh)) { Pause-Menu; return }
    Load-Servers
    Clear-Host
    Write-Host '============================================================' -ForegroundColor Blue
    Write-Host '                 SUBIR ARCHIVO A UNA MAQUINA'                  -ForegroundColor Blue
    Write-Host '============================================================' -ForegroundColor Blue
    Write-Host ''
    $m = Select-Machine 'destino'
    if (-not $m) { return }
    $ep = Get-Endpoint $m.User
    if (-not $ep -or -not $ep.Host -or -not $ep.Port) {
        Write-Host "No hay endpoint para '$($m.User)'." -ForegroundColor Red; Pause-Menu; return
    }

    Write-Host ''
    $src = (Read-Host 'Ruta de origen (archivo local)').Trim('"')
    if (-not (Test-Path $src)) {
        Write-Host "No existe el archivo/carpeta de origen: $src" -ForegroundColor Red; Pause-Menu; return
    }
    $dst = Read-Host "Ruta de destino en Maquina $($m.Name) (ej: /home/$($m.User)/ )"
    if ([string]::IsNullOrWhiteSpace($dst)) { $dst = '.' }

    $scpArgs = @('-P', "$($ep.Port)")
    if ((Get-Item $src).PSIsContainer) { $scpArgs += '-r' }
    $scpArgs += @($src, "$($m.User)@$($ep.Host):$dst")

    Write-Host ''
    Write-Host "Origen:  $src"                                       -ForegroundColor Cyan
    Write-Host "Destino: $($m.User)@$($ep.Host):$dst (puerto $($ep.Port))" -ForegroundColor Cyan
    Write-Host ''
    Write-Host 'Subiendo...' -ForegroundColor Yellow
    & scp.exe @scpArgs
    if ($LASTEXITCODE -eq 0) { Write-Host 'Archivo subido correctamente.' -ForegroundColor Green }
    else                     { Write-Host 'Fallo la subida del archivo.'  -ForegroundColor Red }
    Pause-Menu
}

function Download-File {
    if (-not (Require-Ssh)) { Pause-Menu; return }
    Load-Servers
    Clear-Host
    Write-Host '============================================================' -ForegroundColor Blue
    Write-Host '              DESCARGAR ARCHIVO DE UNA MAQUINA'                -ForegroundColor Blue
    Write-Host '============================================================' -ForegroundColor Blue
    Write-Host ''
    $m = Select-Machine 'origen'
    if (-not $m) { return }
    $ep = Get-Endpoint $m.User
    if (-not $ep -or -not $ep.Host -or -not $ep.Port) {
        Write-Host "No hay endpoint para '$($m.User)'." -ForegroundColor Red; Pause-Menu; return
    }

    Write-Host ''
    $src = Read-Host "Ruta de origen en Maquina $($m.Name) (archivo remoto)"
    if ([string]::IsNullOrWhiteSpace($src)) {
        Write-Host 'Debes indicar la ruta del archivo remoto.' -ForegroundColor Red; Pause-Menu; return
    }
    $dst = (Read-Host 'Ruta de destino local (carpeta, ej: $HOME\Downloads\ )').Trim('"')
    if ([string]::IsNullOrWhiteSpace($dst)) { $dst = '.' }

    Write-Host ''
    Write-Host "Origen:  $($m.User)@$($ep.Host):$src (puerto $($ep.Port))" -ForegroundColor Cyan
    Write-Host "Destino: $dst"                                             -ForegroundColor Cyan
    Write-Host ''
    Write-Host 'Descargando...' -ForegroundColor Yellow
    & scp.exe -r -P "$($ep.Port)" "$($m.User)@$($ep.Host):$src" $dst
    if ($LASTEXITCODE -eq 0) { Write-Host 'Archivo descargado correctamente.' -ForegroundColor Green }
    else                     { Write-Host 'Fallo la descarga del archivo.'    -ForegroundColor Red }
    Pause-Menu
}

function Open-Dashboard {
    Clear-Host
    Write-Host "Abriendo dashboard web: $DashboardUrl" -ForegroundColor Cyan
    try { Start-Process $DashboardUrl } catch {
        Write-Host "Abrelo manualmente en tu navegador: $DashboardUrl" -ForegroundColor Yellow
    }
    Start-Sleep -Seconds 1
}

# ---------------- Bucle principal del menu ----------------
while ($true) {
    Load-Servers
    Clear-Host
    Write-Host '============================================================' -ForegroundColor Blue
    Write-Host '                    NEUSI OPERATIONS CLI'                      -ForegroundColor Blue
    Write-Host '============================================================' -ForegroundColor Blue
    Write-Host "Endpoints: $($script:Source)"
    Write-Host ''
    Write-Host '1. Maquina 10  - Produccion      (produccion)'
    Write-Host '2. Maquina 12  - Desarrollo      (desarrollo)'
    Write-Host '3. Maquina 11  - Testing         (pruebas)'
    Write-Host '4. Maquina 13  - Simulador       (simulador1)'
    Write-Host '5. Maquina 14  - Nodo auxiliar   (camposjulca)'
    Write-Host '6. Maquina 105 - Nodo auxiliar   (cristhiamdaniel)'
    Write-Host '7. Ver infraestructura'
    Write-Host '8. Refrescar puertos (auto: produccion + auxiliares desde pruebas)'
    Write-Host '9. Abrir dashboard web'
    Write-Host '10. Subir archivo a una maquina'
    Write-Host '11. Descargar archivo de una maquina'
    Write-Host '0. Salir'
    Write-Host ''
    $option = Read-Host 'Seleccione una opcion'

    switch ($option) {
        '1'  { Connect-Ssh 'Maquina 10'  'produccion' }
        '2'  { Connect-Ssh 'Maquina 12'  'desarrollo' }
        '3'  { Connect-Ssh 'Maquina 11'  'pruebas' }
        '4'  { Connect-Ssh 'Maquina 13'  'simulador1' }
        '5'  { Connect-Ssh 'Maquina 14'  'camposjulca' }
        '6'  { Connect-Ssh 'Maquina 105' 'cristhiamdaniel' }
        '7'  { Show-Infra }
        '8'  { Invoke-Refresh }
        '9'  { Open-Dashboard }
        '10' { Upload-File }
        '11' { Download-File }
        '0'  { Clear-Host; exit 0 }
        default { Write-Host 'Opcion invalida.' -ForegroundColor Red; Start-Sleep -Seconds 1 }
    }
}
