# WORKFLOW — codebase-specialists

<!-- features:inicio (gerado por .claude/tools/feature.py; não edite à mão) -->
**Estado:** IN_PROGRESS
**Features ativas:** iter19 (criar-feature)
**Última entrega:** iter20 (?) — 
<!-- features:fim -->

Feature = campanha no motor embutido, em `campanhas/<feature>/` (oráculo versionado; `.auto-correcao/` local).
O estado mecânico é do `feature.py status` e do `ac.py status`; aqui fica o porquê e a ordem.
Atualizado em 2026-10-07.

## Sequência de features

- [x] iter18 — 0.10.0: correções de uso real na segunda cobaia .NET (R1–R7) · `5e8f6b2`
- [x] iter20 — 0.10.1: pre-commit aceita o resultado do próprio upgrade (B-13) · `97a1718`; validado em uso real
- [ ] 1. iter19 — 0.11.0: estado em JSON, ordem de leitura, chaves em inglês, amend no arquivo, `cs-state show`,
  migração no upgrade (B-14)
  porquê agora: arquivo de estado ilegível e desatualizado no alvo real; oráculo congelado, aguardando aprovação.
- [ ] 2. B-19 — descarte de task da árvore nunca iniciada (P1, uso real)
  porquê depois: independente da iter19; o alvo contorna ignorando o item.
- [ ] 3. harness: B-15 (saída de legado), B-16 (portão lê o próprio script), B-17 (campanha.py fechar), B-18 (init
  sobrescreve) — defeitos do harness vistos nesta rodada.

## Últimas entregas

| commit | data | o quê |
|---|---|---|
| `97a1718` | 2026-10-07 10:57 | 0.10.1: pre-commit aceita o resultado do próprio upgrade (B-13, iter20) |
| `b2498c5` | 2026-10-06 22:51 | harness: frente vira feature (criar-feature, fechar-feature, feature.py) |
| `5e8f6b2` | 2026-10-06 22:02 | 0.10.0: correções de uso real na segunda cobaia .NET (iter18) |
| `2ad9e03` | 2026-10-06 21:25 | harness: harness de desenvolvimento completo (harness-dev) |
| `4dd7cf2` | 2026-10-06 | harness: /install instala o pacote dist validado (iter17) |

Tabela completa por campanha: `campanhas/README.md`.
