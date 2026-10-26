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
cultura × grupo de solo, com a lista de decêndios viáveis.

FONTES
------
- data/raw/zarc/tabua-risco-2026-2027-patos-de-minas-3148004.csv
- geocodigo 3148004, safra 2026/27

REGRAS
------
- A tábua publica risco 20/30/40%; célula 0 significa fora do zoneamento.
  Portanto viável = 0 < risco <= 40.
- Sorgo usa grupo nativo 1/2/3. Soja, milho e feijão usam AD1/AD3/AD5
  (códigos 11/13/15), mapeados a partir do grupo de solo do talhão.
- Quando há mais de um ciclo, vale o menor risco por decêndio.
- Apenas manejo de sequeiro (o v0 não modela feijão irrigado).

SAÍDAS
------
- data/processed/zarc/zarc_janelas_por_cultura_solo.json
- data/processed/zarc/zarc_janelas_por_cultura_solo.csv
- data/processed/zarc/zarc_janelas_por_cultura_solo_mvp.csv
- data/processed/zarc/zarc_janelas_mvp.json

AUTOR / DATA
------------
D1 - Clima & Produtividade | HackatOhm 2026 | 2026-10-23
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_ZARC = ROOT / "data" / "raw" / "zarc" / "tabua-risco-2026-2027-patos-de-minas-3148004.csv"
OUT_DIR = ROOT / "data" / "processed" / "zarc"

RISCO_LIMITE = 40
DECENDIOS = range(1, 37)

CULTURAS = {
    "soja": {
        "nome_zarc": "Soja",
        "tipo_solo": "AD",
        "grupos": {1: 11, 2: 13, 3: 15},
        "solo_usado": {1: "AD1", 2: "AD3", 3: "AD5"},
    },
    "milho_verao": {
        "nome_zarc": "Milho 1ª Safra",
        "tipo_solo": "AD",
        "grupos": {1: 11, 2: 13, 3: 15},
        "solo_usado": {1: "AD1", 2: "AD3", 3: "AD5"},
    },
    "milho_safrinha": {
        "nome_zarc": "Milho 2ª Safra",
        "tipo_solo": "AD",
        "grupos": {1: 11, 2: 13, 3: 15},
        "solo_usado": {1: "AD1", 2: "AD3", 3: "AD5"},
    },
    "feijao": {
        "nome_zarc": "Feijão",
        "tipo_solo": "AD",
        "grupos": {1: 11, 2: 13, 3: 15},
        "solo_usado": {1: "AD1", 2: "AD3", 3: "AD5"},
    },
    "feijao_2": {
        "nome_zarc": "Feijão 2ª Safra",
        "tipo_solo": "AD",
        "grupos": {1: 11, 2: 13, 3: 15},
        "solo_usado": {1: "AD1", 2: "AD3", 3: "AD5"},
    },
    "sorgo_granifero": {
        "nome_zarc": "Sorgo Granífero",
        "tipo_solo": "nativo",
        "grupos": {1: 1, 2: 2, 3: 3},
        "solo_usado": {1: "grupo 1", 2: "grupo 2", 3: "grupo 3"},
    },
    "sorgo_safrinha": {
        "nome_zarc": "Sorgo Granífero 2ª Safra",
        "tipo_solo": "nativo",
        "grupos": {1: 1, 2: 2, 3: 3},
        "solo_usado": {1: "grupo 1", 2: "grupo 2", 3: "grupo 3"},
    },
}


def carregar_zarc() -> pd.DataFrame:
    return pd.read_csv(RAW_ZARC, sep=";")


def risco_minimo(sub: pd.DataFrame) -> dict[int, int]:
    risco: dict[int, int] = {}
    for _, row in sub.iterrows():
        for dec in DECENDIOS:
            valor = pd.to_numeric(row.get(f"dec{dec}"), errors="coerce")
            if pd.isna(valor):
                continue
            risco[dec] = min(risco.get(dec, 1000), int(valor))
    return {dec: valor for dec, valor in risco.items() if 0 < valor <= RISCO_LIMITE}


def consolidar(df: pd.DataFrame) -> list[dict]:
    registros = []
    for chave, meta in CULTURAS.items():
        base = df[
            (df["Nome_cultura"] == meta["nome_zarc"])
            & (df["Nome_Outros_Manejos"].fillna("Sequeiro") == "Sequeiro")
        ]
        for grupo in (1, 2, 3):
            codigo_solo = meta["grupos"][grupo]
            sub = base[base["Cod_Solo"] == codigo_solo]
            risco = risco_minimo(sub)
            registros.append(
                {
                    "cultura_key": chave,
                    "cultura": meta["nome_zarc"],
                    "grupo_solo": grupo,
                    "cod_solo": codigo_solo,
                    "solo_usado": meta["solo_usado"][grupo],
                    "decendios": sorted(risco),
                    "risco_por_decendio": {str(dec): risco[dec] for dec in sorted(risco)},
                    "ciclos_disponiveis": sorted(
                        {int(ciclo) for ciclo in sub["Cod_Ciclo"].dropna().unique()}
                    ),
                    "portaria": sub["Portaria"].dropna().iloc[0]
                    if not sub["Portaria"].dropna().empty
                    else None,
                }
            )
    return registros


