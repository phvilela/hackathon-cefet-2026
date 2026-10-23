#!/usr/bin/env python3
"""engine/atualiza_config.py — Camada 2 de wiring: fontes reais → config.yaml.

REGENERA o `engine/config.yaml` a partir das fontes reais (idempotente):
  · janelas_viveis ← engine/janelas_zarc.json (ZARC real, gerado pelo
    adequacao.py): para cada rotação, a lista "primeira" (janela PAREADA da
    1ª cultura) por grupo de solo 1/2/3. Lista VAZIA = rotação inviável
    naquele grupo no ZARC real (ex.: soja_milho no grupo 1 arenoso) — a
    validação do motor aceita, pois só exige ≥1 grupo viável por rotação.
  · margem/risco  ← engine/margens_mc.json (OPCIONAL — MC do M1; formato
    combinado: margem em CENTAVOS de R$/ha, risco em POR-MIL, inteiros).
    Se o arquivo NÃO existir: mantém as margens/riscos ATUAIS do config e
    registra a hipótese "margens ainda MOCK" em cada rotação
    (menos capital_pousio, que é custo de oportunidade, não vem do MC).

Preserva (não inventa nada): cenario, settings, talhões (campo irrigacao),
optimization, pareto, monte_carlo; ordem das rotações, culturas e hipóteses.
Rotações do config FORA do janelas_zarc.json (ex.: capital_pousio) mantêm
janelas e margens atuais.

Ao final da execução normal: revalida o config resultante com
`engine.validation.validate_config` e confere que as janelas do config são
IGUAIS às do janelas_zarc.json (resumo ✅/❌ no terminal).

Uso (na raiz do repo):
    python3 engine/atualiza_config.py               # regenera engine/config.yaml
    python3 engine/atualiza_config.py --dry-run     # diff resumido, sem escrever
    python3 engine/atualiza_config.py --margens engine/margens_mc.json
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

# padrão do engine/main.py: raiz do repo no sys.path + import do pacote engine
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.validation import ConfigValidationError, validate_config  # noqa: E402

# ------------------------------------------------------------------ constantes
ENGINE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = ENGINE_DIR / "config.yaml"
DEFAULT_JANELAS = ENGINE_DIR / "janelas_zarc.json"
DEFAULT_MARGENS = ENGINE_DIR / "margens_mc.json"

GRUPOS_SOLO = (1, 2, 3)
PORTAL_ZARC_FALLBACK = ("https://dados.agricultura.gov.br/dataset/"
                       "tabua-de-risco-zoneamento-agricola-de-risco-climatico")

# entrada gerenciada "janelas_zarc" (rastreabilidade das janelas REAIS)
CHAVE_JANELAS = "janelas_zarc"
VALOR_JANELAS_PAREADAS = "ZARC 2026/27 — janelas pareadas (ciclo Grupo I)"
VALOR_JANELAS_SOLTEIRA = "ZARC 2026/27 — janela de plantio (solteira, melhor ciclo)"
METODO_JANELAS = "engine/adequacao.py + portaria MAPA"

# entrada gerenciada "janela_segunda_cultura" (documental: o motor consome a 1ª)
CHAVE_SEGUNDA = "janela_segunda_cultura"
METODO_SEGUNDA = "janelas pareadas do ZARC — engine/adequacao.py"

# aviso gerenciado de margens MOCK (enquanto margens_mc.json não existir)
CHAVE_OBS_MOCK = "observacao"
VALOR_OBS_MOCK = "margens ainda MOCK — aguardando engine/margens_mc.json do MC do M1"
FONTE_OBS_MOCK = "MOCK://hackatohm/m1-monte-carlo-pendente"
METODO_OBS_MOCK = "margens provisórias do config.yaml (MOCK) — substituir pelo MC do M1"

# rotação "não plantar": margem não vem do MC do M1 → não recebe o aviso de MOCK
ROTACAO_SEM_AVISO_MOCK = "capital_pousio"


# ------------------------------------------------------------------- utilidades
def _erro(mensagem: str) -> None:
    raise SystemExit(f"ERRO: {mensagem}")


def _para_int(valor: object, campo: str) -> int:
    """CP-SAT só tem inteiros — margens, riscos, áreas e decêndios nunca float."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        _erro(f"{campo} deve ser um inteiro (recebi {valor!r}).")
    if isinstance(valor, float):
        if not valor.is_integer():
            _erro(f"{campo} deve ser um inteiro (recebi {valor!r}) — "
                  "CP-SAT não trabalha com float.")
        return int(valor)
    return int(valor)


