#!/usr/bin/env python3
"""
pipeline/hipoteses.py — D2: Gera tabela consolidada de hipóteses rastreáveis
para a Tela 3 (Rastreabilidade) do dashboard.

Combina:
- ZARC (premissas + portarias)
- Conab Custos (custo_total por cultura/região)
- B3 (cotações ações agro proxy)
- Engine Config (margens, riscos, janelas MOCK)
"""

from __future__ import annotations
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "data/processed/hipoteses"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_all() -> dict[str, pd.DataFrame]:
    """Carrega todas as fontes processadas."""
    dfs = {}

    # ZARC premissas
    zarc_prem = REPO / "data/processed/zarc/premissas_zarc.parquet"
    if zarc_prem.exists():
        dfs["zarc_premissas"] = pd.read_parquet(zarc_prem)

    # ZARC portarias
    zarc_port = REPO / "data/processed/zarc/portarias_zarc.parquet"
    if zarc_port.exists():
        dfs["zarc_portarias"] = pd.read_parquet(zarc_port)

    # Conab Custos
    conab_custos = REPO / "data/processed/mercado/conab_custos/conab_custos_todos.parquet"
    if conab_custos.exists():
        dfs["conab_custos"] = pd.read_parquet(conab_custos)

    # Conab Preços MG
    conab_precos_mg = REPO / "data/processed/mercado/conab_precos/mg_precos_semanais.parquet"
    if conab_precos_mg.exists():
        dfs["conab_precos_mg"] = pd.read_parquet(conab_precos_mg)

    # B3 cotações
    b3_files = list((REPO / "data/processed/mercado/b3").glob("*.parquet"))
    if b3_files:
        dfs["b3_cotacoes"] = pd.read_parquet(sorted(b3_files)[-1])

    # Engine config (margens, riscos, janelas MOCK)
    config_path = REPO / "engine/config.yaml"
    if config_path.exists():
        import yaml
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        dfs["engine_config"] = cfg

    return dfs


