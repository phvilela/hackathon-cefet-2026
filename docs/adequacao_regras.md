# Regras de Adequação (Camada 1) — Patos de Minas, safra 2026/27

> Gerado a partir do ZARC oficial (tábua de risco, CKAN MAPA) em 22/10/2026.
> Regenerar: `python3 engine/adequacao.py` → saída rastreável em `engine/janelas_zarc.json`.
> Fontes: CSV municipal `data/raw/zarc/tabua-risco-2026-2027-patos-de-minas-3148004.csv`,
> dicionário de dados e portarias em `data/raw/zarc/`.

## 1. As regras (se/então, auditáveis)

| # | Regra | Fonte |
|---|---|---|
| R1 | **Viável** = decêndio com risco ZARC > 0. A tábua só publica janelas de 20/30/40% — célula `0` = fora do zoneamento. Logo "risco > 0" ≡ "risco ≤ 40%" (nosso corte) | Tábua de risco 2026/27 |
| R2 | **Solo:** sorgo usa grupo 1/2/3 nativo do ZARC (arenoso/média/argiloso). Soja, milho e feijão usam classes de **água disponível AD1–AD6** (códigos 11–16); mapeamos o grupo do talhão: **1→AD1(11), 2→AD3(13), 3→AD5(15)** — premissa conservadora; Latossolos da região tipicamente AD4–AD6; o grupo real de cada talhão virá do formulário (tela 1) | Dicionário de dados + IN SPA/MAPA nº 1/2022 |
| R3 | **Ciclo:** a máscara da cultura usa o **menor risco** entre os grupos de ciclo I/II/III (Cod_Ciclo 20/21/22) — "melhor ciclo disponível" | Tábua de risco |
| R4 | **Sequência:** a 2ª cultura só é plantada ≥ ciclo da 1ª depois do plantio dela — **soja Grupo I ≈ 10 decêndios (~100 dias)**, feijão ≈ 9 (~90 dias). O tempo é linearizado na safra (set/26 → ago/27): sem isso, o milho "voltaria no tempo" para antes da colheita da soja | Port. 200 (ciclos soja); premissa documentada |

**Convenção de decêndios:** `dec1` = 1–10 jan … `dec36` = 21–31 dez; na safra 2026/27, dec25–36 = set–dez/**2026** e dec1–24 = jan–ago/**2027** (dec28 = out-1, dec2 = jan-2 etc.).

## 2. Janelas por cultura × grupo de solo (dados reais)

| Cultura | Grupo 1 (arenoso / AD1) | Grupo 2 (médio / AD3) | Grupo 3 (argiloso / AD5) |
|---|---|---|---|
| **Soja** | out-1 a dez-3 + jan-1 (dec 28-36, 1) | idem | idem |
| **Milho 1ª safra** | out-3 a dez-2 (dec 31-35) | out-2 a dez-3 (dec 30-36) | out-2 a dez-3 |
| **Milho 2ª safra** (bruto) | dez-3 + jan-1 (36, 1) | dez-3 + jan-1 a jan-3 (36, 1-3) | dez-3 + jan-1 a fev-1 (36, 1-4) |
| **Sorgo granífero** | out-1 a dez-2 (dec 28-35) | set-3 a dez-2 (dec 27-35) | set-3 a dez-2 |
| **Sorgo granífero 2ª** (bruto) | dez-3 + jan (36, 1-4) | dez-3 + jan-1 a fev-2 (36, 1-5) | dez-3 + jan-1 a fev-3 (36, 1-6) |
| **Feijão 1ª (sequeiro)** | out-2 a nov-3 (dec 29-32) | out-1 a dez-3 (dec 28-36) | out-1 a dez-3 |
| **Feijão 2ª** | — (ZARC não zoneia p/ AD1) | jan-1 a fev-1 (dec 1-4) | jan-1 a fev-2 (dec 1-5) |

*Feijão irrigado (20% de risco o ano inteiro) fica fora do v0 — só entra se a fazenda tiver irrigação (campo do formulário).*

## 3. Rotações com a regra de sequência (R4 aplicada)

| Rotação | Grupo 1 | Grupo 2 | Grupo 3 |
|---|---|---|---|
| **soja → milho safrinha** | ⛔ segunda vazia | jan-2 a jan-3 (dec 2-3) | jan-2 a fev-1 (dec 2-4) |
| **soja → sorgo 2ª** | jan-2 a fev-1 (dec 2-4) | jan-2 a fev-2 (dec 2-5) | jan-2 a fev-3 (dec 2-6) |
| **feijão → sorgo 2ª** | fev (dec 2-4) | jan-1 a fev-2 (dec 1-5) | jan-1 a fev-3 (dec 1-6) |
| **soja solteira** | out-1 a dez-3 + jan-1 | idem | idem |
| **milho verão (solteiro)** | out-3 a dez-2 | out-2 a dez-3 | out-2 a dez-3 |

## 4. Insights que o filtro revelou (usar no pitch/relatório)

1. **"Milho safrinha depois de soja em Patos de Minas é decisão de janeiro, não de dezembro."** O ZARC permite milho 2ª a partir de dez-3, mas a soja plantada em outubro (Grupo I, ~100 dias) só colhe em meados de janeiro — a janela honesta da rotação é **jan-2 em diante**. O wrap-around ingênuo deixaria o milho "antes" da soja; a linearização temporal da safra corrige isso (e virou sanity check automático).
2. **No solo arenoso (grupo 1), soja→milho safrinha não fecha** (janela da 2ª vazia) — **mas soja→sorgo fecha**. Recomendação diferente por textura de talhão: exatamente o gap do ZARC municipal que a tela 1 (formulário de talhões) explora.
3. Soja tem a janela mais larga (10 decêndios + tardia), feijão 1ª é intermediária e milho verão tem a mais curta — consistente com a agronomia local, o que valida o parse.

## 5. Portarias de origem (rastreabilidade)

| Cultura | Portaria (safra 2026/27, MG) |
|---|---|
| Soja | Port. 200 — DOU 03/07/2026 |
| Milho 1ª | Port. 223 — DOU 10/07/2026 |
| Milho 2ª | Port. 324 — DOU 30/07/2026 |
| Sorgo granífero (1ª e 2ª) | Port. 275 — DOU 22/07/2026 |
| Feijão sequeiro | Port. 13 — DOU 16/03/2026 |
| Feijão 2ª | Port. 359 — DOU 24/08/2026 |

PDFs em `data/raw/zarc/portarias/`. Dataset CKAN: `tabua-de-risco-zoneamento-agricola-de-risco-climatico` (id `6d3d141c-885e-41a4-ab7f-dc8ff323b96f`).

## 6. Pendências / premissas a refinar

- **Grupo de solo real por talhão** vem do formulário (tela 1); hoje o mapeamento 1→AD1, 2→AD3, 3→AD5 é premissa conservadora — discutir com o time se argiloso deve ser AD6 (janelas de 2ª safra mais largas).
- **Ciclo da soja**: R4 usa Grupo I (precoce, ~100 dias) por ser o viabilizador da safrinha; se assumirmos Grupo II (~115 dias), a janela do milho desloca ~1 decêndio — testar como sensibilidade.
- Feijão irrigado e culturas consorciadas (braquiária) fora do v0 — insumo já baixado se o time quiser.
- `Produtividade` e `Cod_NM` vêm vazios no ZARC — produtividade esperada continua vindo do PAM/MC (M1).
