## Método (rascunho — seção do relatório final)

> M2 (motor de decisão) · rascunho de 22/10 — números reais pendentes na seção "Faltam".

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
- **Sequência:** milho safrinha só após a colheita da soja no mesmo talhão: liberação = plantio + ciclo da soja (~115–125 dias), premissa rastreável.

Toda recomendação pode ser lida como a lista de regras que a produziu — explicabilidade nativa, não pós-hoc.

### 3. Camada 2 — Margem sob risco (insumo do CP-SAT)

Para cada rotação viável, o Monte Carlo do M1 (bootstrap de ~20 anos de produtividade e preços reais) entrega a distribuição da margem: esperança, P(margem < 0) e P5 — os coeficientes da camada 3. Formulação: seção do M1.

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

### Faltam (preencher depois)

- Valores concretos da fronteira Pareto: nº de pontos, (margem, risco) por ponto, áreas por rotação em cada plano.
- Coeficientes por rotação vindos do MC do M1: margem esperada, P(margem < 0), P5.
- Taxa de estabilidade da recomendação sob perturbação ±10% — e o critério exato de "plano se mantém".
- Tempo de solve medido (alvo: < 1 min) e status de otimalidade reportado pelo solver.
- Talhões do cenário: quantidade, áreas (somando 600 ha) e grupos de solo 1/2/3 atribuídos.
- Valor fixado do ciclo da soja na regra de sequência (dentro da faixa 115–125 dias).
- Piso de risco ZARC (40%) confirmado com D2; versão do OR-Tools usada.
- Checagem das citações marcadas com ⚠️ antes da versão final.
