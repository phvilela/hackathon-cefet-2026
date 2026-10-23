#!/usr/bin/env python3
"""contract/validate.py — o porteiro do contrato motor → site (M3 · HackatOhm 2026).

Duas camadas de verificação:
  1. FORMA      — results.json contra contract/results.schema.json (JSON Schema 2020-12);
  2. SEMÂNTICA — consistência que schema não vê: soma de áreas por talhão, referências
                  talhão/rotação, coerência de grupos de solo, centavos ↔ reais,
                  knee dentro da fronteira, perfis coerentes com a fronteira e
                  status MOCK/REAL versus fontes 'MOCK://…'.

Uso (na raiz do repo):
    python3 contract/validate.py                                 # valida contract/results.json
    python3 contract/validate.py engine/out/results_mock.json    # valida um arquivo qualquer
    python3 contract/validate.py --publish                       # valida o output do motor e
                                                                  # PUBLICA em contract/results.json

Códigos de saída: 0 = válido (avisos não bloqueiam) · 1 = inválido · 2 = arquivo/schema não encontrado.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parents[1]
SCHEMA_DEFAULT = REPO / 'contract/results.schema.json'
CONTRATO_DEFAULT = REPO / 'contract/results.json'
MOTOR_DEFAULT = REPO / 'engine/out/results_mock.json'

TOL_REAIS = 0.011
TOL_HA_RISCO = 0.06


def carregar_json(caminho: Path) -> Dict[str, Any]:
    with caminho.open('r', encoding='utf-8') as f:
        return json.load(f)


def erros_de_forma(dados: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    """Valida contra o JSON Schema e devolve mensagens com caminho JSON Pointer."""
    validador = Draft202012Validator(schema)
    erros = []
    for erro in sorted(validador.iter_errors(dados), key=lambda e: list(e.absolute_path)):
        ponteiro = '/' + '/'.join(str(p) for p in erro.absolute_path)
        erros.append(f'forma{ponteiro}: {erro.message}')
    return erros


# ------------------------------------------------------------------ semântica

def _check_cenario(dados: Dict[str, Any], erros: List[str]) -> None:
    cenario = dados['cenario']
    talhoes = dados['talhoes']
    rotacoes = dados['rotacoes']
    soma_talhoes = sum(t['area_ha'] for t in talhoes.values())
    if soma_talhoes != cenario['area_total_ha']:
        erros.append(
            f"cenario: Σ área dos talhões ({soma_talhoes} ha) != "
            f"area_total_ha ({cenario['area_total_ha']} ha)"
        )
    if len(talhoes) != cenario['n_talhoes']:
        erros.append(f"cenario: n_talhoes ({cenario['n_talhoes']}) != {len(talhoes)} talhões definidos")
    if len(rotacoes) != cenario['n_rotacoes']:
        erros.append(f"cenario: n_rotacoes ({cenario['n_rotacoes']}) != {len(rotacoes)} rotações definidas")


def _check_rotacoes(dados: Dict[str, Any], erros: List[str], avisos: List[str]) -> None:
    for nome, rot in dados['rotacoes'].items():
        grupos_com_janela = sorted(int(g) for g, ds in rot['janelas_viveis_decendios'].items() if ds)
        if grupos_com_janela != sorted(rot['grupos_viveis']):
            erros.append(
                f'rotacoes.{nome}: grupos_viveis {sorted(rot["grupos_viveis"])} != '
                f'grupos com janela não vazia {grupos_com_janela}'
            )
        if abs(rot['margem_reais_por_ha'] - rot['margem_centavos_por_ha'] / 100) > TOL_REAIS:
            erros.append(
                f'rotacoes.{nome}: margem_reais_por_ha ({rot["margem_reais_por_ha"]}) != '
                f'margem_centavos_por_ha/100 ({rot["margem_centavos_por_ha"] / 100})'
            )
        percentis = rot.get('percentis')
        if percentis and not (
            percentis['p5'] <= percentis['p50'] <= percentis['p95']
        ):
            erros.append(
                f'rotacoes.{nome}: percentis fora de ordem '
                f"(p5={percentis['p5']} p50={percentis['p50']} p95={percentis['p95']})"
            )
        p_neg = rot.get('p_margem_negativa')
        if p_neg is not None and abs(rot['risco_por_mil'] / 1000 - p_neg) > 0.051:
            avisos.append(
                f'rotacoes.{nome}: risco_por_mil ({rot["risco_por_mil"]}‰) diverge de '
                f'p_margem_negativa ({p_neg:.1%}) — conferir com o M1'
            )


def _iterar_pontos(dados: Dict[str, Any]) -> Iterator[Tuple[str, Dict[str, Any]]]:
    yield 'plano_otimo', dados['plano_otimo']
    for i, ponto in enumerate(dados['fronteira_pareto']):
        yield f'fronteira_pareto[{i}]', ponto
    if dados.get('knee') is not None:
        yield 'knee', dados['knee']
    for perfil, ponto in dados['planos'].items():
        yield f'planos.{perfil}', ponto


def _check_pontos(dados: Dict[str, Any], erros: List[str]) -> None:
    talhoes = dados['talhoes']
    rotacoes = dados['rotacoes']
    area_total = dados['cenario']['area_total_ha']
    for onde, ponto in _iterar_pontos(dados):
        plano = ponto['plano_por_talhao']
        por_rotacao: Dict[str, int] = {}
        soma_geral = 0
        ref_quebrada = False
        for talhao, alocacao in plano.items():
            soma_talhao = sum(alocacao.values())
            if talhao not in talhoes:
                erros.append(f'{onde}: talhão {talhao!r} não existe em talhoes')
                ref_quebrada = True
                continue
            if soma_talhao != talhoes[talhao]['area_ha']:
                erros.append(
                    f'{onde}.{talhao}: Σ alocada ({soma_talhao} ha) != '
                    f'área do talhão ({talhoes[talhao]["area_ha"]} ha)'
                )
            for rotacao, ha in alocacao.items():
                if rotacao not in rotacoes:
                    erros.append(f'{onde}.{talhao}: rotação {rotacao!r} não existe em rotacoes')
                    ref_quebrada = True
                    continue
                por_rotacao[rotacao] = por_rotacao.get(rotacao, 0) + ha
            soma_geral += soma_talhao
        if ref_quebrada:
            continue
        if soma_geral != area_total:
            erros.append(f'{onde}: Σ geral alocada ({soma_geral} ha) != area_total_ha ({area_total} ha)')
        if por_rotacao != ponto['area_por_rotacao']:
            erros.append(
                f'{onde}: area_por_rotacao ({ponto["area_por_rotacao"]}) != '
                f'soma extraída do plano ({por_rotacao})'
            )
        if abs(ponto['margem_reais'] - ponto['margem_centavos'] / 100) > TOL_REAIS:
            erros.append(
                f'{onde}: margem_reais ({ponto["margem_reais"]}) != '
                f'margem_centavos/100 ({ponto["margem_centavos"] / 100})'
            )
        if abs(ponto['ha_sob_risco'] - ponto['risco_por_mil_ha'] / 1000) > TOL_HA_RISCO:
            erros.append(
                f'{onde}: ha_sob_risco ({ponto["ha_sob_risco"]}) != '
                f'risco_por_mil_ha/1000 ({ponto["risco_por_mil_ha"] / 1000})'
            )


def _check_menu(dados: Dict[str, Any], erros: List[str], avisos: List[str]) -> None:
    fronteira = dados['fronteira_pareto']
    knee = dados.get('knee')
    planos = dados['planos']
    if len(fronteira) < 3:
        avisos.append(
            f'fronteira_pareto tem só {len(fronteira)} ponto(s) — o gráfico da tela 2 '
            'fica pobre com menos de 3'
        )
    if fronteira:
        margem_max = max(p['margem_centavos'] for p in fronteira)
        risco_min = min(p['risco_por_mil_ha'] for p in fronteira)
        if planos['arrojado']['margem_centavos'] != margem_max:
            erros.append('planos.arrojado: margem não é a máxima da fronteira_pareto')
        if planos['conservador']['risco_por_mil_ha'] != risco_min:
            erros.append('planos.conservador: risco não é o mínimo da fronteira_pareto')
    if knee is not None:
        na_fronteira = any(
            p['margem_centavos'] == knee['margem_centavos']
            and p['risco_por_mil_ha'] == knee['risco_por_mil_ha']
            for p in fronteira
        )
        if not na_fronteira:
            erros.append('knee: margem/risco não correspondem a nenhum ponto da fronteira_pareto')
        for campo, esperado in (
            ('margem_centavos', knee['margem_centavos']),
            ('risco_por_mil_ha', knee['risco_por_mil_ha']),
        ):
            if planos['equilibrado'][campo] != esperado:
                erros.append(f'planos.equilibrado: {campo} não bate com o knee')


def _check_status_fontes(dados: Dict[str, Any], erros: List[str], avisos: List[str]) -> None:
    n_mock = sum(
        1
        for rot in dados['rotacoes'].values()
        for hip in rot.get('hipoteses', [])
        if str(hip.get('fonte_url', '')).startswith('MOCK://')
    )
    total = sum(len(rot.get('hipoteses', [])) for rot in dados['rotacoes'].values())
    status = dados['dados']['status']
    if status == 'REAL' and n_mock:
        erros.append(
            f"dados.status=REAL mas {n_mock}/{total} hipótese(s) com fonte_url 'MOCK://…' — "
            'troque pelas fontes oficiais antes de congelar'
        )
    elif n_mock:
        avisos.append(
            f'{n_mock}/{total} hipóteses com fonte MOCK:// (dados.status={status}) — '
            'trocar pelas fontes oficiais antes do congelamento'
        )


def validar_semantica(dados: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    erros: List[str] = []
    avisos: List[str] = []
    _check_cenario(dados, erros)
    _check_rotacoes(dados, erros, avisos)
    _check_pontos(dados, erros)
    _check_menu(dados, erros, avisos)
    _check_status_fontes(dados, erros, avisos)
    return erros, avisos


# ------------------------------------------------------------------------- CLI

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Validador do contrato results.json (M3 — HackatOhm 2026)',
        epilog=(
            'Exemplos:\n'
            '  python3 contract/validate.py engine/out/results_mock.json\n'
            '  python3 contract/validate.py --publish'
        ),
    )
    parser.add_argument(
        'arquivo', nargs='?', default=None,
        help='JSON a validar (default: contract/results.json)',
    )
    parser.add_argument(
        '--publish', action='store_true',
        help='valida engine/out/results_mock.json e publica em contract/results.json',
    )
    parser.add_argument(
        '--schema', default=str(SCHEMA_DEFAULT),
        help=f'caminho do schema (default: {SCHEMA_DEFAULT})',
    )
    args = parser.parse_args()

    origem = MOTOR_DEFAULT if args.publish else (
        Path(args.arquivo) if args.arquivo else CONTRATO_DEFAULT
    )
    schema_path = Path(args.schema)
    for caminho, rotulo in ((origem, 'arquivo'), (schema_path, 'schema')):
        if not caminho.exists():
            print(f'{rotulo.capitalize()} não encontrado: {caminho}', file=sys.stderr)
            raise SystemExit(2)

    try:
        dados = carregar_json(origem)
        schema = carregar_json(schema_path)
    except json.JSONDecodeError as exc:
        print(f'JSON inválido em {exc.filename}:{exc.lineno}: {exc.msg}', file=sys.stderr)
        raise SystemExit(1)

    erros = erros_de_forma(dados, schema)
    avisos: List[str] = []
    if not erros:
        erros_semantica, avisos = validar_semantica(dados)
        erros += erros_semantica

    print(f'Contrato: {origem}')
    print(f'Schema:   {schema_path}')
    print()
    for aviso in avisos:
        print(f'⚠  {aviso}')

    if erros:
        print(f'✖ {len(erros)} erro(s) no contrato:')
        for erro in erros:
            print(f'   - {erro}')
        raise SystemExit(1)

    if args.publish:
        CONTRATO_DEFAULT.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origem, CONTRATO_DEFAULT)
        print(f'✔ Válido — publicado: {origem} → {CONTRATO_DEFAULT}')
    else:
        print('✔ Válido')
    if avisos:
        print(f'({len(avisos)} aviso(s) — não bloqueiam)')


if __name__ == '__main__':
    main()
