export const CROP_KEYS = [
  "soja",
  "milho_verao",
  "feijao",
  "sorgo_granifero",
  "milho_safrinha",
  "feijao_2",
  "sorgo_safrinha",
] as const;

export type CropKey = (typeof CROP_KEYS)[number];
export type GrupoSolo = 1 | 2 | 3;
export type Textura = "arenoso" | "medio" | "argiloso";
export type PerfilRisco = "arrojado" | "equilibrado" | "conservador";

export interface ZarcGrupo {
  decendios: number[];
  risco_por_decendio: Record<string, number>;
  solo_usado: string;
  ciclos_disponiveis: number[];
}

export interface ZarcCenario {
  municipio: string;
  cod_ibge: number;
  safra: string;
  uf: string;
}

export interface ZarcRotacao {
  primeira: number[];
  segunda?: number[];
  primeira_ciclo?: string;
  premissa_ciclo_primeira_decendios?: number;
}

export interface ZarcData {
  cenario: ZarcCenario;
  fonte: {
    arquivo_csv: string;
    portal: string;
    dataset_id: string;
    portarias_por_cultura: Record<string, string[]>;
  };
  premissas: Array<{
    chave: string;
    valor: string | number;
    metodo: string;
    fonte_url: string;
  }>;
  culturas: Record<CropKey, Record<`${GrupoSolo}`, ZarcGrupo>>;
  rotacoes: Record<string, Record<`${GrupoSolo}`, ZarcRotacao>>;
  sanity: Record<string, boolean>;
}

export interface Talhao {
  id: string;
  nome: string;
  areaHa: number;
  textura: Textura;
  irrigacao: boolean;
}

export interface CenarioState {
  talhoes: Talhao[];
  perfil: PerfilRisco;
  culturas: FamiliaCultura[];
  preset: string;
}

export type FamiliaCultura = "soja" | "milho" | "feijao" | "sorgo";

export const FAMILIAS: FamiliaCultura[] = ["soja", "milho", "feijao", "sorgo"];

export const FAMILIA_META: Record<FamiliaCultura, { label: string; color: string }> = {
  soja: { label: "Soja", color: "#d9b64a" },
  milho: { label: "Milho", color: "#e4a13c" },
  feijao: { label: "Feijão", color: "#b07a4c" },
  sorgo: { label: "Sorgo", color: "#9a6b3f" },
};

export const FAMILIA_CULTURAS: Record<FamiliaCultura, CropKey[]> = {
  soja: ["soja"],
  milho: ["milho_verao", "milho_safrinha"],
  feijao: ["feijao", "feijao_2"],
  sorgo: ["sorgo_granifero", "sorgo_safrinha"],
};

export const FAMILIA_DA_CULTURA: Record<CropKey, FamiliaCultura> = {
  soja: "soja",
  milho_verao: "milho",
  milho_safrinha: "milho",
  feijao: "feijao",
  feijao_2: "feijao",
  sorgo_granifero: "sorgo",
  sorgo_safrinha: "sorgo",
};

export interface CropMeta {
  label: string;
  shortLabel: string;
  color: string;
  ink: string;
  descricao: string;
  safra: "1ª" | "2ª";
  ordem: number;
}

export const CROP_META: Record<CropKey, CropMeta> = {
  soja: {
    label: "Soja",
    shortLabel: "Soja",
    color: "#d9b64a",
    ink: "#5b4811",
    descricao: "Janela mais larga do zoneamento; ancora a safrinha.",
    safra: "1ª",
    ordem: 1,
  },
  milho_verao: {
    label: "Milho 1ª safra",
    shortLabel: "Milho 1ª",
    color: "#e4a13c",
    ink: "#653b0a",
    descricao: "Plantio de verão, janela mais curta que a soja.",
    safra: "1ª",
    ordem: 2,
  },
  feijao: {
    label: "Feijão",
    shortLabel: "Feijão",
    color: "#b07a4c",
    ink: "#4e2d16",
    descricao: "Feijão das águas em sequeiro.",
    safra: "1ª",
    ordem: 3,
  },
  sorgo_granifero: {
    label: "Sorgo granífero",
    shortLabel: "Sorgo",
    color: "#9a6b3f",
    ink: "#3f2814",
    descricao: "Tolera plantio mais tardio e solo mais arenoso.",
    safra: "1ª",
    ordem: 4,
  },
  milho_safrinha: {
    label: "Milho 2ª safra",
    shortLabel: "Milho 2ª",
    color: "#c97a2b",
    ink: "#5a2e05",
    descricao: "Precisa caber depois da colheita da primeira cultura.",
    safra: "2ª",
    ordem: 5,
  },
  feijao_2: {
    label: "Feijão 2ª safra",
    shortLabel: "Feijão 2ª",
    color: "#8b5e3c",
    ink: "#3b2110",
    descricao: "ZARC não zoneia feijão 2ª em solo arenoso (AD1).",
    safra: "2ª",
    ordem: 6,
  },
  sorgo_safrinha: {
    label: "Sorgo 2ª safra",
    shortLabel: "Sorgo 2ª",
    color: "#7f6136",
    ink: "#33240e",
    descricao: "Alternativa de segunda safra em todos os grupos de solo.",
    safra: "2ª",
    ordem: 7,
  },
};