def _caminho_legivel(caminho: Path) -> str:
    """Caminho relativo à raiz do repo (mais legível nos logs)."""
    try:
        return str(caminho.relative_to(REPO_ROOT))
    except ValueError:
        return str(caminho)


def _intervalos(decendios: list[int]) -> str:
    """[28, 29, 30] → '[28-30]'; [1, 28, 29] → '[1, 28-29]'; [] → '[]'."""
    if not decendios:
        return "[]"
    ds = sorted(set(decendios))
    partes: list[str] = []
    inicio = anterior = ds[0]
    for d in ds[1:]:
        if d == anterior + 1:
            anterior = d
            continue
        partes.append(str(inicio) if inicio == anterior else f"{inicio}-{anterior}")
        inicio = anterior = d
    partes.append(str(inicio) if inicio == anterior else f"{inicio}-{anterior}")
    return "[" + ", ".join(partes) + "]"


def _janelas_do_config(info_rotacao: dict) -> dict[int, list[int]]:
    """{grupo_solo: [decêndios]} da rotação (tolera chaves str ou int)."""
    saida: dict[int, list[int]] = {}
    for grupo, lista in (info_rotacao.get("janelas_viveis") or {}).items():
        try:
            g = int(grupo)
        except (TypeError, ValueError):
            continue
        saida[g] = [int(d) for d in (lista or [])]
    return saida


# -------------------------------------------------------------------- leituras
def carregar_yaml(caminho: Path) -> dict:
    try:
        texto = caminho.read_text(encoding="utf-8")
    except FileNotFoundError:
        _erro(f"config não encontrado: {caminho}")
    try:
        dados = yaml.safe_load(texto)
    except yaml.YAMLError as exc:
        _erro(f"{caminho} não é um YAML válido: {exc}")
    if not isinstance(dados, dict):
        _erro(f"{caminho} deve ter um mapping na raiz.")
    return dados


def carregar_json(caminho: Path, descricao: str) -> dict:
    try:
        texto = caminho.read_text(encoding="utf-8")
    except FileNotFoundError:
        _erro(f"{descricao} não encontrado: {caminho}")
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as exc:
        _erro(f"{descricao} {caminho} não é um JSON válido: {exc}")
    if not isinstance(dados, dict):
        _erro(f"{descricao} {caminho} deve ter um objeto na raiz.")
    return dados


def janelas_por_rotacao(dados_janelas: dict, n_decendios: int) -> dict[str, dict[int, list[int]]]:
    """{rotação: {grupo_solo: lista 'primeira'}} — janelas REAIS do ZARC.

    A `janelas_viveis` da ROTAÇÃO no config = lista `primeira` (janela
    pareada da 1ª cultura). Rotações com 2ª cultura também têm `segunda`
    no JSON — hoje o motor só consome a 1ª; a 2ª fica documentada lá.
    """
    rotacoes = (dados_janelas or {}).get("rotacoes") or {}
    if not isinstance(rotacoes, dict) or not rotacoes:
        _erro("janelas_zarc.json não tem a seção 'rotacoes' — rode engine/adequacao.py.")
    saida: dict[str, dict[int, list[int]]] = {}
    for rotacao, grupos in rotacoes.items():
        if not isinstance(grupos, dict):
            _erro(f"janelas_zarc.json: rotacoes.{rotacao} deve ser um mapping por grupo de solo.")
        por_grupo: dict[int, list[int]] = {}
        for grupo in GRUPOS_SOLO:
            info_grupo = grupos.get(str(grupo)) or {}
            if not isinstance(info_grupo, dict):
                _erro(f"janelas_zarc.json: rotacoes.{rotacao}.['{grupo}'] deve ser um mapping.")
            primeira = info_grupo.get("primeira")
            if primeira is None:
                primeira = []
            if not isinstance(primeira, list):
                _erro(f"janelas_zarc.json: rotacoes.{rotacao}.['{grupo}'].primeira deve ser uma lista.")
            decendios: list[int] = []
            for d in primeira:
                v = _para_int(d, f"janelas_zarc.rotacoes.{rotacao}.['{grupo}'].primeira")
                if not (1 <= v <= n_decendios):
                    _erro(f"janelas_zarc.rotacoes.{rotacao}.['{grupo}']: decêndio {v} "
                          f"fora da faixa 1..{n_decendios}.")
                if v in decendios:
                    _erro(f"janelas_zarc.rotacoes.{rotacao}.['{grupo}']: decêndio {v} repetido.")
                decendios.append(v)
            por_grupo[grupo] = decendios
        saida[str(rotacao)] = por_grupo
    return saida


