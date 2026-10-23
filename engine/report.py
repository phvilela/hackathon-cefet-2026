"""Relatório texto + dicionário de resultados (rascunho do contrato com o M3).

`generate_report(...)`  → texto legível (PT-BR), gravado em `engine/out/relatorio_engine.txt`
`build_results(...)`    → dict JSON-serializável, gravado em `engine/out/results_mock.json`
Unidades: margem em centavos (exibida em R$); risco em ‰·ha
("ha sob risco" = Σ risco‰ × ha ÷ 1000 = hectares com margem negativa esperada).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

LARGURA = 96
PERFIL_DESCRICOES = {
    'arrojado': 'máxima margem (topo da fronteira)',
    'equilibrado': 'knee point — melhor trade-off margem × risco',
    'conservador': 'mínimo risco dentro da faixa de Pareto',
}


# --------------------------------------------------------------------- helpers

def _fmt_br(valor: Any, decimais: int = 0) -> str:
    """Formata número no padrão PT-BR: 2636000 -> '2.636.000'; 70.93 -> '70,93'."""
    texto = f'{float(valor):,.{decimais}f}'
    return texto.replace(',', 'X').replace('.', ',').replace('X', '.')


def _reais(centavos: int) -> str:
    return f'R$ {_fmt_br(centavos / 100.0, 2)}'


def _ha_sob_risco(risco_por_mil_ha: int) -> str:
    return f'{_fmt_br(risco_por_mil_ha / 1000.0, 1)} ha'


def _formatar_decendios(decendios: List[int]) -> str:
    """[25, 26, 27] -> '[25-27]'; [28, 30, 31] -> '[28, 30-31]'; [] -> '(inviável)'."""
    if not decendios:
        return '(inviável)'
    ds = sorted(set(decendios))
    partes: List[str] = []
    inicio = anterior = ds[0]
    for d in ds[1:]:
        if d == anterior + 1:
            anterior = d
            continue
        partes.append(str(inicio) if inicio == anterior else f'{inicio}-{anterior}')
        inicio = anterior = d
    partes.append(str(inicio) if inicio == anterior else f'{inicio}-{anterior}')
    return '[' + ', '.join(partes) + ']'


def _norm_ponto(ponto: Dict[str, Any]) -> tuple:
    """Normaliza um ponto (fronteira tem 'margem'/'risco'; solução tem *_total)."""
    margem = int(ponto.get('margem', ponto.get('margem_total', 0)))
    risco = int(ponto.get('risco', ponto.get('risco_total', 0)))
    return margem, risco


def _plano_em_linha(plano: Dict[str, Dict[str, int]], talhoes_cfg: Dict[str, Any]) -> str:
    partes = []
    for t_nome, t_info in talhoes_cfg.items():
        alocacao = plano.get(t_nome, {})
        if not alocacao:
            partes.append(f'{t_nome}: (sem alocação)')
            continue
        interno = ' + '.join(
            f'{r} {_fmt_br(a)} ha' for r, a in sorted(alocacao.items(), key=lambda kv: -kv[1])
        )
        partes.append(f'{t_nome} ({_fmt_br(t_info["area_ha"])} ha): {interno}')
    return ' | '.join(partes)


def _formatar_plano(plano: Dict[str, Dict[str, int]], talhoes_cfg: Dict[str, Any]) -> List[str]:
    linhas: List[str] = []
    for t_nome, t_info in talhoes_cfg.items():
        area = int(t_info['area_ha'])
        grupo = int(t_info['grupo_solo'])
        alocacao = plano.get(t_nome, {})
        linhas.append(f'{t_nome} ({_fmt_br(area)} ha, solo grupo {grupo}):')
        if not alocacao:
            linhas.append('    (sem alocação)')
            continue
        for rotacao, ha in sorted(alocacao.items(), key=lambda kv: -kv[1]):
            pct = 100.0 * ha / area
            linhas.append(
                f'    - {rotacao:<16} {_fmt_br(ha):>6} ha   ({_fmt_br(pct, 1)}% da área)'
            )
    return linhas


# ------------------------------------------------------------------ results dict

def _ponto_para_dict(ponto: Dict[str, Any],
                     perfil: Optional[str] = None,
                     descricao: Optional[str] = None) -> Dict[str, Any]:
    """Ponto da fronteira/solução → dict autoexplicativo (contrato com o M3)."""
    margem, risco = _norm_ponto(ponto)
    return {
        'perfil': perfil,
        'descricao': descricao,
        'margem_floor_centavos': (
            int(ponto['margem_floor']) if ponto.get('margem_floor') is not None else None
        ),
        'margem_centavos': margem,
        'margem_reais': round(margem / 100.0, 2),
        'risco_por_mil_ha': risco,
        'ha_sob_risco': round(risco / 1000.0, 1),
        'status': ponto.get('status_name'),
        'plano_por_talhao': ponto.get('plano'),
        'area_por_rotacao': ponto.get('area_por_rotacao'),
    }


def _robustez_json(mc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'runs': mc['settings']['runs'],
        'jitter_percent': mc['settings']['jitter_percent'],
        'seed': mc['settings']['seed'],
        'successful_runs': mc['successful_runs'],
        'failed_runs': mc['failed_runs'],
        'stability_mean': round(mc['stability_mean'], 4),
        'stability_min': round(mc['stability_min'], 4),
        'stability_max': round(mc['stability_max'], 4),
        'max_talhoes_mudados': mc['max_talhoes_mudados'],
        'pct_runs_sem_mudanca': round(mc['pct_runs_sem_mudanca'], 1),
        'distribuicao_mudancas_talhoes': mc['changed_distribution'],
        'frase_estabilidade': mc['frase_estabilidade'],
        'retention_por_rotacao': mc['retention_por_rotacao'],
        'margem_total_centavos': {
            'media': mc['margem_total_media_centavos'],
            'minimo': mc['margem_total_min_centavos'],
            'maximo': mc['margem_total_max_centavos'],
            'desvio_padrao': round(mc['margem_total_std_centavos'], 1),
        },
        'observacao': (
            'Perturba as margens (custos embutidos) em ±10% e re-resolve; mede a '
            'estabilidade da RECOMENDAÇÃO — complementar ao MC do M1, que gera as margens.'
        ),
    }


def build_results(config: Dict[str, Any],
                  solution: Dict[str, Any],
                  frontier: Optional[List[Dict[str, Any]]] = None,
                  knee: Optional[Dict[str, Any]] = None,
                  mc: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Monta o dict de resultados — rascunho do contrato com o M3 (JSON)."""
    frontier = frontier or []
    cenario_cfg = config.get('cenario', {}) or {}
    talhoes_cfg = config.get('talhoes', {}) or {}
    rotacoes_cfg = config.get('rotacoes', {}) or {}

    arrojado = max(frontier, key=lambda p: _norm_ponto(p)[0]) if frontier else None
    conservador = min(frontier, key=lambda p: (_norm_ponto(p)[1], -_norm_ponto(p)[0])) if frontier else None
    equilibrado = knee

    fronteira_json = []
    for ponto in frontier:
        perfil = None
        if ponto is arrojado:
            perfil = 'Arrojado'
        elif ponto is equilibrado:
            perfil = 'Equilibrado (knee)'
        elif ponto is conservador:
            perfil = 'Conservador'
        fronteira_json.append(_ponto_para_dict(ponto, perfil=perfil))

    plano_otimo = _ponto_para_dict(
        solution,
        perfil='Ótimo lexicográfico',
        descricao='lexicográfico: 1º maximiza margem, 2º minimiza risco',
    )
    plano_otimo['stage_results'] = [
        {
            'estagio': estagio['stage'],
            'direcao': estagio['direction'],
            'valor': int(estagio['value']),
            'status': estagio['status_name'],
        }
        for estagio in solution.get('stage_results', [])
    ]

    planos: Dict[str, Any] = {}
    if arrojado is not None:
        planos['arrojado'] = _ponto_para_dict(
            arrojado, perfil='Arrojado', descricao=PERFIL_DESCRICOES['arrojado'])
    if equilibrado is not None:
        planos['equilibrado'] = _ponto_para_dict(
            equilibrado, perfil='Equilibrado (knee)',
            descricao=PERFIL_DESCRICOES['equilibrado'])
    if conservador is not None:
        planos['conservador'] = _ponto_para_dict(
            conservador, perfil='Conservador', descricao=PERFIL_DESCRICOES['conservador'])
    if not planos:
        planos['arrojado'] = dict(
            plano_otimo,
            perfil='Arrojado',
            descricao='sem fronteira gerada — usa o plano lexicográfico',
        )

    rotacoes_json: Dict[str, Any] = {}
    for nome, info in rotacoes_cfg.items():
        janelas = {int(g): list(ds) for g, ds in (info.get('janelas_viveis') or {}).items()}
        rotacoes_json[nome] = {
            'culturas': list(info.get('culturas', [])),
            'margem_centavos_por_ha': int(info['margem_esperada']),
            'margem_reais_por_ha': round(int(info['margem_esperada']) / 100.0, 2),
            'risco_por_mil': int(info['risco']),
            'janelas_viveis_decendios': {str(g): ds for g, ds in janelas.items()},
            'grupos_viveis': sorted(g for g, ds in janelas.items() if ds),
            'hipoteses': info.get('hipoteses', []),
        }

    results = {
        'cenario': {
            'municipio': cenario_cfg.get('municipio'),
            'cod_ibge': cenario_cfg.get('cod_ibge'),
            'safra': cenario_cfg.get('safra'),
            'area_total_ha': int(cenario_cfg.get('area_total_ha', 0)),
            'n_talhoes': len(talhoes_cfg),
            'n_rotacoes': len(rotacoes_cfg),
        },
        'dados': {
            'status': 'MOCK',
            'observacao': (
                'Margens, riscos e janelas são MOCK — substituir pelos outputs do '
                'MC do M1 (margem/risco) e do ZARC via adequacao.py (janelas).'
            ),
            'gerado_em': datetime.now().isoformat(timespec='seconds'),
            'engine': (
                'engine/ — CP-SAT inteiro: lexicográfico margem→risco, fronteira '
                'ε-constraint com knee (Equilibrado) e Monte Carlo de robustez'
            ),
        },
        'talhoes': {
            nome: {'area_ha': int(info['area_ha']), 'grupo_solo': int(info['grupo_solo'])}
            for nome, info in talhoes_cfg.items()
        },
        'rotacoes': rotacoes_json,
        'plano_otimo': plano_otimo,
        'fronteira_pareto': fronteira_json,
        'knee': (
            _ponto_para_dict(
                knee, perfil='Equilibrado (knee)',
                descricao=PERFIL_DESCRICOES['equilibrado'])
            if knee else None
        ),
        'planos': planos,
        'robustez': _robustez_json(mc) if mc else None,
    }
    return results


