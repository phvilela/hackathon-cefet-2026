#!/usr/bin/env python3
"""
pipeline/mercado.py — D2: Conab (preços praça Patrocínio + custos) + B3 cotações

Entrada:  URLs públicas Conab + B3
Saída:    data/raw/mercado/  +  data/processed/mercado/*.parquet

Uso:
    python3 pipeline/mercado.py              # baixa tudo
    python3 pipeline/mercado.py --custos     # só custos Conab
    python3 pipeline/mercado.py --precos     # só preços Patrocínio
    python3 pipeline/mercado.py --b3         # só B3
"""

from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data/raw/mercado"
PROC = REPO / "data/processed/mercado"

# ──────────────────────────────────────────────────────────────────────
# URLs Conab Custos de Produção (série histórica)
# ──────────────────────────────────────────────────────────────────────
CONAB_CUSTOS_URLS: Dict[str, str] = {
    "soja": (
        "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/"
        "custos-de-producao/arquivos-custo-de-producao/agricolas/"
        "serie-historica-custos-soja-1997-a-2026.xls"
    ),
    "milho_1a_safra": (
        "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/"
        "custos-de-producao/arquivos-custo-de-producao/agricolas/milho/"
        "milho_1a_safra_serie_historica_1997-2026.xls"
    ),
    "milho_2a_safra": (
        "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/"
        "custos-de-producao/arquivos-custo-de-producao/agricolas/milho/"
        "milho_2a_safra_serie_historica_2005-2026.xls"
    ),
    "sorgo": (
        "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/"
        "custos-de-producao/arquivos-custo-de-producao/agricolas/"
        "seriehistoricacustossorgo2013a2026.xls"
    ),
    "feijao_1a_safra": (
        "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/"
        "custos-de-producao/arquivos-custo-de-producao/agricolas/feijao/"
        "feijao_1_safra_serie_historica-1998-2026.xls"
    ),
    "feijao_2a_3a_safras": (
        "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/"
        "custos-de-producao/arquivos-custo-de-producao/agricolas/feijao/"
        "feijao_2_e_3_safras_serie_historica_2013-2026.xls"
    ),
}

# Pecuários (links usam @@download/file)
CONAB_CUSTOS_PECUARIOS: Dict[str, str] = {
    "avicultura_corte": (
        "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/"
        "custos-de-producao/arquivos-custo-de-producao/pecuarios/"
        "avicultura-de-corte/serie-historica-custos-avicultura-de-corte-2023-a-2025-1/@@download/file"
    ),
    "avicultura_corte_2016_2019": (
        "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/"
        "custos-de-producao/arquivos-custo-de-producao/pecuarios/"
        "avicultura-de-corte/serie-historica-custos-avicultura-de-corte-2016-a-2019/@@download/file"
    ),
    "avicultura_corte_2020_2022": (
        "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/"
        "custos-de-producao/arquivos-custo-de-producao/pecuarios/"
        "avicultura-de-corte/serie-historica-custos-avicultura-de-corte-2020-a-2022/@@download/file"
    ),
    "bovinocultura_leite": (
        "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/"
        "custos-de-producao/arquivos-custo-de-producao/pecuarios/"
        "bovinocultura-de-leite/bovinocultura-de-leite/@@download/file"
    ),
    "caprino_ovino_corte": (
        "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/"
        "custos-de-producao/arquivos-custo-de-producao/pecuarios/"
        "caprinocultura-e-ovinocultura-de-corte/caprinocultura-e-ovinocultura-de-corte/@@download/file"
    ),
    "suinocultura": (
        "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/"
        "custos-de-producao/arquivos-custo-de-producao/pecuarios/"
        "suinocultura/suinocultura/@@download/file"
    ),
}

