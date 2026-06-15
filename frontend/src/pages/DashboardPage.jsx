import FileExplorer from '../components/FileExplorer';
import ServerCard from '../components/ServerCard';

export default function DashboardPage({ summary, loading, error }) {
  if (loading) {
    return <div className="state-panel">Cargando estado de la infraestructura...</div>;
  }

  if (error) {
    return <div className="state-panel error">{error}</div>;
  }

  const sshBacked = summary.filter((item) => item.health.connection_status === 'online').length;
  const offlineCount = summary.filter((item) => item.health.connection_status === 'offline').length;

  return (
    <main className="dashboard-page">
      <section className="hero">
        <div>
          <p className="eyebrow">Neusi Infra Monitor</p>
          <h1>Visibilidad operativa de las maquinas 10-15</h1>
          <p className="hero-copy">
            Vista unica para revisar salud, capacidad, archivos indexados y proyectos detectados.
          </p>
        </div>
        <div className="hero-panel">
          <span>Servidores monitoreados</span>
          <strong>{summary.length}</strong>
          <small>{sshBacked} online, {offlineCount} no conectados, {summary.length - sshBacked - offlineCount} en mock.</small>
        </div>
      </section>

      <section className="server-grid">
        {summary.map((item) => (
          <ServerCard key={item.server.code} item={item} />
        ))}
      </section>

      <FileExplorer summary={summary} />
    </main>
  );
}
