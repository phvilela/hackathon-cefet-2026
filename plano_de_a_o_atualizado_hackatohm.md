# Plano de Ação Estratégico — "O que plantar?" (HackatOhm)
**Escopo:** Solução de abrangência nacional (MVP baseado em dados estáticos de biomas representativos), arquitetura desacoplada (API + Web App) e pitch focado em valor agronômico e financeiro.

---

## Fase 1: Curadoria de Dados Estáticos (O "Motor" do MVP Nacional)
Para provar que a ferramenta funciona no Brasil todo sem depender de APIs instáveis durante a apresentação, criaremos um banco de dados estático e representativo.

*   **Ação 1.1: Seleção de Municípios-Amostra:** Escolher de 3 a 5 cidades que representem realidades agronômicas distintas. Sugestão:
    *   *Patos de Minas (MG)* - Cerrado (Foco original, sucessão Soja -> Milho/Sorgo).
    *   *Passo Fundo (RS)* - Sul (Sucessão de inverno: Soja -> Trigo/Aveia).
    *   *Barreiras (BA)* - Matopiba (Escala, janelas restritas de chuva, Algodão).
*   **Ação 1.2: Extração de Dados (Data Prep):** Baixar em `.csv` ou `.json` os dados dessas cidades:
    *   **ZARC:** Janelas de plantio e risco (20/30/40%) para as culturas viáveis.
    *   **IBGE (PAM):** Histórico de produtividade municipal (baseline).
    *   **NASA POWER:** Histórico climático básico (chuva/temperatura).
    *   **Conab / B3:** Custos de produção da região e uma "foto" estática dos preços de mercado/futuros para compor as margens.
*   **Ação 1.3: Mapeamento Regional:** Criar uma tabela "de-para" que ligue cada município-amostra à sua respectiva praça de precificação da Conab/B3.

## Fase 2: Desenvolvimento do Backend (Python + FastAPI)
Construção do cérebro da aplicação, responsável por processar os dados e entregar a recomendação via API REST.

*   **Ação 2.1: Setup da API:** Inicializar um projeto FastAPI, que consumirá os arquivos `.csv`/`.json` da Fase 1 e exporá endpoints para o frontend.
*   **Ação 2.2: Implementação da Adequação (Fuzzy/Árvore):** Codificar as regras agronômicas. Exemplo dinâmico: Se a região for RS, liberar sucessão com trigo; se for MT, liberar algodão safrinha. Cortar o que o clima/solo não permite.
*   **Ação 2.3: Motor de Risco (Monte Carlo Simples):** Um script que cruza o histórico climático com a produtividade e o preço, retornando distribuições de probabilidade de lucro (ao invés de um lucro fixo ilusório).
*   **Ação 2.4: Otimizador de Alocação (OR-Tools / CP-SAT):** Configurar o solver para pegar os talhões da fazenda (ex: 600ha divididos) e retornar 3 opções de alocação (Fronteira Pareto):
    *   *Cenário Arrojado* (Maximização de lucro, tolera maior risco ZARC).
    *   *Cenário Equilibrado*.
    *   *Cenário Conservador* (Menor risco, lucro seguro).

## Fase 3: Desenvolvimento do Frontend (React, Vue ou Angular)
A interface onde o produtor ou agrônomo interage com a plataforma. Foco total em usabilidade e na promessa de "traceabilidade".

*   **Ação 3.1: Formulário de Entrada (Onboarding da Fazenda):** 
    *   Tela para o usuário selecionar o município (dentre os mapeados no MVP).
    *   Adicionar talhões: área (ha) e tipo de solo (arenoso/médio/argiloso) para linkar diretamente com os Grupos 1, 2 e 3 do ZARC.
*   **Ação 3.2: Dashboard de Decisão (O Menu de Opções):**
    *   Consumir a API e exibir os 3 cenários de alocação (Conservador, Equilibrado, Arrojado) em formato de cards simples.
    *   Mostrar métricas claras: Lucro esperado (R$/ha) vs. Risco de prejuízo (%).
*   **Ação 3.3: Camada de Traceabilidade (O Diferencial):**
    *   Implementar modais/tooltips em cada recomendação. Se a tela diz "Plante Soja e Trigo no Talhão 2", deve haver um ícone de informação onde o agrônomo clica e vê: *"Baseado na portaria ZARC XYZ, no grupo de solo 2, com expectativa de preço baseada na B3 praça X"*. Isso mata a objeção da "caixa-preta".

## Fase 4: Preparação do Pitch e Relatório (Foco Agronômico)
O discurso deve focar na dor do campo, não no código.

*   **Ação 4.1: Construção da Narrativa (Storytelling):**
    *   *O Problema:* O ZARC diz *quando*, ninguem diz *o que* plantar integrando grana e risco de forma clara e confiável.
    *   *A Solução:* Não vendemos uma IA que adivinha o futuro. Vendemos um motor econômico embasado por regras agronômicas oficiais.
    *   *O Valor:* Empoderamento. A decisão final é do produtor (escolhendo seu apetite de risco), mas com base em dados rastreáveis.
*   **Ação 4.2: Demonstração (Live Demo do MVP):**
    *   Mostrar a tela do frontend funcionando. Escolher um município, preencher a textura do solo e mostrar como o sistema entrega o card de decisão e, o mais importante, clicar no botão de "origem dos dados" (Traceabilidade).
*   **Ação 4.3: Redação do Relatório Final (LaTeX):**
    *   Documento de 3 páginas (pode ser feito no Overleaf para ficar visualmente executivo).
    *   Destacar a arquitetura adotada, o teste com 3 biomas distintos e a robustez das fontes de dados (Conab, ZARC, B3).

## Resumo da Arquitetura do MVP (Para o Readme/Relatório)
```text
[Frontend (React/Vue)] 
  ├── Coleta: Município + Perfil dos Talhões (Textura do solo)
  ├── Exibição: Perfis de Risco (Conservador/Arrojado)
  └── Traceabilidade: Links visuais para a origem dos dados
         ↕ (Comunicação via JSON/REST)
[Backend (Python/FastAPI)]
  ├── Filtro Agronômico (Fuzzy - corta o que não cresce ali)
  ├── Motor Econômico (Monte Carlo - calcula probabilidade de lucro)
  └── Solver (CP-SAT - distribui os hectares otimizando lucro/risco)
         ↑ (Consumo offline)
[Base de Dados Estática (CSV/JSON)]
  └── ZARC, IBGE, Conab, NASA (3 municípios amostragem: MG, RS, BA)
```