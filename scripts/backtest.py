#!/usr/bin/env python3
"""Backtest retrospectivo do motor de decisao "O que plantar".

Decisao ex-ante (plantio em outubro do ano Y, com informacoes ate Y)
validada contra o realizado da colheita de Y+1 (PAM/SIDRA ano Y+1).

Metodologia (cada ano de decisao Y, cada janela de referencia W):
  - Trunca as series municipais ate Y (soja/milho do M1 CSV; sorgo/feijao do PAM).
  - Regime de referencia: preco_ref = media REAL da janela; prod_ref =
    REF_estrutural(cult) * (rendimento medio da janela / rendimento medio
    do historico truncado).
  - Custos Conab REAIS do ano Y (deflacionados a reais de set/2026; fontes
    nominais em conab_custos_todos.parquet, preços reais na serie M1 CSV).
  - Monte Carlo: mc.simula(pam_truncado, custos_reais, runs=20000, rng=42)
    -> margem esperada + risco (P[margem<0]) por rotacao.
  - Decisao: solve_lexicographic com configuracao de 600 ha, 1 talhao,
    solo medio (grupo 2). Escolha = rotacao que recebe toda a area.
  - Realizado (colheita Y+1): margem por cultura = prod_estrutural *
    (rendimento obs / media janela) * preco_real obs - custo_real(Y).
  - Comparacao: rank da escolha dentre as rotacoes validadas no realizado.

Braços de janela: 5, 10, "toda a historia" (>=8 anos exigidos, pula senao).

Dados tratados (reais de set/2026), que --preparar cria:
  data/raw/mercado/backtest/      (furos fonte originais)
  data/processed/mercado/backtest/*.csv

Uso:
  python3 scripts/backtest.py --preparar       # baixa + valida calibracao
  python3 scripts/backtest.py --ano 2023        # caso unico
  python3 scripts/backtest.py --todos           # estudo 2005-2024
  python3 scripts/backtest.py --todos --janela 5 --json out.json
"""
import argparse
import copy
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import monte_carlo as mc
from engine.solver import solve_lexicographic

REPO = Path(__file__).resolve().parent.parent
PAM_CSV = REPO / "notebooks" / "saida_preco" / "dados_anuais_Patos_de_Minas.csv"
CONAB_PARQUET = (
    REPO / "data" / "processed" / "mercado" / "conab_custos" / "conab_custos_todos.parquet"
)
CONFIG_PATH = REPO / "engine" / "config.yaml"

RAW_DIR = REPO / "data" / "raw" / "mercado" / "backtest"
PROC_DIR = REPO / "data" / "processed" / "mercado" / "backtest"

BASE_MONTH = "2026-09"  # reais de set/2026 (base do M1 congelado, calibrada)

# Codigo de oportunidade: custeio ~R$ 3500/ha por ~5 meses (mirrora config.yaml).
CUSTEO_ANUAL_REF = 3500.0
MESES_CAPITAL = 5


# ----------------------------------------------------------------------------- dados brutos
def _fetch_json(url: str, tentativas: int = 4) -> list:
    import time
    ultimo = None
    for i in range(tentativas):
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            ultimo = e
            time.sleep(2 ** i)
    raise ultimo


def _fetch_selic_chunks() -> pd.DataFrame:
    """Selic acumulada no mês (SGS 1178) — diário, fatiado em blocos <=10 anos."""
    chunks = [
        ("01/01/2002", "31/12/2011"),
        ("01/01/2012", "31/12/2021"),
        ("01/01/2022", "31/12/2026"),
    ]
    frames = []
    for i, (ini, fim) in enumerate(chunks, 1):
        url = (
            "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1178/dados"
            f"?formato=json&dataInicial={ini}&dataFinal={fim}"
        )
        data = _fetch_json(url)
        path = RAW_DIR / f"selic_1178_parte{i}.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        frames.append(pd.DataFrame(data))
    selic = pd.concat(frames, ignore_index=True)
    selic["data"] = pd.to_datetime(selic["data"], format="%d/%m/%Y")
    selic["valor"] = pd.to_numeric(selic["valor"], errors="coerce")
    selic = selic.set_index("data").sort_index()
    mensal = selic.groupby(selic.index.to_period("M"))["valor"].last()
    return mensal


