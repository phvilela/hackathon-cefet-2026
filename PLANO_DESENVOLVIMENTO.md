# Plano de Desenvolvimento — HackatOhm 2026
## Quarta 21/10 → Entrega: segunda 26/10 · Time: 2 Dados + 3 Motor

> **Como ler este plano:** cada dia tem (1) *por quê* — a explicação do conceito para quem nunca viu o tema, (2) *tarefas* — por pessoa, e (3) *pronto quando* — o critério objetivo de término do dia. Se você é estudante de computação e nunca ouviu falar de Monte Carlo ou CP-SAT, as seções "Por quê" resolvem isso.

---

## 1. A ideia da solução em 1 parágrafo

Vamos construir um **pipeline de dados** que responde *"o que plantar numa fazenda de 600 ha em Patos de Minas (MG)"* em três camadas:

1. **Adequação** — que culturas *podem* ser plantadas ali (regras do ZARC + tipo de solo do talhão);
2. **Simulação (Monte Carlo)** — para cada opção viável, sorteamos milhares de "safras virtuais" para medir **margem e risco**;
3. **Alocação (CP-SAT)** — um solver do Google divide os 600 ha entre as opções respeitando as regras e gera um **menu de escolhas** (fronteira Pareto).

O site (domingo) só **lê um arquivo JSON** que o pipeline produz. O desafio pede exatamente isso: *"integração de dados climáticos, agronômicos e de mercado"*.

```
[IBGE PAM]──┐
[INMET/NASA]─┤
[ZARC]──────┼─→ pipeline (Python) ─→ fato ─→ Monte Carlo ─→ CP-SAT ─→ results.json
[Conab]─────┤                                                        │
[B3]────────┘                                                        ╞═ CONTRATO
                                                                     ↓
                                                    web/ (domingo, só lê o JSON)
```

### O contrato (`results.json`) — o herói invisível

É um arquivo JSON com **schema combinado** (como uma API versionada) que separa as duas metades do projeto. Ele existe **mockado desde quarta** com números inventados plausíveis — por isso o frontend pode ficar pro final sem risco: quem faz o frontend só depende do contrato, nunca do motor.

### Decisões de escopo (plano único — consolidado com o "plano de ação estratégico")

O time passou a ter **um só plano**. Decisões registradas para não existirem duas verdades (o plano antigo, `plano_de_a_o_atualizado_hackatohm.md`, foi removido — o histórico do git o preserva):

| Tema | Decisão |
|---|---|
| **Município do MVP** | **Só Patos de Minas** (cenário recomendado do desafio, Cerrado) — demo profunda, zero scope creep |
| **Barreiras (BA)** | **Stretch goal** ("se sobrar tempo"): com o pipeline parameterizado por município, o 2º município sai quase de graça — e generaliza o pitch DENTRO do tema (Cerrado/Matopiba) |
| **Passo Fundo (RS)** | Fora do tema (Cerrado) → **vira slide de roadmap** no pitch ("a arquitetura generaliza para outros biomas") |
| **Backend** | Frontend começa lendo o **`results.json` estático**; **wrapper fino FastAPI** (2-3 endpoints servindo o mesmo JSON) SÓ se sobrar tempo no domingo — nunca bloqueia a demo |
| **Relatório** | Markdown → PDF (LaTeX/Overleaf apenas se alguém dominar — não vale o tempo) |

No Plaky, os itens "se sobrar tempo" estão no grupo **Extras (se sobrar tempo)**, com status **Backlog** — sem prazo, não contam contra o cronograma.

### Glossário rápido (para não travar na leitura)

