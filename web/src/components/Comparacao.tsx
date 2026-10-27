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
import { StatusApiBadge } from "./StatusApiBadge";
import {
  PERFIL_META,
  PERFIL_TONE_HEX,
  REFERENCIA_TONE,
  areaRiscoPct,
  brl,
  grupoDoTalhao,
  ha,
  type CenarioState,
  type CropKey,
  type GrupoSolo,
  type PerfilRisco,
  type Plano,
  type Resultados,
  type Talhao,
  type ZarcData,
} from "../types";
import type { StatusApi } from "../lib/api";

interface Props {
  resultados: Resultados;
  cenario: CenarioState;
  zarc: ZarcData;
  statusApi: StatusApi;
  usandoFallback: boolean;
}

/**
 * Identifica o perfil de um ponto da curva pelo marcador `perfil` do contrato
 * (v2: 'Arrojado' | 'Equilibrado (knee)' | 'Conservador' | null).
 * Sem heurística de índice — funciona com 7 ou 14 pontos.
 */
function perfilDoPonto(ponto: Plano): PerfilRisco | null {
  const tag = (ponto.perfil ?? "").toLowerCase();
  if (tag.includes("arrojado")) return "arrojado";
  if (tag.includes("conservador")) return "conservador";
  if (tag.includes("knee") || tag.includes("equilibrado")) return "equilibrado";
  return null;
}

function rotuloDoPonto(perfil: PerfilRisco | null) {
  return perfil ? PERFIL_META[perfil].label : "Plano intermediário";
}

/** Primeira cultura de cada rotação — base para ler o risco ZARC da janela
 *  de plantio recomendada. Rotações sem cultura (ex.: capital no CDI) ficam
 *  de fora do mapa e são ignoradas no chip. */
const PRIMEIRA_CULTURA: Record<string, CropKey> = {
  soja_milho: "soja",
  soja_solteira: "soja",
  soja_sorgo: "soja",
  feijao_sorgo: "feijao",
  milho_verao: "milho_verao",
  soja_feijao2: "soja",
  girassol_solteira: "girassol",
  amendoim_solteira: "amendoim",
  arroz_solteira: "arroz",
  algodao_solteira: "algodao",
};

/**
 * Faixa do risco climático (ZARC) das janelas de plantio do plano selecionado,
 * no estilo do ZARC: para cada rotação alocada, considera os grupos de solo dos
 * talhões do cenário, lê os decêndios viáveis da 1ª cultura
 * (zarc.rotacoes[rot][grupo].primeira) e guarda o MENOR risco decendial
 * (zarc.culturas[crop][grupo].risco_por_decendio) — o risco da "melhor janela".
 * Devolve a faixa [mín, máx] entre as rotações; null se faltar dado
 * (zarc.json antigo sem as rotações/culturas novas) → o chip não renderiza.
 */
function faixaRiscoZarcJanelas(
  zarc: ZarcData,
  plano: Plano,
  talhoes: Talhao[],
): [number, number] | null {
  const grupos = [...new Set(talhoes.map(grupoDoTalhao))];
  const melhores: number[] = [];
  for (const [rot, area] of Object.entries(plano.area_por_rotacao)) {
    if (!area || area <= 0) continue;
    const cultura = zarc.culturas[PRIMEIRA_CULTURA[rot]];
    const rotacao = zarc.rotacoes[rot];
    if (!cultura || !rotacao) continue;
    const riscos: number[] = [];
    for (const grupo of grupos) {
      const janela = cultura[String(grupo) as `${GrupoSolo}`];
      const decendios = rotacao[String(grupo) as `${GrupoSolo}`]?.primeira ?? [];
      if (!janela) continue;
      for (const dec of decendios) {
        const risco = janela.risco_por_decendio?.[String(dec)];
        if (typeof risco === "number") riscos.push(risco);
      }
    }
    if (riscos.length > 0) melhores.push(Math.min(...riscos));
  }
  if (melhores.length === 0) return null;
  return [Math.min(...melhores), Math.max(...melhores)];
}

