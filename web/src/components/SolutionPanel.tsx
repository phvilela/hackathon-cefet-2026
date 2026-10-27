import { Icon } from "./Icon";
import { ROTACAO_FAMILIAS } from "../lib/cenario";
import {
  FAMILIAS,
  GRUPO_META,
  formatJanela,
  grupoDoTalhao,
  type FamiliaCultura,
  type Talhao,
  type ZarcData,
} from "../types";

interface SolutionPanelProps {
  zarc: ZarcData;
  talhoes: Talhao[];
  talhao: Talhao;
  culturas: FamiliaCultura[];
  onSelectTalhao: (id: string) => void;
}

const ROTATIONS = [
  { key: "soja_milho", label: "Soja → milho 2ª", short: "Soja / milho" },
  { key: "soja_sorgo", label: "Soja → sorgo 2ª", short: "Soja / sorgo" },
  { key: "feijao_sorgo", label: "Feijão → sorgo 2ª", short: "Feijão / sorgo" },
  { key: "soja_solteira", label: "Soja solteira", short: "Soja" },
  { key: "milho_verao", label: "Milho verão", short: "Milho" },
  { key: "girassol_solteira", label: "Girassol (solteiro)", short: "Girassol" },
  { key: "amendoim_solteira", label: "Amendoim (solteiro)", short: "Amendoim" },
  { key: "arroz_solteira", label: "Arroz (solteiro)", short: "Arroz" },
  { key: "algodao_solteira", label: "Algodão (solteiro)", short: "Algodão" },
  { key: "soja_feijao2", label: "Soja → feijão 2ª", short: "Soja / feijão" },
] as const;

export function SolutionPanel({
  zarc,
  talhoes,
  talhao,
  culturas,
  onSelectTalhao,
}: SolutionPanelProps) {
  const grupo = grupoDoTalhao(talhao);
  const grupoMeta = GRUPO_META[grupo];
  const familias = new Set<FamiliaCultura>(culturas.length > 0 ? culturas : FAMILIAS);
  // Rotações novas (girassol, amendoim, arroz, algodão, soja_feijao2) só entram
  // na lista quando existem no zarc.json — com o arquivo antigo elas somem e o
  // painel continua com as 5 sequências de sempre.
  const visiveis = ROTATIONS.filter(
    (rotation) =>
      zarc.rotacoes[rotation.key] &&
      (ROTACAO_FAMILIAS[rotation.key]?.every((familia) => familias.has(familia)) ?? true),
  );
  const rows = visiveis.map((rotation) => {
    const data = zarc.rotacoes[rotation.key]?.[String(grupo) as "1" | "2" | "3"];
    const primeira = data?.primeira ?? [];
    const segunda = data?.segunda ?? [];
    const viavel = primeira.length > 0;
    return {
      ...rotation,
      viavel,
      detalhe: viavel
        ? `${formatJanela(primeira)}${segunda.length > 0 ? ` → ${formatJanela(segunda)}` : ""}`
        : "Não fecha neste solo",
    };
  });
  const viaveis = rows.filter((row) => row.viavel);
  const bloqueadas = rows.length - viaveis.length;
  const semRotacoes = visiveis.length === 0;

  return (
    <section className="panel solution-panel" aria-label="Nossa solução para o talhão selecionado">
      <div className="panel-heading">
        <div>
          <span className="section-kicker light">Nossa solução</span>
          <h2>O que plantar em {talhao.nome}</h2>
        </div>
        <span className="solution-badge">
          <span className="soil-swatch" data-group={grupo} />
          solo {grupoMeta.label.toLowerCase()} · <span className="soil-code">{grupoMeta.solo}</span>
        </span>
      </div>

      <div className="solution-switcher" role="group" aria-label="Talhão em análise">
        <span className="solution-switch-label">
          <Icon name="layers" size={13} /> Ver talhão
        </span>
        {talhoes.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`solution-switch-btn ${item.id === talhao.id ? "active" : ""}`}
            onClick={() => onSelectTalhao(item.id)}
            aria-pressed={item.id === talhao.id}
            title={`Analisar ${item.nome}`}
          >
            {item.nome}
          </button>
        ))}
      </div>

      <p className="solution-lede">
        Sequências que respeitam o ZARC real e ainda cabem no calendário deste solo.
      </p>

      <div className="solution-highlight">
        <strong>{viaveis.length}</strong>
        <span>
          de {rows.length} sequências fecham
          {bloqueadas > 0 ? ` · ${bloqueadas} não fecham` : ""}
        </span>
      </div>

      {semRotacoes ? (
        <p className="solution-empty">Nenhuma sequência com as culturas selecionadas.</p>
      ) : viaveis.length === 0 ? (
        <p className="solution-empty">Nenhuma sequência fecha neste solo.</p>
      ) : (
        <ul className="solution-list">
          {rows.map((row, index) => (
            <li key={row.key} className={row.viavel ? "ok" : "blocked"}>
              <span className="solution-index">{String(index + 1).padStart(2, "0")}</span>
              <span className="solution-copy">
                <strong>{row.label}</strong>
                <small>{row.detalhe}</small>
              </span>
              <span className={`solution-status ${row.viavel ? "ok" : "blocked"}`}>
                {row.viavel ? <Icon name="check" size={15} /> : <span aria-hidden="true">—</span>}
                {row.viavel ? "fecha" : "não fecha"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
