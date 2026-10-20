# Relatório de Pesquisa — HackatOhm 2026
## "O que plantar?" — métodos de decisão para escolha de cultivos em 600 ha, Patos de Minas (MG)

> **Para o time:** este documento consolida **12 eixos de pesquisa** feitos por subagentes em paralelo (2 rodadas). O objetivo é nos alinhar sobre **qual método/mix de métodos usar** na proposta (pitch de 5 min + relatório de 3 páginas, nível conceitual — sem implementação obrigatória, mas com viabilidade técnica realista).

---

## 1. Contextualização: o desafio da Embrapa

A Embrapa Milho e Sorgo propôs o tema *"Engenharia digital aplicada à integração de dados climáticos, agronômicos e de mercado para apoio à escolha do cultivo de grãos no Cerrado"*.

O problema gira em torno das três perguntas clássicas do produtor:

| Pergunta | Quem já responde | Situação |
|---|---|---|
| **Quando** plantar | ✅ **ZARC** (Embrapa/MAPA) — janelas de plantio + classes de risco 20/30/40% por município, solo, ciclo e manejo | Já existe, é o baseline |
| **Como** plantar | — | **Fora do escopo** do desafio |
| **O que** plantar | ❌ **Ninguém** | **É o nosso desafio** |

Cenário concreto sugerido: **uma fazenda de 600 ha em Patos de Minas (MG)** que precisa decidir o cultivo (soja→milho safrinha? feijão→sorgo?), com base em dados de **clima, solo, custo de produção, preço de venda futuro, custo de oportunidade e custo alternativo**.

### O gap de mercado (confirmado por mapeamento de sistemas existentes)

Nenhum sistema disponível hoje responde "o quê plantar" integrando tudo:

- **ZARC / Zarc Plantio Certo** → só janela de plantio e risco climático, sem preço/custo/lucro.
- **AgroAPI Embrapa** (ZarcAPI, ClimAPI) → entrega *dados*, não *recomendação*.
- **DSSAT / APSIM / CropSyst / AquaCrop-FAO** → 100% biofísicos, calibração pesada, sem economia.
- **EcoCrop / GAEZ-FAO / CropSuite** → adequação agroclimática explicável, mas sem custo/preço.
- **Agro-techs comerciais** (Climatempo, Agrosmart, Aegro, Agrolend) → monitoram a lavoura *em curso* ou financiam **depois** da decisão.

**GAP-chave:** três mundos que não conversam — *biofísico/governamental* (ZARC, DSSAT), *econômico* (CEPEA, Aegro, custos Conab) e *operacional* (Climatempo, Agrosmart). E nada existente entrega **traceabilidade**: toda recomendação é caixa-preta.

**Frase-síntese do mapeamento:** *"Um EcoCrop econômico brasileiro"* — adequação climática + risco ZARC + potencial produtivo + margem regional, num ranking de "o que plantar" com **origem clicável de cada hipótese**.

---

## 2. Avaliação dos 12 métodos pesquisados

Cada eixo foi pesquisado por um subagente distinto, com busca de casos reais, trade-offs e viabilidade. Nota de **fit** (1-10) = aderência ao desafio específico (decisão de cultivo, dados públicos, prazo curto, pitch conceitual).

### 🥇 Nível A — candidatas fortes

#### 2.1 Google OR-Tools / CP-SAT — **9/10**

**O que é:** solver de programação por restrições da Google (híbrido CP + motor SAT, com Simplex e presolve emprestados do mundo MIP). Open source (Apache 2.0), Python/C++/Java/C#, `pip install ortools`.

**Por que se encaixa tão bem:**
- O problema é **naturalmente inteiro + lógico**: "cultura c no talhão p na dezena d" = variáveis binárias; janelas de plantio do ZARC por dezena = constraints de intervalos; "se soja no talhão X, então milho só depois" = `only_enforce_if` nativo (em MIP puro isso vira big-Ms frágeis).
- Problema **é pequeno**: 5-8 culturas × 10-30 talhões × 36 dezenas = algumas centenas de variáveis binárias → **resolve em segundos em laptop comum**.
- Referência acadêmica direta: Akplogan et al. 2013 (INRA) — crop allocation com hard/soft constraints, a mesma assinatura (ZARC como constraint dura).

