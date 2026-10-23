"""Validação do `config.yaml` da fazenda (padrão `ConfigValidationError` do original).

Mensagens em PT-BR, uma linha por erro. Levanta `ConfigValidationError` com a
lista completa de erros (não para no primeiro).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

KNOWN_MODES = {'lexicographic', 'pareto'}
KNOWN_STAGES = {'margem', 'risco'}
GRUPOS_SOLO_VALIDOS = {1, 2, 3}


@dataclass
class ConfigValidationError(Exception):
    errors: List[str]

    def __str__(self) -> str:
        return '\n'.join(self.errors)


def _eh_int(valor: Any) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def _as_int(valor: Any, campo: str, errors: List[str]) -> Optional[int]:
    """Converte para int (aceita float inteiro); registra erro legível se não der."""
    if _eh_int(valor):
        return int(valor)
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    errors.append(f'{campo} deve ser um inteiro (recebi {valor!r}).')
    return None


def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Valida o config da fazenda. Levanta `ConfigValidationError` se houver erros."""
    errors: List[str] = []

    if not isinstance(config, dict):
        raise ConfigValidationError(['A raiz do config deve ser um dicionário (YAML mapping).'])

    cenario = config.get('cenario')
    settings = config.get('settings', {}) or {}
    talhoes = config.get('talhoes')
    rotacoes = config.get('rotacoes')
    optimization = config.get('optimization', {}) or {}
    pareto = config.get('pareto', {}) or {}
    monte_carlo = config.get('monte_carlo', {}) or {}
    decendios_cfg = 36

    # ---------------------------------------------------------------- cenário
    area_total: Optional[int] = None
    if not isinstance(cenario, dict):
        errors.append("'cenario' é obrigatório e deve ser um mapping.")
    else:
        area_total = _as_int(cenario.get('area_total_ha'), 'cenario.area_total_ha', errors)
        if area_total is not None and area_total <= 0:
            errors.append(f'cenario.area_total_ha deve ser > 0 (recebi {area_total}).')
        if not str(cenario.get('municipio', '')).strip():
            errors.append('cenario.municipio deve ser um texto não vazio.')

    # --------------------------------------------------------------- settings
    if not isinstance(settings, dict):
        errors.append("'settings' deve ser um mapping (se presente).")
    else:
        decendios = _as_int(settings.get('decendios', 36), 'settings.decendios', errors)
        if decendios is not None:
            if decendios <= 0:
                errors.append(f'settings.decendios deve ser > 0 (recebi {decendios}).')
            else:
                decendios_cfg = decendios
        if 'margem_em_centavos' in settings and settings['margem_em_centavos'] is not True:
            errors.append(
                'settings.margem_em_centavos deve ser true — CP-SAT só trabalha com '
                'inteiros (margens em centavos).'
            )

    # ---------------------------------------------------------------- talhões
    total_area_talhoes = 0
    if not isinstance(talhoes, dict) or not talhoes:
        errors.append(
            "'talhoes' deve ser um mapping não vazio "
            "(ex.: T1: {area_ha: 300, grupo_solo: 2})."
        )
        talhoes = talhoes if isinstance(talhoes, dict) else {}
    else:
        for nome, info in talhoes.items():
            if not isinstance(info, dict):
                errors.append(f'talhoes.{nome} deve ser um mapping.')
                continue
            area = _as_int(info.get('area_ha'), f'talhoes.{nome}.area_ha', errors)
            if area is not None:
                if area <= 0:
                    errors.append(f'talhoes.{nome}.area_ha deve ser > 0 (recebi {area}).')
                else:
                    total_area_talhoes += area
            grupo = _as_int(info.get('grupo_solo'), f'talhoes.{nome}.grupo_solo', errors)
            if grupo is not None and grupo not in GRUPOS_SOLO_VALIDOS:
                errors.append(
                    f'talhoes.{nome}.grupo_solo deve ser 1, 2 ou 3 (recebi {grupo}).'
                )

    # --------------------------------------------------------------- rotações
    if not isinstance(rotacoes, dict) or not rotacoes:
        errors.append("'rotacoes' deve ser um mapping não vazio.")
        rotacoes = rotacoes if isinstance(rotacoes, dict) else {}
    else:
        for nome, info in rotacoes.items():
            if not isinstance(info, dict):
                errors.append(f'rotacoes.{nome} deve ser um mapping.')
                continue
            margem = _as_int(info.get('margem_esperada'),
                              f'rotacoes.{nome}.margem_esperada', errors)
            if margem is not None and margem <= 0:
                errors.append(
                    f'rotacoes.{nome}.margem_esperada deve ser > 0 '
                    f'(centavos de R$/ha; recebi {margem}).'
                )
            risco = _as_int(info.get('risco'), f'rotacoes.{nome}.risco', errors)
            if risco is not None and not (0 <= risco <= 1000):
                errors.append(
                    f'rotacoes.{nome}.risco deve estar em 0..1000 por-mil (recebi {risco}).'
                )

            janelas = info.get('janelas_viveis')
            if not isinstance(janelas, dict) or not janelas:
                errors.append(
                    f"rotacoes.{nome}.janelas_viveis deve ser um mapping "
                    '{grupo_solo: [decêndios]} não vazio.'
                )
            else:
                algum_grupo_vivel = False
                for grupo, lista in janelas.items():
                    g = _as_int(grupo,
                                f'rotacoes.{nome}.janelas_viveis (grupo {grupo!r})', errors)
                    if g is not None and g not in GRUPOS_SOLO_VALIDOS:
                        errors.append(
                            f'rotacoes.{nome}.janelas_viveis: grupo inválido {g} '
                            '(use 1, 2 ou 3).'
                        )
                    if not isinstance(lista, list):
                        errors.append(
                            f'rotacoes.{nome}.janelas_viveis[{grupo}] deve ser uma '
                            'lista de decêndios.'
                        )
                        continue
                    if lista:
                        algum_grupo_vivel = True
                    for decendio in lista:
                        d = _as_int(decendio,
                                    f'rotacoes.{nome}.janelas_viveis[{grupo}] '
                                    f'decêndio {decendio!r}', errors)
                        if d is not None and not (1 <= d <= decendios_cfg):
                            errors.append(
                                f'rotacoes.{nome}.janelas_viveis[{grupo}]: decêndio {d} '
                                f'fora da faixa 1..{decendios_cfg}.'
                            )
                    if len(set(lista)) != len(lista):
                        errors.append(
                            f'rotacoes.{nome}.janelas_viveis[{grupo}] tem decêndios repetidos.'
                        )
                if not algum_grupo_vivel:
                    errors.append(
                        f'rotacoes.{nome} precisa de janela viável (lista não vazia) '
                        'em ao menos um grupo de solo.'
                    )

            hipoteses = info.get('hipoteses', [])
            if hipoteses and not isinstance(hipoteses, list):
                errors.append(f'rotacoes.{nome}.hipoteses deve ser uma lista (se presente).')
            elif isinstance(hipoteses, list):
                for indice, hipotese in enumerate(hipoteses):
                    if not isinstance(hipotese, dict):
                        errors.append(
                            f'rotacoes.{nome}.hipoteses[{indice}] deve ser um mapping '
                            '(chave/valor/fonte_url/metodo).'
                        )

    # ------------------------------------------- Σ áreas == área total (600 ha)
    if area_total is not None and isinstance(talhoes, dict) and total_area_talhoes != area_total:
        errors.append(
            f'A soma das áreas dos talhões ({total_area_talhoes} ha) deve ser igual a '
            f'cenario.area_total_ha ({area_total} ha).'
        )

    # --------------------- cada talhão precisa de ≥1 rotação viável (senão inviável)
    if isinstance(talhoes, dict) and isinstance(rotacoes, dict):
        for nome_t, info_t in talhoes.items():
            if not isinstance(info_t, dict):
                continue
            grupo = info_t.get('grupo_solo')
            if not _eh_int(grupo):
                continue
            viveis = [
                nome_r for nome_r, info_r in rotacoes.items()
                if isinstance(info_r, dict) and (info_r.get('janelas_viveis') or {}).get(grupo)
            ]
            if not viveis:
                errors.append(
                    f'talhoes.{nome_t} (grupo de solo {grupo}) não tem nenhuma rotação '
                    'com janela viável — o modelo ficaria inviável.'
                )

    # ------------------------------------------------------------ optimization
    mode = str(optimization.get('mode', 'lexicographic')).lower()
    if mode not in KNOWN_MODES:
        errors.append(f'optimization.mode deve ser um de {sorted(KNOWN_MODES)} (recebi {mode!r}).')
    stages = optimization.get('stages', ['margem', 'risco'])
    if not isinstance(stages, list) or not stages:
        errors.append('optimization.stages deve ser uma lista não vazia.')
    else:
        invalidos = [s for s in stages if s not in KNOWN_STAGES]
        if invalidos:
            errors.append(
                f'optimization.stages tem entradas inválidas: {invalidos} '
                f'(use {sorted(KNOWN_STAGES)}).'
            )

    # ------------------------------------------------------------------ pareto
    if 'pareto' in config:
        if not isinstance(pareto, dict):
            errors.append("'pareto' deve ser um mapping (se presente).")
        else:
            pontos = _as_int(pareto.get('points', 6), 'pareto.points', errors)
            if pontos is not None and pontos < 2:
                errors.append('pareto.points deve ser >= 2.')
            try:
                ratio = float(pareto.get('min_margem_ratio', 0.85))
                if not (0 < ratio <= 1):
                    errors.append('pareto.min_margem_ratio deve estar em (0, 1].')
            except (TypeError, ValueError):
                errors.append(
                    f"pareto.min_margem_ratio deve ser numérico (recebi "
                    f"{pareto.get('min_margem_ratio')!r})."
                )

    # ------------------------------------------------------------ monte_carlo
    if 'monte_carlo' in config:
        if not isinstance(monte_carlo, dict):
            errors.append("'monte_carlo' deve ser um mapping (se presente).")
        else:
            runs = _as_int(monte_carlo.get('runs', 30), 'monte_carlo.runs', errors)
            if runs is not None and runs < 1:
                errors.append('monte_carlo.runs deve ser >= 1.')
            jitter = _as_int(monte_carlo.get('margem_jitter_percent', 10),
                             'monte_carlo.margem_jitter_percent', errors)
            if jitter is not None and not (0 <= jitter <= 100):
                errors.append('monte_carlo.margem_jitter_percent deve estar em 0..100.')
            if monte_carlo.get('seed') is not None:
                _as_int(monte_carlo['seed'], 'monte_carlo.seed', errors)

    if errors:
        logger.error('Validação do config falhou com %d erro(s)', len(errors))
        raise ConfigValidationError(errors)

    logger.info('Config validado: %d talhões, %d rotações', len(talhoes), len(rotacoes))
    return config
