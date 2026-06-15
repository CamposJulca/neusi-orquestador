<#
  neusi-refresh.ps1 — actualiza en el backend del monitor los puertos ngrok
  actuales (version PowerShell de cli/neusi-refresh). NO requiere agentes en los nodos.

  Modo AUTO (sin argumentos):
    1) Entra a produccion por SSH (llave, via ngrok), lee su API local de ngrok
       (127.0.0.1:4040) y actualiza produccion (.10), desarrollo (.12), pruebas (.11).
    2) Con el endpoint de pruebas recien obtenido, entra por SSH a pruebas y
       actualiza los auxiliares: simulador1 (.103), camposjulca (.104), cristhiamdaniel (.105).

  Modo MANUAL:
    .\neusi-refresh.ps1 <code> <host> <port>
    Ej: .\neusi-refresh.ps1 103 6.tcp.ngrok.io 28249

  Config (variables de entorno con defaults):
    NEUSI_MONITOR_URL   backend del monitor    (default http://localhost:8070)
    NEUSI_ENV_FILE      .env con REGISTER_TOKEN (default <repo>\backend\.env)
    REGISTER_TOKEN      token; si no esta, se lee del .env
    PROD_SSH_USER/HOST/PORT  acceso SSH a produccion (defaults produccion@4.tcp.ngrok.io:12385)
    PRUEBAS_SSH_USER         usuario SSH de pruebas (default pruebas)

  Requiere ssh.exe (cliente OpenSSH de Windows 10 1809+).
#>

param(
    [string]$Code,
    [string]$TargetHost,
    [int]$Port
)

$ErrorActionPreference = 'Stop'
$SelfDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$MonitorUrl    = if ($env:NEUSI_MONITOR_URL) { $env:NEUSI_MONITOR_URL } else { 'http://localhost:8070' }
$EnvFile       = if ($env:NEUSI_ENV_FILE)    { $env:NEUSI_ENV_FILE }    else { Join-Path $SelfDir '..\backend\.env' }
$ProdSshUser   = if ($env:PROD_SSH_USER)     { $env:PROD_SSH_USER }     else { 'produccion' }
$ProdSshHost   = if ($env:PROD_SSH_HOST)     { $env:PROD_SSH_HOST }     else { '4.tcp.ngrok.io' }
$ProdSshPort   = if ($env:PROD_SSH_PORT)     { $env:PROD_SSH_PORT }     else { '12385' }
$PruebasSshUser = if ($env:PRUEBAS_SSH_USER) { $env:PRUEBAS_SSH_USER }  else { 'pruebas' }

# octeto interno -> code del backend
$Ip2Code = @{ '10' = '100'; '12' = '101'; '11' = '102'; '13' = '103'; '14' = '104'; '105' = '105' }
# code -> etiqueta legible
$Label = @{
    '100' = 'produccion'; '101' = 'desarrollo'; '102' = 'pruebas'
    '103' = 'simulador1'; '104' = 'camposjulca'; '105' = 'cristhiamdaniel'
}
$AuxCodes = @('103', '104', '105')

if (-not (Get-Command ssh.exe -ErrorAction SilentlyContinue)) {
    Write-Host 'No encontre ssh.exe. Instala el cliente OpenSSH:' -ForegroundColor Red
    Write-Host '  Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0' -ForegroundColor Yellow
    exit 1
}

# Token de registro: variable de entorno o linea REGISTER_TOKEN= del .env
$RegisterToken = $env:REGISTER_TOKEN
if (-not $RegisterToken -and (Test-Path $EnvFile)) {
    $line = Select-String -Path $EnvFile -Pattern '^REGISTER_TOKEN=' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($line) { $RegisterToken = ($line.Line -split '=', 2)[1].Trim() }
}
if (-not $RegisterToken) {
    Write-Host "No encontre REGISTER_TOKEN (revisa $EnvFile o define `$env:REGISTER_TOKEN)." -ForegroundColor Red
    exit 1
}

function Register-Node([string]$NodeCode, [string]$NodeHost, [int]$NodePort) {
    $body = @{ code = $NodeCode; host = $NodeHost; ssh_port = $NodePort } | ConvertTo-Json -Compress
    $lbl  = if ($Label[$NodeCode]) { $Label[$NodeCode] } else { '?' }
    try {
        Invoke-RestMethod -Uri "$MonitorUrl/api/servers/register" -Method Post `
            -Headers @{ 'X-Register-Token' = $RegisterToken } `
            -ContentType 'application/json' -Body $body -TimeoutSec 8 -ErrorAction Stop | Out-Null
        Write-Host ("  OK   {0,-16} code={1,-4} -> {2}:{3}" -f $lbl, $NodeCode, $NodeHost, $NodePort) -ForegroundColor Green
        return $true
    } catch {
        Write-Host ("  FALLO {0,-16} code={1,-4} ({2})" -f $lbl, $NodeCode, $_.Exception.Message) -ForegroundColor Red
        return $false
    }
}

# Resuelve el code: primero por nombre ssh-<code>, luego por octeto.
function Resolve-Code([string]$Name, [string]$Octet) {
    if ($Name -match '^ssh-([0-9]+)$' -and $Label.ContainsKey($Matches[1])) { return $Matches[1] }
    if ($Ip2Code.ContainsKey($Octet)) { return $Ip2Code[$Octet] }
    return $null
}

# Lee la API de ngrok de un nodo por SSH. Devuelve filas @{ Name; Octet; Host; Port }.
function Get-NgrokRows([string]$User, [string]$NodeHost, [string]$NodePort) {
    $json = & ssh.exe -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=10 `
                -p $NodePort "$User@$NodeHost" `
                'curl -s --max-time 5 http://127.0.0.1:4040/api/tunnels' 2>$null
    if (-not $json) { return @() }
    try { $data = ($json -join "`n") | ConvertFrom-Json } catch { return @() }

    $rows = @()
    foreach ($t in $data.tunnels) {
        if ($t.proto -ne 'tcp') { continue }
        $addr = $t.config.addr
        $pub  = $t.public_url
        if ($addr -match '(\d+):22$' -and $pub -match '^tcp://([^:]+):(\d+)') {
            $octet = ([regex]::Match($addr, '(\d+):22$')).Groups[1].Value
            $rows += [pscustomobject]@{
                Name  = $t.name
                Octet = $octet
                Host  = $Matches[1]
                Port  = [int]$Matches[2]
            }
        }
    }
    return $rows
}

# ---------- Modo MANUAL ----------
if ($Code -and $TargetHost -and $Port) {
    Write-Host 'Refresco manual:' -ForegroundColor Cyan
    if (Register-Node $Code $TargetHost $Port) { exit 0 } else { exit 1 }
} elseif ($Code -or $TargetHost -or $Port) {
    Write-Host 'Uso:' -ForegroundColor Yellow
    Write-Host '  .\neusi-refresh.ps1                       (auto: produccion + auxiliares desde pruebas)'
    Write-Host '  .\neusi-refresh.ps1 <code> <host> <port>  (manual: un nodo puntual)'
    exit 1
}

# ---------- AUTO: pasada 1, principales desde produccion ----------
$rc = 0
$done = @{}
$pruebasHost = $null; $pruebasPort = $null

Write-Host "Leyendo ngrok de produccion ($ProdSshUser@$ProdSshHost`:$ProdSshPort)..." -ForegroundColor Cyan
$rows = Get-NgrokRows $ProdSshUser $ProdSshHost $ProdSshPort
if ($rows.Count -eq 0) {
    Write-Host 'No pude leer la API de ngrok en produccion (SSH por llave OK? ngrok corriendo?).' -ForegroundColor Red
    exit 1
}

Write-Host "Actualizando backend ($MonitorUrl):" -ForegroundColor Cyan
foreach ($r in $rows) {
    if (-not $r.Host) { continue }
    $c = Resolve-Code $r.Name $r.Octet
    if (-not $c) {
        Write-Host ("  SKIP tunel '{0}' (.{1}) no mapeado a ningun code" -f $r.Name, $r.Octet) -ForegroundColor Yellow
        continue
    }
    if (Register-Node $c $r.Host $r.Port) { $done[$c] = $true } else { $rc = 1 }
    if ($c -eq '102') { $pruebasHost = $r.Host; $pruebasPort = $r.Port }
}

# ---------- AUTO: pasada 2, auxiliares desde pruebas ----------
Write-Host ''
function Show-ManualHints {
    Write-Host 'Refresca los auxiliares a mano si rotan:' -ForegroundColor Yellow
    Write-Host '  .\neusi-refresh.ps1 103 <host> <port>   # simulador1'
    Write-Host '  .\neusi-refresh.ps1 104 <host> <port>   # camposjulca'
    Write-Host '  .\neusi-refresh.ps1 105 <host> <port>   # cristhiamdaniel'
}

if (-not $pruebasHost -or -not $pruebasPort) {
    Write-Host 'produccion no expuso el tunel de pruebas (.11): no puedo alcanzar pruebas.' -ForegroundColor Yellow
    Show-ManualHints
    exit $rc
}

Write-Host "Leyendo ngrok de pruebas ($PruebasSshUser@$pruebasHost`:$pruebasPort)..." -ForegroundColor Cyan
$auxRows = Get-NgrokRows $PruebasSshUser $pruebasHost $pruebasPort
if ($auxRows.Count -eq 0) {
    Write-Host 'No pude leer la API de ngrok en pruebas (SSH por llave OK? ngrok corriendo?).' -ForegroundColor Red
    Show-ManualHints
    exit 1
}

Write-Host "Actualizando nodos auxiliares ($MonitorUrl):" -ForegroundColor Cyan
foreach ($r in $auxRows) {
    if (-not $r.Host) { continue }
    $c = Resolve-Code $r.Name $r.Octet
    if (-not $c) { continue }
    if ($done[$c]) { continue }
    if (Register-Node $c $r.Host $r.Port) { $done[$c] = $true } else { $rc = 1 }
}

# Avisa de auxiliares esperados que no aparecieron
$missing = $AuxCodes | Where-Object { -not $done[$_] }
if ($missing.Count -gt 0) {
    Write-Host ''
    Write-Host 'Auxiliares sin tunel en pruebas (refrescalos a mano si deberian estar):' -ForegroundColor Yellow
    foreach ($c in $missing) {
        $lbl = if ($Label[$c]) { $Label[$c] } else { '?' }
        Write-Host ("  .\neusi-refresh.ps1 {0} <host> <port>   # {1}" -f $c, $lbl)
    }
}

exit $rc
