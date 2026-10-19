# WORKFLOW — codebase-specialists

<!-- features:inicio (gerado por .claude/tools/feature.py; não edite à mão) -->
**Estado:** IDLE
**Features ativas:** nenhuma
**Última entrega:** iter26 (2026-10-19T15:24:10-0300) — .claude/state/archive/iter26/iter26.md
<!-- features:fim -->

Feature = campanha no motor embutido, em `campanhas/<feature>/` (oráculo versionado; `.auto-correcao/` local).
O estado mecânico é do `feature.py status` e do `ac.py status`; aqui fica o porquê e a ordem.
Atualizado em 2026-10-13.

## Sequência de features

- [x] iter18 — 0.10.0 · `5e8f6b2` · iter20 — 0.10.1 · `97a1718` · iter19 — 0.11.0 · `c2b74ae` · iter21 — 0.12.0 ·
  `7fdb431` · iter22 — 0.12.1 · `da30e17`
- [x] iter24 — 0.12.2: hotfix de segurança do guard (B-44..B-47 parcial) · `b757d1f` · instalado nesta máquina
- [x] iter23 — 0.13.0: fluxo da árvore sem beco sem saída (D1–D6 da cobaia .NET) · `933012d` (+ `1d3d78d` oráculo iter10)
- [ ] 1. B-50 (P0, perda de dados) + B-48/B-49 — próxima feature (decisão da E1 da iter23, D-32)
  porquê agora: perda de dados no alvo é o defeito mais grave restante.
- [ ] 2. B-61 — oráculos antigos iter10/iter15 de volta ao portão; B-54 (segurança residual).
- [ ] 3. harness: B-17 (P1, campanha.py fechar grava execução sem nota), B-15, B-16, B-18.

## Últimas entregas

| commit | data | o quê |
|---|---|---|
| `933012d` | 2026-10-14 20:02 | 0.13.0: fluxo da árvore sem beco sem saída (iter23); `1d3d78d` oráculo iter10 |
| `b757d1f` | 2026-10-13 19:03 | 0.12.2: guard sem portas laterais (iter24) |
| `da30e17` | 2026-10-12 16:58 | 0.12.1: cs-state show liberado no guard e varredura subcomandos x guard (iter22) |
| `7fdb431` | 2026-10-12 14:28 | 0.12.0: memória dos agentes que não esquece (iter21) |
| `c2b74ae` | 2026-10-11 21:04 | 0.11.0: estado legível em JSON, chaves em inglês, cs-state show (iter19) |
| `97a1718` | 2026-10-07 10:57 | 0.10.1: pre-commit aceita o resultado do próprio upgrade (B-13, iter20) |
| `b2498c5` | 2026-10-06 22:51 | harness: frente vira feature (criar-feature, fechar-feature, feature.py) |
| `5e8f6b2` | 2026-10-06 22:02 | 0.10.0: correções de uso real na segunda cobaia .NET (iter18) |
| `2ad9e03` | 2026-10-06 21:25 | harness: harness de desenvolvimento completo (harness-dev) |
| `4dd7cf2` | 2026-10-06 | harness: /install instala o pacote dist validado (iter17) |

Tabela completa por campanha: `campanhas/README.md`.
