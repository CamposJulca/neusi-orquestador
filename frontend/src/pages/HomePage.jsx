import { Link } from 'react-router-dom';

const DashboardIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="3" y="3" width="7" height="9" rx="1.5" />
    <rect x="14" y="3" width="7" height="5" rx="1.5" />
    <rect x="14" y="12" width="7" height="9" rx="1.5" />
    <rect x="3" y="16" width="7" height="5" rx="1.5" />
  </svg>
);

const MachinesIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="3" y="4" width="18" height="6" rx="1.5" />
    <rect x="3" y="14" width="18" height="6" rx="1.5" />
    <line x1="7" y1="7" x2="7" y2="7" />
    <line x1="7" y1="17" x2="7" y2="17" />
  </svg>
);

const ObservabilityIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M3 12h4l2.5 7 5-16 2.5 9H21" />
  </svg>
);

const ExplorerIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
  </svg>
);

const ArrowIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <line x1="5" y1="12" x2="19" y2="12" />
    <polyline points="13 6 19 12 13 18" />
  </svg>
);

const sections = [
  {
    to: '/dashboard',
    title: 'Dashboard',
    description: 'Vista general con salud, conectividad, CPU promedio y alertas de las maquinas.',
    cta: 'Abrir Dashboard',
    accent: '#64d2ff',
    Icon: DashboardIcon,
  },
  {
    to: '/servidores',
    title: 'Maquinas',
    description: 'Estado SSH, CPU, RAM, disco, temperatura, Docker, puertos y storage por nodo.',
    cta: 'Ver Maquinas',
    accent: '#7c9cff',
    Icon: MachinesIcon,
  },
  {
    to: '/observabilidad',
    title: 'Observabilidad',
    description: 'Metricas y telemetria consolidada para vigilar la infraestructura en tiempo real.',
    cta: 'Ver Observabilidad',
    accent: '#5fe3b3',
    Icon: ObservabilityIcon,
  },
  {
    to: '/explorador',
    title: 'Explorador',
    description: 'Navega el drive unificado, el compartido y el backup del nodo 104.',
    cta: 'Abrir Explorador',
    accent: '#ffb778',
    Icon: ExplorerIcon,
  },
];

export default function HomePage() {
  return (
    <main className="page home">
      <section className="home-hero">
        <p className="eyebrow">Neusi Infra Monitor</p>
        <h1 className="home-hero__title">Centro operativo de infraestructura</h1>
        <p className="home-hero__copy">
          Monitoreo SSH, exploracion remota y visibilidad por maquina desde un solo aplicativo.
          Elige un modulo para comenzar.
        </p>
      </section>

      <section className="home-grid">
        {sections.map(({ to, title, description, cta, accent, Icon }) => (
          <Link key={to} to={to} className="home-card" style={{ '--accent': accent }}>
            <span className="home-card__glow" aria-hidden="true" />
            <span className="home-card__icon">
              <Icon />
            </span>
            <div className="home-card__body">
              <h2 className="home-card__title">{title}</h2>
              <p className="home-card__desc">{description}</p>
            </div>
            <span className="home-card__cta">
              {cta}
              <ArrowIcon />
            </span>
          </Link>
        ))}
      </section>
    </main>
  );
}
