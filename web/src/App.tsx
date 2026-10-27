import { useEffect, useMemo, useState } from "react";
import { Comparacao } from "./components/Comparacao";
import { Header } from "./components/Header";
import { Icon } from "./components/Icon";
import { FarmSummary } from "./components/FarmSummary";
import { Rastreabilidade } from "./components/Rastreabilidade";
import { ScenarioBar } from "./components/ScenarioBar";
import { SolutionPanel } from "./components/SolutionPanel";
import { TalhaoCard } from "./components/TalhaoCard";
import { ZarcPanel } from "./components/ZarcPanel";
import resultadosRaw from "./data/results.json";
import zarcRaw from "./data/zarc.json";
import {
  carregarCenario,
  cenarioDoPreset,
  exportarCenario,
  renumerarTalhoes,
  salvarCenario,
} from "./lib/cenario";
import {
  FAMILIA_DA_CULTURA,
  PERFIL_META,
  culturasViaveis,
  grupoDoTalhao,
  type CenarioState,
  type FamiliaCultura,
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
  const selected = cenario.talhoes.find((talhao) => talhao.id === selectedId) ?? cenario.talhoes[0];
  const perfil = PERFIL_META[cenario.perfil];

  const culturas = useMemo(() => {
    const set = new Set<string>();
    const familias = new Set(cenario.culturas);
    for (const talhao of cenario.talhoes) {
      for (const { key } of culturasViaveis(zarc, grupoDoTalhao(talhao))) {
        if (familias.has(FAMILIA_DA_CULTURA[key])) set.add(key);
      }
    }
    return set;
  }, [cenario.talhoes, cenario.culturas]);

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

  function alterarCultura(familia: FamiliaCultura) {
    setCenario((atual) => {
      const tem = atual.culturas.includes(familia);
      if (tem && atual.culturas.length === 1) return atual;
      return {
        ...atual,
        preset: "personalizado",
        culturas: tem
          ? atual.culturas.filter((item) => item !== familia)
          : [...atual.culturas, familia],
      };
    });
  }

  function adicionarTalhao() {
    const proximoIndice =
      Math.max(0, ...cenario.talhoes.map((talhao) => Number(talhao.id.replace(/\D/g, "")) || 0)) + 1;
    const novo: Talhao = {
      id: `T${proximoIndice}`,
      nome: `Talhão ${cenario.talhoes.length + 1}`,
      areaHa: 0,
      textura: "medio",
      irrigacao: false,
    };
    setCenario({
      ...cenario,
      preset: "personalizado",
      talhoes: renumerarTalhoes([...cenario.talhoes, novo]),
    });
    setSelectedId(novo.id);
  }

  function removerTalhao(id: string) {
    if (cenario.talhoes.length <= 1) return;
    const restantes = renumerarTalhoes(cenario.talhoes.filter((talhao) => talhao.id !== id));
    setCenario({
      ...cenario,
      preset: "personalizado",
      talhoes: restantes,
    });
    if (selectedId === id) setSelectedId(restantes[0].id);
  }

  const diferenca = totalArea - AREA_REFERENCIA;

  return (
    <div className="app">
      <Header tela={tela} onNavigate={setTela} />

      <main className="page">
        {tela === "comparacao" ? (
          <Comparacao
            resultados={resultados}
            areaTotal={totalArea}
            perfilInicial={cenario.perfil}
          />
        ) : tela === "rastreabilidade" ? (
          <Rastreabilidade resultados={resultados} culturas={cenario.culturas} />
        ) : (
          <>
            <section className="summary-grid">
              <FarmSummary
                totalArea={totalArea}
                talhoes={cenario.talhoes}
                culturasCount={culturas.size}
                culturas={cenario.culturas}
                perfil={cenario.perfil}
                diferenca={diferenca}
                onChangeArea={(id, areaHa) => alterarTalhao(id, { areaHa })}
                onToggleCultura={alterarCultura}
                onPerfil={alterarPerfil}
                onRemoverTalhao={removerTalhao}
                onAdicionarTalhao={adicionarTalhao}
              />
              <SolutionPanel
                zarc={zarc}
                talhoes={cenario.talhoes}
                talhao={selected}
                culturas={cenario.culturas}
                onSelectTalhao={setSelectedId}
              />
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
            <strong>Safra Certa</strong>
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
