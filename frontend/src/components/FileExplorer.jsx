import { useDeferredValue, useEffect, useMemo, useState } from 'react';
import FileTreeNode from './FileTreeNode';
import { buildFileRawUrl, fetchDriveTree, fetchFilePreview } from '../services/api';

function formatCheckedAt(value) {
  if (!value) return 'Sin consultas';
  return new Date(value).toLocaleString('es-CO', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
}

function filterTreeItems(items, query) {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return items;
  }

  return items.reduce((accumulator, item) => {
    const filteredChildren = item.children?.length ? filterTreeItems(item.children, normalizedQuery) : [];
    const haystack = [
      item.name,
      item.path,
      item.description,
      item.server_name,
    ].filter(Boolean).join(' ').toLowerCase();

    if (haystack.includes(normalizedQuery) || filteredChildren.length > 0) {
      accumulator.push({
        ...item,
        children: filteredChildren,
      });
    }

    return accumulator;
  }, []);
}

function mergeChildren(items, targetId, children) {
  return items.map((item) => {
    if (item.id === targetId) {
      return {
        ...item,
        children,
        children_loaded: true,
      };
    }
    if (item.children?.length) {
      return {
        ...item,
        children: mergeChildren(item.children, targetId, children),
      };
    }
    return item;
  });
}