def rotacoes_com_segunda(dados_janelas: dict) -> set[str]:
    """Rotações com 2ª cultura (janela pareada) no janelas_zarc.json."""
    com_segunda: set[str] = set()
    for rotacao, grupos in ((dados_janelas or {}).get("rotacoes") or {}).items():
        if any(isinstance(g, dict) and "segunda" in g for g in grupos.values()):
            com_segunda.add(str(rotacao))
    return com_segunda


def segunda_por_rotacao(dados_janelas: dict, n_decendios: int) -> dict[str, dict[int, list[int]]]:
    """{rotação: {grupo_solo: lista 'segunda'}} — janela pareada da 2ª cultura.

    Só rotações com 2ª cultura entram; usada para a hipótese rastreável
    'janela_segunda_cultura' no config (o motor só consome a janela da 1ª)."""
    saida: dict[str, dict[int, list[int]]] = {}
    for rotacao, grupos in ((dados_janelas or {}).get("rotacoes") or {}).items():
        por_grupo: dict[int, list[int]] = {}
        for grupo in GRUPOS_SOLO:
            info_grupo = grupos.get(str(grupo)) or {}
            if not isinstance(info_grupo, dict):
                continue
            segunda = info_grupo.get("segunda")
            if not isinstance(segunda, list):
                continue
            decendios: list[int] = []
            for d in segunda:
                v = _para_int(d, f"janelas_zarc.rotacoes.{rotacao}.['{grupo}'].segunda")
                if 1 <= v <= n_decendios:
                    decendios.append(v)
            por_grupo[grupo] = decendios
        if por_grupo:
            saida[str(rotacao)] = por_grupo
    return saida


def _valor_segunda(por_grupo: dict[int, list[int]]) -> str:
    """'plantio da 2ª cultura — g1: sem janela (inviável) · g2: [2-3] · g3: [2-4]'"""
    partes = []
    for grupo in GRUPOS_SOLO:
        if grupo not in por_grupo:
            continue
        js = por_grupo[grupo]
        partes.append(f"g{grupo}: {_intervalos(js) if js else 'sem janela (inviável)'}")
    return "plantio da 2ª cultura — " + " · ".join(partes)


def margens_por_rotacao(dados_margens: dict) -> dict[str, dict]:
    """{rotação: {margem_esperada, risco, hipoteses}} — MC do M1 (centavos/ha, ‰)."""
    saida: dict[str, dict] = {}
    for rotacao, info in (dados_margens or {}).items():
        rotacao = str(rotacao)
        if not isinstance(info, dict):
            _erro(f"margens_mc.json: '{rotacao}' deve ser um mapping.")
        margem = _para_int(info.get("margem_esperada"), f"margens_mc.{rotacao}.margem_esperada")
        risco = _para_int(info.get("risco"), f"margens_mc.{rotacao}.risco")
        if margem <= 0:
            _erro(f"margens_mc.{rotacao}.margem_esperada deve ser > 0 "
                  f"(centavos de R$/ha; recebi {margem}).")
        if not (0 <= risco <= 1000):
            _erro(f"margens_mc.{rotacao}.risco deve estar em 0..1000 por-mil (recebi {risco}).")
        hipoteses: list[dict] = []
        for entrada in info.get("hipoteses") or []:
            if not isinstance(entrada, dict):
                _erro(f"margens_mc.{rotacao}.hipoteses deve ser uma lista de mappings.")
            hipoteses.append({
                "chave": str(entrada.get("chave", "")),
                "valor": str(entrada.get("valor", "")),
                "fonte_url": str(entrada.get("fonte_url", "")),
                "metodo": str(entrada.get("metodo", "")),
            })
        saida[rotacao] = {"margem_esperada": margem, "risco": risco, "hipoteses": hipoteses}
    return saida


