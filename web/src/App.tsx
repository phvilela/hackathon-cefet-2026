import { useEffect, useMemo, useState } from "react";
import { Comparacao } from "./components/Comparacao";
import { Header } from "./components/Header";
import { Icon } from "./components/Icon";
import { Rastreabilidade } from "./components/Rastreabilidade";
import { RotationsCard } from "./components/RotationsCard";
import { ScenarioBar } from "./components/ScenarioBar";
import { TalhaoCard } from "./components/TalhaoCard";
import { ZarcPanel } from "./components/ZarcPanel";
import resultadosRaw from "./data/results.json";
import zarcRaw from "./data/zarc.json";
import {
  carregarCenario,
  cenarioDoPreset,
  exportarCenario,
  salvarCenario,
} from "./lib/cenario";
import {
  PERFIL_META,
  culturasViaveis,
  grupoDoTalhao,
  type CenarioState,
  type PerfilRisco,
  type Resultados,
  type Talhao,
  type ZarcData,
} from "./types";

const zarc = zarcRaw as unknown as ZarcData;
const resultados = resultadosRaw as unknown as Resultados;
const AREA_REFERENCIA = 600;
const numero = new Intl.NumberFormat("pt-BR");

type Tela = "talhoes" | "comparacao" | "rastreabilidade";

function cenarioInicial(): CenarioState {
  return carregarCenario() ?? cenarioDoPreset("desafio");
}