def validar(registros: list[dict]) -> None:
    por_chave = {(r["cultura_key"], r["grupo_solo"]): r for r in registros}
    esperado = {
        ("soja", 1): 10,
        ("soja", 2): 10,
        ("soja", 3): 10,
        ("milho_verao", 1): 5,
        ("milho_safrinha", 1): 2,
        ("milho_safrinha", 2): 4,
        ("milho_safrinha", 3): 5,
        ("feijao", 1): 4,
        ("feijao", 2): 9,
        ("feijao", 3): 9,
        ("feijao_2", 1): 0,
        ("feijao_2", 2): 4,
        ("feijao_2", 3): 5,
        ("sorgo_granifero", 1): 8,
        ("sorgo_granifero", 2): 9,
        ("sorgo_granifero", 3): 9,
        ("sorgo_safrinha", 1): 5,
        ("sorgo_safrinha", 2): 6,
        ("sorgo_safrinha", 3): 7,
    }
    erros = []
    for chave, quantidade in esperado.items():
        registro = por_chave.get(chave)
        if registro is None:
            erros.append(f"ausente: {chave}")
            continue
        obtido = len(registro["decendios"])
        if obtido != quantidade:
            erros.append(f"{chave}: esperado {quantidade}, obtido {obtido}")
        if any(risco <= 0 or risco > RISCO_LIMITE for risco in registro["risco_por_decendio"].values()):
            erros.append(f"{chave}: risco fora da faixa 0 < r <= {RISCO_LIMITE}")
    if erros:
        raise ValueError("Falha na validação do ZARC:\n- " + "\n- ".join(erros))


def escrever(registros: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "zarc_janelas_por_cultura_solo.json").write_text(
        json.dumps(registros, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    csv_rows = []
    for registro in registros:
        csv_rows.append(
            {
                "cultura_key": registro["cultura_key"],
                "cultura": registro["cultura"],
                "grupo_solo": registro["grupo_solo"],
                "cod_solo": registro["cod_solo"],
                "solo_usado": registro["solo_usado"],
                "qtd_decendios": len(registro["decendios"]),
                "decendios": ";".join(str(dec) for dec in registro["decendios"]),
                "risco_por_decendio": json.dumps(
                    registro["risco_por_decendio"], ensure_ascii=False
                ),
                "ciclos_disponiveis": ";".join(
                    str(ciclo) for ciclo in registro["ciclos_disponiveis"]
                ),
                "portaria": registro["portaria"],
            }
        )
    df = pd.DataFrame(csv_rows)
    df.to_csv(OUT_DIR / "zarc_janelas_por_cultura_solo.csv", index=False)
    df[df["cultura_key"].isin(CULTURAS)].to_csv(
        OUT_DIR / "zarc_janelas_por_cultura_solo_mvp.csv", index=False
    )

    mvp = {}
    for registro in registros:
        mvp.setdefault(registro["cultura_key"], {})[str(registro["grupo_solo"])] = {
            "decendios": registro["decendios"],
            "risco_por_decendio": registro["risco_por_decendio"],
            "solo_usado": registro["solo_usado"],
            "ciclos_disponiveis": registro["ciclos_disponiveis"],
        }
    (OUT_DIR / "zarc_janelas_mvp.json").write_text(
        json.dumps(
            {
                "fonte": {
                    "arquivo": str(RAW_ZARC.relative_to(ROOT)),
                    "municipio": "Patos de Minas",
                    "cod_ibge": 3148004,
                    "safra": "2026/27",
                },
                "criterio": f"decêndio viável se 0 < risco <= {RISCO_LIMITE}",
                "culturas": mvp,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    print(f"[INICIO] Lendo {RAW_ZARC}")
    df = carregar_zarc()
    print(f"[OK] {len(df)} linhas brutas")
    registros = consolidar(df)
    validar(registros)
    escrever(registros)
    print(f"[OK] {len(registros)} combinações cultura x grupo de solo")
    for registro in registros:
        print(
            f"  {registro['cultura_key']:<17} grupo {registro['grupo_solo']} "
            f"({registro['solo_usado']:<8}) {len(registro['decendios']):>2} decêndios "
            f"{registro['decendios']}"
        )
    print(f"[OK] Saídas em {OUT_DIR}")


if __name__ == "__main__":
    main()