# ----------------------------------------------------------------- regeneração
def _remontar_hipoteses(hipoteses_atuais: list[dict],
                        rotacao: str,
                        margem_coberta: bool,
                        tem_janelas_reais: bool,
                        com_segunda: set[str],
                        segundas: dict[str, dict[int, list[int]]],
                        margens: dict[str, dict],
                        portal: str) -> list[dict]:
    """Remonta a lista de hipóteses preservando o que existe:

    · entradas de JANELA legadas (chave 'janela*' ou método citando ZARC) são
      DESCARTADAS quando há janelas reais — substituídas pelas gerenciadas;
      sem janelas reais, são preservadas;
    · entradas de MARGEM são substituídas pelas do margens_mc.json, se ele
      cobrir a rotação; senão são preservadas (mas o aviso gerenciado de
      "margens ainda MOCK" substitui um 'observacao' de margem anterior);
    · entradas gerenciadas ('janelas_zarc', 'janela_segunda_cultura' e o aviso
      de MOCK) são recriadas no fim da lista — re-rodar não duplica (idempotente).
    """
    mantidas: list[dict] = []
    for entrada in hipoteses_atuais:
        if not isinstance(entrada, dict):
            continue
        chave = str(entrada.get("chave", ""))
        metodo = str(entrada.get("metodo", ""))
        eh_de_janela = chave.startswith("janela") or "zarc" in metodo.lower()
        if chave in (CHAVE_JANELAS, CHAVE_SEGUNDA):
            continue  # gerenciadas: recriadas abaixo
        if tem_janelas_reais and eh_de_janela:
            continue  # legado MOCK de janela — substituído pelas gerenciadas (ZARC real)
        if margem_coberta and not eh_de_janela:
            continue  # hipóteses de margem vêm do margens_mc.json
        if (not margem_coberta and not eh_de_janela
                and chave == CHAVE_OBS_MOCK and rotacao != ROTACAO_SEM_AVISO_MOCK):
            continue  # aviso gerenciado de margem MOCK: recriado abaixo
        mantidas.append(dict(entrada))

    extras: list[dict] = []
    if margem_coberta:
        extras += [dict(h) for h in margens[rotacao]["hipoteses"]
                   if str(h.get("chave")) not in (CHAVE_JANELAS, CHAVE_SEGUNDA)]
    elif rotacao != ROTACAO_SEM_AVISO_MOCK:
        extras.append({
            "chave": CHAVE_OBS_MOCK,
            "valor": VALOR_OBS_MOCK,
            "fonte_url": FONTE_OBS_MOCK,
            "metodo": METODO_OBS_MOCK,
        })
    if tem_janelas_reais:
        valor = (VALOR_JANELAS_PAREADAS if rotacao in com_segunda
                 else VALOR_JANELAS_SOLTEIRA)
        extras.append({
            "chave": CHAVE_JANELAS,
            "valor": valor,
            "fonte_url": portal,
            "metodo": METODO_JANELAS,
        })
        if rotacao in com_segunda and rotacao in segundas:
            extras.append({
                "chave": CHAVE_SEGUNDA,
                "valor": _valor_segunda(segundas[rotacao]),
                "fonte_url": portal,
                "metodo": METODO_SEGUNDA,
            })
    return mantidas + extras


