# engine/ — motor de decisão "o que plantar" (HackatOhm 2026, desafio Embrapa)

- **Rodar** (na raiz do repo): `python3 engine/main.py --pareto --monte-carlo` — saída em `engine/out/`:
  `relatorio_engine.txt` (relatório PT-BR), `results_mock.json` (contrato com o M3) e `pareto_frontier.png` (fronteira com knee e perfis).
- **Tudo é MOCK**: margens (centavos/ha), riscos (‰) e janelas (decêndios 1–36) no `config.yaml` são provisórios (`fonte_url: "MOCK://…"`).
- **Números reais**: quando o MC do M1 sair, substitua `margem_esperada`/`risco` (e as `janelas_viveis` vindas do ZARC/`adequacao.py`) em `engine/config.yaml` e rode de novo — o motor não muda.
- **Modelo** (CP-SAT só inteiros): `x[(rotação, talhão)]` = ha; por talhão Σx = área; rotação sem janela viável no grupo de solo fica com upper bound 0.
- **Método**: lexicográfico (1º máx margem, 2º mín risco) → fronteira ε-constraint (pisos de 100% a 85% do ótimo) → knee point = perfil **Equilibrado** (extremos = **Arrojado**/máx margem e **Conservador**/mín risco) → Monte Carlo ±10% nas margens mede a estabilidade da recomendação.
- Opções: `--help` (`--pareto-points`, `--min-margem-ratio`, `--mc-runs`, `--mc-jitter`, `--mc-seed`, `--quiet`).
