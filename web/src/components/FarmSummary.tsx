import { useEffect, useRef, useState } from "react";
import { Icon } from "./Icon";
import {
  FAMILIA_META,
  FAMILIAS,
  PERFIL_META,
  grupoDoTalhao,
  type FamiliaCultura,
  type PerfilRisco,
  type Talhao,
} from "../types";

interface FarmSummaryProps {
  totalArea: number;
  talhoes: Talhao[];
  culturasCount: number;
  culturas: FamiliaCultura[];
  perfil: PerfilRisco;
  diferenca: number;
  onChangeArea: (id: string, areaHa: number) => void;
  onToggleCultura: (familia: FamiliaCultura) => void;
  onPerfil: (perfil: PerfilRisco) => void;
  onRemoverTalhao: (id: string) => void;
  onAdicionarTalhao: () => void;
}

const numero = new Intl.NumberFormat("pt-BR");
const PERFIS: PerfilRisco[] = ["arrojado", "equilibrado", "conservador"];
const TONE_COLOR: Record<string, string> = {
  clay: "#b8643a",
  green: "#1d4d33",
  blue: "#426c75",
};

export function FarmSummary({
  totalArea,
  talhoes,
  culturasCount,
  culturas,
  perfil,
  diferenca,
  onChangeArea,
  onToggleCultura,
  onPerfil,
  onRemoverTalhao,
  onAdicionarTalhao,
}: FarmSummaryProps) {
  const irrigados = talhoes.filter((talhao) => talhao.irrigacao).length;
  const [perfilOpen, setPerfilOpen] = useState(false);
  const perfilRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!perfilOpen) return;
    function clicarFora(event: PointerEvent) {
      if (perfilRef.current && !perfilRef.current.contains(event.target as Node)) {
        setPerfilOpen(false);
      }
    }
    function tecla(event: KeyboardEvent) {
      if (event.key === "Escape") setPerfilOpen(false);
    }
    document.addEventListener("pointerdown", clicarFora);
    document.addEventListener("keydown", tecla);
    return () => {
      document.removeEventListener("pointerdown", clicarFora);
      document.removeEventListener("keydown", tecla);
    };
  }, [perfilOpen]);

  return (
    <section className="panel farm-panel" aria-label="Resumo da área cadastrada">
      <div className="panel-heading">
        <div>
          <span className="section-kicker">Área cadastrada</span>
          <h2>Seu cenário atual</h2>
        </div>
        <span className="farm-badge">
          <Icon name="pin" size={14} />
          Patos de Minas
        </span>
      </div>

      <div className="farm-grid">
        <article className={`stat stat-area ${diferenca !== 0 ? "has-warning" : ""}`}>
          <span className="stat-label">Área total</span>
          <div className="stat-value">
            <strong>{numero.format(totalArea)}</strong>
            <span>ha</span>
          </div>
          <div className="area-track" aria-hidden="true">
            <span
              className={diferenca > 0 ? "over" : ""}
              style={{ width: `${Math.min((totalArea / 600) * 100, 100)}%` }}
            />
          </div>
          <span className="stat-hint">
            {diferenca === 0
              ? "de 600 ha de referência"
              : diferenca > 0
                ? `${numero.format(diferenca)} ha acima do desafio (600 ha)`
                : `${numero.format(Math.abs(diferenca))} ha abaixo do desafio (600 ha)`}
          </span>
        </article>

        <article className="stat">
          <span className="stat-label">Talhões</span>
          <div className="stat-value stat-stepper">
            <button
              type="button"
              className="step-btn"
              disabled={talhoes.length <= 1}
              aria-label="Remover o último talhão"
              title="Remover o último talhão"
              onClick={() => {
                const ultimo = talhoes[talhoes.length - 1];
                if (ultimo) onRemoverTalhao(ultimo.id);
              }}
            >
              −
            </button>
            <strong>{talhoes.length}</strong>
            <button
              type="button"
              className="step-btn"
              aria-label="Adicionar talhão"
              title="Adicionar talhão"
              onClick={onAdicionarTalhao}
            >
              +
            </button>
          </div>
          <span className="stat-hint">
            {irrigados === 0 ? "todos em sequeiro" : `${irrigados} com irrigação`}
          </span>
        </article>

        <div className="stat farm-culturas">
          <span className="stat-label">Culturas da fazenda</span>
          <div className="farm-cultura-chips" role="group" aria-label="Culturas que a fazenda planta">
            {FAMILIAS.map((familia) => {
              const meta = FAMILIA_META[familia];
              const ativo = culturas.includes(familia);
              return (
                <button
                  key={familia}
                  type="button"
                  className={`farm-cultura-chip ${ativo ? "active" : ""}`}
                  aria-pressed={ativo}
                  title={ativo ? "Incluída no cenário" : "Incluir no cenário"}
                  onClick={() => onToggleCultura(familia)}
                >
                  <span className="chip-dot" style={{ background: meta.color }} aria-hidden="true" />
                  {meta.label}
                </button>
              );
            })}
          </div>
          <span className="stat-hint">{culturasCount} com janela no cenário</span>
        </div>

        <article className="stat stat-profile" ref={perfilRef}>
          <button
            type="button"
            className="profile-open"
            aria-expanded={perfilOpen}
            aria-haspopup="true"
            title="Escolher perfil de risco"
            onClick={() => setPerfilOpen((aberto) => !aberto)}
          >
            <span className="stat-label">Perfil de risco</span>
            <div className="stat-value stat-text">
              {PERFIL_META[perfil].label}
              <Icon name="chevron" size={16} />
            </div>
            <span className="stat-hint">{PERFIL_META[perfil].hint}</span>
          </button>
          {perfilOpen && (
            <div className="perfil-drawer" role="group" aria-label="Escolher perfil de risco">
              {PERFIS.map((opcao) => {
                const meta = PERFIL_META[opcao];
                const ativa = opcao === perfil;
                return (
                  <button
                    key={opcao}
                    type="button"
                    className={`perfil-option ${ativa ? "is-active" : ""}`}
                    title={meta.hint}
                    onClick={() => {
                      onPerfil(opcao);
                      setPerfilOpen(false);
                    }}
                  >
                    <span
                      className="perfil-option-dot"
                      style={{ background: TONE_COLOR[meta.tone] }}
                      aria-hidden="true"
                    />
                    <span className="perfil-option-copy">
                      <strong>{meta.label}</strong>
                      <small>{meta.hint}</small>
                    </span>
                    {ativa && <Icon name="check" size={14} />}
                  </button>
                );
              })}
            </div>
          )}
        </article>
      </div>

      <div className="farm-alloc">
        <div className="farm-alloc-head">
          <span className="farm-alloc-title">Área por talhão</span>
          <span className="farm-alloc-hint">total livre · ref. 600 ha</span>
        </div>
        {talhoes.map((talhao) => (
          <div className="farm-alloc-row" key={talhao.id}>
            <span className="soil-swatch" data-group={grupoDoTalhao(talhao)} aria-hidden="true" />
            <label className="farm-alloc-name" htmlFor={`area-${talhao.id}`}>
              {talhao.nome}
            </label>
            <span className="farm-alloc-input">
              <input
                id={`area-${talhao.id}`}
                type="number"
                min={0}
                step={10}
                value={talhao.areaHa}
                aria-label={`Área do ${talhao.nome} em hectares`}
                onChange={(event) =>
                  onChangeArea(talhao.id, Math.max(0, Number(event.target.value) || 0))
                }
              />
              <em>ha</em>
            </span>
            <button
              type="button"
              className="farm-alloc-remove"
              disabled={talhoes.length <= 1}
              aria-label={`Remover ${talhao.nome}`}
              title={`Remover ${talhao.nome}`}
              onClick={() => onRemoverTalhao(talhao.id)}
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
