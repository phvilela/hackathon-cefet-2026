export const CROP_KEYS = [
  "soja",
  "milho_verao",
  "feijao",
  "sorgo_granifero",
  "milho_safrinha",
  "feijao_2",
  "sorgo_safrinha",
  "girassol",
  "amendoim",
  "arroz",
  "algodao",
] as const;

export type CropKey = (typeof CROP_KEYS)[number];
export type GrupoSolo = 1 | 2 | 3;
export type Textura = "arenoso" | "medio" | "argiloso";
export type PerfilRisco = "arrojado" | "equilibrado" | "conservador";

export interface ZarcGrupo {
  decendios: number[];
  /** Omitido quando o grupo não tem janela para a cultura (decendios vazio). */
  risco_por_decendio?: Record<string, number>;
  solo_usado: string;
  /** Omitido quando o grupo não tem janela para a cultura (decendios vazio). */
  ciclos_disponiveis?: number[];
  /** Nota do motor para grupos sem janela (ex.: feijão 2ª em solo arenoso). */
  aviso?: string;
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

export type FamiliaCultura =
  | "soja"
  | "milho"
  | "feijao"
  | "sorgo"
  | "girassol"
  | "amendoim"
  | "arroz"
  | "algodao";

export const FAMILIAS: FamiliaCultura[] = [
  "soja",
  "milho",
  "feijao",
  "sorgo",
  "girassol",
  "amendoim",
  "arroz",
  "algodao",
];

export const FAMILIA_META: Record<FamiliaCultura, { label: string; color: string }> = {
  soja: { label: "Soja", color: "#d9b64a" },
  milho: { label: "Milho", color: "#e4a13c" },
  feijao: { label: "Feijão", color: "#b07a4c" },
  sorgo: { label: "Sorgo", color: "#9a6b3f" },
  girassol: { label: "Girassol", color: "var(--crop-girassol)" },
  amendoim: { label: "Amendoim", color: "var(--crop-amendoim)" },
  arroz: { label: "Arroz", color: "var(--crop-arroz)" },
  algodao: { label: "Algodão", color: "var(--crop-algodao)" },
};

export const FAMILIA_CULTURAS: Record<FamiliaCultura, CropKey[]> = {
  soja: ["soja"],
  milho: ["milho_verao", "milho_safrinha"],
  feijao: ["feijao", "feijao_2"],
  sorgo: ["sorgo_granifero", "sorgo_safrinha"],
  girassol: ["girassol"],
  amendoim: ["amendoim"],
  arroz: ["arroz"],
  algodao: ["algodao"],
};

export const FAMILIA_DA_CULTURA: Record<CropKey, FamiliaCultura> = {
  soja: "soja",
  milho_verao: "milho",
  milho_safrinha: "milho",
  feijao: "feijao",
  feijao_2: "feijao",
  sorgo_granifero: "sorgo",
  sorgo_safrinha: "sorgo",
  girassol: "girassol",
  amendoim: "amendoim",
  arroz: "arroz",
  algodao: "algodao",
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
    descricao: "Janela mais larga do zoneamento; ancora a segunda safra.",
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
    descricao: "O ZARC não abre janela para feijão 2ª em solo arenoso.",
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
  girassol: {
    label: "Girassol",
    shortLabel: "Girassol",
    color: "var(--crop-girassol)",
    ink: "var(--crop-girassol-ink)",
    descricao: "Cultura de entressafra que diversifica a rotação e cobre o solo.",
    safra: "1ª",
    ordem: 8,
  },
  amendoim: {
    label: "Amendoim",
    shortLabel: "Amendoim",
    color: "var(--crop-amendoim)",
    ink: "var(--crop-amendoim-ink)",
    descricao: "Leguminosa de grão, que ainda devolve nitrogênio ao solo.",
    safra: "1ª",
    ordem: 9,
  },
  arroz: {
    label: "Arroz",
    shortLabel: "Arroz",
    color: "var(--crop-arroz)",
    ink: "var(--crop-arroz-ink)",
    descricao: "Grão básico com mercado de consumo garantido.",
    safra: "1ª",
    ordem: 10,
  },
  algodao: {
    label: "Algodão",
    shortLabel: "Algodão",
    color: "var(--crop-algodao)",
    ink: "var(--crop-algodao-ink)",
    descricao: "Cultura fibrosa de alto valor por hectare quando bem manejada.",
    safra: "1ª",
    ordem: 11,
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
  return `${month.long} de ${month.year} · ${decendioInMonth(dec)}º período de 10 dias`;
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
    hint: "Prioriza margem, aceita mais chance de prejuízo.",
    tone: "clay",
  },
  equilibrado: {
    label: "Equilibrado",
    hint: "Melhor equilíbrio entre margem e chance de prejuízo.",
    tone: "green",
  },
  conservador: {
    label: "Conservador",
    hint: "Prioriza previsibilidade e menor chance de prejuízo.",
    tone: "blue",
  },
};

export function grupoDoTalhao(talhao: Talhao) {
  return TEXTURA_META[talhao.textura].grupo;
}

export function culturasViaveis(zarc: ZarcData, grupo: GrupoSolo) {
  // Defensivo: culturas novas (girassol, amendoim, arroz, algodão) podem não
  // existir ainda num zarc.json antigo — ausentes do arquivo são puladas.
  return CROP_KEYS.flatMap((key) => {
    const janela = zarc.culturas[key]?.[String(grupo) as `${GrupoSolo}`];
    if (!janela) return [];
    return [{ key, meta: CROP_META[key], janela }];
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
  const janela = zarc.culturas[crop]?.[String(grupo) as `${GrupoSolo}`];
  if (!janela || !janela.decendios.includes(dec)) return null;
  return janela.risco_por_decendio?.[String(dec)] ?? null;
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

const pctFormatter = (casas: number) =>
  new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  });

/**
 * Risco armazenado no contrato como por-mil (220 = 22,0%).
 * Retorna o percentual formatado em pt-BR, ex.: "22,0%".
 */
export function riscoPct(riscoPorMil: number, casas = 1) {
  return `${pctFormatter(casas).format(riscoPorMil / 10)}%`;
}

/**
 * "% da área com chance de prejuízo" — hectares com margem negativa esperada
 * sobre a área total. Ex.: 110,6 ha de 600 ha → "18,4%".
 */
export function areaRiscoPct(haSobRisco: number, areaTotal: number, casas = 1) {
  if (areaTotal <= 0) return `${pctFormatter(casas).format(0)}%`;
  return `${pctFormatter(casas).format((haSobRisco / areaTotal) * 100)}%`;
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
  /** Marcador do contrato v2: 'Arrojado' | 'Equilibrado (knee)' | 'Conservador'
   *  | 'Referência (não plantar)' | null. Não confundir com PerfilRisco
   *  (chaves internas dos planos nomeados). */
  perfil: string | null;
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
  /** Chave do contrato (campo "knee" do results.json) — termo interno da API,
   *  nunca exibido ao usuário; na interface chama-se "ponto equilibrado". */
  knee: Plano;
  planos: Record<PerfilRisco, Plano>;
  /** Contrato v2 (opcional): âncora "não plantar" com todo o capital no CDI.
   *  Ausente em contratos antigos — o ponto só é desenhado quando existe. */
  referencia_sem_plantio?: Plano | null;
  robustez: Robustez;
}

/** Cor por perfil — casa com --green (equilibrado), --clay (arrojado), --blue (conservador). */
export const PERFIL_TONE_HEX: Record<PerfilRisco, string> = {
  arrojado: "#b8643a",
  equilibrado: "#2f6b46",
  conservador: "#426c75",
};

/** Cores do ponto "não plantar (capital no CDI)" no gráfico da fronteira —
 *  espelham os tokens --sand (preenchimento) e --muted (traço/texto). O SVG do
 *  Recharts não resolve var() em atributos de apresentação, então o valor é
 *  espelhado aqui, no mesmo padrão de PERFIL_TONE_HEX. */
export const REFERENCIA_TONE = {
  fill: "#e9e1d0",
  stroke: "#5c6659",
};