| Termo | Tradução simples |
|---|---|
| **Tabela fato** | Tabela única onde 1 linha = município × safra × cultura, com todas as colunas (chuva, produtividade, preço, custo) ao lado. O coração da "integração de dados" |
| **Bootstrap empírico** | Sortear com reposição dos ~20 anos reais de histórico — "rolar o dado" usando o dado real, sem inventar distribuições |
| **Monte Carlo** | Repetir o sorteio 10.000× → sai um histograma da margem: *"em 85% dos sorteios, soja cobre o custo"* |
| **CVaR / P5** | Medidas de "quão ruim é o ano ruim" (a cauda esquerda do histograma) |
| **CP-SAT** | Solver de programação por restrições (Google OR-Tools, `pip install ortools`). Resolve "quebra-cabeças": preencher 600 ha respeitando regras duras maximizando margem — e **prova** que achou o ótimo |
| **Fronteira Pareto** | Menu: para cada nível de risco aceito, qual a maior margem possível. Não vendemos UMA resposta, vendemos as escolhas |
| **Rastreabilidade** | Cada número na tela carrega um cartão: valor + fonte (link) + suposição. O diferencial do pitch: *"por que soja? clique e veja"* |

---

## 2. O time (2 Dados + 3 Motor) e quem faz o que

| Papel | Pessoa | Domínio principal | Tarefas extras |
|---|---|---|---|
| **D1 — Clima & Produtividade** | dados | IBGE SIDRA (PAM), INMET, NASA POWER → produtividade histórica + clima por janela | Relatório: seção de dados |
| **D2 — Mercado & ZARC** | dados | Conab (preços praça Patrocínio + custos), cotações B3, parse das janelas ZARC | Tabela de hipóteses rastreáveis; roteiro do vídeo (domingo) |
| **M3 — Integração & Contrato** | motor | Tabela fato, schema `results.json` + validador, sanity checks, repo/infra | Coordenador do relatório (noites) |
| **M1 — Monte Carlo** | motor | Distribuições, bootstrap, risco da sequência soja→milho, correlação preço–produtividade, outputs | Relatório: seção de método |
| **M2 — CP-SAT & Adequação** | motor | Regras de adequação (se/então), modelo CP-SAT, fronteira Pareto, validação do solver | Relatório: seção de resultados; edição do vídeo (segunda) |

**⚠️ Não temos pessoa dedicada a QA/relatório — então essas tarefas estão distribuídas:**
- **Sanity checks de números → M3** (é parte do pipeline, não tarefa à parte);
- **Relatório → cada um escreve a seção da sua parte (noites, 30-60 min/dia)**, M3 consolida. O conteúdo já existe ~80% pronto em `relatorio_pesquisa_metodos.md` — é transformar, não escrever do zero;
- **Vídeo → domingo o time inteiro grava a demo; segunda M2 edita** (roteiro de domingo por D2).

### Ritual leve (sem burocracia)

- **Checkpoints de 15 min às 10h e às 17h** (remoto + presencial): o que travou, o que quebra o contrato;
- **Git:** trunk-based — branches curtas, merge direto na `main`, sem PR review formal (o "review" é o pipeline rodando verde);
- **O contrato só muda em checkpoint combinado** — quem quebra o schema quebra o time inteiro;
- **Feature freeze do motor: sábado no fim do dia, inegociável.**

### Estrutura do repo

```
hackatohm/
├── data/
│   ├── raw/            # bases baixadas (versionadas — nunca depender de portal)
│   └── processed/      # fato.parquet, etc.
├── pipeline/           # pam.py · clima.py · mercado.py · zarc.py · fato.py · sanity.py
├── engine/             # adequacao.py · monte_carlo.py · cpsat.py
├── contract/           # results.schema.json · results.json · validate.py
├── notebook/           # exploração + gráficos (reaproveitar no relatório/vídeo)
├── web/                # (domingo)
├── docs/               # relatório.md · storyboard.md
└── relatorio_pesquisa_metodos.md   # já existe — base do relatório final
```

---

## 3. Dia a dia

### 📅 QUARTA (21) — Fundação: dados na mão + contrato

**Por quê:** tudo depende de dados reais, e portais públicos são lentos/instáveis (a Conab já deu timeout nos testes). Baixar tudo hoje e versionar elimina esse risco para sempre. E o contrato mockado é o que permite o frontend ficar pro final.

**Tarefas:**

