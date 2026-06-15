@echo off
REM ============================================================
REM  neusi-cliente.cmd — Lanzador del orquestador para Windows
REM ============================================================
REM  Configura el cliente para apuntar a la CENTRAL (backend +
REM  dashboard) y abre el menu neusi.ps1.
REM
REM  Uso:
REM    Doble clic            -> usa la IP por defecto de abajo
REM    neusi-cliente.cmd IP  -> usa otra IP/host de la central
REM      ej: neusi-cliente.cmd 192.168.10.25
REM
REM  Requisitos en Windows: cliente OpenSSH (ssh.exe) y tu llave
REM  privada en %USERPROFILE%\.ssh\id_ed25519.
REM ============================================================

setlocal

REM IP de la central (laptop Linux donde corre el backend). Cambiala
REM si la laptop recibe otra IP por DHCP, o pasala como argumento.
set "CENTRAL=%~1"
if "%CENTRAL%"=="" set "CENTRAL=192.168.10.18"

set "NEUSI_MONITOR_URL=http://%CENTRAL%:8070"
set "NEUSI_DASHBOARD_URL=http://%CENTRAL%:8080"

echo.
echo  Central Neusi: %CENTRAL%
echo  Backend:   %NEUSI_MONITOR_URL%
echo  Dashboard: %NEUSI_DASHBOARD_URL%
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0neusi.ps1"

endlocal
