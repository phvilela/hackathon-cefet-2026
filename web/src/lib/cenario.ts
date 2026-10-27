import {
  FAMILIAS,
  type CenarioState,
  type FamiliaCultura,
  type PerfilRisco,
  type Talhao,
} from "../types";

const STORAGE_KEY = "hackatohm.tela1.cenario.v1";

function talhoes(areas: [number, number, number], texturas: Talhao["textura"][], irrigacao = false): Talhao[] {
  return [
    { id: "T1", nome: "Talhão 1", areaHa: areas[0], textura: texturas[0], irrigacao },
    { id: "T2", nome: "Talhão 2", areaHa: areas[1], textura: texturas[1], irrigacao },
    { id: "T3", nome: "Talhão 3", areaHa: areas[2], textura: texturas[2], irrigacao },
  ];
}

export interface CenarioPreset {
  id: string;
  label: string;
  hint: string;
  perfil: PerfilRisco;
  talhoes: Talhao[];
}

export const ROTACAO_FAMILIAS: Record<string, FamiliaCultura[]> = {
  soja_milho: ["soja", "milho"],
  soja_sorgo: ["soja", "sorgo"],
  feijao_sorgo: ["feijao", "sorgo"],
  soja_solteira: ["soja"],
  milho_verao: ["milho"],
  girassol_solteira: ["girassol"],
  amendoim_solteira: ["amendoim"],
  arroz_solteira: ["arroz"],
  algodao_solteira: ["algodao"],
  soja_feijao2: ["soja", "feijao"],
};

export const PRESETS: CenarioPreset[] = [
  {
    id: "desafio",
    label: "Fazenda do desafio",
    hint: "600 ha · 3 texturas · sequeiro",
    perfil: "equilibrado",
    talhoes: talhoes([300, 200, 100], ["medio", "arenoso", "argiloso"]),
  },
  {
    id: "conservador",
    label: "Conservador",
    hint: "Mesma área · prioriza menor chance de prejuízo",
    perfil: "conservador",
    talhoes: talhoes([300, 200, 100], ["medio", "arenoso", "argiloso"]),
  },
  {
    id: "irrigado",
    label: "Irrigado",
    hint: "600 ha · irrigação habilitada",
    perfil: "arrojado",
    talhoes: talhoes([300, 200, 100], ["medio", "arenoso", "argiloso"], true),
  },
];

const NOME_PADRAO = /^Talhão \d+$/;

export function renumerarTalhoes(talhoes: Talhao[]): Talhao[] {
  return talhoes.map((talhao, index) => ({
    ...talhao,
    nome: NOME_PADRAO.test(talhao.nome) ? `Talhão ${index + 1}` : talhao.nome,
  }));
}

export function cenarioDoPreset(id: string): CenarioState {
  const preset = PRESETS.find((item) => item.id === id) ?? PRESETS[0];
  return {
    talhoes: preset.talhoes.map((talhao) => ({ ...talhao })),
    perfil: preset.perfil,
    culturas: [...FAMILIAS],
    preset: preset.id,
  };
}

export function carregarCenario(): CenarioState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<CenarioState>;
    if (!Array.isArray(parsed.talhoes) || parsed.talhoes.length < 1) return null;
    if (!parsed.perfil || !["arrojado", "equilibrado", "conservador"].includes(parsed.perfil)) {
      return null;
    }
    const validos = parsed.talhoes.every(
      (talhao) =>
        typeof talhao.id === "string" &&
        typeof talhao.nome === "string" &&
        typeof talhao.areaHa === "number" &&
        ["arenoso", "medio", "argiloso"].includes(talhao.textura) &&
        typeof talhao.irrigacao === "boolean",
    );
    if (!validos) return null;
    const culturas = Array.isArray(parsed.culturas)
      ? parsed.culturas.filter(
          (familia): familia is FamiliaCultura => FAMILIAS.includes(familia),
        )
      : [];
    return {
      talhoes: parsed.talhoes,
      perfil: parsed.perfil,
      culturas: culturas.length > 0 ? culturas : [...FAMILIAS],
      preset: typeof parsed.preset === "string" ? parsed.preset : "personalizado",
    };
  } catch {
    return null;
  }
}

export function salvarCenario(cenario: CenarioState) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(cenario));
}

export function exportarCenario(cenario: CenarioState, perfilLabel: string) {
  const total = cenario.talhoes.reduce((acc, talhao) => acc + talhao.areaHa, 0);
  const payload = {
    cenario: {
      municipio: "Patos de Minas",
      uf: "MG",
      cod_ibge: 3148004,
      safra: "2026/27",
      area_total_ha: total,
      perfil_risco: cenario.perfil,
      perfil_label: perfilLabel,
      culturas: cenario.culturas,
      gerado_em: new Date().toISOString(),
    },
    talhoes: Object.fromEntries(
      cenario.talhoes.map((talhao) => [
        talhao.id,
        {
          nome: talhao.nome,
          area_ha: talhao.areaHa,
          textura: talhao.textura,
          grupo_solo: { arenoso: 1, medio: 2, argiloso: 3 }[talhao.textura],
          irrigacao: talhao.irrigacao,
        },
      ]),
    ),
  };

  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "cenario-talhoes.json";
  anchor.click();
  URL.revokeObjectURL(url);
}
