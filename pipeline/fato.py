#!/usr/bin/env python3
"""pipeline/fato.py — a tabela fato: onde os mundos se encontram (M3 · HackatOhm 2026).

1 linha = município × ano-safra × cultura, com TUDO ao lado:
  produtividade real (PAM) · chuva da janela de plantio (INMET A523 decendial)
  · custo (Conab, regiões-referência) · preço (hipótese do config até o D2
  entregar a praça Patrocínio) · colunas origem_* = rastreabilidade por linha.

É o insumo do Monte Carlo do M1: bootstrap de anos-safra INTEIROS mantém
prod × chuva × preço pareados na mesma linha (correlações reais preservadas).

Regra ano civil → ano-safra (PAM registra no ano da COLHEITA):
  safra N/N+1 usa prod do ano civil N+1; a chuva da janela de plantio soma os
  decêndios 25–36 do ano civil N (set–dez) e 1–12 do ano civil N+1 (jan–abr),
  conforme a janela ZARC da cultura no grupo de solo 2 (médio = 300/600 ha,
  referência municipal). Documentada aqui e na coluna `observacao`.

Gates de qualidade (falham ANTES de gerar arquivo — dado ruim versionado é
pior que dado ausente):
  G1. chuva: média anual do decendial > 800 mm (Cerrado MG ~1.100 mm). Hoje
      aborta: bug do clima.py:213/219 (D1) — matching 'PRECIPITACAO' sem
      acento vs 'PRECIPITAÇÃO' → chuva 100% zerada no processado;
  G2. produtividade: ≥ 18 safras com prod E chuva utilizável.

Cobertura parcial (ex.: 2019–25 truncados no decendial): a linha entra com
`frac_cobertura_janela`; chuva NaN se cobertura < 60% — visível, sem invenção.

Uso (na raiz do repo):
    python3 pipeline/fato.py                                        # insumos oficiais
    python3 pipeline/fato.py --decendial /tmp/clima_corrigido.csv   # decendial alternativo (testes)
    python3 pipeline/fato.py --saida /tmp/fato_teste                # não escreve em data/processed

Saída: data/processed/fato.parquet + data/processed/fato.csv
Códigos: 0 = fato gerado · 1 = gate reprovado (leia a mensagem) · 2 = insumo ausente.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
PROD_CSV_DEFAULT = REPO / 'notebooks/saida/produtividade.csv'
SERIE_M1_DEFAULT = REPO / 'notebooks/saida_preco/dados_anuais_Patos_de_Minas.csv'
DECENDIAL_DEFAULT = REPO / 'data/processed/clima/clima_patrcinio_decendial.csv'
JANELAS_DEFAULT = REPO / 'engine/janelas_zarc.json'
CUSTOS_DEFAULT = REPO / 'data/processed/mercado/conab_custos/resumo_custos_para_engine.csv'
CONFIG_DEFAULT = REPO / 'engine/config.yaml'
SAIDA_DEFAULT = REPO / 'data/processed'

MUNICIPIO = 'Patos de Minas'
COD_IBGE = 3148004
GRUPO_SOLO_REF = 2
PESO_SACA_KG = 60
COBERTURA_MINIMA = 0.6
DIAS_MINIMOS_DECENDIO = 5
SAFRAS_MINIMAS = 18
CHUVA_MEDIA_MINIMA_MM = 800

CULTURA_FATO = {'soja': 'soja', 'milho': 'milho'}
CULTURA_JANELA = {'soja': 'soja', 'milho': 'milho_verao'}
CULTURA_CUSTO = {'soja': 'soja', 'milho': 'milho_1a_safra'}
CULTURA_PRECO = {'soja': 'preco_soja', 'milho': 'preco_milho'}


def _carregar_produtividade(caminho: Path) -> pd.DataFrame:
    """CSV do notebook (ano civil, Soja, Milho em kg/ha) → longo [ano_civil, cultura, prod_kg_ha].

    FALLBACK: a fonte preferida é a série do M1 (_carregar_serie_m1)."""
    if not caminho.exists():
        print(f'[G2] Insumo ausente: {caminho} — série de produtividade não encontrada',
              file=sys.stderr)
        raise SystemExit(2)
    df = pd.read_csv(caminho)
    df.columns = [str(c).strip().lower() for c in df.columns]
    df = df.rename(columns={df.columns[0]: 'ano_civil'})
    longo = df.melt(id_vars='ano_civil', var_name='cultura_pam', value_name='prod_kg_ha')
    longo = longo[longo['cultura_pam'].isin(CULTURA_FATO)]
    longo['cultura'] = longo['cultura_pam'].map(CULTURA_FATO)
    return longo[['ano_civil', 'cultura', 'prod_kg_ha']].dropna(subset=['prod_kg_ha'])


def _carregar_serie_m1(caminho: Path) -> Optional[pd.DataFrame]:
    """Série do M1 (SIDRA t/5457): prod + preço implícito da PAM por ano civil.

    Fonte: notebooks/analise_preco_produtividade.py (M1) — preço implícito =
    valor da produção ÷ quantidade produzida (R$/saca 60 kg), versão REAL
    deflacionada pelo IPCA (BCB série 433) e NOMINAL.
    1 linha = ano civil × cultura {milho, soja}; None se o arquivo não existir.
    """
    if not caminho.exists():
        print(f'ℹ série do M1 ausente ({caminho}) — fallback: notebook p/ prod + '
              'hipótese do config p/ preço')
        return None
    df = pd.read_csv(caminho, header=None, skiprows=3,
                     names=['ano_civil', 'rend_milho', 'rend_soja',
                            'pnom_milho', 'pnom_soja', 'preal_milho', 'preal_soja'])
    partes = []
    for cultura, (rend, pnom, preal) in (
        ('milho', ('rend_milho', 'pnom_milho', 'preal_milho')),
        ('soja', ('rend_soja', 'pnom_soja', 'preal_soja')),
    ):
        partes.append(pd.DataFrame({
            'ano_civil': df['ano_civil'],
            'cultura': cultura,
            'prod_kg_ha': df[rend],
            'preco_nominal_rs_sc': df[pnom],
            'preco_real_rs_sc': df[preal],
        }))
    serie = pd.concat(partes, ignore_index=True).dropna(subset=['prod_kg_ha'])
    print(f'✔ Série do M1 carregada: {serie["ano_civil"].nunique()} anos civis '
          f'({serie["ano_civil"].min()}–{serie["ano_civil"].max()}) — prod e preço '
          'implícito PAM/SIDRA por ano-safra')
    return serie


def _carregar_decendial(caminho: Path) -> pd.DataFrame:
    """Decendial do D1 [ano, decendio, precipitacao_mm_total, origem] com GATE de chuva (G1)."""
    if not caminho.exists():
        print(f'[G1] Insumo ausente: {caminho} — rodar pipeline/clima.py primeiro',
              file=sys.stderr)
        raise SystemExit(2)
    df = pd.read_csv(caminho)
    colunas = {str(c).strip().lower() for c in df.columns}
    if not {'ano', 'decendio'}.issubset(colunas):
        print(f'[G1] Colunas inesperadas no decendial: {sorted(colunas)} — esperado [ano, decendio, ...]',
              file=sys.stderr)
        raise SystemExit(2)
    chuva_col = next((c for c in colunas if 'precipitacao' in c), None)
    if chuva_col is None:
        print(f'[G1] Coluna de precipitação não encontrada no decendial: {sorted(colunas)}',
              file=sys.stderr)
        raise SystemExit(2)
    df = df.rename(columns={chuva_col: 'chuva_mm'})
    anual = df.groupby('ano')['chuva_mm'].sum()
    media = anual.mean()
    if media < CHUVA_MEDIA_MINIMA_MM:
        print('=' * 88)
        print('✖ GATE G1 REPROVADO — a chuva do decendial é implausível, o fato NÃO foi gerado.')
        print(f'  Média anual observada: {media:.0f} mm (esperado: > {CHUVA_MEDIA_MINIMA_MM} mm no Cerrado MG).')
        print(f'  Insumo: {caminho}')
        print()
        print('  Causa provável (diagnóstico já registrado com o D1):')
        print('    pipeline/clima.py:213/219 — matching de coluna "PRECIPITACAO" (sem acento)')
        print('    contra "PRECIPITAÇÃO_TOTAL,_HORÁRIO_(MM)" (com Ç/Á) → coluna nunca achada')
        print('    → np.nan → groupby().sum() = 0. Os brutos em data/raw/inmet/csv estão bons.')
        print('  Como prosseguir: o D1 corrige o clima.py (normalizar acentos antes do matching),')
        print('  reprocessa e o fato.py passa a gerar o fato sem mudar nada aqui.')
        print('=' * 88)
        raise SystemExit(1)
    dias_col = next((c for c in df.columns if 'dias' in str(c).lower()), None)
    colunas = ['ano', 'decendio', 'chuva_mm']
    if dias_col is not None:
        df = df.rename(columns={dias_col: 'dias_com_dados'})
        colunas.append('dias_com_dados')
    return df[colunas]


def _carregar_janelas(caminho: Path) -> Dict[str, List[int]]:
    """engine/janelas_zarc.json → {cultura: decêndios viáveis no grupo de solo de referência}."""
    if not caminho.exists():
        print(f'Insumo ausente: {caminho} — rodar engine/adequacao.py primeiro', file=sys.stderr)
        raise SystemExit(2)
    with caminho.open('r', encoding='utf-8') as f:
        janelas = json.load(f)
    culturas = janelas.get('culturas', {})
    saida: Dict[str, List[int]] = {}
    for cultura, nome_janela in CULTURA_JANELA.items():
        grupo = culturas.get(nome_janela, {}).get(str(GRUPO_SOLO_REF), {})
        decendios = grupo.get('decendios', [])
        if not decendios:
            print(f'Janela vazia p/ {nome_janela} no grupo de solo {GRUPO_SOLO_REF} em {caminho}',
                  file=sys.stderr)
            raise SystemExit(2)
        saida[cultura] = sorted(int(d) for d in decendios)
    return saida


def _carregar_custos(caminho: Path) -> Dict[str, Dict[str, Any]]:
    """resumo_custos_para_engine.csv (D2) → {cultura: {custo_rs_ha, regioes, anos}}."""
    if not caminho.exists():
        print(f'Insumo ausente: {caminho} — rodar pipeline/mercado.py --custos primeiro',
              file=sys.stderr)
        raise SystemExit(2)
    df = pd.read_csv(caminho)
    custos: Dict[str, Dict[str, Any]] = {}
    for cultura, nome_conab in CULTURA_CUSTO.items():
        linha = df[df['cultura'].str.strip() == nome_conab]
        if linha.empty:
            print(f'Cultura {nome_conab!r} ausente de {caminho}', file=sys.stderr)
            raise SystemExit(2)
        reg = linha.iloc[0]
        custos[cultura] = {
            'custo_rs_ha': float(reg['custo_medio_ha']),
            'regioes': str(reg['regioes']),
            'anos': str(reg['anos']),
            'origem': 'conab_custos_regioes',
        }
    return custos


def _preco_para_rs_t(valor: str) -> Tuple[float, str]:
    """'R$ 130/sc' → (2166.67, 'hipótese do config'); falha se ilegível."""
    m = re.search(r'R\$\s*([\d.,]+)\s*/\s*([a-zA-Z]+)', str(valor).strip())
    if not m:
        return float('nan'), f'ilegível: {valor!r}'
    bruto = m.group(1)
    if ',' in bruto:
        bruto = bruto.replace('.', '').replace(',', '.')
    else:
        bruto = bruto.replace('.', '')
    numero = float(bruto)
    unidade = m.group(2).lower()
    if unidade == 'sc':
        return numero * 1000 / PESO_SACA_KG, 'hipotese_config'
    if unidade == 'kg':
        return numero * 1000, 'hipotese_config'
    if unidade == 't':
        return numero, 'hipotese_config'
    return float('nan'), f'unidade inesperada: R$/{unidade}'


def _carregar_config(caminho: Path) -> Dict[str, Any]:
    if not caminho.exists():
        print(f'Insumo ausente: {caminho} — hipóteses de preço/custo vêm do config do motor',
              file=sys.stderr)
        raise SystemExit(2)
    with caminho.open('r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


CUSTO_CHAVE_CONFIG = {
    'soja': ['custo_total_soja', 'custo_total'],
    'milho': ['custo_total'],
}


def _extrair_precos(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """{cultura: {preco_rs_t, origem}} a partir das hipóteses do config (pendência D2)."""
    saida: Dict[str, Dict[str, Any]] = {}
    for cultura, chave in CULTURA_PRECO.items():
        achado = None
        for info in (config.get('rotacoes') or {}).values():
            for hip in info.get('hipoteses', []):
                if str(hip.get('chave', '')) == chave:
                    achado = hip
                    break
            if achado:
                break
        if achado is None:
            print(f'Hipótese {chave!r} não encontrada no config', file=sys.stderr)
            raise SystemExit(2)
        preco_t, origem = _preco_para_rs_t(achado.get('valor', ''))
        if pd.isna(preco_t):
            print(f'Preço de hipótese ilegível p/ {chave}: {achado.get("valor")!r} ({origem})',
                  file=sys.stderr)
            raise SystemExit(2)
        saida[cultura] = {'preco_rs_t': round(preco_t, 2), 'origem': origem}
    return saida


def _extrair_custos(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Custos REAIS das hipóteses do config (Conab, D2) — {cultura: {...}} ou {} se ausentes.

    Preferido ao resumo CSV (média de regiões incl. Sul); o config usa a
    região-referência escolhida pelo D2 (Unaí-MG / Uruçuí-PI — proxy Cerrado),
    a MESMA fonte que o motor consome.
    """
    saida: Dict[str, Dict[str, Any]] = {}
    rotacoes = config.get('rotacoes') or {}
    for cultura, chaves in CUSTO_CHAVE_CONFIG.items():
        if cultura == 'milho':
            grupos = [rotacoes.get('milho_verao') or {}]
        else:
            grupos = [info for info in rotacoes.values() if info.get('culturas') and cultura in [c.lower() for c in info['culturas']]]
        for info in grupos:
            for chave in chaves:
                achado = next((h for h in info.get('hipoteses', []) if str(h.get('chave', '')) == chave), None)
                if achado is not None:
                    parse = _parse_hipotese_custo(achado.get('valor', ''))
                    if parse is not None:
                        saida[cultura] = {
                            'custo_rs_ha': parse[0],
                            'regioes': str(achado.get('metodo', 'config do motor')),
                            'anos': 'config do motor',
                            'origem': 'conab_custos_config',
                        }
                    break
            if cultura in saida:
                break
    return saida


