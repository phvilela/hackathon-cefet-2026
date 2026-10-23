#!/usr/bin/env python3
"""engine/adequacao.py — Camada 1 do motor: ZARC → máscaras de decêndios viáveis.

Lê:      data/raw/zarc/tabua-risco-2026-2027-patos-de-minas-3148004.csv
         (CKAN MAPA, dataset "tabua-de-risco-zoneamento-agricola-de-risco-climatico",
          id 6d3d141c-885e-41a4-ab7f-dc8ff323b96f, safra 2026/2027)
Escreve: engine/janelas_zarc.json — insumo rastreável para o engine/config.yaml
         (janelas_viveis por cultura/rotação × grupo de solo + hipóteses com fonte).

Regras (todas documentadas no JSON de saída — rastreabilidade é requisito):
  R1. Viável: decêndio com risco ZARC > 0. A tábua só publica janelas com risco
      20/30/40% — célula 0 = fora do zoneamento. Logo "risco > 0" ≡ "risco ≤ 40%".
  R2. Solo: Sorgo usa grupo 1/2/3 nativo (arenoso/média/argiloso). Soja, milho e
      feijão usam classes de água disponível AD1–AD6 (códigos 11–16); mapeamos do
      grupo de solo do talhão: 1(arenoso)→AD1(11), 2(médio)→AD3(13), 3(argiloso)→AD5(15).
  R3. Ciclo: máscara da cultura = menor risco entre os grupos de ciclo I/II/III
      (Cod_Ciclo 20/21/22) — usa o melhor ciclo disponível.
  R4. Sequência: a 2ª cultura da rotação só é viável no decêndio d se existir
      plantio da 1ª em d_s com (abs(d) − abs(d_s)) ≥ ciclo da 1ª em decêndios
      (soja Grupo I ≈ 10 decêndios ≈ 100 dias; feijão ≈ 9 ≈ 90 dias), onde abs()
      lineariza o ano circular da safra: a safra 2026/27 corre de set/2026 (dec25)
      a ago/2027 (dec24) — dec1-3 são 2027 e vêm DEPOIS de dec25-36 (2026).
      Sem isso, o wrap-around deixaria o milho "voltar no tempo" para antes da soja.

Uso: python3 engine/adequacao.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
CSV_PATH = REPO / "data/raw/zarc/tabua-risco-2026-2027-patos-de-minas-3148004.csv"
OUT_PATH = Path(__file__).resolve().parent / "janelas_zarc.json"

GEOCODIGO = 3148004  # Patos de Minas
DECS = [f"dec{i}" for i in range(1, 37)]  # dec1 = 1-10 jan ... dec36 = 21-31 dez

# Nome_cultura (literal no CSV) → (chave interna, usa_classes_AD?)
CULTURAS = {
    "Soja": ("soja", True),
    "Milho 1ª Safra": ("milho_verao", True),
    "Milho 2ª Safra": ("milho_safrinha", True),
    "Sorgo Granífero": ("sorgo_granifero", False),
    "Sorgo Granífero 2ª Safra": ("sorgo_safrinha", False),
    "Feijão": ("feijao", True),        # só Sequeiro (v0) — irrigado é outra realidade
    "Feijão 2ª Safra": ("feijao_2", True),
}

GRUPO_TO_AD = {1: 11, 2: 13, 3: 15}      # R2
CICLO_PRIMEIRA = {"soja": 10, "feijao": 9}  # R4, em decêndios

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


def load_zarc() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH, sep=";", encoding="utf-8-sig")
    df = df[(df.geocodigo == GEOCODIGO) & (df.SafraIni == 2026)]
    # Feijão de sequeiro apenas (Cod_Outros_Manejos == 1); irrigado fica fora do v0
    feijao = df.Nome_cultura == "Feijão"
    df = df[~(feijao & (df.Cod_Outros_Manejos != 1))]
    return df


def masks_for(df: pd.DataFrame, nome_cultura: str, usa_ad: bool) -> dict:
    """Máscara de decêndios viáveis por grupo de solo {1,2,3} (R1+R2+R3)."""
    rows = df[df.Nome_cultura == nome_cultura]
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
                          "aviso": "sem linha no ZARC para esse solo/cultura"}
            continue
        risco = sel[DECS].min(axis=0)  # R3: melhor risco entre grupos de ciclo
        out[grupo] = {
            "decendios": [i + 1 for i, v in enumerate(risco.values) if v > 0],
            "risco_por_decendio": {str(i + 1): int(v) for i, v in enumerate(risco.values) if v > 0},
            "solo_usado": solo_label,
            "ciclos_disponiveis": sorted(int(c) for c in sel.Cod_Ciclo.unique()),
        }
    return out


def abs_decendio(d: int, inicio_safra: int = 25) -> int:
    """Lineariza o ano circular da safra: 2026/27 começa em set/2026 (dec25).
    dec25-36 (set-dez/2026) antecedem dec1-24 (jan-ago/2027) na linha do tempo."""
    return d if d >= inicio_safra else d + 36


def seq_mask(primeira: list[int], segunda: list[int], ciclo_dec: int) -> list[int]:
    """R4: d é viável na 2ª cultura se a 1ª pode ser plantada em d_s com
    abs(d) − abs(d_s) ≥ ciclo_dec (tempo absoluto da safra — sem wrap-around)."""
    p_abs = [abs_decendio(ds) for ds in primeira]
    return [d for d in segunda
            if any((abs_decendio(d) - pa) >= ciclo_dec for pa in p_abs)]


def main() -> None:
    df = load_zarc()

    culturas: dict[str, dict] = {}
    portarias: dict[str, list] = {}
    for nome, (chave, usa_ad) in CULTURAS.items():
        rows = df[df.Nome_cultura == nome]
        culturas[chave] = masks_for(df, nome, usa_ad)
        portarias[chave] = sorted(set(rows.Portaria))

    rotacoes: dict[str, dict] = {}
    for rot, spec in ROTACOES.items():
        rotacoes[rot] = {}
        for grupo in (1, 2, 3):
            p_mask = culturas[spec["primeira"]][grupo]["decendios"]
            if spec["segunda"] is None:
                rotacoes[rot][str(grupo)] = {"primeira": p_mask}
            else:
                s_mask = culturas[spec["segunda"]][grupo]["decendios"]
                ciclo = CICLO_PRIMEIRA[spec["primeira"]]
                rotacoes[rot][str(grupo)] = {
                    "primeira": p_mask,
                    "segunda": seq_mask(p_mask, s_mask, ciclo),
                    "premissa_ciclo_primeira_decendios": ciclo,
                }

    # ---- sanity (falha alto e claro se a agronomia real divergir) ----
    sanity = {
        "soja_grupo2_tem_janela_out_nov":
            bool(set(culturas["soja"][2]["decendios"]) & set(range(28, 34))),
        "milho_verao_grupo2_tem_janela_out_nov":
            bool(set(culturas["milho_verao"][2]["decendios"]) & set(range(28, 34))),
        "soja_milho_grupo2_segunda_nao_vazia":
            bool(rotacoes["soja_milho"]["2"]["segunda"]),
        "soja_milho_grupo2_segunda_restrita_a_jan_abr":  # jan-abr = dec1-12
            all(1 <= d <= 12 for d in rotacoes["soja_milho"]["2"]["segunda"]),
        "todas_rotacoes_tem_primeira_nao_vazia_todos_grupos":
            all(rotacoes[r][str(g)]["primeira"]
                for r in ROTACOES for g in (1, 2, 3)),
    }

    resultado = {
        "cenario": {
            "municipio": "Patos de Minas", "cod_ibge": GEOCODIGO,
            "safra": "2026/2027", "uf": "MG",
        },
        "fonte": {
            "arquivo_csv": str(CSV_PATH.relative_to(REPO)),
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
             "valor": "menor risco entre os grupos de ciclo I/II/III (usa o melhor ciclo)",
             "metodo": "regra R3", "fonte_url": CKAN_URL},
            {"chave": "ciclo_soja_decendios", "valor": CICLO_PRIMEIRA["soja"],
             "metodo": "Grupo I (precoce, ~100 dias) — viabiliza safrinha; Grupo II/III postergam a 2ª cultura",
             "fonte_url": "data/raw/zarc/portarias/PORTN200_*_MG_2026-2027.pdf"},
            {"chave": "ciclo_feijao_decendios", "valor": CICLO_PRIMEIRA["feijao"],
             "metodo": "~90 dias (ciclo precoce) — sequência feijão→sorgo",
             "fonte_url": "data/raw/zarc/portarias/PORTN13_*_MG_2026-2027.pdf"},
            {"chave": "convencao_decendio",
             "valor": "dec1 = 1-10 jan ... dec36 = 21-31 dez; ano circular: na safra 2026/27, "
                      "dec28-36 = out-dez/2026 e dec1-3 = jan-mar/2027",
             "metodo": "item 3.3 da Port. 200/2026", "fonte_url": CKAN_URL},
        ],
        "culturas": culturas,
        "rotacoes": rotacoes,
        "sanity": sanity,
    }

    OUT_PATH.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- resumo legível ----
    print(f"OK → {OUT_PATH}")
    print("\nSanity:")
    for k, v in sanity.items():
        print(f"  {'✅' if v else '❌'} {k}")
    print("\nJanelas (decêndios viáveis) por cultura × grupo de solo:")
    for chave, grupos in culturas.items():
        for grupo, info in grupos.items():
            print(f"  {chave:<16} grupo {grupo} ({info.get('solo_usado','?')}): "
                  f"{info['decendios']}")
    print("\nRotações (primeira → segunda, com regra de sequência):")
    for rot, grupos in rotacoes.items():
        for grupo, info in grupos.items():
            seg = info.get("segunda")
            seg_s = f" → {seg}" if seg is not None else ""
            print(f"  {rot:<14} grupo {grupo}: {info['primeira']}{seg_s}")

    if not all(sanity.values()):
        raise SystemExit("SANITY FALHOU — conferir dados/regras antes de seguir.")


if __name__ == "__main__":
    main()