# Regiões de interesse para Patos de Minas (MG) e Cerrado
REGOES_INTERESSE = {
    "soja": ["Unaí", "Pedro Afonso", "São Gabriel", "S. Luiz Gonzaga"],
    "milho_1a_safra": ["Unaí", "Rio Verde", "Barreiras", "Chapadão", "Ponta Grossa", "Passo Fundo", "Campos Novos", "Santo Ângelo", "Uruçuí", "Guarapuava", "Canguçu", "Venâncio Aires", "Palmitos", "Carira"],
    "milho_2a_safra": ["Unaí", "Rio Verde", "Ponta Grossa", "São Luiz Gonzaga", "Passo Fundo", "Santo Ângelo", "Canguçu", "Venâncio Aires", "Campos Novos", "Palmitos", "Carira", "Uruçuí", "Guarapuava", "Boa Vista"],
    "sorgo": ["Unaí", "Pedro Afonso", "Rio Verde", "Uberaba", "Barreiras", "Chapadão", "C. Novo Do Parecis"],
    "feijao_1a_safra": ["Unaí", "Cristalina", "Ponta Grossa", "Cristalina", "Canguçu", "Canoinhas", "Cm Restingaseca", "Crateús", "Irecê", "Guanambi", "Macaúbas", "Icó", "Ivaiporã", "Nioaque", "Nova Palma", "Pd Restingaseca", "Pitanga", "Prudentópolis", "Roraima", "S. Mateus Do Sul", "S.R.Nonato", "Sidrolândia", "Taquarituba", "Tracuateua"],
    "feijao_2a_3a_safras": ["Unaí", "Sorriso", "Cascavel", "Francisco Beltrão", "Rolim De Moura", "Taquarituba", "3ª Sorriso", "3ªsorriso"],
}

# ──────────────────────────────────────────────────────────────────────
# HTTP client com retry
# ──────────────────────────────────────────────────────────────────────
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) HackatOhm/2026"
})


def download_file(url: str, dest: Path, chunk_size: int = 8192) -> bool:
    """Baixa arquivo com streaming e progress bar."""
    try:
        with SESSION.get(url, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f, tqdm(
                total=total, unit="B", unit_scale=True, desc=dest.name, leave=False
            ) as pbar:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))
        return True
    except Exception as e:
        print(f"  ✗ Falha ao baixar {dest.name}: {e}", file=sys.stderr)
        if dest.exists():
            dest.unlink(missing_ok=True)
        return False


# ──────────────────────────────────────────────────────────────────────
# Conab CUSTOS — parsing robusto
# ──────────────────────────────────────────────────────────────────────
def download_conab_custos() -> List[Path]:
    """Baixa todas as planilhas de custos Conab (agrícolas + pecuários)."""
    RAW_CUSTOS = RAW / "conab_custos"
    RAW_CUSTOS.mkdir(parents=True, exist_ok=True)
    PROC.mkdir(parents=True, exist_ok=True)

    downloaded: List[Path] = []

    # Agrícolas
    print("\n=== Conab CUSTOS — Agrícolas ===")
    for nome, url in CONAB_CUSTOS_URLS.items():
        dest = RAW_CUSTOS / f"{nome}.xls"
        if dest.exists():
            print(f"  ⊙ Já existe: {dest.name}")
            downloaded.append(dest)
            continue
        print(f"  ↓ {nome}")
        if download_file(url, dest):
            downloaded.append(dest)

    # Pecuários
    print("\n=== Conab CUSTOS — Pecuários ===")
    for nome, url in CONAB_CUSTOS_PECUARIOS.items():
        dest = RAW_CUSTOS / f"{nome}.xls"
        if dest.exists():
            print(f"  ⊙ Já existe: {dest.name}")
            downloaded.append(dest)
            continue
        print(f"  ↓ {nome}")
        if download_file(url, dest):
            downloaded.append(dest)

    return downloaded


