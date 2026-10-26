import { useMemo, useState } from "react";
import { Icon } from "./Icon";
import {
  PERFIL_TONE_HEX,
  type Hipotese,
  type Resultados,
} from "../types";

interface Props {
  resultados: Resultados;
}

interface Fonte {
  id: string;
  orgao: string;
  url: string;
  usos: Hipotese[];
}

/** Agrupa as hipóteses pela fonte, para mostrar de onde vem cada número. */
function agruparPorFonte(resultados: Resultados): Fonte[] {
  const mapa = new Map<string, Fonte>();
  for (const [rot, info] of Object.entries(resultados.rotacoes)) {
    for (const h of info.hipoteses) {
      const id = h.fonte_url;
      const existente = mapa.get(id);
      const uso = { ...h, valor: `${h.valor} · ${rotLabel(rot)}` };
      if (existente) {
        existente.usos.push(uso);
      } else {
        mapa.set(id, { id, orgao: orgaoDaFonte(h.fonte_url), url: h.fonte_url, usos: [uso] });
      }
    }
  }
  return [...mapa.values()].sort((a, b) => b.usos.length - a.usos.length);
}

function orgaoDaFonte(url: string) {
  if (url.startsWith("MOCK://")) return "Pendente";
  if (url.includes("sidra") || url.includes("apisidra")) return "IBGE · SIDRA";
  if (url.includes("conab") || url.includes("gov.br")) return "Conab";
  if (url.includes("dados.agricultura") || url.includes("zarc")) return "ZARC · MAPA";
  if (url.includes("bcb") || url.includes("selic")) return "Banco Central";
  if (url.includes("notebooks") || url.includes("data/")) return "Repositório (pipeline)";
  return "Fonte interna";
}

function rotLabel(rot: string) {
  const mapa: Record<string, string> = {
    soja_milho: "soja→milho",
    soja_solteira: "soja solteira",
    soja_sorgo: "soja→sorgo",
    feijao_sorgo: "feijão→sorgo",
    milho_verao: "milho 1ª safra",
    capital_pousio: "capital pousio",
  };
  return mapa[rot] ?? rot;
}

const ORDEM_ROTACAO = [
  "soja_milho",
  "soja_solteira",
  "soja_sorgo",
  "feijao_sorgo",
  "milho_verao",
  "capital_pousio",
];

