# Diretrizes de Identidade Visual — "Safra Certa"

> Base extraída da **Tela 1 (Talhões)**, que já está implementada e aprovada.
> Serve de fonte única de verdade para construir a **Tela 2 (Comparação)** e a
> **Tela 3 (Rastreabilidade)** sem divergir de estilo.
>
> Tokens machine-readable: [`web/src/tokens.css`](src/tokens.css).
> **Regra de ouro:** se um valor não está em `tokens.css`, provavelmente não deve
> existir. Adicione o token antes de usar.

---

## 1. Princípios

| # | Princípio | O que significa na prática |
|---|-----------|----------------------------|
| 1 | **Agronômico, não "SaaS azul"** | A paleta vem do campo: papel, verde folha, terracota, areia. Nada de azul-violeta de dashboard genérico. |
| 2 | **Editorial / confiável** | Tipografia serifada nos números e títulos (voz de autoridade, tipo relatório Embrapa); sans limpa na UI. |
| 3 | **Cada número é rastreável** | Dado real ganha selo `.real-badge`; dado ilustrativo é rotulado. A identidade comunica honestidade. |
| 4 | **Cor = significado** | Cor nunca é decorativa. Vermelho/verde/lime sempre dizem algo sobre risco, estado ou ação. |
| 5 | **Superfície quente, profundidade sutil** | Fundo `--bg` com gradientes radiais suaves; cards "flutuam" com sombra esverdeada, não cinza. |

---

## 2. Paleta

### 2.1 Base e tinta

| Token | Hex | Uso | ⚠️ Evitar |
|-------|-----|-----|-----------|
| `--bg` | `#f2efe7` | Fundo da página (papel) | Não usar como cor de card |
| `--surface` | `#fbfaf6` | Card principal (`.panel`) | — |
| `--surface-2` | `#f5f1e8` | Bloco rebaixado (`.stat`) | — |
| `--ink` | `#17251b` | Texto principal | Não usar preto puro `#000` |
| `--muted` | `#5c6659` | Texto secundário, rótulos | Nunca para texto de corpo longo |
| `--line` | `#ded9cb` | Borda padrão | — |
| `--line-soft` | `#ebe6da` | Divisor interno sutil | — |

### 2.2 Marcas

| Token | Hex | Uso | ⚠️ Evitar |
|-------|-----|-----|-----------|
| `--green` | `#1d4d33` | Verde primário. Títulos em destaque, perfil **Equilibrado** | Não usar em fundo escuro (contraste) |
| `--green-2` | `#2f6b46` | Interativo: links, `:focus-visible`, ícones ativos, eyebrow | — |
| `--lime` | `#c9df7b` | **Acento vivo.** Chip/preset ATIVO **só sobre fundo verde escuro** | ❌ Nunca como texto em fundo claro |
| `--clay` | `#b8643a` | Atenção, valor fora do limite, perfil **Arrojado** | Não usar para "sucesso" |
| `--sand` | `#e9e1d0` | Preenchimento neutro | — |
| `--blue` | `#426c75` | Perfil **Conservador** | Não usar como cor de marca |

### 2.3 Semântica de risco ZARC (4 tons)

Usada no **calendário de janelas** e na **legenda**. É a cor mais importante do
produto — comunicar risco climático é o coração do zoneamento.

| Risco | Token | Hex | Onde |
|-------|-------|-----|------|
| 20% (boa janela) | `--risk-low` | `#3f7d4f` | célula sólida, texto claro |
| 30% (médio) | `--risk-mid` | `#6d7a2b` | célula sólida (`--risk-mid-alt` `#8c9c42` no ponto da legenda) |
| 40% (limite) | `--risk-high` | `#d2a445` | célula sólida, **texto escuro** `#3d2804` |
| fora da janela | `--risk-off` | `#ece7db` | **sempre hachurado** (`repeating-linear-gradient` 135°), nunca sólido |

> **Contraste:** `--risk-high` é claro → texto de cima deve ser escuro
> (`#3d2804`). `--risk-low`/`--risk-mid` são escuros → texto claro (`#f5fff7`).

### 2.4 Culturas (cor de preenchimento + tinta legível)

