import { Icon } from "./Icon";
import { PRESETS } from "../lib/cenario";
import { PERFIL_META, type CenarioState, type PerfilRisco } from "../types";

interface ScenarioBarProps {
  cenario: CenarioState;
  onPreset: (id: string) => void;
  onPerfil: (perfil: PerfilRisco) => void;
  onExport: () => void;
  onReset: () => void;
}

const PERFIS: PerfilRisco[] = ["arrojado", "equilibrado", "conservador"];

export function ScenarioBar({
  cenario,
  onPreset,
  onPerfil,
  onExport,
  onReset,
}: ScenarioBarProps) {
  return (
    <section className="scenario-bar" aria-label="Cenários e perfil de risco">
      <div className="scenario-presets">
        <span className="scenario-label">
          <Icon name="sliders" size={14} /> Cenário
        </span>
        <div className="preset-list">
          {PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              className={`preset-chip ${cenario.preset === preset.id ? "active" : ""}`}
              onClick={() => onPreset(preset.id)}
              aria-pressed={cenario.preset === preset.id}
              title={preset.hint}
            >
              {preset.label}
            </button>
          ))}
          {cenario.preset === "personalizado" && (
            <span className="preset-custom">Personalizado</span>
          )}
        </div>
      </div>

      <div className="scenario-profile">
        <span className="scenario-label">Perfil de risco</span>
        <div className="profile-options" role="group" aria-label="Perfil de risco">
          {PERFIS.map((perfil) => (
            <button
              key={perfil}
              type="button"
              className={`profile-chip ${cenario.perfil === perfil ? "active" : ""} tone-${PERFIL_META[perfil].tone}`}
              onClick={() => onPerfil(perfil)}
              aria-pressed={cenario.perfil === perfil}
              title={PERFIL_META[perfil].hint}
            >
              {PERFIL_META[perfil].label}
            </button>
          ))}
        </div>
        <span className="profile-hint">{PERFIL_META[cenario.perfil].hint}</span>
      </div>

      <div className="scenario-actions">
        <button type="button" className="bar-action" onClick={onExport}>
          <Icon name="download" size={15} /> Exportar
        </button>
        <button type="button" className="bar-action ghost" onClick={onReset}>
          <Icon name="reset" size={15} /> Restaurar
        </button>
      </div>
    </section>
  );
}
