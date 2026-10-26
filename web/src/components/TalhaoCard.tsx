import type { CSSProperties } from "react";
import { Icon } from "./Icon";
import {
  CROP_META,
  TEXTURA_META,
  culturasViaveis,
  grupoDoTalhao,
  type Talhao,
  type Textura,
  type ZarcData,
} from "../types";

interface TalhaoCardProps {
  talhao: Talhao;
  index: number;
  selected: boolean;
  zarc: ZarcData;
  onSelect: () => void;
  onChange: (patch: Partial<Talhao>) => void;
}

const TEXTURAS: Textura[] = ["arenoso", "medio", "argiloso"];

const SOIL_COLOR: Record<number, string> = {
  1: "#b58b4c",
  2: "#7f8a52",
  3: "#9a6040",
};

export function TalhaoCard({
  talhao,
  index,
  selected,
  zarc,
  onSelect,
  onChange,
}: TalhaoCardProps) {
  const grupo = grupoDoTalhao(talhao);
  const solo = TEXTURA_META[talhao.textura].solo;
  const viaveis = culturasViaveis(zarc, grupo);
  const soilColor = SOIL_COLOR[grupo];

  return (
    <article
      className={`talhao-card ${selected ? "is-selected" : ""}`}
      style={{ "--soil": soilColor } as CSSProperties}
      onClick={onSelect}
    >
      <div className="talhao-head">
        <span className="talhao-index" aria-hidden="true">
          {String(index + 1).padStart(2, "0")}
        </span>
        <div className="talhao-name-wrap">
          <input
            className="talhao-name"
            value={talhao.nome}
            aria-label={`Nome do talhão ${index + 1}`}
            onFocus={onSelect}
            onChange={(event) => onChange({ nome: event.target.value })}
          />
          <span className="talhao-sub">
            <Icon name="layers" size={13} />
            Grupo {grupo} · {solo}
            <span className="sep-dot" />
            {TEXTURA_META[talhao.textura].label.toLowerCase()}
          </span>
        </div>
        <label className="talhao-area">
          <span>Área</span>
          <span className="area-input-wrap">
            <input
              type="number"
              min={0}
              step={10}
              value={talhao.areaHa}
              aria-label={`Área do ${talhao.nome} em hectares`}
              onFocus={onSelect}
              onChange={(event) =>
                onChange({ areaHa: Math.max(0, Number(event.target.value) || 0) })
              }
            />
            <em>ha</em>
          </span>
        </label>
      </div>

      <div className="talhao-controls">
        <div className="texture-field">
          <span className="field-label">Textura do solo</span>
          <div className="texture-switch" role="group" aria-label="Textura do solo">
            {TEXTURAS.map((textura) => (
              <button
                key={textura}
                type="button"
                className={talhao.textura === textura ? "active" : ""}
                onClick={(event) => {
                  event.stopPropagation();
                  onSelect();
                  onChange({ textura });
                }}
                aria-pressed={talhao.textura === textura}
                title={TEXTURA_META[textura].hint}
              >
                {TEXTURA_META[textura].label}
              </button>
            ))}
          </div>
        </div>

        <button
          type="button"
          role="switch"
          aria-checked={talhao.irrigacao}
          className={`irrigation-switch ${talhao.irrigacao ? "on" : ""}`}
          onClick={(event) => {
            event.stopPropagation();
            onSelect();
            onChange({ irrigacao: !talhao.irrigacao });
          }}
        >
          <span className="switch-track" aria-hidden="true">
            <span className="switch-thumb" />
          </span>
          <span className="switch-copy">
            <Icon name="droplet" size={14} />
            Irrigação
          </span>
        </button>
      </div>

      <div className="talhao-foot">
        <span className="crop-count">
          <strong>{viaveis.length}</strong> culturas com janela
        </span>
        <div className="crop-dots" aria-label="Culturas com janela neste talhão">
          {viaveis.slice(0, 5).map(({ key, meta }) => (
            <span
              key={key}
              className="crop-dot"
              style={{ background: CROP_META[key].color }}
              title={meta.label}
            />
          ))}
          {viaveis.length > 5 && <span className="crop-more">+{viaveis.length - 5}</span>}
        </div>
        <button
          type="button"
          className="talhao-select"
          onClick={(event) => {
            event.stopPropagation();
            onSelect();
          }}
        >
          {selected ? "Em análise" : "Ver janelas"}
          <Icon name={selected ? "check" : "arrow"} size={14} />
        </button>
      </div>
    </article>
  );
}
