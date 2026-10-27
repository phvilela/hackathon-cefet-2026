"""API serverless de decisão "o que plantar" (FastAPI — Vercel, Root Directory=web).

Reimplementa a orquestração de engine/main.py sem importá-la (main.py puxa
matplotlib via visualization.py):
    validate_config → solve_lexicográfico → fronteira de Pareto (ε-constraint)
    → knee point → ponto de mínimo risco (custo de oportunidade) →
    Monte Carlo de robustez → results JSON (contract/results.json).

O motor é o CÓPIA vendorizada em web/api/engine/ (congelada — ressincronice com
scripts/sync_web_api_engine.sh quando engine/ mudar). O config congelado
(config.yaml) é self-contained: janelas ZARC e margens MC já estão inlinadas
nele; janelas_zarc.json/margens_mc.json são vendored apenas como proveniência
(nenhum código vendorizado lê arquivos externos — nada para re-caminhar).
"""
from __future__ import annotations

import copy
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import yaml
from fastapi import Body, FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

# sys.path RELATIVO A ESTE ARQUIVO (não ao cwd — no Vercel o cwd não é web/api)
API_DIR = Path(__file__).resolve().parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from engine.pareto import (  # noqa: E402
    _filter_nondominated,
    find_knee_point,
    generate_pareto_frontier,
    solve_pareto_point,
)
from engine.report import build_results  # noqa: E402
from engine.robustness import run_monte_carlo_robustness  # noqa: E402
from engine.solver import solve_lexicographic  # noqa: E402
from engine.validation import ConfigValidationError, validate_config  # noqa: E402

CONFIG_PATH = API_DIR / 'engine' / 'config.yaml'

GRUPOS_SOLO_VALIDOS = (1, 2, 3)

# texto exibido pelo frontend — PT-BR, sem caminhos internos
OBSERVACAO_REAL = (
    'Janelas de plantio reais (ZARC 2026/27) e margens estimadas por Monte Carlo '
    'sobre referências SIDRA/Conab. Este cenário foi recalculado em tempo real '
    'pelo motor de decisão (CP-SAT).'
)
ENGINE_DESCRICAO = (
    'Motor CP-SAT inteiro — lexicográfico margem→risco, fronteira ε-constraint '
    'com knee (Equilibrado) e Monte Carlo de robustez'
)