def regenerar_config(config_atual: dict,
                     janelas: dict[str, dict[int, list[int]]],
                     com_segunda: set[str],
                     segundas: dict[str, dict[int, list[int]]],
                     margens: dict[str, dict],
                     portal: str) -> tuple[dict, list[str]]:
    """Novo config a partir do atual + fontes reais. Preserva tudo que não
    vem das fontes (cenário, settings, talhões, optimization, pareto,
    monte_carlo, ordem das rotações, culturas)."""
    novo = copy.deepcopy(config_atual)
    rotacoes = novo.get("rotacoes")
    if not isinstance(rotacoes, dict) or not rotacoes:
        _erro("config atual não tem a seção 'rotacoes'.")
    avisos: list[str] = []

    for rotacao in janelas:
        if rotacao not in rotacoes:
            avisos.append(f"rotação '{rotacao}' está no janelas_zarc.json mas NÃO no "
                          "config — ignorada (o config manda no que existe).")
    for rotacao in margens:
        if rotacao not in rotacoes:
            avisos.append(f"rotação '{rotacao}' está no margens_mc.json mas NÃO no "
                          "config — ignorada (o config manda no que existe).")

    for rotacao, info in rotacoes.items():
        tem_janelas_reais = rotacao in janelas
        margem_coberta = rotacao in margens

        # 1) janelas REAIS do ZARC (lista vazia = inviável no grupo — informação, não erro)
        if tem_janelas_reais:
            info["janelas_viveis"] = {g: list(janelas[rotacao][g]) for g in GRUPOS_SOLO}

        # 2) margens/riscos do MC do M1 (se existirem); senão ficam as atuais (MOCK)
        if margem_coberta:
            info["margem_esperada"] = int(margens[rotacao]["margem_esperada"])
            info["risco"] = int(margens[rotacao]["risco"])

        # 3) hipóteses: preserva e soma as entradas gerenciadas
        info["hipoteses"] = _remontar_hipoteses(
            info.get("hipoteses") or [], rotacao, margem_coberta,
            tem_janelas_reais, com_segunda, segundas, margens, portal,
        )
    return novo, avisos


# ------------------------------------------------------------- escrita do YAML
def _yaml_texto(valor: str) -> str:
    return '"' + str(valor).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _yaml_escalar(valor: object) -> str:
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, int):
        return str(valor)
    if isinstance(valor, float):
        return repr(valor)
    if valor is None:
        return "null"
    return _yaml_texto(valor)


def _yaml_chave(chave: object) -> str:
    texto = str(chave)
    if texto and all(c.isalnum() or c in "_-." for c in texto):
        return texto
    return _yaml_texto(texto)


def _yaml_lista(valores: list) -> str:
    return "[" + ", ".join(_yaml_escalar(v) for v in valores) + "]"


def _yaml_mapa_fluxo(dicionario: dict) -> str:
    return "{ " + ", ".join(
        f"{_yaml_chave(k)}: {_yaml_escalar(v)}" for k, v in dicionario.items()
    ) + " }"


def _linhas_bloco(dicionario: dict, nivel: int = 0) -> list[str]:
    """Dump genérico em estilo bloco (usado nas seções simples)."""
    recuo = "  " * nivel
    linhas: list[str] = []
    for chave, valor in dicionario.items():
        if isinstance(valor, dict):
            linhas.append(f"{recuo}{_yaml_chave(chave)}:")
            linhas.extend(_linhas_bloco(valor, nivel + 1))
        elif isinstance(valor, list):
            linhas.append(f"{recuo}{_yaml_chave(chave)}: {_yaml_lista(valor)}")
        else:
            linhas.append(f"{recuo}{_yaml_chave(chave)}: {_yaml_escalar(valor)}")
    return linhas


def _cabecalho(config: dict, margens_status: str, data: str) -> list[str]:
    cenario = config.get("cenario") or {}
    talhoes = config.get("talhoes") or {}
    largura = 78
    return [
        "=" * largura,
        "# HackatOhm 2026 — desafio Embrapa | Motor de decisão \"o que plantar\"",
        f"# Fazenda: {cenario.get('area_total_ha', '?')} ha em {len(talhoes)} talhões — "
        f"{cenario.get('municipio', '?')} (safra {cenario.get('safra', '?')})",
        "#",
        f"# Regenerado por engine/atualiza_config.py em {data} — fontes:",
        "#   · janelas_viveis → REAIS: engine/janelas_zarc.json (ZARC via adequacao.py)",
        f"#   · margem/risco   → {margens_status}",
        "#",
        "# ⚠ AVISO MOCK vs REAL:",
        "#   - janelas_viveis JÁ são reais (ZARC, safra 2026/27). Lista VAZIA = rotação",
        "#     INVIÁVEL naquele grupo de solo (ex.: soja_milho no arenoso — a safrinha",
        "#     não fecha) — a validação do motor aceita (só exige ≥1 grupo viável).",
        "#   - margem_esperada/risco ver o status acima; hipóteses de cada rotação",
        "#     registram a fonte e o método (rastreabilidade).",
        "#",
        "# Unidades (CP-SAT só tem inteiros — nunca float no objetivo):",
        "#   margem_esperada: centavos de R$ por hectare (R$ 4.180/ha → 418000)",
        "#   risco: por-mil (‰) = P(margem < 0) × 10 (12% → 120)",
        "#   janelas_viveis: decêndios 1–36 (dec25–27 = set … dec36 = 21–31 dez);",
        "#     a janela da ROTAÇÃO = decêndios de plantio da 1ª cultura, PAREADA com",
        "#     a 2ª (só entram decêndios que deixam a safrinha caber — ciclo Grupo I).",
        "=" * largura,
        "",
    ]


