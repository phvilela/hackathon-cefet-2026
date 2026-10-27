#!/usr/bin/env python3
"""Teste de aceitação da API /api/solve contra o contrato congelado.

Roda o motor vendorizado IN-PROCESS (sem HTTP) para o cenário PADRÃO
(T1 300ha/g2, T2 200ha/g1, T3 100ha/g3) e compara com contract/results.json:

  (a) os 7 pontos da fronteira: margem_centavos EXATO; ha_sob_risco e
      risco_por_mil_ha dentro de ±0,06;
  (b) knee == fronteira_pareto[4] (5º ponto) em margem_centavos;
  (c) planos.arrojado/equilibrado/conservador: area_por_rotacao EXATO;
  (d) plano_otimo.margem_centavos EXATO.

Uso: python3 web/api/test_acceptance.py   (exit 0 = PASS, exit 1 = FAIL)
"""
import json
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(API_DIR))

from solve import solve_scenario  # noqa: E402  (vendor engine roda por baixo)

CONTRACT_PATH = API_DIR.parents[1] / 'contract' / 'results.json'

TALHOES_PADRAO = {
    'T1': {'area_ha': 300, 'grupo_solo': 2},
    'T2': {'area_ha': 200, 'grupo_solo': 1},
    'T3': {'area_ha': 100, 'grupo_solo': 3},
}

TOLERANCIA = 0.06

falhas = 0


def check(rotulo: str, cond: bool, detalhe: str = '') -> None:
    global falhas
    if cond:
        print(f'[PASS] {rotulo}')
    else:
        falhas += 1
        print(f'[FAIL] {rotulo}' + (f' — {detalhe}' if detalhe else ''))


def main() -> int:
    print(f'Contrato: {CONTRACT_PATH}')
    resumo = ', '.join(
        '{} {}ha/g{}'.format(k, v['area_ha'], v['grupo_solo'])
        for k, v in TALHOES_PADRAO.items()
    )
    print(f'Rodando o motor vendorizado para o cenário padrão ({resumo})...')
    esperado = json.loads(CONTRACT_PATH.read_text(encoding='utf-8'))
    obtido = solve_scenario(TALHOES_PADRAO)

    # ------------------------------------------------------------------ (a) fronteira
    fe = esperado['fronteira_pareto']
    fo = obtido['fronteira_pareto']
    check(f'(a) fronteira tem {len(fe)} pontos como o contrato',
          len(fo) == len(fe), f'contrato={len(fe)} api={len(fo)}')
    for i, (pe, po) in enumerate(zip(fe, fo)):
        dm = abs(po['margem_centavos'] - pe['margem_centavos'])
        dr = abs(po['risco_por_mil_ha'] - pe['risco_por_mil_ha'])
        dh = abs(po['ha_sob_risco'] - pe['ha_sob_risco'])
        check(f'(a) fronteira[{i}].margem_centavos EXATO ({pe["margem_centavos"]})',
              dm == 0, f'contrato={pe["margem_centavos"]} api={po["margem_centavos"]}')
        check(f'(a) fronteira[{i}].risco_por_mil_ha ±{TOLERANCIA} ({pe["risco_por_mil_ha"]})',
              dr <= TOLERANCIA, f'|Δ|={dr}')
        check(f'(a) fronteira[{i}].ha_sob_risco ±{TOLERANCIA} ({pe["ha_sob_risco"]})',
              dh <= TOLERANCIA, f'|Δ|={dh}')

    # --------------------------------------------------------------------- (b) knee
    k = obtido['knee']
    p4 = fo[4]
    check('(b) knee == fronteira_pareto[4] em margem_centavos '
          f'({p4["margem_centavos"]})',
          k is not None and k['margem_centavos'] == p4['margem_centavos'],
          f'knee={k and k["margem_centavos"]} fronteira[4]={p4["margem_centavos"]}')

    # ------------------------------------------------------------------- (c) planos
    for perfil in ('arrojado', 'equilibrado', 'conservador'):
        apr_e = esperado['planos'][perfil]['area_por_rotacao']
        apr_o = obtido['planos'][perfil]['area_por_rotacao']
        check(f'(c) planos.{perfil}.area_por_rotacao EXATO {apr_o}',
              apr_o == apr_e, f'contrato={apr_e} api={apr_o}')

    # -------------------------------------------------------------- (d) plano ótimo
    m_e = esperado['plano_otimo']['margem_centavos']
    m_o = obtido['plano_otimo']['margem_centavos']
    check(f'(d) plano_otimo.margem_centavos EXATO ({m_e})',
          m_o == m_e, f'contrato={m_e} api={m_o}')

    check("extras) dados.status == 'REAL' e sem caminhos internos na observacao",
          obtido['dados']['status'] == 'REAL' and 'engine/' not in obtido['dados']['observacao'],
          repr(obtido['dados']['observacao']))

    print()
    if falhas:
        print(f'RESULTADO: FAIL — {falhas} asserção(ões) falharam')
        return 1
    print('RESULTADO: PASS — todos os cenários batem com o contrato congelado')
    return 0


if __name__ == '__main__':
    sys.exit(main())
