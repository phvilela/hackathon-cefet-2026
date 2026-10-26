import { Icon } from "./Icon";

interface HeaderProps {
  tela?: "talhoes" | "comparacao";
  onNavigate?: (tela: "talhoes" | "comparacao") => void;
}

export function Header({ tela = "talhoes", onNavigate }: HeaderProps) {
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
          <button
            type="button"
            className={`nav-item ${tela === "talhoes" ? "active" : ""}`}
            aria-current={tela === "talhoes" ? "page" : undefined}
            onClick={() => onNavigate?.("talhoes")}
          >
            Talhões
          </button>
          <button
            type="button"
            className={`nav-item ${tela === "comparacao" ? "active" : ""}`}
            aria-current={tela === "comparacao" ? "page" : undefined}
            onClick={() => onNavigate?.("comparacao")}
          >
            Comparação
          </button>
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
