# O que plantar? — Desafio Embrapa

### Integração de dados climáticos, agronômicos e de mercado para a escolha de cultivos no Cerrado

> **🏆 1º lugar no HackatOhm 2026** · desafio proposto pela **Embrapa Milho e Sorgo** · CEFET-MG
> Equipe de 5 estudantes de Engenharia de Computação · entrega: 26/10/2026

---

## 1. O desafio, em 30 segundos (para quem não conhece o assunto)

Um produtor rural de **Patos de Minas (MG)** tem uma fazenda de **600 hectares** e precisa decidir **o que plantar**: soja seguida de milho safrinha? Feijão seguido de sorgo? Milho "sozinho" no verão?

O governo já responde **quando** plantar: o **ZARC** (Zoneamento Agrícola de Risco Climático, ferramenta da Embrapa/MAPA) indica as épocas seguras para cada cultura, município e tipo de solo. Mas **ninguém responde o quê** — juntando clima, solo, custo de produção e preço de venda numa recomendação que o produtor consiga conferir.

**Este projeto responde o "quê"** — e cada número da resposta tem **fonte clicável**: nada de caixa-preta.

## 2. A ideia, em 1 parágrafo

A decisão vira três perguntas encadeadas, cada uma com método e saída próprios:

```
[Dados oficiais: ZARC, IBGE/SIDRA, Conab, clima]
        │
        ▼
(1) ADEQUAÇÃO — "o que PODE ser plantado aqui, e quando?"
    regras oficiais do ZARC, por tipo de solo de cada talhão
        │
        ▼
(2) MARGEM SOB RISCO — "quanto rende cada opção, e com que risco?"
    Monte Carlo sobre o histórico real de produtividade e preços
        │
        ▼
(3) ALOCAÇÃO — "quantos hectares em cada opção?"
    otimização (CP-SAT) que divide os 600 ha e devolve um MENU
        │
        ▼
   MENU DE PLANOS: Arrojado · Equilibrado · Conservador
   + cada número com hipótese, fonte e método (rastreabilidade)
```

Não vendemos UMA resposta: entregamos o menu e marcamos nele o ponto de melhor equilíbrio entre lucro e segurança — **a decisão final continua sendo do produtor**, agora com evidência.

## 3. 🗺️ Onde fica cada coisa (mapa do repositório)

```
hackatohm/
│
│  📄 A PESQUISA POR TRÁS DAS ESCOLHAS
├── relatorio_pesquisa_metodos.md  → 12 métodos avaliados, trade-offs e referências
│
│  🧠 O MOTOR — engine/ (o código que decide)
├── engine/
│   ├── adequacao.py       → CAMADA 1: lê o ZARC oficial e calcula o que PODE ser plantado, quando e por tipo de solo
│   ├── monte_carlo.py     → CAMADA 2: margem sob risco, simulada sobre o histórico real
│   ├── model.py           → CAMADA 3: monta o "quebra-cabeça" (áreas por rotação em cada talhão)
│   ├── solver.py          → CAMADA 3: resolve (1º a maior margem possível; depois, o menor risco)
│   ├── pareto.py          → gera o MENU: planos Arrojado / Equilibrado / Conservador
│   ├── robustness.py      → teste de estresse: a recomendação sobrevive a ±10% de variação em preço/custo?
│   ├── validation.py      → confere se a "fazenda virtual" faz sentido (ex.: áreas somam 600 ha)
│   ├── report.py          → escreve o relatório e o JSON de resultados
│   ├── visualization.py   → desenha o gráfico do menu
│   ├── config.yaml        → A FAZENDA VIRTUAL: talhões, margens, riscos, janelas — o arquivo editável
│   ├── margens_mc.json    → margens e riscos reais por rotação (saída do Monte Carlo)
│   ├── janelas_zarc.json  → janelas de plantio REAIS, geradas pelo adequacao.py (com fontes e premissas)
│   ├── main.py            → o "botão de rodar": junta tudo
│   ├── README.md          → como o motor funciona por dentro (visão técnica)
│   └── out/               → RESULTADOS GERADOS: relatório em texto, o gráfico e o results.json
│
│  🖥️ O SITE — web/ (React + Vite + TypeScript)
├── web/
│   ├── src/App.tsx            → as 3 telas: cenário, comparação de planos e rastreabilidade
│   ├── src/components/        → componentes de cada tela
│   ├── src/data/results.json  → o resultado publicado que o site lê (status REAL)
│   └── src/data/zarc.json     → janelas do ZARC para o cenário
│
│  📊 DADOS OFICIAIS
├── data/raw/zarc/         → tábua de risco do ZARC, safra 2026/27 (Patos de Minas e todo o MG),
│                            dicionário de dados e as portarias oficiais em PDF
├── data/processed/        → tabela fato e séries limpas, geradas pelos importadores
│
│  📓 ANÁLISES DE DADOS
├── notebooks/             → exploração de produtividade, clima e preço (Jupyter);
│                            os CSVs de notebooks/saida*/ alimentam o pipeline
│
│  📝 DOCUMENTAÇÃO
├── docs/adequacao_regras.md   → as regras de plantio em linguagem clara, com fontes e insights
│
│  📦 O CONTRATO — contract/ (o motor escreve, o site lê)
├── contract/
│   ├── results.schema.json → o formato oficial do arquivo de resultados (JSON Schema 2020-12)
│   ├── validate.py         → o "porteiro": valida forma + semântica e publica (`--publish`)
│   └── results.json        → o arquivo oficial publicado
│
│  🔧 O PIPELINE DE DADOS — pipeline/
├── pipeline/
│   ├── sanity.py          → QA de ordem de grandeza: margens vs literatura, unidades (R$/sc × sc/ha),
│   │                        recomposição da margem, chuva, nulos
│   ├── fato.py            → tabela fato oficial com produtividade e preço reais PAM/SIDRA, custo
│   │                        Conab e chuva INMET/NASA POWER — origem_* por linha (rastreabilidade)
│   ├── hipoteses.py       → monta as hipóteses de margem a partir da tabela fato
│   ├── clima.py · pam.py · zarc.py  → importadores D1 (data/raw → data/processed)
│   └── mercado.py         → importador D2 (custos Conab)
│
└── requirements.txt       → a lista de bibliotecas necessárias para rodar
```

