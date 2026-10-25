#!/usr/bin/env python3
"""
Correlacao preco x produtividade (milho e soja)  -  hipotese de "hedge natural"

Hipotese (v1): clima ruim -> produtividade cai -> preco sobe  => correlacao NEGATIVA.

Escalas testadas: Patos de Minas (municipio), Minas Gerais e Brasil.
O preco de mercado e formado nacional/internacionalmente; por isso a correlacao
local tende a ser fraca e o sinal pode aparecer so nas escalas maiores.

Fontes
  - IBGE/SIDRA, Pesquisa Agricola Municipal:
      produtividade = rendimento medio (kg/ha)
      preco implicito = valor da producao / quantidade produzida (R$/saca de 60 kg)
  - Banco Central (SGS): IPCA (serie 433) para deflacionar; dolar (serie 1) opcional

Etapas (secoes 1 a 6 do guia)
  1. escalas  -> local, estadual, nacional
  2. fonte    -> preco implicito da PAM (CONAB estava com erro de certificado)
  3. preparo  -> deflacionar, tirar tendencia (log - reta), defasagem de 1 ano
  4. analise  -> Pearson e Spearman, IC por bootstrap, teste sem anos extremos,
                 e variacao da receita (preco x produtividade) = efeito hedge
  5. cuidados -> n de anos, p-valores, aviso de testes multiplos
  6. saidas   -> CSVs e grafico em ./saida_preco

Uso:
    pip install requests pandas numpy scipy matplotlib
    python analise_preco_produtividade.py
"""
import datetime as dt
import os
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import urllib3
from scipy import stats

# ----------------------------------------------------------------------------
# CONFIGURACAO
# ----------------------------------------------------------------------------
ESCALAS = {
    "Patos de Minas": ("n6", "3148004"),
    "Minas Gerais": ("n3", "31"),
    "Brasil": ("n1", "all"),
}
TABELAS = [5457, 1612]                       # tentadas em ordem
CULTURAS = {"Milho": "Milho (em grão)", "Soja": "Soja (em grão)"}

VARS = {
    "rendimento": "Rendimento médio",
    "quantidade": "Quantidade produzida",
    "valor": "Valor da produção",
}
UNIDADES = {"quantidade": "toneladas", "valor": "mil reais"}   # trava de seguranca
SACA_KG = 60
ANO_MIN = 1995             # antes do Plano Real os valores estao em outras moedas
N_MIN = 10                 # minimo de anos para calcular correlacao
N_BOOT = 2000              # reamostragens do bootstrap
USAR_DOLAR = True          # tambem testa o preco em dolares (opcional)
PASTA_SAIDA = "saida_preco"

# False = NAO verifica o certificado SSL das APIs (IBGE, Banco Central).
# Use so se o erro for de certificado; volte para True assim que o problema for resolvido.
VERIFICAR_SSL = False

SIDRA = "https://apisidra.ibge.gov.br/values"
META = "https://servicodados.ibge.gov.br/api/v3/agregados/{t}/metadados"
SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{s}/dados"
SGS_IPCA = 433             # IPCA, variacao mensal (%)
SGS_DOLAR = 1              # dolar americano (venda), diario  -> CONFIRME o codigo no site do SGS

# Codigos de reserva, usados SO se o servico de metadados do IBGE estiver inacessivel.
# Sao de memoria (tabela 5457): confirme com  python analise_preco_produtividade.py --diagnostico
RESERVA = {
    "classificacao": "782",
    "categorias": {"Milho": 40122, "Soja": 40124},
    "variaveis": {"rendimento": "112", "quantidade": "214", "valor": "215"},
}


# ----------------------------------------------------------------------------
# UTILIDADES
# ----------------------------------------------------------------------------
def get_json(url, params=None, tentativas=3):
    for i in range(tentativas):
        try:
            r = requests.get(url, params=params, timeout=90, verify=VERIFICAR_SSL)
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if i == tentativas - 1:
                raise
            time.sleep(2 * (i + 1))


# ----------------------------------------------------------------------------
# PAM / SIDRA  (produtividade e preco implicito)
# ----------------------------------------------------------------------------
def achar_classificacao(tabela):
    meta = get_json(META.format(t=tabela))
    for cls in meta.get("classificacoes", []):
        cats = {c["nome"].strip(): c["id"] for c in cls.get("categorias", [])}
        achados = {k: cats[v] for k, v in CULTURAS.items() if v in cats}
        if len(achados) == len(CULTURAS):
            return str(cls["id"]), achados, meta
    raise ValueError(f"Tabela {tabela}: nao encontrei milho/soja nas classificacoes.")


