# ZARC — Tábua de Risco, safra 2026/2027 (dados brutos)

Dados do **Zoneamento Agrícola de Risco Climático (ZARC)** usados na camada de
"janelas de plantio" do modelo HackatOhm 2026 (fazenda 600 ha, Patos de Minas-MG,
código IBGE **3148004**, lat ≈ −18.58, lon ≈ −46.52).

## Fonte primária (CKAN do MAPA)

- Dataset: **"Zoneamento Agrícola de Risco Climático (Zarc) - Tábua de Risco"**
  - Portal: https://dados.agricultura.gov.br
  - `package_id`: `6d3d141c-885e-41a4-ab7f-dc8ff323b96f`
  - API: `https://dados.agricultura.gov.br/api/3/action/package_show?id=6d3d141c-885e-41a4-ab7f-dc8ff323b96f`
  - Mantenedor: CGRA/DEGER/SPA (renan.monteiro@agro.gov.br), atualização diária.
- Recurso usado: **"Tábua de risco - Safra 2026/2027"** (CSV nacional, ~211 MB)
  - `resource_id`: `139e5a60-1f43-4cc8-aeab-a35dbbf816c0`
  - URL direta:
    `https://dados.agricultura.gov.br/dataset/6d3d141c-885e-41a4-ab7f-dc8ff323b96f/resource/139e5a60-1f43-4cc8-aeab-a35dbbf816c0/download/dados-abertos-tabua-de-risco-safra-2026-2027.csv`
  - Safra mais recente disponível em 22/10/2026 (o arquivo foi modificado no próprio
    dia 22/10/2026 — atualização diária). Safras 2016/17 a 2025/26 também existem no
    mesmo dataset.
- O CSV nacional original (211 MB) **não** foi mantido aqui (regra: > 20 MB). Cópia
  temporária em `/tmp/opencode/zarc/tabua-risco-2026-2027.csv` (sujeita a limpeza).
  Para re-baixar: `curl -A "Mozilla/5.0" --http1.1 -L -o <arquivo> "<URL direta acima>"`
  (nota: sem `--http1.1`/User-Agent o servidor às vezes reseta a conexão).

## Arquivos neste diretório

| Arquivo | Conteúdo |
|---|---|
| `tabua-risco-2026-2027-patos-de-minas-3148004.csv` | **202 linhas** de Patos de Minas (geocodigo 3148004), safra 2026/27, todas as 17 culturas zoneadas p/ o município (inclui as 5 do modelo + braquiária, girassol etc.) |
| `tabua-risco-2026-2027-MG.csv` | **150.733 linhas** de todo o estado de MG (853 municípios), safra 2026/27, todas as culturas. Útil p/ vizinhança regional e mapas |
| `dicionario-de-dados-tabua-de-risco-2026.pdf` | Dicionário de dados oficial do MAPA (colunas, códigos de solo/ciclo/clima/manejo) |
| `portarias/` | 8 PDFs: as portarias SPA/MAPA 2026/27 de MG para soja (200), milho 1ª (223), milho 2ª (324), sorgo granífero (275), sorgo forrageiro (302), feijão sequeiro (13), feijão irrigado (32) e feijão 2ª safra (359). Contêm metodologia, classes de solo, tabela de conversão decêndio↔data e listas de cultivares |

## Formato do CSV

- Separador `;`, **UTF-8 com BOM**, quebras de linha **CRLF**, sem quoting (valores
  não contêm `;`).
- 55 colunas (19 de identificação + `dec1`..`dec36`):

| Coluna | Significado |
|---|---|
| `Nome_cultura` | Nome da cultura zoneada (ex.: `Soja`, `Milho 2ª Safra`, `Sorgo Granífero`, `Feijão`) |
| `SafraIni`, `SafraFin` | Ano inicial/final da safra (2026/2027) |
| `Cod_Cultura` | Código composto MAPA (ex. soja `12016720000011`; sufixo `...011`=1ª safra, `...021`=2ª safra) |
| `Cod_Ciclo` | Grupo de ciclo da cultivar: **20=Grupo I, 21=Grupo II, 22=Grupo III** (24=IV, 25=V, 26=VI; 13=perene, 19=semiperene). Milho: G-I ≤110 dias, G-II 110–130, G-III >130. Soja: ciclos ~100/115/130 dias |
| `Cod_Solo` | **Sorgo: 1=arenoso, 2=textura média, 3=argiloso.** Soja/Milho/Feijão: **11=AD1 … 16=AD6** (classes de água disponível; AD1≈24 mm … AD6≈95 mm de CAD, IN SPA/MAPA nº 1/2022) |
| `geocodigo` | Código IBGE de 7 dígitos do município (**3148004** = Patos de Minas) |
| `UF`, `municipio` | Sigla UF e nome do município |
| `Cod_Clima`, `Nome_Clima` | Classe climática (p/ culturas perenes/olericolas; `0` = Não se aplica nas anuais aqui) |
| `Cod_Outros_Manejos`, `Nome_Outros_Manejos` | **1=Sequeiro, 2=Irrigado** (3=irrigado c/ controle de geada). Ex.: feijão tem linhas sequeiro E irrigado |
| `Produtividade`, `Cod_NM` | Vazios (`NaN`) na maioria; milho 2ª safra usa `0` |
| `Cod_Munic` | Código SICOR do município (Patos de Minas = `028549`) |
| `Cod_Meso`, `Cod_Micro` | Mesorregião IBGE (`05` = Triângulo Mineiro/Alto Paranaíba) e microrregião (`020` = Patos de Minas) |
| `Portaria` | Portaria que publica a janela (ex. `Port.200_de_03-07-2026`) |
| `dec1`..`dec36` | **Risco (%) associado ao plantio naquele decêndio**: `20`, `30` ou `40` = classe de risco da janela; **`0` = fora da janela (não plantar)** |