**Pareto/multiobjetivo:** CP-SAT não tem objetivo multi nativo, mas **ε-constraint** resolve: fixar risco ≤ ε e maximizar lucro, varrendo ε → **fronteira lucro × risco**. Funciona até com fronteira não-convexa. Narrativa forte para o pitch: *"não vendemos UMA resposta, vendemos o menu de escolhas"* (perfis arrojado / conservador / equilibrado).

**Trade-off:** o gargalo real não é o solver, é **integrar os dados de entrada** (ZARC por dezena × grupos de solo, margens por cultura).

#### 2.2 Simulação Estocástica / Monte Carlo — **9/10**

**O que é:** simular clima + produtividade + preço como distribuições de probabilidade, milhares de iterações, e sair com **distribuição da margem** por combinação de culturas. Em vez de "qual cultura dá mais lucro?", responde **"qual cultura tem maior probabilidade de dar prejuízo?"**.

**Pontos únicos:**
- Modela a **correlação preço–produtividade** (cópulas): clima ruim no Brasil/na Russia → preço alto → *hedge natural*. Dados independentes superestimam erro.
- Modela o **risco da sequência** soja→milho safrinha: atraso na colheita da soja aperta a janela do milho → produtividade condicionada. Nenhum outro método captura isso.
- Saída na **mesma linguagem de risco do ZARC** (percentis 20/30/40%, P(cobrir custo)) — familiar ao produtor e ao agente de crédito (Proagro/PSR).

**Caso de referência perfeito:** **Embrapa (Guiducci & Hirakuri, SOBER 2020)** — Monte Carlo sobre produtividade/preços/insumos reais em municípios brasileiros. Validação: lucro determinístico caiu dentro do intervalo de 90% de probabilidade; descobertas: **safrinha é mais arriscada que milho de verão**; preço domina a sensibilidade na soja (cultura consolidada), produtividade domina em culturas menos tradicionais (patrão esperado em Patos de Minas).

**Trade-offs:** "lixo entra, lixo sai" (correlações mal estimadas com n≈20-30 anos contaminam tudo); assume distribuições estacionárias; **só avalia opções, não aloca hectares** → precisa de LP/CP-SAT em cima.

#### 2.3 Formulário de campo guiado (referência: LandPKS) — **9/10**

**O que é:** questionário por talhão perguntando ao produtor o que ele já sabe: área, **textura de solo** (arenosa/média/argilosa — chaves direto no **grupo 1/2/3 do ZARC**), histórico de cultivo, irrigação/maquinário, apetite de risco, canal de venda (cooperativa).

**Por que é o elo que faltava:** ZARC/IBGE/Conab são **municipais ou regionais**. A fazenda real tem variabilidade por talhão — o formulário é o que **des-generiza** a média: dois talhões podem receber janelas e potenciais diferentes se texturas divergem. Isso ataca diretamente a limitação do ZARC.

**Referencial open source:** **LandPKS** (USDA-ARS → Terraso) — gratuito, open source, faz coleta guiada de solo por GPS + foto + paisagem. Bragável: *"como LandPKS faz com dados globais, fazemos com a fazenda local"*.

**Custo:** Google Forms → planilha → mapeamento para grupo ZARC = dias de trabalho, custo zero. Prototipável com 1 mockup no pitch.

#### 2.4 Redes neurais leves (MLP) — **8/10**

**Onde cabem:** como **preditor de produtividade regional** (não de preço!), treinado sobre dados municipais tabulares (IBGE PAM + clima + solo). A literatura mostra: MLP 2 camadas ocultas + dropout + early stopping com validação leave-one-year-out é honesta e treinável em minutos.

**Evidência com números (produção de grãos):**
- Soja Brasil municipal (20 safras, PAM + ONI + MODIS): rRMSE ~16% municipal; ~5-7% nacional; previsão 3 meses antes da colheita com erro ~6% (von Bloh 2023).
- Cerrado/Matopiba: Random Forest R² 0,81, RMSE 177 kg/ha (Corniani 2021).
- Centro-Oeste + Sentinel-2: XGBoost R² 0,72 (precipitação, radiação e déficit hídrico = variáveis mais importantes).

