## Método (rascunho — seção do relatório final)

> M2 (motor de decisão) · **números reais do congelamento de 26/10** (`contract/results.json`, status `REAL`).

### 1. Arquitetura em três camadas

"O que plantar" vira três perguntas encadeadas, cada uma com método e saída próprios:

| Camada | Pergunta | Método | Saída |
|---|---|---|---|
| 1. Adequação | O que pode ser plantado, onde e quando? | Regras se/então (ZARC) | Máscara de viabilidade por cultura × talhão × decêndio |
| 2. Margem sob risco | Quanto rende, com que risco? | Monte Carlo (M1) | Distribuição da margem por rotação |
| 3. Alocação | Quantos hectares por opção? | CP-SAT + fronteira Pareto | Menu de planos por perfil de risco |

A camada 1 corta o espaço de opções; a 2 gera os coeficientes econômicos; a 3 aloca os 600 ha e expõe o trade-off.

### 2. Camada 1 — Adequação explicável

Regras auditáveis que espelham o ZARC de Patos de Minas:

- **Viabilidade climática:** "o decêndio d é viável para a cultura X no grupo de solo G se o risco ZARC de X em G em d for ≤ 40%". Cada cultura × grupo de solo vira uma **máscara de 36 decêndios**, derivada da tábua de risco oficial.
- **Sequência:** milho safrinha só após a colheita da soja no mesmo talhão: liberação = plantio + **ciclo precoce da soja (Grupo I, 10 decêndios ≈ 100 dias)**, premissa rastreável. O Grupo I é o único que fecha a janela da 2ª cultura — Grupos II/III colhem tarde demais.

Toda recomendação pode ser lida como a lista de regras que a produziu — explicabilidade nativa, não pós-hoc.

### 3. Camada 2 — Margem sob risco (insumo do CP-SAT)

Para cada rotação viável, o Monte Carlo do M1 (bootstrap de 31 anos de produtividade × preço pareados, PAM/SIDRA de Patos de Minas) entrega a distribuição da margem: esperança e P(margem < 0) — os coeficientes da camada 3.

**Coeficientes congelados** (freeze v2, 27/10; regime de preços 2026/27; margem em R$/ha, risco em ‰ = P[margem < 0] × 10):

| Rotação | Margem esperada | Risco (‰) | P[margem < 0] |
|---|---|---|---|
| soja → feijão 2ª safra | R$ 4.999,14/ha | 129 | 12,9% |
| soja → milho safrinha | R$ 4.621,95/ha | 213 | 21,3% |
| soja solteira | R$ 3.784,30/ha | 192 | 19,2% |
| soja → sorgo safrinha | R$ 2.558,96/ha | 279 | 27,9% |
| milho 1ª safra | R$ 880,44/ha | 515 | 51,5% |
| feijão das águas → sorgo | R$ 422,86/ha | 486 | 48,6% |
| arroz (sequeiro) | R$ 146,75/ha | 480 | 48,0% |
| algodão (pluma) | R$ 120,50/ha | 530 | 53,0% |
| capital pousio (CDI) | R$ 200,00/ha | 0 | 0,0% |

Soja e milho usam o bootstrap de 31 anos (PAM×SIDRA pareados). Feijão, sorgo, feijão 2ª, arroz e algodão não têm série municipal: usam preço Conab de referência com volatilidade lognormal documentada (CV 20–25%) e produtividade oficial (Conab/boletim). Custos são Conab 2024–2026, base CUSTO TOTAL, regiões de Cerrado.

**13 culturas avaliadas, 9 entram no menu.** Girassol e amendoim têm janela ZARC real em Patos de Minas, mas margem NEGATIVA nas referências Conab de out/2026 (custo/saca acima do preço de mercado: girassol −R$ 37 a −R$ 961/ha; amendoim −R$ 309 a −R$ 783/ha) — ficam fora do menu por honestidade, com janelas registradas para quando a margem virar. Arroz e algodão entram (margem fina) e o otimizador corretamente nunca os escolhe.

Nota de reprodutibilidade: corrigimos um bug em que o Monte Carlo iterava um `set` Python — a ordem variava entre execuções mesmo com semente fixa. Corrigido (ordem determinística), margens re-sincronizadas (mudança típica de 1–2%).