def _load_base_config() -> dict:
    """Carrega e normaliza o config congelado (mesma normalização de main.load_config)."""
    with CONFIG_PATH.open('r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    if config is None:
        raise RuntimeError(f'Arquivo de config vazio: {CONFIG_PATH.name}')

    for info in (config.get('talhoes') or {}).values():
        info['area_ha'] = int(info['area_ha'])
        info['grupo_solo'] = int(info['grupo_solo'])
    for info in (config.get('rotacoes') or {}).values():
        info['margem_esperada'] = int(info['margem_esperada'])
        info['risco'] = int(info['risco'])
        info['janelas_viveis'] = {
            int(grupo): [int(d) for d in decendios]
            for grupo, decendios in (info.get('janelas_viveis') or {}).items()
        }
    optimization = config.get('optimization') or {}
    if 'stages' in optimization:
        optimization['stages'] = [str(s) for s in optimization['stages']]
    return config


@lru_cache(maxsize=1)
def base_config() -> dict:
    """Config congelado carregado UMA vez por processo (cold start do Vercel)."""
    return _load_base_config()


def _config_com_talhoes(talhoes: Dict[str, Dict[str, int]]) -> dict:
    """Deep-cópia do config base com os talhões do usuário no lugar."""
    config = copy.deepcopy(base_config())
    config['talhoes'] = {
        nome: {
            'area_ha': int(info['area_ha']),
            'grupo_solo': int(info['grupo_solo']),
            'irrigacao': False,
        }
        for nome, info in talhoes.items()
    }
    config['cenario']['area_total_ha'] = sum(t['area_ha'] for t in config['talhoes'].values())
    return config


def solve_scenario(talhoes: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
    """Mesmo fluxo de engine/main.py --pareto --monte-carlo → dict results.

    `talhoes`: {id: {'area_ha': int, 'grupo_solo': int}}. Levanta
    ConfigValidationError (entrada inválida) ou RuntimeError (solver falhou).
    """
    config = _config_com_talhoes(talhoes)
    validate_config(config)

    solution = solve_lexicographic(config)
    if solution is None:
        raise RuntimeError('Nenhuma solução viável para os talhões informados.')

    # fronteira de Pareto (ε-constraint) + knee, como em main.py com --pareto
    frontier: List[Dict[str, Any]] = []
    knee = None
    if str((config.get('optimization') or {}).get('mode', 'lexicographic')).lower() == 'pareto':
        frontier = generate_pareto_frontier(config, quiet=True)
        knee = find_knee_point(frontier) if frontier else None

        # ponto de MÍNIMO risco absoluto (custo de oportunidade = capital_pousio)
        ponto_min_risco = solve_pareto_point(config)
        if ponto_min_risco is not None:
            ja_existe = any(p['margem'] == ponto_min_risco['margem']
                            and p['risco'] == ponto_min_risco['risco']
                            for p in frontier)
            if not ja_existe:
                ponto_min_risco['referencia'] = 'custo_oportunidade'
                frontier = _filter_nondominated(frontier + [ponto_min_risco])

    # robustez ao vivo: ±10% nas margens, 30 runs, seed 42 (do config congelado)
    mc = run_monte_carlo_robustness(config, baseline_solution=solution, quiet=True)

    results = build_results(config, solution, frontier=frontier, knee=knee, mc=mc)

    # status honesto + texto amigável p/ o usuário final (sem caminhos internos)
    results['dados']['status'] = 'REAL'
    results['dados']['observacao'] = OBSERVACAO_REAL
    results['dados']['engine'] = ENGINE_DESCRICAO
    return results


# --------------------------------------------------------------------- API models

class TalhaoIn(BaseModel):
    id: str = Field(min_length=1, description='Identificador do talhão (ex.: T1)')
    area_ha: int = Field(description='Área do talhão em hectares')
    grupo_solo: int = Field(description='Grupo de solo ZARC: 1, 2 ou 3')

    @field_validator('area_ha')
    @classmethod
    def _area_positiva(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('area_ha deve ser > 0')
        return v

    @field_validator('grupo_solo')
    @classmethod
    def _grupo_valido(cls, v: int) -> int:
        if v not in GRUPOS_SOLO_VALIDOS:
            raise ValueError(f'grupo_solo deve ser um de {list(GRUPOS_SOLO_VALIDOS)}')
        return v


class SolveRequest(BaseModel):
    talhoes: List[TalhaoIn]

    @field_validator('talhoes')
    @classmethod
    def _pelo_menos_um_e_ids_unicos(cls, v: List[TalhaoIn]) -> List[TalhaoIn]:
        if not v:
            raise ValueError('informe ao menos um talhão')
        ids = [t.id for t in v]
        if len(set(ids)) != len(ids):
            raise ValueError('ids de talhão duplicados')
        return v


app = FastAPI(
    title='API de decisão "o que plantar"',
    description='Recalcula o plano de plantio (CP-SAT + Pareto + robustez) para cenários editados.',
    version='1.0.0',
)


@app.get('/api/health')
def health() -> Dict[str, str]:
    """Warm-up ping do Vercel (mantém a função aquecida)."""
    return {'status': 'ok'}


@app.post('/api/solve')
def solve(payload: SolveRequest = Body(...)) -> Dict[str, Any]:
    """Resolve o cenário e devolve o JSON no formato de contract/results.json."""
    talhoes = {t.id: {'area_ha': t.area_ha, 'grupo_solo': t.grupo_solo}
               for t in payload.talhoes}
    try:
        return solve_scenario(talhoes)
    except ConfigValidationError as exc:
        # entrada do usuário inválida para o motor (ex.: talhão sem rotação viável)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Erro ao resolver o cenário: {exc}') from exc
