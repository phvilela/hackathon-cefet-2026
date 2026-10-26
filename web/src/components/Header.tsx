import { Icon } from "./Icon";

export function Header() {
  return (
    <header className="site-header">
      <div className="header-inner">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <Icon name="leaf" size={22} />
          </span>
          <span className="brand-copy">
            <strong>O que plantar?</strong>
            <small>Embrapa · HackatOhm 2026</small>
          </span>
        </div>

        <nav className="main-nav" aria-label="Etapas da recomendação">
          <span className="nav-item active" aria-current="page">
            Talhões
          </span>
          <span className="nav-item disabled">
            Comparação <em>em breve</em>
          </span>
          <span className="nav-item disabled">
            Rastreabilidade <em>em breve</em>
          </span>
        </nav>

        <div className="header-meta">
          <span className="live-dot" aria-hidden="true" />
          ZARC 2026/27
        </div>
      </div>
    </header>
  );
}
