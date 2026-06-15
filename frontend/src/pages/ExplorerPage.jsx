import FileExplorer from '../components/FileExplorer';

export default function ExplorerPage({ servers }) {
  return (
    <main className="page">
      <section className="section-heading">
        <div>
          <p className="eyebrow">Drive Unico</p>
          <h2>Tus maquinas como una sola biblioteca</h2>
        </div>
        <p className="section-heading__copy">
          Navega archivos remotos desde un solo panel, con vista previa y descarga segura.
        </p>
      </section>

      <FileExplorer servers={servers} />
    </main>
  );
}
