# API "o que plantar" (FastAPI — Vercel serverless)

Endpoint que recalcula o plano de plantio (CP-SAT + fronteira de Pareto + knee
point + Monte Carlo de robustez) para cenários com talhões editados pelo usuário.

- `GET  /api/health` → `{"status": "ok"}` (ping de warm-up).
- `POST /api/solve`  → `{"talhoes": [{"id": "T1", "area_ha": 300, "grupo_solo": 2, "irrigacao": false}, ...]}`
  devolve o MESMO JSON de `contract/results.json` (cenario, dados, talhoes,
  rotacoes, plano_otimo, fronteira_pareto, knee, planos, robustez), com
  `dados.status = "REAL"`. 422 = entrada inválida; 500 = falha do solver.
  O campo `irrigacao` já é aceito no contrato, mas o motor v0 ainda não o usa
  no solver (fica guardado no `config` para a próxima versão de manejo).
  O filtro de culturas da tela 1 continua apenas visual — ele não altera o solver.

Como o Vercel pegaa: no projeto, Root Directory = `web`; funções Python são
auto-detectadas em `api/*.py` que exportam `app` (aqui: `api/solve.py`), e o
`api/requirements.txt` (fastapi, ortools, pyyaml, tqdm) é instalado no build.

`api/engine/` é uma CÓPIA vendorizada do motor congelado em `engine/` (o deploy
só enxerga `web/`). NUNCA edite `api/engine/*.py` à mão — edite `engine/` e rode:

    scripts/sync_web_api_engine.sh           # ressincroniza o vendor
    scripts/sync_web_api_engine.sh --check   # CI: exit 1 se houver drift

Teste de aceitação (compara com o contrato congelado, sem HTTP):

    python3 web/api/test_acceptance.py

Desenvolvimento local: `cd web/api && python3 -m uvicorn solve:app --port 8000`.
