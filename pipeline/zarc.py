#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline/zarc.py
================
Consolidação das janelas de plantio do ZARC para Patos de Minas (MG)
HackatOhm 2026 - "O que plantar?"

OBJETIVO
--------
Transformar a tábua de risco oficial do ZARC em um formato enxuto por
cultura × grupo de solo, com a lista de decêndios viáveis (risco <= 40%).

FONTES
------
- data/raw/zarc/tabua-risco-2026-2027-patos-de-minas-3148004.csv
- geocodigo 3148004, safra 2026/27

REGRAS
------
- Grupo de solo: Cod_Solo (1,2,3) mapeado para grupos do modelo
- Decêndios: dec1..dec36 (valores 0,20,30,40,... representam % de risco)
- Viável quando risco <= 40% (conforme engine/config.yaml: risco_maximo_percent: 40)
- Foco no MVP: soja, milho 1ª safra, milho 2ª safra, feijão, feijão 2ª safra, sorgo granífero, sorgo granífero 2ª safra

SAÍDAS
------
- data/processed/zarc/zarc_janelas_por_cultura_solo.json
- data/processed/zarc/zarc_janelas_por_cultura_solo.csv
- data/processed/zarc/zarc_janelas_mvp.json

AUTOR / DATA
------------
D1 - Clima & Produtividade | HackatOhm 2026 | 2026-10-23
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_ZARC = ROOT / "data" / "raw" / "zarc" / "tabua-risco-2026-2027-patos-de-minas-3148004.csv"
OUT_DIR = ROOT / "data" / "processed" / "zarc"

RISCO_LIMITE = 40


def _ensure_dirs():
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def carregar_zarc() -> pd.DataFrame:
    df = pd.read_csv(RAW_ZARC, sep=";")
    return df


def consolidar(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    dec_cols = [f"dec{i}" for i in range(1, 37)]
    for _, r in df.iterrows():
        cultura = str(r["Nome_cultura"]).strip()
        solo = int(r["Cod_Solo"])
        ciclo = r.get("Cod_Ciclo")
        manejo = r.get("Nome_Outros_Manejos")
        viaveis = []
        for i, c in enumerate(dec_cols, start=1):
            val = r.get(c)
            try:
                v = float(val)
            except Exception:
                v = 100
            if v <= RISCO_LIMITE:
                viaveis.append(i)
        rows.append({
            "cultura": cultura,
            "grupo_solo": solo,
            "cod_ciclo": ciclo,
            "manejo": manejo,
            "decendios_viaveis": viaveis,
            "qtd_decendios": len(viaveis),
            "portaria": r.get("Portaria"),
        })
    res = pd.DataFrame(rows)
    return res


def filtrar_mvp(df: pd.DataFrame) -> pd.DataFrame:
    mvp = [
        "Soja",
        "Milho 1ª Safra",
        "Milho 2ª Safra",
        "Feijão",
        "Feijão 2ª Safra",
        "Feijão Caupi",
        "Sorgo Granífero",
        "Sorgo Granífero 2ª Safra",
    ]
    dfm = df[df["cultura"].isin(mvp)].copy()
    return dfm


def gerar_mapeamento_mvp(dfm: pd.DataFrame) -> Dict:
    out = {}
    for cultura, g in dfm.groupby("cultura"):
        out[cultura] = {}
        for solo, s in g.groupby("grupo_solo"):
            # preferir entrada com mais decêndios ou manter lista única
            decs = []
            for _, row in s.iterrows():
                decs.extend(row["decendios_viaveis"])
            # remover duplicados mantendo ordem
            decs_unicos = sorted(set(decs))
            out[cultura][str(solo)] = decs_unicos
    return out


def main():
    _ensure_dirs()
    print(f"[INICIO] Lendo {RAW_ZARC}")
    df = carregar_zarc()
    print(f"[OK] {len(df)} linhas")
    cons = consolidar(df)
    mvp = filtrar_mvp(cons)
    print(f"[OK] MVP: {len(mvp)} combinações")
    cons.to_csv(OUT_DIR / "zarc_janelas_por_cultura_solo.csv", index=False)
    cons.to_json(OUT_DIR / "zarc_janelas_por_cultura_solo.json", orient="records", force_ascii=False, indent=2)
    mvp.to_csv(OUT_DIR / "zarc_janelas_por_cultura_solo_mvp.csv", index=False)
    mapa = gerar_mapeamento_mvp(mvp)
    (OUT_DIR / "zarc_janelas_mvp.json").write_text(json.dumps(mapa, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Salvo em {OUT_DIR}")
    print(json.dumps(mapa, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
