import { Icon } from "./Icon";
import {
  PERFIL_META,
  PERFIL_TONE_HEX,
  brl,
  ha,
  type PerfilRisco,
  type Resultados,
} from "../types";
import "../guia.css";

type TelaDestino = "talhoes" | "comparacao" | "rastreabilidade";

interface GuiaProps {
  resultados: Resultados;
  onNavigate: (tela: TelaDestino) => void;
}

const PERFIS: PerfilRisco[] = ["arrojado", "equilibrado", "conservador"];

const CAMADAS = [
  {
    titulo: "Adequação",
    pergunta: "O que pode ser plantado aqui, e quando?",
    detalhe:
      "Lê a tábua de risco climático do ZARC 2026/27 e, para o solo de cada talhão, mostra as janelas de plantio e quais rotações fecham.",
    saida: "Janelas por decêndio",
  },
  {
    titulo: "Margem × chance de prejuízo",
    pergunta: "Quanto rende cada opção, e com que chance de prejuízo?",
    detalhe:
      "Combina preço e produtividade históricos com o custo de produção da Conab. Uma simulação de Monte Carlo estima a margem e a chance de ela ficar negativa.",
    saida: "Margem R$/ha e chance de prejuízo em ‰",
  },
  {
    titulo: "Alocação",
    pergunta: "Quantos hectares em cada opção?",
    detalhe:
      "Um otimizador divide a área entre as rotações viáveis, primeiro pela maior margem e depois pela menor chance de prejuízo, e devolve um menu de planos.",
    saida: "Arrojado · Equilibrado · Conservador",
  },
] as const;

const ROTACOES = [
  "Soja → milho 2ª safra",
  "Soja solteira",
  "Soja → sorgo 2ª safra",
  "Feijão → sorgo 2ª safra",
  "Milho 1ª safra",
  "Girassol (solteiro)",
  "Amendoim (solteiro)",
  "Arroz (solteiro)",
  "Algodão (solteiro)",
  "Soja → feijão 2ª safra",
  "Capital em pousio (não plantar)",
];

const DESAFIO = [
  {
    icone: "calendar",
    titulo: "O “quando” já existe",
    texto:
      "O ZARC, do MAPA e da Embrapa, indica as épocas de menor risco climático para cada cultura, município e tipo de solo.",
  },
  {
    icone: "layers",
    titulo: "O “o quê” ainda não",
    texto:
      "Ninguém junta janela, solo, custo e preço numa recomendação que o produtor consiga conferir. É a lacuna que o projeto cobre.",
  },
  {
    icone: "shield",
    titulo: "Sem caixa-preta",
    texto:
      "Cada número da resposta carrega hipótese, método e fonte clicável. A decisão final continua sendo do produtor.",
  },
] as const;

const PASSOS = [
  {
    tela: "talhoes",
    icone: "pin",
    titulo: "Talhões",
    texto:
      "Informe área, textura e irrigação de cada talhão e veja as janelas do ZARC para o seu solo.",
  },
  {
    tela: "comparacao",
    icone: "trend",
    titulo: "Comparação",
    texto:
      "Compare os planos na fronteira de margem × chance de prejuízo e escolha o perfil que combina com a sua safra.",
  },
  {
    tela: "rastreabilidade",
    icone: "check",
    titulo: "Rastreabilidade",
    texto:
      "Abra a fonte de cada hipótese e confira de onde vem cada número da recomendação.",
  },
] as const;