def achar_variaveis(meta, tabela):
    # A tabela tem variaveis parecidas (ex.: "Valor da producao" e "Valor da producao -
    # percentual do total geral"). Prefere o nome EXATO; so recorre ao "comeca com"
    # se nao houver exato, e nesse caso ignora as variaveis em percentual.
    ids = {}
    variaveis = meta.get("variaveis", [])
    for chave, alvo in VARS.items():
        alvo = alvo.lower()
        exatas = [v for v in variaveis if v["nome"].strip().lower() == alvo]
        parecidas = [
            v for v in variaveis
            if v["nome"].strip().lower().startswith(alvo)
            and "%" not in v.get("unidade", "") and "percent" not in v.get("unidade", "").lower()
            and "percent" not in v["nome"].lower()
        ]
        escolhida = (exatas or parecidas or [None])[0]
        if escolhida is not None:
            ids[chave] = str(escolhida["id"])
    faltam = set(VARS) - set(ids)
    if faltam:
        raise ValueError(f"Tabela {tabela}: variaveis nao encontradas: {sorted(faltam)}")
    return ids


def baixar_pam(tabela, nivel, codigo):
    """Devolve (rendimento kg/ha, preco nominal R$/saca), cada um com ano x cultura."""
    try:
        cls, cats, meta = achar_classificacao(tabela)
        var = achar_variaveis(meta, tabela)
    except requests.RequestException as e:
        # metadados fora do ar: usa os codigos de reserva (so faz sentido para a tabela 5457)
        if tabela != 5457:
            raise
        print(f"[AVISO] metadados do IBGE inacessiveis ({type(e).__name__}); usando codigos de reserva.")
        cls, cats, var = RESERVA["classificacao"], RESERVA["categorias"], RESERVA["variaveis"]
    ids_cult = ",".join(str(i) for i in cats.values())
    ids_var = ",".join([var["rendimento"], var["quantidade"], var["valor"]])
    url = f"{SIDRA}/t/{tabela}/{nivel}/{codigo}/v/{ids_var}/p/all/c{cls}/{ids_cult}"
    dados = get_json(url)
    cab, linhas = dados[0], dados[1:]
    if not linhas:
        raise ValueError(f"Tabela {tabela}: resposta vazia.")

    k_ano = next(k for k, v in cab.items() if v == "Ano")
    k_var = next(k for k, v in cab.items() if v == "Variável")
    k_uni = next(k for k, v in cab.items() if v == "Unidade de Medida")
    k_prod = next(k for k, v in cab.items() if v.startswith("Produto") and not v.endswith("(Código)"))
    inverso = {v: k for k, v in CULTURAS.items()}

    def tipo_var(nome):
        n = nome.strip().lower()
        for chave, alvo in VARS.items():
            if n == alvo.lower():                 # nome exato (evita variaveis "percentual")
                return chave
        for chave, alvo in VARS.items():
            if n.startswith(alvo.lower()) and "percent" not in n:
                return chave
        return None

    df = pd.DataFrame(
        {
            "ano": [int(l[k_ano]) for l in linhas],
            "cultura": [inverso.get(l[k_prod].strip(), l[k_prod]) for l in linhas],
            "tipo": [tipo_var(l[k_var]) for l in linhas],
            "unidade": [l[k_uni].strip().lower() for l in linhas],
            # "-", "..", "..." e "X" (sem dado / sigilo) viram NaN
            "V": pd.to_numeric(pd.Series([l["V"] for l in linhas]), errors="coerce"),
        }
    ).dropna(subset=["tipo"])

    # Antes do Plano Real a serie esta em moedas antigas (cruzeiro, cruzado, ...).
    # Descarta esses anos ANTES de conferir as unidades.
    df = df[df["ano"] >= ANO_MIN]

    for tipo, esperada in UNIDADES.items():
        achadas = set(df.loc[df["tipo"] == tipo, "unidade"])
        if achadas != {esperada}:
            raise ValueError(f"Unidade inesperada para '{tipo}': {achadas} (esperado: {esperada})")

    p = df.pivot_table(index=["ano", "cultura"], columns="tipo", values="V")
    p = p[(p["quantidade"] > 0) & (p.index.get_level_values("ano") >= ANO_MIN)]
    # mil R$ -> R$ ; t -> kg ; resultado em R$/saca
    p["preco"] = (p["valor"] * 1000) / (p["quantidade"] * 1000) * SACA_KG
    rend = p["rendimento"].unstack("cultura").dropna(how="all")
    preco = p["preco"].unstack("cultura").dropna(how="all")
    if rend.empty or preco.empty:
        raise ValueError(f"Tabela {tabela}: sem dados numericos para a regiao.")
    return rend, preco