# ------------------------------------------------------------------ relatório txt

def _secao_fronteira(frontier: List[Dict[str, Any]],
                     knee: Optional[Dict[str, Any]]) -> List[str]:
    linhas = [
        'FRONTEIRA DE PARETO — ε-constraint (mínimo risco sujeito a margem ≥ piso)',
        '-' * LARGURA,
        f"{'#':>2}  {'piso margem (R$)':>20}  {'margem (R$)':>18}  "
        f"{'risco (‰·ha)':>14}  {'ha sob risco':>12}  perfil",
    ]
    for indice, ponto in enumerate(frontier, start=1):
        margem, risco = _norm_ponto(ponto)
        perfil = ''
        if knee is not None and ponto is knee:
            perfil = 'Equilibrado (knee)'
        elif indice == 1:
            perfil = 'Arrojado'
        elif indice == len(frontier):
            perfil = 'Conservador'
        linhas.append(
            f'{indice:>2}.  {_reais(ponto["margem_floor"]):>20}  {_reais(margem):>18}  '
            f'{_fmt_br(risco):>14}  {_ha_sob_risco(risco):>12}  {perfil}'.rstrip()
        )
    if knee is not None:
        margem_k, risco_k = _norm_ponto(knee)
        linhas.append('')
        linhas.append(
            f'Knee point (perfil Equilibrado): margem {_reais(margem_k)} | '
            f'risco {_fmt_br(risco_k)} ‰·ha ({_ha_sob_risco(risco_k)} sob risco)'
        )
    linhas.append('')
    return linhas


