import MetricBar from './MetricBar';

function statusLabel(status) {
  if (status === 'offline') return 'No conectado';
  if (status === 'critical') return 'Critical';
  if (status === 'warning') return 'Warning';
  return 'Online';
}

function formatCheckedAt(checkedAt) {
  return new Date(checkedAt).toLocaleTimeString('es-CO', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatDiskPercent(usagePercent) {
  return `${Math.round(usagePercent)}%`;
}

function formatReasonValue(reason) {
  return `${Math.round(reason.value)}%`;
}

export default function ServerCard({ item }) {
  const { server, health, files, projects } = item;
  const isOffline = health.connection_status === 'offline';

  return (
    <article className={`server-card ${health.status}`}>
      <header className="server-card__header">
        <div>
          <p className="eyebrow">{server.role || server.environment}</p>
          <h2>{server.name}</h2>
          <p className="server-host">
            {server.real_ip} · {server.host}:{server.ssh_port} · {server.ssh_username}
          </p>
          {health.status_reasons.length ? (
            <ul className="server-card__status-reasons">
              {health.status_reasons.map((reason, index) => (
                <li key={`${server.code}-${reason.metric}-${reason.target}-${index}`}>
                  <strong>{reason.target}</strong>
                  <span>{formatReasonValue(reason)} · {reason.message}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        <span className={`status-pill ${health.status}`}>{statusLabel(health.status)}</span>
      </header>

      {isOffline ? (
        <section className="offline-banner">
          <strong>● No conectado</strong>
          <span>{health.last_error || 'No fue posible establecer conexion SSH.'}</span>
        </section>
      ) : null}

      <section className="metric-grid">
        <MetricBar label="CPU" value={health.cpu_usage} tone={health.status} />
        <MetricBar label="Memoria" value={health.memory_usage} tone={health.status} />
        <MetricBar label="Disco (/)" value={health.disk_usage} tone={health.status} />
      </section>

      <section className="server-card__stats">
        <div>
          <span>Estado SSH</span>
          <strong>{health.connection_message}</strong>
        </div>
        <div>
          <span>Latencia</span>
          <strong>{health.latency_label}</strong>
        </div>
        <div>
          <span>Uptime</span>
          <strong>{health.uptime}</strong>
        </div>
        <div>
          <span>Temperatura</span>
          <strong>{health.temperature_label}</strong>
        </div>
        <div>
          <span>Docker</span>
          <strong>{health.docker_count} contenedores</strong>
        </div>
      </section>

      {health.disks.length ? (
        <section className="server-card__disks">
          <div className="server-card__disks-header">
            <h3>Particiones</h3>
            <span>{health.disks.length} monitoreadas</span>
          </div>
          <ul className="server-card__disk-list">
            {health.disks.map((disk) => (
              <li key={`${server.code}-${disk.mount}`}>
                <div>
                  <strong>{disk.mount}</strong>
                  <span>{disk.filesystem}</span>
                </div>
                <div>
                  <strong>{formatDiskPercent(disk.usage_percent)}</strong>
                  <span>{disk.used} / {disk.size}</span>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {health.storage ? (
        <section className="server-card__stats">
          <div>
            <span>Storage</span>
            <strong>{health.storage.mounted ? 'Montado' : 'No montado'}</strong>
          </div>
          <div>
            <span>Uso</span>
            <strong>{health.storage.usage_label}</strong>
          </div>
          <div>
            <span>Capacidad</span>
            <strong>{health.storage.total || 'No disponible'}</strong>
          </div>
          <div>
            <span>Libre</span>
            <strong>{health.storage.free || 'No disponible'}</strong>
          </div>
        </section>
      ) : null}

      <section className="server-card__list">
        <div>
          <h3>Servicios</h3>
          {health.running_services.length ? (
            <div className="chip-group">
              {health.running_services.map((service) => (
                <span key={service} className="obs-tag is-healthy">{service}</span>
              ))}
            </div>
          ) : <ul><li>No conectado</li></ul>}
        </div>
        <div>
          <h3>Puertos</h3>
          {health.open_ports.length ? (
            <div className="chip-group">
              {health.open_ports.map((port) => (
                <span key={port} className="obs-tag is-neutral">{port}</span>
              ))}
            </div>
          ) : <ul><li>No conectado</li></ul>}
        </div>
      </section>

      <section className="server-card__list">
        <div>
          <h3>Rutas indexadas</h3>
          <ul>
            {files.indexed_paths.length ? files.indexed_paths.map((path) => (
              <li key={path}>{path}</li>
            )) : <li>No conectado</li>}
          </ul>
        </div>
        <div>
          <h3>Proyectos detectados</h3>
          <ul>
            {projects.projects.length ? projects.projects.map((project) => (
              <li key={project}>{project}</li>
            )) : <li>No conectado</li>}
          </ul>
        </div>
      </section>

      <footer className="server-card__footer">
        <span>Stacks: {projects.detected_stacks.length ? projects.detected_stacks.join(' / ') : 'No disponible'}</span>
        <span>Ultimo intento: {formatCheckedAt(health.checked_at)}</span>
        <span>Fuente: {health.source}</span>
      </footer>
    </article>
  );
}