### 4. Camada 3 — Alocação ótima (CP-SAT)

Programação por restrições inteira, resolvida com o **CP-SAT do Google OR-Tools** (open source, Apache 2.0). Assinatura de Akplogan et al. (2013, INRA): alocação de culturas com restrições duras/soft ⚠️; o ZARC entra como restrição dura.

- **Variáveis:** área (ha, inteira) por rotação × talhão.
- **Restrições:** a soma das áreas por talhão é fixa (área do talhão; total 600 ha); só rotações viáveis no grupo de solo recebem área — inviáveis nem geram variável; margem em R$ inteiro (o CP-SAT é inteiro; escala documentada).
- **Otimização lexicográfica:** a 1ª passada maximiza a margem total; congela-se o ótimo como piso; a 2ª minimiza o risco sob esse piso. Sem pesos λ arbitrários misturando R$ com probabilidade.
- **Custo de oportunidade no menu:** entre as opções há a rotação `capital/pousio` — o rendimento da Selic sobre o capital de custeio, sem risco. O modelo só recomenda plantar o que rende mais que o melhor uso do dinheiro; o plano Conservador pode ser explicitamente "não plantar".

O problema é pequeno; resolve em segundos, com **prova de otimalidade** — não é heurística.

### 5. Fronteira Pareto e o menu de perfis

O CP-SAT não tem objetivo multiobjetivo nativo; a fronteira vem de **ε-constraint** (Haimes, 1971 ⚠️): impõe-se um piso de margem (≥ ótimo − ε), minimiza-se o risco e varre-se ε. O filtro de não-dominância devolve a **fronteira margem × risco** — análogo discreto da fronteira retorno × risco de Markowitz ⚠️.

Dela extraímos três planos: **arrojado** (extremo de margem), **conservador** (extremo de risco) e **equilibrado** — o *knee point*, onde ganhar margem passa a custar risco desproporcional. Não vendemos UMA resposta; vendemos o menu — arrojado, equilibrado, conservador. Cada ponto é ótimo para o seu nível de risco.

### 6. Robustez: a recomendação sobrevive à incerteza?

Coeficientes são estimativas. Medimos a dependência com um segundo Monte Carlo, de papel distinto: perturbamos margens e custos em ±10%, **re-resolvemos** a alocação e medimos a fração de rodadas em que o plano se mantém (taxa de estabilidade).

São dois papéis: o MC do M1 **gera os coeficientes** a partir do histórico; o de robustez **testa a alocação contra incerteza nesses coeficientes**. Um modela o mundo; o outro pergunta se a decisão muda quando a estimativa muda.

### 7. Rastreabilidade como princípio de design

Todo número carrega um **cartão de hipótese**: valor + fonte (URL) + método + suposição. Produtividade da soja → PAM/IBGE (código 3148004, média de 20 anos); preço → praça de Patrocínio (Conab); ciclo da soja → Embrapa. "Por que soja?" tem resposta clicável. Sem fonte, o número não entra no pipeline — antídoto direto à objeção da caixa-preta.

### 8. Referências do método

- OR-Tools CP-SAT (Google) — solver de programação por restrições, open source (Apache 2.0).
- Haimes, Y. Y. (1971) — método ε-constraint. ⚠️ forma exata da citação
- Akplogan et al. (2013, INRA) — alocação de culturas com restrições duras/soft. ⚠️ referência completa
- Guiducci & Hirakuri (Embrapa, SOBER 2020) — Monte Carlo agro validado. ⚠️ título exato
- Markowitz (1952) — analogia fronteira margem × risco. ⚠️ analogia conceitual

### 8. Resultados congelados (27/10 — freeze v2, status `REAL`)

**Cenário:** 600 ha em 3 talhões — T1 300 ha (grupo de solo 2, médio) · T2 200 ha (grupo 1, arenoso) · T3 100 ha (grupo 3, argiloso). **13 culturas avaliadas → 9 rotações candidatas** (girassol e amendoim rejeitados por margem negativa; arroz e algodão no menu com margem fina — §3).

**Fronteira** (14 pontos, ε-constraint, pisos de 100% a 5% do ótimo; todos com prova de otimalidade):

