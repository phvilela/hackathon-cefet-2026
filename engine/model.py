"""Modelo CP-SAT do motor "o que plantar" (HackatOhm 2026 — desafio Embrapa).

Variável de decisão:
    x[(rotacao, talhao)] = área plantada da rotação no talhão (ha, inteira)

Restrições:
    por talhão: Σ_rotações x == área do talhão
    rotações SEM janela viável no grupo de solo do talhão ficam com upper
    bound 0 (a máscara de 36 decêndios do ZARC entra aqui, aplicada por
    grupo de solo).

Unidades (CP-SAT só tem inteiros — nunca float no objetivo):
    margem em centavos de R$ por hectare (R$ 4.180/ha → 418000)
    risco em por-mil (P[margem < 0] = 12% → 120); risco_total em ‰·ha
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from ortools.sat.python import cp_model

logger = logging.getLogger(__name__)


def janelas_do_grupo(rot_info: Dict[str, Any], grupo: int) -> List[int]:
    """Decêndios viáveis da rotação no grupo de solo dado (pode ser lista vazia)."""
    janelas = (rot_info.get('janelas_viveis') or {}).get(int(grupo)) or []
    return [int(d) for d in janelas]


def rotacao_vivel_em_grupo(rot_info: Dict[str, Any], grupo: int) -> bool:
    """Rotação é plantável no grupo de solo se houver ao menos 1 decêndio viável."""
    return len(janelas_do_grupo(rot_info, grupo)) > 0


def rotacoes_viveis_no_grupo(rotacoes: Dict[str, Any], grupo: int) -> List[str]:
    """Nomes das rotações com janela não vazia no grupo de solo dado."""
    return [nome for nome, info in rotacoes.items() if rotacao_vivel_em_grupo(info, grupo)]


def build_model(config: Dict[str, Any]) -> Tuple[
    cp_model.CpModel,
    Dict[Tuple[str, str], cp_model.IntVar],
    Dict[str, Any],
    Dict[str, Any],
]:
    """Constrói o modelo de alocação de áreas por rotação × talhão.

    Retorna `(model, x, meta, components)` no espírito do `src/model.py`
    original, com:
        components['margem'] = Σ margem_r · x   (centavos — maximizar)
        components['risco']  = Σ risco_r · x    (‰·ha — minimizar)
    """
    talhoes_cfg = config['talhoes']
    rotacoes_cfg = config['rotacoes']

    talhoes = {
        nome: {'area_ha': int(info['area_ha']), 'grupo_solo': int(info['grupo_solo'])}
        for nome, info in talhoes_cfg.items()
    }
    rotacoes = {
        nome: {
            'margem': int(info['margem_esperada']),
            'risco': int(info['risco']),
            'janelas_viveis': {
                int(g): [int(d) for d in decendios]
                for g, decendios in (info.get('janelas_viveis') or {}).items()
            },
        }
        for nome, info in rotacoes_cfg.items()
    }

    model = cp_model.CpModel()
    x: Dict[Tuple[str, str], cp_model.IntVar] = {}

    for t_nome, t_info in talhoes.items():
        area_t = t_info['area_ha']
        grupo = t_info['grupo_solo']
        for r_nome, r_info in rotacoes.items():
            # só pode plantar rotação com janela viável no grupo do talhão
            vivel = rotacao_vivel_em_grupo(r_info, grupo)
            ub = area_t if vivel else 0
            x[(r_nome, t_nome)] = model.NewIntVar(0, ub, f'x_{r_nome}_{t_nome}')
        # a área do talhão é toda alocada (Σ_rotações x == área)
        model.Add(sum(x[(r, t_nome)] for r in rotacoes) == area_t)

    margem_expr = sum(rotacoes[r]['margem'] * x[(r, t)] for (r, t) in x)
    risco_expr = sum(rotacoes[r]['risco'] * x[(r, t)] for (r, t) in x)

    components = {
        'margem': margem_expr,  # centavos
        'risco': risco_expr,    # ‰·ha
    }

    meta = {
        'talhoes': talhoes,
        'rotacoes': rotacoes,
        'viveis_por_talhao': {
            t: rotacoes_viveis_no_grupo(rotacoes_cfg, info['grupo_solo'])
            for t, info in talhoes.items()
        },
        'grupos_viveis_por_rotacao': {
            r: sorted(g for g, ds in rotacoes[r]['janelas_viveis'].items() if ds)
            for r in rotacoes
        },
        'area_total_ha': sum(t['area_ha'] for t in talhoes.values()),
        'optimization': config.get('optimization', {}) or {},
        'pareto': config.get('pareto', {}) or {},
    }

    n_viveis = sum(len(v) for v in meta['viveis_por_talhao'].values())
    logger.debug(
        'Modelo: %d talhões, %d rotações, %d variáveis (%d pares viáveis)',
        len(talhoes), len(rotacoes), len(x), n_viveis,
    )

    return model, x, meta, components
