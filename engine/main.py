#!/usr/bin/env python3
"""CLI do motor de decisão "o que plantar" (HackatOhm 2026 — desafio Embrapa).

Uso (na raiz do repo):
    python3 engine/main.py --pareto --monte-carlo

Orquestra: validate → solve (lexicográfico) → fronteira de Pareto (ε-constraint
+ knee) → Monte Carlo de robustez → relatório txt + results JSON + PNG.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml

from engine.pareto import find_knee_point, generate_pareto_frontier
from engine.report import build_results, generate_report
from engine.robustness import run_monte_carlo_robustness
from engine.solver import solve_lexicographic
from engine.validation import ConfigValidationError, validate_config
from engine.visualization import generate_pareto_frontier_scatter

logger = logging.getLogger('engine')


def load_config(path: Path) -> dict:
    """Carrega e normaliza levemente o YAML (papel do data_loader original)."""
    with path.open('r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    if config is None:
        raise ValueError(f'Arquivo de config vazio: {path}')

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
    logger.info('Config carregado de %s', path)
    return config


def _setup_logging(quiet: bool, verbose: bool) -> None:
    level = logging.WARNING if quiet else (logging.DEBUG if verbose else logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stderr,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Motor de decisão "o que plantar" — CP-SAT (HackatOhm 2026, desafio Embrapa)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Exemplos:\n'
            '  python3 engine/main.py --pareto --monte-carlo\n'
            '  python3 engine/main.py --config engine/config.yaml --output-dir engine/out\n'
            '  python3 engine/main.py --pareto --pareto-points 8 --monte-carlo --mc-runs 50\n'
        ),
    )
    parser.add_argument('--config', default='engine/config.yaml',
                        help='caminho do config YAML (default: engine/config.yaml)')
    parser.add_argument('--pareto', action='store_true',
                        help='gera a fronteira de Pareto (ε-constraint + knee)')
    parser.add_argument('--monte-carlo', action='store_true',
                        help='roda o Monte Carlo de robustez (±10%% nas margens)')
    parser.add_argument('--output-dir', default='engine/out',
                        help='diretório de saída (default: engine/out)')
    parser.add_argument('--pareto-points', type=int, default=None,
                        help='nº de pontos da fronteira (default: config, 6)')
    parser.add_argument('--min-margem-ratio', type=float, default=None,
                        help='piso de margem como fração do ótimo (default: config, 0.85)')
    parser.add_argument('--mc-runs', type=int, default=None,
                        help='nº de cenários do Monte Carlo (default: config, 30)')
    parser.add_argument('--mc-jitter', type=int, default=None,
                        help='perturbação ±%% nas margens (default: config, 10)')
    parser.add_argument('--mc-seed', type=int, default=None,
                        help='seed do Monte Carlo (default: config, 42)')
    parser.add_argument('--quiet', action='store_true', help='suprime mensagens e barras')
    parser.add_argument('--verbose', action='store_true', help='logs de debug')
    args = parser.parse_args()

    _setup_logging(args.quiet, args.verbose)

    config = load_config(Path(args.config))

    try:
        validate_config(config)
    except ConfigValidationError as exc:
        print('Configuração inválida:', file=sys.stderr)
        for erro in exc.errors:
            print(f'  - {erro}', file=sys.stderr)
        raise SystemExit(1)

    logger.info('Resolvendo plano ótimo (lexicográfico: 1º margem, 2º risco)')
    solution = solve_lexicographic(config)
    if solution is None:
        logger.error('Nenhuma solução viável encontrada')
        raise SystemExit(1)
    logger.info('Plano ótimo: margem=%d centavos | risco=%d ‰·ha',
                solution['margem_total'], solution['risco_total'])

    frontier, knee = [], None
    pareto_ativado = (
        args.pareto
        or str((config.get('optimization') or {}).get('mode', 'lexicographic')).lower() == 'pareto'
    )
    if pareto_ativado:
        logger.info('Gerando fronteira de Pareto (ε-constraint)')
        frontier = generate_pareto_frontier(
            config,
            points=args.pareto_points,
            min_margem_ratio=args.min_margem_ratio,
            quiet=args.quiet,
        )
        knee = find_knee_point(frontier) if frontier else None
        if frontier:
            logger.info('Fronteira: %d pontos não-dominados | knee %s', len(frontier),
                        'identificado' if knee else 'não identificado')

    mc = None
    if args.monte_carlo:
        logger.info('Rodando Monte Carlo de robustez')
        mc = run_monte_carlo_robustness(
            config,
            runs=args.mc_runs,
            jitter=args.mc_jitter,
            seed=args.mc_seed,
            baseline_solution=solution,
            quiet=args.quiet,
        )

    relatorio = generate_report(config, solution, frontier=frontier, knee=knee, mc=mc)
    results = build_results(config, solution, frontier=frontier, knee=knee, mc=mc)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    relatorio_path = out_dir / 'relatorio_engine.txt'
    relatorio_path.write_text(relatorio, encoding='utf-8')
    logger.info('Relatório salvo em %s', relatorio_path)

    results_path = out_dir / 'results_mock.json'
    results_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2, default=str) + '\n',
        encoding='utf-8',
    )
    logger.info('Results (contrato com o M3) salvos em %s', results_path)

    png_path = None
    if frontier:
        png_path = generate_pareto_frontier_scatter(
            frontier, knee, path=str(out_dir / 'pareto_frontier.png'))

    print(relatorio)
    artefatos = [str(relatorio_path), str(results_path)]
    if png_path:
        artefatos.append(str(png_path))
    print()
    print(f'Artefatos gerados em {out_dir}:')
    for artefato in artefatos:
        print(f'  - {artefato}')


if __name__ == '__main__':
    main()