**Achado crítico (honestidade):** "simples > complexo" em dados tabulares. Grinsztajn et al. 2022 e benchmark de Kadra: **GBDT/árvores superam deep learning em dados tabulares**; Huber et al. 2022 confirmaram na agricultura (XGBoost > DL na estimativa de yield, mais explicável via SHAP). No caso TUM 2022 o Bi-LSTM **perdeu para RF/XGBoost** e custou 3-4h vs segundos de treino.

**Trade-offs:** séries de safra são curtas (~20-40 obs por município) → overfitting é o risco nº 1; modelo "da fazenda" treinado só com dados dela é inviável.

#### 2.5 Fuzzy + árvore de decisão (camada explicável) — **8/10**

**Como encaixam** (não como motor, sim como **pré-filtro**):

```
[ZARC: risco ≤ 40%]    ──┐
[Solo: textura/pH]      ├→ FUZZY de adequação (score 0-1 por
[Clima: janela de chuva]┘   cultura × talhão × janela)
      ↓  (corte: score ≥ τ)
[Culturas viáveis]  →  MONTE CARLO (margem × risco)  →  CP-SAT (alocação)
```

- **Árvore de decisão manual (expert-based)**: 5-15 nós codificando regras do agrônomo (`IF risco_milho_safrinha ≥ 40% AND água_disponível < 60% THEN não recomendar`). Com séries curtas locais, é quase sempre preferível à árvore *induzida* de dados (que aprende onde a soja **foi** melhor, não onde **será** — e é instável).
- **Lógica fuzzy (Mamdani)**: variáveis linguísticas (chuva "baixa/média/alta") + regras IF-THEN de especialistas + defuzzificação (centroide) → score de adequação. Suaviza fronteiras artificiais do booleano (FAO land suitability). Literatura rica: fuzzy-MCDM para sorgo (2012, 30 citações), fuzzy-FAO (2018-2019), **ALUES** (SoftwareX 2022 — pacote R open source que faz exatamente adequação de terras FAO+fuzzy), review IEEE 2025 de fuzzy expert systems para crop recommendation, e FMOLP 2026 (fuzzy + LP como pipeline estabelecido).
- **Neutraliza a crítica "conjuntos fuzzy são subjetivos"**: usar como regra dura só o próprio ZARC; fuzzy apenas nos fatores flexíveis.

### 🥈 Nível B — componentes/inputs essenciais (não são "métodos", são ingredientes)

#### 2.6 Mercado futuro B3 (preço travável) — input indispensável

- Contratos: soja **SJC** (US$/sc, espelho CBOT) e milho **CCM** (R$/sc, mais líquido da B3). **Feijão e sorgo não têm futuro** → maior risco de preço → exigem **prêmio de risco** no comparativo de margens.
- Regra: `preço porteira = futuro ± basis − frete − desconto de qualidade`. A praça regional de referência é **Patrocínio** (Patos de Minas não é praça listada).
- Exemplo numérico: soja margem ≈ **R$ 4.180/ha (130%)** vs milho safrinha ≈ **R$ 2.600/ha (76%)** — e a diferença é **observável antes do plantio**, não é opinião do produtor.
- **Custo de oportunidade**: capital na Selic rende ~R$ 580/ha no ciclo → "não plantar" também é opção do modelo.
- Cautelas: basis oscila ±R$ 5-10/sc; limitar fixação antecipada a ~30-50% da produção (risco de frustração de safra).

#### 2.7 Revisão de literatura — o que o estado da arte diz

Quatro famílias pouco interlocuentes entre si:
1. **MCDA/aptação** (AHP/fuzzy/TOPSIS + GIS) — a mais consolidada (AHP em ~53% dos estudos).
2. **ML crop recommendation** — cresceu explosivamente, **com problemas graves de validação** (veja crítica abaixo).
3. **Simulação biofísica → zoneamento** — padrão Embrapa/FAO; sem economia.
4. **Otimização econômica de fazenda** (LP/MILP-CVaR, MOTAD, programação estocástica, LUSO/CSIRO 2025) — única família que integra clima+preço+risco, mas geralmente ignora aptidão edafoclimática.

