#!/usr/bin/env python3
"""pipeline/sanity.py — QA de ordem de grandeza dos números do projeto (M3 · HackatOhm 2026).

O contract/validate.py confere FORMA e CONSISTÊNCIA; este confere CREDIBILIDADE:
  · margens e produtividades plausíveis contra a literatura (Conab/Embrapa/PLANO §Pegadinhas);
  · unidades corretas — o clássico "R$/t virou R$/sc" explode aqui;
  · a margem declarada bate com as PRÓPRIAS hipóteses da rotação (Σ prod×preço − custo);
  · chuva plausível p/ o Cerrado mineiro, sem sentinelas 9999 do INMET, nulos ≤ 10%.

Pegar aqui custa 1 minuto; pegar depois do congelamento de sábado custa o pitch.

Grupos:
  A — Produtividade histórica (PAM real, notebooks/saida/produtividade.csv);
  B — Chuva da safra (notebooks/saida/chuva_mensal.csv);
  C — Margens/riscos do contrato (contract/results.json) contra a literatura;
  D — Unidades: recomposição da margem por rotação + faixas de preço por cultura;
  E — Tabela fato (--fato): colunas, duplicatas, ranges por linha e nulos ≤ 10%
      como regra INTEGRAL (com --fato, B4 também endurece de AVISO p/ ERRO).

Uso (na raiz do repo):
    python3 pipeline/sanity.py                                    # hoje: contrato + CSVs históricos
    python3 pipeline/sanity.py --fato data/processed/fato.parquet  # modo congelamento (sábado)

Códigos de saída: 0 = sem ERRO (avisos não bloqueiam) · 1 = ERRO · 2 = contrato ausente.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
CONTRATO_DEFAULT = REPO / 'contract/results.json'
CSV_DIR_DEFAULT = REPO / 'notebooks/saida'

OK, AVISO, ERRO = 'OK', 'AVISO', 'ERRO'
MARCA = {OK: '✔', AVISO: '⚠', ERRO: '✖'}

GRUPO_A = 'A · Produtividade histórica (PAM)'
GRUPO_B = 'B · Chuva da safra (Cerrado MG)'
GRUPO_C = 'C · Margens e riscos do contrato vs literatura'
GRUPO_D = 'D · Unidades e recomposição de margem'
GRUPO_E = 'E · Tabela fato'

PESO_SACA_KG = {'soja': 60, 'milho': 60, 'milho_safrinha': 60, 'feijao': 60, 'milho_verao': 60}

FAIXAS_PRECO = {
    'soja': ('R$/sc', 90, 180, 'Conab — soja, saca 60 kg (~R$ 120–160/sc)'),
    'milho': ('R$/sc', 30, 90, 'Conab/ESALQ — milho (~R$ 50–80/sc)'),
    'milho_safrinha': ('R$/sc', 30, 90, 'Conab/ESALQ — milho safrinha (mesma saca)'),
    'milho_verao': ('R$/sc', 30, 90, 'Conab/ESALQ — milho 1ª safra (mesma saca)'),
    'feijao': ('R$/kg', 6, 15, 'Conab/CEPEA — feijão carioca (~R$ 7–12/kg)'),
    'sorgo': ('R$/kg', 0.30, 1.00, 'Conab/CEPEA — sorgo granífero (~R$ 0,45–0,70/kg)'),
}

ROTACOES_ESPERADAS = ['soja_milho', 'soja_sorgo', 'feijao_sorgo', 'milho_verao', 'soja_solteira', 'capital_pousio']


def _res(ident: str, grupo: str, status: str, texto: str) -> Dict[str, str]:
    return {'id': ident, 'grupo': grupo, 'status': status, 'texto': texto}


def _brs(valor: float, decimais: int = 0) -> str:
    """4180.0 → '4.180'; 70.93 → '70,93' (padrão PT-BR, como o engine/report.py)."""
    texto = f'{valor:,.{decimais}f}'
    return texto.replace(',', 'X').replace('.', ',').replace('X', '.')


# ------------------------------------------------------------- parsing de unidades

def _numero_br(texto: str) -> Optional[float]:
    """'4.000'→4000 · '0,55'→0.55 · '9,00'→9.0 · '130'→130 · sem número→None."""
    m = re.search(r'-?\d[\d.,]*', str(texto))
    if not m:
        return None
    bruto = m.group(0)
    if ',' in bruto:
        bruto = bruto.replace('.', '').replace(',', '.')
    else:
        bruto = bruto.replace('.', '')
    try:
        return float(bruto)
    except ValueError:
        return None


def _parse_hipotese(valor: str) -> Optional[Tuple[float, str]]:
    """'R$ 130/sc'→(130,'R$/sc') · '55 sc/ha'→(55,'sc/ha') · '4.000 kg/ha'→(4000,'kg/ha'). Ilegível→None."""
    v = str(valor).strip()
    m = re.search(r'R\$\s*([\d.,]+)\s*/\s*([a-zA-Z]+)', v)
    if m:
        return _numero_br(m.group(1)), f'R$/{m.group(2).lower()}'
    m = re.search(r'([\d.,]+)\s*(sc/ha|kg/ha)', v)
    if m:
        return _numero_br(m.group(1)), m.group(2)
    return None


def _extrair_hipoteses(info: Dict[str, Any]) -> Tuple[Dict[str, Tuple[float, str]], List[str]]:
    """Chaves produtividade_*/preco_*/custo_total → {(chave): (valor, unidade)}; ilegíveis listadas."""
    achados: Dict[str, Tuple[float, str]] = {}
    ilegiveis: List[str] = []
    for hip in info.get('hipoteses', []):
        chave = str(hip.get('chave', ''))
        if not chave.startswith(('produtividade_', 'preco_', 'custo_total')):
            continue
        parse = _parse_hipotese(hip.get('valor', ''))
        if parse is None:
            ilegiveis.append(chave)
        else:
            achados[chave] = parse
    return achados, ilegiveis


def _receita_rs_ha(prod: Tuple[float, str], preco: Tuple[float, str], cultura: str) -> Optional[float]:
    """Receita R$/ha a partir de (valor, unidade); None se unidades incompatíveis."""
    peso = PESO_SACA_KG.get(cultura)
    p_val, p_un = prod
    if p_un == 'sc/ha':
        if peso is None:
            return None
        kg_ha = p_val * peso
    elif p_un == 'kg/ha':
        kg_ha = p_val
    else:
        return None
    q_val, q_un = preco
    if q_un == 'R$/kg':
        rs_kg = q_val
    elif q_un == 'R$/sc':
        if peso is None:
            return None
        rs_kg = q_val / peso
    elif q_un == 'R$/t':
        rs_kg = q_val / 1000
    else:
        return None
    return kg_ha * rs_kg


def _converter_preco(val: float, un: str, alvo: str, cultura: str) -> Optional[float]:
    peso = PESO_SACA_KG.get(cultura, 60)
    if un == alvo:
        return val
    if alvo == 'R$/sc':
        if un == 'R$/kg':
            return val * peso
        if un == 'R$/t':
            return val * peso / 1000
    elif alvo == 'R$/kg':
        if un == 'R$/sc':
            return val / peso
        if un == 'R$/t':
            return val / 1000
    return None


# ------------------------------------------------------------------------ grupo A

def checar_produtividade(csv_dir: Path) -> List[Dict[str, str]]:
    resultados: List[Dict[str, str]] = []
    caminho = csv_dir / 'produtividade.csv'
    if not caminho.exists():
        return [_res('A0', GRUPO_A, AVISO, f'{caminho} não encontrado — grupo pulado (aguardando D1 versionar data/raw)')]
    df = pd.read_csv(caminho)
    df.columns = [str(c).strip().lower() for c in df.columns]
    df = df.rename(columns={df.columns[0]: 'ano'})
    if 'soja' not in df.columns or 'milho' not in df.columns:
        return [_res('A0', GRUPO_A, AVISO, f'colunas inesperadas em {caminho}: {list(df.columns)} — esperado [ano, Milho, Soja]')]
    ultimos = df[df['ano'] >= df['ano'].max() - 20]

    soja_sc = ultimos['soja'].mean() / 60.0
    if not (45 <= soja_sc <= 70):
        resultados.append(_res('A1', GRUPO_A, ERRO,
            f'média soja (últimos 20 anos): {soja_sc:.1f} sc/ha FORA de [45, 70] — '
            'unidade errada (kg/ha vs sc/ha)? município errado? (fonte: Conab/Embrapa · PLANO §Quinta)'))
    elif not (55 <= soja_sc <= 65):
        resultados.append(_res('A1', GRUPO_A, AVISO,
            f'média soja (últimos 20 anos): {soja_sc:.1f} sc/ha — plausível ([45, 70]), '
            'mas abaixo do estrito 55–65 da literatura (fonte: Conab/Embrapa)'))
    else:
        resultados.append(_res('A1', GRUPO_A, OK,
            f'média soja (últimos 20 anos): {soja_sc:.1f} sc/ha ∈ [55, 65] (fonte: Conab/Embrapa)'))

    fora = ultimos[ultimos['soja'].notna() & ((ultimos['soja'] / 60 < 15) | (ultimos['soja'] / 60 > 80))]
    if len(fora):
        anos = ', '.join(str(a) for a in fora['ano'].tolist())
        resultados.append(_res('A2', GRUPO_A, ERRO,
            f'{len(fora)} ano(s) de soja fora de [15, 80] sc/ha na janela do bootstrap: anos {anos} '
            '(plausibilidade física)'))
    else:
        resultados.append(_res('A2', GRUPO_A, OK,
            f'soja por ano dentro de [15, 80] sc/ha na janela do bootstrap (20 anos) — '
            f'observado {ultimos["soja"].min()/60:.0f}–{ultimos["soja"].max()/60:.0f} sc/ha'))

    fora_m = ultimos[ultimos['milho'].notna() & ((ultimos['milho'] / 60 < 60) | (ultimos['milho'] / 60 > 200))]
    if len(fora_m):
        anos = ', '.join(str(a) for a in fora_m['ano'].tolist())
        resultados.append(_res('A3', GRUPO_A, ERRO,
            f'{len(fora_m)} ano(s) de milho FORA de [60, 200] sc/ha na janela do bootstrap: anos {anos} — '
            'PAM mistura 1ª+2ª safra (pegadinha do PLANO); unidade trocada?'))
    else:
        resultados.append(_res('A3', GRUPO_A, OK,
            f'milho por ano dentro de [60, 200] sc/ha na janela do bootstrap (PAM total 1ª+2ª) — '
            f'média 20a: {ultimos["milho"].mean()/60:.0f} sc/ha'))

    nulos_20 = int(ultimos['soja'].isna().sum() + ultimos['milho'].isna().sum())
    if len(ultimos) >= 20 and nulos_20 == 0:
        resultados.append(_res('A4', GRUPO_A, OK,
            f'série de {len(df)} anos ({df["ano"].min()}–{df["ano"].max()}), últimos 20 sem nulos — '
            'suficiente p/ o bootstrap do M1'))
    else:
        resultados.append(_res('A4', GRUPO_A, AVISO,
            f'janela de 20 anos incompleta: {len(ultimos)} anos, {nulos_20} nulos — '
            'bootstrap com série curta aumenta incerteza'))
    return resultados


# ------------------------------------------------------------------------ grupo B

def checar_chuva(csv_dir: Path, regra_integral: bool) -> List[Dict[str, str]]:
    resultados: List[Dict[str, str]] = []
    caminho = csv_dir / 'chuva_mensal.csv'
    if not caminho.exists():
        return [_res('B0', GRUPO_B, AVISO, f'{caminho} não encontrado — grupo pulado (aguardando D1 versionar data/raw)')]
    df = pd.read_csv(caminho)
    if str(df.columns[0]).startswith('Unnamed'):
        df = df.rename(columns={df.columns[0]: 'ano'})
    df.columns = [str(c).strip() for c in df.columns]
    safra = next((c for c in df.columns if 'safra' in c.lower()), None)
    if safra is None:
        return [_res('B0', GRUPO_B, AVISO, f'coluna de safra não encontrada em {caminho}: {list(df.columns)}')]
    num_cols = [c for c in df.columns if c != 'ano']

    serie = df[['ano', safra]].dropna()
    li, ls = serie[safra].min(), serie[safra].max()
    if li < 500 or ls > 2000:
        resultados.append(_res('B1', GRUPO_B, ERRO,
            f'chuva da safra fora de [500, 2000] mm: min {li:.0f}, máx {ls:.0f} — '
            'unidade errada (mm vs cm)? estação errada? (Cerrado MG)'))
    else:
        resultados.append(_res('B1', GRUPO_B, OK,
            f'chuva da safra Out–Mar por ano dentro de [500, 2000] mm — observado {li:.0f}–{ls:.0f} mm'))

    media = serie[safra].mean()
    if not (800 <= media <= 1600):
        resultados.append(_res('B2', GRUPO_B, AVISO,
            f'média da safra {media:.0f} mm fora de [800, 1600] mm (Cerrado MG) — conferir série/estação'))
    else:
        resultados.append(_res('B2', GRUPO_B, OK, f'média da safra {media:.0f} mm ∈ [800, 1600] mm (Cerrado MG)'))

    sentinelas = int((df[num_cols] == 9999).sum().sum())
    if sentinelas:
        resultados.append(_res('B3', GRUPO_B, ERRO,
            f'{sentinelas} célula(s) com valor 9999 — sentinela de falha do INMET: '
            'tratar como nulo no pipeline/clima.py antes do fato (pegadinha do PLANO)'))
    else:
        resultados.append(_res('B3', GRUPO_B, OK, 'nenhuma sentinela 9999 (falha INMET) na série'))

    pct_nulos = (df[num_cols].isna().mean() * 100).round(0)
    alvo = pct_nulos[pct_nulos > 10]
    if len(alvo):
        detalhe = ', '.join(f'{c}: {v:.0f}%' for c, v in alvo.items())
        texto = (f'nulos > 10% em {len(alvo)} coluna(s) — {detalhe}; se concentrados no início '
                 'da série, truncar (ex.: a partir de 1981) resolve (regra: PLANO §Quinta — '
                 '">10% de nulos sem explicação")')
        resultados.append(_res('B4', GRUPO_B, ERRO if regra_integral else AVISO, texto))
    else:
        resultados.append(_res('B4', GRUPO_B, OK, 'nenhuma coluna com > 10% de nulos (regra dos 10% do plano)'))

    meses = [c for c in num_cols if 'Safra' not in c and ':' not in c]
    if meses:
        total_anual = df[meses].sum(axis=1, min_count=5)
        media_anual = total_anual.mean()
        if media_anual <= 800:
            resultados.append(_res('B5', GRUPO_B, ERRO,
                f'chuva anual média {media_anual:.0f} mm ≤ 800 mm — série zerada ou incompleta? '
                '(sentinela anti-bug: pegaria chuva 100% zero de uma vez)'))
        else:
            resultados.append(_res('B5', GRUPO_B, OK,
                f'chuva anual média {media_anual:.0f} mm > 800 mm (Cerrado MG ~1.100 mm) ✓'))
    return resultados


# ------------------------------------------------------------------------ grupo C

def checar_margens(contrato: Dict[str, Any]) -> List[Dict[str, str]]:
    resultados: List[Dict[str, str]] = []
    rot = contrato.get('rotacoes', {})

    def margem(nome: str) -> Optional[float]:
        return rot[nome]['margem_reais_por_ha'] if nome in rot else None

    def risco(nome: str) -> Optional[int]:
        return rot[nome]['risco_por_mil'] if nome in rot else None

    ausentes = [n for n in ROTACOES_ESPERADAS if n not in rot]
    if ausentes:
        resultados.append(_res('C0', GRUPO_C, AVISO,
            f'rotações esperadas ausentes do contrato: {", ".join(ausentes)} — checagens C cobrem o que existe'))

    m = margem('soja_milho')
    if m is not None:
        if not (2500 <= m <= 6000):
            resultados.append(_res('C1', GRUPO_C, ERRO,
                f'margem soja_milho R$ {_brs(m)}/ha FORA de [2.500, 6.000] — '
                'literatura ≈ R$ 4.180/ha (PLANO §Sexta: "se der muito diferente, entender por quê")'))
        else:
            resultados.append(_res('C1', GRUPO_C, OK,
                f'margem soja_milho R$ {_brs(m)}/ha ∈ [2.500, 6.000] (literatura ≈ R$ 4.180/ha · PLANO §Sexta)'))

    m = margem('milho_verao')
    if m is not None:
        if not (1500 <= m <= 4000):
            resultados.append(_res('C2', GRUPO_C, ERRO,
                f'margem milho_verao R$ {_brs(m)}/ha FORA de [1.500, 4.000] — literatura ≈ R$ 2.600/ha'))
        else:
            resultados.append(_res('C2', GRUPO_C, OK,
                f'margem milho_verao R$ {_brs(m)}/ha ∈ [1.500, 4.000] (literatura ≈ R$ 2.600/ha)'))

    trio = [margem('soja_milho'), margem('soja_solteira'), margem('capital_pousio')]
    if all(v is not None for v in trio):
        if not (trio[0] > trio[1] > trio[2]):
            resultados.append(_res('C3', GRUPO_C, ERRO,
                f'ordem econômica violada: esperado soja_milho ({_brs(trio[0])}) > soja_solteira '
                f'({_brs(trio[1])}) > capital_pousio ({_brs(trio[2])}) — rotação que não agrega valor é bug'))
        else:
            resultados.append(_res('C3', GRUPO_C, OK,
                f'ordem econômica ok: soja_milho {_brs(trio[0])} > soja_solteira {_brs(trio[1])} > '
                f'capital_pousio {_brs(trio[2])} R$/ha — a rotação agrega valor'))

    mf, rf = margem('feijao_sorgo'), risco('feijao_sorgo')
    ms, rs = margem('soja_milho'), risco('soja_milho')
    if None not in (mf, rf, ms, rs):
        if mf > ms and rf < rs:
            resultados.append(_res('C4', GRUPO_C, AVISO,
                f'feijao_sorgo: margem R$ {_brs(mf)}/ha MAIOR que soja_milho (R$ {_brs(ms)}) com risco '
                f'MENOR ({rf}‰ vs {rs}‰) — too good to be true: conferir preços/custos do feijão'))
        else:
            resultados.append(_res('C4', GRUPO_C, OK,
                f'feijao_sorgo: margem alta (R$ {_brs(mf)}/ha) com risco alto ({rf}‰) — consistente'))

    m = margem('capital_pousio')
    if m is not None:
        if not (80 <= m <= 500):
            resultados.append(_res('C5', GRUPO_C, ERRO,
                f'capital_pousio R$ {_brs(m)}/ha FORA de [80, 500] — Selic ~13% a.a. sobre custeio '
                '~R$ 3.500/ha por ~5 meses ≈ R$ 190/ha (referência de "não plantar")'))
        else:
            resultados.append(_res('C5', GRUPO_C, OK,
                f'capital_pousio R$ {_brs(m)}/ha ∈ [80, 500] (Selic ~13% × custeio ~5 meses)'))

    riscos = [(nome, int(info['risco_por_mil'])) for nome, info in rot.items()]
    suspeitos = [f'{n} ({r}‰)' for n, r in riscos if r > 500]
    if suspeitos:
        resultados.append(_res('C6', GRUPO_C, ERRO,
            f'risco > 500‰ (ninguém plantaria): {", ".join(suspeitos)} — conferir o MC'))
    else:
        maior = max(riscos, key=lambda nr: nr[1]) if riscos else ('—', 0)
        resultados.append(_res('C6', GRUPO_C, OK,
            f'risco máximo plausível: {maior[0]} com {maior[1]}‰ (P[margem<0] ≈ {maior[1]/10:.0f}%)'))
    return resultados


# ------------------------------------------------------------------------ grupo D

def checar_unidades(contrato: Dict[str, Any]) -> List[Dict[str, str]]:
    resultados: List[Dict[str, str]] = []
    for nome, info in contrato.get('rotacoes', {}).items():
        achados, ilegiveis = _extrair_hipoteses(info)
        ident = f'D1·{nome}'

        if ilegiveis:
            resultados.append(_res(ident, GRUPO_D, ERRO,
                f'hipótese(s) ilegível(is): {", ".join(ilegiveis)} — padrão exigido: '
                '"55 sc/ha", "R$ 130/sc", "R$ 0,55/kg", "R$ 7.610/ha" (decisão de checkpoint: fora do padrão reprova)'))
            continue

        prods = {k[len('produtividade_'):]: v for k, v in achados.items() if k.startswith('produtividade_')}
        precos = {k[len('preco_'):]: v for k, v in achados.items() if k.startswith('preco_')}
        custo = achados.get('custo_total')

        if not prods and not precos:
            resultados.append(_res(ident, GRUPO_D, OK,
                'isenta de recomposição (sem prod×preço — ex.: capital/pousio; faixa coberta em C5)'))
            continue

        for cultura, (q_val, q_un) in sorted(precos.items()):
            faixa = FAIXAS_PRECO.get(cultura)
            if faixa is None:
                resultados.append(_res(f'D2·{nome}[{cultura}]', GRUPO_D, AVISO,
                    f'preco_{cultura} = {q_val:g} {q_un} — cultura sem faixa de referência; conferir manualmente'))
                continue
            alvo, li, ls, fonte = faixa
            conv = _converter_preco(q_val, q_un, alvo, cultura)
            if conv is None:
                resultados.append(_res(f'D2·{nome}[{cultura}]', GRUPO_D, ERRO,
                    f'preco_{cultura} = "{q_val:g} {q_un}" — unidade incompatível com a cultura (esperado {alvo})'))
            elif conv < li / 2 or conv > ls * 2:
                resultados.append(_res(f'D2·{nome}[{cultura}]', GRUPO_D, ERRO,
                    f'preco_{cultura} = {q_val:g} {q_un} (→ {conv:g} {alvo}) FORA de ×2 da faixa '
                    f'[{li:g}, {ls:g}] {alvo} — unidade trocada? (fonte: {fonte})'))
            elif conv < li or conv > ls:
                resultados.append(_res(f'D2·{nome}[{cultura}]', GRUPO_D, AVISO,
                    f'preco_{cultura} = {q_val:g} {q_un} (→ {conv:g} {alvo}) fora da faixa histórica '
                    f'[{li:g}, {ls:g}] {alvo}, mas dentro de ×2 (fonte: {fonte})'))
            else:
                resultados.append(_res(f'D2·{nome}[{cultura}]', GRUPO_D, OK,
                    f'preco_{cultura} = {q_val:g} {q_un} (→ {conv:g} {alvo}) ∈ [{li:g}, {ls:g}] (fonte: {fonte})'))

        if custo is None:
            resultados.append(_res(ident, GRUPO_D, AVISO,
                'sem custo_total declarado — margem não auditável contra as próprias hipóteses'))
            continue
        sem_par = sorted(set(prods) ^ set(precos))
        if sem_par:
            resultados.append(_res(ident, GRUPO_D, AVISO,
                f'recomposição incompleta: sem preço p/ {", ".join(sem_par)} — margem não auditável '
                '(pedir a hipótese faltante ao D2/M1 no checkpoint)'))
            continue
        pares = sorted(set(prods) & set(precos))
        receitas: List[float] = []
        incompativel = False
        for cultura in pares:
            receita = _receita_rs_ha(prods[cultura], precos[cultura], cultura)
            if receita is None:
                resultados.append(_res(ident, GRUPO_D, ERRO,
                    f'unidades incompatíveis p/ {cultura}: prod {prods[cultura]} × preço {precos[cultura]}'))
                incompativel = True
                break
            receitas.append(receita)
        if incompativel:
            continue
        recomp = sum(receitas) - custo[0]
        declarada = float(info.get('margem_reais_por_ha', 0))
        diff = abs(recomp - declarada) / max(abs(declarada), 1)
        parcelas = ' + '.join(f'{c} {prods[c][0]:g} {prods[c][1]}×{precos[c][0]:g} {precos[c][1]}' for c in pares)
        if diff <= 0.15:
            resultados.append(_res(ident, GRUPO_D, OK,
                f'margem recomposta R$ {_brs(recomp)}/ha ≈ declarada R$ {_brs(declarada)}/ha (Δ {diff:.0%}) — '
                f'{parcelas} − custo {custo[0]:g} R$/ha ✓'))
        else:
            resultados.append(_res(ident, GRUPO_D, ERRO,
                f'margem recomposta R$ {_brs(recomp)}/ha ≠ declarada R$ {_brs(declarada)}/ha (Δ {diff:.0%} > 15%) — '
                f'{parcelas} − custo {custo[0]:g} R$/ha: unidade trocada? custo deduzido 2×?'))
    return resultados


# ------------------------------------------------------------------------ grupo E

def _faixa_prod_kg_ha(cultura: str) -> Optional[Tuple[int, int]]:
    c = str(cultura).lower()
    if 'soja' in c:
        return (900, 4800)
    if 'milho' in c:
        return (3600, 12000)
    if 'sorgo' in c:
        return (1000, 8000)
    if 'feij' in c:
        return (400, 4000)
    return None


def checar_fato(caminho: Path) -> List[Dict[str, str]]:
    resultados: List[Dict[str, str]] = []
    if not caminho.exists():
        return [_res('E0', GRUPO_E, ERRO, f'{caminho} não encontrado — rodar pipeline/fato.py primeiro')]
    fato = pd.read_parquet(caminho)
    colunas = {str(c).lower() for c in fato.columns}
    minimas = {'ano_safra', 'cultura', 'prod_kg_ha', 'custo_rs_ha', 'preco_rs_t'}
    faltam = minimas - colunas
    if faltam:
        resultados.append(_res('E1', GRUPO_E, ERRO,
            f'colunas mínimas ausentes no fato: {", ".join(sorted(faltam))} — '
            f'presentes: {", ".join(sorted(colunas))}'))
        return resultados
    flags = [c for c in colunas if c.startswith('origem_')]
    if not flags:
        resultados.append(_res('E1', GRUPO_E, AVISO,
            'sem colunas origem_* (flag de proveniência INMET/NASA) — perder a rastreabilidade por linha'))
    else:
        resultados.append(_res('E1', GRUPO_E, OK,
            f'colunas mínimas presentes + flags de origem: {", ".join(sorted(flags))}'))

    chaves = ([c for c in ('municipio', 'cod_ibge') if c in colunas] + ['ano_safra', 'cultura'])
    duplicatas = int(fato.duplicated(subset=chaves).sum())
    if duplicatas:
        resultados.append(_res('E2', GRUPO_E, ERRO,
            f'{duplicatas} linha(s) duplicada(s) por {chaves} — o fato é 1 linha = município × ano-safra × cultura'))
    else:
        resultados.append(_res('E2', GRUPO_E, OK, f'sem duplicatas por {chaves} ({len(fato)} linhas)'))

    violacoes: List[str] = []
    for cultura, grupo in fato.groupby('cultura'):
        faixa = _faixa_prod_kg_ha(cultura)
        if faixa is None:
            violacoes.append(f'{cultura}: sem faixa de referência')
            continue
        fora = grupo[(grupo['prod_kg_ha'] < faixa[0]) | (grupo['prod_kg_ha'] > faixa[1])]
        if len(fora):
            violacoes.append(f'{cultura}: {len(fora)} ano(s) fora de [{faixa[0]:,}, {faixa[1]:,}] kg/ha'.replace(',', '.'))
    if violacoes:
        resultados.append(_res('E3', GRUPO_E, ERRO, 'produtividade fora da faixa física por linha — ' + '; '.join(violacoes)))
    else:
        culturas = ', '.join(sorted(fato['cultura'].astype(str).unique()))
        resultados.append(_res('E3', GRUPO_E, OK, f'produtividade por linha dentro das faixas físicas ({culturas})'))

    negativos = int((fato['custo_rs_ha'] <= 0).sum() + (fato['preco_rs_t'] <= 0).sum())
    if negativos:
        resultados.append(_res('E3·sinais', GRUPO_E, ERRO,
            f'{negativos} linha(s) com custo/preço ≤ 0 — sinal trocado ou unidade errada'))
    for col_chuva in [c for c in colunas if c.startswith('chuva')]:
        fora = fato[fato[col_chuva].notna() & ((fato[col_chuva] < 10) | (fato[col_chuva] > 1000))]
        if len(fora):
            resultados.append(_res('E3·chuva', GRUPO_E, ERRO,
                f'{len(fora)} linha(s) com {col_chuva} fora de [10, 1000] mm — '
                'piso 10 (seca extrema real ok, ex.: El Niño 2024/25); teto 1000 '
                '(janela chuvosa real chega a ~950; alvo: zero/unidade errada)'))

    pct_nulos = (fato[list(minimas)].isna().mean() * 100).round(0)
    alvo = pct_nulos[pct_nulos > 10]
    if len(alvo):
        detalhe = ', '.join(f'{c}: {v:.0f}%' for c, v in alvo.items())
        resultados.append(_res('E4', GRUPO_E, ERRO,
            f'nulos > 10% em {len(alvo)} coluna(s) — {detalhe} (regra INTEGRAL do plano: sem explicação reprova)'))
    else:
        resultados.append(_res('E4', GRUPO_E, OK, 'nenhuma coluna com > 10% de nulos'))

    if 'origem_preco' in colunas:
        n_hip = int(fato['origem_preco'].astype(str).str.startswith('hipotese').sum())
        if n_hip:
            resultados.append(_res('E5', GRUPO_E, AVISO,
                f'{n_hip}/{len(fato)} linha(s) com preço de HIPÓTESE do config '
                "(origem_preco='hipotese_*') — trocar pela praça Patrocínio (Conab) quando o D2 entregar"))
        else:
            resultados.append(_res('E5', GRUPO_E, OK,
                'preço com origem oficial (não hipótese) ✓'))
    return resultados


# ------------------------------------------------------------------------- saída

def imprimir(resultados: List[Dict[str, str]], insumos: Dict[str, str]) -> int:
    print('=' * 96)
    print('SANITY — QA DE ORDEM DE GRANDEZA · HackatOhm 2026 (M3)')
    print(f"Contrato: {insumos['contrato']} | Histórico: {insumos['csv_dir']}"
          + (f" | Fato: {insumos['fato']}" if insumos['fato'] else ''))
    print('=' * 96)
    grupo = None
    for r in resultados:
        if r['grupo'] != grupo:
            grupo = r['grupo']
            print()
            print(grupo)
            print('-' * 96)
        print(f"  {MARCA[r['status']]} {r['id']:<26} {r['texto']}")
    n_ok = sum(1 for r in resultados if r['status'] == OK)
    n_av = sum(1 for r in resultados if r['status'] == AVISO)
    n_er = sum(1 for r in resultados if r['status'] == ERRO)
    print()
    print('-' * 96)
    if n_er:
        print(f'RESUMO: {n_ok} ✔ · {n_av} ⚠ · {n_er} ✖  →  REPROVADO — corrigir antes do publish: '
              'o validate.py aprova a FORMA, este aprova a CREDIBILIDADE (o que o schema não vê)')
    else:
        print(f'RESUMO: {n_ok} ✔ · {n_av} ⚠ · 0 ✖  →  VALIDADO (avisos não bloqueiam)')
    return 1 if n_er else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description='QA de ordem de grandeza do projeto (M3 — HackatOhm 2026)',
        epilog=(
            'Exemplos:\n'
            '  python3 pipeline/sanity.py\n'
            '  python3 pipeline/sanity.py --fato data/processed/fato.parquet'
        ),
    )
    parser.add_argument('--contrato', default=str(CONTRATO_DEFAULT),
                        help=f'contrato publicado (default: {CONTRATO_DEFAULT})')
    parser.add_argument('--csv-dir', default=str(CSV_DIR_DEFAULT),
                        help=f'diretório com CSVs históricos (default: {CSV_DIR_DEFAULT})')
    parser.add_argument('--fato', default=None,
                        help='data/processed/fato.parquet — ativa grupo E e ENDURECE a regra de nulos (B4 → ERRO)')
    args = parser.parse_args()

    contrato_path = Path(args.contrato)
    if not contrato_path.exists():
        print(f'Contrato não encontrado: {contrato_path} — rode contract/validate.py --publish antes',
              file=sys.stderr)
        raise SystemExit(2)
    with contrato_path.open('r', encoding='utf-8') as f:
        contrato = json.load(f)

    csv_dir = Path(args.csv_dir)
    regra_integral = args.fato is not None
    resultados: List[Dict[str, str]] = []
    resultados += checar_produtividade(csv_dir)
    resultados += checar_chuva(csv_dir, regra_integral)
    resultados += checar_margens(contrato)
    resultados += checar_unidades(contrato)
    if args.fato:
        resultados += checar_fato(Path(args.fato))

    insumos = {'contrato': str(contrato_path), 'csv_dir': str(csv_dir), 'fato': args.fato}
    raise SystemExit(imprimir(resultados, insumos))


if __name__ == '__main__':
    main()