def _parse_hipotese_custo(valor: str) -> Optional[Tuple[float, str]]:
    """'R$ 7.291/ha' → (7291.0, 'R$/ha'); ilegível → None."""
    m = re.search(r'R\$\s*([\d.,]+)\s*/\s*([a-zA-Z]+)', str(valor).strip())
    if not m:
        return None
    bruto = m.group(1)
    if ',' in bruto:
        bruto = bruto.replace('.', '').replace(',', '.')
    else:
        bruto = bruto.replace('.', '')
    return float(bruto), f'R$/{m.group(2).lower()}'


def _chuva_da_janela(decendial: pd.DataFrame, janela: List[int], ano_plantio: int) -> Tuple[float, float]:
    """Soma a chuva nos decêndios da janela; dec 1–12 contam do ano civil seguinte.

    Decêndios com < DIAS_MINIMOS_DECENDIO dias de dados contam como ausentes
    (estação falhou — somar o pouco existente seria chuva de mentira).
    Devolve (chuva_mm | NaN, frac_cobertura 0–1).
    """
    fonte = decendial
    if 'dias_com_dados' in decendial.columns:
        fonte = decendial[decendial['dias_com_dados'] >= DIAS_MINIMOS_DECENDIO]
    mapa = fonte.set_index(['ano', 'decendio'])['chuva_mm']
    achados: List[float] = []
    for d in janela:
        ano_civil = ano_plantio + 1 if d <= 12 else ano_plantio
        if (ano_civil, d) in mapa.index:
            achados.append(float(mapa.loc[(ano_civil, d)]))
    cobertura = len(achados) / len(janela)
    if cobertura < COBERTURA_MINIMA:
        return float('nan'), cobertura
    return sum(achados), cobertura