**Consenso implícito de TODAS as revisões:** nenhum método vence; **o gargalo é a integração em cadeia** (aptidão → simulação de produtividade → margem → otimização) e a validação contra decisões reais. Ou seja: **a proposta híbrida é o estado da arte, não uma gambiarra** — esse é um argumento defensável no relatório.

**Papers brasileiros relevantes:**
- **Dantas Neto, Azevedo & Frizzone** (ESALQ/USP, SciELO) — LP para padrão de cultivo; Target-MOTAD mostra que o plano ótimo muda conforme a **aversão a risco**.
- **Lacerda et al.** (UFLA + Embrapa Milho e Sorgo, Sete Lagoas!) — rotação soja-milho em Cerrado: **o milho responde economicamente a NPK, a soja não** em solo de fertilidade construída.
- **Revista E&S 2026** — **o paper mais espelho do desafio**: avaliação econômica de segunda-safra no Cerrado sob restrições ZARC → feijão dominante, sorgo ótimo em janelas específicas, milho sistematicamente inferior economicamente.

#### 2.8 Coleta presencial clássica de solo — roadmap 7/10

Amostragem composta por talhão (trado zigzag 0-20 cm, 10-15 subamostras) → laboratório (R$ 25-60/amostra; prazo 3-10 dias úteis). 600 ha ≈ 10-15 talhões ⇒ **R$ 300-900, uma única vez** (textura, que define o grupo ZARC, é estável). Vale como "plano de 1ª safra", não como entrega do hackathon.

### 🥉 Nível C — descartar / mencionar como visão de futuro

#### 2.9 Câmeras/scanners para análise de solo — **4/10**

- **NIR portátil (AgroCares/SoilCares)**: existe, comercial (€2.650-6.695), mas calibração depende de base global (Brasil não é rotineiramente calibrado) + custo inviável para 5 estudantes.
- **Foto de smartphone (RGB)**: literatura acadêmica estima cor/textura/MO, mas **N/P/K não têm sinal espectral em RGB** — não mede fertilidade com robustez. Pode servir como **documentação/classificação grosseira** (ex: cor Munsell).
- **Veredito:** citar honestamente como "roadmap", não prometer.

#### 2.10 Jaya (metaheurística) — **5/10**

Algoritmo real (Rao 2016), open source, funciona tecnicamente para alocação com penalidades. Mas: **sem prova de otimalidade** e o LP/CP-SAT resolve o mesmo problema em segundos **com ótimo provado**. Só faria sentido em funções objetivo não-lineares/diferenciáveis tácitas. Se o júri valorizar "mostrar metaheurística", incluir apenas como bônus comparativo.

#### 2.11 Jev / Laya (modelos de decisão IA de 2026) — **2-3/10** ⚠️ desambiguação feita

**Veredito da pesquisa:** o nome citado mistura **dois itens distintos do mesmo hype recente de set/out 2026**:

| | **Jev** (TypeSafe AI) | **Laya** (Convai Innovations) |
|---|---|---|
| Modelo | Fechado, hospedado; texto + escolha → opção + probabilidade | **Open source (Apache 2.0)**, GitHub; encoders 322-421M parâmetros, roda em CPU |
| Propaganda | "193× mais rápido, 444× mais barato" que LLMs | 6-43 ms por resposta |
| Auditoria independente | Sem sinal → marca sempre a 1ª opção com 76-92% de confiança; probabilidade mal calibrada fora do domínio; sem LGPD | **Zero-shot ≈ acaso** (36-43% de acurácia; 6,04/100 no Decision Index); cai a 15-19% sob distratores; checklist de calibração precisa ser refeito por domínio |

**Por que descartar para o desafio:** o problema é **alocação espacial com restrições duras** (otimização restrita), não classificação texto→opção com poucos exemplos rotulados. E o Jev é fechado/sem LGPD — péssimo para "risco climático". Se o júri valorizar, o ponto forte é justamente dizer *"avaliamos Jev/Laya e descartamos com evidência"* (Laya zero-shot: 6,04/100).