def pam_escala(nome, nivel, codigo):
    erros = []
    for t in TABELAS:
        try:
            r = baixar_pam(t, nivel, codigo)
            print(f"[SIDRA] {nome} (tabela {t}): {r[0].index.min()}-{r[0].index.max()}")
            return r
        except Exception as e:
            erros.append(f"tabela {t}: {e}")
    raise RuntimeError(f"{nome}: " + " | ".join(erros))


# ----------------------------------------------------------------------------
# BANCO CENTRAL (SGS)
# ----------------------------------------------------------------------------
def sgs(serie, ano_ini, hoje=None):
    """Baixa a serie em blocos de 10 anos (o SGS limita o periodo por consulta)."""
    hoje = hoje or dt.date.today()
    partes, a = [], ano_ini
    while a <= hoje.year:
        b = min(a + 9, hoje.year)
        fim = min(dt.date(b, 12, 31), hoje)
        j = get_json(
            SGS.format(s=serie),
            params={"formato": "json", "dataInicial": f"01/01/{a}", "dataFinal": fim.strftime("%d/%m/%Y")},
        )
        partes.extend(j)
        a = b + 1
    d = pd.DataFrame(partes)
    d["data"] = pd.to_datetime(d["data"], dayfirst=True)
    return d.set_index("data")["valor"].astype(float).sort_index()


def deflator_anual(ano_ini):
    """Fator que leva um valor nominal do ano Y para reais do ultimo mes disponivel."""
    ipca = sgs(SGS_IPCA, ano_ini)
    indice = (1 + ipca / 100).cumprod()
    idx_ano = indice.groupby(indice.index.year).mean()
    fator = indice.iloc[-1] / idx_ano
    print(f"[SGS] IPCA ate {indice.index.max():%m/%Y}; reais de {indice.index.max():%m/%Y}")
    return fator


def dolar_anual(ano_ini):
    d = sgs(SGS_DOLAR, ano_ini)
    return d.groupby(d.index.year).mean()


# ----------------------------------------------------------------------------
# PREPARO: anomalias e correlacao
# ----------------------------------------------------------------------------
def anomalia_log(s):
    """Residuo de log(s) contra uma reta no tempo: remove a tendencia e fica em ~%."""
    s = s.dropna()
    t = s.index.values.astype(float)
    y = np.log(s.values)
    return pd.Series(y - np.polyval(np.polyfit(t, y, 1), t), index=s.index)


def corr_basica(x, y):
    r, p = stats.pearsonr(x, y)
    rho, ps = stats.spearmanr(x, y)
    return r, p, rho, ps


def bootstrap_ic(x, y, n=N_BOOT, seed=0):
    rng = np.random.default_rng(seed)
    idx = np.arange(len(x))
    rs = []
    for _ in range(n):
        b = rng.choice(idx, size=len(idx), replace=True)
        if np.std(x[b]) == 0 or np.std(y[b]) == 0:
            continue
        rs.append(np.corrcoef(x[b], y[b])[0, 1])
    return tuple(np.percentile(rs, [2.5, 97.5])) if rs else (np.nan, np.nan)


def correlacionar(x, y, y_ref):
    """x, y: Series alinhadas (mesmo indice). y_ref: anomalia de produtividade, para achar os anos extremos."""
    ok = x.notna() & y.notna()
    x, y, y_ref = x[ok], y[ok], y_ref.reindex(x[ok].index)
    if len(x) < N_MIN:
        return None
    r, p, rho, ps = corr_basica(x.values, y.values)
    lo, hi = bootstrap_ic(x.values, y.values)
    # robustez: refaz sem os 2 anos de maior desvio de produtividade
    extremos = y_ref.abs().nlargest(2).index
    mant = ~x.index.isin(extremos)
    r2 = stats.pearsonr(x[mant].values, y[mant].values)[0] if mant.sum() >= N_MIN else np.nan
    return {
        "n_anos": int(len(x)), "pearson": r, "p_pearson": p, "ic95_inf": lo, "ic95_sup": hi,
        "spearman": rho, "p_spearman": ps, "pearson_sem_2_extremos": r2,
    }


