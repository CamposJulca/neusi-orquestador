const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? 'http://localhost:8000/api' : '/api');

export async function fetchDashboardSummary() {
  const response = await fetch(`${API_BASE_URL}/dashboard/health`);
  if (!response.ok) {
    throw new Error('No se pudo cargar el dashboard');
  }
  return response.json();
}

export async function fetchServerHealth(serverId) {
  const response = await fetch(`${API_BASE_URL}/servers/${serverId}/health`);
  if (!response.ok) {
    throw new Error('No se pudo cargar la salud del servidor');
  }
  return response.json();
}

export async function fetchStorage104() {
  const response = await fetch(`${API_BASE_URL}/servers/104/storage`);
  if (!response.ok) {
    throw new Error('No se pudo cargar el storage del nodo 104');
  }
  return response.json();
}

export async function fetchServers() {
  const response = await fetch(`${API_BASE_URL}/servers`);
  if (!response.ok) {
    throw new Error('No se pudo cargar el inventario de servidores');
  }
  return response.json();
}

export async function fetchObservabilityOverview(serverId) {
  const response = await fetch(`${API_BASE_URL}/observability/${serverId}`);
  if (!response.ok) {
    throw new Error('No se pudo cargar la observabilidad del servidor');
  }
  return response.json();
}

export async function fetchObservabilityHistory(serverId, limit = 48) {
  const response = await fetch(`${API_BASE_URL}/observability/${serverId}/history?limit=${limit}`);
  if (!response.ok) {
    throw new Error('No se pudo cargar el historico del servidor');
  }
  return response.json();
}

export async function fetchObservabilitySnapshots(serverId, limit = 20) {
  const response = await fetch(`${API_BASE_URL}/observability/${serverId}/snapshots?limit=${limit}`);
  if (!response.ok) {
    throw new Error('No se pudo cargar los snapshots');
  }
  return response.json();
}

export async function captureObservabilitySnapshot(serverId) {
  const response = await fetch(`${API_BASE_URL}/observability/${serverId}/snapshots`, { method: 'POST' });
  if (!response.ok) {
    throw new Error('No se pudo capturar el snapshot');
  }
  return response.json();
}

export async function searchObservabilityFiles(serverId, query, path = '/home') {
  const params = new URLSearchParams({ q: query, path });
  const response = await fetch(`${API_BASE_URL}/observability/${serverId}/files/search?${params.toString()}`);
  if (!response.ok) {
    throw new Error('No se pudo ejecutar la busqueda de archivos');
  }
  return response.json();
}

export async function fetchDuplicateFiles(serverId, path = '/home') {
  const params = new URLSearchParams({ path });
  const response = await fetch(`${API_BASE_URL}/observability/${serverId}/files/duplicates?${params.toString()}`);
  if (!response.ok) {
    throw new Error('No se pudo detectar duplicados');
  }
  return response.json();
}

export async function fetchDriveTree({ scope = 'root', serverId, path } = {}) {
  const params = new URLSearchParams({ scope });
  if (serverId) {
    params.set('server_id', serverId);
  }
  if (path) {
    params.set('path', path);
  }
  const response = await fetch(`${API_BASE_URL}/drive/tree?${params.toString()}`);
  if (!response.ok) {
    throw new Error('No se pudo cargar el drive remoto');
  }
  return response.json();
}

export async function fetchFileTree(serverId, path, depth = 2) {
  const params = new URLSearchParams({
    server_id: serverId,
    path,
    depth: String(depth),
  });
  const response = await fetch(`${API_BASE_URL}/files/tree?${params.toString()}`);
  if (!response.ok) {
    throw new Error('No se pudo cargar el explorador de archivos');
  }
  return response.json();
}

export async function fetchFilePreview(serverId, path) {
  const params = new URLSearchParams({
    server_id: serverId,
    path,
  });
  const response = await fetch(`${API_BASE_URL}/files/preview?${params.toString()}`);
  if (!response.ok) {
    throw new Error('No se pudo cargar la vista previa del archivo');
  }
  return response.json();
}

export function buildFileRawUrl(serverId, path, download = false) {
  const params = new URLSearchParams({
    server_id: serverId,
    path,
  });
  if (download) {
    params.set('download', 'true');
  }
  return `${API_BASE_URL}/files/raw?${params.toString()}`;
}