def serializar_yaml(config: dict, margens_status: str,
                    janelas_reais: set[str] | None = None) -> str:
    """Escreve o YAML final (legível, com cabeçalho — sem comentários inline)."""
    data = datetime.now().strftime("%d/%m/%Y")
    linhas = [f"# {l}" if not l.startswith("#") and l.strip() else l
              for l in _cabecalho(config, margens_status, data)]

    # seções preservadas e simples: dump bloco genérico
    for secao in ("cenario", "settings"):
        if secao in config:
            linhas.append(f"{secao}:")
            linhas.extend(_linhas_bloco(config[secao], 1))
            linhas.append("")

    if "talhoes" in config:
        linhas.append("talhoes:   # gerado do formulário (tela 1); "
                      "irrigacao: true habilita manejo irrigado (v0 = só sequeiro)")
        for nome, info in (config["talhoes"] or {}).items():
            linhas.append(f"  {_yaml_chave(nome)}: {_yaml_mapa_fluxo(info)}")
        linhas.append("")

    if "rotacoes" in config:
        linhas.append("rotacoes:  # coeficientes por rotação — hipóteses citam a fonte de cada número")
        for nome, info in (config["rotacoes"] or {}).items():
            linhas.append(f"  {_yaml_chave(nome)}:")
            if "culturas" in info:
                linhas.append(f"    culturas: {_yaml_lista(info['culturas'])}")
            linhas.append(f"    margem_esperada: {int(info['margem_esperada'])}"
                          "   # centavos de R$/ha")
            linhas.append(f"    risco: {int(info['risco'])}"
                          "   # P[margem<0] em por-mil (‰)")
            origem = ("decêndios (ZARC real)" if nome in (janelas_reais or set())
                      else "decêndios mantidos (rotação fora do janelas_zarc.json)")
            linhas.append(f"    janelas_viveis:   # por grupo de solo — {origem}")
            janelas = _janelas_do_config(info)
            for grupo in sorted(janelas):
                linhas.append(f"      {grupo}: {_yaml_lista(janelas[grupo])}")
            hipoteses = info.get("hipoteses") or []
            if hipoteses:
                linhas.append("    hipoteses:")
                for entrada in hipoteses:
                    linhas.append(f"      - {_yaml_mapa_fluxo(entrada)}")
            linhas.append("")

    for secao in ("optimization", "pareto", "monte_carlo"):
        if secao in config:
            linhas.append(f"{secao}:")
            linhas.extend(_linhas_bloco(config[secao], 1))
            linhas.append("")

    # qualquer seção extra (defensivo) — dump genérico
    conhecidas = {"cenario", "settings", "talhoes", "rotacoes",
                  "optimization", "pareto", "monte_carlo"}
    for secao, valor in config.items():
        if secao in conhecidas:
            continue
        if isinstance(valor, dict):
            linhas.append(f"{_yaml_chave(secao)}:")
            linhas.extend(_linhas_bloco(valor, 1))
        else:
            linhas.append(f"{_yaml_chave(secao)}: {_yaml_escalar(valor)}")
        linhas.append("")

    return "\n".join(linhas).rstrip() + "\n"


