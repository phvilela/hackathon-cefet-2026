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
     Conab com volatilidade LOGNORMAL documentada. Arroz, algodão e feijão 2ª
     (novas culturas) seguem o mesmo caminho de referência: preço, custo e
     produtividade Conab (out/2026) com CV lognormal documentada.

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

# Novas culturas (referências Conab de out/2026 — todas com URL rastreável):
#   · preço: Conab "Desempenho de Mercado — Semanal 40" (28/09–02/10/2026) e
#     série mensal de preços recebidos da Conab (relatório FAESP/Senar-SP,
#     ed. 60/out/2026, ref. set/2026 — fonte CONAB);
#   · produtividade: planilhas de custo Conab ("Produtividade Média") e/ou
#     boletim safra 2026/27 — a coluna "Produtividade" da tábua ZARC do
#     município está vazia (inspecionada na safra 2026/27);
#   · custo: CUSTO TOTAL (H+I=J) das planilhas Conab — mesma base das demais
#     culturas (resumo_custos_para_engine.csv).
FONTE_CONAB_SEMANAL = (
    "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/"
    "analises-do-mercado-agropecuario-e-extrativista/analises-de-mercado/"
    "historico-semanal/historico-semanal-resumo-executivo/"
    "desempenho-de-mercado-2026-1/desempenho_de_mercado40-2.pdf"
)
FONTE_CONAB_BOLETIM = (
    "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/safras/"
    "safra-de-graos/boletim-da-safra-de-graos/1o-levantamento-safra-2026-27/"
    "boletim-de-safras-1o-levantamento_2026.pdf"
)
FONTE_CONAB_PRECO_MENSAL = (
    "https://faespsenar.com.br/painel-de-dados/wp-content/uploads/2026/10/"
    "2026.10-Precos-pagos-ao-produtor-paulista_compressed.pdf"
)
FONTE_CUSTO_ARROZ = (
    "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/"
    "custos-de-producao/arquivos-custo-de-producao/agricolas/arroz/"
    "arroz_sequeiro_serie_historica_2001-2026.xls"
)
FONTE_CUSTO_ALGODAO = (
    "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/"
    "custos-de-producao/arquivos-custo-de-producao/agricolas/"
    "serie-historica-custos-algodao-em-pluma-1998-a-2026.xlsx"
)
FONTE_CUSTO_FEIJAO2 = (
    "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/"
    "custos-de-producao/arquivos-custo-de-producao/agricolas/feijao/"
    "feijao_2_e_3_safras_serie_historica_2013-2026.xls"
)

# Volatilidade (CV) para culturas SEM série anual em Patos
CV_PRECO_REF = {"sorgo": 0.20, "feijao": 0.25,
                "arroz": 0.20, "algodao": 0.20, "feijao_2": 0.25}
PRECO_REF_KG = {"sorgo": 0.55, "feijao": 9.00}

