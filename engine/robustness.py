"""Monte Carlo de robustez da RECOMENDAÇÃO (padrão do robustness.py original).

Perturba os COEFICIENTES (margens — onde os custos já estão embutidos) com
multiplicador U[1−j/100, 1+j/100] e re-resolve o lexicográfico, medindo
quanto o PLANO muda. É a camada complementar ao MC do M1: o do M1 gera as
margens por rotação; este mede a estabilidade da alocação recomendada.
"""
from __future__ import annotations

import logging
from collections import Counter
from copy import deepcopy
from random import Random
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional

import tqdm

from .solver import solve_lexicographic

logger = logging.getLogger(__name__)

DEFAULT_RUNS = 30
DEFAULT_JITTER = 10
DEFAULT_SEED = 42
DEFAULT_TIME_LIMIT = 10.0


def _perturb_config(config: Dict[str, Any],
                    rng: Random,
                    jitter_percent: int) -> Dict[str, Any]:
    """Multiplica cada margem por U[1−j/100, 1+j/100] (custos embutidos na margem)."""
    perturbed = deepcopy(config)
    lo = 1.0 - jitter_percent / 100.0
    hi = 1.0 + jitter_percent / 100.0
    for info in perturbed['rotacoes'].values():
        base = int(info['margem_esperada'])
        info['margem_esperada'] = int(round(base * rng.uniform(lo, hi)))
    return perturbed