### Convenção decêndio ↔ data (confirmando o item 3.3 das portarias)

3 decêndios por mês: `dec1`=1–10 jan, `dec2`=11–20 jan, `dec3`=21–31 jan, …,
`dec36`=21–31 dez. I.e. `decN` → mês `(N-1)//3 + 1`, parte `(N-1)%3 + 1`
(1º/2º/3º decêndio do mês). Ex.: soja Patos de Minas: `dec28`=`1–10 out`,
`dec36`=`21–31 dez`; milho 2ª safra: `dec1`=1–10 jan, `dec3`=21–31 jan.

### Classes de risco

`20` = risco de perda ≤ 20% · `30` = ≤ 30% · `40` = ≤ 40% · `0` = inviável/não zoneado
naquele decêndio. ZARC vale para cultivo de **sequeiro** (linhas irrigadas existem
só p/ feijão; a portaria diz que lavouras irrigadas não ficam restritas às janelas).

## Como parsear (recomendação)

1. Ler com `pd.read_csv(caminho, sep=';', encoding='utf-8-sig')`.
2. Filtrar: `geocodigo == 3148004`, `SafraIni == 2026`, `Nome_cultura` em
   {`Soja`, `Milho 1ª Safra`, `Milho 2ª Safra`, `Sorgo Granífero` (grão) ou
   `Sorgo Forrageiro`, `Feijão` (1ª) e `Feijão 2ª Safra`}; `Nome_Outros_Manejos == 'Sequeiro'`.
3. **Unpivot** `dec1..dec36` → linha por (cultura, ciclo, solo, decêndio) e decodificar
   decêndio em data (`dec N` → mês/parte acima; data-fim do decêndio = dia 10, 20 ou
   último dia do mês).
4. "Decêndio viável com risco ≤ 40%" = qualquer `decN ∈ {20,30,40}`;
   opcionalmente separar por classe (`==20`, `≤30`, `≤40`) para score decrescente.
5. Chaves de agregação: `Nome_cultura × Cod_Ciclo (20/21/22) × Cod_Solo`
   (sorgo 1/2/3; demais AD1–AD6 = 11..16). Se o modelo não souber o solo da fazenda,
   usar o pior caso (AD1/arenoso = mais restritivo) ou juntar por interseção.

## Fallbacks/alternativas (documentação)

- **Embrapa AgroAPI (Agritec)**: `https://api.cnptia.embrapa.br/agritec/v2`
  (época de plantio derivada do ZARC + cultivares p/ 12 culturas). Exige cadastro em
  https://www.agroapi.cnptia.embrapa.br/portal/ → criar aplicação → Consumer Key/Secret
  → Access Token (`Authorization: Bearer …`, validade 60 min). Sem token o gateway
  responde `900902 Missing Credentials` (testado 22/10/2026).
- **SISZARC**: https://sistemasweb.agricultura.gov.br/siszarc/base.action (relatórios
  PDF/XLS por cultura/safra/UF).
- **Painel ZARC**: https://mapa-indicadores.agricultura.gov.br/publico/extensions/Zarc/Zarc.html
- **App Plantio Certo** (iOS/Android, citado nas portarias).
- **Portarias por estado**:
  https://www.gov.br/agricultura/pt-br/assuntos/riscos-seguro/programa-nacional-de-zoneamento-agricola-de-risco-climatico/portarias/safra-vigente/minas-gerais
  (atenção: os PDFs 2026/27 de MG têm nomes crípticos `PO*.PDF`; a página associa
  título↔arquivo).

## Checksums (sha256, 16 primeiros hex)

- tabua-risco-2026-2027-MG.csv: `2dd614cdffd6b495`
- tabua-risco-2026-2027-patos-de-minas-3148004.csv: `ffa91efc15b150fd`
- dicionario-de-dados-tabua-de-risco-2026.pdf: `2143127cd635744e`

Baixado/extraído em 2026-10-22 por subagente de dados (nada foi commitado).