def analisar_escala(nome, rend, preco_real, moeda):
    """Roda as 3 especificacoes de correlacao e o efeito sobre a receita, por cultura."""
    linhas_corr, linhas_hedge = [], []
    for c in rend.columns:
        if c not in preco_real.columns:
            continue
        anos = rend[c].dropna().index.intersection(preco_real[c].dropna().index)
        if len(anos) < N_MIN:
            continue
        y_s, p_s = rend[c].loc[anos], preco_real[c].loc[anos]
        a_y, a_p = anomalia_log(y_s), anomalia_log(p_s)

        specs = {
            "mesmo_ano": (a_p, a_y),
            # preco do ano anterior (o que o produtor via ao decidir o plantio)
            "preco_ano_anterior": (a_p.shift(1), a_y),
            # primeiras diferencas: variacao % do preco x variacao % da produtividade
            "variacao_anual": (np.log(p_s).diff(), np.log(y_s).diff()),
        }
        for spec, (x, y) in specs.items():
            res = correlacionar(x.reindex(a_y.index), y.reindex(a_y.index), a_y)
            if res:
                linhas_corr.append({"escala": nome, "cultura": c, "moeda": moeda, "especificacao": spec, **res})

        # Efeito hedge: log(receita) = log(preco) + log(produtividade)  (receita/ha, preco x kg/ha)
        a_r = a_y + a_p
        var_y, var_r = a_y.var(), a_r.var()
        linhas_hedge.append(
            {
                "escala": nome, "cultura": c, "moeda": moeda, "n_anos": len(anos),
                "desvio_produtividade": a_y.std(), "desvio_preco": a_p.std(), "desvio_receita": a_r.std(),
                "reducao_variancia_receita_pct": 100 * (1 - var_r / var_y),
            }
        )
    return linhas_corr, linhas_hedge


def interpretar(df):
    """Rotulo simples para a hipotese v1 (sinal negativo), olhando a especificacao 'mesmo_ano' em BRL."""
    sub = df[(df.especificacao == "mesmo_ano") & (df.moeda == "BRL real")]
    saida = []
    for _, l in sub.iterrows():
        if l.pearson < 0 and l.p_pearson < 0.05 and l.ic95_sup < 0:
            r = "compativel com hedge natural"
        elif l.pearson < 0:
            r = "sinal negativo, mas sem significancia"
        else:
            r = "sem evidencia de hedge (sinal nao negativo)"
        saida.append(f"  {l.escala:15s} {l.cultura:6s} r={l.pearson:+.2f} (p={l.p_pearson:.3f}, n={l.n_anos}) -> {r}")
    return "\n".join(saida)


# ----------------------------------------------------------------------------
# GRAFICO
# ----------------------------------------------------------------------------
def grafico(series_anom, corr, caminho):
    escalas = list(series_anom.keys())
    culturas = list(CULTURAS)
    fig, eixos = plt.subplots(len(culturas), len(escalas), figsize=(5 * len(escalas), 4.2 * len(culturas)), squeeze=False)
    for j, e in enumerate(escalas):
        for i, c in enumerate(culturas):
            ax = eixos[i][j]
            par = series_anom[e].get(c)
            if par is None:
                ax.set_axis_off()
                continue
            a_p, a_y = par
            ax.scatter(100 * a_p, 100 * a_y, c=a_p.index, cmap="viridis")
            ax.axhline(0, color="k", lw=0.6)
            ax.axvline(0, color="k", lw=0.6)
            sel = corr[(corr.escala == e) & (corr.cultura == c) & (corr.especificacao == "mesmo_ano") & (corr.moeda == "BRL real")]
            if len(sel):
                ax.set_title(f"{e} - {c}  (r = {sel.iloc[0].pearson:+.2f}, n = {sel.iloc[0].n_anos})")
            ax.set_xlabel("Anomalia do preco real (%)")
            ax.set_ylabel("Anomalia da produtividade (%)")
    fig.tight_layout()
    fig.savefig(caminho, dpi=130)
    plt.close(fig)


