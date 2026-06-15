import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  captureObservabilitySnapshot,
  fetchDuplicateFiles,
  fetchObservabilityHistory,
  fetchObservabilityOverview,
  fetchObservabilitySnapshots,
  searchObservabilityFiles,
} from '../services/api';

function TinyChart({ points, metric, color, label }) {
  const values = points.map((point) => Number(point[metric] || 0));
  const isLatency = metric === 'latency_ms';
  const unit = isLatency ? ' ms' : '%';
  const max = isLatency ? Math.max(...values, 1) : Math.max(100, ...values, 1);
  const width = 320;
  const height = 120;
  const pad = 8;
  const step = values.length > 1 ? width / (values.length - 1) : width;
  const coords = values.map((value, index) => {
    const x = index * step;
    const y = height - (value / max) * (height - pad * 2) - pad;
    return [x, y];
  });
  const line = coords
    .map(([x, y], index) => `${index === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`)
    .join(' ');
  const area = coords.length
    ? `${line} L ${coords.at(-1)[0].toFixed(1)} ${height} L 0 ${height} Z`
    : '';
  const [lastX, lastY] = coords.at(-1) || [0, height];
  const latest = values.at(-1) ?? 0;
  const peak = values.length ? Math.max(...values) : 0;
  const low = values.length ? Math.min(...values) : 0;
  const avg = values.length ? values.reduce((acc, v) => acc + v, 0) / values.length : 0;
  const gridLines = [0.25, 0.5, 0.75];
  const gradId = `obs-grad-${metric}`;

  return (
    <article className="observability-mini-chart" style={{ '--chart-color': color }}>
      <div className="observability-mini-chart__header">
        <span>{label}</span>
        <strong>{Math.round(latest)}{unit}</strong>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.35" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        {gridLines.map((ratio) => (
          <path
            key={ratio}
            d={`M 0 ${(height * ratio).toFixed(1)} L ${width} ${(height * ratio).toFixed(1)}`}
            className="observability-mini-chart__grid"
          />
        ))}
        <path d={`M 0 ${height - 1} L ${width} ${height - 1}`} className="observability-mini-chart__axis" />
        {area ? <path d={area} className="observability-mini-chart__area" style={{ fill: `url(#${gradId})` }} /> : null}
        {line ? <path d={line} className="observability-mini-chart__line" /> : null}
        {coords.length ? <circle cx={lastX} cy={lastY} r="4" className="observability-mini-chart__dot" /> : null}
      </svg>
      <div className="observability-mini-chart__footer">
        <span>min {Math.round(low)}{unit}</span>
        <span>prom {Math.round(avg)}{unit}</span>
        <span>max {Math.round(peak)}{unit}</span>
      </div>
    </article>
  );
}

function StatusDot({ tone }) {
  return <span className={`obs-dot is-${tone}`} aria-hidden="true" />;
}

function PanelHeader({ eyebrow, title, badge, badgeTone = 'neutral' }) {
  return (
    <div className="explorer-panel__header">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
      </div>
      {badge ? <span className={`obs-count is-${badgeTone}`}>{badge}</span> : null}
    </div>
  );
}

function formatDate(value) {
  return new Date(value).toLocaleString('es-CO', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function statusTone(status) {
  if (status === 'critical' || status === 'offline') return 'critical';
  if (status === 'warning') return 'warning';
  return 'healthy';
}

function serviceTone(service) {
  const state = (service.active_state || '').toLowerCase();
  if (state === 'failed') return 'critical';
  if (state === 'active') return 'healthy';
  if (state === 'activating' || state === 'reloading' || state === 'deactivating') return 'warning';
  return 'neutral';
}

function dockerTone(status) {
  const value = (status || '').toLowerCase();
  if (value.includes('restart')) return 'warning';
  if (value.includes('exit') || value.includes('dead') || value.includes('paused')) return 'critical';
  if (value.includes('up') || value.includes('running')) return 'healthy';
  return 'neutral';
}

function ObservabilitySkeleton() {
  return (
    <main className="page">
      <div className="obs-skeleton obs-skeleton--heading" />
      <section className="observability-summary-grid">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="obs-skeleton obs-skeleton--card" />
        ))}
      </section>
      <section className="observability-charts-grid">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="obs-skeleton obs-skeleton--chart" />
        ))}
      </section>
    </main>
  );
}