def comparar_planos(plano_base: Dict[str, Dict[str, int]],
                   plano_outro: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
    """Compara dois planos {talhao: {rotacao: ha}}: talhões e pares que mudaram."""
    talhoes = sorted(set(plano_base) | set(plano_outro))
    mudados: List[str] = []
    pares_mudados = 0
    for t in talhoes:
        aloc_a = plano_base.get(t, {})
        aloc_b = plano_outro.get(t, {})
        if aloc_a == aloc_b:
            continue
        mudados.append(t)
        for r in set(aloc_a) | set(aloc_b):
            if aloc_a.get(r, 0) != aloc_b.get(r, 0):
                pares_mudados += 1
    return {
        'talhoes_mudados': mudados,
        'n_talhoes_mudados': len(mudados),
        'pares_mudados': pares_mudados,
    }


def run_monte_carlo_robustness(config: Dict[str, Any],
                               runs: Optional[int] = None,
                               jitter: Optional[int] = None,
                               seed: Optional[int] = None,
                               baseline_solution: Optional[Dict[str, Any]] = None,
                               time_limit: Optional[float] = None,
                               quiet: bool = False) -> Dict[str, Any]:
    """Robustez da recomendação sob ±`jitter`% nas margens.

    `runs`/`jitter`/`seed` default para os valores do `config.yaml`
    (30 runs, ±10%, seed 42). Retorna estabilidade, mudanças por cenário,
    retenção por rotação e a frase pronta para o pitch.
    """
    mc_cfg = config.get('monte_carlo', {}) or {}
    if runs is None:
        runs = int(mc_cfg.get('runs', DEFAULT_RUNS))
    if jitter is None:
        jitter = int(mc_cfg.get('margem_jitter_percent', DEFAULT_JITTER))
    if seed is None:
        seed = mc_cfg.get('seed', DEFAULT_SEED)
    if time_limit is None:
        time_limit = DEFAULT_TIME_LIMIT
    runs, jitter = int(runs), int(jitter)

    n_talhoes = len(config['talhoes'])
    rotacoes = list(config['rotacoes'].keys())
    settings = {'runs': runs, 'jitter_percent': jitter, 'seed': seed}

    if baseline_solution is None:
        logger.info('Calculando solução baseline para o Monte Carlo')
        baseline_solution = solve_lexicographic(config)
    if baseline_solution is None:
        logger.error('Baseline falhou — Monte Carlo não pode prosseguir')
        return {
            'settings': settings,
            'successful_runs': 0,
            'failed_runs': runs,
            'stability_mean': 0.0,
            'stability_min': 0.0,
            'stability_max': 0.0,
            'changed_counts': [],
            'changed_distribution': {},
            'pairs_changed_mean': 0.0,
            'max_talhoes_mudados': 0,
            'pct_runs_sem_mudanca': 0.0,
            'margem_total_media_centavos': 0,
            'margem_total_min_centavos': 0,
            'margem_total_max_centavos': 0,
            'margem_total_std_centavos': 0.0,
            'retention_por_rotacao': {
                r: {'presente_no_baseline': False, 'runs_presente': 0,
                    'fracao_runs': 0.0, 'area_media_ha': 0.0}
                for r in rotacoes
            },
            'frase_estabilidade': 'Monte Carlo indisponível: sem solução baseline viável.',
        }

    baseline_plano = baseline_solution['plano']
    baseline_presenca = {
        r: any(r in alocacao for alocacao in baseline_plano.values()) for r in rotacoes
    }

    # seeds derivados de uma seed mestra → reprodutível (mesmo padrão do original)
    master_rng = Random(seed)
    run_seeds = [master_rng.randint(0, 2 ** 31) for _ in range(runs)]

    changed_counts: List[int] = []
    pairs_changed_counts: List[int] = []
    stabilities: List[float] = []
    margens: List[int] = []
    presencas: Dict[str, int] = {r: 0 for r in rotacoes}
    areas_acumuladas: Dict[str, List[int]] = {r: [] for r in rotacoes}
    successful = 0
    failed = 0

    for run_seed in tqdm.tqdm(run_seeds, desc='Monte Carlo', disable=quiet):
        rng = Random(run_seed)
        perturbed = _perturb_config(config, rng, jitter)
        solucao = solve_lexicographic(perturbed, time_limit=time_limit)
        if solucao is None:
            failed += 1
            continue
        successful += 1

        comparacao = comparar_planos(baseline_plano, solucao['plano'])
        changed_counts.append(int(comparacao['n_talhoes_mudados']))
        pairs_changed_counts.append(int(comparacao['pares_mudados']))
        stabilities.append(1.0 - comparacao['n_talhoes_mudados'] / max(1, n_talhoes))
        margens.append(int(solucao['margem_total']))

        for rotacao, area in solucao['area_por_rotacao'].items():
            presencas[rotacao] += 1
            areas_acumuladas[rotacao].append(int(area))

    distribuicao = Counter(changed_counts)
    max_changed = max(changed_counts) if changed_counts else 0
    cobertura = (
        100.0 * sum(1 for c in changed_counts if c <= max_changed) / successful
        if successful else 0.0
    )

    retention: Dict[str, Dict[str, Any]] = {}
    for rotacao in rotacoes:
        presente_runs = int(presencas[rotacao])
        retention[rotacao] = {
            'presente_no_baseline': baseline_presenca[rotacao],
            'runs_presente': presente_runs,
            'fracao_runs': (presente_runs / successful) if successful else 0.0,
            'area_media_ha': (
                float(mean(areas_acumuladas[rotacao])) if areas_acumuladas[rotacao] else 0.0
            ),
        }

    # frase pronta para o pitch
    if successful == 0:
        frase = 'Monte Carlo indisponível: nenhum cenário foi resolvido com sucesso.'
    else:
        palavra = 'talhão' if max_changed == 1 else 'talhões'
        frase = (
            f'A alocação muda em no máximo {max_changed} {palavra} em '
            f'{cobertura:.0f}% dos cenários de ±{jitter}% em preço/custo.'
        )

    logger.info('Monte Carlo: %d/%d cenários resolvidos — %s',
                successful, runs, frase)

    return {
        'settings': settings,
        'successful_runs': successful,
        'failed_runs': failed,
        'success_rate': (successful / runs) if runs else 0.0,
        'stability_mean': float(mean(stabilities)) if stabilities else 0.0,
        'stability_min': float(min(stabilities)) if stabilities else 0.0,
        'stability_max': float(max(stabilities)) if stabilities else 0.0,
        'changed_counts': changed_counts,  # nº de talhões mudados, por run
        'changed_distribution': {str(k): int(v) for k, v in sorted(distribuicao.items())},
        'pairs_changed_mean': float(mean(pairs_changed_counts)) if pairs_changed_counts else 0.0,
        'max_talhoes_mudados': int(max_changed),
        'pct_runs_sem_mudanca': (
            100.0 * distribuicao.get(0, 0) / successful if successful else 0.0
        ),
        'margem_total_media_centavos': int(mean(margens)) if margens else 0,
        'margem_total_min_centavos': int(min(margens)) if margens else 0,
        'margem_total_max_centavos': int(max(margens)) if margens else 0,
        'margem_total_std_centavos': float(pstdev(margens)) if len(margens) > 1 else 0.0,
        'retention_por_rotacao': retention,
        'frase_estabilidade': frase,
    }