# ----------------------------------------------------------------------------
# PRINCIPAL
# ----------------------------------------------------------------------------
def main():
    os.makedirs(PASTA_SAIDA, exist_ok=True)
    pam = {}
    for nome, (nivel, codigo) in ESCALAS.items():
        try:
            pam[nome] = pam_escala(nome, nivel, codigo)
        except Exception as e:
            print(f"[AVISO] {nome} ignorada: {e}")
    if not pam:
        raise SystemExit("Nenhuma escala foi baixada com sucesso.")

    ano_ini = min(r[0].index.min() for r in pam.values())
    fator = deflator_anual(ano_ini)
    dolar = None
    if USAR_DOLAR:
        try:
            dolar = dolar_anual(ano_ini)
        except Exception as e:
            print(f"[AVISO] dolar ignorado ({e}). Confira o codigo da serie SGS_DOLAR.")

    todas_corr, todos_hedge, anom_plot = [], [], {}
    for nome, (rend, preco_nom) in pam.items():
        preco_real = preco_nom.mul(fator.reindex(preco_nom.index), axis=0)
        dados = {"BRL real": preco_real}
        if dolar is not None:
            dados["USD nominal"] = preco_nom.div(dolar.reindex(preco_nom.index), axis=0)

        # guarda as series anuais para conferencia
        pd.concat({"rendimento_kg_ha": rend, "preco_nominal_rs_saca": preco_nom, "preco_real_rs_saca": preco_real}, axis=1) \
            .round(2).to_csv(f"{PASTA_SAIDA}/dados_anuais_{nome.replace(' ', '_')}.csv")

        for moeda, pr in dados.items():
            lc, lh = analisar_escala(nome, rend, pr, moeda)
            todas_corr += lc
            todos_hedge += lh

        anom_plot[nome] = {}
        for c in rend.columns:
            if c in preco_real.columns:
                anos = rend[c].dropna().index.intersection(preco_real[c].dropna().index)
                if len(anos) >= N_MIN:
                    anom_plot[nome][c] = (anomalia_log(preco_real[c].loc[anos]), anomalia_log(rend[c].loc[anos]))

    corr = pd.DataFrame(todas_corr)
    hedge = pd.DataFrame(todos_hedge)
    if corr.empty:
        raise SystemExit(f"Poucos anos em comum (minimo {N_MIN}) para calcular correlacao.")
    corr.round(4).to_csv(f"{PASTA_SAIDA}/correlacoes.csv", index=False)
    hedge.round(4).to_csv(f"{PASTA_SAIDA}/hedge_receita.csv", index=False)
    grafico(anom_plot, corr, f"{PASTA_SAIDA}/grafico.png")

    pd.set_option("display.width", 200)
    print("\n=== Correlacao preco x produtividade (anomalias; esperado: NEGATIVA) ===")
    print(corr[["escala", "cultura", "moeda", "especificacao", "n_anos", "pearson", "p_pearson",
                "ic95_inf", "ic95_sup", "spearman", "pearson_sem_2_extremos"]].round(3).to_string(index=False))
    print("\n=== Efeito sobre a receita (reducao de variancia > 0 = hedge natural) ===")
    print(hedge.round(3).to_string(index=False))
    print("\n=== Leitura da hipotese v1 (preco real em BRL, mesmo ano) ===")
    print(interpretar(corr))
    print(
        f"\nAtencao: foram feitos {len(corr)} testes; alguns saem 'significativos' so por acaso. "
        "Valorize padroes consistentes entre escalas e especificacoes.\n"
        f"Arquivos em ./{PASTA_SAIDA}/"
    )


def diagnostico():
    """python analise_preco_produtividade.py --diagnostico
    Testa cada etapa isoladamente e mostra o erro real (e o formato da resposta)."""
    nivel, codigo = ESCALAS["Patos de Minas"]
    t = TABELAS[0]
    print(f"1) Metadados da tabela {t} (servicodados.ibge.gov.br)")
    try:
        meta = get_json(META.format(t=t), tentativas=1)
        print("   OK. variaveis:", [(v["id"], v["nome"]) for v in meta.get("variaveis", [])])
        for cls in meta.get("classificacoes", []):
            print(f"   classificacao {cls['id']} '{cls['nome']}': {len(cls.get('categorias', []))} categorias")
    except Exception as e:
        print("   FALHOU:", repr(e))

    print("\n2) Dados do SIDRA (apisidra.ibge.gov.br), Patos de Minas")
    url = f"{SIDRA}/t/{t}/{nivel}/{codigo}/v/112,214,215/p/all/c782/40122,40124"
    print("   URL:", url)
    try:
        d = get_json(url, tentativas=1)
        print("   linhas de dados:", len(d) - 1)
        print("   cabecalho:", d[0])
        print("   amostra:", d[1:4])
    except Exception as e:
        print("   FALHOU:", repr(e))

    print("\n3) Banco Central (api.bcb.gov.br), IPCA")
    try:
        j = get_json(SGS.format(s=SGS_IPCA), params={"formato": "json", "dataInicial": "01/01/2024", "dataFinal": "31/12/2024"}, tentativas=1)
        print("   OK. exemplo:", j[:2])
    except Exception as e:
        print("   FALHOU:", repr(e))
    print("\nMande a saida acima se algum passo falhar.")


if __name__ == "__main__":
    import sys

    if not VERIFICAR_SSL:
        # evita um aviso por requisicao; o aviso unico abaixo basta
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        print("[ATENCAO] VERIFICAR_SSL = False: o certificado SSL das APIs NAO esta sendo verificado.\n")
    if "--diagnostico" in sys.argv:
        diagnostico()
    else:
        main()