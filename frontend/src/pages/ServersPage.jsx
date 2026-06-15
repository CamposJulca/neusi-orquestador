import { useQuery } from '@tanstack/react-query';
import ServerCard from '../components/ServerCard';
import { fetchDashboardSummary } from '../services/api';

export default function ServersPage() {
  const {
    data: summary = [],
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: fetchDashboardSummary,
    refetchInterval: 30000,
    staleTime: 25000,
  });

  if (isLoading) {
    return (
      <main className="page">
        <div className="obs-skeleton obs-skeleton--heading" />
        <section className="server-grid">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="obs-skeleton obs-skeleton--servercard" />
          ))}
        </section>
      </main>
    );
  }

  if (error) {
    return <main className="page"><div className="state-panel error">{error.message}</div></main>;
  }

  const downloadDetailedState = () => {
    const exportedAt = new Date().toISOString();
    const payload = {
      exported_at: exportedAt,
      source: 'dashboard/health',
      servers: summary,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `estado-detallado-servidores-${exportedAt.replaceAll(':', '-').replace('.', '-')}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const sshBacked = summary.filter((item) => item.health.connection_status === 'online').length;
  const offlineCount = summary.filter((item) => item.health.connection_status === 'offline').length;
  const warningCount = summary.filter((item) => item.health.status === 'warning').length;
  const criticalCount = summary.filter((item) => item.health.status === 'critical').length;

  return (
    <main className="page">
      <section className="section-heading">
        <div>
          <p className="eyebrow">Maquinas</p>
          <h2>Estado detallado por servidor</h2>
        </div>
        <div className="section-heading__actions">
          <div className="obs-count-row">
            <span className="obs-count is-healthy">{sshBacked} online</span>
            {offlineCount ? <span className="obs-count is-neutral">{offlineCount} sin conexion</span> : null}
            {criticalCount ? <span className="obs-count is-critical">{criticalCount} criticos</span> : null}
            {warningCount ? <span className="obs-count is-warning">{warningCount} warning</span> : null}
          </div>
          <button type="button" className={`section-action-button${isFetching ? ' is-loading' : ''}`} onClick={() => refetch()} disabled={isFetching}>
            {isFetching ? 'Actualizando...' : 'Actualizar'}
          </button>
          <button type="button" className="section-download-button" onClick={downloadDetailedState}>
            Descargar JSON
          </button>
        </div>
      </section>

      <section className="server-grid">
        {summary.map((item) => (
          <ServerCard key={item.server.code} item={item} />
        ))}
      </section>
    </main>
  );
}
