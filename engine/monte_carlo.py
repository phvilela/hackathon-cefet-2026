#!/usr/bin/env python3
"""
engine/monte_carlo.py — M1/M2: Monte Carlo → engine/margens_mc.json

Gera a MARGEM ESPERADA e o RISCO de cada rotação para o motor CP-SAT.

Método (dois passos, para separar NÍVEL de VOLATILIDADE):

  1) MARGEM ESPERADA = preço de referência ATUAL × produtividade de referência
     − custo Conab. Preço/produtividade de referência são os valores reais já
     usados no contrato (SIDRA + PAM, com fonte_url) — regime vigente 2026/27.
     É o que um prodente de fato planeja (forward-looking).

  2) RISCO = Monte Carlo sobre a VOLATILIDADE histórica. Para soja e milho, a
     série PAM×SIDRA pareada (31 anos, Patos) fornece o coeficiente de variação
     de preço e produtividade e a correlação entre eles; simulamos desvios
     MULTIPLICATIVOS em torno da referência (rebase), preservando a forma e a
     correlação históricas. Sorgo/feijão (sem série anual em Patos) usam preço
     Conab com volatilidade LOGNORMAL documentada.

Unidades de saída (o CP-SAT só tem inteiros):
  · margem_esperada: CENTAVOS de R$/ha  (R$ 1.866/ha → 186600)
  · risco: POR-MIL (‰) = P(margem < 0) × 1000  (8% → 80)

Uso:
    python3 engine/monte_carlo.py                 # gera margens_mc.json
    python3 engine/monte_carlo.py --runs 20000    # mais iterações
    python3 engine/monte_carlo.py --seed 7        # reprodutível
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
ENGINE = REPO / "engine"
PAM = REPO / "notebooks/saida_preco/dados_anuais_Patos_de_Minas.csv"
CUSTOS = REPO / "data/processed/mercado/conab_custos/resumo_custos_para_engine.csv"
SAIDA = ENGINE / "margens_mc.json"

SC_KG = 60.0  # 1 saca = 60 kg

FONTE_SIDRA = "https://apisidra.ibge.gov.br/values/t/54"
FONTE_CONAB = ("https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/"
               "custos-de-producao")
FONTE_PAM = "notebooks/saida_preco/dados_anuais_Patos_de_Minas.csv"

# Volatilidade (CV) para culturas SEM série anual em Patos
CV_PRECO_REF = {"sorgo": 0.20, "feijao": 0.25}
PRECO_REF_KG = {"sorgo": 0.55, "feijao": 9.00}

# Referências reais (contrato results.json — SIDRA/PAM/Conab, com fonte)
# prod em unidade própria; preço na mesma unidade (sc=60kg, ou R$/kg p/ sorgo/feijão)
REF = {
    "soja":        {"prod": 55.0,  "prod_un": "sc/ha", "preco": 166.49, "preco_un": "R$/sc"},
    "milho_safr":  {"prod": 80.0,  "prod_un": "sc/ha", "preco": 84.44,  "preco_un": "R$/sc"},
    "milho_verao": {"prod": 110.0, "prod_un": "sc/ha", "preco": 84.44,  "preco_un": "R$/sc"},
    "sorgo":       {"prod": 4000.0, "prod_un": "kg/ha", "preco": 0.55,  "preco_un": "R$/kg"},
    "feijao":      {"prod": 1200.0, "prod_un": "kg/ha", "preco": 9.00,  "preco_un": "R$/kg"},
}
CUSTO = {  # R$/ha — Conab; milho_verão alinhado ao contrato v2.1 (R$ 8.804/ha)
    "soja": "soja", "milho_safr": "milho_2a_safra", "milho_verao": None,
    "sorgo": "sorgo", "feijao": "feijao_1a_safra",
}
CUSTO_MILHO_VERAO = 8804.0  # Conab, 1ª safra — valor já publicado no contrato v2.1
# rotacao -> lista de culturas (cada uma contribui receita−custo)
ROTACOES = {
    "soja_solteira": ["soja"],
    "milho_verao": ["milho_verao"],
    "soja_milho": ["soja", "milho_safr"],
    "soja_sorgo": ["soja", "sorgo"],
    "feijao_sorgo": ["feijao", "sorgo"],
}


def _carrega_pam() -> pd.DataFrame:
    df = pd.read_csv(PAM, header=[0, 1], index_col=0)
    df.index.name = "ano"
    df = df.dropna(how="all").astype(float)
    return pd.DataFrame({
        "prod_soja": df[("rendimento_kg_ha", "Soja")],
        "prod_milho": df[("rendimento_kg_ha", "Milho")],
        "preco_soja": df[("preco_real_rs_saca", "Soja")],
        "preco_milho": df[("preco_real_rs_saca", "Milho")],
    }).dropna()


def _carrega_custos() -> Dict[str, float]:
    df = pd.read_csv(CUSTOS)
    return {k.strip(): float(v) for k, v in
            zip(df["cultura"], df["custo_medio_ha"])}


def _simula_cultura_serie(chave: str, pam: pd.DataFrame, runs: int,
                          rng: np.random.Generator) -> np.ndarray:
    """Receita R$/ha por run para soja/milho: aplica desvio histórico (rebase)
    em torno da referência atual, preservando correlação preço×prod."""
    par = {"soja": ("prod_soja", "preco_soja"),
           "milho_safr": ("prod_milho", "preco_milho"),
           "milho_verao": ("prod_milho", "preco_milho")}[chave]
    pc, pp = par
    idx = rng.integers(0, len(pam), size=runs)
    # razões normalizadas (hist / média hist) — desvio multiplicativo ~ centrado em 1
    raz_prod = pam[pc].to_numpy()[idx] / pam[pc].mean()
    raz_preco = pam[pp].to_numpy()[idx] / pam[pp].mean()
    ref = REF[chave]
    prod = ref["prod"] * raz_prod          # produtividade simulada (sc ou kg)/ha
    preco = ref["preco"] * raz_preco       # preço simulado
    return prod * preco                    # receita R$/ha


def _simula_cultura_ref(chave: str, runs: int, rng: np.random.Generator) -> np.ndarray:
    """Receita R%/ha para sorgo/feijão: preço lognormal em torno do ref, prod fixa."""
    cv = CV_PRECO_REF[chave]
    preco = REF[chave]["preco"] * np.exp(-0.5 * cv ** 2 + cv * rng.standard_normal(runs))
    return REF[chave]["prod"] * preco


def _custo(chave: str, custos: Dict[str, float]) -> float:
    """Custo R$/ha da cultura; milho_verão usa o valor já publicado no contrato."""
    if chave == "milho_verao":
        return CUSTO_MILHO_VERAO
    return custos[CUSTO[chave]]


def simula(pam: pd.DataFrame, custos: Dict[str, float], runs: int,
           rng: np.random.Generator) -> Dict[str, np.ndarray]:
    cache: Dict[str, np.ndarray] = {}
    receita: Dict[str, np.ndarray] = {}
    for chave in set(c for cs in ROTACOES.values() for c in cs):
        if chave in ("soja", "milho_safr", "milho_verao"):
            receita[chave] = _simula_cultura_serie(chave, pam, runs, rng)
        else:
            receita[chave] = _simula_cultura_ref(chave, runs, rng)
        cache[chave] = receita[chave] - _custo(chave, custos)  # margem por cultura

    return {rot: sum(cache[c] for c in culturas)
            for rot, culturas in ROTACOES.items()}


def _hipoteses(rota: str) -> list:
    base = [
        {"chave": "referencia_preco_prod", "valor": "preço SIDRA × produtividade PAM (regime 2026/27)",
         "fonte_url": FONTE_SIDRA, "metodo": "margem esperada = preço_ref × prod_ref − custo Conab"},
        {"chave": "volatilidade_historica", "valor": "31 anos PAM×SIDRA pareados (1995-2025), rebased na referência",
         "fonte_url": FONTE_PAM, "metodo": "MC: desvios multiplicativos preço×prod preservando correlação"},
        {"chave": "custo_conab", "valor": "custo médio R$/ha Conab 2024-2026 (Cerrado)",
         "fonte_url": FONTE_CONAB, "metodo": "resumo_custos_para_engine.csv"},
    ]
    extra = []
    if "sorgo" in rota:
        extra.append({"chave": "preco_sorgo_ref",
                      "valor": "R$ 0,55/kg (Conab) c/ CV 20% lognormal",
                      "fonte_url": FONTE_CONAB,
                      "metodo": "sem série anual em Patos — volatilidade documentada"})
    if "feijao" in rota:
        extra.append({"chave": "preco_feijao_ref",
                      "valor": "R$ 9,00/kg (Conab) c/ CV 25% lognormal",
                      "fonte_url": FONTE_CONAB,
                      "metodo": "sem série anual em Patos — volatilidade documentada"})
    return base + extra


def main() -> int:
    ap = argparse.ArgumentParser(description="MC → margens_mc.json")
    ap.add_argument("--runs", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--saida", type=Path, default=SAIDA)
    args = ap.parse_args()

    pam = _carrega_pam()
    custos = _carrega_custos()
    rng = np.random.default_rng(args.seed)
    margens = simula(pam, custos, args.runs, rng)

    out: Dict[str, dict] = {}
    print(f"Monte Carlo — {args.runs} runs, seed {args.seed}, {len(pam)} anos pareados (rebase na ref. 2026/27)\n")
    print(f"{'rotação':14} {'margem R$/ha':>13} {'centavos':>11} {'P(m<0)':>8} {'‰':>6}")
    for rota in ROTACOES:
        arr = margens[rota]
        m_esp = float(np.mean(arr))
        p_neg = float(np.mean(arr < 0))
        centavos = int(round(m_esp * 100))
        por_mil = int(round(p_neg * 1000))
        out[rota] = {"margem_esperada": centavos, "risco": por_mil,
                     "hipoteses": _hipoteses(rota)}
        print(f"{rota:14} {m_esp:13,.0f} {centavos:11,} {p_neg*100:7.1f}% {por_mil:6}")
    print(f"{'capital_pousio':14} {'(Selic/custeio — do config)':>13}")

    # Só chaves de rotação no topo (o loader do atualiza_config itera toda chave de topo)
    args.saida.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    print(f"\n✔ escrito: {args.saida}")
    print(f"  (runs={args.runs}, seed={args.seed}, {len(pam)} anos pareados, "
          f"rebase na referência 2026/27)")
    print("  Próximo: python3 engine/atualiza_config.py --margens engine/margens_mc.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