1. **(Todos, 30 min)** Kickoff: repo, README, kanban (GitHub Projects), stack — Python 3.11+, `pandas`, `numpy`, `ortools` (`pip install ortools`).
2. **(D1)** IBGE SIDRA (API): produtividade histórica por cultura, ~20 anos. Endpoint testado:
   `https://apisidra.ibge.gov.br/values/t/839/n6/3148004/v/214,112/p/last 20`
   ⚠️ **Patos de Minas = código IBGE 3148004** (o 3138107 não existe!).
   Baixar também INMET (ZIPs históricos no portal — a API antiga retorna 404) e NASA POWER (API por lat/lon da fazenda ≈ −18.58, −46.52; funciona sem chave).
3. **(D2)** Conab: painéis de **preços da praça Patrocínio** (Patos não é praça!) + **custos de produção** por cultura; ZARC: CSV "Tábua de Risco" no CKAN `dados.agricultura.gov.br`; B3: registrar cotações futuras do dia (soja/milho) — é o "preço travável".
4. **(M3)** Escrever o **contrato**: `contract/results.schema.json` + `results.json` mock (2 culturas, números plausíveis inventados) + `validate.py` (falha se o arquivo não bate com o schema). Esboço inicial do schema:

```jsonc
// results.json — esqueleto inicial (M3 refina na quarta)
{
  "cenario": { "municipio": "Patos de Minas", "cod_ibge": 3148004,
               "area_total_ha": 600, "safra": "2026/27" },
  "talhoes": [ { "id": 1, "area_ha": 300, "grupo_solo_zarc": 2, "textura": "media" } ],
  "rotacoes": [ {
      "id": "soja->milho",
      "margem_esperada_rs_ha": 0,           // preenchido pelo MC
      "p_margem_negativa": 0,               // P(margem < 0)
      "percentis": { "p5": 0, "p50": 0, "p95": 0 },
      "hipoteses": [ { "chave": "produtividade_soja", "valor": 60,
                       "unidade": "sc/ha", "fonte_url": "...", "metodo": "media PAM 20 anos" } ]
  } ],
  "fronteira_pareto": [ { "risco": 0, "margem": 0, "plano": { "soja->milho": 600 } } ],
  "planos": { "arrojado": {}, "equilibrado": {}, "conservador": {} }
}
```

5. **(M1)** Notebook de exploração: histograma da produtividade histórica da soja e do milho em Patos de Minas; scatter chuva×produtividade por ano.
6. **(M2)** Rodar o tutorial oficial de CP-SAT (hello-world) para tirar o susto; escrever rascunho das **regras de adequação** (se/então, espelhando o ZARC).
7. **(Todos, noite, 30 min)** Cada um cria seu arquivo de rascunho no `docs/relatorio/` com os títulos das suas seções.

**Pronto quando:** `data/raw/` preenchido · `results.json` mock passa no `validate.py` · qualquer um clona e roda `make setup`.

**Pegadinhas:** PAM usa **ano civil**, não ano-safra (jul–jun) — anotem a regra de conversão · PAM **não separa milho 1ª de 2ª safra** (a Conab separa) · INMET marca falha como `9999`.

---

### 📅 QUINTA (22) — Tabela fato: onde os mundos se encontram

**Por quê:** a **tabela fato** (conceito de data warehouse) é a materialização do que o título do desafio pede: uma linha = município × safra × cultura, com chuva da janela de plantio, produtividade histórica, preço e custo **na mesma linha**. Sem isso, cada análise vive numa planilha isolada — exatamente o problema que criticamos no pitch.

**Tarefas:**

1. **(D1)** `pipeline/pam.py`: produtividade (kg/ha) por cultura × ano, convertida para ano-safra (regra documentada no código). Depois `pipeline/clima.py`: por ano, chuva e temperatura **na janela de plantio do ZARC** (por dezena) — INMET com lacunas preenchidas por NASA POWER (flag `origem` em cada linha).
2. **(D2)** `pipeline/mercado.py`: série de preço (praça Patrocínio, R$/t internamente — padronizar!) e custos (R$/ha) por cultura; guardar cotação futura B3 de hoje em `hipoteses.json`. Depois `pipeline/zarc.py`: janelas permitidas por cultura × grupo de solo × dezena, em formato de tabela.
3. **(M3)** `pipeline/fato.py`: junta tudo → `data/processed/fato.parquet`. Rodar `pipeline/sanity.py` (testes de ordem de grandeza):
   - produtividade média de soja em Patos de Minas ~55–65 sc/ha (checar contra Embrapa/Conab);
   - **unidades**: saca de 60 kg? R$/sc ou R$/t? Padronizar em R$/t internamente, converter só na exibição;
   - nenhuma coluna com >10% de nulos sem explicação.
