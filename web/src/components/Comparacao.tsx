import { useEffect, useState } from "react";
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Icon } from "./Icon";
import {
  PERFIL_META,
  PERFIL_TONE_HEX,
  brl,
  ha,
  type PerfilRisco,
  type Plano,
  type Resultados,
} from "../types";

interface Props {
  resultados: Resultados;
  areaTotal: number;
  perfilInicial: PerfilRisco;
}

function perfilDoPonto(ponto: Plano, index: number, total: number): PerfilRisco | null {
  if (index === 0) return "arrojado";
  if (index === total - 1) return "conservador";
  return ponto.perfil === "equilibrado" || ponto.descricao?.includes("knee")
    ? "equilibrado"
    : null;
}

export function Comparacao({ resultados, areaTotal, perfilInicial }: Props) {
  const [selecionado, setSelecionado] = useState<PerfilRisco>(perfilInicial);
  useEffect(() => setSelecionado(perfilInicial), [perfilInicial]);

  const base = Number((resultados.cenario as { area_total_ha?: number }).area_total_ha ?? 600);
  const nOficial = Number((resultados.cenario as { n_talhoes?: number }).n_talhoes ?? 3);
  const areaEfetiva = areaTotal > 0 ? areaTotal : base;
  const fator = base > 0 ? areaEfetiva / base : 1;
  const escalaPx = (n: number) => Math.round(n * fator);

  const plano0 = resultados.planos[selecionado];
  const arrojado0 = resultados.planos.arrojado;
  const fronteira = resultados.fronteira_pareto;
  const total = fronteira.length;
  const perfil = PERFIL_META[selecionado];
  const tone = PERFIL_TONE_HEX[selecionado];
  const dados = resultados.dados;

  const plano = {
    ...plano0,
    margem_reais: plano0.margem_reais * fator,
    ha_sob_risco: escalaPx(plano0.ha_sob_risco),
    area_por_rotacao: Object.fromEntries(
      Object.entries(plano0.area_por_rotacao).map(([k, v]) => [k, v * fator]),
    ),
  };
  const arrojado = {
    ...arrojado0,
    margem_reais: arrojado0.margem_reais * fator,
    ha_sob_risco: escalaPx(arrojado0.ha_sob_risco),
  };

  const economiaMargem = arrojado.margem_reais - plano.margem_reais;
  const ganhoRisco = arrojado.ha_sob_risco - plano.ha_sob_risco;

  const serie = fronteira.map((ponto, index) => ({
    ...point2plot(ponto, fator),
    index,
    perfil: perfilDoPonto(ponto, index, total),
  }));

  return (
    <section className="painel-comparacao">
      <div className="section-heading">
        <div>
          <span className="section-kicker">Comparação</span>
          <h2>Não há uma resposta certa. Há um menu.</h2>
          <p>
            Cada ponto é um plano ótimo para o seu nível de risco. A curva é a fronteira
            de Pareto: abaixo dela, todo real a menos custa risco desproporcional.
          </p>
        </div>
        <div className="section-meta">
          <span className={`real-badge ${dados.status === "REAL" ? "is-real" : "is-warn"}`}>
            <span className="real-dot" aria-hidden="true" />
            dados {dados.status}
          </span>
        </div>
      </div>

      <div className="comparacao-grid">
        <div className="panel fronteira-panel">
          <div className="panel-heading">
            <div>
              <h3>Fronteira margem × risco</h3>
              <p className="panel-lede">
                {total} planos não-dominados · CP-SAT com prova de otimalidade
              </p>
            </div>
          </div>

          <div className="fronteira-chart" role="img"
               aria-label="Gráfico da fronteira de Pareto: margem total em reais contra hectares sob risco">
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={serie} margin={{ top: 16, right: 16, bottom: 8, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#ebe6da" vertical={false} />
                <XAxis
                  dataKey="ha_sob_risco"
                  type="number"
                  domain={["dataMin - 8", "dataMax + 8"]}
                  tickFormatter={(v: number) => `${ha(v)} ha`}
                  tick={{ fontSize: 10, fill: "#5c6659" }}
                  axisLine={{ stroke: "#ded9cb" }}
                  tickLine={false}
                  label={{
                    value: "hectares sob risco  →",
                    position: "insideBottomRight",
                    fontSize: 9.5,
                    fill: "#5c6659",
                    letterSpacing: "0.14em",
                  }}
                />
                <YAxis
                  dataKey="margem_reais"
                  type="number"
                  domain={["dataMin - 120000", "dataMax + 120000"]}
                  tickFormatter={(v: number) => brl(v).replace(/\s/g, " ")}
                  tick={{ fontSize: 10, fill: "#5c6659" }}
                  axisLine={false}
                  tickLine={false}
                  width={92}
                  label={{
                    value: "margem total",
                    angle: -90,
                    position: "insideLeft",
                    fontSize: 9.5,
                    fill: "#5c6659",
                    letterSpacing: "0.14em",
                  }}
                />
                <Tooltip
                  cursor={{ stroke: "#ded9cb", strokeDasharray: "3 3" }}
                  content={<TooltipFronteira />}
                />
                <Line
                  dataKey="margem_reais"
                  stroke="#2f6b46"
                  strokeWidth={2}
                  dot={(props) => {
                    const { payload, cx, cy } = props as unknown as {
                      payload: { perfil: PerfilRisco | null };
                      cx: number;
                      cy: number;
                    };
                    const fill = payload.perfil
                      ? PERFIL_TONE_HEX[payload.perfil]
                      : "#2f6b46";
                    const r = payload.perfil ? 7 : 4;
                    return (
                      <circle
                        cx={cx}
                        cy={cy}
                        r={r}
                        fill={fill}
                        stroke="#fbfaf6"
                        strokeWidth={2}
                      />
                    );
                  }}
                />
                {plano && (
                  <ReferenceDot
                    x={plano.ha_sob_risco}
                    y={plano.margem_reais}
                    r={11}
                    fill="none"
                    stroke={tone}
                    strokeWidth={1.5}
                    strokeDasharray="3 2"
                  />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          <div className="fronteira-legend" role="group" aria-label="Legenda de perfis">
            {(Object.keys(PERFIL_META) as PerfilRisco[]).map((p) => (
              <span key={p}>
                <i className="legend-swatch" style={{ background: PERFIL_TONE_HEX[p] }} />
                {PERFIL_META[p].label}
              </span>
            ))}
            <span>
              <i className="legend-swatch" style={{ background: "#2f6b46" }} />
              plano intermediário
            </span>
          </div>
        </div>

        <div className="panel plano-panel">
          <div className="panel-heading">
            <div>
              <h3 className="plano-titulo" style={{ color: tone }}>
                {perfil.label}
              </h3>
              <p className="panel-lede">{perfil.hint}</p>
            </div>
          </div>

          <div className="plano-stats">
            <div className="stat">
              <span className="stat-label">Margem total</span>
              <div className="stat-value">
                <strong>{brl(plano.margem_reais)}</strong>
              </div>
              <span className="stat-hint">
                {ha(plano.margem_reais / areaEfetiva)} por hectare da fazenda
              </span>
            </div>
            <div className="stat">
              <span className="stat-label">Risco</span>
              <div className="stat-value">
                <strong>{ha(plano.ha_sob_risco)}</strong>
                <span>ha sob risco</span>
              </div>
              <span className="stat-hint">
                hectares com margem negativa esperada
              </span>
            </div>
          </div>

          {selecionado !== "arrojado" && (
            <div className="rotation-callout">
              <span className="callout-icon" aria-hidden="true">
                <Icon name="trend" size={15} />
              </span>
              <p>
                Em relação ao Arrojado, abre {brl(economiaMargem)} de margem para fugir de{" "}
                {ha(ganhoRisco)} ha de risco.
              </p>
            </div>
          )}

          {Math.abs(fator - 1) > 0.001 && (
            <div className="rotation-callout">
              <span className="callout-icon" aria-hidden="true">
                <Icon name="info" size={15} />
              </span>
              <p>
                O motor rodou para o cenário oficial ({ha(base)} ha · {nOficial} talhões). Com os{" "}
                {ha(areaEfetiva)} ha do seu cenário na Tela 1, os números desta tela seguem a
                mesma proporção.
              </p>
            </div>
          )}

          <div className="perfil-opcoes" role="group" aria-label="Escolher perfil de risco">
            {(Object.keys(PERFIL_META) as PerfilRisco[]).map((p) => (
              <button
                key={p}
                type="button"
                className={`perfil-chip ${selecionado === p ? "active" : ""}`}
                onClick={() => setSelecionado(p)}
                style={
                  selecionado === p
                    ? ({ background: PERFIL_TONE_HEX[p] } as React.CSSProperties)
                    : undefined
                }
              >
                {PERFIL_META[p].label}
              </button>
            ))}
          </div>

          <Alocacao plano={plano} areaTotal={areaEfetiva} />
        </div>
      </div>

      <RobustezPanel resultados={resultados} />
    </section>
  );
}

/** Converte um ponto do contrato para o formato do gráfico, escalando pela área. */
function point2plot(ponto: Plano, fator: number) {
  return {
    margem_reais: ponto.margem_reais * fator,
    ha_sob_risco: Math.round(ponto.ha_sob_risco * fator),
    descricao: ponto.descricao,
  };
}

function Alocacao({ plano, areaTotal }: { plano: Plano; areaTotal: number }) {
  const entradas = Object.entries(plano.area_por_rotacao).sort((a, b) => b[1] - a[1]);
  const total = entradas.reduce((acc, [, v]) => acc + v, 0) || 1;
  return (
    <div className="alocacao">
      <span className="stat-label">Como dividir os {ha(areaTotal)} ha</span>
      <ul className="alocacao-list">
        {entradas.map(([rot, area]) => (
          <li key={rot}>
            <span className="alocacao-rot">{labelRotacao(rot)}</span>
            <div className="alocacao-track" aria-hidden="true">
              <span style={{ width: `${(area / total) * 100}%` }} />
            </div>
            <span className="alocacao-area">{ha(area)} ha</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RobustezPanel({ resultados }: { resultados: Resultados }) {
  const r = resultados.robustez;
  return (
    <div className="panel robustez-panel">
      <div className="panel-heading">
        <div>
          <h3>A recomendação sobrevive à incerteza?</h3>
          <p className="panel-lede">
            Perturbamos margens e custos em ±{r.jitter_percent}% e re-resolvemos{" "}
            {r.runs} vezes. Medimos se o plano continua o mesmo.
          </p>
        </div>
        <div className="robustez-numero">
          <strong>{Math.round(r.stability_mean * 100)}%</strong>
          <span>estabilidade média</span>
        </div>
      </div>

      <div className="robustez-stats">
        <div className="stat">
          <span className="stat-label">Cenários resolvidos</span>
          <div className="stat-value">
            <strong>{r.successful_runs}</strong>
            <span>de {r.runs}</span>
          </div>
        </div>
        <div className="stat">
          <span className="stat-label">Sem nenhuma mudança</span>
          <div className="stat-value">
            <strong>{Math.round(r.pct_runs_sem_mudanca)}%</strong>
          </div>
          <span className="stat-hint">dos cenários mantêm o plano idêntico</span>
        </div>
        <div className="stat">
          <span className="stat-label">Pior caso</span>
          <div className="stat-value">
            <strong>{r.max_talhoes_mudados}</strong>
            <span>talhões</span>
          </div>
          <span className="stat-hint">mudam no cenário mais adverso</span>
        </div>
      </div>

      <div className="rotation-callout">
        <span className="callout-icon" aria-hidden="true">
          <Icon name="shield" size={15} />
        </span>
        <p>{r.frase_estabilidade}</p>
      </div>
    </div>
  );
}

function TooltipFronteira({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: { margem_reais: number; ha_sob_risco: number; descricao: string } }>;
}) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="fronteira-tooltip">
      <strong>{brl(p.margem_reais)}</strong>
      <span>{ha(p.ha_sob_risco)} ha sob risco</span>
      {p.descricao && <em>{p.descricao}</em>}
    </div>
  );
}

function labelRotacao(rot: string) {
  const mapa: Record<string, string> = {
    soja_milho: "Soja → milho safrinha",
    soja_solteira: "Soja solteira",
    soja_sorgo: "Soja → sorgo safrinha",
    feijao_sorgo: "Feijão → sorgo",
    milho_verao: "Milho 1ª safra",
    capital_pousio: "Capital no CDI (não plantar)",
  };
  return mapa[rot] ?? rot;
}
