"""Pacote `engine` — motor de decisão "o que plantar" (HackatOhm 2026, desafio Embrapa).

Motor de decisão: otimização lexicográfica, fronteira Pareto por
ε-constraint + knee point e Monte Carlo de robustez, aplicados à alocação de
rotações agrícolas em talhões, com margens/riscos INTEIROS (CP-SAT):
  margem em centavos de R$/ha · risco em por-mil (‰) · áreas em hectares.
"""
