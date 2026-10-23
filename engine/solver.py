"""Solver lexicográfico do motor "o que plantar".

Estágio 1: `Maximize(margem)` → congela o ótimo com `model.Add(margem == valor)`
Estágio 2: `Minimize(risco)`

Tudo em inteiro: margem em centavos, risco em ‰·ha — nunca float no objetivo.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ortools.sat.python import cp_model

from .model import build_model

logger = logging.getLogger(__name__)

FEASIBLE_STATUS = {cp_model.OPTIMAL, cp_model.FEASIBLE}

STAGE_DIRECTIONS = {'margem': 'max', 'risco': 'min'}

DEFAULT_STAGE_TIME_LIMIT = 10.0


def extract_plano(solver: cp_model.CpSolver,
                  x: Dict[tuple, cp_model.IntVar],
                  meta: Dict[str, Any]) -> Dict[str, Any]:
    """Extrai o plano (áreas por rotação × talhão) de um modelo resolvido."""
    talhoes = meta['talhoes']
    rotacoes = meta['rotacoes']

    plano: Dict[str, Dict[str, int]] = {t: {} for t in talhoes}
    area_por_rotacao: Dict[str, int] = {r: 0 for r in rotacoes}
    margem_por_talhao: Dict[str, int] = {t: 0 for t in talhoes}
    risco_por_talhao: Dict[str, int] = {t: 0 for t in talhoes}
    margem_total = 0
    risco_total = 0

    for (r, t), var in x.items():
        area = int(solver.Value(var))
        if area <= 0:
            continue
        plano[t][r] = area
        area_por_rotacao[r] += area
        margem_t = rotacoes[r]['margem'] * area
        risco_t = rotacoes[r]['risco'] * area
        margem_por_talhao[t] += margem_t
        risco_por_talhao[t] += risco_t
        margem_total += margem_t
        risco_total += risco_t

    return {
        'plano': plano,
        'area_por_rotacao': {r: a for r, a in area_por_rotacao.items() if a > 0},
        'margem_total': margem_total,
        'risco_total': risco_total,
        'margem_por_talhao': margem_por_talhao,
        'risco_por_talhao': risco_por_talhao,
    }


def build_solution_dict(solver: cp_model.CpSolver,
                        x: Dict[tuple, cp_model.IntVar],
                        meta: Dict[str, Any],
                        stage_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Monta o dict de solução: plano, margem_total, risco_total, estágios etc."""
    solution = extract_plano(solver, x, meta)
    solution.update({
        'status': stage_results[-1]['status'] if stage_results else None,
        'status_name': stage_results[-1]['status_name'] if stage_results else 'UNKNOWN',
        'stage_results': stage_results,
        'meta': meta,
    })
    return solution


def solve_lexicographic(config: Dict[str, Any],
                        time_limit: Optional[float] = None,
                        stages: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """Resolve o problema em estágios lexicográficos (1º máx margem, 2º mín risco).

    Retorna dict com `plano` (áreas por rotação × talhão), `margem_total`
    (centavos), `risco_total` (‰·ha), `stage_results` e `status_name`,
    ou `None` se inviável.
    """
    model, x, meta, components = build_model(config)

    opt_cfg = meta.get('optimization', {}) or {}
    if stages is None:
        stages = [str(s) for s in opt_cfg.get('stages', ['margem', 'risco'])]
    if not stages:
        stages = ['margem']

    if time_limit is None:
        time_limit = DEFAULT_STAGE_TIME_LIMIT
    per_stage_limit = max(0.5, float(time_limit) / len(stages))

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1  # determinismo p/ Monte Carlo
    stage_results: List[Dict[str, Any]] = []

    for stage_name in stages:
        if stage_name not in components:
            logger.warning('Estágio %s não existe nos componentes — ignorado', stage_name)
            continue

        expr = components[stage_name]
        direction = STAGE_DIRECTIONS.get(stage_name, 'min')

        if direction == 'max':
            model.Maximize(expr)
        else:
            model.Minimize(expr)

        solver.parameters.max_time_in_seconds = per_stage_limit
        status = solver.Solve(model)

        if status not in FEASIBLE_STATUS:
            logger.error('Estágio %s falhou com status %s', stage_name, solver.StatusName(status))
            return None

        value = int(round(solver.Value(expr)))
        logger.debug('Estágio %s (%s): valor=%d', stage_name, direction, value)
        stage_results.append({
            'stage': stage_name,
            'direction': direction,
            'value': value,
            'status': status,
            'status_name': solver.StatusName(status),
        })

        # congela o ótimo do estágio antes de otimizar o próximo
        model.Add(expr == value)

    if not stage_results:
        logger.error('Nenhum estágio produziu resultado')
        return None

    return build_solution_dict(solver, x, meta, stage_results)
