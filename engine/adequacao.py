#!/usr/bin/env python3
"""engine/adequacao.py — Camada 1 do motor: ZARC → máscaras de decêndios viáveis.

Lê:      tábua de risco do ZARC (CKAN MAPA, safra 2026/2027) — por padrão o
         extrato de Patos de Minas; use --municipio/--csv para outro município.
Escreve: engine/janelas_zarc.json (ou --saida) — insumo rastreável do config.yaml.

Regras (todas documentadas no JSON de saída — rastreabilidade é requisito):
  R1. Viável: decêndio com risco ZARC > 0. A tábua só publica janelas com risco
      20/30/40% — célula 0 = fora do zoneamento. Logo "risco > 0" ≡ "risco ≤ 40%".
  R2. Solo: Sorgo usa grupo 1/2/3 nativo (arenoso/médio/argiloso). Soja, milho e
      feijão usam classes de água disponível AD1–AD6 (códigos 11–16); mapeamos do
      grupo de solo do talhão: 1(arenoso)→AD1(11), 2(médio)→AD3(13), 3(argiloso)→AD5(15).
  R3. Ciclo: a máscara da cultura (para plantio solteiro) usa o menor risco entre
      os grupos de ciclo I/II/III (Cod_Ciclo 20/21/22) — "melhor ciclo disponível".
  R4. Sequência (rotações com 2ª cultura): usa a máscara da 1ª cultura restrita ao
      CICLO PRECOCE (Grupo I) e PAREIA as janelas nos dois sentidos:
        - a 2ª cultura é viável em d  se ∃ plantio da 1ª em d_s com abs(d)−abs(d_s) ≥ ciclo
        - a 1ª cultura é viável em d_s se ∃ decêndio viável da 2ª após d_s + ciclo
      onde abs() lineariza o ano circular da safra (set/26 → ago/27: dec25–36 são
      2026 e dec1–24 são 2027 — dec1-3 vêm DEPOIS de dec25-36). Consequências:
      (i) todo decêndio da janela da 1ª cultura realmente "fecha" a rotação;
      (ii) uma rotação pode ser INVÁVEL num grupo de solo — informação, não erro.

Uso:
    python3 engine/adequacao.py                      # Patos de Minas (3148004)
    python3 engine/adequacao.py --municipio 3171301  # outro município de MG (tábua estadual)
    python3 engine/adequacao.py --csv caminho.csv --saida engine/janelas_x.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
DIR_ZARC = REPO / "data/raw/zarc"
CSV_PATOS = DIR_ZARC / "tabua-risco-2026-2027-patos-de-minas-3148004.csv"
CSV_MG = DIR_ZARC / "tabua-risco-2026-2027-MG.csv"

GEOCODIGO_PADRAO = 3148004  # Patos de Minas
DECS = [f"dec{i}" for i in range(1, 37)]  # dec1 = 1-10 jan ... dec36 = 21-31 dez
CICLO_PRECOCE = 20                         # Cod_Ciclo 20 = Grupo I (~100 dias na soja)

# Nome_cultura (literal no CSV) → (chave interna, usa_classes_AD?)
CULTURAS = {
    "Soja": ("soja", True),
    "Milho 1ª Safra": ("milho_verao", True),
    "Milho 2ª Safra": ("milho_safrinha", True),
    "Sorgo Granífero": ("sorgo_granifero", False),
    "Sorgo Granífero 2ª Safra": ("sorgo_safrinha", False),
    "Feijão": ("feijao", True),        # só Sequeiro (v0) — irrigado exige talhão com irrigação
    "Feijão 2ª Safra": ("feijao_2", True),
}

GRUPO_TO_AD = {1: 11, 2: 13, 3: 15}        # R2
CICLO_PRIMEIRA = {"soja": 10, "feijao": 9}  # R4, em decêndios (Grupo I)

ROTACOES = {
    "soja_milho": {"primeira": "soja", "segunda": "milho_safrinha"},
    "soja_sorgo": {"primeira": "soja", "segunda": "sorgo_safrinha"},
    "feijao_sorgo": {"primeira": "feijao", "segunda": "sorgo_safrinha"},
    "soja_solteira": {"primeira": "soja", "segunda": None},
    "milho_verao": {"primeira": "milho_verao", "segunda": None},
}

CKAN_URL = ("https://dados.agricultura.gov.br/dataset/"
            "tabua-de-risco-zoneamento-agricola-de-risco-climatico")
DICT_URL = "data/raw/zarc/dicionario-de-dados-tabua-de-risco-2026.pdf (IN SPA/MAPA nº 1/2022)"


def abs_decendio(d: int, inicio_safra: int = 25) -> int:
    """Lineariza o ano circular da safra: 2026/27 começa em set/2026 (dec25).
    dec25-36 (set-dez/2026) antecedem dec1-24 (jan-ago/2027) na linha do tempo."""
    return d if d >= inicio_safra else d + 36


def load_zarc(csv_path: Path, geodigo: int) -> pd.DataFrame:
    df = pd.read_csv(csv_path, sep=";", encoding="utf-8-sig")
    df = df[(df.geocodigo == geodigo) & (df.SafraIni == 2026)]
    # Feijão de sequeiro apenas (Cod_Outros_Manejos == 1); irrigado fica fora do v0
    feijao = df.Nome_cultura == "Feijão"
    df = df[~(feijao & (df.Cod_Outros_Manejos != 1))]
    if df.empty:
        raise SystemExit(
            f"ERRO: nenhuma linha do ZARC (safra 2026) para o geocódigo {geodigo} "
            f"em {csv_path}. Baixe a tábua correta e use --csv."
        )
    return df


def masks_for(df: pd.DataFrame, nome_cultura: str, usa_ad: bool,
              ciclos: list[int] | None = None) -> dict:
    """Máscara de decêndios viáveis por grupo de solo {1,2,3} (R1+R2+R3).

    `ciclos` filtra os grupos de ciclo (ex.: [20] = só Grupo I/precoce)."""
    rows = df[df.Nome_cultura == nome_cultura]
    if ciclos is not None:
        rows = rows[rows.Cod_Ciclo.isin(ciclos)]
    out: dict[int, dict] = {}
    for grupo, ad in GRUPO_TO_AD.items():
        if usa_ad:
            sel = rows[rows.Cod_Solo == ad]
            solo_label = f"AD{ad - 10}"
        else:  # sorgo: grupo 1/2/3 nativo do ZARC
            sel = rows[rows.Cod_Solo == grupo]
            solo_label = f"grupo {grupo}"
        if sel.empty:
            out[grupo] = {"decendios": [], "solo_usado": solo_label,
                          "aviso": "sem linha no ZARC para esse solo/cultura/ciclo"}
            continue
        risco = sel[DECS].min(axis=0)  # R3: melhor risco entre os grupos de ciclo restantes
        out[grupo] = {
            "decendios": [i + 1 for i, v in enumerate(risco.values) if v > 0],
            "risco_por_decendio": {str(i + 1): int(v) for i, v in enumerate(risco.values) if v > 0},
            "solo_usado": solo_label,
            "ciclos_disponiveis": sorted(int(c) for c in sel.Cod_Ciclo.unique()),
        }
    return out


def janelas_rotacao(primeira_gi: list[int], segunda_zarc: list[int],
                    ciclo_dec: int) -> tuple[list[int], list[int]]:
    """R4: janelas PAREADAS da rotação.

    - segunda viável em d  se ∃ d_s na 1ª (Grupo I) com abs(d) − abs(d_s) ≥ ciclo
    - primeira viável em d_s se ∃ d na 2ª (ZARC) com abs(d) − abs(d_s) ≥ ciclo
    """
    primeira_ok = [
        d_s for d_s in primeira_gi
        if any((abs_decendio(d) - abs_decendio(d_s)) >= ciclo_dec for d in segunda_zarc)
    ]
    segunda_ok = [
        d for d in segunda_zarc
        if any((abs_decendio(d) - abs_decendio(d_s)) >= ciclo_dec for d_s in primeira_gi)
    ]
    return primeira_ok, segunda_ok


def _pares_consistentes(rotacoes: dict) -> bool:
    """Todo decêndio da janela da 1ª cultura 'fecha' a rotação (tem 2ª compatível)."""
    for rot, spec in ROTACOES.items():
        if spec["segunda"] is None:
            continue
        for grupo in ("1", "2", "3"):
            info = rotacoes[rot][grupo]
            ciclo = info["premissa_ciclo_primeira_decendios"]
            for d_s in info["primeira"]:
                if not any((abs_decendio(d) - abs_decendio(d_s)) >= ciclo
                           for d in info["segunda"]):
                    return False
    return True


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Camada 1: tábua de risco do ZARC → máscaras de decêndios viáveis")
    parser.add_argument("--municipio", type=int, default=GEOCODIGO_PADRAO,
                        help=f"geocódigo IBGE (default: {GEOCODIGO_PADRAO} — Patos de Minas)")
    parser.add_argument("--csv", default=None,
                        help="caminho da tábua de risco (default: extrato de Patos de Minas "
                             "para o município padrão; senão, a tábua completa de MG)")
    parser.add_argument("--saida", default=None,
                        help="JSON de saída (default: engine/janelas_zarc.json para o "
                             "município padrão; senão, engine/janelas_zarc_<geocode>.json)")
    args = parser.parse_args(argv)

    if args.csv:
        csv_path = Path(args.csv)
    else:
        csv_path = CSV_PATOS if args.municipio == GEOCODIGO_PADRAO else CSV_MG
    engine_dir = Path(__file__).resolve().parent
    if args.saida:
        out_path = Path(args.saida)
    elif args.municipio == GEOCODIGO_PADRAO:
        out_path = engine_dir / "janelas_zarc.json"
    else:
        out_path = engine_dir / f"janelas_zarc_{args.municipio}.json"

    df = load_zarc(csv_path, args.municipio)
    nome_municipio = str(df.municipio.iloc[0])

    culturas: dict[str, dict] = {}
    portarias: dict[str, list] = {}
    for nome, (chave, usa_ad) in CULTURAS.items():
        rows = df[df.Nome_cultura == nome]
        culturas[chave] = masks_for(df, nome, usa_ad)
        portarias[chave] = sorted(set(rows.Portaria))

    # máscaras de CICLO PRECOCE (Grupo I) das 1ªs culturas das rotações com 2ª cultura
    chaves_primeira = {spec["primeira"] for spec in ROTACOES.values() if spec["segunda"]}
    gi: dict[str, dict] = {}
    for nome, (chave, usa_ad) in CULTURAS.items():
        if chave in chaves_primeira:
            gi[chave] = masks_for(df, nome, usa_ad, ciclos=[CICLO_PRECOCE])

    rotacoes: dict[str, dict] = {}
    for rot, spec in ROTACOES.items():
        rotacoes[rot] = {}
        for grupo in (1, 2, 3):
            if spec["segunda"] is None:
                rotacoes[rot][str(grupo)] = {
                    "primeira": culturas[spec["primeira"]][grupo]["decendios"],
                }
            else:
                p_gi = gi[spec["primeira"]][grupo]["decendios"]
                s_zarc = culturas[spec["segunda"]][grupo]["decendios"]
                ciclo = CICLO_PRIMEIRA[spec["primeira"]]
                p_ok, s_ok = janelas_rotacao(p_gi, s_zarc, ciclo)
                rotacoes[rot][str(grupo)] = {
                    "primeira": p_ok,
                    "segunda": s_ok,
                    "primeira_ciclo": "Grupo I (precoce)",
                    "premissa_ciclo_primeira_decendios": ciclo,
                }

    # ---- sanity (falha alto e claro se a agronomia real divergir) ----
    sanity = {
        "soja_grupo2_tem_janela_out_nov":
            bool(set(culturas["soja"][2]["decendios"]) & set(range(28, 34))),
        "soja_grupoI_tem_janela_out_nov":
            bool(set(gi["soja"][2]["decendios"]) & set(range(28, 34))),
        "milho_verao_grupo2_tem_janela_out_nov":
            bool(set(culturas["milho_verao"][2]["decendios"]) & set(range(28, 34))),
        "soja_milho_grupo2_segunda_nao_vazia":
            bool(rotacoes["soja_milho"]["2"]["segunda"]),
        "soja_milho_grupo2_segunda_restrita_a_jan_abr":  # jan-abr = dec1-12
            all(1 <= d <= 12 for d in rotacoes["soja_milho"]["2"]["segunda"]),
        "janelas_da_rotacao_pareadas": _pares_consistentes(rotacoes),
        "toda_rotacao_viavel_em_algum_grupo":
            all(any(rotacoes[r][str(g)]["primeira"] for g in (1, 2, 3))
                for r in ROTACOES),
    }

    resultado = {
        "cenario": {
            "municipio": nome_municipio, "cod_ibge": args.municipio,
            "safra": "2026/2027", "uf": str(df.UF.iloc[0]),
        },
        "fonte": {
            "arquivo_csv": str(csv_path.relative_to(REPO)) if csv_path.is_relative_to(REPO) else str(csv_path),
            "portal": CKAN_URL,
            "dataset_id": "6d3d141c-885e-41a4-ab7f-dc8ff323b96f",
            "recurso_safra_2026_2027": "139e5a60-1f43-4cc8-aeab-a35dbbf816c0",
            "portarias_por_cultura": portarias,
        },
        "premissas": [
            {"chave": "criterio_viabilidade",
             "valor": "decêndio viável se risco ZARC > 0 (a tábua só publica janelas ≤ 40%)",
             "metodo": "regra R1", "fonte_url": CKAN_URL},
            {"chave": "mapeamento_grupo_solo_ad",
             "valor": "grupo 1 (arenoso)→AD1 (11); 2 (médio)→AD3 (13); 3 (argiloso)→AD5 (15); "
                      "sorgo usa grupo 1/2/3 nativo",
             "metodo": "mapeamento conservador textura→água disponível; Latossolos de Patos de "
                       "Minas tipicamente AD4–AD6 — o grupo real do talhão vem do formulário (tela 1)",
             "fonte_url": DICT_URL},
            {"chave": "agregacao_ciclo",
             "valor": "menor risco entre os grupos de ciclo I/II/III (usa o melhor ciclo) — "
                      "para plantio SOLTEIRO; nas ROTAÇÕES usa-se o ciclo precoce (Grupo I)",
             "metodo": "regras R3+R4", "fonte_url": CKAN_URL},
            {"chave": "ciclo_soja_decendios", "valor": CICLO_PRIMEIRA["soja"],
             "metodo": "Grupo I (precoce, ~100 dias) — só ele viabiliza a safrinha; "
                       "Grupo II/III colhem além da janela da 2ª cultura",
             "fonte_url": "data/raw/zarc/portarias/PORTN200_*_MG_2026-2027.pdf"},
            {"chave": "ciclo_feijao_decendios", "valor": CICLO_PRIMEIRA["feijao"],
             "metodo": "Grupo I (~90 dias) — sequência feijão→sorgo",
             "fonte_url": "data/raw/zarc/portarias/PORTN13_*_MG_2026-2027.pdf"},
            {"chave": "janelas_pareadas",
             "valor": "nas rotações, a janela da 1ª cultura só contém decêndios que fecham a 2ª "
                      "(cada decêndio listado permite ao menos um decêndio viável da 2ª após o ciclo)",
             "metodo": "regra R4 — evita recomendar plantio de soja que não deixa a safrinha caber",
             "fonte_url": CKAN_URL},
            {"chave": "convencao_decendio",
             "valor": "dec1 = 1-10 jan ... dec36 = 21-31 dez; ano circular: na safra 2026/27, "
                      "dec28-36 = out-dez/2026 e dec1-3 = jan-mar/2027",
             "metodo": "item 3.3 da Port. 200/2026", "fonte_url": CKAN_URL},
            {"chave": "feijao_irrigado",
             "valor": "fora do v0: só entra quando o talhão tem irrigação (campo 'irrigacao' do config)",
             "metodo": "ZARC lista manejo irrigado à parte (risco 20% o ano todo)",
             "fonte_url": "data/raw/zarc/portarias/PORTN32_*_MG_2026-2027.pdf"},
        ],
        "culturas": culturas,
        "rotacoes": rotacoes,
        "sanity": sanity,
    }

    out_path.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- resumo legível ----
    print(f"OK → {out_path}")
    print("\nSanity:")
    for k, v in sanity.items():
        print(f"  {'✅' if v else '❌'} {k}")
    print("\nJanelas (decêndios viáveis) por cultura × grupo de solo:")
    for chave, grupos in culturas.items():
        for grupo, info in grupos.items():
            print(f"  {chave:<16} grupo {grupo} ({info.get('solo_usado','?')}): "
                  f"{info['decendios']}")
    print("\nCiclo precoce (Grupo I) das 1ªs culturas — base das rotações:")
    for chave, grupos in gi.items():
        for grupo, info in grupos.items():
            print(f"  {chave:<16} grupo {grupo}: {info['decendios']}")
    print("\nRotações (janelas PAREADAS — 1ª só entra se a 2ª fecha):")
    for rot, grupos in rotacoes.items():
        for grupo, info in grupos.items():
            seg = info.get("segunda")
            if seg is None:
                print(f"  {rot:<14} grupo {grupo}: {info['primeira']} (solteira)")
            elif not info["primeira"]:
                print(f"  {rot:<14} grupo {grupo}: INVIÁVEL (a rotação não fecha nesse solo)")
            else:
                print(f"  {rot:<14} grupo {grupo}: {info['primeira']} → {seg}")

    if not all(sanity.values()):
        raise SystemExit("SANITY FALHOU — conferir dados/regras antes de seguir.")


if __name__ == "__main__":
    main()
