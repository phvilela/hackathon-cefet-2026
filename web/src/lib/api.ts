import { TEXTURA_META, type GrupoSolo, type Resultados, type Talhao } from "../types";

export type StatusApi = "ok" | "carregando" | "erro";

export interface TalhaoPayload {
  id: string;
  area_ha: number;
  grupo_solo: GrupoSolo;
}

/** Monta o payload do POST /api/solve a partir do cenário da tela 1. */
export function payloadDaCenario(talhoes: Talhao[]): TalhaoPayload[] {
  return talhoes.map((talhao) => ({
    id: talhao.id,
    area_ha: talhao.areaHa,
    grupo_solo: TEXTURA_META[talhao.textura].grupo,
  }));
}

/**
 * Resolve o cenário no backend. Em produção (Vercel) é same-origin em /api/solve;
 * em dev o proxy do Vite encaminha para http://localhost:8000.
 * Aceita um AbortController para cancelar requisições obsoletas.
 */
export async function resolverCenario(
  talhoes: Talhao[],
  signal?: AbortSignal,
): Promise<Resultados> {
  const resposta = await fetch("/api/solve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ talhoes: payloadDaCenario(talhoes) }),
    signal,
  });
  if (!resposta.ok) throw new Error(`POST /api/solve respondeu ${resposta.status}`);
  const dados = (await resposta.json()) as Partial<Resultados> | null;
  if (!dados || typeof dados !== "object" || !dados.planos || !Array.isArray(dados.fronteira_pareto)) {
    throw new Error("Resposta de /api/solve fora do contrato");
  }
  return dados as Resultados;
}

/** Aquece o endpoint (evita cold start no demo). Nunca lança. */
export async function pingApi(): Promise<boolean> {
  try {
    const resposta = await fetch("/api/health", { signal: AbortSignal.timeout(8000) });
    return resposta.ok;
  } catch {
    return false;
  }
}