#### 2.12 RNN/LSTM e CNN — **7/10**, papel delimitado

- **LSTM para PREÇO: não usar.** Futuros da B3 já agregam a expectativa do mercado (eficiência de mercado; Fed: futuros vencem o random walk apenas "modestamente"). Papers que mostram LSTM batendo ARIMA ganham no in-sample e perdem fora da amostra.
- **LSTM para produtividade/séries climáticas longas (ERA5)**: funciona (LSTM global R² 0,82), mas RF/XGBoost geralmente empatam ou ganham com muito menos custo.
- **CNN sobre imagens de satélite (MODIS/Sentinel)**: caso de uso real e mensurável (MAPE 4-6% em Iowa; R² 0,88 com Sentinel-2 na China) — **complemento visual**, não argumento central.
- **CNN sobre imagem de solo**: dado escasso no Cerrado → descartar.

---

## 3. Arquitetura recomendada (convergência de todos os eixos)

Os subagentes chegaram **independentemente** na mesma arquitetura híbrida:

```
DADOS PÚBLICOS                           CAMADAS DE DECISÃO
═══════════════                          ══════════════════
ZARC (CKAN dados.agricultura.gov.br;     ① ADEQUAÇÃO EXPLICÁVEL
     testado HTTP 200)      ──┐             (fuzzy + árvore manual):
IBGE SIDRA PAM (apisidra;      │             score 0-1 de cada cultura por
     muni 3148004; HTTP 200) ──┤   tabela     talhão × janela, com regras
Conab preços/custos (painéis  ──┤   fato:      auditáveis do agrônomo.
     XLS, sem API REST)    ──┤  município ×  ↓ corta para culturas viáveis
NASA POWER (API sem chave,   ──┤  safra ×    ② MARGEM SOB RISCO
     testada OK; lat/lon da ──┤  cultura       (Monte Carlo): mundo
     fazenda)              ──┘  + campo       climático × produtividade ×
        ║                                   preço (curva futura B3, NÃO
  INMET BDMEP (download                     previsão ML) → distribuição
  manual; API antiga 404)                   da margem por rotação
                                           ③ ALOCAÇÃO ÓTIMA (CP-SAT):
        ║                                     max margem s/ restrições
CAMADA DE CAMPO (formulário                  ZARC/rotação/600 ha;
estilo LandPKS: textura→grupo                fronteira Pareto lucro×risco
de solo, maquinário, risco,                  via ε-constraint
venda) ──────────────────────────►          ④ TRACEABILIDADE:
                                               "por que soja?" → hipótese
                                               clicável até a fonte
```

**Os 4 diferenciais de pitch:**
1. **Usamos ZARC como restrição dura** e fuzzy como pré-filtro explicável — carrega explicabilidade e conformidade regulatória "antes da economia".
2. **Preço = curva futura B3** (observável antes do plantio) **cenários Conab** — não "previsão de IA" que você não pode verificar.
3. **Fronteira Pareto** lucro × risco: soja/milho/feijão/sorgo comparados na linguagem de percentis do próprio ZARC (20/30/40%).
4. **Traceabilidade** — o gap confirmado que ninguém cobre: cada número com link para a fonte que o fundamenta.

---

## 4. Dados: verificação real (HTTP testada pelos subagentes)

| Base | Status | Chave/atenção |
|---|---|---|
| NASA POWER | ✅ API sem chave, testada OK | lat/lon da fazenda (≈ −18,58, −46,52); fill de lacunas do INMET |
| INMET BDMEP | ⚠️ download manual OK; **API antiga 404** | estação mais próxima; automáticos brutos, lacunas=9999 |
| ZARC | ✅ CKAN dados.agricultura.gov.br (HTTP 200) | município × cultura × **grupo de solo** × safra |
| IBGE SIDRA PAM | ✅ API testada (tabela 839, HTTP 200) | **Patos de Minas = código IBGE 3148004** (3138107 não existe!) |
| Conab | ⚠️ painéis XLS/CSV, sem API REST; portal instável | praça regional = Patrocínio; preço porteira = praça − frete |
| Redape Embrapa | ✅ DOI, FAIR | pontual; calibrar premissas de rendimento |