| # | Margem total | Ha com chance de prejuízo | | # | Margem total | Ha com chance de prejuízo |
|---|---|---|---|---|---|---|
| **1 (Arrojado)** | **R$ 2.756.516** | 90,0 | | 8 | R$ 1.348.580 | 33,0 |
| 2 | R$ 2.555.795 | 79,2 | | 9 | R$ 1.147.016 | 27,6 |
| 3 | R$ 2.355.074 | 68,5 | | 10 | R$ 945.452 | 22,2 |
| 4 | R$ 2.154.354 | 57,7 | | 11 | R$ 743.888 | 16,8 |
| **5 (knee)** | **R$ 1.953.271** | 49,3 | | 12 | R$ 542.324 | 11,4 |
| 6 | R$ 1.751.708 | 43,9 | | 13 | R$ 340.760 | 5,9 |
| 7 | R$ 1.550.144 | 38,4 | | **14 (Conservador)** | **R$ 139.197** | 0,5 |

> Por que 14 pontos: a v1 amostrava pisos apenas entre 100% e 85% do ótimo — o abismo entre "conservador" (R$ 120 mil, tudo no CDI) e "equilibrado" (R$ 2,2 milhões) era **artefato de amostragem**, não economia real. A v2 varre o intervalo inteiro e mostra a curva verdadeira: a partir do knee, cada real de margem abandonado compra cada vez menos redução de chance de prejuízo.

**O menu de perfis:**

| Perfil | Margem | Ha com chance de prejuízo | Alocação |
|---|---|---|---|
| **Arrojado** | R$ 2.756.516 | 90,0 | soja→feijão 2ª 400 ha · soja solteira 200 ha |
| **Equilibrado** (knee) | R$ 1.953.271 | 49,3 | soja→feijão 2ª 382 ha · **capital 218 ha** |
| **Conservador** | R$ 139.197 | 0,5 | soja→feijão 2ª 4 ha · **capital 596 ha** |
| *Referência (não plantar)* | *R$ 120.000* | *0,0* | *capital 600 ha — fora da fronteira* |

Três mudanças de conceito na v2:
1. **"Ha sob risco" virou "ha com chance de prejuízo"** — nosso risco é econômico (P[margem < 0] da simulação de 31 anos), distinto do **risco de perda por seca (ZARC)**, climático e por período de plantio. Dois conceitos, dois nomes — na interface e aqui.
2. **O conservador planta.** Antes o perfil era "tudo no CDI" (o ponto de mínimo risco absoluto); agora ele é o menor risco **entre os planos que plantam**, e o "não plantar" vira ponto de referência explícito — o custo de oportunidade fica visível sem se disfarçar de recomendação.
3. **A rotação de maior margem mudou de verdade:** soja→feijão 2ª safra (R$ 4.999/ha, 12,9% de chance de prejuízo) supera soja→milho (R$ 4.622/ha, 21,3%) — o feijão cores subiu ~40% no ano (Conab, Semanal 40/2026) e a janela ZARC pareada fecha nos três grupos de solo viáveis.

**Robustez sob ±10% em preço/custo** (30 re-solves, seed 42): **30/30 cenários resolvidos**; estabilidade média **88,9%**, com **83,3% dos cenários sem nenhuma mudança** de alocação (25/30; nos 5 restantes mudam 2 talhões). A soja→milho ressurge em 5/30 cenários — soja→feijão 2ª e soja→milho estão próximas o suficiente para trocarem de posto conforme o preço; a estrutura da recomendação (soja no verão + safrinha) é estável.

**Tempo de solve:** ~14 ms por ponto (CP-SAT, `OPTIMAL` com prova); fronteira de 14 pontos + 30 re-solves de robustez em segundos — muito abaixo do alvo de 1 min.

**Versões:** OR-Tools 9.15 · piso de risco ZARC ≤ 40% (a tábua só publica janelas ≤ 40%) · ciclo da soja = Grupo I (10 decêndios ≈ 100 dias) · preços/custos Conab out/2026.

### 9. Pendências antes da versão final

- Checagem das citações marcadas com ⚠️ (§8 Referências) — conferir forma exata de Haimes (1971), Akplogan et al. (2013) e Guiducci & Hirakuri (Embrapa/SOBER 2020).