export default function App() {
  const [cenario, setCenario] = useState<CenarioState>(cenarioInicial);
  const [selectedId, setSelectedId] = useState("T1");
  const [tela, setTela] = useState<Tela>("talhoes");

  useEffect(() => {
    salvarCenario(cenario);
  }, [cenario]);

  const totalArea = cenario.talhoes.reduce((acc, talhao) => acc + talhao.areaHa, 0);
  const irrigados = cenario.talhoes.filter((talhao) => talhao.irrigacao).length;
  const selected = cenario.talhoes.find((talhao) => talhao.id === selectedId) ?? cenario.talhoes[0];
  const perfil = PERFIL_META[cenario.perfil];

  const culturas = useMemo(() => {
    const set = new Set<string>();
    for (const talhao of cenario.talhoes) {
      for (const cultura of culturasViaveis(zarc, grupoDoTalhao(talhao))) {
        set.add(cultura.key);
      }
    }
    return set;
  }, [cenario.talhoes]);

  function aplicarPreset(id: string) {
    setCenario(cenarioDoPreset(id));
    setSelectedId("T1");
  }

  function alterarPerfil(novo: PerfilRisco) {
    setCenario((atual) => ({ ...atual, perfil: novo, preset: "personalizado" }));
  }

  function alterarTalhao(id: string, patch: Partial<Talhao>) {
    setCenario((atual) => ({
      ...atual,
      preset: "personalizado",
      talhoes: atual.talhoes.map((talhao) =>
        talhao.id === id ? { ...talhao, ...patch } : talhao,
      ),
    }));
  }

  const diferenca = totalArea - AREA_REFERENCIA;

  return (
    <div className="app">
      <Header tela={tela} onNavigate={setTela} />

      <main className="page">
        {tela === "comparacao" ? (
          <Comparacao resultados={resultados} />
        ) : tela === "rastreabilidade" ? (
          <Rastreabilidade resultados={resultados} />
        ) : (
          <>
            <section className="hero">
          <div className="hero-copy">
            <div className="eyebrow">
              <span className="eyebrow-rule" />
              Patos de Minas · MG
              <span className="eyebrow-sep" />
              Safra 2026/27
            </div>
            <h1>
              Cada talhão tem uma janela.
              <br />
              <em>O ZARC mostra quando.</em>
            </h1>
            <p>
              Comece pela textura e pela área de cada pedaço da fazenda. A recomendação
              cruza a adequação real do ZARC com margem e risco, sem esconder nenhuma
              premissa.
            </p>
            <div className="hero-chips">
              <span>
                <Icon name="pin" size={14} /> IBGE 3148004
              </span>
              <span>
                <Icon name="layers" size={14} /> 3 grupos de solo
              </span>
              <span>
                <Icon name="calendar" size={14} /> janelas decendiais
              </span>
            </div>
          </div>

          <div className="hero-stats">
            <div className={`stat stat-area ${diferenca !== 0 ? "has-warning" : ""}`}>
              <span className="stat-label">Área cadastrada</span>
              <div className="stat-value">
                <strong>{numero.format(totalArea)}</strong>
                <span>ha</span>
              </div>
              <div className="area-track" aria-hidden="true">
                <span
                  className={diferenca > 0 ? "over" : ""}
                  style={{ width: `${Math.min((totalArea / AREA_REFERENCIA) * 100, 100)}%` }}
                />
              </div>
              <span className="stat-hint">
                {diferenca === 0
                  ? "de 600 ha de referência"
                  : `${diferenca > 0 ? "+" : ""}${numero.format(diferenca)} ha vs. referência de 600 ha`}
              </span>
            </div>

            <div className="stat">
              <span className="stat-label">Talhões</span>
              <div className="stat-value">
                <strong>{cenario.talhoes.length}</strong>
              </div>
              <span className="stat-hint">
                {irrigados === 0 ? "todos em sequeiro" : `${irrigados} com irrigação`}
              </span>
            </div>

            <div className="stat">
              <span className="stat-label">Culturas com janela</span>
              <div className="stat-value">
                <strong>{culturas.size}</strong>
              </div>
              <span className="stat-hint">entre soja, milho, feijão e sorgo</span>
            </div>

            <div className="stat stat-profile">
              <span className="stat-label">Perfil de risco</span>
              <div className="stat-value stat-text">{perfil.label}</div>
              <span className="stat-hint">{perfil.hint}</span>
            </div>
          </div>
        </section>

        <ScenarioBar
          cenario={cenario}
          onPreset={aplicarPreset}
          onPerfil={alterarPerfil}
          onExport={() => exportarCenario(cenario, perfil.label)}
          onReset={() => aplicarPreset("desafio")}
        />

        <div className="workspace">
          <div className="workspace-left">
            <section className="talhoes-section">
              <div className="section-heading">
                <div>
                  <span className="section-kicker">Cadastro</span>
                  <h2>Seus talhões</h2>
                  <p>
                    A textura define o grupo de solo do ZARC. A área entra no balanceamento
                    da recomendação.
                  </p>
                </div>
                <div className="section-meta">
                  <span>{cenario.talhoes.length} talhões</span>
                  <span>{numero.format(totalArea)} ha</span>
                </div>
              </div>

              <div className="talhao-list">
                {cenario.talhoes.map((talhao, index) => (
                  <TalhaoCard
                    key={talhao.id}
                    talhao={talhao}
                    index={index}
                    selected={selected.id === talhao.id}
                    zarc={zarc}
                    onSelect={() => setSelectedId(talhao.id)}
                    onChange={(patch) => alterarTalhao(talhao.id, patch)}
                  />
                ))}
              </div>
            </section>

            <RotationsCard zarc={zarc} talhao={selected} />
          </div>

          <ZarcPanel
            key={`${selected.id}-${selected.textura}`}
            zarc={zarc}
            talhao={selected}
          />
        </div>
          </>
        )}
      </main>

      <footer className="site-footer">
        <div className="footer-brand">
          <span className="brand-mark small" aria-hidden="true">
            <Icon name="leaf" size={17} />
          </span>
          <div>
            <strong>O que plantar?</strong>
            <span>Embrapa · HackatOhm 2026</span>
          </div>
        </div>
        <p className="footer-note">
          Janelas ZARC reais da safra 2026/27 e margens do Monte Carlo. Cada número
          tem fonte, método e URL — veja em Rastreabilidade.
        </p>
        <div className="footer-sources">
          <a
            href="https://dados.agricultura.gov.br/dataset/tabua-de-risco-zoneamento-agricola-de-risco-climatico"
            target="_blank"
            rel="noreferrer"
          >
            ZARC/MAPA
          </a>
          <a href="https://sidra.ibge.gov.br/tabela/839" target="_blank" rel="noreferrer">
            PAM/IBGE
          </a>
          <a
            href="https://portal.inmet.gov.br/dadoshistoricos"
            target="_blank"
            rel="noreferrer"
          >
            INMET A523
          </a>
          <a href="https://power.larc.nasa.gov/" target="_blank" rel="noreferrer">
            NASA POWER
          </a>
        </div>
      </footer>
    </div>
  );
}