### Não quer explorar pastas? Vá direto ao ponto:

| Se você quer… | Abra… |
|---|---|
| entender o problema e a solução **sem código** | seções 1 e 2 deste README |
| **rodar a demonstração** agora | seção 4 (abaixo) |
| ver os **resultados congelados** que o site lê | `contract/results.json` |
| ver as **janelas de plantio reais** e as regras | `docs/adequacao_regras.md` |
| entender **por que** escolhemos cada método | `relatorio_pesquisa_metodos.md` |
| mudar as premissas da fazenda virtual | `engine/config.yaml` |
| checar **se os números são críveis** (QA) | `python3 pipeline/sanity.py` |
| ver **os dados que o site lê** | `web/src/data/results.json` |
| entender o **código** do motor | `engine/README.md` |

## 4. Como rodar

### O motor (Python)

Abra um terminal **na pasta do projeto** e execute, nesta ordem:

```bash
# 1. Instalar as bibliotecas (só na primeira vez)
python3 -m pip install -r requirements.txt

# 2. Gerar as janelas de plantio a partir dos dados oficiais do ZARC
python3 engine/adequacao.py

# 3. Rodar o motor de decisão
python3 engine/main.py --pareto --monte-carlo

# 4. Testes de sanidade: os números são críveis? (ordem de grandeza vs literatura)
python3 pipeline/sanity.py

# 5. Validar o contrato e publicar o arquivo oficial
python3 contract/validate.py --publish
```

**Se deu certo**, você verá no terminal o resumo das janelas de plantio e do menu de planos — e três arquivos em `engine/out/`:

- `relatorio_engine.txt` — relatório em português, feito para ser lido;
- `pareto_frontier.png` — o gráfico do menu;
- `results.json` — os resultados em formato de dados.

O passo 5 valida esse JSON (contra `contract/results.schema.json` + checagens de consistência) e **publica a cópia oficial em `contract/results.json`** — é este arquivo, e não o de `engine/out/`, que o site lê. O passo 4, antes dele, é o **QA de credibilidade**: margens plausíveis contra a literatura, unidades certas (o clássico "R$/t virou R$/sc" explode aí), a margem declarada reconstituída a partir das próprias hipóteses da rotação, chuva plausível para o Cerrado. Assim o motor pode continuar sendo rodado sem surpreender o site: só entra no ar o que passar nos dois porteiros.

> ℹ️ Se aparecer uma mensagem de erro de "segmentation fault" **depois** de o programa terminar, ignore: é um defeito conhecido de uma biblioteca no Python 3.14 ao encerrar — os arquivos já foram salvos normalmente.

### O site (React + Vite)

```bash
cd web
npm install
npm run dev     # servidor local
npm run build   # build de produção
```

## 5. De onde vêm os dados (todos públicos)

