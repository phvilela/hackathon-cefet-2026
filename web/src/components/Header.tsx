import { Icon } from "./Icon";

interface HeaderProps {
  tela?: "talhoes" | "comparacao" | "rastreabilidade";
  onNavigate?: (tela: "talhoes" | "comparacao" | "rastreabilidade") => void;
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
            <strong>Safra Certa</strong>
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
          <button
            type="button"
            className={`nav-item ${tela === "rastreabilidade" ? "active" : ""}`}
            aria-current={tela === "rastreabilidade" ? "page" : undefined}
            onClick={() => onNavigate?.("rastreabilidade")}
          >
            Rastreabilidade
          </button>
        </nav>

        <div className="header-meta">
          <span className="live-dot" aria-hidden="true" />
          ZARC 2026/27
        </div>
      </div>
    </header>
  );
}