def montar_fato(fonte: pd.DataFrame,
                decendial: pd.DataFrame,
                janelas: Dict[str, List[int]],
                custos: Dict[str, Dict[str, Any]],
                precos: Dict[str, Dict[str, Any]],
                tem_serie: bool = False) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Devolve (fato, safras_puladas_por_cultura). O fato só contém anos-safra
    COMPLETOS (prod + chuva com cobertura) — é a matéria-prima do bootstrap
    pareado do M1; safra sem chuva utilizável fica de fora, contada e informada.

    `fonte` com série do M1 (tem_serie=True): prod e preços NOMINAL/REAL por
    ano civil (PAM/SIDRA t/5457); sem série: notebook p/ prod + hipótese fixa
    do config p/ preço (fallback)."""
    linhas: List[Dict[str, Any]] = []
    puladas: Dict[str, int] = {}
    for cultura, grupo_prod in fonte.groupby('cultura'):
        janela = janelas[cultura]
        for _, reg in grupo_prod.iterrows():
            ano_colheita = int(reg['ano_civil'])
            ano_plantio = ano_colheita - 1
            chuva, cobertura = _chuva_da_janela(decendial, janela, ano_plantio)
            if pd.isna(chuva):
                puladas[cultura] = puladas.get(cultura, 0) + 1
                continue
            obs: List[str] = []
            if cobertura < 1.0:
                obs.append(f'chuva parcial: {cobertura:.0%} da janela')
            if cultura == 'milho':
                obs.append('PAM mistura milho 1ª+2ª safra; janela/custo da 1ª como referência')
            custo = custos[cultura]
            obs.append(f"custo: {custo['regioes']}")
            if tem_serie:
                p_real = float(reg['preco_real_rs_sc'])
                p_nom = float(reg['preco_nominal_rs_sc'])
                preco_rs_t = round(p_real * 1000 / PESO_SACA_KG, 2)
                origem_prod = 'pam_sidra_t5457'
                origem_preco = 'pam_preco_implicito_sidra'
                obs.append(f'preço REAL IPCA R$ {p_real:.2f}/sc (nominal R$ {p_nom:.2f}/sc) '
                           '— implícito PAM valor÷quantidade')
                preco_nominal, preco_real = p_nom, p_real
            else:
                preco_rs_t = precos[cultura]['preco_rs_t']
                origem_prod = 'notebook_pam_1974_2025'
                origem_preco = precos[cultura]['origem']
                preco_nominal, preco_real = float('nan'), float('nan')
            linhas.append({
                'municipio': MUNICIPIO,
                'cod_ibge': COD_IBGE,
                'ano_safra': f'{ano_plantio}/{str(ano_colheita)[-2:]}',
                'ano_plantio': ano_plantio,
                'cultura': cultura,
                'prod_kg_ha': float(reg['prod_kg_ha']),
                'chuva_plantio_mm': chuva,
                'frac_cobertura_janela': round(cobertura, 2),
                'custo_rs_ha': custo['custo_rs_ha'],
                'preco_nominal_rs_sc': preco_nominal,
                'preco_real_rs_sc': preco_real,
                'preco_rs_t': preco_rs_t,
                'origem_prod': origem_prod,
                'origem_chuva': 'inmet_a523_patrocinio_decendial',
                'origem_custo': custo['origem'],
                'origem_preco': origem_preco,
                'observacao': ' | '.join(obs),
            })
    fato = pd.DataFrame(linhas)
    fato = fato.sort_values(['ano_safra', 'cultura']).reset_index(drop=True)
    return fato, puladas


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Gera a tabela fato (M3 — HackatOhm 2026): município × ano-safra × cultura',
        epilog=(
            'Exemplos:\n'
            '  python3 pipeline/fato.py\n'
            '  python3 pipeline/fato.py --decendial /tmp/clima_corrigido.csv --saida /tmp/fato'
        ),
    )
    parser.add_argument('--prod', default=str(PROD_CSV_DEFAULT),
                        help=f'série de produtividade FALLBACK (default: {PROD_CSV_DEFAULT})')
    parser.add_argument('--serie-m1', default=str(SERIE_M1_DEFAULT),
                        help=f'série do M1 (prod + preços PAM/SIDRA; preferida) (default: {SERIE_M1_DEFAULT})')
    parser.add_argument('--decendial', default=str(DECENDIAL_DEFAULT),
                        help=f'decendial de chuva (default: {DECENDIAL_DEFAULT})')
    parser.add_argument('--janelas', default=str(JANELAS_DEFAULT),
                        help=f'janelas ZARC por cultura/solo (default: {JANELAS_DEFAULT})')
    parser.add_argument('--custos', default=str(CUSTOS_DEFAULT),
                        help=f'custos Conab do D2 (default: {CUSTOS_DEFAULT})')
    parser.add_argument('--config', default=str(CONFIG_DEFAULT),
                        help=f'config do motor (hipóteses de preço/custo) (default: {CONFIG_DEFAULT})')
    parser.add_argument('--saida', default=str(SAIDA_DEFAULT),
                        help=f'diretório de saída (default: {SAIDA_DEFAULT})')
    args = parser.parse_args()

    serie = _carregar_serie_m1(Path(args.serie_m1))
    fonte = serie if serie is not None else _carregar_produtividade(Path(args.prod))
    decendial = _carregar_decendial(Path(args.decendial))
    janelas = _carregar_janelas(Path(args.janelas))
    config = _carregar_config(Path(args.config))
    precos = _extrair_precos(config)
    custos = _extrair_custos(config)
    faltam = sorted(set(CULTURA_FATO.values()) - set(custos))
    if faltam:
        print(f'ℹ custos REAIS ausentes no config p/ {faltam} — usando o resumo do D2 '
              '(média de regiões) como fallback')
        custos = _carregar_custos(Path(args.custos))

    fato, puladas = montar_fato(fonte, decendial, janelas, custos, precos,
                                tem_serie=serie is not None)

    safras_uteis = fato['ano_safra'].nunique()
    if safras_uteis < SAFRAS_MINIMAS:
        print(f'✖ GATE G2 REPROVADO — só {safras_uteis} safras com prod E chuva utilizável '
              f'(mínimo {SAFRAS_MINIMAS}): bootstrap do M1 fica frágil. Insumo: {args.decendial}')
        raise SystemExit(1)

    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    fato.to_parquet(saida / 'fato.parquet', index=False)
    fato.to_csv(saida / 'fato.csv', index=False)

    print(f'✔ Fato gerado: {len(fato)} linhas ({safras_uteis} safras × '
          f'{fato["cultura"].nunique()} culturas) → {saida}/fato.parquet + fato.csv')
    for cultura, grupo in fato.groupby('cultura'):
        media_chuva = grupo['chuva_plantio_mm'].mean()
        print(f"  {cultura:<6} {len(grupo)} safras | chuva da janela: média "
              f"{media_chuva:.0f} mm | custo R$ {grupo['custo_rs_ha'].iloc[0]:,.2f}/ha | "
              f"preço R$ {grupo['preco_rs_t'].iloc[0]:,.2f}/t ({grupo['origem_preco'].iloc[0]})")
    if puladas:
        puladas_txt = ', '.join(f'{c}: {n} safra(s)' for c, n in sorted(puladas.items()))
        print(f'  ℹ fora do fato (sem chuva utilizável na janela — estação A523 existe de ago/2006; '
              f'fill NASA POWER até 2005 é pendência do D1): {puladas_txt}')
    parcial = int((fato['frac_cobertura_janela'] < 1).sum())
    if parcial:
        print(f'  ⚠ {parcial} linha(s) com cobertura parcial da janela — ver frac_cobertura_janela/observacao')


if __name__ == '__main__':
    main()