4. **(M1)** A partir do fato (versão parcial já serve): medir correlação histórica produtividade×preço e produtividade_soja×produtividade_milho (o atraso da soja correlaciona com quebra do milho?) — alimenta o MC de amanhã.
5. **(M2)** `engine/adequacao.py` v0: regras se/então por cultura × grupo de solo (ex.: *"risco ZARC da dezena > 40% → dezena não é viável"*). Output já no formato do contrato.

**Pronto quando:** `fato.parquet` completo · notebook com visão geral que **qualquer um do time abre e entende** · sanity checks verdes · adequação v0 escrevendo no formato do contrato.

**Pegadinhas:** feijão/soja/milho têm pesos de saca e praças diferentes — padronizar cedo evita refactor no sábado.

---

### 📅 SEXTA (23) — Monte Carlo: o coração do risco

**Por quê:** o produtor não decide pela média, decide pelo risco de quebrar. Monte Carlo responde na **mesma linguagem do ZARC** (percentis): *"no plano soja→milho, em 85% dos sorteios a margem cobre o custo; P5 = R$ 210/ha"*. É o que transforma dados em decisão defensável.

**Tarefas:**

1. **(M1)** `engine/monte_carlo.py`: **bootstrap empírico** — reamostrar (com reposição) os ~20 anos reais de produtividade e preço; 10.000 iterações. Menos hipótese, mais dado.
2. **(M1)** **Risco da sequência** (detalhe que ninguém mais modela): atraso da colheita da soja encurta a janela do milho safrinha → penalidade condicionada na produtividade do milho (calibrar com dados do ZARC; documentar como premissa rastreável).
3. **(M1)** **Correlação preço–produtividade:** v0 independente; v1 = correlação negativa simples (clima ruim → preço alto = hedge natural).
4. **(M2)** Apoio ao MC: saídas por **rotação** (soja→milho, soja→sorgo, feijão→sorgo, milho verão, ...) → margem esperada, **P(margem<0)**, P5/P50/P95, CVaR 5% — tudo no formato do contrato. Gráficos bonitos no `notebook/` (histograma + curva de margem acumulada) — **reaproveitar no vídeo**.
5. **(D1)** Consolidar as janelas ZARC por cultura × grupo de solo na forma final (é insumo do CP-SAT de amanhã).
6. **(D2)** Começar a **tabela de hipóteses rastreáveis**: cada número que aparecerá na tela → fonte (URL) + método + suposição. É a matéria-prima da tela 3.
7. **(M3)** QA do dia: bater os números contra a literatura (soja ≈ R$ 4.180/ha vs milho-safrinha ≈ R$ 2.600/ha) — se der muito diferente, entender *por quê* antes de seguir. Congelar contrato v2 se houver mudança.

**Pronto quando:** `results.json` com MC completo para ≥4 rotações · histogramas prontos · números batem com a ordem de grandeza da literatura.

---

### 📅 SÁBADO (24) — CP-SAT: o quebra-cabeça ótimo + menu Pareto

**Por quê:** com MC sabemos quanto cada rotação rende e arrisca; falta **dividir os 600 ha** respeitando as regras duras (só janelas permitidas pelo ZARC pro solo daquele talhão, milho só depois da soja no mesmo talhão, capital). O CP-SAT resolve isso **com prova de otimalidade, em segundos**, num problema desse tamanho. A fronteira Pareto é o produto final: o menu de escolhas por perfil de risco.

**Tarefas:**

