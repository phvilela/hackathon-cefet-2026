#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline/clima.py
=================
Processamento de dados climáticos para o HackatOhm 2026 - "O que plantar?"

OBJETIVO
--------
Extrair, limpar e agregar séries diárias de precipitação e temperatura da estação
automática A523 - PATROCÍNIO (MG), presente nos ZIPs anuais do INMET
(portal.inmet.gov.br/dadoshistoricos), complementar com NASA POWER (lat/lon da
fazenda) quando houver lacunas e gerar saídas prontas para integração com a
janela de plantio do ZARC e com a tabela fato.

FONTES
------
- INMET (Dados Históricos): data/raw/inmet/zips/AAAA.zip
  - Arquivo alvo por ano: *PATROCINIO*_DD-MM-AAAA_A_DD-MM-AAAA.CSV
  - Estação proxy: A523 - PATROCÍNIO (MG) | Próxima a Patos de Minas/MG
- NASA POWER (ponto): data/raw/nasa_power/*.json (lon=-46.52, lat=-18.58)
  - Parâmetros: PRECTOTCORR, T2M, ALLSKY_SFC_SW_DWN
  - Uso: preenchimento de lacunas (origem = 'inmet' ou 'power')

REGRAS IMPORTANTES
------------------
- Falhas do INMET são marcadas como 9999 / -9999. DEVEM ser tratadas como NaN,
  nunca como 0.
- Patrocínio é usado como ESTAÇÃO PROXY de Patos de Minas (MG). Essa limitação
  deve constar na rastreabilidade.
- A agregação por decêndio (janela ZARC) e a relação com ano-safra devem ser
  feitas preservando a coluna `origem` por registro/linha.
- Os ZIPs já estão em data/raw/inmet/zips/ e NÃO devem ser rebaixados.
- Preferir trabalhar apenas com a estação PATROCÍNIO quando houver mais de uma
  estação no mesmo ZIP.

SAÍDAS ESPERADAS (sugeridas)
---------------------------
- data/processed/inmet/inmet_patrcinio_diario_limpo.parquet/csv  (diário limpo)
- data/processed/clima/clima_patrcinio_decendial.parquet/csv      (agregado por decêndio)
- data/processed/clima/chuvatemperatura_janela_zarc.parquet/csv   (agregado por janela ZARC)

DEPENDÊNCIAS
------------
pandas, numpy, pyarrow (opcionais), requests (se baixar NASA POWER)

AUTOR / DATA
------------
D1 - Clima & Produtividade | HackatOhm 2026 | 2026-10-23
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import unicodedata
import zipfile
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
import pandas as pd

# Diretórios padrão do repositório
ROOT = Path(__file__).resolve().parents[1]
RAW_INMET_ZIPS = ROOT / "data" / "raw" / "inmet" / "zips"
RAW_INMET_CSV = ROOT / "data" / "raw" / "inmet" / "csv"
RAW_NASA = ROOT / "data" / "raw" / "nasa_power"
PROCESSED_INMET = ROOT / "data" / "processed" / "inmet"
PROCESSED_CLIMA = ROOT / "data" / "processed" / "clima"

# Estação proxy
ESTACAO_NOME = "PATROCINIO"
ESTACAO_CODIGO = "A523"  # confirmar com cabeçalho do CSV quando extraído

# Valores de falha INMET
FALHAS_INMET = {9999, -9999, 9999.0, -9999.0, "9999", "-9999"}


def _ensure_dirs() -> None:
    """Cria diretórios de saída caso não existam."""
    for p in (RAW_INMET_CSV, PROCESSED_INMET, PROCESSED_CLIMA):
        p.mkdir(parents=True, exist_ok=True)


def _is_falha(val) -> bool:
    """Retorna True se o valor for considerado falha do INMET."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return True
    try:
        if isinstance(val, str):
            s = val.strip()
            if s in ("", "****", "---", "null"):
                return True
            # tenta converter
            try:
                fv = float(s.replace(",", "."))
                return fv in {9999, -9999}
            except Exception:
                return False
        fv = float(val)
        return fv in {9999, -9999}
    except Exception:
        return False


def _norm_num(val):
    """Normaliza número (vírgula->ponto). Retorna float ou np.nan."""
    if _is_falha(val):
        return np.nan
    if isinstance(val, str):
        s = val.strip().replace(",", ".")
        if s == "":
            return np.nan
        try:
            return float(s)
        except Exception:
            return np.nan
    try:
        return float(val)
    except Exception:
        return np.nan


def extrair_zip_patrocinio(ano: int) -> Optional[Path]:
    """
    Extrai o CSV da estação PATROCÍNIO do ZIP anual do INMET para data/raw/inmet/csv/
    Retorna o caminho do CSV extraído ou None se não encontrado.
    """
    _ensure_dirs()
    zip_path = RAW_INMET_ZIPS / f"{ano}.zip"
    if not zip_path.exists():
        print(f"[AVISO] ZIP não encontrado: {zip_path}")
        return None

    with zipfile.ZipFile(zip_path, "r") as zf:
        # Procura arquivo com PATROCINIO no nome
        candidatos = [n for n in zf.namelist() if "PATROCINIO" in n.upper() and n.upper().endswith(".CSV")]
        if not candidatos:
            print(f"[AVISO] Nenhum CSV com PATROCINIO encontrado em {zip_path.name}")
            return None
        # Em geral vem um único arquivo por estação/ano
        nome = candidatos[0]
        zf.extract(nome, path=RAW_INMET_CSV)
        extraido = RAW_INMET_CSV / nome
        print(f"[OK] Extraído: {extraido}")
        return extraido


def ler_csv_inmet(caminho: Path) -> pd.DataFrame:
    """
    Lê CSV do INMET (formato dos dados históricos). 
    Os arquivos costumam ter cabeçalho com metadados; esta função tenta detectar
    a linha com os nomes das colunas.
    """
    if not caminho.exists():
        raise FileNotFoundError(caminho)

    # Tenta ler pulando possíveis cabeçalhos
    with open(caminho, "r", encoding="latin-1", errors="replace") as f:
        linhas = f.readlines()

    # Detecta linha de cabeçalho (geralmente contém 'DATA' ou 'HORA')
    # Nota: 'PRECIPITA' sem o Ç — a linha de metadado 'DATA DE FUNDAÇÃO...' não pode casar
    idx_cab = 0
    for i, l in enumerate(linhas):
        if "DATA" in l.upper() and ("PRECIPITA" in l.upper() or "TEMPERATURA" in l.upper()):
            idx_cab = i
            break
    # Se não achou pelo padrão, tenta linha que tem ';' e palavras-chave
    if idx_cab == 0:
        for i, l in enumerate(linhas[:30]):
            if ";" in l and ("DATA" in l.upper()):
                idx_cab = i
                break

    df = pd.read_csv(caminho, sep=";", encoding="latin-1", skiprows=idx_cab, decimal=",")
    # Normaliza nomes de coluna SEM ACENTO: 'PRECIPITAÇÃO_TOTAL,_HORÁRIO_(MM)' tem Ç/Á —
    # sem isso o matching por 'PRECIPITACAO'/'HORARIO' nunca casa e a chuva vira 100% NaN.
    df.columns = [
        "".join(
            ch for ch in unicodedata.normalize("NFD", str(c))
            if unicodedata.category(ch) != "Mn"
        ).upper().strip().replace(" ", "_")
        for c in df.columns
    ]
    return df


def normalizar_inmet(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza colunas principais do INMET para um formato padrão:
    data, precipitacao_mm, temp_media_c, temp_min_c, temp_max_c, umidade_relativa, origem
    """
    out = pd.DataFrame()
    # DATA — sem dayfirst: os CSVs do INMET usam AAAA-MM-DD ou AAAA/MM/DD (ano primeiro).
    # Com dayfirst=True o pandas lia '2020/01/13' como dia↔mês trocados → mês 13 não
    # existe → NaT: sobreviviam só os 12 primeiros dias de cada mês (bug dos 144 dias/ano).
    if "DATA" in df.columns:
        out["data"] = pd.to_datetime(df["DATA"], errors="coerce")
    elif "DATA_(YYYY-MM-DD)" in df.columns:
        out["data"] = pd.to_datetime(df["DATA_(YYYY-MM-DD)"], errors="coerce")
    else:
        # tenta primeira coluna com DATA
        for c in df.columns:
            if str(c).startswith("DATA"):
                out["data"] = pd.to_datetime(df[c], errors="coerce")
                break

    # HORA (opcional) - manter para agregação horária
    hora_col = None
    for c in df.columns:
        uc = str(c).upper()
        if "HORA" in uc and "UTC" in uc:
            hora_col = c
            break
    if hora_col is not None:
        out["hora"] = df[hora_col]

    # Precipitação (horária) - somar por dia depois
    for c in df.columns:
        uc = str(c).upper()
        if "PRECIPITACAO" in uc and "TOTAL" in uc and "HORARIO" in uc:
            out["precipitacao_mm"] = df[c].apply(_norm_num)
            break
    if "precipitacao_mm" not in out.columns:
        for c in df.columns:
            uc = str(c).upper()
            if "PRECIPITACAO" in uc:
                out["precipitacao_mm"] = df[c].apply(_norm_num)
                break
    if "precipitacao_mm" not in out.columns:
        out["precipitacao_mm"] = np.nan

    # Temperaturas (horárias)
    for c in df.columns:
        uc = str(c).upper()
        if ("TEMPERATURA" in uc and "BULBO_SECO" in uc and "HORARIA" in uc) or uc == "TEMPERATURA_DO_AR_-_BULBO_SECO,_HORARIA_(°C)":
            out["temp_media_c"] = df[c].apply(_norm_num)
            break
    if "temp_media_c" not in out.columns:
        for c in df.columns:
            uc = str(c).upper()
            if uc.startswith("TEMPERATURA_MEDIA"):
                out["temp_media_c"] = df[c].apply(_norm_num)
                break

    for c in df.columns:
        uc = str(c).upper()
        if "TEMPERATURA" in uc and "MINIMA" in uc and "HORA" in uc:
            out["temp_min_c"] = df[c].apply(_norm_num)
            break
    if "temp_min_c" not in out.columns:
        for c in df.columns:
            uc = str(c).upper()
            if "TEMPERATURA_MINIMA" in uc:
                out["temp_min_c"] = df[c].apply(_norm_num)
                break

    for c in df.columns:
        uc = str(c).upper()
        if "TEMPERATURA" in uc and "MAXIMA" in uc and "HORA" in uc:
            out["temp_max_c"] = df[c].apply(_norm_num)
            break
    if "temp_max_c" not in out.columns:
        for c in df.columns:
            uc = str(c).upper()
            if "TEMPERATURA_MAXIMA" in uc:
                out["temp_max_c"] = df[c].apply(_norm_num)
                break

    if "temp_media_c" not in out.columns and all(x in out.columns for x in ["temp_min_c", "temp_max_c"]):
        out["temp_media_c"] = (out["temp_min_c"] + out["temp_max_c"]) / 2.0

    # Umidade
    for c in df.columns:
        uc = str(c).upper()
        if "UMIDADE" in uc and "RELATIVA" in uc and "HORARIA" in uc and "MAX" not in uc and "MIN" not in uc:
            out["umidade_relativa"] = df[c].apply(_norm_num)
            break
    if "umidade_relativa" not in out.columns:
        for c in df.columns:
            uc = str(c).upper()
            if "UMIDADE" in uc and "RELATIVA" in uc:
                out["umidade_relativa"] = df[c].apply(_norm_num)
                break

    out["origem"] = "inmet"
    out["estacao"] = ESTACAO_NOME
    out["estacao_codigo"] = ESTACAO_CODIGO
    out["fonte"] = "INMET_DADOS_HISTORICOS"
    # Remove linhas sem data
    out = out.dropna(subset=["data"]).copy()
    return out


def carregar_todos_inmet(anos: Iterable[int]) -> pd.DataFrame:
    """Extrai (se necessário) e concatena todos os anos da estação PATROCÍNIO."""
    _ensure_dirs()
    dfs = []
    for ano in anos:
        csv_extraido = None
        # Procura já extraído (rglob: os CSVs do D1 vêm em subpastas por ano, ex.: csv/2006/)
        candidatos_existentes = list(RAW_INMET_CSV.rglob(f"*PATROCINIO*{ano}*.CSV"))
        if candidatos_existentes:
            csv_extraido = candidatos_existentes[0]
        else:
            csv_extraido = extrair_zip_patrocinio(ano)
        if csv_extraido is None:
            continue
        try:
            df = ler_csv_inmet(csv_extraido)
            df_n = normalizar_inmet(df)
            dfs.append(df_n)
            print(f"[OK] Normalizado {ano}: {len(df_n)} linhas")
        except Exception as e:
            print(f"[ERRO] Falha ao processar {ano}: {e}")
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)


def agregar_diario(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega série horária para diária."""
    if df.empty:
        return df
    df = df.copy()
    df["data"] = df["data"].dt.date
    agg_dict = {
        "precipitacao_mm": "sum",
        "origem": lambda x: x.mode().iloc[0] if len(x.dropna().mode()) else (x.iloc[0] if len(x) else "inmet"),
        "estacao": "first",
        "estacao_codigo": "first",
        "fonte": "first",
    }
    if "temp_media_c" in df.columns:
        agg_dict["temp_media_c"] = "mean"
    if "temp_min_c" in df.columns:
        agg_dict["temp_min_c"] = "min"
    if "temp_max_c" in df.columns:
        agg_dict["temp_max_c"] = "max"
    if "umidade_relativa" in df.columns:
        agg_dict["umidade_relativa"] = "mean"
    df_d = df.groupby(["data"], as_index=False).agg(agg_dict)
    df_d["data"] = pd.to_datetime(df_d["data"])
    return df_d


def agregar_decendial(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega diário para decêndio (10 dias). ZARC usa decêndios 1-36.
    """
    if df.empty:
        return df
    df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df["data"]):
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["data"])
    try:
        df["dia_ano"] = df["data"].dt.day_of_year
    except Exception:
        df["dia_ano"] = df["data"].dt.dayofyear
    df["decendio"] = ((df["dia_ano"] - 1) // 10 + 1).clip(lower=1, upper=36)
    df["ano"] = df["data"].dt.year
    # Agregação compatível com pandas
    agg = df.groupby(["ano", "decendio"], as_index=False).agg(
        precipitacao_mm_total=("precipitacao_mm", "sum"),
        dias_com_dados=("data", "count"),
    )
    if "temp_media_c" in df.columns:
        agg = agg.merge(df.groupby(["ano", "decendio"], as_index=False)["temp_media_c"].mean().rename(columns={"temp_media_c": "temp_media_c_media"}), on=["ano", "decendio"], how="left")
    if "temp_min_c" in df.columns:
        agg = agg.merge(df.groupby(["ano", "decendio"], as_index=False)["temp_min_c"].mean().rename(columns={"temp_min_c": "temp_min_c_media"}), on=["ano", "decendio"], how="left")
    if "temp_max_c" in df.columns:
        agg = agg.merge(df.groupby(["ano", "decendio"], as_index=False)["temp_max_c"].mean().rename(columns={"temp_max_c": "temp_max_c_media"}), on=["ano", "decendio"], how="left")
    if "umidade_relativa" in df.columns:
        agg = agg.merge(df.groupby(["ano", "decendio"], as_index=False)["umidade_relativa"].mean().rename(columns={"umidade_relativa": "umidade_relativa_media"}), on=["ano", "decendio"], how="left")
    # origem
    orig = df.groupby(["ano", "decendio"])["origem"].agg(lambda x: x.mode().iloc[0] if len(x.dropna().mode()) else (x.iloc[0] if len(x) else "inmet")).reset_index()
    agg = agg.merge(orig, on=["ano", "decendio"], how="left")
    return agg


def main(anos: Optional[Iterable[int]] = None) -> None:
    _ensure_dirs()
    if anos is None:
        anos = range(2000, 2026)  # cobre os ZIPs presentes
    print(f"[INICIO] Processando INMET PATROCÍNIO {list(anos)}")
    df_horario = carregar_todos_inmet(anos)
    if df_horario.empty:
        print("[FALHA] Nenhum dado carregado. Verifique ZIPs e extração.")
        return
    # Agrega horário -> diário
    df_diario = agregar_diario(df_horario)
    # Salva diário limpo
    out_diario_csv = PROCESSED_INMET / "inmet_patrcinio_diario_limpo.csv"
    out_diario_parquet = PROCESSED_INMET / "inmet_patrcinio_diario_limpo.parquet"
    df_diario.to_csv(out_diario_csv, index=False)
    try:
        df_diario.to_parquet(out_diario_parquet, index=False)
    except Exception as e:
        print(f"[AVISO] Não foi possível salvar parquet (instale pyarrow): {e}")
    print(f"[OK] Diário limpo salvo: {out_diario_csv} ({len(df_diario)} linhas)")

    df_dec = agregar_decendial(df_diario)
    out_dec_csv = PROCESSED_CLIMA / "clima_patrcinio_decendial.csv"
    out_dec_parquet = PROCESSED_CLIMA / "clima_patrcinio_decendial.parquet"
    df_dec.to_csv(out_dec_csv, index=False)
    try:
        df_dec.to_parquet(out_dec_parquet, index=False)
    except Exception as e:
        print(f"[AVISO] Não foi possível salvar parquet (instale pyarrow): {e}")
    print(f"[OK] Decêndial salvo: {out_dec_csv} ({len(df_dec)} linhas)")


if __name__ == "__main__":
    main()