Cada cultura tem um **par** (cor, ink). A `ink` é a cor do texto/gráfico legível
sobre a `cor`. Nunca use a cor da cultura como cor de texto em fundo claro.

| Cultura | `--crop-*` | Hex | Ink | Hex |
|---------|-----------|-----|-----|-----|
| Soja | `soja` | `#d9b64a` | `soja-ink` | `#5b4811` |
| Milho 1ª safra | `milho-1a` | `#e4a13c` | `milho-1a-ink` | `#653b0a` |
| Milho 2ª safra | `milho-2a` | `#c97a2b` | `milho-2a-ink` | `#5a2e05` |
| Feijão | `feijao` | `#b07a4c` | `feijao-ink` | `#4e2d16` |
| Feijão 2ª safra | `feijao-2a` | `#8b5e3c` | `feijao-2a-ink` | `#3b2110` |
| Sorgo granífero | `sorgo` | `#9a6b3f` | `sorgo-ink` | `#3f2814` |
| Sorgo 2ª safra | `sorgo-2a` | `#7f6136` | `sorgo-2a-ink` | `#33240e` |

> **Tela 2 (fronteira Pareto):** use a cor da cultura dominante de cada plano
> como acento do ponto/marcador. **Tela 3:** use `--crop-*` nos dots de cultura
> ao lado de cada hipótese rastreável.

---

## 3. Tipografia

Duas vozes, papéis fixos:

- **Display (serifada)** — `--font-display`: "Iowan Old Style", Palatino, Georgia.
  Números grandes, títulos editoriais, o `h1`. Transmite relatório/oficial.
- **Sans (UI)** — `--font-sans`: Inter, system-ui. Corpo, rótulos, chips, botões.

| Papel | Token | Tamanho | Detalhes |
|-------|-------|---------|----------|
| H1 hero | `--fs-hero` | `clamp(2.7rem, 5.2vw, 4.55rem)` | serif, weight 500, `letter-spacing: -0.045em`, `line-height: 0.97` |
| Número grande | `--fs-stat` | `2.25rem` | serif, weight 500, `font-variant-numeric: lining-nums tabular-nums` |
| Título de bloco | `--fs-title` | `1.45rem` | serif, `letter-spacing: -0.02em`, cor `--green` |
| Corpo | `--fs-body` | `15px` | sans, `line-height: 1.5` |
| Lede (parágrafo hero) | `--fs-lede` | `16px` | sans, `line-height: 1.68`, cor `#4d5a4f` |
| Rótulo (eyebrow/stat) | `--fs-label` | `9.5–10px` | sans, weight 650, `letter-spacing: 0.14em`, **UPPERCASE**, cor `--muted` |
| Chip / botão | `--fs-chip` | `10.5–12px` | sans |

**Regras:**
- Todo número monetário/percentual usa **tabular-nums** (colunas alinhadas).
- Rótulos são sempre `text-transform: uppercase` + `letter-spacing` largo.
- `em` dentro do `h1` fica **itálico + `--green`** (palavra-chave do título).

---

## 4. Forma: raios, sombras, espaçamento

### Raios (nunca "quase retos")

| Uso | Token | Valor |
|-----|-------|-------|
| Chip, tag, badge, nav-item | `--radius-pill` | `999px` |
| Card principal (`.panel`) | `--radius-card` | `23px` |
| Bloco de número (`.stat`) | `--radius-stat` | `18px` |
| Callout, bloco interno | `--radius-md` | `13px` |
| Botão, input, célula | `--radius-sm` | `9px` |
| Marca (brand-mark) | `--radius-mark` | `13px` |

### Sombras (sempre esverdeadas)

```css
--shadow-sm: 0 8px 24px -18px rgba(23, 63, 42, 0.4);   /* cards */
--shadow-md: 0 22px 50px -30px rgba(23, 63, 42, 0.45); /* painéis flutuantes */
```
> Nunca `rgba(0,0,0,…)`. A sombra tem matiz verde para coerência com o papel.

### Espaçamento (grade de 8px, meio-passo 4px)

`--sp-1 4` · `--sp-2 8` · `--sp-3 11` · `--sp-4 16` · `--sp-5 22` · `--sp-6 30` · `--sp-7 48` · `--sp-8 70`

