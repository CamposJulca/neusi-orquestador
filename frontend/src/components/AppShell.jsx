import { NavLink } from 'react-router-dom';

const navigation = [
  { to: '/home', label: 'Inicio' },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/servidores', label: 'Maquinas' },
  { to: '/observabilidad', label: 'Observabilidad' },
  { to: '/explorador', label: 'Explorador' },
];

export default function AppShell({ children, servers }) {
  const activeCount = servers.length;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar__brand">
          <p className="eyebrow">Neusi Infra Monitor</p>
          <h1>Centro operativo de infraestructura</h1>
          <p className="sidebar__copy">
            Monitoreo SSH, exploracion remota y visibilidad por maquina desde un solo aplicativo.
          </p>
        </div>

        <nav className="sidebar__nav" aria-label="Navegacion principal">
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `sidebar__link${isActive ? ' is-active' : ''}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <section className="sidebar__status">
          <span>Servidores activos</span>
          <strong>{activeCount}</strong>
          <small>Inventario base cargado sin esperar telemetria SSH</small>
        </section>
      </aside>

      <div className="app-shell__content">{children}</div>
    </div>
  );
}
