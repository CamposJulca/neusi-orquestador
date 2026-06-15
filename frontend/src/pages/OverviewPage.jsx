import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { fetchDashboardSummary } from '../services/api';

function formatLastCheck(summary) {
  const checkedAt = summary
    .map((item) => item.health.checked_at)
    .filter(Boolean)
    .sort()
    .at(-1);

  if (!checkedAt) {
    return 'Sin datos';
  }

  return new Date(checkedAt).toLocaleString('es-CO', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
}

function pct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—';
  }
  return `${Math.round(Number(value))}%`;
}

function statusBadge(health) {
  if (health.connection_status === 'offline') {
    return { label: 'Offline', tone: 'offline' };
  }
  if (health.status === 'critical') {
    return { label: 'Critico', tone: 'critical' };
  }
  if (health.status === 'warning') {
    return { label: 'Warning', tone: 'warning' };
  }
  return { label: 'Online', tone: 'ok' };
}

function meterTone(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return 'idle';
  if (n >= 90) return 'critical';
  if (n >= 75) return 'warning';
  return 'ok';
}

function rowTone(health) {
  if (health.connection_status === 'offline') return 'offline';
  if (health.status === 'critical') return 'critical';
  if (health.status === 'warning') return 'warning';
  return 'healthy';
}

function DashboardSkeleton() {
  return (
    <main className="page dash">
      <div className="obs-skeleton obs-skeleton--heading" />
      <section className="dash-stats">
        {Array.from({ length: 5 }).map((_, index) => (
          <div key={index} className="obs-skeleton obs-skeleton--card" />
        ))}
      </section>
      <div className="obs-skeleton obs-skeleton--panel" />
    </main>
  );
}

function Meter({ value }) {
  const n = Number(value);
  const width = Number.isNaN(n) ? 0 : Math.min(100, Math.max(0, n));
  return (
    <div className="dash-meter" title={pct(value)}>
      <span className={`dash-meter__fill is-${meterTone(value)}`} style={{ width: `${width}%` }} />
      <span className="dash-meter__label">{pct(value)}</span>
    </div>
  );
}

const StatIcons = {
  servers: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="6" rx="1.5" /><rect x="3" y="14" width="18" height="6" rx="1.5" />
      <line x1="7" y1="7" x2="7" y2="7" /><line x1="7" y1="17" x2="7" y2="17" />
    </svg>
  ),
  link: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 12a3 3 0 0 1 3-3h3a3 3 0 0 1 0 6h-1" /><path d="M15 12a3 3 0 0 1-3 3H9a3 3 0 0 1 0-6h1" />
    </svg>
  ),
  cpu: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="7" y="7" width="10" height="10" rx="1.5" />
      <path d="M10 2v3M14 2v3M10 19v3M14 19v3M2 10h3M2 14h3M19 10h3M19 14h3" />
    </svg>
  ),
  ram: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="7" width="18" height="10" rx="1.5" /><path d="M7 17v2M12 17v2M17 17v2M8 11h2M14 11h2" />
    </svg>
  ),
  alert: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3 2 20h20z" /><line x1="12" y1="9" x2="12" y2="14" /><line x1="12" y1="17" x2="12" y2="17" />
    </svg>
  ),
};