def _fetch_ipca() -> pd.Series:
    url = (
        "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados"
        "?formato=json&dataInicial=01/01/1995&dataFinal=31/12/2026"
    )
    data = _fetch_json(url)
    (RAW_DIR / "ipca_433.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    df = pd.DataFrame(data)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    s = df.set_index("data").sort_index()["valor"]
    idx = s.groupby(s.index.to_period("M")).last()
    return idx


def _build_indices(ipca_m: pd.Series) -> pd.Series:
    indice = (1 + ipca_m / 100).cumprod()
    return indice


def fator_deflacao(indice: pd.Series, ano: int, base: str = BASE_MONTH) -> float:
    """Fator que leva um nominal do ano Y para reais do mes base (set/2026)."""
    idx_ano = indice[indice.index.year == ano].mean()
    return float(indice.loc[base] / idx_ano)


def _calibracao_ok(indice: pd.Series) -> bool:
    """Reproduz preco_real do CSV do M1 a partir do nominal (gate de validacao)."""
    df = pd.read_csv(PAM_CSV, header=[0, 1], index_col=0)
    testes = [(2015, "Milho"), (2020, "Milho"), (2023, "Milho"), (2025, "Milho"),
              (2015, "Soja"), (2020, "Soja"), (2023, "Soja"), (2025, "Soja")]
    ok_all = True
    print("Gate de calibracao (preco real: calc vs alvo):")
    for ano, cult in testes:
        nom = float(df.loc[ano, ("preco_nominal_rs_saca", cult)])
        alvo = float(df.loc[ano, ("preco_real_rs_saca", cult)])
        alvo = alvo / nom
        calc = fator_deflacao(indice, ano)
        dif = abs(calc - alvo)
        ok = dif < 0.005
        ok_all = ok_all and ok
        print(f"  {ano} {cult}: calc {calc:.4f} | alvo {alvo:.4f} | dif {dif:.4f} {'OK' if ok else 'FALHA'}")
    return ok_all


# ----------------------------------------------------------------------------- series municipais
def _carrega_pam_municipal() -> pd.DataFrame:
    """M1 CSV: soja/milho, anos 1995-2025, preco REAL (reais de set/2026)."""
    return mc._carrega_pam()


def _carrega_sorgo_feijao_pam() -> pd.DataFrame:
    """PAM sorgo/feijao por ano civil (implicito preco R$/kg = valor/quantidade)."""
    raw = RAW_DIR / "pam_sorgo_feijao.json"
    if not raw.exists():
        url = (
            "https://apisidra.ibge.gov.br/values/t/5457/n6/3148004/"
            "c782/40112,40125/v/112,214,215/p/all"
        )
        data = _fetch_json(url)
        raw.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    rows = json.loads(raw.read_text(encoding="utf-8"))[1:]  # pula cabecalho de metadados
    PRODUTOS_VALIDOS = ("Feijão (em grão)", "Sorgo (em grão)")
    VARIAVEIS_VALIDAS = ("Rendimento médio da produção", "Quantidade produzida",
                         "Valor da produção")
    recs = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        # Dimensões: pares (código, nome) em D1C/D1N .. D4C/D4N. A ordem
        # varia com o filtro, então identifica cada uma pelo VALOR (nome),
        # não pela chave.
        produto_codigo = variavel_codigo = ano_codigo = None
        produto_nome = variavel_nome = ano_nome = None
        for sufixo in ("1", "2", "3", "4"):
            nome = r.get(f"D{sufixo}N")
            nome = nome.strip() if isinstance(nome, str) else nome
            codigo = r.get(f"D{sufixo}C")
            if nome in PRODUTOS_VALIDOS:
                produto_codigo, produto_nome = codigo, nome
            elif nome in VARIAVEIS_VALIDAS:
                variavel_codigo, variavel_nome = codigo, nome
            elif nome is not None and str(nome).isdigit() and len(str(nome)) == 4:
                ano_codigo, ano_nome = codigo, nome
        produto = produto_nome
        variavel = variavel_nome
        ano_raw = ano_nome
        valor = r.get("V")
        if produto not in PRODUTOS_VALIDOS:
            continue
        if variavel not in VARIAVEIS_VALIDAS:
            continue
        try:
            ano_i = int(str(ano_raw).strip())
            valor_f = float(valor)
        except (TypeError, ValueError):
            continue
        recs.append({"ano": ano_i, "cultura": "feijao" if produto.startswith("Feijão") else "sorgo",
                     "variavel": variavel, "valor": valor_f})
    df = pd.DataFrame(recs)
    if df.empty:
        return df
    wide = df.pivot_table(index="ano", columns=["cultura", "variavel"], values="valor", aggfunc="first")
    wide.columns = [f"{c}_{v}" for c, v in wide.columns]
    wide = wide.reset_index()
    wide["preco_feijao_rs_kg"] = wide["feijao_Valor da produção"] / wide["feijao_Quantidade produzida"]
    wide["preco_sorgo_rs_kg"] = wide["sorgo_Valor da produção"] / wide["sorgo_Quantidade produzida"]
    wide = wide.rename(columns={"sorgo_Rendimento médio da produção": "rend_sorgo",
                                "feijao_Rendimento médio da produção": "rend_feijao"})
    return wide


# ----------------------------------------------------------------------------- ex-ante
def _regime_ex_ante(pam: pd.DataFrame, pam_sf: pd.DataFrame, ano: int, janela: int | str) -> dict:
    """Referencia (preco_ref, prod_ref) com dados ate o ano da decisao."""
    disponiveis = sorted(pam.index.unique())
    if isinstance(janela, int):
        recentes = [y for y in disponiveis if y <= ano][-janela:]
        if len(recentes) < 3:
            return {"skip": f"apenas {len(recentes)} anos <= {ano} (min 3)"}
        window = recentes
    else:
        window = [y for y in disponiveis if y <= ano]
        if len(window) < 3:
            return {"skip": f"historico truncado tem {len(window)} anos <= {ano} (min 3)"}

    refs = {}
    for cult, pc, pp in [("soja", "prod_soja", "preco_soja"),
                         ("milho", "prod_milho", "preco_milho")]:
        win_y = pam.loc[window]
        p_ref = float(win_y[pp].mean())
        prod_mean_hist = float(pam[pc].mean())
        prod_mean_win = float(win_y[pc].mean())
        # fator unitless: produtividade da janela vs media historica
        f_prod = prod_mean_win / prod_mean_hist
        refs[cult] = {"preco": p_ref, "prod_factor": f_prod}

    # sorgo/feijao: preco real do PAM proprio
    for cult, col_r, col_p in [("sorgo", "rend_sorgo", "preco_sorgo_rs_kg"),
                               ("feijao", "rend_feijao", "preco_feijao_rs_kg")]:
        if pam_sf.empty:
            return {"skip": f"sem serie PAM de {cult} para ano {ano}"}
        linha = pam_sf[(pam_sf["ano"] <= ano) & (pam_sf[col_r].notna())].sort_values("ano").tail(1)
        if linha.empty:
            return {"skip": f"sem PAM {cult} ate {ano}"}
        linha = linha.iloc[0]
        f_ipca = fator_deflacao(_INDICE, ano)
        p_ref = float(linha[col_p]) * f_ipca
        win_sf = pam_sf[pam_sf["ano"] <= ano]
        prod_mean_hist = float(win_sf[col_r].dropna().mean())
        prod_mean_win = float(linha[col_r])
        f_prod = prod_mean_win / prod_mean_hist if prod_mean_hist > 0 else 1.0
        refs[cult] = {"preco": p_ref, "prod_factor": f_prod}

    return {"window": window, "refs": refs}


def _ex_ante(cfg_base: dict, refs: dict, custos: dict, selic_real: float,
             area: int, grupo: int, runs: int) -> dict:
    """Roda MC + solver com o regime injetado. Retorna dict da decisao."""
    mc_cfg = copy.deepcopy(cfg_base)
    mc_cfg["talhoes"] = {"T1": {"area_ha": area, "grupo_solo": grupo, "irrigacao": True}}
    mc_cfg["pareto"] = {"points": 12, "min_margem_ratio": 0.2}

    mc.REF = {
        # Soja/milho: serie municipal de preco e produtividade (PAM/SIDRA Patos).
        "soja": {"prod": mc.REF["soja"]["prod"] * refs["soja"]["prod_factor"],
                 "preco": refs["soja"]["preco"]},
        "milho_safr": {"prod": mc.REF["milho_safr"]["prod"] * refs["milho"]["prod_factor"],
                       "preco": refs["milho"]["preco"]},
        "milho_verao": {"prod": mc.REF["milho_verao"]["prod"] * refs["milho"]["prod_factor"],
                        "preco": refs["milho"]["preco"]},
        # Sorgo/feijao: preco do PAM municipal (quando disponivel); produto de referencia.
        "sorgo": {"prod": mc.REF["sorgo"]["prod"] * refs["sorgo"]["prod_factor"],
                  "preco": refs["sorgo"]["preco"]},
        "feijao": {"prod": mc.REF["feijao"]["prod"] * refs["feijao"]["prod_factor"],
                   "preco": refs["feijao"]["preco"]},
    }
    # Arroz/algodao/soja-feijao2: hipotese de referencia (sem serie municipal).
    # Precisam de REF para mc.simula nao quebrar, mas NAO entram no solver
    # (removidas de mc_cfg["rotacoes"] abaixo) nem na validacao retrospectiva.
    mc.REF["arroz"] = {"prod": 5500.0, "preco": 2.20}
    mc.REF["algodao"] = {"prod": 2500.0, "preco": 4.60}
    mc.REF["feijao_2"] = {"prod": mc.REF["feijao"]["prod"], "preco": mc.REF["feijao"]["preco"]}
    mc.CV_PRECO_REF["arroz"] = 0.20
    mc.CV_PRECO_REF["algodao"] = 0.25
    mc.CV_PRECO_REF["feijao_2"] = 0.25
    custos = dict(custos)
    custos.setdefault("algodao_em_pluma", 6000.0)
    custos.setdefault("arroz_sequeiro", 4500.0)
    custos.setdefault("feijao_2a_safra", 8000.0)
    mc_cfg["rotacoes"] = {k: v for k, v in mc_cfg["rotacoes"].items()
                          if k in ("soja_solteira", "milho_verao", "soja_milho",
                                   "soja_sorgo", "feijao_sorgo", "capital_pousio")}
    mc.CUSTO_MILHO_VERAO = custos.get("milho_1a_safra", mc.CUSTO_MILHO_VERAO)

    rng = np.random.default_rng(42)
    margens = mc.simula(pam=_TRUNCATED_PAM, custos=custos, runs=runs, rng=rng)

    for rot, arr in margens.items():
        if rot in mc_cfg["rotacoes"]:
            m_ha = float(np.mean(arr))
            r_pm = float((arr < 0).mean()) * 1000
            mc_cfg["rotacoes"][rot]["margem_esperada"] = int(round(max(-2000000, min(2000000, m_ha * 100))))
            mc_cfg["rotacoes"][rot]["risco"] = int(round(max(0, min(1000, r_pm))))

    try:
        sol = solve_lexicographic(mc_cfg)
    except Exception:
        sol = None
    if sol is None:
        return {
            "escolha": None, "hectares": 0,
            "margem_esperada_ha": None, "risco_esperado_per_mil": None,
            "margens_ex_ante": {rot: float(np.mean(arr)) for rot, arr in margens.items()},
            "risco_ex_ante": {rot: float((arr < 0).mean()) for rot, arr in margens.items()},
            "plano": None, "sem_solucao": True,
        }
    plano = sol.get("plano", {})
    t1 = plano.get("T1", {})
    escolha = max(t1.items(), key=lambda kv: kv[1])[0] if t1 else None
    hectares = t1.get(escolha, 0) if escolha else 0

    return {
        "escolha": escolha,
        "hectares": hectares,
        "margem_esperada_ha": float(np.mean(margens[escolha])) if escolha else None,
        "risco_esperado_per_mil": float((margens[escolha] < 0).mean() * 1000) if escolha else None,
        "margens_ex_ante": {rot: float(np.mean(arr)) for rot, arr in margens.items()},
        "risco_ex_ante": {rot: float((arr < 0).mean()) for rot, arr in margens.items()},
        "plano": sol.get("area_por_rotacao"),
    }


# ----------------------------------------------------------------------------- ex-post
def _realizado(pam: pd.DataFrame, pam_sf: pd.DataFrame, refs: dict, custos: dict,
               selic_real: float) -> dict:
    """Margem realizada da colheita do ano seguinte (dados observados)."""
    ano = _ANO_DECISAO
    ano_colheita = ano + 1
    out = {}
    rend_hist = {"soja": float(pam["prod_soja"].mean()),
                 "milho": float(pam["prod_milho"].mean()),
                 "sorgo": float(pam_sf["rend_sorgo"].dropna().mean()) if not pam_sf.empty else np.nan,
                 "feijao": float(pam_sf["rend_feijao"].dropna().mean()) if not pam_sf.empty else np.nan}

    for cult, col_r, col_p, custo_key, prod_ref in [
        ("soja", "prod_soja", "preco_soja", "soja", mc.REF["soja"]["prod"]),
        ("milho_safr", "prod_milho", "preco_milho", "milho_2a_safra", mc.REF["milho_safr"]["prod"]),
        ("milho_verao", "prod_milho", "preco_milho", "milho_1a_safra", mc.REF["milho_verao"]["prod"]),
        ("sorgo", "rend_sorgo", "preco_sorgo_rs_kg", "sorgo", mc.REF["sorgo"]["prod"]),
        ("feijao", "rend_feijao", "preco_feijao_rs_kg", "feijao_1a_safra", mc.REF["feijao"]["prod"]),
    ]:
        try:
            if cult in ("soja", "milho"):
                linha = pam.loc[ano_colheita]
                prod_obs = float(linha[col_r])
                preco_obs = float(linha[col_p])
            else:
                linha = pam_sf[pam_sf["ano"] == ano_colheita]
                if linha.empty:
                    continue
                linha = linha.iloc[0]
                prod_obs = float(linha[col_r])
                f_ipca = fator_deflacao(_INDICE, ano_colheita)
                preco_obs = float(linha[col_p]) * f_ipca
        except (KeyError, ValueError):
            continue
        if prod_obs <= 0 or preco_obs <= 0:
            continue
        if custo_key not in custos:
            continue
        prod_real = prod_ref * (prod_obs / rend_hist[cult.replace("_safr", "")])
        receita = prod_real * preco_obs
        margem = receita - custos[custo_key]
        out[cult] = margem

    rotacoes = {
        "soja_solteira": (out.get("soja"),),
        "milho_verao": (out.get("milho_safr"),),
        "soja_milho": (out.get("soja") if "soja" in out else None,
                       out.get("milho_safr") if "milho_safr" in out else None),
        "soja_sorgo": (out.get("soja") if "soja" in out else None,
                       out.get("sorgo") if "sorgo" in out else None),
        "feijao_sorgo": (out.get("feijao") if "feijao" in out else None,
                         out.get("sorgo") if "sorgo" in out else None),
        "arroz_solteira": (out.get("arroz"),),
        "algodao_solteira": (out.get("algodao"),),
        "soja_feijao2": (out.get("soja") if "soja" in out else None,
                         out.get("feijao_2") if "feijao_2" in out else None),
    }
    disponiveis = {}
    for rot, partes in rotacoes.items():
        if todas(partes):
            disponiveis[rot] = sum(partes)
    disponiveis["capital_pousio"] = CUSTEO_ANUAL_REF * selic_real / 100 * MESES_CAPITAL / 12
    ranking = sorted(disponiveis.items(), key=lambda kv: -kv[1])
    return {"disponiveis": disponiveis, "ranking": ranking,
            "obs_ano": ano_colheita}


def todas(vals):
    return all(v is not None for v in vals)


# ----------------------------------------------------------------------------- CLI
def cmd_preparar(args):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROC_DIR.mkdir(parents=True, exist_ok=True)

    ipca_m = _fetch_ipca()
    global _INDICE
    _INDICE = _build_indices(ipca_m)
    if not _calibracao_ok(_INDICE):
        print("\nFALHA NA CALIBRACAO: preco real reconstruido diverge do M1.", file=sys.stderr)
        sys.exit(2)

    mensal_selic = _fetch_selic_chunks()
    selic_anual = mensal_selic.groupby(mensal_selic.index.year).apply(
        lambda s: float(np.prod(1 + s / 100) - 1))
    ipca_anual = ipca_m.groupby(ipca_m.index.year).apply(
        lambda s: float(np.prod(1 + s / 100) - 1))
    selic_real = (1 + selic_anual) / (1 + ipca_anual) - 1
    anual = pd.DataFrame({"selic_nominal_aa": selic_anual, "ipca_aa": ipca_anual,
                          "selic_real_aa": selic_real})
    anual.to_csv(PROC_DIR / "selic_ipca_anual.csv")

    conab = pd.read_parquet(CONAB_PARQUET)
    conab["ano"] = pd.to_numeric(conab["ano"], errors="coerce")
    conab = conab.dropna(subset=["ano"])
    conab["ano"] = conab["ano"].astype(int)
    custos = []
    for (ano, cultura), sub in conab.groupby(["ano", "cultura"]):
        if len(sub) < 1:
            continue
        c_real = float(sub["custo_total_ha"].mean()) * fator_deflacao(_INDICE, int(ano))
        custos.append({"ano": int(ano), "cultura": cultura, "custo_real_ha": round(c_real, 2),
                       "n_regioes": int(len(sub))})
    pd.DataFrame(custos).to_csv(PROC_DIR / "custos_conab_reais.csv", index=False)

    pam_sf = _carrega_sorgo_feijao_pam()
    if not pam_sf.empty:
        pam_sf.to_csv(PROC_DIR / "pam_sorgo_feijao_real.csv", index=False)

    print("=== --preparar concluído ===")
    print(f"IPCA: {_INDICE.index[0]} a {_INDICE.index[-1]} | base {BASE_MONTH}")
    print(f"Selic mensal: {len(mensal_selic)} meses")
    print("Arquivos processados em", PROC_DIR)


def cmd_ano(args):
    global _TRUNCATED_PAM, _ANO_DECISAO
    _ANO_DECISAO = args.ano
    pam = _carrega_pam_municipal()
    pam_sf = _carrega_sorgo_feijao_pam()
    _TRUNCATED_PAM = pam[pam.index <= args.ano]

    indice = _build_indices(_fetch_ipca())
    f_ipca = fator_deflacao(indice, args.ano)
    selic_anual = pd.read_csv(PROC_DIR / "selic_ipca_anual.csv", index_col=0)
    selic_real = float(selic_anual.loc[args.ano, "selic_real_aa"])

    custos_df = pd.read_csv(PROC_DIR / "custos_conab_reais.csv")
    custos = {r["cultura"]: float(r["custo_real_ha"])
              for _, r in custos_df[custos_df["ano"] == args.ano].iterrows()}
    for c in ["soja", "milho_2a_safra", "sorgo", "feijao_1a_safra"]:
        if c not in custos:
            print(f"AVISO: custo nao disponível para {c} em {args.ano}", file=sys.stderr)

    regime = _regime_ex_ante(pam, pam_sf, args.ano, args.janela)
    if "skip" in regime:
        print(f"Ano {args.ano} pulado (janela {args.janela}): {regime['skip']}")
        return

    cfg_base = copy.deepcopy(yaml.safe_load(open(CONFIG_PATH)))
    ex = _ex_ante(cfg_base, regime["refs"], custos, selic_real, args.area, args.grupo, args.runs)

    realizado = _realizado(pam, pam_sf, regime["refs"], custos, selic_real)
    obs_ano = realizado["obs_ano"]
    refs = regime["refs"]
    print(f"\n======= CASO {args.ano} (decisao out/{args.ano} | colheita {obs_ano}) =======")
    if ex.get("sem_solucao") or ex["escolha"] is None:
        print("O solver nao encontrou solucao viavel (todas as rotacoes com margem abaixo do piso).")
        return
    print(f"Janela: {regime['window'][0]}-{regime['window'][-1]} ({len(regime['window'])} anos) | "
          f"Selic real {args.ano}: {selic_real*100:.1f}% a.a.")
    print("Regime ex-ante:")
    for cult, r in refs.items():
        print(f"  {cult:10} preco {r['preco']:>9.2f} | fator prod {r['prod_factor']:.3f}")
    print("\nEx-ante (MC, 20000 runs):")
    for rot in sorted(ex["margens_ex_ante"]):
        m = ex["margens_ex_ante"][rot]; r = ex["risco_ex_ante"][rot]
        marca = " <== ESCOLHA" if rot == ex["escolha"] else ""
        print(f"  {rot:14} margem R$ {m:>8,.0f}/ha | risco {r*100:4.1f}%{marca}")
    print(f"\nDecisao: {ex['escolha']} ({ex['hectares']} ha) | margem R$ {ex['margem_esperada_ha']:,.0f}/ha | "
          f"risco {ex['risco_esperado_per_mil']/10:.1f}%")

    print(f"\nRealizado {obs_ano} (PAM/SIDRA ano {obs_ano}):")
    ranking = realizado["ranking"]
    for i, (rot, m) in enumerate(ranking, 1):
        marca = " <== sua escolha" if rot == ex["escolha"] else ""
        print(f"  {i}. {rot:14} margem R$ {m:>9,.0f}/ha{marca}")
    rank_escolha = [r for r, _ in ranking].index(ex["escolha"]) + 1 if ex["escolha"] in \
        [r for r, _ in ranking] else None
    melhor = ranking[0][0]
    gap = ranking[0][1] - (realizado["disponiveis"].get(ex["escolha"], float("nan")))
    print(f"\nVeredito: escolha '{ex['escolha']}' ficou rank {rank_escolha} de {len(ranking)}; "
          f"melhor realizada foi '{melhor}' (gap {gap:+,.0f} R$/ha)")


def cmd_todos(args):
    global _TRUNCATED_PAM, _ANO_DECISAO
    anos = list(range(2005, 2025))  # decisao Y -> colheita Y+1 (até 2025)
    pam = _carrega_pam_municipal()
    pam_sf = _carrega_sorgo_feijao_pam()
    indice = _build_indices(_fetch_ipca())
    selic_tab = pd.read_csv(PROC_DIR / "selic_ipca_anual.csv", index_col=0)
    custos_tab = pd.read_csv(PROC_DIR / "custos_conab_reais.csv")
    cfg_base = copy.deepcopy(yaml.safe_load(open(CONFIG_PATH)))

    janelas = {"5": 5, "10": 10, "toda": None}
    if args.janela:
        janelas = {args.janela: janelas.get(args.janela, args.janela)}

    resultados = []
    for ano in anos:
        _ANO_DECISAO = ano
        _TRUNCATED_PAM = pam[pam.index <= ano]
        f_ipca = fator_deflacao(indice, ano)
        if ano not in selic_tab.index:
            continue
        selic_real = float(selic_tab.loc[ano, "selic_real_aa"])
        custos_df = custos_tab[custos_tab["ano"] == ano]
        custos = {r["cultura"]: float(r["custo_real_ha"]) for _, r in custos_df.iterrows()}
        # Fallback: media historica para culturas sem custo Conab naquele ano.
        media_hist = custos_tab.groupby("cultura")["custo_real_ha"].mean()
        for c in ["soja", "milho_2a_safra", "sorgo", "feijao_1a_safra", "milho_1a_safra",
                  "arroz", "algodao", "feijao_2a_3a_safras"]:
            custos.setdefault(c, float(media_hist.get(c, custos.get(c, 5000.0))))
        for nome_w, W in janelas.items():
            regime = _regime_ex_ante(pam, pam_sf, ano, W)
            if "skip" in regime:
                continue
            ex = _ex_ante(cfg_base, regime["refs"], custos, selic_real,
                          args.area, args.grupo, args.runs)
            if ex.get("sem_solucao") or ex["escolha"] is None:
                resultados.append({
                    "ano": ano, "janela": nome_w, "escolha": None,
                    "margem_esperada": None, "risco_ex_ante": None,
                    "melhor_realizada": None, "margem_melhor": None,
                    "margem_escolha": None, "rank": None, "gap": None,
                    "escolha_positiva": None, "capital_venceu": None,
                    "sem_solucao": True,
                })
                continue
            real = _realizado(pam, pam_sf, regime["refs"], custos, selic_real)
            ranking = real["ranking"]
            nomes_realizados = [r for r, _ in ranking]
            escolha = ex["escolha"]
            if escolha not in nomes_realizados:
                # Escolha sem dado de colheita para validar (ex. arroz/algodao com
                # hipotese de referencia). Nao conta como acerto nem erro.
                resultados.append({
                    "ano": ano, "janela": nome_w, "escolha": escolha,
                    "margem_esperada": ex["margem_esperada_ha"],
                    "risco_ex_ante": ex["risco_esperado_per_mil"] / 10,
                    "melhor_realizada": ranking[0][0] if ranking else None,
                    "margem_melhor": ranking[0][1] if ranking else None,
                    "margem_escolha": None,
                    "rank": None, "gap": None,
                    "escolha_positiva": None, "capital_venceu": None,
                    "sem_solucao": False, "nao_validavel": True,
                })
                continue
            rank_e = nomes_realizados.index(escolha) + 1
            melhor = ranking[0][0]
            gap = ranking[0][1] - real["disponiveis"][escolha]
            resultados.append({
                "ano": ano, "janela": nome_w, "escolha": escolha,
                "margem_esperada": ex["margem_esperada_ha"],
                "risco_ex_ante": ex["risco_esperado_per_mil"] / 10,
                "melhor_realizada": melhor,
                "margem_melhor": ranking[0][1],
                "margem_escolha": real["disponiveis"][escolha],
                "rank": rank_e,
                "gap": gap,
                "escolha_positiva": bool(real["disponiveis"][escolha] >= 0),
                "capital_venceu": bool(melhor == "capital_pousio"),
                "sem_solucao": False, "nao_validavel": False,
            })

    df = pd.DataFrame(resultados)
    print(f"\n======= ESTUDO MULTI-ANO ({args.janela or 'todas'}) =======")
    for nome_w, W in janelas.items():
        sub = df[df["janela"] == nome_w]
        if sub.empty:
            continue
        val = sub[(sub["sem_solucao"] == False) & (sub["nao_validavel"] == False)]
        n_val = len(val)
        hit = (val["rank"] == 1).mean() * 100 if n_val > 0 else 0.0
        cap = val["capital_venceu"].mean() * 100 if n_val > 0 else 0.0
        pos = val["escolha_positiva"].mean() * 100 if n_val > 0 else 0.0
        n_inv = int(sub["sem_solucao"].sum())
        n_nv = int(sub["nao_validavel"].sum())
        print(f"Janela {nome_w}: n={len(sub)} | validaveis={n_val} | "
              f"hit-rate (escolha==melhor) {hit:.0f}% | escolha em prejuízo {100-pos:.0f}% | "
              f"capital venceu {cap:.0f}% | rank medio {val['rank'].mean():.1f}"
              + (f" | sem_solucao={n_inv} | nao_validavel={n_nv}" if (n_inv or n_nv) else ""))
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        df.to_json(args.json, orient="records", force_ascii=False, indent=2)
        print("JSON salvo em", args.json)
    print("\nTabela ano a ano:")
    print(df[["ano", "janela", "escolha", "rank", "melhor_realizada", "gap", "escolha_positiva"]]
          .to_string(index=False))


def main():
    ap = argparse.ArgumentParser(description="Backtest retrospectivo do motor de decisao")
    ap.add_argument("--preparar", action="store_true", help="baixa dados e valida calibracao")
    ap.add_argument("--ano", type=int, metavar="Y", help="caso unico: decisao em out/Y")
    ap.add_argument("--todos", action="store_true", help="estudo 2005-2024")
    ap.add_argument("--janela", type=str, help="5 | 10 | toda (só com --todos)")
    ap.add_argument("--area", type=int, default=600)
    ap.add_argument("--grupo", type=int, default=2)
    ap.add_argument("--runs", type=int, default=20000)
    ap.add_argument("--json", type=str, help="caminho para dump JSON (só --todos)")
    a = ap.parse_args()

    if a.preparar:
        cmd_preparar(a)
        return
    if not PROC_DIR.exists() or not (PROC_DIR / "selic_ipca_anual.csv").exists():
        print("Rode primeiro --preparar", file=sys.stderr)
        sys.exit(2)
    global _INDICE
    _INDICE = _build_indices(_fetch_ipca())
    if a.ano:
        cmd_ano(a)
    elif a.todos:
        cmd_todos(a)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
