from __future__ import annotations

import logging
import mimetypes
import socket
import shlex
import time
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import paramiko

from app.config import get_settings


logger = logging.getLogger(__name__)


class SSHExecutionError(RuntimeError):
    pass


class SSHService:
    FILE_STREAM_CHUNK_SIZE = 1024 * 256

    def __init__(self) -> None:
        self.settings = get_settings()

    def is_enabled(self) -> bool:
        return self.settings.ssh_enabled and not self.settings.use_mock_data

    def _connect(self, host: str, port: int, username: str | None = None) -> tuple[paramiko.SSHClient, int]:
        started_at = time.perf_counter()
        resolved_username = username or self.settings.ssh_username
        base_connect_kwargs: dict[str, object] = {
            "port": port,
            "username": resolved_username,
            "timeout": self.settings.ssh_timeout_seconds,
            "banner_timeout": self.settings.ssh_timeout_seconds,
            "auth_timeout": self.settings.ssh_timeout_seconds,
            "allow_agent": self.settings.ssh_allow_agent,
            "look_for_keys": self.settings.ssh_look_for_keys,
        }
        auth_variants = self._build_auth_variants(base_connect_kwargs)

        resolved_hosts = self._resolve_host_candidates(host, port)
        last_error: Exception | None = None

        for candidate_host in resolved_hosts:
            for connect_kwargs in auth_variants:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                try:
                    client.connect(hostname=candidate_host, **connect_kwargs)
                    logger.info(
                        "SSH connection success host=%s resolved_host=%s port=%s username=%s auth=%s",
                        host,
                        candidate_host,
                        port,
                        resolved_username,
                        self._auth_label(connect_kwargs),
                    )
                    latency_ms = max(1, int((time.perf_counter() - started_at) * 1000))
                    return client, latency_ms
                except paramiko.AuthenticationException as exc:
                    last_error = exc
                    logger.warning(
                        "SSH authentication failed host=%s resolved_host=%s port=%s username=%s auth=%s",
                        host,
                        candidate_host,
                        port,
                        resolved_username,
                        self._auth_label(connect_kwargs),
                    )
                    client.close()
                    continue
                except socket.timeout as exc:
                    last_error = exc
                    logger.warning(
                        "SSH timeout host=%s resolved_host=%s port=%s username=%s",
                        host,
                        candidate_host,
                        port,
                        resolved_username,
                    )
                    client.close()
                    break
                except OSError as exc:
                    last_error = exc
                    logger.warning(
                        "SSH host unreachable host=%s resolved_host=%s port=%s username=%s error=%s",
                        host,
                        candidate_host,
                        port,
                        resolved_username,
                        exc,
                    )
                    client.close()
                    break
                except Exception as exc:
                    last_error = exc
                    logger.exception(
                        "SSH connection failed host=%s resolved_host=%s port=%s username=%s auth=%s",
                        host,
                        candidate_host,
                        port,
                        resolved_username,
                        self._auth_label(connect_kwargs),
                    )
                    client.close()
                    continue

        if isinstance(last_error, socket.timeout):
            raise SSHExecutionError("SSH timeout") from last_error
        if isinstance(last_error, OSError):
            raise SSHExecutionError("Host unreachable") from last_error
        if last_error is not None:
            raise SSHExecutionError(f"SSH connection failed: {last_error}") from last_error
        raise SSHExecutionError("Host unreachable")

    def _build_auth_variants(self, base_connect_kwargs: dict[str, object]) -> list[dict[str, object]]:
        auth_variants: list[dict[str, object]] = []
        for key_path in self._candidate_private_keys():
            auth_variants.append({
                **base_connect_kwargs,
                "key_filename": key_path,
            })

        auth_variants.append({**base_connect_kwargs})

        if self.settings.ssh_password:
            auth_variants.append({
                **base_connect_kwargs,
                "password": self.settings.ssh_password,
                "allow_agent": False,
                "look_for_keys": False,
            })

        unique_variants: list[dict[str, object]] = []
        seen: set[tuple[tuple[str, str], ...]] = set()
        for variant in auth_variants:
            fingerprint = tuple(sorted((key, str(value)) for key, value in variant.items()))
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            unique_variants.append(variant)
        return unique_variants

    def _candidate_private_keys(self) -> list[str]:
        candidates: list[str] = []
        configured_key = self.settings.ssh_private_key_path
        if configured_key:
            expanded = Path(configured_key).expanduser()
            if expanded.exists():
                candidates.append(str(expanded))

        ssh_dir = Path.home() / ".ssh"
        for key_name in ("id_rsa", "id_ed25519", "id_ecdsa", "id_dsa"):
            candidate = ssh_dir / key_name
            if candidate.exists():
                normalized = str(candidate)
                if normalized not in candidates:
                    candidates.append(normalized)
        return candidates

    @staticmethod
    def _auth_label(connect_kwargs: dict[str, object]) -> str:
        if connect_kwargs.get("key_filename"):
            return "key"
        if connect_kwargs.get("password"):
            return "password"
        if connect_kwargs.get("allow_agent") or connect_kwargs.get("look_for_keys"):
            return "agent"
        return "default"

    def _resolve_host_candidates(self, host: str, port: int) -> list[str]:
        candidates: list[str] = [host]
        last_error: OSError | None = None

        for attempt in range(3):
            try:
                addrinfos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
                for family, socktype, proto, canonname, sockaddr in addrinfos:
                    address = sockaddr[0]
                    if address not in candidates:
                        candidates.append(address)
                if len(candidates) > 1:
                    return candidates[:2]
                return candidates
            except OSError as exc:
                last_error = exc
                logger.warning("SSH DNS resolution failed host=%s port=%s attempt=%s error=%s", host, port, attempt + 1, exc)
                time.sleep(0.35 * (attempt + 1))

        if last_error is not None:
            logger.warning("SSH DNS fallback to raw host host=%s port=%s error=%s", host, port, last_error)
        return candidates

    def _run_command(self, client: paramiko.SSHClient, command: str) -> str:
        try:
            _, stdout, stderr = client.exec_command(command, timeout=self.settings.ssh_timeout_seconds)
            exit_code = stdout.channel.recv_exit_status()
        except Exception as exc:
            raise SSHExecutionError(f"SSH command execution failed: {exc}") from exc

        stdout_text = stdout.read().decode("utf-8", errors="replace").strip()
        stderr_text = stderr.read().decode("utf-8", errors="replace").strip()
        if exit_code != 0:
            message = stderr_text or stdout_text or f"exit code {exit_code}"
            raise SSHExecutionError(f"Remote command failed: {message}")
        return stdout_text

    def _open_sftp(self, host: str, port: int, username: str | None = None) -> tuple[paramiko.SSHClient, paramiko.SFTPClient]:
        client, _ = self._connect(host, port, username=username)
        try:
            sftp = client.open_sftp()
        except Exception as exc:
            client.close()
            raise SSHExecutionError(f"SFTP open failed: {exc}") from exc
        return client, sftp

    def collect_runtime_snapshot(self, host: str, port: int, username: str | None = None) -> dict:
        if not self.is_enabled():
            raise SSHExecutionError("SSH mode is disabled.")

        command = r"""
CPU=$(LC_ALL=C top -bn1 | awk -F',' '/Cpu\(s\)/ {for (i=1; i<=NF; i++) if ($i ~ /id/) {gsub(/[^0-9.]/, "", $i); printf "%.1f", 100 - $i; exit}}')
MEM=$(free -m | awk '/Mem:/ {if ($2>0) printf "%.1f", ($3/$2)*100; else print "0.0"}')
DISK=$(df -P / | awk 'NR==2 {gsub("%","",$5); print $5}')
UPTIME=$(uptime -p 2>/dev/null | sed 's/^up //')
TEMP=$(python3 - <<'PY'
from pathlib import Path
import re
import subprocess

temps = []
try:
    output = subprocess.run(["sensors"], capture_output=True, text=True, timeout=3, check=False).stdout
    for match in re.findall(r'([+-]?\d+(?:\.\d+)?)°C', output):
        temps.append(float(match))
except Exception:
    pass

if not temps:
    for path in Path('/sys/class/thermal').glob('thermal_zone*/temp'):
        try:
            raw = path.read_text(encoding='utf-8').strip()
            value = float(raw)
            temps.append(value / 1000 if value > 500 else value)
        except Exception:
            continue

if temps:
    print(f"{max(temps):.1f}")
PY
)
echo "cpu=${CPU}"
echo "memory=${MEM:-0}"
echo "disk=${DISK:-0}"
echo "uptime=${UPTIME:-No disponible}"
echo "temperature=${TEMP:-}"
echo "__DISKS__"
df -h --output=source,size,used,avail,pcent,target 2>/dev/null | tail -n +2 | awk '$6=="/" || $6=="/home" || $6=="/var" || $6=="/boot" || index($6,"/mnt/")==1 {gsub("%","",$5); print $1 "|" $2 "|" $3 "|" $4 "|" $5 "|" $6}'
echo "__DOCKER__"
docker ps --format '{{.Names}}' 2>/dev/null | head -n 20
echo "__SERVICES__"
systemctl list-units --type=service --state=running --no-legend --no-pager 2>/dev/null | awk '{print $1}' | head -n 200
echo "__PORTS__"
ss -tulnpH 2>/dev/null | awk '{print $1 " " $5}' | head -n 20
echo "__END__"
"""
        client, latency_ms = self._connect(host, port, username=username)
        try:
            output = self._run_command(client, command)
        finally:
            client.close()

        payload = self._parse_runtime_snapshot(output)
        payload["latency"] = latency_ms
        logger.info(
            "SSH metrics collected host=%s port=%s username=%s latency_ms=%s",
            host,
            port,
            username or self.settings.ssh_username,
            latency_ms,
        )
        return payload

    def collect_storage_snapshot(
        self,
        host: str,
        port: int,
        mount_path: str,
        username: str | None = None,
    ) -> dict[str, str]:
        if not self.is_enabled():
            raise SSHExecutionError("SSH mode is disabled.")

        quoted_path = shlex.quote(mount_path)
        command = f"""
if mountpoint -q {quoted_path}; then
  echo "mounted=yes"
  df -hP {quoted_path} | awk 'NR==2 {{print "filesystem="$1; print "total="$2; print "used="$3; print "free="$4; gsub("%","",$5); print "usage_percent="$5; print "mounted_on="$6}}'
else
  echo "mounted=no"
fi
"""
        client, _ = self._connect(host, port, username=username)
        try:
            output = self._run_command(client, command)
        finally:
            client.close()
        payload = self._parse_key_value_lines(output)
        logger.info(
            "SSH storage collected host=%s port=%s username=%s mount=%s mounted=%s",
            host,
            port,
            username or self.settings.ssh_username,
            mount_path,
            payload.get("mounted"),
        )
        return {key: str(value) for key, value in payload.items()}

    def collect_file_summary(self, host: str, port: int, username: str | None = None) -> dict:
        if not self.is_enabled():
            raise SSHExecutionError("SSH mode is disabled.")

        quoted_paths = " ".join(shlex.quote(path) for path in self.settings.monitored_file_paths)
        command = f"""
TOTAL=0
FOUND=""
for path in {quoted_paths}; do
  if [ -d "$path" ]; then
    COUNT=$(find "$path" -maxdepth {self.settings.file_scan_max_depth} -type f 2>/dev/null | wc -l | tr -d ' ')
    TOTAL=$((TOTAL + COUNT))
    if [ -z "$FOUND" ]; then
      FOUND="$path"
    else
      FOUND="$FOUND|$path"
    fi
  fi
done
echo "indexed_paths=$FOUND"
echo "total_files=$TOTAL"
"""
        client, _ = self._connect(host, port, username=username)
        try:
            output = self._run_command(client, command)
        finally:
            client.close()
        return self._parse_key_value_lines(output)

    def collect_project_summary(self, host: str, port: int, username: str | None = None) -> dict:
        if not self.is_enabled():
            raise SSHExecutionError("SSH mode is disabled.")

        quoted_paths = " ".join(shlex.quote(path) for path in self.settings.monitored_project_paths)
        command = f"""
for path in {quoted_paths}; do
  if [ -d "$path" ]; then
    find "$path" -maxdepth {self.settings.project_scan_max_depth} \\( -name .git -o -name package.json -o -name pyproject.toml -o -name requirements.txt -o -name Dockerfile -o -name docker-compose.yml \\) -printf '%h|%f\n' 2>/dev/null
  fi
done | sort -u | head -n 200
"""
        client, _ = self._connect(host, port, username=username)
        try:
            output = self._run_command(client, command)
        finally:
            client.close()
        return {"project_markers": output.splitlines() if output else []}

    def run_remote_command(self, host: str, port: int, command: str, username: str | None = None) -> str:
        if not self.is_enabled():
            raise SSHExecutionError("SSH mode is disabled.")

        client, _ = self._connect(host, port, username=username)
        try:
            return self._run_command(client, command)
        finally:
            client.close()

    def collect_file_tree(self, host: str, port: int, base_path: str, depth: int, username: str | None = None) -> list[str]:
        if not self.is_enabled():
            raise SSHExecutionError("SSH mode is disabled.")

        quoted_path = shlex.quote(base_path)
        ignored_names = " -o ".join(
            f"-name {shlex.quote(name)}" for name in [
                "node_modules",
                "venv",
                ".venv",
                ".git",
                "__pycache__",
                "dist",
                "build",
                ".cache",
                ".env",
            ]
        )
        command = f"""
if [ ! -d {quoted_path} ]; then
  echo "__MISSING__"
  exit 0
fi
find {quoted_path} \\
  \\( {ignored_names} \\) -prune -o \\
  -mindepth 1 -maxdepth {depth} -printf '%p|%y|%s|%TY-%Tm-%Td %TH:%TM\\n' 2>/dev/null || true
"""
        client, _ = self._connect(host, port, username=username)
        try:
            output = self._run_command(client, command)
        finally:
            client.close()

        if output.strip() == "__MISSING__":
            raise SSHExecutionError("Remote path not found")
        return output.splitlines() if output else []

    def read_remote_file_metadata(self, host: str, port: int, path: str, username: str | None = None) -> dict[str, str]:
        client, sftp = self._open_sftp(host, port, username=username)
        try:
            stat = sftp.stat(path)
        except FileNotFoundError as exc:
            raise SSHExecutionError("Remote file not found") from exc
        finally:
            try:
                sftp.close()
            finally:
                client.close()

        mime_type, _ = mimetypes.guess_type(path)
        return {
            "type": "file",
            "mime_type": mime_type or "application/octet-stream",
            "size": self._format_size(stat.st_size),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
        }

    def read_remote_text_preview(
        self,
        host: str,
        port: int,
        path: str,
        limit: int,
        username: str | None = None,
    ) -> str:
        client, sftp = self._open_sftp(host, port, username=username)
        try:
            with sftp.open(path, "r") as remote_file:
                data = remote_file.read(limit)
        except Exception as exc:
            raise SSHExecutionError(f"Remote file read failed: {exc}") from exc
        finally:
            try:
                sftp.close()
            finally:
                client.close()
        return data.decode("utf-8", errors="replace")

    def read_remote_file_bytes(self, host: str, port: int, path: str, username: str | None = None) -> tuple[bytes, str]:
        client, sftp = self._open_sftp(host, port, username=username)
        try:
            with sftp.open(path, "rb") as remote_file:
                data = remote_file.read()
        except Exception as exc:
            raise SSHExecutionError(f"Remote file read failed: {exc}") from exc
        finally:
            try:
                sftp.close()
            finally:
                client.close()

        mime_type, _ = mimetypes.guess_type(path)
        return data, mime_type or "application/octet-stream"

    def stream_remote_file(
        self,
        host: str,
        port: int,
        path: str,
        username: str | None = None,
        chunk_size: int | None = None,
    ) -> tuple[Iterator[bytes], str]:
        client, sftp = self._open_sftp(host, port, username=username)
        resolved_chunk_size = chunk_size or self.FILE_STREAM_CHUNK_SIZE
        mime_type, _ = mimetypes.guess_type(path)

        try:
            remote_file = sftp.open(path, "rb")
        except Exception as exc:
            try:
                sftp.close()
            finally:
                client.close()
            raise SSHExecutionError(f"Remote file read failed: {exc}") from exc

        def iterator() -> Iterator[bytes]:
            try:
                while True:
                    chunk = remote_file.read(resolved_chunk_size)
                    if not chunk:
                        break
                    yield chunk
            except Exception as exc:
                raise SSHExecutionError(f"Remote file stream failed: {exc}") from exc
            finally:
                try:
                    remote_file.close()
                finally:
                    try:
                        sftp.close()
                    finally:
                        client.close()

        return iterator(), mime_type or "application/octet-stream"

    @staticmethod
    def _parse_key_value_lines(output: str) -> dict[str, str | int]:
        payload: dict[str, str | int] = {}
        for line in output.splitlines():
            if "=" not in line:
                logger.debug("Ignoring unexpected SSH output line: %s", line)
                continue
            key, value = line.split("=", 1)
            payload[key.strip()] = value.strip()
        return payload

    def _parse_runtime_snapshot(self, output: str) -> dict[str, object]:
        sections = {"disks": [], "docker": [], "services": [], "ports": []}
        payload: dict[str, object] = {}
        section: str | None = None

        for line in output.splitlines():
            stripped = line.strip()
            if stripped == "__DISKS__":
                section = "disks"
                continue
            if stripped == "__DOCKER__":
                section = "docker"
                continue
            if stripped == "__SERVICES__":
                section = "services"
                continue
            if stripped == "__PORTS__":
                section = "ports"
                continue
            if stripped == "__END__":
                section = None
                continue
            if section:
                if stripped:
                    sections[section].append(stripped)
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                payload[key.strip()] = value.strip()

        disks: list[dict[str, object]] = []
        for line in sections["disks"]:
            disk = self._parse_disk_line(line)
            if disk:
                disks.append(disk)

        payload["disks"] = disks
        payload["docker_containers"] = sections["docker"]
        payload["running_services"] = sections["services"]
        payload["open_ports"] = sections["ports"]
        return payload

    @staticmethod
    def _parse_disk_line(line: str) -> dict[str, object] | None:
        parts = line.split("|")
        if len(parts) != 6:
            logger.debug("Ignoring unexpected disk line: %s", line)
            return None

        filesystem, size, used, available, usage_percent, mount = (part.strip() for part in parts)
        try:
            usage_value = float(usage_percent)
        except ValueError:
            logger.debug("Ignoring disk line with invalid usage: %s", line)
            return None

        return {
            "filesystem": filesystem,
            "size": size,
            "used": used,
            "available": available,
            "usage_percent": usage_value,
            "mount": mount,
        }

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(size_bytes)
        unit_index = 0
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        return f"{size:.1f} {units[unit_index]}"