def build_hipoteses_table(dfs: dict) -> pd.DataFrame:
    """Constrói tabela unificada de hipóteses rastreáveis."""
    rows = []

    # 1. ZARC Premissas
    if "zarc_premissas" in dfs:
        for _, r in dfs["zarc_premissas"].iterrows():
            rows.append({
                "variavel": r["chave"],
                "valor": r["valor"],
                "unidade": "",
                "fonte": "ZARC/MAPA",
                "fonte_url": r["fonte_url"],
                "metodo": r["metodo"],
                "categoria": "Adequação/Zoneamento",
                "observacao": r.get("categoria", "ZARC"),
            })

    # 2. ZARC Portarias
    if "zarc_portarias" in dfs:
        for _, r in dfs["zarc_portarias"].iterrows():
            rows.append({
                "variavel": f"portaria_{r['cultura']}",
                "valor": r["portaria"],
                "unidade": "",
                "fonte": "ZARC/MAPA",
                "fonte_url": "https://dados.agricultura.gov.br/dataset/tabua-de-risco-zoneamento-agricola-de-risco-climatico",
                "metodo": "Portaria oficial MAPA",
                "categoria": "Base Legal",
                "observacao": f"Cultura: {r['cultura']}",
            })

    # 3. Conab Custos (último ano por cultura/região-chave)
    if "conab_custos" in dfs:
        df = dfs["conab_custos"]
        # Regiões de interesse para Patos de Minas / Cerrado
        regioes_chave = {
            "soja": ["Unaí", "Pedro Afonso", "São Gabriel", "S. Luiz Gonzaga"],
            "milho_1a_safra": ["Unaí", "Barreiras", "Uruçuí", "Ponta Grossa", "Passo Fundo", "Campos Novos", "Santo Ângelo", "Guarapuava"],
            "milho_2a_safra": ["Unaí", "Rio Verde", "Ponta Grossa", "São Luiz Gonzaga", "Passo Fundo", "Santo Ângelo", "Canguçu", "Venâncio Aires", "Campos Novos", "Palmitos", "Carira", "Uruçuí", "Guarapuava", "Boa Vista"],
            "sorgo": ["Unaí", "Pedro Afonso", "Rio Verde", "Uberaba", "Barreiras", "Chapadão", "C. Novo Do Parecis"],
            "feijao_1a_safra": ["Unaí", "Cristalina", "Ponta Grossa", "Canguçu", "Canoinhas"],
        }

        for cultura, regioes in regioes_chave.items():
            sub = df[df["cultura"] == cultura].copy()
            if sub.empty:
                continue
            mask = sub["regiao"].apply(lambda r: any(rg.lower() in str(r).lower() for rg in regioes))
            sub = sub[mask]
            if sub.empty:
                continue

            # Último ano disponível
            latest_year = sub["ano"].max()
            sub_latest = sub[sub["ano"] == latest_year]

            for _, r in sub_latest.iterrows():
                rows.append({
                    "variavel": f"custo_total_ha_{cultura}",
                    "valor": f"{r['custo_total_ha']:.2f}",
                    "unidade": "R$/ha",
                    "fonte": "Conab - Custos de Produção",
                    "fonte_url": f"https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/custos-de-producao/arquivos-custo-de-producao/agricolas/",
                    "metodo": f"Série histórica Conab, {r['regiao']}-{r['uf']}, {int(r['ano'])}",
                    "categoria": "Custo de Produção",
                    "observacao": f"Região: {r['regiao']}-{r['uf']}, Ano: {int(r['ano'])}, Produtividade: {r.get('produtividade_kg_ha', 'N/A')}",
                })

    # 4. Conab Preços MG (Preços médios semanais estado MG)
    if "conab_precos_mg" in dfs:
        df_precos = dfs["conab_precos_mg"]
        for _, r in df_precos.iterrows():
            rows.append({
                "variavel": f"preco_conab_mg_{r['cultura']}_{r['nivel_comercializacao'].lower()}",
                "valor": f"{r['preco_rs_tonelada']:.2f}",
                "unidade": "R$/t",
                "fonte": "Conab/SIAGRO",
                "fonte_url": "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/precos-agropecuarios",
                "metodo": f"Preço médio semanal MG - nível {r['nivel_comercializacao']} - convertido de R$/unidade para R$/t",
                "categoria": "Preço de Mercado (Conab MG)",
                "observacao": f"Produto: {r['produto_original']} | Período: {r['periodo']} | Preço original: R$ {r['preco_original']} | Estado: {r['estado']}",
            })

    # 5. B3 Cotações (proxy ações agro)
    if "b3_cotacoes" in dfs:
        for _, r in dfs["b3_cotacoes"].iterrows():
            rows.append({
                "variavel": f"cotacao_{r['ticker'].replace('.SA', '')}",
                "valor": f"{r['fechamento']:.2f}",
                "unidade": "R$/ação",
                "fonte": "B3 via Yahoo Finance",
                "fonte_url": "https://finance.yahoo.com",
                "metodo": "Fechamento do dia (proxy para commodities agrícolas)",
                "categoria": "Preço de Mercado",
                "observacao": f"{r['empresa']} - Data: {r['data']}",
            })

    # 6. Engine Config (parâmetros MOCK - marcados como tal)
    if "engine_config" in dfs:
        cfg = dfs["engine_config"]
        for rot_id, rot in cfg.get("rotacoes", {}).items():
            rows.append({
                "variavel": f"margem_esperada_{rot_id}",
                "valor": f"{rot.get('margem_esperada', 0) / 100:.0f}",  # centavos -> R$
                "unidade": "R$/ha",
                "fonte": "Engine Config (MOCK)",
                "fonte_url": "MOCK://hackatohm/engine-config",
                "metodo": "MOCK - será substituído pelo Monte Carlo do M1 na sexta",
                "categoria": "Margem/Risco (MOCK)",
                "observacao": f"Risco: {rot.get('risco', 0)}‰ = P(margem<0) ≈ {rot.get('risco', 0)/10:.1f}%",
            })
            for h in rot.get("hipoteses", []):
                rows.append({
                    "variavel": h["chave"],
                    "valor": h["valor"],
                    "unidade": "",
                    "fonte": "Engine Config (MOCK)",
                    "fonte_url": h.get("fonte_url", "MOCK://hackatohm"),
                    "metodo": h.get("metodo", "MOCK"),
                    "categoria": "Hipótese de Modelo (MOCK)",
                    "observacao": f"Rotação: {rot_id}",
                })

    df_out = pd.DataFrame(rows)
    return df_out


def main() -> int:
    print("Carregando fontes...")
    dfs = load_all()
    for k, v in dfs.items():
        if isinstance(v, pd.DataFrame):
            print(f"  {k}: {len(v)} linhas")
        else:
            print(f"  {k}: dict")

    print("\nConstruindo tabela de hipóteses...")
    df_hip = build_hipoteses_table(dfs)

    # Salva Parquet
    out_parquet = OUT_DIR / "hipoteses_rastreaveis.parquet"
    df_hip.to_parquet(out_parquet, index=False)
    print(f"✅ {out_parquet}: {len(df_hip)} linhas")

    # Salva CSV legível
    out_csv = OUT_DIR / "hipoteses_rastreaveis.csv"
    df_hip.to_csv(out_csv, index=False)
    print(f"✅ {out_csv}: {len(df_hip)} linhas")

    # Resumo por categoria
    print("\n--- Resumo por categoria ---")
    print(df_hip["categoria"].value_counts().to_string())

    return 0


if __name__ == "__main__":
    sys.exit(main())