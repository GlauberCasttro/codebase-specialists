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
- [x] iter25 — 0.13.1: status canônico no arquivo do item (B-64) · `633a307` (+ `bac0e0f` oráculo iter23)
- [x] iter26 — 0.14.0: modelo de itens canônico, telemetria por tentativa, tokens no guard, B-49, B-67 · `8401adc`
  (+ oráculos `244006a`, `d12e026`, `58ebdc9`, `e920288`)
- [ ] 1. iter27 — CLI e motor inteiros em inglês (B-72 + B-68 + B-71)
  porquê agora: o uso real mostrou o inglês pela metade; a task melhor precisa de vocabulário fechado.
- [ ] 2. iter28 — task melhor (brief com contexto/DoD, matriz de casos, vermelho por caso, checks do revisor por script)
- [ ] 3. iter29 — métricas (`cs-state metrics`); depois B-61, B-50, B-48, B-70.

## Últimas entregas

| commit | data | o quê |
|---|---|---|
| `8401adc` | 2026-10-19 | 0.14.0: modelo de itens canônico (iter26); oráculos iter10/13/19/23 em commits à parte |
| `633a307` | 2026-10-17 | 0.13.1: status canônico no arquivo do item (iter25); `bac0e0f` oráculo iter23 |
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