1. **(M2)** `engine/cpsat.py`:
   - **variáveis:** área (ha) por rotação × talhão × janela (inteiros);
   - **restrições:** Σ área = 600 · só janelas permitidas (ZARC × grupo de solo do talhão) · rotação (milho só depois da soja no mesmo talhão) · capital máximo;
   - **objetivo:** `margem_esperada − λ·risco` (coeficientes vindos do MC de sexta).
2. **(M2)** Sweep de λ (ou ε-constraint) → **5–8 pontos da fronteira Pareto** + planos para 3 perfis (arrojado / equilibrado / conservador).
3. **(M2 + M1)** **Validação obrigatória:** λ=0 → tudo na rotação de maior margem esperada; risco mínimo → porto seguro; solve < 1 min. Se der estranho, é bug de modelagem de restrição (90% das vezes é a rotação).
4. **(M1)** Suporte: rodadas de sensibilidade (±10% no preço/custo → a recomendação muda? Isso vira um insight do pitch).
5. **(D1 + D2)** Montar os **3 talhões fictícios plausíveis** (texturas diferentes → grupos de solo 1/2/3, áreas somando 600 ha) — esses dados alimentam a tela 1 amanhã. Fechar a tabela de hipóteses rastreáveis (todas as fontes com URL).
6. **(M3)** **Congelar todos os números de tela** no `results.json` FINAL + validador verde.

**🏁 FEATURE FREEZE DO MOTOR no fim do dia.** A partir daqui, o motor não muda — só o frontend, o relatório e o vídeo.

**Pronto quando:** `results.json` final congelado (rotações, fronteira, 3 planos, hipóteses com fonte) · validação do solver passou · sensibilidade rodada.

**Plano B (se o CP-SAT travar):** alocação *greedy* (ordenar rotações por margem/risco e preencher hectares) + fronteira aproximada por pesos. O produto fica visualmente idêntico; documentar honestamente. O produto **não pode depender** do solver.

---

### 📅 DOMINGO (25) — Frontend: 3 telas + primeira gravação

**Por quê agora funciona:** com o contrato congelado, o site é só **leitura do JSON** — zero lógica de negócio. 5 pessoas fazem em 1 dia. E a demo já é gravada hoje (garantia de entrega), porque segunda é só edição/relatório.

**Tarefas:**

1. **(Todos, manhã)** Setup React+Vite+Recharts, deploy na Vercel **no primeiro commit** (deploy contínuo — membros remotos veem sozinhos).
2. **Tela 1 — Talhões (D1 + M1):** os 3 talhões + "formulário" (textura → grupo de solo ZARC, área, perfil de risco) — modo demonstração com cenários prontos.
3. **Tela 2 — Comparação (M3 + M2):** ranking margem × risco + gráfico da **fronteira Pareto** (scatter + linha), com percentis na linguagem 20/30/40% do ZARC.
4. **Tela 3 — Rastreabilidade (D2):** "por que soja e não milho?" — painel de hipóteses com **fonte clicável** (SIDRA/Conab/ZARC) + comparação lado a lado com a opção descartada. *Essa tela é o diferencial do pitch — capriche.*
5. **(Todos, tarde)** Modo apresentação (dark, fonte grande), transições suaves; **gravar a demo completa cena por cena**, mesmo com polish parcial.
6. **(D2, noite)** Roteiro de narração final (~750 palavras = 5 min) — usar o storyboard da seção 5.
7. **(Stretch — só se as 3 telas estiverem 100%)** **(M3)** Wrapper fino FastAPI: 2-3 endpoints servindo o `results.json` (bônus de arquitetura para o relatório; para o vídeo, indistinguível do JSON estático).

**Pronto quando:** site no ar com dados reais · demo gravada ponta a ponta · rascunho do relatório 90% pronto.

---

### 📅 SEGUNDA (26) — Pitch + relatório + entrega (com buffer)

1. **(M2 + D2)** Gravação final da narração + edição do vídeo: máx. 5:00, zoom nos painéis, trilha neutra, capa e créditos.
2. **(D1 + M3)** Relatório 3 páginas: passar o rascunho a limpo, inserir gráficos do `notebook/` (histograma do MC + fronteira Pareto), revisão cruzada (um revisa o texto do outro), conferir as citações marcadas ⚠️ em `relatorio_pesquisa_metodos.md`.
3. **(M1)** Checklist de entrega: vídeo no formato pedido, relatório em PDF, repo limpo com README ("como rodar em 3 comandos"), backup em nuvem, **submeter com ≥2h de folga**.
4. **(Todos)** Buffer pro que estourar — sempre estoura alguma coisa.