# ---------------------------------------------------------------- relatórios
def imprimir_diff(antes: dict, depois: dict, janelas: dict, margens: dict) -> None:
    """Diff resumido do config atual → regenerado (é o que o --dry-run mostra)."""
    mudancas_janelas = 0
    mudancas_margens = 0
    print("=" * 78)
    print("DIFF RESUMIDO — config atual → regenerado")
    print("=" * 78)
    for rotacao, info in (antes.get("rotacoes") or {}).items():
        nova_info = (depois.get("rotacoes") or {}).get(rotacao, {})
        culturas = " + ".join(str(c) for c in info.get("culturas") or [])
        print(f"{rotacao} ({culturas}):")
        if rotacao in janelas:
            antigas = _janelas_do_config(info)
            novas = _janelas_do_config(nova_info)
            for grupo in GRUPOS_SOLO:
                ja, jn = antigas.get(grupo, []), novas.get(grupo, [])
                if ja != jn:
                    mudancas_janelas += 1
                    nota = "  ← INVIÁVEL no ZARC real (rotação não fecha nesse solo)" if not jn else ""
                    print(f"    janelas g{grupo}: {_intervalos(ja)} → {_intervalos(jn)}{nota}")
        else:
            print("    janelas: mantidas (rotação fora do janelas_zarc.json — ex.: opção 'não plantar')")

        ma, ra = int(info.get("margem_esperada", 0)), int(info.get("risco", 0))
        mn, rn = int(nova_info.get("margem_esperada", ma)), int(nova_info.get("risco", ra))
        if (ma, ra) != (mn, rn):
            mudancas_margens += 1
            print(f"    margem: {ma} → {mn} ¢/ha | risco: {ra} → {rn} ‰ (margens_mc.json)")
        elif rotacao in margens:
            print("    margem/risco: iguais ao margens_mc.json")
        else:
            print(f"    margem/risco: mantidos — {ma} ¢/ha | {ra} ‰ (MOCK)")

        chaves_antigas = [str(h.get("chave")) for h in info.get("hipoteses") or []]
        chaves_novas = [str(h.get("chave")) for h in nova_info.get("hipoteses") or []]
        adicionadas = [c for c in chaves_novas if c not in chaves_antigas]
        removidas = [c for c in chaves_antigas if c not in chaves_novas]
        if adicionadas or removidas:
            partes = []
            if adicionadas:
                partes.append(f"+ {', '.join(adicionadas)}")
            if removidas:
                partes.append(f"− {', '.join(removidas)}")
            print(f"    hipóteses: {' | '.join(partes)}")
        print()

    print(f"RESUMO: {mudancas_janelas} janela(s) de grupo alterada(s) | "
          f"{mudancas_margens} rotação(ões) com margem/risco atualizado(s)")
    print("=" * 78)


def _conferir_janelas(config_carregado: dict, janelas: dict) -> tuple[int, int, list[str]]:
    """Confera: janelas do config (em disco) == janelas do janelas_zarc.json."""
    detalhes: list[str] = []
    ok = total = 0
    rotacoes = config_carregado.get("rotacoes") or {}
    for rotacao, por_grupo in janelas.items():
        if rotacao not in rotacoes:
            continue
        total += 1
        atuais = _janelas_do_config(rotacoes[rotacao])
        bate = all(atuais.get(g, []) == list(por_grupo[g]) for g in GRUPOS_SOLO)
        if bate:
            ok += 1
        detalhes.append(
            f"{'✅' if bate else '❌'} {rotacao}: "
            + " | ".join(f"g{g} {_intervalos(por_grupo[g])}" for g in GRUPOS_SOLO)
        )
    for rotacao in rotacoes:
        if rotacao not in janelas:
            detalhes.append(f"➖ {rotacao}: fora do janelas_zarc.json — janelas mantidas "
                            f"({_intervalos(list(_janelas_do_config(rotacoes[rotacao]).get(1) or []))} …)")
    return ok, total, detalhes


def revalidar(caminho_config: Path, novo_config: dict, janelas: dict,
              do_disco: bool) -> bool:
    """Revalida o config resultante (padrão do engine/main.py) e confere as
    janelas contra o janelas_zarc.json. Retorna True se está tudo ✅."""
    origem = f"relido do disco: {caminho_config}" if do_disco else "em memória (dry-run)"
    print()
    print(f"VALIDAÇÃO DO CONFIG REGENERADO ({origem})")
    try:
        if do_disco:
            config_final = carregar_yaml(caminho_config)
        else:
            config_final = copy.deepcopy(novo_config)
        validate_config(config_final)
        print("  ✅ engine.validation.validate_config — config OK "
              f"({len(config_final.get('rotacoes') or {})} rotações, "
              f"{len(config_final.get('talhoes') or {})} talhões)")
    except ConfigValidationError as exc:
        print("  ❌ validação do motor falhou:")
        for erro in exc.errors:
            print(f"      - {erro}")
        return False

    ok, total, detalhes = _conferir_janelas(config_final, janelas)
    if ok == total:
        print(f"  ✅ janelas do config == janelas do janelas_zarc.json ({ok}/{total} rotações)")
    else:
        print(f"  ❌ janelas divergem do janelas_zarc.json ({ok}/{total} rotações)")
    for linha in detalhes:
        print(f"      {linha}")
    return ok == total


