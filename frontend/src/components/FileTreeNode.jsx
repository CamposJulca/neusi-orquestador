import { useState } from 'react';

function itemIcon(type) {
  return type === 'directory' ? '📁' : '📄';
}

export default function FileTreeNode({
  item,
  level = 0,
  onToggleDirectory,
  onSelectFile,
  selectedNodeId,
  loadingPaths = new Set(),
  forceExpanded = false,
}) {
  const canExpand = Boolean(item.expandable);
  const hasChildren = item.children.length > 0;
  const [expanded, setExpanded] = useState(level < 1);
  const isLoading = loadingPaths.has(item.id);
  const isExpanded = forceExpanded || expanded;

  async function handleToggle() {
    if (!canExpand) {
      return;
    }
    if (!expanded && !item.children_loaded && onToggleDirectory) {
      await onToggleDirectory(item);
    }
    setExpanded((current) => !current);
  }

  return (
    <li className="file-tree-node">
      <div className="file-tree-node__row">
        <button
          type="button"
          className={`file-tree-node__toggle ${canExpand ? 'enabled' : 'disabled'}`}
          onClick={handleToggle}
        >
          {canExpand ? (isExpanded ? '▾' : '▸') : '·'}
        </button>
        <span className="file-tree-node__icon">{itemIcon(item.type)}</span>
        <button
          type="button"
          className={`file-tree-node__name ${selectedNodeId === item.id ? 'selected' : ''}`}
          onClick={() => (item.type === 'file' ? onSelectFile?.(item) : handleToggle())}
        >
          <span>{item.name}</span>
          {item.description ? <small>{item.description}</small> : null}
        </button>
        <span className="file-tree-node__meta">{item.type === 'file' ? item.size : 'Carpeta'}</span>
        <span className="file-tree-node__meta">
          {isLoading ? 'Cargando...' : (item.modified_at || item.server_name || 'Virtual')}
        </span>
      </div>

      {isExpanded && hasChildren ? (
        <ul className="file-tree-node__children">
          {item.children.map((child) => (
            <FileTreeNode
              key={child.path}
              item={child}
              level={level + 1}
              onToggleDirectory={onToggleDirectory}
              onSelectFile={onSelectFile}
              selectedNodeId={selectedNodeId}
              loadingPaths={loadingPaths}
              forceExpanded={forceExpanded}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}