def _secao_perfis(frontier: List[Dict[str, Any]],
                  knee: Optional[Dict[str, Any]],
                  talhoes_cfg: Dict[str, Any]) -> List[str]:
    linhas = ['PERFIS DE DECISÃO (o menu que vendemos no pitch)', '-' * LARGURA]
    if not frontier:
        linhas.append('Fronteira não gerada — rode com --pareto.')
        linhas.append('')
        return linhas
    arrojado = max(frontier, key=lambda p: _norm_ponto(p)[0])
    conservador = min(frontier, key=lambda p: (_norm_ponto(p)[1], -_norm_ponto(p)[0]))
    for perfil, ponto in (
        ('Arrojado', arrojado),
        ('Equilibrado (knee)', knee),
        ('Conservador', conservador),
    ):
        if ponto is None:
            continue
        margem, risco = _norm_ponto(ponto)
        linhas.append(
            f'{perfil}: margem {_reais(margem)} | risco {_fmt_br(risco)} ‰·ha '
            f'({_ha_sob_risco(risco)} sob risco)'
        )
        linhas.append(f'    {_plano_em_linha(ponto["plano"], talhoes_cfg)}')
    linhas.append('')
    return linhas


def _secao_robustez(mc: Optional[Dict[str, Any]]) -> List[str]:
    if not mc:
        return []
    settings = mc['settings']
    linhas = [
        f'ROBUSTEZ — MONTE CARLO (±{settings["jitter_percent"]}% nas margens; '
        f'{settings["runs"]} cenários; seed {settings["seed"]})',
        '-' * LARGURA,
        f'"{mc["frase_estabilidade"]}"',
        '',
        f"Cenários resolvidos: {mc['successful_runs']}/{settings['runs']}"
        f" (falhas: {mc['failed_runs']})",
        f"Estabilidade média: {mc['stability_mean']:.1%}"
        f" | melhor {mc['stability_max']:.1%} | pior {mc['stability_min']:.1%}",
        f"Cenários sem nenhuma mudança: {mc['pct_runs_sem_mudanca']:.1f}%",
        'Mudanças por cenário (nº de talhões com alocação diferente):',
    ]
    for mudanca, quantidade in sorted(mc['changed_distribution'].items()):
        porcento = 100.0 * quantidade / max(1, mc['successful_runs'])
        linhas.append(f'    {mudanca} talhão(ões) mudou/mudaram: {quantidade} cenários ({porcento:.1f}%)')
    linhas.append(
        f"Margem total nos cenários: média {_reais(mc['margem_total_media_centavos'])} | "
        f"mín {_reais(mc['margem_total_min_centavos'])} | "
        f"máx {_reais(mc['margem_total_max_centavos'])}"
    )
    linhas.append('')
    linhas.append('Retenção por rotação (em quantos cenários a rotação aparece):')
    for rotacao, info in mc['retention_por_rotacao'].items():
        marca = '[baseline]' if info['presente_no_baseline'] else '[fora do baseline]'
        linhas.append(
            f"    {rotacao:<16} {info['runs_presente']:>3}/{mc['successful_runs']}"
            f" ({info['fracao_runs']:.1%})  {marca}"
        )
    linhas.append('')
    return linhas