### Layout

- Largura máxima do conteúdo: **`--page-max 1240px`**, centralizada.
- Respiro lateral: **`--page-pad 32px`**.
- Header fixo (`sticky`), altura `74px`, com `backdrop-filter: blur(16px)` e
  fundo `rgba(242,239,231,0.82)` (glass sobre o papel).

---

## 5. Componentes prontos (copiar da Tela 1)

Todos já existem em `web/src/styles.css`. Reaproveite a classe, não reescreva.

| Componente | Classe | Receita resumida |
|------------|--------|------------------|
| **Card** | `.panel` | `padding: 22px; border: 1px solid var(--line); border-radius: var(--radius-card); background: rgba(251,250,246,.94); box-shadow: var(--shadow-sm)` |
| **Número (stat)** | `.stat` | fundo `--surface-2`, raio 18, valor em serif `--fs-stat` com tabular-nums, `.stat-label` em cima |
| **Eyebrow** | `.eyebrow` | rótulo uppercase tracked `--green-2`, com `.eyebrow-rule` (linha 26px) e `.eyebrow-sep` (dot 3px) |
| **Chip / preset** | `.preset-chip` | pill/botão pequeno; **ativo** = fundo `--lime` + texto `#1b2b1c` + borda `--lime` |
| **Barra de cenário** | `.scenario-bar` | fundo verde escuro `linear-gradient(135deg,#173f2a,#1f5137,#24573b)`, texto claro, chips ativos em lime |
| **Callout** | `.rotation-callout` | fundo `#edf3dc`, borda `#dde6c4`, texto `#35502a`, raio 13, ícone `--green-2` |
| **Selo "real"** | `.real-badge` | pill, fundo `#eff5e2`, borda `#d6e2c2`, dot verde `.real-dot` |
| **Nav / breadcrumb** | `.nav-item` | pill; `.active` = fundo branco 72% + borda + peso 650; `.disabled` = `#9a9f95` + selo "em breve" |
| **Status ok/bloqueado** | `.rotation-status` | `.ok` → `--green-2`; `.blocked` → `#b27a58` |

**Acessibilidade (obrigatório):**
- Foco sempre visível: `outline: 2px solid var(--green-2); outline-offset: 2px`.
- Ícones decorativos: `aria-hidden="true"`.
- Calendário/legenda: `role="group"` + `aria-label`.

---

## 6. Fundo (body)

O fundo não é plano — usa dois gradientes radiais suaves sobre `--bg`:

```css
background:
  radial-gradient(1100px 560px at 88% -8%,  #e3ebd2 0%, transparent 62%),
  radial-gradient(900px  520px at -8% 18%,  #f0e5d0 0%, transparent 58%),
  var(--bg);
```
> Reutilize idêntico nas Telas 2 e 3 para continuidade. Não invente novo fundo.

---

## 7. Checklist para as Telas 2 e 3

**Tela 2 — Comparação (ranking margem × risco + fronteira Pareto)**
- [ ] Gráfico da fronteira: eixos com rótulos uppercase tracked; pontos dos perfis
      usando `--green` (Equilibrado), `--clay` (Arrojado), `--blue` (Conservador).
- [ ] Números de margem/risco em **serif + tabular-nums**.
- [ ] Perfil selecionado reusa o padrão `.profile-chip` da `.scenario-bar`.
- [ ] Marcador de cada plano acentuado com a `--crop-*` dominante.

**Tela 3 — Rastreabilidade ("por que soja?")**
- [ ] Cada hipótese com `--crop-*` dot + fonte clicável (link em `--green-2`).
- [ ] Dado real com `.real-badge`; pendência com tom `--clay`.
- [ ] Números de fonte (R$, ‰, %) em tabular-nums.

**Ambas**
- [ ] Zero hex hardcoded — tudo via `var(--token)` de `tokens.css`.
- [ ] Contraste AA nos textos sobre `--risk-high` (usar tinta escura).
- [ ] Header da Tela 1 reaproveitado (só muda o `.nav-item.active`).
- [ ] Responsivo: `--page-max` + `--page-pad`, grids com `minmax(0, …)`.