export default function ObservabilityPage({ servers }) {
  const queryClient = useQueryClient();
  const [serverId, setServerId] = useState(servers[0]?.code || '100');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchPath, setSearchPath] = useState('/home');
  const [submittedQuery, setSubmittedQuery] = useState('');
  const [duplicatePath, setDuplicatePath] = useState('/home');

  const overviewQuery = useQuery({
    queryKey: ['observability-overview', serverId],
    queryFn: () => fetchObservabilityOverview(serverId),
    refetchInterval: 45000,
  });

  const historyQuery = useQuery({
    queryKey: ['observability-history', serverId],
    queryFn: () => fetchObservabilityHistory(serverId, 72),
    refetchInterval: 60000,
  });

  const snapshotsQuery = useQuery({
    queryKey: ['observability-snapshots', serverId],
    queryFn: () => fetchObservabilitySnapshots(serverId, 12),
  });

  const searchQueryState = useQuery({
    queryKey: ['observability-search', serverId, submittedQuery, searchPath],
    queryFn: () => searchObservabilityFiles(serverId, submittedQuery, searchPath),
    enabled: submittedQuery.trim().length > 0,
  });

  const duplicatesQuery = useQuery({
    queryKey: ['observability-duplicates', serverId, duplicatePath],
    queryFn: () => fetchDuplicateFiles(serverId, duplicatePath),
    enabled: false,
  });

  const snapshotMutation = useMutation({
    mutationFn: () => captureObservabilitySnapshot(serverId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['observability-snapshots', serverId] });
      queryClient.invalidateQueries({ queryKey: ['observability-history', serverId] });
      queryClient.invalidateQueries({ queryKey: ['observability-overview', serverId] });
    },
  });

  const overview = overviewQuery.data;
  const history = historyQuery.data;
  const snapshots = snapshotsQuery.data || [];

  if (overviewQuery.isLoading || historyQuery.isLoading) {
    return <ObservabilitySkeleton />;
  }

  if (overviewQuery.error || historyQuery.error) {
    const message = overviewQuery.error?.message || historyQuery.error?.message || 'No se pudo cargar observabilidad.';
    return <main className="page"><div className="state-panel error">{message}</div></main>;
  }

  const isRefreshing = overviewQuery.isFetching || historyQuery.isFetching;
  const onlineChecks = overview.http_checks.filter((item) => item.status === 'online').length;
  const totalChecks = overview.http_checks.length;
  const checksTone = totalChecks === 0 ? 'neutral' : onlineChecks === totalChecks ? 'healthy' : onlineChecks === 0 ? 'critical' : 'warning';
  const activeServices = overview.service_uptime.filter((service) => serviceTone(service) === 'healthy').length;
  const dbDown = overview.databases.filter((database) => statusTone(database.status) === 'critical').length;

  return (
    <main className="page">
      <section className="section-heading">
        <div>
          <p className="eyebrow">Observabilidad</p>
          <h2>Historico, salud de servicios y snapshots</h2>
        </div>
        <div className="section-heading__actions">
          <label className="observability-select">
            <span>Servidor</span>
            <select value={serverId} onChange={(event) => setServerId(event.target.value)}>
              {servers.map((server) => (
                <option key={server.code} value={server.code}>{server.code} · {server.name}</option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className={`section-action-button${isRefreshing ? ' is-loading' : ''}`}
            onClick={() => {
              overviewQuery.refetch();
              historyQuery.refetch();
              snapshotsQuery.refetch();
            }}
          >
            {isRefreshing ? 'Actualizando…' : 'Refrescar'}
          </button>
          <button
            type="button"
            className="section-download-button"
            onClick={() => snapshotMutation.mutate()}
            disabled={snapshotMutation.isPending}
          >
            {snapshotMutation.isPending ? 'Capturando...' : 'Snapshot manual'}
          </button>
        </div>
      </section>

      <section className="observability-summary-grid">
        <article className={`overview-card obs-summary ${statusTone(overview.health.status)}`}>
          <span className="obs-summary__label"><StatusDot tone={statusTone(overview.health.status)} />Estado general</span>
          <strong>{overview.health.status}</strong>
          <small>{overview.health.status_reasons[0]?.message || 'Sin alertas activas'}</small>
        </article>
        <article className={`overview-card obs-summary ${checksTone === 'healthy' ? 'healthy' : checksTone === 'critical' ? 'critical' : checksTone === 'warning' ? 'warning' : ''}`}>
          <span className="obs-summary__label"><StatusDot tone={checksTone} />Healthchecks HTTP</span>
          <strong>{onlineChecks}/{totalChecks}</strong>
          <small>Checks remotos sobre localhost de cada maquina</small>
        </article>
        <article className="overview-card obs-summary">
          <span className="obs-summary__label"><StatusDot tone={overview.docker_containers.length ? 'healthy' : 'neutral'} />Docker activos</span>
          <strong>{overview.docker_containers.length}</strong>
          <small>{overview.health.docker_count} contenedores reportados por salud</small>
        </article>
        <article className="overview-card obs-summary">
          <span className="obs-summary__label"><StatusDot tone={overview.latest_snapshot ? 'healthy' : 'neutral'} />Ultimo snapshot</span>
          <strong className="obs-summary__date">{overview.latest_snapshot ? formatDate(overview.latest_snapshot.created_at) : 'Sin datos'}</strong>
          <small>{snapshots.length} snapshots recientes cargados</small>
        </article>
      </section>

      <section className="observability-charts-grid">
        <TinyChart points={history.points} metric="cpu_usage" color="#64d2ff" label="CPU historica" />
        <TinyChart points={history.points} metric="memory_usage" color="#ffcb65" label="Memoria historica" />
        <TinyChart points={history.points} metric="disk_usage" color="#64e5a8" label="Disco historico" />
        <TinyChart points={history.points} metric="latency_ms" color="#ff8f7a" label="Latencia historica" />
      </section>

      <section className="observability-grid">
        <article className="explorer-panel">
          <PanelHeader
            eyebrow="Servicios HTTP"
            title="Healthchecks"
            badge={totalChecks ? `${onlineChecks}/${totalChecks} online` : 'sin checks'}
            badgeTone={checksTone}
          />
          <div className="observability-list">
            {overview.http_checks.map((check) => {
              const tone = statusTone(check.status);
              return (
                <div key={`${check.name}-${check.url}`} className={`observability-list-item is-${tone}`}>
                  <StatusDot tone={tone} />
                  <div className="observability-list-item__body">
                    <div className="observability-list-item__title">
                      <strong>{check.name}</strong>
                      <em className={`obs-tag is-${tone}`}>{check.status}</em>
                    </div>
                    <span>{check.url}</span>
                    <small>{check.status_code || 'sin codigo'} · {check.response_time_ms || 0} ms</small>
                  </div>
                </div>
              );
            })}
            {!overview.http_checks.length ? <div className="explorer-empty">Sin healthchecks configurados.</div> : null}
          </div>
        </article>

        <article className="explorer-panel">
          <PanelHeader
            eyebrow="Servicios del sistema"
            title="Uptime por servicio"
            badge={`${activeServices}/${overview.service_uptime.length} activos`}
            badgeTone={overview.service_uptime.length && activeServices === overview.service_uptime.length ? 'healthy' : activeServices ? 'warning' : 'neutral'}
          />
          <div className="observability-list observability-list--scroll">
            {overview.service_uptime.map((service) => {
              const tone = serviceTone(service);
              return (
                <div key={service.name} className={`observability-list-item is-${tone}`}>
                  <StatusDot tone={tone} />
                  <div className="observability-list-item__body">
                    <div className="observability-list-item__title">
                      <strong>{service.name}</strong>
                      <em className={`obs-tag is-${tone}`}>{service.active_state}</em>
                    </div>
                    <span>{service.sub_state}</span>
                    <small>{service.entered_at || 'Sin timestamp'}</small>
                  </div>
                </div>
              );
            })}
            {!overview.service_uptime.length ? <div className="explorer-empty">Sin servicios reportados.</div> : null}
          </div>
        </article>

        <article className="explorer-panel">
          <PanelHeader
            eyebrow="Contenedores"
            title="Monitoreo Docker"
            badge={`${overview.docker_containers.length} activos`}
            badgeTone={overview.docker_containers.length ? 'healthy' : 'neutral'}
          />
          <div className="observability-list">
            {overview.docker_containers.map((container) => {
              const tone = dockerTone(container.status);
              return (
                <div key={container.name} className={`observability-list-item is-${tone}`}>
                  <StatusDot tone={tone} />
                  <div className="observability-list-item__body">
                    <div className="observability-list-item__title">
                      <strong>{container.name}</strong>
                      <em className={`obs-tag is-${tone}`}>{container.running_for}</em>
                    </div>
                    <span>{container.image}</span>
                    <small>{container.status}</small>
                  </div>
                </div>
              );
            })}
            {!overview.docker_containers.length ? <div className="explorer-empty">Sin contenedores en ejecucion.</div> : null}
          </div>
        </article>

        <article className="explorer-panel">
          <PanelHeader
            eyebrow="Bases de datos"
            title="PostgreSQL y Mongo"
            badge={dbDown ? `${dbDown} con alerta` : `${overview.databases.length} en linea`}
            badgeTone={dbDown ? 'critical' : overview.databases.length ? 'healthy' : 'neutral'}
          />
          <div className="observability-list">
            {overview.databases.map((database) => {
              const tone = statusTone(database.status);
              return (
                <div key={database.engine} className={`observability-list-item is-${tone}`}>
                  <StatusDot tone={tone} />
                  <div className="observability-list-item__body">
                    <div className="observability-list-item__title">
                      <strong>{database.engine}</strong>
                      <em className={`obs-tag is-${tone}`}>{database.status}</em>
                    </div>
                    <span>{database.version || 'Version no detectada'}</span>
                    <small>{database.metric_label || 'estado'}: {database.metric_value || 'n/a'} · {database.message || database.status}</small>
                  </div>
                </div>
              );
            })}
            {!overview.databases.length ? <div className="explorer-empty">Sin motores de base de datos detectados.</div> : null}
          </div>
        </article>
      </section>

      <section className="observability-grid">
        <article className="explorer-panel">
          <PanelHeader eyebrow="Busqueda" title="Busqueda remota de archivos" />
          <form
            className="explorer-controls explorer-controls--library"
            onSubmit={(event) => {
              event.preventDefault();
              setSubmittedQuery(searchQuery);
            }}
          >
            <label>
              <span>Ruta base</span>
              <input value={searchPath} onChange={(event) => setSearchPath(event.target.value)} />
            </label>
            <label>
              <span>Nombre o fragmento</span>
              <input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="ej. docker-compose" />
            </label>
            <button type="submit" className="explorer-refresh">Buscar archivos</button>
          </form>
          {searchQueryState.isFetching ? (
            <div className="explorer-empty">Buscando archivos remotos…</div>
          ) : searchQueryState.data ? (
            <div className="observability-list">
              {searchQueryState.data.results.map((item) => (
                <div key={item.path} className="observability-list-item is-neutral">
                  <StatusDot tone="neutral" />
                  <div className="observability-list-item__body">
                    <strong>{item.path}</strong>
                    <span>{item.size || 'Tamaño desconocido'}</span>
                    <small>{item.modified_at || 'Sin fecha'}</small>
                  </div>
                </div>
              ))}
              {!searchQueryState.data.results.length ? <div className="explorer-empty">{searchQueryState.data.message}</div> : null}
            </div>
          ) : <div className="explorer-empty">Ejecuta una busqueda para inspeccionar archivos remotos.</div>}
        </article>

        <article className="explorer-panel">
          <PanelHeader eyebrow="Integridad" title="Deteccion de duplicados" />
          <form
            className="explorer-controls explorer-controls--library"
            onSubmit={(event) => {
              event.preventDefault();
              duplicatesQuery.refetch();
            }}
          >
            <label>
              <span>Ruta base</span>
              <input value={duplicatePath} onChange={(event) => setDuplicatePath(event.target.value)} />
            </label>
            <button type="submit" className="explorer-refresh">Buscar duplicados</button>
          </form>
          {duplicatesQuery.isFetching ? (
            <div className="explorer-empty">Analizando duplicados…</div>
          ) : duplicatesQuery.data ? (
            <div className="observability-list">
              {duplicatesQuery.data.groups.map((group) => (
                <div key={group.fingerprint} className="observability-list-item is-warning">
                  <StatusDot tone="warning" />
                  <div className="observability-list-item__body">
                    <div className="observability-list-item__title">
                      <strong>{group.size}</strong>
                      <em className="obs-tag is-warning">{group.files.length} archivos</em>
                    </div>
                    <span>{group.fingerprint}</span>
                    <small>{group.files.join(' | ')}</small>
                  </div>
                </div>
              ))}
              {!duplicatesQuery.data.groups.length ? <div className="explorer-empty">{duplicatesQuery.data.message}</div> : null}
            </div>
          ) : <div className="explorer-empty">Ejecuta una deteccion para localizar archivos duplicados.</div>}
        </article>
      </section>

      <section className="explorer-panel">
        <PanelHeader
          eyebrow="Snapshots"
          title="Historial automatizado"
          badge={`${snapshots.length} recientes`}
          badgeTone={snapshots.length ? 'healthy' : 'neutral'}
        />
        <div className="observability-list observability-list--grid">
          {snapshots.map((snapshot) => {
            const tone = statusTone(snapshot.status);
            return (
              <div key={snapshot.id} className={`observability-list-item is-${tone}`}>
                <StatusDot tone={tone} />
                <div className="observability-list-item__body">
                  <div className="observability-list-item__title">
                    <strong>{formatDate(snapshot.created_at)}</strong>
                    <em className={`obs-tag is-${tone}`}>{snapshot.snapshot_type}</em>
                  </div>
                  <small>CPU {Math.round(snapshot.cpu_usage || 0)}% · RAM {Math.round(snapshot.memory_usage || 0)}% · Disco {Math.round(snapshot.disk_usage || 0)}%</small>
                </div>
              </div>
            );
          })}
          {!snapshots.length ? <div className="explorer-empty">Sin snapshots registrados todavia.</div> : null}
        </div>
      </section>
    </main>
  );
}