**Pronto quando:** confirmação de submissão recebida.

---

## 4. Os 3 riscos e as mitigações (já embutidas no plano)

| Risco | Mitigação |
|---|---|
| **Relatório e vídeo 100% de segunda** (o erro clássico que entrega atrasado) | Relatório em pedacinhos nas noites (M3 consolida; conteúdo já 80% pronto) · demo gravada domingo · roteiro pronto domingo à noite |
| **Motor atrasar** | Plano B do sábado (greedy + cenários Conab) a um commit de distância · feature freeze do motor no sábado |
| **Dados/portal cair** | Tudo baixado e versionado na quarta · nenhuma chamada de API ao vivo no site |

---

## 5. Storyboard do vídeo (5 min ≈ 750 palavras)

| Tempo | Cena |
|---|---|
| 0:00–0:45 | Problema: produtor decide "o que plantar" no escuro; o ZARC resolve "quando", ninguém resolve "o quê" |
| 0:45–1:30 | O gap: 3 mundos que não conversam (biofísico / econômico / operacional) + nenhuma rastreabilidade |
| 1:30–3:30 | **Demo**: cadastra talhão → culturas viáveis (adequação/ZARC) → fronteira Pareto margem×risco → clica "por que soja?" → hipóteses com fonte |
| 3:30–4:15 | Os números: comparação final (soja/milho/feijão/sorgo, prêmio de risco p/ quem não tem futuro B3, Selic como custo de oportunidade) |
| 4:15–5:00 | Fechamento: *"A Embrapa diz quando. Nós dizemos o quê — com evidência."* + roadmap (coleta de solo R$ 300–900/talhão, scanner NIR como visão) |

## 6. Esqueleto do relatório (3 páginas)

1. **Página 1 — Problema e gap (0,5 pág)** · o que existe (ZARC etc.) · o que falta ("o quê", com rastreabilidade)
2. **Página 2 — Método (1,5 pág)** · arquitetura das 3 camadas · tabela fato · Monte Carlo (com 1 histograma) · CP-SAT + fronteira Pareto (com 1 gráfico) · como o ZARC vira restrição
3. **Página 3 — Resultados e roadmap (1 pág)** · comparação final entre rotações (tabela) · sensibilidade · limitações honestas (premissas, séries curtas) · roadmap (coleta de campo, NIR) · referências

> **Fonte de conteúdo:** quase tudo já está escrito em `relatorio_pesquisa_metodos.md` — as seções são *transformar e resumir*, não escrever do zero. Citações marcadas com ⚠️ precisam de verificação antes da versão final.

---

## 7. Bases de dados — referência rápida

| Base | Acesso | Granularidade | Atenção |
|---|---|---|---|
| IBGE SIDRA PAM | API: `apisidra.ibge.gov.br/values/t/839/n6/3148004/...` | município × ano civil × cultura | **código 3148004**; não separa milho 1ª/2ª |
| NASA POWER | API sem chave, por lat/lon | ponto diário/mensal | fill de lacunas do INMET |
| INMET BDMEP | download manual (portal) | estação, diário | API antiga 404; falhas = `9999` |
| ZARC | CKAN `dados.agricultura.gov.br` (CSV) | município × cultura × solo × dezena | municipal, não fazenda — por isso a tela de talhões |
| Conab | painéis (XLS/CSV), sem API REST | preço: semanal × praça (Patrocínio); custo: município-referência × safra | portal instável — baixar tudo |
| B3 | cotações do dia (site) | contrato × vencimento | feijão/sorgo não têm futuro → prêmio de risco |

---

*Plano gerado em 21/10/2026. Ajustes de rota só em checkpoint — o cronograma tem buffer, mas não tem espaço para replanejar tudo duas vezes.*
