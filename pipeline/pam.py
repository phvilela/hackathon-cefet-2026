#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline/pam.py
================
Download e tratamento da Produção Agrícola Municipal (PAM) - IBGE/SIDRA
para o HackatOhm 2026 - "O que plantar?"

OBJETIVO
--------
Baixar a produtividade histórica por cultura para Patos de Minas (MG),
converter de ano civil para ano-safra (quando necessário) e gerar arquivos
prontos para a tabela fato (`data/processed/pam/`).

FONTE
-----
IBGE SIDRA - Tabela 839 (Produção Agrícola Municipal)
- Município: Patos de Minas - Código IBGE **3148004**
- Variável principal: v=214 - Rendimento médio (kg/ha)
- Produtos: c81/all
- Período: p=last 20 (anos civis)
- Endpoint referência:
  https://apisidra.ibge.gov.br/values/t/839/n6/3148004/v/214/p/last%2020/c81/all

REGRAS IMPORTANTES
------------------
- PAM usa **ano civil**, não ano-safra (jul/jun). A conversão deve ficar
  documentada e aplicada de forma explícita.
- PAM **não separa milho 1ª safra e 2ª safra** (milho safrinha). A Conab faz essa
  separação. Essa limitação deve ser registrada na rastreabilidade.
- Código correto: **3148004**. **Não** usar 3138107.
- Salvar **bruto** em data/raw/ibge/pam/ e **tratado** em data/processed/pam/
- Não rebaixar do portal ao vivo no site/demo; tudo deve ficar versionado.

SAÍDAS ESPERADAS (sugeridas)
---------------------------
- data/raw/ibge/pam/pam_3148004_rendimento_ultimos20.json  (bruto)
- data/raw/ibge/pam/pam_3148004_rendimento_ultimos20.csv   (bruto, ; )
- data/processed/pam/pam_pat_minas_rendimento_tratado.csv   (limpo/normalizado)
- data/processed/pam/pam_pat_minas_rendimento_ano_safra.csv (se aplicado)

DEPENDÊNCIAS
------------
requests, pandas

AUTOR / DATA
------------
D1 - Clima & Produtividade | HackatOhm 2026 | 2026-10-23
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW_PAM_DIR = ROOT / "data" / "raw" / "ibge" / "pam"
PROCESSED_PAM_DIR = ROOT / "data" / "processed" / "pam"

# Patos de Minas - MG
MUNI_COD = "3148004"
TABELA = "839"


def _ensure_dirs() -> None:
    RAW_PAM_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_PAM_DIR.mkdir(parents=True, exist_ok=True)


def baixar_pam_rendimento(usar_cache: bool = True) -> tuple[pd.DataFrame, Path]:
    """
    Baixa rendimento médio (v=214) para Patos de Minas dos últimos 20 anos.
    Salva JSON bruto e CSV bruto em data/raw/ibge/pam/.
    """
    _ensure_dirs()
    out_json = RAW_PAM_DIR / "pam_3148004_rendimento_ultimos20.json"
    out_csv = RAW_PAM_DIR / "pam_3148004_rendimento_ultimos20.csv"

    if usar_cache and out_json.exists():
        print(f"[CACHE] Usando arquivo bruto existente: {out_json}")
        with open(out_json, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        url = f"https://apisidra.ibge.gov.br/values/t/{TABELA}/n6/{MUNI_COD}/v/214/p/last%2020/c81/all"
        print(f"[DOWNLOAD] Baixando: {url}")
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        data = r.json()
        out_json.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        print(f"[OK] Salvo JSON bruto: {out_json}")

    # Primeira linha é cabeçalho
    if not data:
        raise ValueError("Resposta vazia do SIDRA/PAM")
    df = pd.DataFrame(data[1:], columns=data[0])
    df.to_csv(out_csv, index=False, sep=";")
    print(f"[OK] Salvo CSV bruto: {out_csv} | Shape: {df.shape}")
    return df, out_csv


def normalizar_pam(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza colunas do PAM para formato padronizado.
    Mantém informações relevantes e adiciona metadados.
    """
    df = df.copy()
    # Normaliza nomes de colunas
    df.columns = [str(c).strip() for c in df.columns]

    # Renomeia colunas comuns
    rename_map = {}
    for c in df.columns:
        cl = c.upper()
        if cl == "ANO":
            rename_map[c] = "ano_civil"
        elif "PRODUTO" in cl and "COD" not in cl:
            rename_map[c] = "produto"
        elif "VALOR" in cl:
            rename_map[c] = "rendimento_kg_ha"
        elif "UNIDADE" in cl:
            rename_map[c] = "unidade"
        elif "MUNICIPIO" in cl or "N6" in cl:
            rename_map[c] = "municipio"
    df = df.rename(columns=rename_map)

    # Converte valores numéricos
    if "rendimento_kg_ha" in df.columns:
        df["rendimento_kg_ha"] = (
            df["rendimento_kg_ha"].astype(str).str.replace(",", ".").str.strip()
        )
        df["rendimento_kg_ha"] = pd.to_numeric(df["rendimento_kg_ha"], errors="coerce")

    if "ano_civil" in df.columns:
        df["ano_civil"] = pd.to_numeric(df["ano_civil"], errors="coerce")

    df["municipio_cod"] = MUNI_COD
    df["municipio_nome"] = "Patos de Minas"
    df["fonte"] = "IBGE_SIDRA_PAM_T839"
    df["observacao"] = "Ano civil. PAM nao separa milho 1a/2a safra."
    return df


def converter_ano_safra(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adiciona coluna ano_safra. Convenção comum: safra 2026/27 agrupa
    colheitas/produção relativa ao ciclo; para rendimento do PAM (ano civil)
    deve-se manter EXPLÍCITO o critério usado.
    
    ATENÇÃO: A conversão exata depende do critério acordado com o time.
    Aqui é adicionado apenas o campo para preenchimento/conferência.
    """
    df = df.copy()
    if "ano_civil" not in df.columns:
        return df
    df["ano_safra"] = df["ano_civil"].apply(lambda x: f"{int(x)}/{str(int(x)+1)[-2:]}" if pd.notna(x) else None)
    df["regra_conversao"] = "PENDENTE_DEFINICAO_PELO_TIME (ano civil vs ano-safra)"
    return df


def main(baixar: bool = True, usar_cache: bool = True) -> Optional[pd.DataFrame]:
    _ensure_dirs()
    try:
        if baixar:
            df_bruto, _ = baixar_pam_rendimento(usar_cache=usar_cache)
        else:
            out_csv = RAW_PAM_DIR / "pam_3148004_rendimento_ultimos20.csv"
            if not out_csv.exists():
                print("[ERRO] Arquivo bruto não encontrado. Rode com baixar=True")
                return None
            df_bruto = pd.read_csv(out_csv, sep=";")
        df_norm = normalizar_pam(df_bruto)
        df_norm = converter_ano_safra(df_norm)
        out_tratado = PROCESSED_PAM_DIR / "pam_pat_minas_rendimento_tratado.csv"
        df_norm.to_csv(out_tratado, index=False)
        print(f"[OK] Salvo tratado: {out_tratado} | Shape: {df_norm.shape}")
        return df_norm
    except Exception as e:
        print(f"[ERRO] {e}")
        return None


if __name__ == "__main__":
    main(baixar=True, usar_cache=True)