export function Guia({ resultados, onNavigate }: GuiaProps) {
  const { cenario, dados, planos, robustez, fronteira_pareto: fronteira } = resultados;
  const area = Number(cenario.area_total_ha ?? 0);
  const municipio = String(cenario.municipio ?? "Patos de Minas");
  const safra = String(cenario.safra ?? "2026/27");
  const nTalhoes = Number(cenario.n_talhoes ?? 0);
  const nRotacoes = Number(cenario.n_rotacoes ?? 0);
  const dadosReais = dados.status === "REAL";

  function ir(tela: TelaDestino) {
    onNavigate(tela);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <div className="painel-guia">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <section className="guia-hero" aria-labelledby="guia-titulo">
        <span className="eyebrow">
          <span className="eyebrow-rule" aria-hidden="true" />
          Guia do projeto
          <span className="eyebrow-sep" aria-hidden="true" />
          {municipio} · MG · Safra {safra}
        </span>
        <h1 id="guia-titulo">
          Plante na janela certa. <em>Decida com números.</em>
        </h1>
        <p className="guia-lede">
          O Safra Certa cruza as janelas oficiais do ZARC com margem e chance de prejuízo
          de cada rotação e devolve um menu de planos para a sua fazenda, com a fonte de
          cada número à vista.
        </p>
        <div className="guia-acoes">
          <button type="button" className="guia-btn primario" onClick={() => ir("talhoes")}>
            Cadastrar meus talhões <Icon name="arrow" size={16} />
          </button>
          <a className="guia-btn" href="#guia-metodos">
            Ver os métodos
          </a>
        </div>

        <div className="guia-stats">
          <div className="stat stat-area">
            <span className="stat-label">Fazenda de referência</span>
            <div className="stat-value">
              <strong>{ha(area)}</strong>
              <span>hectares</span>
            </div>
          </div>
          <div className="stat">
            <span className="stat-label">Talhões</span>
            <div className="stat-value">
              <strong>{nTalhoes}</strong>
              <span>por tipo de solo</span>
            </div>
          </div>
          <div className="stat">
            <span className="stat-label">Rotações</span>
            <div className="stat-value">
              <strong>{nRotacoes}</strong>
              <span>em avaliação</span>
            </div>
          </div>
          <div className="stat">
            <span className="stat-label">Planos na fronteira</span>
            <div className="stat-value">
              <strong>{fronteira.length}</strong>
              <span>não dominados</span>
            </div>
          </div>
        </div>
      </section>

      {/* ── O desafio ────────────────────────────────────────────────────── */}
      <section className="guia-secao" aria-labelledby="guia-desafio">
        <div className="section-heading">
          <div>
            <span className="section-kicker">O desafio</span>
            <h2 id="guia-desafio">Escolher o que plantar é decidir sob incerteza</h2>
            <p>
              Em {municipio}, soja, milho, feijão e sorgo dependem de janela de plantio,
              solo, custo de produção e preço de venda. Errar a época ou a cultura pesa na
              margem da safra inteira.
            </p>
          </div>
        </div>
        <div className="guia-grade">
          {DESAFIO.map((item) => (
            <article className="panel guia-card" key={item.titulo}>
              <span className="guia-icone" aria-hidden="true">
                <Icon name={item.icone} size={20} />
              </span>
              <h3>{item.titulo}</h3>
              <p>{item.texto}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ── A solução ────────────────────────────────────────────────────── */}
      <section className="guia-secao" aria-labelledby="guia-solucao">
        <div className="panel solution-panel guia-solucao">
          <span className="section-kicker light">A solução</span>
          <h2 id="guia-solucao">Três perguntas encadeadas</h2>
          <p className="solution-lede">
            A decisão vira um pipeline em que cada etapa responde uma pergunta e entrega
            um resultado que a próxima usa.
          </p>

          <ol className="solution-list">
            {CAMADAS.map((camada, index) => (
              <li key={camada.titulo}>
                <span className="solution-index">{String(index + 1).padStart(2, "0")}</span>
                <span className="solution-copy">
                  <strong>
                    {camada.titulo} · {camada.pergunta}
                  </strong>
                  <small>{camada.detalhe}</small>
                </span>
                <span className="solution-status ok">{camada.saida}</span>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* ── Métodos ──────────────────────────────────────────────────────── */}
      <section className="guia-secao" id="guia-metodos" aria-labelledby="guia-metodos-titulo">
        <div className="section-heading">
          <div>
            <span className="section-kicker">Métodos aplicados</span>
            <h2 id="guia-metodos-titulo">O que está por trás da recomendação</h2>
            <p>Cada técnica responde a uma pergunta específica da decisão de plantio.</p>
          </div>
          <div className="section-meta">
            <span className={`real-badge ${dadosReais ? "is-real" : "is-warn"}`}>
              <span className="real-dot" aria-hidden="true" />
              dados {dados.status}
            </span>
          </div>
        </div>

        <div className="guia-metodos">
          <article className="panel guia-metodo">
            <span className="guia-metodo-rotulo">Adequação</span>
            <h3>ZARC 2026/27</h3>
            <p>
              Zoneamento Agrícola de Risco Climático. Define os decêndios de plantio com
              risco de perda por seca (ZARC) de 20%, 30% ou 40% para cada cultura e
              grupo de solo (arenoso, médio ou argiloso).
            </p>
          </article>
          <article className="panel guia-metodo">
            <span className="guia-metodo-rotulo">Custo</span>
            <h3>Custos de produção Conab</h3>
            <p>
              Custo médio por hectare no Cerrado entra no cálculo da margem de cada
              rotação: margem esperada = preço × produtividade − custo.
            </p>
          </article>
          <article className="panel guia-metodo">
            <span className="guia-metodo-rotulo">Chance de prejuízo</span>
            <h3>Monte Carlo com histórico real</h3>
            <p>
              Reaproveita 31 anos de produtividade (PAM) e preço (SIDRA) do IBGE,
              pareados, com desvios multiplicativos que preservam a correlação entre
              preço e produtividade. O indicador é a chance de a margem ficar negativa
              (prejuízo).
            </p>
          </article>
          <article className="panel guia-metodo">
            <span className="guia-metodo-rotulo">Decisão</span>
            <h3>Otimização CP-SAT lexicográfica</h3>
            <p>
              Programação por restrições com variáveis inteiras: primeiro maximiza a
              margem total, depois, mantendo essa margem, minimiza os hectares com
              chance de prejuízo. Respeita a área de cada talhão e as janelas viáveis.
            </p>
          </article>
          <article className="panel guia-metodo">
            <span className="guia-metodo-rotulo">Menu de planos</span>
            <h3>Fronteira de Pareto</h3>
            <p>
              Restringe os hectares com chance de prejuízo aos poucos (método
              ε-constraint) e resolve de novo. Os{" "}
              {fronteira.length} planos resultantes são não dominados. O ponto de melhor
              equilíbrio, o knee, vira o perfil Equilibrado.
            </p>
          </article>
          <article className="panel guia-metodo">
            <span className="guia-metodo-rotulo">Robustez</span>
            <h3>Teste de estresse de ±{robustez.jitter_percent}%</h3>
            <p>
              Perturba as margens em até ±{robustez.jitter_percent}% em{" "}
              {robustez.runs} cenários e re-resolve. Mede se a recomendação muda, não só
              se o lucro muda.
            </p>
          </article>
        </div>

        <div className="guia-rotacoes">
          <span className="guia-rotacoes-titulo">Rotações consideradas</span>
          <ul>
            {ROTACOES.map((rotacao) => (
              <li key={rotacao}>{rotacao}</li>
            ))}
          </ul>
        </div>
      </section>

      {/* ── Resultado do cenário ─────────────────────────────────────────── */}
      <section className="guia-secao" aria-labelledby="guia-resultado">
        <div className="section-heading">
          <div>
            <span className="section-kicker">Resultado do cenário</span>
            <h2 id="guia-resultado">Um menu em vez de uma resposta única</h2>
            <p>
              Para a fazenda de {ha(area)} ha em {nTalhoes} talhões, o motor devolve três
              perfis. Quanto mais margem, mais hectares com chance de prejuízo.
            </p>
          </div>
        </div>

        <div className="guia-perfis">
          {PERFIS.map((perfil) => {
            const plano = planos[perfil];
            const meta = PERFIL_META[perfil];
            return (
              <article
                className="panel guia-perfil"
                key={perfil}
                style={{ ["--perfil" as string]: PERFIL_TONE_HEX[perfil] }}
              >
                <span className="guia-perfil-nome">
                  <i aria-hidden="true" />
                  {meta.label}
                </span>
                <p className="guia-perfil-hint">{meta.hint}</p>
                <div className="guia-perfil-numero">
                  <strong>{brl(plano.margem_reais)}</strong>
                  <span>margem total</span>
                </div>
                <div className="guia-perfil-numero secundario">
                  <strong>{ha(plano.ha_sob_risco)} ha</strong>
                  <span>com chance de prejuízo</span>
                </div>
              </article>
            );
          })}
        </div>

        <div className="rotation-callout">
          <span className="callout-icon" aria-hidden="true">
            <Icon name="info" size={15} />
          </span>
          <p>
            {robustez.frase_estabilidade}{" "}
            {dadosReais
              ? "As janelas do ZARC e as margens do Monte Carlo são reais."
              : "Parte das margens ainda é ilustrativa. Trate os planos como demonstração do método."}
          </p>
        </div>
      </section>

      {/* ── Como usar ────────────────────────────────────────────────────── */}
      <section className="guia-secao" aria-labelledby="guia-uso">
        <div className="section-heading">
          <div>
            <span className="section-kicker">Como usar</span>
            <h2 id="guia-uso">Três telas, uma decisão</h2>
          </div>
        </div>
        <div className="guia-grade">
          {PASSOS.map((passo, index) => (
            <button
              type="button"
              className="panel guia-passo"
              key={passo.tela}
              onClick={() => ir(passo.tela)}
            >
              <span className="guia-passo-topo">
                <span className="guia-icone" aria-hidden="true">
                  <Icon name={passo.icone} size={20} />
                </span>
                <span className="guia-passo-num">{String(index + 1).padStart(2, "0")}</span>
              </span>
              <h3>{passo.titulo}</h3>
              <p>{passo.texto}</p>
              <span className="guia-passo-link">
                Abrir <Icon name="arrow" size={14} />
              </span>
            </button>
          ))}
        </div>
      </section>

      {/* ── Chamada final ────────────────────────────────────────────────── */}
      <section className="guia-secao" aria-labelledby="guia-final">
        <div className="panel solution-panel guia-final">
          <div>
            <h2 id="guia-final">Pronto para planejar a próxima safra?</h2>
            <p className="solution-lede">
              Cadastre seus talhões e veja as janelas de plantio para {municipio}.
            </p>
          </div>
          <button type="button" className="guia-btn destaque" onClick={() => ir("talhoes")}>
            Abrir os talhões <Icon name="arrow" size={16} />
          </button>
        </div>
      </section>
    </div>
  );
}