def _secao_configuracao(config: Dict[str, Any]) -> List[str]:
    cenario = config.get('cenario', {}) or {}
    settings = config.get('settings', {}) or {}
    talhoes_cfg = config.get('talhoes', {}) or {}
    rotacoes_cfg = config.get('rotacoes', {}) or {}
    pareto_cfg = config.get('pareto', {}) or {}
    mc_cfg = config.get('monte_carlo', {}) or {}

    linhas = ['CONFIGURAÇÃO E DADOS (TUDO MOCK — real: MC do M1 + ZARC)', '-' * LARGURA]
    talhoes_txt = ', '.join(
        f"{nome} {_fmt_br(info['area_ha'])} ha (solo grupo {info['grupo_solo']})"
        for nome, info in talhoes_cfg.items()
    )
    linhas.append(f'Talhões: {talhoes_txt}')
    linhas.append('Rotações (margem | risco | janelas viáveis por grupo de solo):')
    for nome, info in rotacoes_cfg.items():
        linhas.append(
            f"  {nome} — {' + '.join(info.get('culturas', []))}"
        )
        linhas.append(
            f"      margem {_reais(info['margem_esperada'])}/ha | "
            f"risco {_fmt_br(info['risco'])}‰ "
            f"(P[margem<0] ≈ {_fmt_br(info['risco'] / 10.0, 1)}%)"
        )
        janelas = {
            int(g): _formatar_decendios(list(ds))
            for g, ds in (info.get('janelas_viveis') or {}).items()
        }
        janelas_txt = ' | '.join(f'g{g}: {janelas[g]}' for g in sorted(janelas))
        linhas.append(f'      janelas: {janelas_txt}')
        chaves = [h.get('chave', '?') for h in (info.get('hipoteses') or [])]
        if chaves:
            linhas.append(f"      hipóteses MOCK: {', '.join(chaves)} (fonte_url 'MOCK://…')")
    linhas.append('')
    linhas.append(
        f"Settings: {settings.get('decendios', 36)} decêndios | "
        f"corte de risco ZARC ≤ {settings.get('risco_maximo_percent', 40)}% | "
        f"margem_em_centavos: {settings.get('margem_em_centavos', True)}"
    )
    linhas.append(
        f"Pareto: {pareto_cfg.get('points', 6)} pontos, piso de margem ≥ "
        f"{pareto_cfg.get('min_margem_ratio', 0.85)}× ótimo | "
        f"Monte Carlo: {mc_cfg.get('runs', 30)} runs, "
        f"±{mc_cfg.get('margem_jitter_percent', 10)}%, seed {mc_cfg.get('seed', 42)}"
    )
    linhas.append('')
    return linhas