# Referências reais (contrato results.json — SIDRA/PAM/Conab, com fonte)
# prod em unidade própria; preço na mesma unidade (sc=60kg, ou R$/kg p/ sorgo/feijão)
REF = {
    "soja":        {"prod": 55.0,  "prod_un": "sc/ha", "preco": 166.49, "preco_un": "R$/sc"},
    "milho_safr":  {"prod": 80.0,  "prod_un": "sc/ha", "preco": 84.44,  "preco_un": "R$/sc"},
    "milho_verao": {"prod": 110.0, "prod_un": "sc/ha", "preco": 84.44,  "preco_un": "R$/sc"},
    "sorgo":       {"prod": 4000.0, "prod_un": "kg/ha", "preco": 0.55,  "preco_un": "R$/kg"},
    "feijao":      {"prod": 1200.0, "prod_un": "kg/ha", "preco": 9.00,  "preco_un": "R$/kg"},
    # Novas culturas — Conab out/2026 (ver constantes FONTE_* acima):
    # arroz em casca R$ 105,75/sc 60 kg (Conab, set/2026) = R$ 1,7625/kg;
    # prod. 2.584 kg/ha = arroz de SEQUEIRO, média nacional safra 2026/27 (Conab).
    "arroz":       {"prod": 2584.0, "prod_un": "kg/ha", "preco": 1.7625, "preco_un": "R$/kg"},
    # algodão em pluma R$ 138,67/@ 15 kg (Conab, Semanal 40, Bahia) = R$ 9,2447/kg
    # de pluma; prod. 1.863 kg/ha de pluma ≈ 124 @/ha (média Cerrado: Barreiras-BA
    # 1.845 / Cristalina-GO 1.890). O custo Conab já credita a receita do caroço
    # (linha "Receita" da planilha) — por isso a receita aqui é só a pluma.
    "algodao":     {"prod": 1863.0, "prod_un": "kg/ha de pluma", "preco": 9.2447,
                    "preco_un": "R$/kg de pluma"},
    # feijão cores R$ 290,00/sc 60 kg (Conab, Semanal 40, Paraná) = R$ 4,8333/kg;
    # prod. 2.000 kg/ha = referência da planilha de custo Conab da 2ª safra
    # (Francisco Beltrão-PR) — pareada com o custo usado.
    "feijao_2":    {"prod": 2000.0, "prod_un": "kg/ha", "preco": 4.8333, "preco_un": "R$/kg"},
}
CUSTO = {  # R$/ha — Conab; milho_verão alinhado ao contrato v2.1 (R$ 8.804/ha)
    "soja": "soja", "milho_safr": "milho_2a_safra", "milho_verao": None,
    "sorgo": "sorgo", "feijao": "feijao_1a_safra",
    "arroz": "arroz_sequeiro", "algodao": "algodao_em_pluma",
    "feijao_2": "feijao_2a_safra",
}
CUSTO_MILHO_VERAO = 8804.0  # Conab, 1ª safra — valor já publicado no contrato v2.1
# rotacao -> lista de culturas (cada uma contribui receita−custo)
ROTACOES = {
    "soja_solteira": ["soja"],
    "milho_verao": ["milho_verao"],
    "soja_milho": ["soja", "milho_safr"],
    "soja_sorgo": ["soja", "sorgo"],
    "feijao_sorgo": ["feijao", "sorgo"],
    "arroz_solteira": ["arroz"],
    "algodao_solteira": ["algodao"],
    "soja_feijao2": ["soja", "feijao_2"],
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
    """Receita R$/ha p/ sorgo/feijão/arroz/algodão/feijão 2ª: preço lognormal em
    torno da referência Conab, produtividade fixa (sem série anual em Patos)."""
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
    # ordem determinística (set de strings varia com o hash do interpretador —
    # o --seed promete reprodutibilidade, então ordenamos a iteração)
    chaves = sorted(set(c for cs in ROTACOES.values() for c in cs))
    for chave in chaves:
        if chave in ("soja", "milho_safr", "milho_verao"):
            receita[chave] = _simula_cultura_serie(chave, pam, runs, rng)
        else:
            receita[chave] = _simula_cultura_ref(chave, runs, rng)
        cache[chave] = receita[chave] - _custo(chave, custos)  # margem por cultura

    return {rot: sum(cache[c] for c in culturas)
            for rot, culturas in ROTACOES.items()}


# Cartões de rastreabilidade das rotações NOVAS (referências Conab out/2026 —
# sem série PAM×SIDRA municipal para arroz/algodão/feijão 2ª). Textos em PT-BR
# apresentáveis ao usuário; cada número cita a fonte (fonte_url).
_HIPOTESES_NOVAS = {
    "arroz_solteira": [
        {"chave": "referencia_preco_prod",
         "valor": "arroz em casca R$ 105,75/sc 60 kg (R$ 1,76/kg) — preço recebido do "
                  "produtor, Conab, set/2026; produtividade 2.584 kg/ha (arroz de "
                  "sequeiro, média nacional da safra 2026/27, Conab)",
         "fonte_url": FONTE_CONAB_PRECO_MENSAL,
         "metodo": "margem esperada = preço_ref × prod_ref − custo Conab; a coluna "
                   "'Produtividade' da tábua ZARC do município está vazia — referências "
                   "do boletim de safra e da planilha de custo da Conab"},
        {"chave": "volatilidade_preco",
         "valor": "CV 20% lognormal no preço (documentada)",
         "fonte_url": FONTE_CONAB_SEMANAL,
         "metodo": "sem série anual de preços em Patos de Minas — volatilidade documentada "
                   "(mesma regra usada para sorgo)"},
        {"chave": "custo_conab",
         "valor": "custo total R$ 4.426,71/ha — arroz de sequeiro, Balsas-MA, safra 2024 "
                  "(último custo publicado da principal região de sequeiro no Cerrado)",
         "fonte_url": FONTE_CUSTO_ARROZ,
         "metodo": "CUSTO TOTAL (operacional + renda de fatores) da planilha Conab — "
                   "mesma base de custo das demais culturas"},
    ],
    "algodao_solteira": [
        {"chave": "referencia_preco_prod",
         "valor": "algodão em pluma R$ 138,67/@ 15 kg (R$ 9,24/kg de pluma) — preço "
                  "recebido do produtor, Conab, 28/09 a 02/10/2026 (Bahia); "
                  "produtividade 1.863 kg/ha de pluma (≈124 @/ha — média Cerrado)",
         "fonte_url": FONTE_CONAB_SEMANAL,
         "metodo": "margem esperada = preço_ref × prod_ref − custo Conab; a coluna "
                   "'Produtividade' da tábua ZARC do município está vazia — referência "
                   "das planilhas de custo Conab (Barreiras-BA 1.845 / Cristalina-GO 1.890)"},
        {"chave": "receita_caroco",
         "valor": "a receita do caroço (semente) já vem abatida no custo Conab — a receita "
                  "simulada é somente a da pluma",
         "fonte_url": FONTE_CUSTO_ALGODAO,
         "metodo": "a planilha de custo Conab credita o subproduto na linha 'Receita' "
                   "das despesas de custeio"},
        {"chave": "volatilidade_preco",
         "valor": "CV 20% lognormal no preço (documentada)",
         "fonte_url": FONTE_CONAB_SEMANAL,
         "metodo": "sem série anual de preços em Patos de Minas — volatilidade documentada"},
        {"chave": "custo_conab",
         "valor": "custo total R$ 17.071,42/ha — algodão 1ª safra, média 2024-2026 das "
                  "regiões Cerrado (Barreiras-BA e Cristalina-GO)",
         "fonte_url": FONTE_CUSTO_ALGODAO,
         "metodo": "CUSTO TOTAL (H+I=J) da planilha Conab — mesma base de custo das "
                   "demais culturas"},
    ],
}


def _hipoteses(rota: str) -> list:
    if rota in _HIPOTESES_NOVAS:
        return _HIPOTESES_NOVAS[rota]
    base = [
        {"chave": "referencia_preco_prod", "valor": "preço SIDRA × produtividade PAM (regime 2026/27)",
         "fonte_url": FONTE_SIDRA, "metodo": "margem esperada = preço_ref × prod_ref − custo Conab"},
        {"chave": "volatilidade_historica", "valor": "31 anos PAM×SIDRA pareados (1995-2025), rebased na referência",
         "fonte_url": FONTE_PAM, "metodo": "MC: desvios multiplicativos preço×prod preservando correlação"},
        {"chave": "custo_conab", "valor": "custo médio R$/ha Conab 2024-2026 (Cerrado)",
         "fonte_url": FONTE_CONAB, "metodo": "resumo_custos_para_engine.csv"},
    ]
    extra = []
    if rota == "soja_feijao2":
        # soja (série PAM×SIDRA, base acima) + feijão 2ª safra (referências Conab)
        return base + [
            {"chave": "preco_feijao2_ref",
             "valor": "feijão cores R$ 290,00/sc 60 kg (R$ 4,83/kg) — preço recebido do "
                      "produtor, Conab, 28/09 a 02/10/2026 (Paraná)",
             "fonte_url": FONTE_CONAB_SEMANAL,
             "metodo": "sem série anual em Patos — CV 25% lognormal (mesma regra do "
                       "feijão de 1ª safra)"},
            {"chave": "produtividade_feijao2_ref",
             "valor": "2.000 kg/ha — feijão 2ª safra (cores), produtividade média da "
                      "planilha de custo Conab (Francisco Beltrão-PR)",
             "fonte_url": FONTE_CUSTO_FEIJAO2,
             "metodo": "referência pareada com o custo da 2ª safra; a coluna "
                       "'Produtividade' da tábua ZARC do município está vazia"},
            {"chave": "custo_feijao2_conab",
             "valor": "custo total R$ 8.438,93/ha — feijão 2ª safra a sequeiro "
                      "(Francisco Beltrão-PR), média 2024-2026",
             "fonte_url": FONTE_CUSTO_FEIJAO2,
             "metodo": "CUSTO TOTAL (H+I=J) da planilha Conab — média das 2ªs safras; "
                       "3ªs safras irrigadas (Unaí-MG/Sorriso-MT) ficam fora por não "
                       "refletirem o sequeiro do ZARC"},
        ]
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
