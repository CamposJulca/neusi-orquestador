import { Suspense, lazy } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import AppShell from './components/AppShell';
import { fetchServers } from './services/api';

const HomePage = lazy(() => import('./pages/HomePage'));
const OverviewPage = lazy(() => import('./pages/OverviewPage'));
const ServersPage = lazy(() => import('./pages/ServersPage'));
const ObservabilityPage = lazy(() => import('./pages/ObservabilityPage'));
const ExplorerPage = lazy(() => import('./pages/ExplorerPage'));

export default function App() {
  const {
    data: servers = [],
    isLoading,
    error,
  } = useQuery({
    queryKey: ['servers'],
    queryFn: fetchServers,
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) {
    return <div className="state-panel">Cargando inventario de infraestructura...</div>;
  }

  if (error) {
    return <div className="state-panel error">{error.message}</div>;
  }

  return (
    <BrowserRouter>
      <AppShell servers={servers}>
        <Suspense fallback={<div className="state-panel">Cargando modulo...</div>}>
          <Routes>
            <Route path="/" element={<Navigate to="/explorador" replace />} />
            <Route path="/home" element={<HomePage />} />
            <Route path="/dashboard" element={<OverviewPage />} />
            <Route path="/servidores" element={<ServersPage />} />
            <Route path="/observabilidad" element={<ObservabilityPage servers={servers} />} />
            <Route path="/explorador" element={<ExplorerPage servers={servers} />} />
          </Routes>
        </Suspense>
      </AppShell>
    </BrowserRouter>
  );
}
