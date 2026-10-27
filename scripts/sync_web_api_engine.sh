#!/usr/bin/env bash
# Sincroniza o motor congelado (engine/) para o vendor da API (web/api/engine/).
#
# O motor em engine/ está CONGELADO (o contrato contract/results.json é gerado
# dele). A API serverless em web/api/ usa uma CÓPIA vendorizada porque o deploy
# no Vercel tem Root Directory=web e não enxerga engine/ na raiz do repo.
#
# Uso (na raiz do repo):
#   scripts/sync_web_api_engine.sh           # copia engine/ -> web/api/engine/
#   scripts/sync_web_api_engine.sh --check   # só verifica drift (exit 1 se houver)
#
# Regra: NUNCA edite web/api/engine/*.py à mão — edite engine/ e ressincronize.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO_ROOT/engine"
DST="$REPO_ROOT/web/api/engine"

# módulos vendorizados (imports ortools/yaml/tqdm/stdlib apenas — NUNCA main.py
# nem visualization.py, que puxam matplotlib)
PY_FILES=(model.py solver.py pareto.py robustness.py report.py validation.py)
# dados congelados (janelas ZARC + margens MC do M1 — insumos do config.yaml)
DATA_FILES=(config.yaml janelas_zarc.json margens_mc.json)

HEADER='# COPIADO de engine/ — nao edite aqui; rode scripts/sync_web_api_engine.sh'

mode="${1:-sync}"

if [[ "$mode" == "--check" ]]; then
    drifted=()
    for f in "${PY_FILES[@]}"; do
        if [[ ! -f "$DST/$f" ]] || ! diff -q "$SRC/$f" <(tail -n +2 "$DST/$f") >/dev/null 2>&1; then
            drifted+=("$f")
        fi
    done
    for f in "${DATA_FILES[@]}"; do
        if [[ ! -f "$DST/$f" ]] || ! diff -q "$SRC/$f" "$DST/$f" >/dev/null 2>&1; then
            drifted+=("$f")
        fi
    done
    if (( ${#drifted[@]} > 0 )); then
        echo "ERRO: web/api/engine/ divergiu de engine/: ${drifted[*]}" >&2
        echo "Rode 'scripts/sync_web_api_engine.sh' para ressincronizar o vendor." >&2
        exit 1
    fi
    echo "OK: web/api/engine/ sincronizado com engine/ (${#PY_FILES[@]} .py + ${#DATA_FILES[@]} dados)."
    exit 0
elif [[ "$mode" != "sync" && "$mode" != "--sync" ]]; then
    echo "Uso: $0 [--check]" >&2
    exit 2
fi

mkdir -p "$DST"

for f in "${PY_FILES[@]}"; do
    { echo "$HEADER"; cat "$SRC/$f"; } > "$DST/$f"
done
for f in "${DATA_FILES[@]}"; do
    cp "$SRC/$f" "$DST/$f"
done
# __init__.py vazio — o pacote vendorizado só precisa ser importável; o docstring
# do engine/__init__.py original referencia caminhos que não existem no deploy.
: > "$DST/__init__.py"

echo "Sincronizado: ${#PY_FILES[@]} módulos .py + ${#DATA_FILES[@]} arquivos de dados -> web/api/engine/"
