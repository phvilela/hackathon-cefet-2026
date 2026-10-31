"""Gráficos do motor.

`generate_pareto_frontier_scatter` — scatter margem × risco da fronteira,
com knee destacado, perfis rotulados e nota de rodapé opcional (o chamador
informa o status dos dados; nada de nota fixa — o gráfico já exibiu
"Dados MOCK" com dados reais por muito tempo).
Unidades (documentadas no próprio gráfico):
    x = "área sob risco" = Σ (risco‰ × ha) ÷ 1000  → ha com margem negativa esperada
    y = margem total em R$ (centavos do modelo ÷ 100)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)

try:
    plt.style.use('seaborn-v0_8-whitegrid')
except Exception:
    plt.style.use('ggplot')


def _ensure_parent_dir(output_path: str | Path) -> Path:
    path = Path(output_path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _finalize(fig: plt.Figure, output_path: str | Path) -> Path:
    path = _ensure_parent_dir(output_path)
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches='tight')
    plt.close(fig)
    logger.info('Gráfico salvo em %s', path)
    return path


def generate_pareto_frontier_scatter(
    frontier: Sequence[Dict[str, Any]],
    knee: Optional[Dict[str, Any]] = None,
    path: str | Path = 'engine/out/pareto_frontier.png',
    nota_rodape: Optional[str] = None,
) -> Optional[Path]:
    """Scatter da fronteira margem × risco com knee e perfis destacados.

    Eixo x em "ha sob risco" (Σ risco‰ × ha ÷ 1000) e eixo y em R$ milhões
    (centavos ÷ 100). Rótulos: Arrojado (maior margem), Equilibrado (knee) e
    Conservador (menor risco). `nota_rodape` (ex.: status dos dados) é
    opcional; quando omitida, nenhuma nota é estampada no gráfico.
    """
    if not frontier:
        return None

    pontos = sorted(frontier, key=lambda p: (int(p.get('risco', 0)), -int(p.get('margem', 0))))
    xs = [int(p['risco']) / 1000.0 for p in pontos]               # ha sob risco
    ys = [int(p['margem']) / 100.0 / 1_000_000.0 for p in pontos]  # R$ milhões

    fig, ax = plt.subplots(figsize=(10, 6.5))
    ax.plot(xs, ys, linestyle='--', linewidth=1.0, alpha=0.45, color='#555555', zorder=2)
    ax.scatter(xs, ys, s=95, c='#4c72b0', edgecolors='#333333', linewidths=0.6, zorder=3)

    # rótulo de margem em cada ponto
    for ponto, x, y in zip(pontos, xs, ys):
        ax.annotate(
            f'R$ {y:.2f} M'.replace('.', ','),
            (x, y), textcoords='offset points', xytext=(7, 7),
            fontsize=8, color='#555555',
        )

    arrojado = max(pontos, key=lambda p: int(p['margem']))
    conservador = min(pontos, key=lambda p: (int(p['risco']), -int(p['margem'])))

    def _coord(ponto: Dict[str, Any]) -> tuple:
        return int(ponto['risco']) / 1000.0, int(ponto['margem']) / 100.0 / 1_000_000.0

    if knee is not None and knee is not arrojado and knee is not conservador:
        kx, ky = _coord(knee)
        ax.scatter(kx, ky, marker='*', s=420, c='#d62728',
                   edgecolors='black', linewidths=0.8, zorder=5)
        ax.annotate(
            'Equilibrado (knee)', (kx, ky), textcoords='offset points',
            xytext=(12, -4), fontsize=11, fontweight='bold', color='#d62728',
        )

    ax.annotate(
        'Arrojado', _coord(arrojado), textcoords='offset points',
        xytext=(-14, 12), fontsize=11, fontweight='bold', color='#d62728',
    )
    ax.annotate(
        'Conservador', _coord(conservador), textcoords='offset points',
        xytext=(8, -18), fontsize=11, fontweight='bold', color='#2ca02c',
    )

    ax.set_title(
        'Fronteira de Pareto — margem × risco (Patos de Minas, 600 ha, 3 talhões)',
        fontsize=13, fontweight='bold',
    )
    ax.set_xlabel(
        'Área sob risco esperada (ha) — Σ risco‰ × ha ÷ 1000',
        fontsize=11,
    )
    ax.set_ylabel('Margem total (R$ milhões)', fontsize=11)
    ax.grid(True, alpha=0.3, linestyle=':')

    if nota_rodape:
        fig.text(
            0.99, 0.005,
            nota_rodape,
            ha='right', va='bottom', fontsize=8, style='italic', color='#777777',
        )

    return _finalize(fig, path)
