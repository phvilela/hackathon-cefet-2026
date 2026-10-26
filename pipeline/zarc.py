#!/usr/bin/env python3
"""
pipeline/zarc.py — D2: Converte janelas ZARC (JSON do engine) → formato tabela para fato.parquet

Entrada:  engine/janelas_zarc.json (gerado por engine/adequacao.py)
Saída:    data/processed/zarc/janelas_zarc.parquet
          data/processed/zarc/rotacoes_zarc.parquet

Formato fato-friendly: uma linha por (cultura, grupo_solo, decendio, viavel, risco, tipo)
"""

from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
JSON_PATH = REPO / "engine/janelas_zarc.json"
OUT_DIR = REPO / "data/processed/zarc"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_janelas() -> dict[str, Any]:
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def culturas_to_table(data: dict) -> pd.DataFrame:
    """culturas -> linhas: cultura, grupo_solo, decendio, viavel, risco, solo_usado, ciclos"""
    rows = []
    for cultura, grupos in data["culturas"].items():
        for grupo_solo, info in grupos.items():
            solo_usado = info.get("solo_usado", "")
            ciclos = info.get("ciclos_disponiveis", [])
            decendios_viaveis = set(info.get("decendios", []))
            risco_map = info.get("risco_por_decendio", {})

            for dec in range(1, 37):
                viavel = dec in decendios_viaveis
                risco = risco_map.get(str(dec), 0)
                rows.append({
                    "cultura": cultura,
                    "grupo_solo": int(grupo_solo),
                    "decendio": dec,
                    "viavel": viavel,
                    "risco_percent": risco,
                    "solo_usado": solo_usado,
                    "ciclos_disponiveis": "|".join(map(str, ciclos)),
                    "municipio": data["cenario"]["municipio"],
                    "cod_ibge": data["cenario"]["cod_ibge"],
                    "safra": data["cenario"]["safra"],
                })
    return pd.DataFrame(rows)


def rotacoes_to_table(data: dict) -> pd.DataFrame:
    """rotacoes -> linhas: rotacao, grupo_solo, decendio, primeira_viavel, segunda_viavel, primeira_ciclo, ciclo_dias"""
    rows = []
    for rotacao, grupos in data["rotacoes"].items():
        for grupo_solo, info in grupos.items():
            primeira_viaveis = set(info.get("primeira", []))
            segunda_viaveis = set(info.get("segunda", []))
            primeira_ciclo = info.get("primeira_ciclo", "")
            ciclo_dias = info.get("premissa_ciclo_primeira_decendios", 0)

            todos_dec = set(primeira_viaveis) | set(segunda_viaveis)
            for dec in range(1, 37):
                rows.append({
                    "rotacao": rotacao,
                    "grupo_solo": int(grupo_solo),
                    "decendio": dec,
                    "primeira_viavel": dec in primeira_viaveis,
                    "segunda_viavel": dec in segunda_viaveis,
                    "primeira_ciclo": primeira_ciclo,
                    "ciclo_primeira_decendios": ciclo_dias,
                    "municipio": data["cenario"]["municipio"],
                    "cod_ibge": data["cenario"]["cod_ibge"],
                    "safra": data["cenario"]["safra"],
                })
    return pd.DataFrame(rows)


def premissas_to_table(data: dict) -> pd.DataFrame:
    """premissas -> linhas rastreáveis para tabela de hipóteses"""
    rows = []
    for p in data["premissas"]:
        rows.append({
            "chave": p["chave"],
            "valor": str(p["valor"]),
            "metodo": p["metodo"],
            "fonte_url": p["fonte_url"],
            "categoria": "ZARC",
        })
    return pd.DataFrame(rows)


def portarias_to_table(data: dict) -> pd.DataFrame:
    """portarias por cultura -> linhas"""
    rows = []
    for cultura, portarias in data["fonte"]["portarias_por_cultura"].items():
        for port in portarias:
            rows.append({
                "cultura": cultura,
                "portaria": port,
                "municipio": data["cenario"]["municipio"],
                "cod_ibge": data["cenario"]["cod_ibge"],
                "safra": data["cenario"]["safra"],
            })
    return pd.DataFrame(rows)


def main() -> int:
    if not JSON_PATH.exists():
        print(f"❌ {JSON_PATH} não existe. Rode primeiro: python3 engine/adequacao.py", file=sys.stderr)
        return 1

    print(f"Lendo {JSON_PATH}...")
    data = load_janelas()

    # 1. Culturas (plantio solteiro)
    df_cult = culturas_to_table(data)
    out_cult = OUT_DIR / "janelas_zarc_culturas.parquet"
    df_cult.to_parquet(out_cult, index=False)
    print(f"✅ {out_cult.name}: {len(df_cult)} linhas")

    # 2. Rotações (pareadas)
    df_rot = rotacoes_to_table(data)
    out_rot = OUT_DIR / "janelas_zarc_rotacoes.parquet"
    df_rot.to_parquet(out_rot, index=False)
    print(f"✅ {out_rot.name}: {len(df_rot)} linhas")

    # 3. Premissas (para hipóteses rastreáveis)
    df_prem = premissas_to_table(data)
    out_prem = OUT_DIR / "premissas_zarc.parquet"
    df_prem.to_parquet(out_prem, index=False)
    print(f"✅ {out_prem.name}: {len(df_prem)} linhas")

    # 4. Portarias
    df_port = portarias_to_table(data)
    out_port = OUT_DIR / "portarias_zarc.parquet"
    df_port.to_parquet(out_port, index=False)
    print(f"✅ {out_port.name}: {len(df_port)} linhas")

    # 5. Resumo legível
    print("\n--- Resumo janelas viáveis (culturas) ---")
    for cultura in sorted(df_cult["cultura"].unique()):
        sub = df_cult[df_cult["cultura"] == cultura]
        for grupo in sorted(sub["grupo_solo"].unique()):
            decs = sub[(sub["grupo_solo"] == grupo) & (sub["viavel"])]["decendio"].tolist()
            print(f"  {cultura:15} grupo {grupo}: {decs}")

    print("\n--- Resumo rotações (primeira cultura) ---")
    for rot in sorted(df_rot["rotacao"].unique()):
        sub = df_rot[df_rot["rotacao"] == rot]
        for grupo in sorted(sub["grupo_solo"].unique()):
            decs = sub[(sub["grupo_solo"] == grupo) & (sub["primeira_viavel"])]["decendio"].tolist()
            if decs:
                print(f"  {rot:15} grupo {grupo}: {decs}")
            else:
                print(f"  {rot:15} grupo {grupo}: INVIÁVEL")

    print(f"\nArquivos salvos em {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())