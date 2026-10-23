"""Fronteira de Pareto margem × risco via ε-constraint.

Para cada piso de margem (de 100% do ótimo até `min_margem_ratio` × ótimo):
    `Minimize(risco)  s.t.  margem >= piso`
Depois remove dominados (`_filter_nondominated`) e acha o knee point
(maior distância perpendicular à reta entre os extremos), que vira o
perfil "Equilibrado" do pitch.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import tqdm
from ortools.sat.python import cp_model

from .model import build_model
from .solver import FEASIBLE_STATUS, extract_plano, solve_lexicographic

logger = logging.getLogger(__name__)

DEFAULT_POINTS = 6
DEFAULT_MIN_MARGEM_RATIO = 0.85
DEFAULT_TIME_LIMIT = 10.0


def _plano_signature(plano: Dict[str, Dict[str, int]]) -> tuple:
    """Assinatura única de um plano (p/ descartar duplicados entre pisos)."""
    return tuple(sorted((t, r, a) for t, alocacao in plano.items() for r, a in alocacao.items()))


def _dominates(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """a domina b: margem >= (maior é melhor) e risco <= (menor é melhor), com estriteza."""
    return (
        a['margem'] >= b['margem'] and a['risco'] <= b['risco']
        and (a['margem'] > b['margem'] or a['risco'] < b['risco'])
    )


def _filter_nondominated(points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove pontos dominados; ordena por margem decrescente (índice 0 = Arrojado)."""
    nondominated: List[Dict[str, Any]] = []
    for p in points:
        if any(q is not p and _dominates(q, p) for q in points):
            continue
        nondominated.append(p)
    nondominated.sort(key=lambda p: (-p['margem'], p['risco']))
    return nondominated


def solve_pareto_point(config: Dict[str, Any],
                        margem_floor: Optional[int] = None,
                        time_limit: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """Um ponto da fronteira: minimiza risco sujeito a `margem >= piso` (ε-constraint)."""
    model, x, meta, components = build_model(config)

    if margem_floor is not None:
        model.Add(components['margem'] >= int(margem_floor))
    model.Minimize(components['risco'])

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = float(
        time_limit if time_limit is not None else DEFAULT_TIME_LIMIT
    )

    status = solver.Solve(model)
    if status not in FEASIBLE_STATUS:
        logger.debug('Piso de margem %s inviável (%s)', margem_floor, solver.StatusName(status))
        return None

    base = extract_plano(solver, x, meta)
    return {
        'margem': int(round(solver.Value(components['margem']))),   # centavos
        'risco': int(round(solver.Value(components['risco']))),     # ‰·ha
        'margem_floor': int(margem_floor) if margem_floor is not None else None,
        'plano': base['plano'],
        'area_por_rotacao': base['area_por_rotacao'],
        'margem_por_talhao': base['margem_por_talhao'],
        'risco_por_talhao': base['risco_por_talhao'],
        'status_name': solver.StatusName(status),
        'meta': meta,
    }


def generate_pareto_frontier(config: Dict[str, Any],
                             points: Optional[int] = None,
                             min_margem_ratio: Optional[float] = None,
                             time_limit: Optional[float] = None,
                             quiet: bool = False) -> List[Dict[str, Any]]:
    """Gera a fronteira: varre pisos de margem de best até best×ratio.

    Cada ponto guarda o `plano` correspondente. Retorna pontos não-dominados
    ordenados por margem decrescente.
    """
    pareto_cfg = config.get('pareto', {}) or {}
    if points is None:
        points = int(pareto_cfg.get('points', DEFAULT_POINTS))
    if min_margem_ratio is None:
        min_margem_ratio = float(pareto_cfg.get('min_margem_ratio', DEFAULT_MIN_MARGEM_RATIO))
    points = max(2, int(points))

    logger.info('Calculando baseline (lexicográfico) para a fronteira')
    baseline = solve_lexicographic(config, time_limit=time_limit)
    if baseline is None or not baseline.get('stage_results'):
        logger.error('Baseline falhou — impossível gerar a fronteira de Pareto')
        return []

    best = int(baseline['stage_results'][0]['value'])  # ótimo do estágio margem
    min_margem = max(0, int(best * float(min_margem_ratio)))
    logger.info('Faixa de margem: %d a %d centavos (%d pontos)', best, min_margem, points)

    span = best - min_margem
    if span <= 0:
        floors = [best]
    else:
        floors = [int(round(best - (span * i) / (points - 1))) for i in range(points)]
    floors = sorted(set(floors), reverse=True)

    raw_points: List[Dict[str, Any]] = []
    for floor in tqdm.tqdm(floors, desc='Pontos de Pareto', disable=quiet):
        point = solve_pareto_point(config, margem_floor=floor, time_limit=time_limit)
        if point is not None:
            raw_points.append(point)

    # pisos distintos podem gerar o mesmo plano — fica só o primeiro
    seen: set = set()
    unique: List[Dict[str, Any]] = []
    for point in raw_points:
        signature = _plano_signature(point['plano'])
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(point)

    frontier = _filter_nondominated(unique)
    logger.info('Fronteira de Pareto: %d pontos não-dominados', len(frontier))
    return frontier


def find_knee_point(frontier: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Knee point: ponto de maior distância à reta entre os extremos.

    Algoritmo: maior distância perpendicular entre o ponto e a reta que liga
    os extremos, com x = risco (menor é melhor) e y = margem (maior é melhor).
    É o perfil "Equilibrado" — o melhor trade-off margem × risco.
    """
    if not frontier:
        return None
    if len(frontier) <= 2:
        return frontier[-1]

    margem_vals = [float(p['margem']) for p in frontier]
    risco_vals = [float(p['risco']) for p in frontier]
    m_min, m_max = min(margem_vals), max(margem_vals)
    k_min, k_max = min(risco_vals), max(risco_vals)
    m_range = (m_max - m_min) or 1.0
    k_range = (k_max - k_min) or 1.0

    first, last = frontier[0], frontier[-1]
    x1 = (float(first['risco']) - k_min) / k_range
    y1 = (float(first['margem']) - m_min) / m_range
    x2 = (float(last['risco']) - k_min) / k_range
    y2 = (float(last['margem']) - m_min) / m_range

    line_len = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    if line_len < 1e-9:
        return frontier[len(frontier) // 2]

    max_dist = -1.0
    knee = frontier[0]
    for point in frontier:
        x0 = (float(point['risco']) - k_min) / k_range
        y0 = (float(point['margem']) - m_min) / m_range
        dist = abs((y2 - y1) * x0 - (x2 - x1) * y0 + x2 * y1 - y2 * x1) / line_len
        if dist > max_dist:
            max_dist = dist
            knee = point

    logger.debug('Knee no índice %d (distância normalizada %.4f)',
                 frontier.index(knee), max_dist)
    return knee