def _parse_conab_sheet(df: pd.DataFrame, sheet_name: str) -> Optional[Dict]:
    """
    Extrai custo total por hectare de uma sheet Conab.
    Retorna dict com: regiao, uf, ano, produtividade, custo_total_ha, custo_total_sc
    """
    try:
        # Encontra linhas-chave
        df_str = df.astype(str)
        
        # Produtividade
        prod_row = df_str[df_str.iloc[:, 0].str.contains("Produtividade", case=False, na=False)]
        produtividade = None
        if not prod_row.empty:
            val = prod_row.iloc[0, 1] if prod_row.shape[1] > 1 else ""
            match = re.search(r"([\d.,]+)\s*(?:kg|sc|ha)", str(val))
            if match:
                produtividade = float(match.group(1).replace(",", "."))
        
        # Custo total (procura por "TOTAL" ou "CUSTO TOTAL" nas linhas de resumo)
        custo_total_ha = None
        custo_total_sc = None
        
        # Procura em várias linhas possíveis
        for idx, row in df.iterrows():
            row_str = " ".join(str(v) for v in row.values if pd.notna(v))
            if any(kw in row_str.upper() for kw in ["TOTAL GERAL", "CUSTO TOTAL", "TOTAL DO CUSTO"]):
                # Tenta extrair valores das colunas numéricas
                for col in row.index:
                    val = row[col]
                    if pd.notna(val) and isinstance(val, (int, float)) and val > 100:
                        if custo_total_ha is None:
                            custo_total_ha = float(val)
                        elif custo_total_sc is None:
                            custo_total_sc = float(val)
        
        # Extrai região/ano do nome da sheet
        match = re.match(r"(.+?)-(\w{2})-(\d{4})", sheet_name)
        if match:
            regiao = match.group(1).replace("-", " ").title()
            uf = match.group(2)
            ano = int(match.group(3))
        else:
            # Tenta extrair da primeira coluna
            regiao = sheet_name
            uf = ""
            ano = None
        
        if custo_total_ha is not None:
            return {
                "regiao": regiao,
                "uf": uf,
                "ano": ano,
                "produtividade_kg_ha": produtividade,
                "custo_total_ha": custo_total_ha,
                "custo_total_sc": custo_total_sc,
                "sheet": sheet_name,
            }
    except Exception:
        pass
    return None


def process_conab_custos() -> Dict[str, Path]:
    """Processa planilhas Conab → extrai custo total por hectare por região/ano."""
    RAW_CUSTOS = RAW / "conab_custos"
    PROC_CUSTOS = PROC / "conab_custos"
    PROC_CUSTOS.mkdir(parents=True, exist_ok=True)

    all_records: List[Dict] = []

    for xls_file in RAW_CUSTOS.glob("*.xls*"):
        nome = xls_file.stem
        print(f"  Processando {nome}...")
        try:
            xls = pd.read_excel(xls_file, sheet_name=None, engine="xlrd")
            for sheet_name, df in xls.items():
                if sheet_name == "Índice":
                    continue
                if df.empty or df.shape[0] < 10:
                    continue
                
                parsed = _parse_conab_sheet(df, sheet_name)
                if parsed:
                    parsed["cultura"] = nome
                    all_records.append(parsed)
        except Exception as e:
            print(f"  ✗ Erro lendo {xls_file.name}: {e}", file=sys.stderr)

    if all_records:
        df_out = pd.DataFrame(all_records)
        # Filtra apenas regiões de interesse se definidas
        for cultura, regioes in REGOES_INTERESSE.items():
            if regioes:
                mask = df_out["cultura"] == cultura
                if mask.any():
                    df_reg = df_out[mask].copy()
                    # Filtra por região (match parcial)
                    regiao_mask = df_reg["regiao"].apply(
                        lambda r: any(rg.lower() in str(r).lower() for rg in regioes)
                    )
                    df_reg = df_reg[regiao_mask]
                    if not df_reg.empty:
                        out_path = PROC_CUSTOS / f"{cultura}_custo_ha_regioes_interesse.parquet"
                        df_reg.to_parquet(out_path, index=False)
                        print(f"  ✓ {out_path.name} ({len(df_reg)} registros)")
        
        # Salva tudo também
        out_all = PROC_CUSTOS / "conab_custos_todos.parquet"
        df_out.to_parquet(out_all, index=False)
        print(f"  ✓ {out_all.name} ({len(df_out)} registros totais)")
        
        return {"all": out_all}
    
    print("  ⚠ Nenhum registro extraído")
    return {}