export function Comparacao({
  resultados,
  cenario,
  zarc,
  statusApi,
  usandoFallback,
}: Props) {
  const [selecionado, setSelecionado] = useState<PerfilRisco>(
    cenario.perfil ?? "equilibrado",
  );

  // O banner de recomendação acompanha o perfil escolhido na tela 1.
  useEffect(() => {
    setSelecionado(cenario.perfil);
  }, [cenario.perfil]);

  const areaTotal = cenario.talhoes.reduce((acc, talhao) => acc + talhao.areaHa, 0);
  const fronteira = resultados.fronteira_pareto;
  const total = fronteira.length;
  const plano = resultados.planos[selecionado];
  const perfil = PERFIL_META[selecionado];
  const tone = PERFIL_TONE_HEX[selecionado];
  const dados = resultados.dados;

  // Âncora "não plantar" (contrato v2, opcional) — ponto destacado, fora da
  // fronteira e não selecionável como perfil.
  const referencia = resultados.referencia_sem_plantio ?? null;

  const serie = fronteira.map((ponto) => {
    const perfilPonto = perfilDoPonto(ponto);
    return {
      margem_reais: ponto.margem_reais,
      ha_sob_risco: ponto.ha_sob_risco,
      perfil: perfilPonto,
      rotulo: rotuloDoPonto(perfilPonto),
    };
  });

  // Domínio numérico explícito: inclui a âncora "não plantar" (se existir) e
  // continua correto com 7 ou 14 pontos na fronteira.
  const margens = serie.map((ponto) => ponto.margem_reais);
  const hectares = serie.map((ponto) => ponto.ha_sob_risco);
  if (referencia) {
    margens.push(referencia.margem_reais);
    hectares.push(referencia.ha_sob_risco);
  }
  const dominioX: [number, number] = [
    Math.max(0, (hectares.length ? Math.min(...hectares) : 0) - 8),
    (hectares.length ? Math.max(...hectares) : 8) + 8,
  ];
  const dominioY: [number, number] = [
    (margens.length ? Math.min(...margens) : 0) - 120000,
    (margens.length ? Math.max(...margens) : 120000) + 120000,
  ];

  const arrojado = resultados.planos.arrojado;
  const economiaMargem = arrojado.margem_reais - plano.margem_reais;
  const ganhoRisco = arrojado.ha_sob_risco - plano.ha_sob_risco;

  const pctArea = areaRiscoPct(plano.ha_sob_risco, areaTotal);
  const resumoAlocacao = Object.entries(plano.area_por_rotacao)
    .sort((a, b) => b[1] - a[1])
    .map(([rot, area]) => `${labelRotacao(rot)} ${ha(area)} ha`)
    .join(" · ");

  // Chip ZARC: faixa do risco de perda por seca nas janelas recomendadas.
  const faixaZarc = faixaRiscoZarcJanelas(zarc, plano, cenario.talhoes);
  const riscoZarcJanelas = faixaZarc
    ? faixaZarc[0] === faixaZarc[1]
      ? `${faixaZarc[0]}%`
      : `${faixaZarc[0]}–${faixaZarc[1]}%`
    : null;

  return (
    <section className="painel-comparacao">
      <div className="section-heading">
        <div>
          <span className="section-kicker">Comparação</span>
          <h2>Não há uma resposta certa. Há um menu.</h2>
          <p>
            Cada ponto é um plano possível para o seu perfil. A curva liga os
            planos que não são superados: ganhar mais margem sempre exige aceitar
            mais chance de prejuízo — e o contrário também vale.
          </p>
        </div>
        <div className="section-meta">
          <span className={`real-badge ${dados.status === "REAL" ? "is-real" : "is-warn"}`}>
            <span className="real-dot" aria-hidden="true" />
            dados {dados.status}
          </span>
          <StatusApiBadge status={statusApi} usandoFallback={usandoFallback} />
        </div>
      </div>

      <div className="rotation-callout verdict-banner" style={{ borderLeftColor: tone }}>
        <span className="callout-icon" aria-hidden="true">
          <Icon name="trend" size={17} />
        </span>
        <div className="verdict-copy">
          <p className="verdict-line">
            <span className="verdict-kicker">Recomendação:</span> perfil{" "}
            <strong style={{ color: tone }}>{perfil.label}</strong>
            <span className="verdict-sep" aria-hidden="true">
              —
            </span>
            <strong className="verdict-num">{brl(plano.margem_reais)}</strong> de margem
            <span className="verdict-sep" aria-hidden="true">
              ·
            </span>
            <strong className="verdict-num">{pctArea}</strong> da área com chance
            de prejuízo
          </p>
          <p className="verdict-sub">Como dividir os {ha(areaTotal)} ha: {resumoAlocacao}</p>
        </div>
      </div>

      <div className="comparacao-grid">
        <div className="panel fronteira-panel">
          <div className="panel-heading">
            <div>
              <h3>Margem × chance de prejuízo</h3>
              <p className="panel-lede">
                {total} planos possíveis — nenhum supera o outro · algoritmo de otimização
                com prova de melhor solução
              </p>
            </div>
          </div>

          <div className="fronteira-chart" role="img"
               aria-label="Gráfico dos planos possíveis: margem total em reais contra hectares com chance de prejuízo">
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={serie} margin={{ top: 16, right: 16, bottom: 8, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#ebe6da" vertical={false} />
                <XAxis
                  dataKey="ha_sob_risco"
                  type="number"
                  domain={dominioX}
                  tickFormatter={(v: number) => `${ha(v)} ha`}
                  tick={{ fontSize: 10, fill: "#5c6659" }}
                  axisLine={{ stroke: "#ded9cb" }}
                  tickLine={false}
                  label={{
                    value: "hectares com chance de prejuízo  →",
                    position: "insideBottomRight",
                    fontSize: 9.5,
                    fill: "#5c6659",
                    letterSpacing: "0.14em",
                  }}
                />
                <YAxis
                  dataKey="margem_reais"
                  type="number"
                  domain={dominioY}
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
                  content={<TooltipFronteira areaTotal={areaTotal} />}
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
                {referencia && (
                  <ReferenceDot
                    x={referencia.ha_sob_risco}
                    y={referencia.margem_reais}
                    r={6}
                    fill={REFERENCIA_TONE.fill}
                    stroke={REFERENCIA_TONE.stroke}
                    strokeWidth={1.5}
                    strokeDasharray="4 3"
                    ifOverflow="extendDomain"
                    label={{
                      value: "não plantar (capital no CDI)",
                      position: "insideTopRight",
                      fontSize: 9.5,
                      fill: REFERENCIA_TONE.stroke,
                    }}
                  />
                )}
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
            {referencia && (
              <span>
                <i className="legend-swatch ref" />
                não plantar (capital no CDI)
              </span>
            )}
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
                {areaTotal > 0 ? ha(plano.margem_reais / areaTotal) : "—"} por hectare da
                fazenda
              </span>
            </div>
            <div className="stat">
              <span className="stat-label">% da área com chance de prejuízo</span>
              <div className="stat-value">
                <strong>{pctArea}</strong>
                <span>{ha(plano.ha_sob_risco)} ha</span>
              </div>
              <span className="stat-hint">
                hectares com margem negativa esperada
              </span>
            </div>
            {riscoZarcJanelas && (
              <div className="stat">
                <span className="stat-label">Risco ZARC das janelas</span>
                <div className="stat-value">
                  <strong>{riscoZarcJanelas}</strong>
                </div>
                <span className="stat-hint">
                  janelas de plantio do plano — risco de perda por seca (ZARC) por
                  período de 10 dias
                </span>
              </div>
            )}
          </div>

          {selecionado !== "arrojado" && (
            <div className="rotation-callout">
              <span className="callout-icon" aria-hidden="true">
                <Icon name="trend" size={15} />
              </span>
              <p>
                Em relação ao Arrojado, abre {brl(economiaMargem)} de margem para fugir de{" "}
                {ha(ganhoRisco)} ha com chance de prejuízo.
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

          <Alocacao plano={plano} areaTotal={areaTotal} />
        </div>
      </div>

      <RobustezPanel resultados={resultados} />
    </section>
  );
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
            Variamos margens e custos em ±{r.jitter_percent}% e refazemos o cálculo{" "}
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
  areaTotal,
}: {
  active?: boolean;
  payload?: Array<{
    payload: { margem_reais: number; ha_sob_risco: number; rotulo: string };
  }>;
  areaTotal?: number;
}) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="fronteira-tooltip">
      <strong>{brl(p.margem_reais)}</strong>
      <span>
        {`chance de prejuízo: ${areaRiscoPct(p.ha_sob_risco, areaTotal ?? 0)} da área (${ha(p.ha_sob_risco)} ha)`}
      </span>
      {p.rotulo && <em>{p.rotulo}</em>}
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
    girassol_solteira: "Girassol (solteiro)",
    amendoim_solteira: "Amendoim (solteiro)",
    arroz_solteira: "Arroz (solteiro)",
    algodao_solteira: "Algodão (solteiro)",
    soja_feijao2: "Soja → feijão 2ª safra",
  };
  return mapa[rot] ?? rot;
}