export function Rastreabilidade({ resultados }: Props) {
  const [aba, setAba] = useState<"porRotacao" | "porFonte">("porRotacao");
  const fontes = useMemo(() => agruparPorFonte(resultados), [resultados]);
  const status = resultados.dados.status;

  const totalHip = Object.values(resultados.rotacoes).reduce(
    (acc, r) => acc + r.hipoteses.length,
    0,
  );

  return (
    <section className="painel-rastreio">
      <div className="section-heading">
        <div>
          <span className="section-kicker">Rastreabilidade</span>
          <h2>Por que soja? Porque cada número tem dono.</h2>
          <p>
            Nenhum número entra no pipeline sem fonte, método e URL. Clique para abrir a
            fonte oficial. É o antídoto para a objeção da caixa-preta.
          </p>
        </div>
        <div className="section-meta">
          <span className={`real-badge ${status === "REAL" ? "is-real" : "is-warn"}`}>
            <span className="real-dot" aria-hidden="true" />
            dados {status}
          </span>
          <span>{totalHip} hipóteses</span>
          <span>{fontes.length} fontes</span>
        </div>
      </div>

      <div className="rastreio-abas" role="tablist" aria-label="Agrupamento das hipóteses">
        <button
          type="button"
          role="tab"
          aria-selected={aba === "porRotacao"}
          className={`rastreio-aba ${aba === "porRotacao" ? "active" : ""}`}
          onClick={() => setAba("porRotacao")}
        >
          Por rotação
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={aba === "porFonte"}
          className={`rastreio-aba ${aba === "porFonte" ? "active" : ""}`}
          onClick={() => setAba("porFonte")}
        >
          Por fonte
        </button>
      </div>

      {aba === "porRotacao" ? (
        <div className="rastreio-lista">
          {ORDEM_ROTACAO.filter((r) => resultados.rotacoes[r]).map((rot) => {
            const info = resultados.rotacoes[rot];
            return (
              <div className="panel rastreio-card" key={rot}>
                <div className="rastreio-cabecalho">
                  <div>
                    <span className="crop-dot-grupo" aria-hidden="true">
                      {info.culturas.map((c, i) => (
                        <i key={c} style={{ background: corCultura(c), zIndex: 3 - i }} />
                      ))}
                    </span>
                    <h3>{rotLabel(rot)}</h3>
                  </div>
                  <div className="rastreio-numeros">
                    <span className="rastreio-margem">
                      {brlCurto(info.margem_reais_por_ha)}/ha
                    </span>
                    <span className="rastreio-risco">
                      {info.risco_por_mil}‰ · P(margem negativa){" "}
                      {(info.risco_por_mil / 10).toFixed(1)}%
                    </span>
                  </div>
                </div>

                <ul className="hipotese-lista">
                  {info.hipoteses.map((h) => (
                    <HipoteseLinha key={h.chave} h={h} />
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="rastreio-lista">
          {fontes.map((f) => (
            <div className="panel fonte-card" key={f.id}>
              <div className="rastreio-cabecalho">
                <div>
                  <span className="fonte-orgao">{f.orgao}</span>
                  <h3 className="fonte-url">{encurtar(f.url)}</h3>
                </div>
                <span className="fonte-usos">{f.usos.length} números</span>
              </div>
              <ul className="hipotese-lista">
                {f.usos.map((h, i) => (
                  <HipoteseLinha key={`${h.chave}-${i}`} h={h} esconderFonte />
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      <div className="rotation-callout">
        <span className="callout-icon" aria-hidden="true">
          <Icon name="info" size={15} />
        </span>
        <p>
          {resultados.dados.observacao || "Toda hipótese acima carrega fonte, método e URL."}
        </p>
      </div>
    </section>
  );
}

function HipoteseLinha({ h, esconderFonte }: { h: Hipotese; esconderFonte?: boolean }) {
  const pendente = h.fonte_url.startsWith("MOCK://");
  const externa = h.fonte_url.startsWith("http");
  return (
    <li className={`hipotese ${pendente ? "pendente" : ""}`}>
      <span className="hipotese-chave">{chaveLabel(h.chave)}</span>
      <span className="hipotese-valor">{h.valor}</span>
      <span className="hipotese-metodo">{h.metodo}</span>
      {!esconderFonte &&
        (externa ? (
          <a
            className="hipotese-fonte"
            href={h.fonte_url}
            target="_blank"
            rel="noreferrer"
          >
            <Icon name="arrow" size={12} /> fonte
          </a>
        ) : (
          <span className="hipotese-fonte interna" title={h.fonte_url}>
            <Icon name="check" size={12} /> interno
          </span>
        ))}
    </li>
  );
}

function chaveLabel(chave: string) {
  return chave
    .replace(/_/g, " ")
    .replace("preco", "preço")
    .replace("prod", "prod")
    .replace(/^./, (c) => c.toUpperCase());
}

function corCultura(nome: string) {
  const n = nome.toLowerCase();
  if (n.includes("soja") && !n.includes("milho")) return "#d9b64a";
  if (n.includes("milho") && n.includes("safrinha")) return "#c97a2b";
  if (n.includes("milho")) return "#e4a13c";
  if (n.includes("feij")) return "#b07a4c";
  if (n.includes("sorgo")) return "#9a6b3f";
  if (n.includes("capital")) return PERFIL_TONE_HEX.conservador;
  return "#9a6b3f";
}

function brlCurto(valor: number) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  }).format(valor);
}

function encurtar(url: string) {
  if (url.startsWith("MOCK://")) return url.replace("MOCK://hackatohm/", "");
  try {
    const u = new URL(url);
    return `${u.hostname.replace("www.", "")}${u.pathname}`.slice(0, 60);
  } catch {
    return url.slice(0, 60);
  }
}
