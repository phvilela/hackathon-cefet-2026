#!/usr/bin/env python3
"""Gera `web/src/data/zarc.json` a partir de `engine/janelas_zarc.json`.

O arquivo do motor já tem exatamente a forma que o frontend consome:
  culturas[cultura][grupo] = {decendios, risco_por_decendio, solo_usado,
                              ciclos_disponiveis}
  rotacoes[rotacao][grupo]  = {primeira, segunda, ...}
além das chaves de topo (cenario, fonte, premissas, sanity), que são
preservadas sem alteração. As chaves de cultura/rotação são as mesmas do
motor (convenção comprovada: hoje os dois arquivos são idênticos), então o
mapeamento é 1:1 — culturas novas (girassol, amendoim, arroz, algodão...) e
rotações novas (girassol_solteira, amendoim_solteira, arroz_solteira,
algodao_solteira, soja_feijao2) passam direto.

Uso:
  python scripts/gera_zarc_web.py          # regenera web/src/data/zarc.json
  python scripts/gera_zarc_web.py --check  # CI: sai 1 se o arquivo estiver desatualizado

O script é determinístico (mesma entrada ⇒ mesmos bytes), serializando com
indent=2 e ensure_ascii=False, sem newline final — o mesmo formato do arquivo
atual, para que rodá-lo sobre o engine atual seja um no-op.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ENGINE_PADRAO = RAIZ / "engine" / "janelas_zarc.json"
WEB_PADRAO = RAIZ / "web" / "src" / "data" / "zarc.json"

GRUPOS = {"1", "2", "3"}
CAMPOS_CULTURA = {"decendios", "risco_por_decendio", "solo_usado", "ciclos_disponiveis"}


def carregar(caminho: Path) -> dict:
    if not caminho.is_file():
        sys.exit(f"ERRO: arquivo não encontrado: {caminho}")
    with caminho.open(encoding="utf-8") as fh:
        dados = json.load(fh)
    if not isinstance(dados, dict):
        sys.exit(f"ERRO: {caminho} não contém um objeto JSON de topo.")
    return dados


def validar(dados: dict, origem: Path) -> None:
    """Valida a forma do contrato do motor; falha cedo com mensagem clara."""
    culturas = dados.get("culturas")
    rotacoes = dados.get("rotacoes")
    if not isinstance(culturas, dict) or not culturas:
        sys.exit(f"ERRO: {origem} sem a seção 'culturas'.")
    if not isinstance(rotacoes, dict):
        sys.exit(f"ERRO: {origem} sem a seção 'rotacoes'.")

    for cultura, grupos in culturas.items():
        if not isinstance(grupos, dict) or not set(grupos) <= GRUPOS:
            sys.exit(f"ERRO: culturas[{cultura}] com grupos inesperados: {sorted(grupos)}")
        for grupo, janela in grupos.items():
            if not isinstance(janela, dict):
                sys.exit(f"ERRO: culturas[{cultura}][{grupo}] não é um objeto.")
            if not isinstance(janela.get("decendios"), list):
                sys.exit(
                    f"ERRO: culturas[{cultura}][{grupo}] sem a lista 'decendios'."
                )
            if not janela.get("solo_usado"):
                sys.exit(f"ERRO: culturas[{cultura}][{grupo}] sem 'solo_usado'.")
            # Convenção do motor: sem janela no grupo (decendios vazio) os
            # campos de risco/ciclos são omitidos e entra um 'aviso'.
            if janela["decendios"]:
                faltando = CAMPOS_CULTURA - set(janela)
                if faltando:
                    sys.exit(
                        f"ERRO: culturas[{cultura}][{grupo}] com janela mas sem os "
                        f"campos {sorted(faltando)}."
                    )
                if not isinstance(janela["risco_por_decendio"], dict):
                    sys.exit(
                        f"ERRO: culturas[{cultura}][{grupo}].risco_por_decendio não é objeto."
                    )

    for rotacao, grupos in rotacoes.items():
        if not isinstance(grupos, dict) or not set(grupos) <= GRUPOS:
            sys.exit(f"ERRO: rotacoes[{rotacao}] com grupos inesperados: {sorted(grupos)}")
        for grupo, janelas in grupos.items():
            if not isinstance(janelas, dict) or not isinstance(janelas.get("primeira"), list):
                sys.exit(
                    f"ERRO: rotacoes[{rotacao}][{grupo}] sem a lista 'primeira'."
                )

    # Avisa (sem falhar) se o motor gerar cultura fora da convenção de chaves
    # conhecida pelo frontend — o arquivo continua sendo gerado.
    chaves_conhecidas = set(json.loads('["soja","milho_verao","milho_safrinha",'
                                      '"sorgo_granifero","sorgo_safrinha","feijao",'
                                      '"feijao_2","girassol","amendoim","arroz",'
                                      '"algodao"]'))
    desconhecidas = set(culturas) - chaves_conhecidas
    if desconhecidas:
        print(f"AVISO: culturas fora da lista conhecida (passam direto): "
              f"{sorted(desconhecidas)}", file=sys.stderr)


def serializar(dados: dict) -> str:
    """Serialização estável — mesma do arquivo atual (indent 2, UTF-8, sem \\n final)."""
    return json.dumps(dados, indent=2, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--engine",
        type=Path,
        default=ENGINE_PADRAO,
        help=f"arquivo-fonte do motor (padrão: {ENGINE_PADRAO})",
    )
    parser.add_argument(
        "--web",
        type=Path,
        default=WEB_PADRAO,
        help=f"arquivo de destino do frontend (padrão: {WEB_PADRAO})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="só verifica se o arquivo web está atualizado; sai 1 se houver divergência",
    )
    args = parser.parse_args()

    dados = carregar(args.engine)
    validar(dados, args.engine)
    conteudo = serializar(dados)

    if args.check:
        if not args.web.is_file():
            print(f"DRIFT: {args.web} não existe (rode sem --check para gerar).")
            return 1
        atual = args.web.read_text(encoding="utf-8")
        if atual == conteudo:
            print(f"OK: {args.web} está atualizado com {args.engine}.")
            return 0
        print(f"DRIFT: {args.web} difere de {args.engine}. "
              f"Rode: python {Path(__file__).name}")
        return 1

    args.web.parent.mkdir(parents=True, exist_ok=True)
    args.web.write_text(conteudo, encoding="utf-8")
    print(f"Gerado {args.web} a partir de {args.engine} "
          f"({len(dados['culturas'])} culturas, {len(dados['rotacoes'])} rotações).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