export default function FileExplorer() {
  const [searchTerm, setSearchTerm] = useState('');
  const [treeResponse, setTreeResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingPaths, setLoadingPaths] = useState(new Set());
  const [previewLoading, setPreviewLoading] = useState(false);
  const [preview, setPreview] = useState(null);
  const [selectedNodeId, setSelectedNodeId] = useState('');
  const [selectedLabel, setSelectedLabel] = useState('Drive');
  const [previewMediaUrl, setPreviewMediaUrl] = useState('');
  const [error, setError] = useState('');

  const deferredSearchTerm = useDeferredValue(searchTerm);

  useEffect(() => {
    let mounted = true;

    async function loadRoot() {
      setLoading(true);
      try {
        const response = await fetchDriveTree({ scope: 'root' });
        if (mounted) {
          setTreeResponse(response);
          setError('');
        }
      } catch (err) {
        if (mounted) {
          setError(err.message);
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    loadRoot();

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!preview?.connected || !preview.server_id || !preview.path) {
      setPreviewMediaUrl('');
      return;
    }

    if (!['image', 'video'].includes(preview.preview_kind)) {
      setPreviewMediaUrl('');
      return;
    }

    setPreviewMediaUrl(buildFileRawUrl(preview.server_id, preview.path));
  }, [preview]);

  const filteredItems = useMemo(() => filterTreeItems(treeResponse?.items || [], deferredSearchTerm), [treeResponse, deferredSearchTerm]);
  const hasActiveSearch = deferredSearchTerm.trim().length > 0;

  async function handleRefresh() {
    setLoading(true);
    setPreview(null);
    setPreviewMediaUrl('');
    setSelectedNodeId('');
    try {
      const response = await fetchDriveTree({ scope: 'root' });
      setTreeResponse(response);
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleToggleDirectory(item) {
    setLoadingPaths((current) => new Set(current).add(item.id));

    try {
      const response = await fetchDriveTree({
        scope: item.scope,
        serverId: item.server_id || undefined,
        path: item.path || undefined,
      });
      setTreeResponse((current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          items: mergeChildren(current.items, item.id, response.items),
          checked_at: response.checked_at,
        };
      });
      setSelectedLabel(item.path ? `${item.server_name || item.name} · ${item.path}` : item.name);
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingPaths((current) => {
        const next = new Set(current);
        next.delete(item.id);
        return next;
      });
    }
  }

  async function handleSelectFile(item) {
    if (!item.server_id || !item.path) {
      return;
    }

    setSelectedNodeId(item.id);
    setSelectedLabel(`${item.server_name || 'Servidor'} · ${item.path}`);
    setPreviewLoading(true);
    setPreviewMediaUrl('');
    try {
      const response = await fetchFilePreview(item.server_id, item.path);
      setPreview({
        ...response,
        server_id: item.server_id,
        server_name: item.server_name,
      });
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setPreviewLoading(false);
    }
  }

  return (
    <section className="explorer-panel">
      <div className="explorer-panel__header">
        <div>
          <p className="eyebrow">Drive Remoto</p>
          <h2>Un drive virtual unico para tus seis maquinas</h2>
        </div>
        <div className="explorer-panel__actions">
          {treeResponse?.items?.length ? (
            <span className="obs-count is-healthy">{treeResponse.items.length} nodos</span>
          ) : null}
          <button
            type="button"
            className={`explorer-refresh${loading ? ' is-loading' : ''}`}
            onClick={handleRefresh}
          >
            {loading ? 'Actualizando…' : 'Actualizar'}
          </button>
        </div>
      </div>

      <div className="explorer-controls explorer-controls--library">
        <label>
          <span>Buscar en el drive</span>
          <input
            type="search"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Servidor, ruta, carpeta o archivo"
          />
        </label>
      </div>

      <div className="explorer-status explorer-status--library">
        <span>{selectedLabel}</span>
        <span>Ultima consulta: {formatCheckedAt(treeResponse?.checked_at)}</span>
      </div>

      {loading ? (
        <div className="file-tree-skeleton">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="obs-skeleton obs-skeleton--row" />
          ))}
        </div>
      ) : null}
      {error ? <div className="explorer-empty error">{error}</div> : null}

      {!loading && !error && treeResponse?.items?.length === 0 ? (
        <div className="explorer-empty">No hay nodos disponibles en el drive.</div>
      ) : null}

      {!loading && !error && treeResponse?.items?.length > 0 && hasActiveSearch && filteredItems.length === 0 ? (
        <div className="explorer-empty">No hay resultados para "{searchTerm}".</div>
      ) : null}

      {!loading && !error && treeResponse?.items?.length > 0 && (!hasActiveSearch || filteredItems.length > 0) ? (
        <div className="explorer-content">
          <div className="file-tree">
            <div className="file-tree__header">
              <span aria-hidden="true" />
              <span aria-hidden="true" />
              <span>Nombre</span>
              <span>Tamano</span>
              <span>Ubicacion</span>
            </div>
            <ul className="file-tree__list">
              {filteredItems.map((item) => (
                <FileTreeNode
                  key={item.id}
                  item={item}
                  onToggleDirectory={handleToggleDirectory}
                  onSelectFile={handleSelectFile}
                  selectedNodeId={selectedNodeId}
                  loadingPaths={loadingPaths}
                  forceExpanded={hasActiveSearch}
                />
              ))}
            </ul>
          </div>

          <aside className="file-preview">
            <div className="file-preview__header">
              <h3>Vista previa</h3>
              {preview ? (
                <span className={`obs-tag is-${preview.connected ? 'healthy' : 'critical'}`}>
                  {preview.connected ? 'conectado' : 'sin conexion'}
                </span>
              ) : null}
              {preview?.connected && preview.type === 'file' ? (
                <a className="file-preview__download" href={buildFileRawUrl(preview.server_id, preview.path, true)}>
                  Descargar
                </a>
              ) : null}
            </div>

            {!preview && !previewLoading ? (
              <div className="file-preview__empty">Selecciona un archivo del drive para visualizarlo.</div>
            ) : null}
            {previewLoading ? <div className="file-preview__empty">Cargando vista previa...</div> : null}
            {preview && !preview.connected ? <div className="file-preview__empty">No conectado</div> : null}

            {preview?.connected ? (
              <div className="file-preview__body">
                <div className="file-preview__meta">
                  <strong>{preview.name}</strong>
                  <span>{preview.server_name}</span>
                  <span>{preview.path}</span>
                  <span>{preview.mime_type}</span>
                  <span>{preview.size || 'Sin tamano'}</span>
                  <span>{preview.modified_at || 'Sin fecha'}</span>
                </div>

                {preview.preview_kind === 'text' ? (
                  <pre className="file-preview__text">{preview.text_content}</pre>
                ) : null}

                {preview.preview_kind === 'image' && previewMediaUrl ? (
                  <img
                    className="file-preview__image"
                    src={previewMediaUrl}
                    alt={preview.name}
                  />
                ) : null}

                {preview.preview_kind === 'video' && previewMediaUrl ? (
                  <video className="file-preview__video" controls src={previewMediaUrl} />
                ) : null}

                {['image', 'video'].includes(preview.preview_kind) && !previewMediaUrl ? (
                  <div className="file-preview__empty">Cargando archivo multimedia...</div>
                ) : null}

                {preview.preview_kind === 'unsupported' ? (
                  <div className="file-preview__empty">Vista previa no disponible para este tipo de archivo.</div>
                ) : null}
              </div>
            ) : null}
          </aside>
        </div>
      ) : null}
    </section>
  );
}
