import { useMemo, useState, type CSSProperties } from "react";
import { Icon } from "./Icon";
import {
  CROP_META,
  MONTH_COLUMNS,
  TEXTURA_META,
  culturasViaveis,
  formatDecendioLong,
  formatJanela,
  grupoDoTalhao,
  riskTone,
  riscoNoDecendio,
  type CropKey,
  type Talhao,
  type ZarcData,
} from "../types";

interface ZarcPanelProps {
  zarc: ZarcData;
  talhao: Talhao;
}

export function ZarcPanel({ zarc, talhao }: ZarcPanelProps) {
  const grupo = grupoDoTalhao(talhao);
  const viaveis = useMemo(() => culturasViaveis(zarc, grupo), [zarc, grupo]);
  const [selectedCrop, setSelectedCrop] = useState<CropKey>(viaveis[0]?.key ?? "soja");
  const crop = viaveis.find((item) => item.key === selectedCrop) ?? viaveis[0];
  const meta = crop ? CROP_META[crop.key] : CROP_META.soja;
  const janela = crop?.janela;

  if (!crop || !janela) {
    return (
      <aside className="panel zarc-panel">
        <div className="panel-heading">
          <div>
            <span className="section-kicker">D1 · ZARC</span>
            <h2>Janelas do talhão</h2>
          </div>
        </div>
        <p className="empty-window">Nenhuma cultura com janela viável neste solo.</p>
      </aside>
    );
  }

  return (
    <aside className="panel zarc-panel">
      <div className="panel-heading">
        <div>
          <span className="section-kicker">D1 · ZARC</span>
          <h2>Janelas do talhão</h2>
        </div>
        <span className="real-badge">
          <span className="real-dot" aria-hidden="true" /> dados reais
        </span>
      </div>

      <div className="zarc-target">
        <div>
          <strong>{talhao.nome}</strong>
          <span>
            {talhao.areaHa} ha · grupo {grupo} · {TEXTURA_META[talhao.textura].solo}
          </span>
        </div>
        <span className={`target-irrigation ${talhao.irrigacao ? "on" : ""}`}>
          <Icon name="droplet" size={13} />
          {talhao.irrigacao ? "irrigado" : "sequeiro"}
        </span>
      </div>

      <div className="crop-tabs" role="tablist" aria-label="Culturas com janela no talhão">
        {viaveis.map((item) => (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={item.key === crop.key}
            className={`crop-tab ${item.key === crop.key ? "active" : ""}`}
            style={{ "--crop": item.meta.color, "--crop-ink": item.meta.ink } as CSSProperties}
            onClick={() => setSelectedCrop(item.key)}
          >
            <span className="crop-tab-dot" />
            {item.meta.shortLabel}
            <small>{item.janela.decendios.length}</small>
          </button>
        ))}
      </div>

      <div className="calendar-block" role="tabpanel" aria-label={`Calendário ZARC de ${meta.label}`}>
        <div className="calendar-grid">
          <span className="calendar-corner" aria-hidden="true" />
          {MONTH_COLUMNS.map((month) => (
            <span key={`${month.label}-${month.year}`} className="calendar-month">
              <b>{month.label}</b>
              <i>{String(month.year).slice(2)}</i>
            </span>
          ))}
          {[0, 1, 2].map((row) => (
            <div className="calendar-row" key={row}>
              <span className="calendar-row-label">{row + 1}º</span>
              {MONTH_COLUMNS.map((month) => {
                const dec = month.decendios[row];
                const risk = riscoNoDecendio(zarc, crop.key, grupo, dec);
                return (
                  <span
                    key={dec}
                    role="img"
                    className={`calendar-cell tone-${riskTone(risk)}`}
                    title={
                      risk === null
                        ? `${formatDecendioLong(dec)} · fora da janela`
                        : `${formatDecendioLong(dec)} · risco ${risk}%`
                    }
                    aria-label={
                      risk === null
                        ? `${formatDecendioLong(dec)}: fora da janela`
                        : `${formatDecendioLong(dec)}: risco ${risk}%`
                    }
                  >
                    {risk ?? ""}
                  </span>
                );
              })}
            </div>
          ))}
        </div>

        <div className="risk-legend" role="group" aria-label="Legenda de risco ZARC">
          <span><i className="legend-dot low" /> 20%</span>
          <span><i className="legend-dot mid" /> 30%</span>
          <span><i className="legend-dot high" /> 40%</span>
          <span><i className="legend-dot off" /> fora da janela</span>
        </div>
      </div>

      <div className="window-summary">
        <div className="window-summary-head">
          <span>Janela viável · {meta.label}</span>
          <em>{janela.decendios.length} decêndios</em>
        </div>
        <strong>{formatJanela(janela.decendios)}</strong>
        <p>{meta.descricao}</p>
      </div>

      <div className={`irrigation-note ${talhao.irrigacao ? "on" : ""}`}>
        <Icon name={talhao.irrigacao ? "droplet" : "info"} size={15} />
        <p>
          {talhao.irrigacao
            ? "Irrigação habilitada. O v0 ainda usa as janelas de sequeiro; o manejo irrigado entra na próxima rodada do modelo."
            : "Talhão em sequeiro. Ative a irrigação para habilitar esse manejo na otimização."}
        </p>
      </div>

      <div className="zarc-foot">
        <span>
          <Icon name="info" size={13} />
          Corte risco ≤ 40% · melhor ciclo · {janela.solo_usado}
        </span>
        <a href={zarc.fonte.portal} target="_blank" rel="noreferrer">
          ZARC/MAPA
        </a>
      </div>
    </aside>
  );
}