export default function OverviewPage() {
  const {
    data: summary = [],
    isLoading,
    error,
    isFetching,
  } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: fetchDashboardSummary,
    refetchInterval: 30000,
    staleTime: 25000,
  });

  if (isLoading) {
    return <DashboardSkeleton />;
  }

  if (error) {
    return <main className="page"><div className="state-panel error">{error.message}</div></main>;
  }

  const total = summary.length;
  const online = summary.filter((item) => item.health.connection_status === 'online').length;
  const offline = summary.filter((item) => item.health.connection_status === 'offline').length;
  const warning = summary.filter((item) => item.health.status === 'warning').length;
  const critical = summary.filter((item) => item.health.status === 'critical').length;

  const avg = (key) => {
    const values = summary
      .filter((item) => item.health.connection_status === 'online')
      .map((item) => Number(item.health[key]))
      .filter((n) => !Number.isNaN(n));
    if (!values.length) return null;
    return values.reduce((acc, n) => acc + n, 0) / values.length;
  };

  const averageCpu = avg('cpu_usage');
  const averageRam = avg('memory_usage');

  const stats = [
    { key: 'total', icon: StatIcons.servers, label: 'Total de maquinas', value: total, hint: 'Inventario 10-15', accent: '#64d2ff' },
    { key: 'conn', icon: StatIcons.link, label: 'Conectividad', value: `${online}/${total}`, hint: `${offline} no conectadas`, accent: online === total ? '#5fe3b3' : '#ffb778' },
    { key: 'cpu', icon: StatIcons.cpu, label: 'CPU promedio', value: pct(averageCpu), hint: 'Solo maquinas online', accent: '#7c9cff' },
    { key: 'ram', icon: StatIcons.ram, label: 'RAM promedio', value: pct(averageRam), hint: 'Solo maquinas online', accent: '#c08cff' },
    { key: 'alert', icon: StatIcons.alert, label: 'Alertas', value: warning + critical, hint: `${critical} criticas, ${warning} warning`, accent: warning + critical > 0 ? '#ff8080' : '#5fe3b3' },
  ];

  const sorted = [...summary].sort((a, b) => {
    const rank = (i) => (i.health.connection_status === 'offline' ? 3 : i.health.status === 'critical' ? 0 : i.health.status === 'warning' ? 1 : 2);
    return rank(a) - rank(b);
  });

  return (
    <main className="page dash">
      <section className="dash-header">
        <div>
          <p className="eyebrow">Vista general</p>
          <h1 className="dash-header__title">Centro de monitoreo de las maquinas 10-15</h1>
          <p className="dash-header__copy">
            Salud, capacidad, Docker, puertos y storage por nodo via SSH en tiempo real.
          </p>
        </div>
        <span className={`dash-live${isFetching ? ' is-fetching' : ''}`}>
          <span className="dash-live__dot" />
          {isFetching ? 'Actualizando…' : 'En vivo'}
          <small>{formatLastCheck(summary)}</small>
        </span>
      </section>

      <section className="dash-stats">
        {stats.map((s) => (
          <article key={s.key} className="dash-stat" style={{ '--accent': s.accent }}>
            <span className="dash-stat__icon">{s.icon}</span>
            <span className="dash-stat__label">{s.label}</span>
            <strong className="dash-stat__value">{s.value}</strong>
            <small className="dash-stat__hint">{s.hint}</small>
          </article>
        ))}
      </section>

      <section className="dash-panel">
        <header className="dash-panel__head">
          <h2>Estado por maquina</h2>
          <Link to="/servidores" className="dash-panel__link">Ver detalle completo →</Link>
        </header>

        <div className="dash-table" role="table">
          <div className="dash-table__row dash-table__row--head" role="row">
            <span>Maquina</span>
            <span>Estado</span>
            <span>CPU</span>
            <span>RAM</span>
            <span>Disco</span>
            <span>Latencia</span>
            <span>Uptime</span>
          </div>
          {sorted.map((item) => {
            const badge = statusBadge(item.health);
            const tone = rowTone(item.health);
            return (
              <div key={item.server.code} className={`dash-table__row is-${tone}`} role="row">
                <span className="dash-cell-machine">
                  <span className="dash-cell-machine__name">
                    <span className={`obs-dot is-${tone}`} aria-hidden="true" />
                    <strong>{item.server.code}</strong>
                  </span>
                  <small>{item.server.name || item.server.host}</small>
                </span>
                <span><em className={`dash-badge is-${badge.tone}`}>{badge.label}</em></span>
                <span><Meter value={item.health.cpu_usage} /></span>
                <span><Meter value={item.health.memory_usage} /></span>
                <span><Meter value={item.health.disk_usage} /></span>
                <span className="dash-cell-muted">{item.health.latency_label || (item.health.latency_ms != null ? `${item.health.latency_ms} ms` : '—')}</span>
                <span className="dash-cell-muted">{item.health.uptime || '—'}</span>
              </div>
            );
          })}
        </div>
      </section>

      <section className="quick-links">
        <article className="quick-link-card">
          <h2>Monitoreo por maquina</h2>
          <p>Revisa estado SSH, CPU, RAM, disco, temperatura, Docker, puertos y storage.</p>
          <Link to="/servidores">Ir a Maquinas</Link>
        </article>
        <article className="quick-link-card">
          <h2>Explorador remoto</h2>
          <p>Navega el drive unificado, el compartido y el backup del nodo 104 sin salir del monitor.</p>
          <Link to="/explorador">Abrir Explorador</Link>
        </article>
      </section>
    </main>
  );
}
