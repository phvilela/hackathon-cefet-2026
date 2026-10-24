# `data/raw/` - Dados brutos (HackatOhm 2026)

> **Regra:** Nunca depender de portais ao vivo. Tudo baixado e versionado aqui.
> - Município: **Patos de Minas (MG)** — Código IBGE: **3148004**
> - Área da fazenda (MVP): **600 ha** (3 talhões)
> - Coordenadas aproximadas da fazenda: **lat -18.58, lon -46.52**

## Estrutura

```text
data/raw/
├── ibge/
│   └── pam/        # IBGE SIDRA - Produção Agrícola Municipal (PAM)
├── inmet/
│   └── zips/       # ZIPs anuais do portal de Dados Históricos do INMET
├── nasa_power/     # Séries diárias por ponto do NASA POWER
└── zarc/           # Tábua de Risco ZARC 2026/27 (já versionado)
```

## 1) IBGE SIDRA - PAM (Tabela 839)

- **Fonte:** [apisidra.ibge.gov.br](https://apisidra.ibge.gov.br/)
- **Tabela:** `839` - Produção Agrícola Municipal
- **Município:** `n6/3148004` (Patos de Minas)
- **Variável principal:** `v/214` - Rendimento médio (kg/ha)
- **Produtos:** `c81/all` (filtrar depois para as culturas do modelo)
- **Período:** `p/last 20` (anos civis)
- **Endpoint de referência:**  
  `https://apisidra.ibge.gov.br/values/t/839/n6/3148004/v/214/p/last%2020/c81/all`
- **Arquivos esperados:** `ibge/pam/pam_3148004_rendimento_ultimos20.json` e `.csv`
- **Observações importantes:**
  - **Ano civil**, não ano-safra (jul/jun). A conversão precisa ser feita em `pipeline/pam.py`.
  - **Não separa milho 1ª e 2ª safra.** A Conab faz essa separação.
  - O código `3138107` **não** corresponde a Patos de Minas.

## 2) INMET - Dados Históricos (ZIPs anuais)

- **Fonte:** [portal.inmet.gov.br/dadoshistoricos](https://portal.inmet.gov.br/dadoshistoricos)
- **Método:** Download dos arquivos `.ZIP` por ano contendo CSVs de estações automáticas/convencionais.
- **Estação proxy utilizada:** **A523 - PATROCÍNIO (MG)**
  - Encontrada nos ZIPs a partir de **2006**. 
  - Patrocínio é próxima a Patos de Minas; por isso é utilizada como *proxy*. Essa limitação deve constar na rastreabilidade do projeto.
- **Arquivos presentes:** `inmet/zips/2000.zip` até `inmet/zips/2025.zip`
- **Padrão dos CSVs:** `INMET_*_<UF>_<CODIGO>_<NOME_ESTACAO>_DD-MM-AAAA_A_DD-MM-AAAA.CSV`
- **Variáveis mínimas para o projeto:** Precipitação (mm), Temperatura (Média/Mínima/Máxima), Umidade Relativa
- **Tratamento de falhas:** Valores `9999` e `-9999` devem ser tratados como **falha/nulo**. Nunca substituir por 0.
- **Observação:** O **BDMEP** ([bdmep.inmet.gov.br](https://bdmep.inmet.gov.br/)) gera **CSV por estação/período**, mas **não** possui opção de `.ZIP`. Os `.ZIP` anuais vêm **exclusivamente** do portal de Dados Históricos.

## 3) NASA POWER (Preenchimento de lacunas)

- **Fonte:** [power.larc.nasa.gov](https://power.larc.nasa.gov/) - NASA Prediction Of Worldwide Energy Resources
- **Método:** API pública (sem chave) por ponto geográfico
- **Coordenadas:** `longitude=-46.52`, `latitude=-18.58` (região da fazenda)
- **Comunidade:** `AG` (Agroclimatologia)
- **Parâmetros recomendados:**
  - `PRECTOTCORR` - Precipitação corrigida (mm/dia)
  - `T2M` - Temperatura do ar a 2m (°C)
  - `ALLSKY_SFC_SW_DWN` - Radiação solar incidente (kWh/m²/dia)
- **Endpoint de referência:**  
  `https://power.larc.nasa.gov/api/temporal/daily/point?parameters=PRECTOTCORR,T2M,ALLSKY_SFC_SW_DWN&community=AG&longitude=-46.52&latitude=-18.58&start=20050101&end=20251231&format=JSON`
- **Arquivos esperados:** `nasa_power/nasa_power_patos_2005_2025.json`
- **Uso:** Preencher lacunas da série INMET. **Toda linha processada deve ter `origem = 'inmet'` ou `origem = 'power'`.**

## 4) ZARC (já presente)

- **Fonte:** [dados.agricultura.gov.br](https://dados.agricultura.gov.br/)
- **Arquivos:** `zarc/tabua-risco-2026-2027-MG.csv`, `zarc/tabua-risco-2026-2027-patos-de-minas-3148004.csv`, portarias e dicionário
- **Uso:** Definir janelas viáveis por cultura × solo × decêndio.

## Proveniência (preencher ao baixar)

| Base | URL/Origem | Data do download | Filtros/Período | Arquivo(s) | Responsável |
| :-- | :----------- | :--------------: | :-------------- | :----------- | :----------: |
| **IBGE PAM** | `apisidra.ibge.gov.br` (t/839/n6/3148004) | `____-__-__` | 3148004, v/214, c81/all, p/last 20 (ano civil) | `ibge/pam/*` | D1 |
| **INMET Dados Históricos** | `portal.inmet.gov.br/dadoshistoricos` | `____-__-__` | ZIPs por ano 2000-2025; Estação A523 (Patrocínio) | `inmet/zips/*.zip` | D1 |
| **NASA POWER** | `power.larc.nasa.gov/api/temporal/daily/point` | `____-__-__` | lon=-46.52, lat=-18.58, 2005-01-01 a 2025-12-31, AG | `nasa_power/*.json` | D1 |

## Pegadinhas para não esquecer

- **Ano civil vs ano-safra:** PAM é ano civil. Clima deve ser agregado por janela de plantio do ZARC e depois relacionado ao ano-safra quando for para a tabela fato.
- **Milho 1ª x 2ª safra:** O PAM não distingue. A rastreabilidade precisa deixar isso explícito.
- **Estação proxy:** Patrocínio não é exatamente Patos de Minas. Documentar distância/código da estação sempre que for exibir números derivados da chuva/temperatura.
- **Valores 9999:** Falhas do INMET. Tratar como `NaN`, nunca como 0.
- **Nunca re-buscar no meio do pipeline:** Os arquivos brutos aqui são a **fonte única** para o processamento.
