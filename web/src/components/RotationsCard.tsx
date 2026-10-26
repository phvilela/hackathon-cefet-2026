import { Icon } from "./Icon";
import {
  GRUPO_META,
  formatJanela,
  grupoDoTalhao,
  type Talhao,
  type ZarcData,
} from "../types";

interface RotationsCardProps {
  zarc: ZarcData;
  talhao: Talhao;
}

const ROTATIONS = [
  { key: "soja_milho", label: "Soja → milho 2ª", short: "Soja / milho" },
  { key: "soja_sorgo", label: "Soja → sorgo 2ª", short: "Soja / sorgo" },
  { key: "feijao_sorgo", label: "Feijão → sorgo 2ª", short: "Feijão / sorgo" },
  { key: "soja_solteira", label: "Soja solteira", short: "Soja" },
  { key: "milho_verao", label: "Milho verão", short: "Milho" },
] as const;

export function RotationsCard({ zarc, talhao }: RotationsCardProps) {
  const grupo = grupoDoTalhao(talhao);
  const grupoMeta = GRUPO_META[grupo];
  const rows = ROTATIONS.map((rotation) => {
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
  const viaveis = rows.filter((row) => row.viavel).length;

  const insight =
    grupo === 1
      ? "No solo arenoso, soja → milho safrinha não fecha: a colheita da soja consome a janela do milho. Soja → sorgo é o caminho que sobra."
      : "As janelas pareadas já descontam o ciclo da primeira cultura. Em Patos de Minas, o milho safrinha depois da soja é uma decisão de janeiro, não de dezembro.";

  return (
    <section className="panel rotations-panel">
      <div className="panel-heading">
        <div>
          <span className="section-kicker">Sequência · regra R4</span>
          <h2>O que fecha neste talhão</h2>
        </div>
        <span className="soil-badge">
          <span className="soil-swatch" data-group={grupo} />
          Grupo {grupo} · {grupoMeta.solo}
        </span>
      </div>
      <p className="panel-lede">
        A janela da rotação desconta o ciclo da primeira cultura. {viaveis} de{" "}
        {rows.length} sequências fecham no solo {grupoMeta.label.toLowerCase()}.
      </p>

      <ul className="rotation-list">
        {rows.map((row, index) => (
          <li key={row.key} className={row.viavel ? "ok" : "blocked"}>
            <span className="rotation-index">{String(index + 1).padStart(2, "0")}</span>
            <span className="rotation-copy">
              <strong>{row.label}</strong>
              <small>{row.detalhe}</small>
            </span>
            <span className={`rotation-status ${row.viavel ? "ok" : "blocked"}`}>
              {row.viavel ? <Icon name="check" size={14} /> : <span aria-hidden="true">—</span>}
              {row.viavel ? "fecha" : "não fecha"}
            </span>
          </li>
        ))}
      </ul>

      <div className="rotation-callout">
        <span className="callout-icon" aria-hidden="true">
          <Icon name="info" size={16} />
        </span>
        <p>{insight}</p>
      </div>
    </section>
  );
}