# ──────────────────────────────────────────────────────────────────────
# Conab PREÇOS — Praça Patrocínio
# ──────────────────────────────────────────────────────────────────────
def download_conab_precos_patrocinio() -> Optional[Path]:
    """
    Tenta baixar preços da praça Patrocínio (MG).
    O painel consultaprecosdemercado.conab.gov.br é Angular — requer investigação de API.
    Por enquanto, placeholder para implementação futura via Selenium/Playwright
    ou descoberta de endpoint JSON.
    """
    RAW_PRECOS = RAW / "conab_precos"
    RAW_PRECOS.mkdir(parents=True, exist_ok=True)

    print("\n=== Conab PREÇOS — Praça Patrocínio ===")
    print("  ⚠ Painel Angular — requer descoberta de API ou scraping")
    print("  🔍 Endpoints candidatos a testar:")
    print("     - https://consultaprecosdemercado.conab.gov.br/api/precos")
    print("     - https://portaldeinformacoes.conab.gov.br/api/precos")
    print("     - https://sistemas.conab.gov.br/consulta-precos-mercado/...")

    # Placeholder: criar arquivo vazio para não quebrar pipeline
    placeholder = RAW_PRECOS / "patrocinio_placeholder.txt"
    placeholder.write_text("TODO: implementar coleta de preços Patrocínio via API/scraping\n")
    return placeholder


# ──────────────────────────────────────────────────────────────────────
# B3 COTAÇÕES
# ──────────────────────────────────────────────────────────────────────
def download_b3_cotacoes() -> Optional[Path]:
    """
    Registra cotações B3 do dia para ações do setor agro.
    Yahoo Finance tem cobertura para ações (não futuros).
    Usamos proxies: SLCE3, AGRO3, SMTO3, RAIZ4, BEEF3, etc.
    """
    from datetime import date
    RAW_B3 = RAW / "b3"
    RAW_B3.mkdir(parents=True, exist_ok=True)
    PROC_B3 = PROC / "b3"
    PROC_B3.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()
    print(f"\n=== B3 COTAÇÕES — {today} ===")

    # Ações do setor agro com boa liquidez no yfinance
    tickers = {
        "SLCE3.SA": "SLC Agrícola (soja/milho/algodão)",
        "AGRO3.SA": "BrasilAgro (soja/milho/boi/terras)",
        "SMTO3.SA": "São Martinho (açúcar/etanol/milho)",
        "RAIZ4.SA": "Raízen (açúcar/etanol/energia)",
        "BEEF3.SA": "Minerva Foods (boi/carne)",
        "JBSS3.SA": "JBS (boi/carne/proteína)",
        "MRFG3.SA": "Marfrig (boi/carne)",
        "BRSR6.SA": "Banrisul (crédito agro - RS)",
    }

    results = []
    for ticker, desc in tickers.items():
        try:
            tk = yfinance.Ticker(ticker)
            hist = tk.history(period="1d")
            if not hist.empty:
                row = hist.iloc[-1]
                results.append({
                    "data": today,
                    "ticker": ticker,
                    "empresa": desc,
                    "abertura": row.Open,
                    "maxima": row.High,
                    "minima": row.Low,
                    "fechamento": row.Close,
                    "volume": int(row.Volume),
                })
                print(f"  ✓ {ticker}: R$ {row.Close:.2f} ({desc})")
            else:
                print(f"  ⊙ {ticker}: sem dados hoje")
        except Exception as e:
            print(f"  ✗ {ticker}: {e}")

    if results:
        df = pd.DataFrame(results)
        out_path = PROC_B3 / f"b3_acoes_agro_{today}.parquet"
        df.to_parquet(out_path, index=False)
        print(f"  → Salvo: {out_path}")
        return out_path

    print("  ⚠ Nenhuma cotação obtida")
    return None