# ---------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Regenera o engine/config.yaml a partir das fontes reais "
                    "(ZARC + MC do M1) — idempotente.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos (na raiz do repo):\n"
            "  python3 engine/atualiza_config.py\n"
            "  python3 engine/atualiza_config.py --dry-run\n"
            "  python3 engine/atualiza_config.py --config engine/config.yaml \\\n"
            "       --janelas engine/janelas_zarc.json --margens engine/margens_mc.json\n"
        ),
    )
    parser.add_argument("--config", default=None,
                        help="caminho do config YAML (default: engine/config.yaml)")
    parser.add_argument("--janelas", default=None,
                        help="caminho do janelas_zarc.json (default: engine/janelas_zarc.json)")
    parser.add_argument("--margens", default=None,
                        help="caminho do margens_mc.json (default: engine/margens_mc.json; "
                             "se ausente, as margens/riscos atuais são mantidos — MOCK)")
    parser.add_argument("--dry-run", action="store_true",
                        help="imprime o diff resumido e valida, sem escrever no disco")
    args = parser.parse_args(argv)

    config_path = Path(args.config) if args.config else DEFAULT_CONFIG
    janelas_path = Path(args.janelas) if args.janelas else DEFAULT_JANELAS
    margens_path = Path(args.margens) if args.margens else DEFAULT_MARGENS

    # ------------------------------------------------------------- 1) fontes
    config_atual = carregar_yaml(config_path)
    n_decendios = int((config_atual.get("settings") or {}).get("decendios", 36))
    dados_janelas = carregar_json(janelas_path, "janelas_zarc.json")
    janelas = janelas_por_rotacao(dados_janelas, n_decendios)
    com_segunda = rotacoes_com_segunda(dados_janelas)
    segundas = segunda_por_rotacao(dados_janelas, n_decendios)
    portal = str(((dados_janelas.get("fonte") or {}).get("portal")) or PORTAL_ZARC_FALLBACK)

    if margens_path.is_file():
        margens = margens_por_rotacao(carregar_json(margens_path, "margens_mc.json"))
        margens_status = f"REAIS: {_caminho_legivel(margens_path)} (MC do M1)"
    elif args.margens:
        _erro(f"--margens {margens_path} não existe.")
    else:
        margens = {}
        margens_status = (f"MOCK: {_caminho_legivel(margens_path)} AUSENTE — "
                           "margens/riscos atuais mantidos (aguardando MC do M1)")

    print("FONTES")
    print(f"  · config atual : {_caminho_legivel(config_path)}")
    print(f"  · janelas     : {_caminho_legivel(janelas_path)} — REAIS (ZARC {portal})")
    print(f"  · margens     : {margens_status}")
    print()

    # -------------------------------------------------------- 2) regenerar
    novo, avisos = regenerar_config(config_atual, janelas, com_segunda, segundas, margens, portal)
    for aviso in avisos:
        print(f"AVISO: {aviso}")

    # ----------------------------------------------------------- 3) diff
    imprimir_diff(config_atual, novo, janelas, margens)

    # ------------------------------------------- 4) escrever (ou só dry-run)
    if args.dry_run:
        print("DRY-RUN — config NÃO foi escrito.")
        ok = revalidar(config_path, novo, janelas, do_disco=False)
        raise SystemExit(0 if ok else 1)

    texto = serializar_yaml(novo, margens_status, janelas_reais=set(janelas.keys()))
    config_path.write_text(texto, encoding="utf-8")
    print(f"OK → {_caminho_legivel(config_path)} regenerado "
          f"({len(texto.splitlines())} linhas)")

    # ------------------------------------------- 5) revalidar do disco + ✅/❌
    ok = revalidar(config_path, novo, janelas, do_disco=True)
    if ok:
        print()
        print("✅ Config regenerado, validado e consistente com o janelas_zarc.json.")
    else:
        print()
        print("❌ Config regenerado com problemas — confira as mensagens acima.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