const MONTHS = [
  { month: 1, label: "Jan", long: "Janeiro", year: 2027 },
  { month: 2, label: "Fev", long: "Fevereiro", year: 2027 },
  { month: 3, label: "Mar", long: "Março", year: 2027 },
  { month: 4, label: "Abr", long: "Abril", year: 2027 },
  { month: 5, label: "Mai", long: "Maio", year: 2027 },
  { month: 6, label: "Jun", long: "Junho", year: 2027 },
  { month: 7, label: "Jul", long: "Julho", year: 2027 },
  { month: 8, label: "Ago", long: "Agosto", year: 2027 },
  { month: 9, label: "Set", long: "Setembro", year: 2026 },
  { month: 10, label: "Out", long: "Outubro", year: 2026 },
  { month: 11, label: "Nov", long: "Novembro", year: 2026 },
  { month: 12, label: "Dez", long: "Dezembro", year: 2026 },
];

const SAFRA_MONTHS = [
  ...MONTHS.filter((m) => m.month >= 9),
  ...MONTHS.filter((m) => m.month <= 8),
];

export const SAFRA_ORDER = SAFRA_MONTHS.flatMap((m) => {
  const start = (m.month - 1) * 3 + 1;
  return [start, start + 1, start + 2];
});

export const MONTH_COLUMNS = SAFRA_MONTHS.map((m) => {
  const start = (m.month - 1) * 3 + 1;
  return { ...m, decendios: [start, start + 1, start + 2] };
});

export function monthForDecendio(dec: number) {
  return MONTHS[(Math.ceil(dec / 3) - 1) % 12];
}

export function decendioInMonth(dec: number) {
  return ((dec - 1) % 3) + 1;
}

export function formatDecendio(dec: number) {
  const month = monthForDecendio(dec);
  return `${month.label}/${decendioInMonth(dec)}`;
}

export function formatDecendioLong(dec: number) {
  const month = monthForDecendio(dec);
  return `${month.long} de ${month.year} · ${decendioInMonth(dec)}º decêndio`;
}

export function sortBySafra(decs: number[]) {
  const order = new Map(SAFRA_ORDER.map((dec, index) => [dec, index]));
  return [...decs].sort((a, b) => (order.get(a) ?? 0) - (order.get(b) ?? 0));
}

export function formatJanela(decs: number[]) {
  if (decs.length === 0) return "Sem janela";
  const ordered = sortBySafra(decs);
  const runs: number[][] = [];
  const order = new Map(SAFRA_ORDER.map((dec, index) => [dec, index]));

  for (const dec of ordered) {
    const last = runs[runs.length - 1];
    if (
      last &&
      (order.get(dec) ?? 0) - (order.get(last[last.length - 1]) ?? 0) === 1
    ) {
      last.push(dec);
    } else {
      runs.push([dec]);
    }
  }

  return runs
    .map((run) =>
      run.length === 1
        ? formatDecendio(run[0])
        : `${formatDecendio(run[0])} a ${formatDecendio(run[run.length - 1])}`,
    )
    .join(" · ");
}

export const TEXTURA_META: Record<
  Textura,
  { label: string; grupo: GrupoSolo; solo: string; hint: string }
> = {
  arenoso: {
    label: "Arenoso",
    grupo: 1,
    solo: "AD1",
    hint: "Menor retenção de água",
  },
  medio: {
    label: "Médio",
    grupo: 2,
    solo: "AD3",
    hint: "Latossolo típico da região",
  },
  argiloso: {
    label: "Argiloso",
    grupo: 3,
    solo: "AD5",
    hint: "Maior retenção de água",
  },
};