def generate_cost_summary_for_engine() -> Path:
    """Gera resumo de custos atuais (últimos 3 anos) para atualizar engine/config.yaml"""
    PROC_CUSTOS = PROC / "conab_custos"
    df = pd.read_parquet(PROC_CUSTOS / "conab_custos_todos.parquet")
    
    # Para cada cultura, pega a média dos últimos 3 anos nas regiões de interesse
    summary = []
    for cultura, regioes in REGOES_INTERESSE.items():
        sub = df[df["cultura"] == cultura].copy()
        if sub.empty:
            continue
        
        # Filtra regiões de interesse
        if regioes:
            mask = sub["regiao"].apply(
                lambda r: any(rg.lower() in str(r).lower() for rg in regioes)
            )
            sub = sub[mask]
        
        if sub.empty:
            continue
        
        # Últimos 3 anos disponíveis
        anos_disponiveis = sorted(sub["ano"].dropna().unique())
        ultimos_anos = [a for a in anos_disponiveis if a >= max(anos_disponiveis) - 2]
        sub_recente = sub[sub["ano"].isin(ultimos_anos)]
        
        if not sub_recente.empty:
            custo_medio = sub_recente["custo_total_ha"].mean()
            custo_sc = sub_recente["custo_total_sc"].mean()
            summary.append({
                "cultura": cultura,
                "regioes": ", ".join(regioes) if regioes else "todas",
                "anos": f"{min(ultimos_anos):.0f}-{max(ultimos_anos):.0f}",
                "custo_medio_ha": round(custo_medio, 2),
                "custo_medio_sc": round(custo_sc, 2) if pd.notna(custo_sc) else None,
                "n_obs": len(sub_recente),
            })
    
    df_sum = pd.DataFrame(summary)
    out_path = PROC_CUSTOS / "resumo_custos_para_engine.csv"
    df_sum.to_csv(out_path, index=False)
    print(f"\n=== Resumo para engine/config.yaml ===")
    print(df_sum.to_string(index=False))
    return out_path


# ──────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────
def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="D2 — Mercado: Conab + B3")
    parser.add_argument("--custos", action="store_true", help="Baixar/processar custos Conab")
    parser.add_argument("--precos", action="store_true", help="Baixar preços Patrocínio")
    parser.add_argument("--b3", action="store_true", help="Registrar cotações B3 do dia")
    parser.add_argument("--resumo", action="store_true", help="Gerar resumo de custos para engine")
    args = parser.parse_args(argv)

    # Default: roda tudo se nenhuma flag
    run_all = not (args.custos or args.precos or args.b3 or args.resumo)

    if run_all or args.custos:
        print("=" * 60)
        print("DOWNLOAD: Conab CUSTOS DE PRODUÇÃO")
        print("=" * 60)
        downloaded = download_conab_custos()
        print(f"\nBaixados: {len(downloaded)} arquivos")

        print("\nPROCESSAMENTO: Conab CUSTOS → Parquet")
        processed = process_conab_custos()
        print(f"Gerados: {len(processed)} arquivos Parquet")

    if run_all or args.resumo:
        print("\nGERANDO RESUMO PARA ENGINE/CONFIG.YAML")
        generate_cost_summary_for_engine()

    if run_all or args.precos:
        download_conab_precos_patrocinio()

    if run_all or args.b3:
        # Import lazy para não quebrar se yfinance não instalado
        global yfinance
        import yfinance
        download_b3_cotacoes()

    print("\n✅ Pipeline mercado concluído")
    print(f"Raw:    {RAW}")
    print(f"Proc:   {PROC}")
    return 0


if __name__ == "__main__":
    sys.exit(main())