def generate_report(config: Dict[str, Any],
                    solution: Dict[str, Any],
                    frontier: Optional[List[Dict[str, Any]]] = None,
                    knee: Optional[Dict[str, Any]] = None,
                    mc: Optional[Dict[str, Any]] = None) -> str:
    """Gera o relatório texto (PT-BR) do run completo."""
    frontier = frontier or []
    cenario = config.get('cenario', {}) or {}
    talhoes_cfg = config.get('talhoes', {}) or {}
    rotacoes_cfg = config.get('rotacoes', {}) or {}
    area_total = int(cenario.get('area_total_ha', 0))

    linhas: List[str] = []
    linhas.append('=' * LARGURA)
    linhas.append('HACKATOHM 2026 — DESAFIO EMBRAPA | MOTOR DE DECISÃO "O QUE PLANTAR"')
    linhas.append('=' * LARGURA)
    linhas.append(
        f"Cenário: {cenario.get('municipio')} (IBGE {cenario.get('cod_ibge')}) — "
        f"safra {cenario.get('safra')}"
    )
    linhas.append(
        f"Área: {_fmt_br(area_total)} ha em {len(talhoes_cfg)} talhões — "
        f"{len(rotacoes_cfg)} rotações candidatas | Status: {solution.get('status_name')}"
    )
    linhas.append('')
    linhas.append('PLANO ÓTIMO — lexicográfico (1º maximiza margem, 2º minimiza risco)')
    linhas.append('-' * LARGURA)
    for estagio in solution.get('stage_results', []):
        direcao = 'maximizar' if estagio['direction'] == 'max' else 'minimizar'
        valor = (
            _reais(estagio['value']) if estagio['stage'] == 'margem'
            else f"{_fmt_br(estagio['value'])} ‰·ha"
        )
        linhas.append(f"  estágio {estagio['stage']} ({direcao}): {valor}  [{estagio['status_name']}]")
    linhas.append('')
    linhas.extend(_formatar_plano(solution['plano'], talhoes_cfg))
    linhas.append('')
    linhas.append(
        f"Margem total: {_reais(solution['margem_total'])} "
        f"({_reais(solution['margem_total'] / max(1, area_total))}/ha)"
    )
    linhas.append(
        f"Risco total: {_fmt_br(solution['risco_total'])} ‰·ha ≈ "
        f"{_ha_sob_risco(solution['risco_total'])} com margem negativa esperada"
    )
    linhas.append('')

    if frontier:
        linhas.extend(_secao_fronteira(frontier, knee))
        linhas.extend(_secao_perfis(frontier, knee, talhoes_cfg))

    if mc:
        linhas.extend(_secao_robustez(mc))

    linhas.extend(_secao_configuracao(config))

    linhas.append('UNIDADES E LEGENDA', )
    linhas.append('-' * LARGURA)
    linhas.append('margem: centavos de R$/ha (CP-SAT inteiro); exibida em R$.')
    linhas.append(
        'risco: por-mil (‰) = P[margem < 0]×10 por ha; risco_total = Σ risco‰ × ha (‰·ha);'
    )
    linhas.append(
        '       "ha sob risco" = risco_total ÷ 1000 = hectares com margem negativa esperada.'
    )
    linhas.append('janelas: decêndios 1–36 (3/mês; 25–27 = setembro, 28–30 = outubro, 31–33 = novembro).')
    linhas.append('MOCK: números provisórios — margem/risco vêm do MC do M1; janelas do ZARC (adequacao.py).')
    linhas.append('=' * LARGURA)

    return '\n'.join(linhas)