export const GRUPO_META: Record<
  GrupoSolo,
  { textura: Textura; label: string; solo: string }
> = {
  1: { textura: "arenoso", label: "Arenoso", solo: "AD1" },
  2: { textura: "medio", label: "Médio", solo: "AD3" },
  3: { textura: "argiloso", label: "Argiloso", solo: "AD5" },
};

export const PERFIL_META: Record<
  PerfilRisco,
  { label: string; hint: string; tone: string }
> = {
  arrojado: {
    label: "Arrojado",
    hint: "Prioriza margem, aceita mais risco.",
    tone: "clay",
  },
  equilibrado: {
    label: "Equilibrado",
    hint: "O ponto de equilíbrio da fronteira.",
    tone: "green",
  },
  conservador: {
    label: "Conservador",
    hint: "Prioriza previsibilidade e menor risco.",
    tone: "blue",
  },
};

export function grupoDoTalhao(talhao: Talhao) {
  return TEXTURA_META[talhao.textura].grupo;
}

export function culturasViaveis(zarc: ZarcData, grupo: GrupoSolo) {
  return CROP_KEYS.map((key) => {
    const janela = zarc.culturas[key][String(grupo) as `${GrupoSolo}`];
    return { key, meta: CROP_META[key], janela };
  })
    .filter(({ janela }) => janela.decendios.length > 0)
    .sort((a, b) => a.meta.ordem - b.meta.ordem);
}

export function riscoNoDecendio(
  zarc: ZarcData,
  crop: CropKey,
  grupo: GrupoSolo,
  dec: number,
) {
  const janela = zarc.culturas[crop][String(grupo) as `${GrupoSolo}`];
  if (!janela.decendios.includes(dec)) return null;
  return janela.risco_por_decendio[String(dec)] ?? null;
}

export function riskTone(risk: number | null) {
  if (risk === null) return "off";
  if (risk <= 20) return "low";
  if (risk <= 30) return "mid";
  return "high";
}

export function brl(value: number) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  }).format(value);
}

export function ha(valor: number) {
  return new Intl.NumberFormat("pt-BR", {
    maximumFractionDigits: 1,
  }).format(valor);
}

/* ── Contrato motor → frontend (contract/results.json) ────────────────── */

export type StatusDados = "REAL" | "PARCIAL" | "MOCK";

export interface Hipotese {
  chave: string;
  valor: string;
  fonte_url: string;
  metodo: string;
}

export interface Plano {
  perfil: PerfilRisco;
  descricao: string;
  margem_floor_centavos: number;
  margem_centavos: number;
  margem_reais: number;
  risco_por_mil_ha: number;
  ha_sob_risco: number;
  status: string;
  plano_por_talhao: Record<string, Record<string, number>>;
  area_por_rotacao: Record<string, number>;
}

export interface RotacaoResult {
  culturas: string[];
  margem_centavos_por_ha: number;
  margem_reais_por_ha: number;
  risco_por_mil: number;
  janelas_viveis_decendios: Record<string, number[]>;
  grupos_viveis: string[];
  hipoteses: Hipotese[];
}

export interface Robustez {
  runs: number;
  jitter_percent: number;
  seed: number;
  successful_runs: number;
  failed_runs: number;
  stability_mean: number;
  stability_min: number;
  stability_max: number;
  max_talhoes_mudados: number;
  pct_runs_sem_mudanca: number;
  distribuicao_mudancas_talhoes: Record<string, number>;
  frase_estabilidade: string;
  margem_total_centavos: {
    media: number;
    minimo: number;
    maximo: number;
    desvio_padrao: number;
  };
  observacao: string;
}

export interface Resultados {
  cenario: Record<string, unknown>;
  dados: { status: StatusDados; observacao: string; gerado_em: string; engine: string };
  talhoes: Record<string, { area_ha: number; grupo_solo: GrupoSolo }>;
  rotacoes: Record<string, RotacaoResult>;
  plano_otimo: Plano;
  fronteira_pareto: Plano[];
  knee: Plano;
  planos: Record<PerfilRisco, Plano>;
  robustez: Robustez;
}

/** Cor por perfil — casa com --green (equilibrado), --clay (arrojado), --blue (conservador). */
export const PERFIL_TONE_HEX: Record<PerfilRisco, string> = {
  arrojado: "#b8643a",
  equilibrado: "#2f6b46",
  conservador: "#426c75",
};