| Fonte | O que dá ao projeto | Situação |
|---|---|---|
| **ZARC** — MAPA ([dados.agricultura.gov.br](https://dados.agricultura.gov.br)) | janelas de plantio e risco por município, cultura, ciclo e tipo de solo | ✅ `data/raw/zarc/`, safra 2026/27 + portarias |
| **IBGE — SIDRA/PAM** ([sidra.ibge.gov.br](https://sidra.ibge.gov.br)) | produtividade e preço históricos municipais | ✅ integrado (`pipeline/`) |
| **Conab** ([portaldeinformacoes.conab.gov.br](https://portaldeinformacoes.conab.gov.br)) | custos de produção (soja, milho, feijão, sorgo) | ✅ integrado (`pipeline/`) |
| **INMET** e **NASA POWER** | chuva e temperatura da região | ✅ integrado (`pipeline/`) |
| **B3** ([b3.com.br](https://www.b3.com.br)) | preços futuros (referência de "preço travável") | 📥 base baixada para análise; o resultado final usa o preço SIDRA |

> ✅ **Dados reais:** as janelas de plantio vêm da tábua de risco oficial do ZARC (safra 2026/27); margens e riscos vêm de Monte Carlo sobre o histórico real de produtividade e preço (IBGE PAM/SIDRA) e custos de produção da Conab. O arquivo `web/src/data/results.json` carrega `status: REAL`, e cada hipótese traz fonte e método.

## 6. Status do projeto (transparência)

| Peça | Estado |
|---|---|
| Regras de plantio (adequação, ZARC real) | ✅ pronto |
| Dados econômicos + simulação de margem | ✅ integrados |
| Motor de decisão (Monte Carlo + CP-SAT + menu + estresse) | ✅ pronto |
| Resultados reais + congelamento do contrato | ✅ `status: REAL` |
| Site de demonstração (3 telas) | ✅ `web/` |
| Vídeo pitch (5 min) + relatório (3 págs) | ✅ entregues · **1º lugar** |

## 7. 📖 Glossário para não-especialistas

- **ZARC** — Zoneamento Agrícola de Risco Climático: o "calendário oficial" que indica, para cada município, cultura e tipo de solo, as épocas de plantio com risco de perda aceitável (20/30/40%).
- **Decêndio** — período de ~10 dias; o ZARC divide o ano em 36 ("dec1" = 1–10 de janeiro, "dec36" = 21–31 de dezembro).
- **Talhão** — pedaço da fazenda com solo parecido entre si. A fazenda de 600 ha do exemplo tem 3 talhões.
- **Grupo de solo (e classes AD)** — forma de classificar o solo (arenoso / médio / argiloso). No ZARC, soja/milho/feijão usam classes de água disponível (AD1–AD6); o projeto faz essa tradução e documenta.
- **Rotação / safrinha** — plantar duas culturas em sequência no mesmo ano agrícola (ex.: soja na primavera, milho logo após a colheita — o "milho safrinha").
- **Monte Carlo** — "rolar o dado" milhares de vezes usando o histórico real, para medir não só o lucro médio, mas o risco de dar prejuízo.
- **CP-SAT** — ferramenta gratuita do Google que resolve um "quebra-cabeça" com regras e **prova** que achou a melhor solução possível (não é um palpite).
- **Fronteira de Pareto / knee point** — o menu de opções margem × risco; o "joelho" da curva é o ponto de melhor equilíbrio (nosso plano **Equilibrado**).

## 8. O time

| Papel | Membro | Responsável por |
|---|---|---|
| D1 — Clima & Produtividade | Matheus Ramos | IBGE PAM, INMET/NASA POWER, talhões do cenário |
| D2 — Mercado & ZARC | Luis Vilela | Conab, B3, janelas ZARC, rastreabilidade, roteiro do pitch |
| M1 — Monte Carlo | Pedro Lopes | simulação de margem sob risco, validação, sensibilidade |
| M2 — CP-SAT & Adequação | Matheus Henriques | motor de otimização, regras de adequação, vídeo |
| M3 — Integração & Contrato | Pedro Vilela | tabela fato, contrato de dados, congelamento dos resultados |

*Estudantes de Engenharia de Computação — CEFET-MG. Desafio HackatOhm 2026, proposto pela Embrapa Milho e Sorgo.*

## 9. Para se aprofundar

- **A pesquisa por trás das escolhas** (12 métodos avaliados, trade-offs, referências): [`relatorio_pesquisa_metodos.md`](relatorio_pesquisa_metodos.md)
- **As regras de plantio com os dados reais de 2026/27**: [`docs/adequacao_regras.md`](docs/adequacao_regras.md)
- **Como o motor funciona por dentro**: [`engine/README.md`](engine/README.md)
