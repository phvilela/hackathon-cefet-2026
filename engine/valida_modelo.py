#!/usr/bin/env python3
"""Kit de smoke-tests de sábado do motor — carta [SÁB][M1] "Validação do solver".

Qualquer um do time roda na raiz do repo e vê ✅/❌ por critério:

    python3 engine/valida_modelo.py [--config engine/config.yaml] [--quick] [--quiet]

Não reimplementa nada do motor: reusa engine.validation (validate_config),
engine.solver (solve_lexicographic), engine.pareto (solve_pareto_point,
generate_pareto_frontier, find_knee_point, _filter_nondominated),
engine.model (rotacoes_viveis_no_grupo) e os helpers PT-BR do engine.report.

Checks (uma linha "✅/❌ nome — detalhe" por critério):
  1. Config válido              — o YAML carrega e validate_config passa
  2. Solve lexicográfico        — OPTIMAL em < 60 s; Σ_rotações área == área do talhão
  3. Propriedade λ=0 (Arrojado) — margem do estágio 1 == upper bound teórico por talhão
                                  (talhão 100% na rotação de MAIOR margem viável do grupo)
  4. Mínimo risco (Conservador) — com capital_pousio: risco 0, tudo no capital; sem:
                                  risco == mínimo teórico (menor risco viável por talhão)
  5. Fronteira de Pareto        — ≥4 pontos não-dominados, Arrojado no topo (margem ==
                                  baseline lexicográfico), knee pertence à fronteira
  6. Unidades                   — margens/riscos do config são int (nunca float no objetivo)
  7. Janelas × ZARC (⚠ aviso)   — config × engine/janelas_zarc.json; se divergir em alguma
                                  rotação, avisa "rode engine/atualiza_config.py para
                                  alinhar as janelas ao ZARC real" — NÃO derruba o kit

--quick pula o item 5 (fronteira, o mais demorado). --quiet silencia os logs
INFO do motor e as barras de progresso. Exit 1 se qualquer ❌ (itens 1–6); o
item 7 nunca conta no "N/M checks OK" nem muda o exit.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml

from engine.model import rotacoes_viveis_no_grupo
from engine.pareto import (
    _filter_nondominated,
    find_knee_point,
    generate_pareto_frontier,
    solve_pareto_point,
)
from engine.report import _fmt_br, _formatar_decendios, _reais
from engine.solver import solve_lexicographic
from engine.validation import ConfigValidationError, validate_config

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ constantes
ZARC_JSON = Path(__file__).resolve().parent / 'janelas_zarc.json'
ROTACAO_CAPITAL = 'capital_pousio'  # custo de oportunidade ("não plantar")
LIMITE_SOLVE_S = 60.0               # item 2: tempo de parede máximo do solve
MIN_PONTOS_FRONTEIRA = 4            # item 5
LARGURA = 96                         # mesma do engine/report.py
AVISO_ZARC = 'rode engine/atualiza_config.py para alinhar as janelas ao ZARC real'


# ---------------------------------------------------------------- formatação PT
def _segundos(duracao: float) -> str:
    return f'{_fmt_br(duracao, 1)} s'


# ----------------------------------------------------------------------- kit
@dataclass
class Resultado:
    """Uma linha do kit: ✅ passou | ❌ falhou | ⚠ aviso | ⏭ pulado (--quick)."""

    nome: str
    detalhe: str
    simbolo: str
    bloqueante: bool  # True: conta em N/M e pode derrubar o exit (itens 1–6)


def _check(nome: str, funcao: Callable[..., Tuple[bool, str]], *args: Any,
           bloqueante: bool = True) -> Resultado:
    """Roda um check; qualquer exceção vira ❌ (o kit nunca explode no meio)."""
    try:
        ok, detalhe = funcao(*args)
    except Exception as exc:  # noqa: BLE001 — smoke-kit: erro inesperado vira ❌ legível
        ok, detalhe = False, f'exceção inesperada: {type(exc).__name__}: {exc}'
    if ok:
        simbolo = '✅'
    else:
        simbolo = '❌' if bloqueante else '⚠'
    return Resultado(nome=nome, detalhe=detalhe, simbolo=simbolo, bloqueante=bloqueante)


def _imprime(resultado: Resultado) -> None:
    print(f'{resultado.simbolo} {resultado.nome} — {resultado.detalhe}')


def _load_config(path: Path) -> Dict[str, Any]:
    """Espelho do `load_config` do engine/main.py (normaliza o YAML da mesma
    forma) — evita importar engine.main, que puxa matplotlib via visualization."""
    with path.open('r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    if not isinstance(config, dict):
        raise ValueError(f'arquivo de config vazio/inválido: {path}')

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


def _resolve_config_path(argumento: str) -> Path:
    """Aceita caminho relativo ao CWD ou à raiz do repo (default engine/config.yaml)."""
    caminho = Path(argumento)
    if not caminho.is_absolute() and not caminho.exists():
        na_raiz = REPO_ROOT / argumento
        if na_raiz.exists():
            return na_raiz
    return caminho


def _setup_logging(quiet: bool) -> None:
    logging.basicConfig(
        level=logging.WARNING if quiet else logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stderr,  # logs do motor em stderr; o kit fala por stdout
    )


def _valor_estagio(solution: Optional[Dict[str, Any]], estagio: str) -> Optional[int]:
    """Valor congelado de um estágio lexicográfico (ex.: 'margem') na solução."""
    if not solution:
        return None
    for resultado in solution.get('stage_results') or []:
        if str(resultado.get('stage')) == estagio:
            return int(resultado['value'])
    return None


def _tem_talhoes_e_rotacoes(config: Optional[Dict[str, Any]]) -> Tuple[bool, str]:
    """Guarda comum dos itens que calculam bounds teóricos por talhão."""
    talhoes = (config or {}).get('talhoes') or {}
    rotacoes = (config or {}).get('rotacoes') or {}
    if not talhoes or not rotacoes:
        return False, 'pulado — config sem talhões/rotações utilizáveis (ver item 1)'
    return True, ''


# --------------------------------------------------------------------- checks

def _check_config(ctx: Dict[str, Any]) -> Tuple[bool, str]:
    """Item 1 — o config carrega e passa no validate_config."""
    config, erros = ctx['config'], ctx['erros']
    if erros:
        resumo = '; '.join(erros[:4]) + ('; …' if len(erros) > 4 else '')
        return False, f'esperado 0 erros de validação; recebi {len(erros)}: {resumo}'
    talhoes = (config or {}).get('talhoes') or {}
    rotacoes = (config or {}).get('rotacoes') or {}
    area = sum(int(info['area_ha']) for info in talhoes.values())
    return True, (f'validate_config OK — {len(talhoes)} talhões ({_fmt_br(area)} ha), '
                  f'{len(rotacoes)} rotações')


def _check_solve(ctx: Dict[str, Any]) -> Tuple[bool, str]:
    """Item 2 — solve_lexicographic: OPTIMAL, < 60 s de parede, áreas 100% cobertas."""
    config = ctx['config']
    if config is None:
        return False, 'pulado — config não carregou (ver item 1)'

    comeco = time.perf_counter()
    solution = solve_lexicographic(config)
    duracao = time.perf_counter() - comeco
    ctx['solution'] = solution  # itens 3 e 5 reusam (baseline lexicográfico)

    if solution is None:
        return False, 'esperado plano ótimo viável; solve_lexicographic retornou None (inviável)'

    problemas: List[str] = []
    status = [str(s.get('status_name')) for s in (solution.get('stage_results') or [])]
    if solution.get('status_name') != 'OPTIMAL' or any(s != 'OPTIMAL' for s in status):
        problemas.append(f'status: esperado OPTIMAL em todos os estágios; recebi {status}')
    if duracao >= LIMITE_SOLVE_S:
        problemas.append(f'tempo de parede: esperado < {LIMITE_SOLVE_S:.0f} s; '
                         f'foram {_segundos(duracao)}')

    talhoes = config.get('talhoes') or {}
    plano = solution.get('plano') or {}
    for nome, info in talhoes.items():
        alocada = sum((plano.get(nome) or {}).values())
        esperada = int(info['area_ha'])
        if alocada != esperada:
            problemas.append(f'talhão {nome}: esperado Σ_rotações área == {esperada} ha; '
                             f'recebi {alocada} ha')
    if problemas:
        return False, '; '.join(problemas)

    estagios = ', '.join(f"{s['stage']}={_fmt_br(s['value'])}"
                         for s in (solution.get('stage_results') or []))
    return True, (f'OPTIMAL em {_segundos(duracao)} (estágios: {estagios}) — margem total '
                  f'{_reais(solution["margem_total"])} ({_fmt_br(solution["margem_total"])} '
                  f'centavos), risco total {_fmt_br(solution["risco_total"])} ‰·ha; '
                  f'todos os {len(talhoes)} talhões com a área toda alocada')


def _check_lambda_zero(ctx: Dict[str, Any]) -> Tuple[bool, str]:
    """Item 3 — λ=0: margem do estágio 1 == upper bound teórico por talhão.

    Upper bound: cada talhão 100% na rotação de MAIOR margem VIÁVEL no seu
    grupo de solo (viável = janelas_viveis[grupo] não vazia).
    """
    config, solution = ctx['config'], ctx['solution']
    if config is None:
        return False, 'pulado — config não carregou (ver item 1)'
    if solution is None:
        return False, 'pulado — solve lexicográfico falhou (ver item 2)'
    ok, motivo = _tem_talhoes_e_rotacoes(config)
    if not ok:
        return False, motivo

    rotacoes, talhoes = config['rotacoes'], config['talhoes']
    ub_por_talhao: Dict[str, int] = {}
    melhor_por_talhao: Dict[str, str] = {}
    for nome, info in talhoes.items():
        grupo = int(info['grupo_solo'])
        viveis = rotacoes_viveis_no_grupo(rotacoes, grupo)
        if not viveis:
            return False, (f'talhão {nome} (grupo de solo {grupo}) sem rotação viável — '
                          'upper bound indefinido')
        melhor = max(viveis, key=lambda r: int(rotacoes[r]['margem_esperada']))
        melhor_por_talhao[nome] = melhor
        ub_por_talhao[nome] = int(info['area_ha']) * int(rotacoes[melhor]['margem_esperada'])
    ub_total = sum(ub_por_talhao.values())

    problemas: List[str] = []
    margem_estagio1 = _valor_estagio(solution, 'margem')
    if margem_estagio1 is None:
        problemas.append('estágio "margem" ausente nos stage_results')
    elif margem_estagio1 != ub_total:
        problemas.append(f'margem do estágio 1: esperado upper bound teórico '
                         f'{_fmt_br(ub_total)} centavos ({_reais(ub_total)}); '
                         f'recebi {_fmt_br(margem_estagio1)}')
    margem_plano = int(solution.get('margem_total', -1))
    if margem_plano != ub_total:
        problemas.append(f'margem_total do plano: esperado {_fmt_br(ub_total)}; '
                         f'recebi {_fmt_br(margem_plano)}')
    margem_por_talhao = solution.get('margem_por_talhao') or {}
    for nome, ub in ub_por_talhao.items():
        obtido = int(margem_por_talhao.get(nome, 0))
        if obtido != ub:
            problemas.append(f'talhão {nome}: esperado margem {_fmt_br(ub)} '
                             f'(100% em {melhor_por_talhao[nome]}); recebi {_fmt_br(obtido)}')
    if problemas:
        return False, '; '.join(problemas)

    escolhas = ', '.join(f'{t}→{r}' for t, r in melhor_por_talhao.items())
    return True, (f'margem do estágio 1 == upper bound teórico Σ (área × maior margem viável) '
                  f'= {_fmt_br(ub_total)} centavos ({_reais(ub_total)}); '
                  f'por talhão: {escolhas}')


def _check_min_risco(ctx: Dict[str, Any]) -> Tuple[bool, str]:
    """Item 4 — Conservador: mínimo risco absoluto (solve_pareto_point sem piso)."""
    config = ctx['config']
    if config is None:
        return False, 'pulado — config não carregou (ver item 1)'
    ok, motivo = _tem_talhoes_e_rotacoes(config)
    if not ok:
        return False, motivo

    ponto = solve_pareto_point(config, margem_floor=None)
    if ponto is None:
        return False, ('esperado ponto de mínimo risco absoluto; '
                       'solve_pareto_point(margem_floor=None) retornou None (inviável)')
    rotacoes, talhoes = config['rotacoes'], config['talhoes']
    area_total = sum(int(info['area_ha']) for info in talhoes.values())

    if ROTACAO_CAPITAL in rotacoes:
        # com capital_pousio: o mínimo risco absoluto é "não plantar" — risco 0
        margem_capital = int(rotacoes[ROTACAO_CAPITAL]['margem_esperada'])
        esperado_margem = margem_capital * area_total
        problemas: List[str] = []
        if int(ponto['risco']) != 0:
            problemas.append(f'risco_total: esperado 0 ‰·ha; recebi {_fmt_br(ponto["risco"])}')
        if int(ponto['margem']) != esperado_margem:
            problemas.append(f'margem_total: esperado {_fmt_br(esperado_margem)} centavos '
                             f'({_reais(esperado_margem)} = margem_capital × Σ áreas); '
                             f'recebi {_fmt_br(ponto["margem"])}')
        alocacao = ponto.get('area_por_rotacao') or {}
        if set(alocacao) != {ROTACAO_CAPITAL}:
            problemas.append(f'plano: esperado 100% da área em {ROTACAO_CAPITAL}; recebi {alocacao}')
        if problemas:
            return False, '; '.join(problemas)
        return True, (f'risco_total 0 ‰·ha e margem {_reais(esperado_margem)} == margem_capital '
                      f'({_fmt_br(margem_capital)} centavos/ha) × Σ áreas ({_fmt_br(area_total)} ha) '
                      f'— tudo no {ROTACAO_CAPITAL} (âncora conservadora da fronteira)')

    # sem capital_pousio: o mínimo teórico é a rotação de MENOR risco viável por talhão
    esperado_por_talhao: Dict[str, int] = {}
    escolhas: Dict[str, str] = {}
    for nome, info in talhoes.items():
        grupo = int(info['grupo_solo'])
        viveis = rotacoes_viveis_no_grupo(rotacoes, grupo)
        if not viveis:
            return False, (f'talhão {nome} (grupo de solo {grupo}) sem rotação viável — '
                          'mínimo teórico indefinido')
        melhor = min(viveis, key=lambda r: int(rotacoes[r]['risco']))
        escolhas[nome] = melhor
        esperado_por_talhao[nome] = int(info['area_ha']) * int(rotacoes[melhor]['risco'])
    esperado = sum(esperado_por_talhao.values())
    if int(ponto['risco']) != esperado:
        return False, (f'risco_total: esperado mínimo teórico {_fmt_br(esperado)} ‰·ha; '
                       f'recebi {_fmt_br(ponto["risco"])}')
    por_talhao = ', '.join(f'{t}→{r}' for t, r in escolhas.items())
    return True, (f'risco_total == mínimo teórico Σ (área × menor risco viável) = '
                  f'{_fmt_br(esperado)} ‰·ha (sem {ROTACAO_CAPITAL} no config); '
                  f'por talhão: {por_talhao}')


def _check_fronteira(ctx: Dict[str, Any]) -> Tuple[bool, str]:
    """Item 5 — fronteira ε-constraint: ≥4 pontos, Arrojado no topo, knee ∈ fronteira."""
    config = ctx['config']
    if config is None:
        return False, 'pulado — config não carregou (ver item 1)'

    # baseline lexicográfico: reusa o do item 2; senão resolve na hora
    baseline_margem = _valor_estagio(ctx.get('solution'), 'margem')
    if baseline_margem is None:
        baseline_margem = _valor_estagio(solve_lexicographic(config), 'margem')
    if baseline_margem is None:
        return False, 'baseline lexicográfico indisponível — impossível bater o topo da fronteira'

    frontier = generate_pareto_frontier(config, quiet=bool(ctx.get('quiet')))
    if not frontier:
        return False, 'esperado fronteira com ≥4 pontos; generate_pareto_frontier retornou []'

    problemas: List[str] = []
    if len(frontier) < MIN_PONTOS_FRONTEIRA:
        problemas.append(f'esperado ≥{MIN_PONTOS_FRONTEIRA} pontos não-dominados; '
                         f'recebi {len(frontier)}')
    if len(_filter_nondominated(list(frontier))) != len(frontier):
        problemas.append('a fronteira retornada contém pontos dominados')
    if any(int(frontier[i]['margem']) < int(frontier[i + 1]['margem'])
           for i in range(len(frontier) - 1)):
        problemas.append('fronteira não ordenada por margem decrescente (índice 0 = Arrojado)')

    topo = int(frontier[0]['margem'])
    if topo != baseline_margem:
        problemas.append(f'topo: esperado margem do baseline lexicográfico '
                         f'{_fmt_br(baseline_margem)}; recebi {_fmt_br(topo)}')

    knee = find_knee_point(frontier)
    if knee is None:
        problemas.append('knee: esperado um ponto da fronteira; find_knee_point retornou None')
    else:
        pares = {(int(p['margem']), int(p['risco'])) for p in frontier}
        if (int(knee['margem']), int(knee['risco'])) not in pares:
            problemas.append(f'knee (margem {_fmt_br(knee["margem"])}, risco '
                             f'{_fmt_br(knee["risco"])}) não pertence à fronteira')
    if problemas:
        return False, '; '.join(problemas)

    return True, (f'{len(frontier)} pontos não-dominados (≥{MIN_PONTOS_FRONTEIRA}); topo = '
                  f'Arrojado com margem {_fmt_br(topo)} == baseline lexicográfico; knee '
                  f'(perfil Equilibrado) em margem {_fmt_br(knee["margem"])} / risco '
                  f'{_fmt_br(knee["risco"])} está na fronteira')


def _check_unidades(ctx: Dict[str, Any]) -> Tuple[bool, str]:
    """Item 6 — todas as margens/riscos do config são int (nunca float no objetivo).

    Lê o YAML cru de propósito: o load normaliza com int() e MASCARARIA um
    float (418000.5 viraria 418000 em silêncio) — o teste honesto é na fonte.
    """
    config_path: Path = ctx['config_path']
    try:
        raw = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    except Exception as exc:
        return False, f'esperado YAML legível; não consegui reler {config_path}: {exc}'
    if not isinstance(raw, dict):
        return False, f'esperado mapping na raiz do YAML; recebi {type(raw).__name__}'
    rotacoes = raw.get('rotacoes') or {}
    if not rotacoes:
        return False, "esperado mapping 'rotacoes' não vazio no YAML"

    violacoes: List[str] = []
    for nome, info in rotacoes.items():
        for campo in ('margem_esperada', 'risco'):
            valor = (info or {}).get(campo) if isinstance(info, dict) else None
            if isinstance(valor, bool) or not isinstance(valor, int):
                violacoes.append(f'rotacoes.{nome}.{campo}={valor!r} ({type(valor).__name__})')
    if violacoes:
        lista = '; '.join(violacoes[:6]) + ('; …' if len(violacoes) > 6 else '')
        return False, ('esperado int em todas as margens/riscos (CP-SAT só tem inteiros no '
                       f'objetivo); recebi: {lista}')
    return True, (f'{len(rotacoes)} rotações × 2 campos (margem_esperada, risco) = '
                  f'{2 * len(rotacoes)} valores, todos int no YAML — objetivo 100% inteiro')


def _check_janelas_zarc(ctx: Dict[str, Any]) -> Tuple[bool, str]:
    """Item 7 (⚠ só aviso) — janelas do config × engine/janelas_zarc.json."""
    config = ctx['config']
    if config is None:
        return False, 'pulado — config não carregou (ver item 1)'
    if not ZARC_JSON.exists():
        return False, f'{ZARC_JSON.name} não encontrado — rode engine/adequacao.py para gerá-lo'
    zarc = json.loads(ZARC_JSON.read_text(encoding='utf-8'))
    zarc_rotacoes = zarc.get('rotacoes') or {}

    divergencias: List[str] = []
    comparadas = 0
    for nome, info in (config.get('rotacoes') or {}).items():
        if nome == ROTACAO_CAPITAL:
            continue  # não é cultura ZARC: o capital "planta" o ano todo, por construção
        zarc_rot = zarc_rotacoes.get(nome)
        if zarc_rot is None:
            divergencias.append(f'{nome}: não existe no janelas_zarc.json')
            continue
        janelas = info.get('janelas_viveis') or {}
        for grupo in sorted(set(janelas) | {int(g) for g in zarc_rot}):
            comparadas += 1
            do_config = sorted(int(d) for d in (janelas.get(grupo) or []))
            do_zarc = sorted(int(d) for d in ((zarc_rot.get(str(grupo)) or {}).get('primeira') or []))
            if do_config != do_zarc:
                divergencias.append(
                    f'{nome} g{grupo}: config {_formatar_decendios(do_config)} vs '
                    f'ZARC {_formatar_decendios(do_zarc)}')
    if divergencias:
        exemplos = '; '.join(divergencias[:4]) + ('; …' if len(divergencias) > 4 else '')
        return False, (f'{len(divergencias)} de {comparadas} janelas de plantio divergem do ZARC '
                       f'real ({exemplos}) — {AVISO_ZARC}')
    return True, (f'janelas do config em linha com {ZARC_JSON.name} '
                  f'({comparadas} janelas comparadas)')


# ---------------------------------------------------------------------- CLI

def _cabecalho(config_path: Path, quick: bool) -> str:
    py = f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'
    linhas = [
        '=' * LARGURA,
        'HackatOhm 2026 · kit de smoke-tests do motor — carta [SÁB][M1] "Validação do solver"',
        f'config: {config_path}  |  motor: engine/ (CP-SAT: lexicográfico + Pareto ε-constraint)  |  Python {py}',
    ]
    if quick:
        linhas.append('modo --quick: item 5 (fronteira) pulado')
    linhas.append('item 7 (janelas × ZARC) é só aviso ⚠: não conta em N/M e não derruba o kit')
    linhas.append('=' * LARGURA)
    return '\n'.join(linhas)


def _main() -> int:
    parser = argparse.ArgumentParser(
        description='Kit de smoke-tests do motor "o que plantar" (carta [SÁB][M1] "Validação '
                    'do solver"): ✅/❌ por critério; exit 1 se qualquer ❌ (itens 1–6).',
        epilog=('Exemplos:\n'
                '  python3 engine/valida_modelo.py\n'
                '  python3 engine/valida_modelo.py --quick --quiet\n'
                '  python3 engine/valida_modelo.py --config engine/config.yaml\n'),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--config', default='engine/config.yaml',
                        help='caminho do config YAML (default: engine/config.yaml)')
    parser.add_argument('--quick', action='store_true',
                        help='pula o item 5 (fronteira de Pareto, o mais demorado)')
    parser.add_argument('--quiet', action='store_true',
                        help='suprime logs INFO do motor e barras de progresso')
    args = parser.parse_args()

    _setup_logging(args.quiet)

    config_path = _resolve_config_path(args.config)
    print(_cabecalho(config_path, args.quick))
    inicio = time.perf_counter()

    # ------------------------------------------- item 1: carregar + validar config
    config: Optional[Dict[str, Any]] = None
    erros: List[str] = []
    try:
        config = _load_config(config_path)
    except Exception as exc:
        erros.append(f'falha ao carregar {config_path}: {exc}')
    else:
        try:
            validate_config(config)
        except ConfigValidationError as exc:
            erros.extend(str(erro) for erro in exc.errors)

    ctx: Dict[str, Any] = {
        'config_path': config_path,
        'config': config,
        'erros': erros,
        'solution': None,
        'quiet': args.quiet,
    }

    resultados: List[Resultado] = []
    for resultado in [
        _check('1. Config válido', _check_config, ctx),
        _check('2. Solve lexicográfico', _check_solve, ctx),
        _check('3. Propriedade λ=0 (Arrojado)', _check_lambda_zero, ctx),
        _check('4. Mínimo risco absoluto (Conservador)', _check_min_risco, ctx),
    ]:
        resultados.append(resultado)
        _imprime(resultado)

    if args.quick:
        resultados.append(Resultado(nome='5. Fronteira de Pareto', detalhe='pulado (--quick)',
                                    simbolo='⏭', bloqueante=False))
    else:
        resultados.append(_check('5. Fronteira de Pareto', _check_fronteira, ctx))
    _imprime(resultados[-1])

    for resultado in [
        _check('6. Unidades inteiras', _check_unidades, ctx),
        _check('7. Janelas × ZARC (aviso)', _check_janelas_zarc, ctx, bloqueante=False),
    ]:
        resultados.append(resultado)
        _imprime(resultado)

    # ---------------------------------------------------------------- resumo
    duracao = time.perf_counter() - inicio
    bloqueantes = [r for r in resultados if r.bloqueante]
    n_ok = sum(1 for r in bloqueantes if r.simbolo == '✅')
    falhas = sum(1 for r in bloqueantes if r.simbolo == '❌')
    avisos = sum(1 for r in resultados if r.simbolo == '⚠')

    print('-' * LARGURA)
    resumo = f'Resumo: {n_ok}/{len(bloqueantes)} checks OK'
    if falhas:
        resumo += f' · ❌ {falhas} falha(s) — corrija antes de seguir'
    if avisos:
        resumo += f' · ⚠ {avisos} aviso(s) (não bloqueiam)'
    resumo += f' · {_segundos(duracao)} no total'
    print(resumo)

    return 1 if falhas else 0


if __name__ == '__main__':
    raise SystemExit(_main())