**Modelo de integração:** tabela fato `município × safra × cultura`; clima por estação-mais-próxima/POWER; produtividade proxy = rendimento PAM; preço = praça regional + basis.

---

## 5. Crítica metodológica que vale citar no relatório

- O dataset Kaggle "Crop Recommendation" (2.200 amostras, 22 culturas) — base de **muitos papers com 99%+ de acurácia** — é **sintético, rotulado por faixas de adequação**: as classes são literalmente separáveis pelas features. Acurácia alta = **artefato do benchmark**, não validação agronômica.
- **Kapoor & Narayanan 2023** (*Patterns*): data leakage infla resultados em 17 campos científicos; **One Earth 2025**: validação espacial/temporal e benchmarks FAIR são pré-requisitos em ML agrícola.
- Muitos fuzzy expert systems estão "fracamente validados contra resultados reais de fazenda" (review IEEE 2025).

**Por que isso nos ajuda:** mostra por que escolhemos **otimização + economia com risco medido** em vez de "IA que adivinha a cultura" — e nos posiciona criticamente acima da média dos competidores que vão cair nessa armadilha.

---

## 6. Números e referências prontas (verificar citação antes de publicar!)

| Ref | Achado citável |
|---|---|
| ZARC/Embrapa | Metodologia (ISNA, balanço hídrico) economizou **R$ ~1 bi/ano** em sinistros Proagro |
| Guiducci & Hirakuri, SOBER 2020 | Monte Carlo Embrapa validado (lucro determinístico dentro do intervalo de 90% prob.) |
| Reis et al. 2023, *Logistics* | Programação estocástica 2 estágios: **US$ 4,3 mi** a mais vs determinístico |
| Akplogan et al. 2013, INRA | Crop allocation com hard/soft constraints (mesma assinatura CP-SAT) |
| Carauta et al. 2021, *Agricultural Systems* | Cenário seco inviabiliza safrinha em MT ("no more double-cropping") |
| Thomas et al. 2025, *Agricultural Systems* | LUSO/CSIRO: rotações com lucro + risco (CVaR) |
| Lacerda et al. (UFLA+Embrapa) | Milho responde a NPK economicamente, soja não (Cerrado) |
| Grinsztajn et al. 2022 | Árvores > deep learning em dados tabulares |
| von Bloh et al. 2023 | Previsão de rendimento soja: erro ~6% nacional, 3 meses antes |
| Revista E&S 2026 | Feijão dominante, sorgo contextual, milho inferior — 2ª safra Cerrado sob ZARC |
| Haimes 1971 | ε-constraint (base da fronteira Pareto) |
| Rao 2016 | Algoritmo Jaya (descartado com justificativa) |

⚠️ *Alguns itens (Mackenzie 2025, CropSuite 2025, número do ZARC "R$ 1 bi/ano") vêm de busca web dos subagentes — confirmar fonte original antes de entregar o relatório oficial.*

---

## 7. Risca/pendências para o time resolver

1. **Escolher o ponto de corte da fronteira Pareto** para o exemplo numérico (soja R$ 4.180/ha vs milho safrinha R$ 2.600/ha vs feijão/sorgo com prêmio de risco).
2. **Decidir o foco do pitch:** mostrar arquitetura completa ou só gap + traceabilidade (sugestão: gancho inicial no gap + 1 slide por camada + fechamento com números).
3. **Validar as citações** marcadas como "verificar" (subagentes podem ter rumores).
4. **Não esquecer:** ano civil (PAM) ≠ safra Jul-Jun; PAM não separa milho 1ª/2ª safra (usar Conab); ZARC é municipal (formulário de campo resolve por talhão).

## 8. Mensagem central para o pitch

> *"A Embrapa já diz **quando** plantar. Nós dizemos **o quê** — com evidência: ZARC e conhecimento agronômico viram regras explicáveis (fuzzy), clima e histórico viram margem sob risco (Monte Carlo sobre dados reais de PAM/Conab/B3), e a decisão final fica no produtor: uma **fronteira lucro × risco** em Pareto, com cada resposta clicável até a fonte que a sustenta. Avaliamos 12 métodos com evidência — e descartamos os que os dados não suportam."*
