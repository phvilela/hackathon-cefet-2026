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

**Coeficientes congelados** (regime de preços 2026/27; margem em R$/ha, risco em ‰ = P[margem < 0] × 10):

| Rotação | Margem esperada | Risco (‰) | P[margem < 0] |
|---|---|---|---|
| soja → milho safrinha | R$ 4.496,73/ha | 220 | 22,0% |
| soja solteira | R$ 3.695,44/ha | 200 | 20,0% |
| soja → sorgo safrinha | R$ 2.473,64/ha | 281 | 28,1% |
| milho 1ª safra | R$ 896,79/ha | 515 | 51,5% |
| feijão das águas → sorgo | R$ 380,41/ha | 498 | 49,8% |
| capital pousio (CDI) | R$ 200,00/ha | 0 | 0,0% |

Sorgo e feijão não têm série anual em Patos; usam preço Conab de referência com volatilidade lognormal documentada (CV 20% e 25%). Custos são médias Conab 2024–2026 das regiões de Cerrado.

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

### 8. Resultados congelados (26/10, status `REAL`)

**Cenário:** 600 ha em 3 talhões — T1 300 ha (grupo de solo 2, médio) · T2 200 ha (grupo 1, arenoso) · T3 100 ha (grupo 3, argiloso). 6 rotações candidatas.

**Fronteira de Pareto** (7 pontos, ε-constraint, piso de margem ≥ 85% do ótimo; todos com prova de otimalidade):

| # | Margem total | Ha sob risco |
|---|---|---|
| 1 | R$ 2.537.780 | 128,0 |
| 2 | R$ 2.461.972 | 123,7 |
| 3 | R$ 2.385.874 | 119,4 |
| 4 | R$ 2.309.775 | 115,0 |
| **5 (knee)** | **R$ 2.233.677** | **110,6** |
| 6 | R$ 2.157.869 | 106,3 |
| 7 | R$ 120.000 | 0,0 |

**Os três perfis do menu:**

| Perfil | Margem | Ha sob risco | Alocação |
|---|---|---|---|
| **Arrojado** | R$ 2.537.780 | 128,0 | soja→milho 400 ha · soja solteira 200 ha |
| **Equilibrado** (knee) | R$ 2.233.677 | 110,6 | soja→milho 400 ha · soja solteira 113 ha · **capital pousio 87 ha** |
| **Conservador** | R$ 120.000 | 0,0 | capital pousio 600 ha |

> "Ha sob risco" = risco total (‰·ha) ÷ 1000 = hectares com margem negativa esperada. O perfil Equilibrado paga R$ 304.103 de margem (−12%) para fugir de 17,4 ha de risco (−13,6%) — e ainda reserva 87 ha no CDI.

**Robustez sob ±10% em preço/custo** (30 re-solves, seed 42): **30/30 cenários resolvidos**, estabilidade média **100%** — a alocação **não muda em nenhum talhão** em nenhum cenário (distribuição de mudanças: 30 rodadas com 0 talhões alterados). A recomendação não é fruto da estimativa pontual.

**Tempo de solve:** ~14 ms (CP-SAT, status `OPTIMAL` com prova) — muito abaixo do alvo de 1 min.

**Versões:** OR-Tools 9.15 · piso de risco ZARC ≤ 40% (confirmado com D2) · ciclo da soja = Grupo I (10 decêndios ≈ 100 dias).

### 9. Pendências antes da versão final

- Checagem das citações marcadas com ⚠️ (§8 Referências) — conferir forma exata de Haimes (1971), Akplogan et al. (2013) e Guiducci & Hirakuri (Embrapa/SOBER 2020).
