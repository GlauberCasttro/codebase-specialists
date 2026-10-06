# 07 — Evals e qualidade

Como a skill é medida, e o que as medições disseram até agora. Fontes: `evals/README.md`, `evals/evals.json`,
`evals/check_run.py`, `evals/summarize.py`, `evals/fixtures/`, e os resultados em
`campanhas/` (`iteration-1` … `iteration-4`, `PROXIMA-RODADA.md`).

## 1. O oráculo

```text
 evals/fixtures/<f>/repo/ ──build.sh──▶ alvo git com histórico realista ──▶ execução (com skill | sem skill)
                                                                                 │
 evals/fixtures/<f>/GROUND_TRUTH.json  (NUNCA chega ao alvo) ─────────────┐      │
                                                                          ▼      ▼
                                                            check_run.py <alvo> <GROUND_TRUTH> --mode setup
                                                                          │
                                                                          ▼
                                       grading.json  (expectations [Q] qualidade + [S] estrutura)
                                                                          │
                                                       summarize.py <iteração>/runs  →  benchmark-q.md/.json
```

### Fixtures (repositórios com gabarito oculto)

Só `repo/` é copiado para o alvo; `GROUND_TRUTH.json`, `history.plan`, `history/` e o oráculo oculto do bug
nunca chegam lá. `build.sh <nome> <destino>` reconstrói o histórico commit a commit e **aborta** se o histórico
não terminar exatamente em `repo/`.

| Fixture | Stack | Sinais plantados (resumo de `evals/README.md`) |
|---|---|---|
| `py-billing` | Python ≥3.9, uv.lock, unittest, ruff, Makefile | 3 subdomínios + shared; ADRs (centavos inteiros, ledger append-only, captura idempotente); 21 commits, 5 `fix:`, revert de `delete` no ledger, co-change payments↔ledger, bump httpx 0.26→0.27; **bug plantado** em `late_fees.py`; README desatualizado; CLAUDE.md humano; `tests/fixtures/` com .csproj e package.json falsos |
| `ts-shop` | npm workspaces, node:test, eslint 9, TS 5.5.4 | shared/api/web; ADRs (web só por HTTP; estoque nunca negativo, reserva 15 min); fix do enum; revert do import web→api; ranges × versões exatas do lock; README cita `npm run e2e` inexistente; AGENTS.md humano; fixture legacy-erp com Django/Spring |
| `go-polyglot` | Go 1.22.5, bash de deploy, Dockerfile, migrações SQL | enum espelhado em Go; co-change migrations↔storage; revert de edição de migração aplicada; README diz Go 1.21; `testdata/` e `examples/python-client`; `go` ausente na máquina ⇒ teste tem de ser `declared` |
| `py-billing-features` | — | `refund-percent`, `accept-float-amounts`, `bug-late-fee` (oráculo oculto) para os evals de modo autônomo, escalada e bugfix |

`GROUND_TRUTH.json` (py-billing) tem: `product_dirs`, `fixture_paths`, `bounded_contexts`, `commands`,
`invariants`, `terms`, `business_rules`, `hotspots`, `co_change`, `coupled_pair`, `fix_commits_min`, `revert`,
`adrs`, `stack`, `stack_must_not_include`, `absent_patterns`, `stale_doc_claim`, `human_content`, `planted_bug`,
`features`… `python3 evals/check_run.py --verify-ground-truth all` confere que todo `arquivo:linha` do gabarito
ainda casa o texto esperado.

### Evals (`evals/evals.json`, 12 prompts)

| id | nome | tipo |
|---|---|---|
| 1, 2, 3 | py-billing-setup-1/2/3 | montar o time (vago PT, detalhado PT, EN) |
| 4 | py-billing-autonomous-refund-percent | modo autônomo |
| 5 | py-billing-autonomous-escalation | escalada (feature exige tocar invariante) |
| 6 | py-billing-bugfix-late-fee | correção de bug com oráculo oculto |
| 7, 8, 9 | ts-shop-setup-7/8/9 | montar o time |
| 10, 11, 12 | go-polyglot-setup-10/11/12 | montar o time |

As rodadas registradas no workspace usaram os evals **1, 7 e 10** (prompts vagos: "monta o time de agentes pra
esse repo", "create a team of expert agents for this monorepo", "monta o time de agentes especialistas para
este repo"). Os evals 4–6 (autônomo, escalada, bugfix) **não aparecem** nos resultados do workspace.

### `check_run.py` — duas famílias de asserção

- **[Q] qualidade — neutra de formato.** Lida dos artefatos de **qualquer** plataforma (`.claude/agents`,
  `.cursor/…`, `.github/…`, `AGENTS.md`/`CLAUDE.md` raiz e aninhados) e, se existir, de `.swarm/`. Em
  arquivo que já existia na fixture conta só o texto **adicionado**. É a família que se compara com a baseline.
  Asserções: TERR, BC, INV, TERM, RULE, STACK, FIX, NEG, HIST, HUMAN, TESTCMD, STALE (13 no modo setup).
- **[S] estrutura — artefatos da skill.** G1–G16 e FMT (`team.json5`, fatos, sondas, harness, cenários
  `evals/harness_scenarios.json`). Reportada à parte; **não** compare com a baseline por ela (a baseline não tem
  esses artefatos).

Princípios do corretor: usa o código da **skill** (json5io, CLI), nunca scripts do alvo para decidir;
recalcula o que pode (testes, hashes, git diff); cenários que escrevem estado rodam numa **cópia** do alvo; um
comando marcado `verified` é **reexecutado** pelo corretor. Sobre a fixture recém-construída, sem skill, o
corretor dá **0/13 [Q] e 0/15 [S]** (py-billing, `--no-scenarios`, conferido em 2026-10-02) — as asserções de
"não estragar" só contam quando a skill rodou.

### Como rodar

```text
SK=~/.claude/skills/codebase-specialists
T=$(mktemp -d)/py-billing
bash $SK/evals/fixtures/build.sh py-billing "$T"           # 1. alvo com histórico
#    2. rode o prompt do eval NO alvo — com a skill (with_skill) ou sem (without_skill)
python3 $SK/evals/check_run.py "$T" $SK/evals/fixtures/py-billing/GROUND_TRUTH.json --mode setup --out grading.json
python3 $SK/evals/summarize.py <iteração>/runs             # [Q] e [S] separados por config
```

- Plataformas restritas (evals 2 e 8): `--platforms claude-code,cursor` (G7 reprova plataforma emitida sem pedido).
- Autônomo/escalada/bug (evals 4–6): depois do eval 1 no mesmo alvo,
  `bash $SK/evals/fixtures/install_feature.sh refund-percent|accept-float-amounts|bug-late-fee "$T"` e
  `--mode autonomous --feature refund-percent`, `--mode escalation --feature accept-float-amounts` ou
  `--mode bugfix`.
- `--only G1,G3,BC` restringe; `--no-scenarios` pula os cenários; `--skill DIR` aponta outra versão da skill.
- `summarize.py` espera `runs/eval-N/<config>/run-K/{grading.json,timing.json}` e grava `benchmark-q.md` e
  `benchmark-q.json` com [Q] e [S] por config (média ± desvio), tempo e tokens.
- Testes do próprio corretor: `python3 -m unittest discover -s evals/tests`.

## 2. Resultados das 4 iterações

Evals de setup com prompt vago. [Q] = qualidade (13 asserções); [S] = estrutura. Tokens = orquestrador apenas
(**subagentes não contabilizados**, como dizem as notas de `timing.json`). Aprovações sempre simuladas
(`eval-sim`).

### Baseline (sem a skill)

| Fixture | [Q] | tempo | tokens | Falhas [Q] (iteração 2, `benchmark-q.md`) |
|---|---|---|---|---|
| py-billing | 9/13 | 408 s | 90.334 | TERR (cobertura), TERM, STACK, HIST |
| ts-shop | 10/13 | 395 s | 86.730 | TERR, STACK, HIST |
| go-polyglot | 10/13 | 473 s | 93.044 | TERR, INV, HIST |

### Com a skill

| Iteração | Fixture | Modo | [Q] (corretor) | [S] | Decisão | Tempo | Tokens orq. | Observação |
|---|---|---|---|---|---|---|---|---|
| 1 | py-billing | completo | 12/13 | 17/42 | NO-GO | 705 s | 199.220 | parou em specialize.4 |
| 1 | ts-shop | completo | 13/13 | 15/36 | NO-GO | 1.260 s | 282.359 | parou em rt.1 |
| 1 | go-polyglot | completo | 13/13 | 29/37 | NO-GO | 1.862 s | 417.387 | parou em validate.3 |
| 2 | py-billing | completo | 13/13 | 34/43 | GO | 1.860 s | 329.335 | — |
| 2 | ts-shop | completo | 13/13 | 27/37 | NO-GO | 3.459 s | 346.647 | — |
| 2 | go-polyglot | completo | 13/13 | 27/37 | GO | 3.496 s | 397.527 | — |
| 3 | py-billing | `--full` | 13/13 | 34/43 | NO-GO | — | 325.959 | "1 ref inválida em 504"; 10/10 agentes provados |
| 3 | py-billing | `--fast` | 13/13 | 33/43 | NO-GO | 1.402 s (~21 min) | 230.405 | G2 (checks sem `[unverified]`); G4: 5 reprovados por sondas de sha sem `.git`; 4/9 provados; 33 subagentes |
| 3 | ts-shop | `--full` | 13/13 | 27/37 | NO-GO | 2.794 s | 380.011 | 6/9 provados (2 por nota None) |
| 3 | go-polyglot | `--full` | 11/13 (13/13 real) | 27/37 | GO "inconsistente" | — | 392.386 | 2 falsos positivos de negação; ops `nao-especialista` aceito e mesmo assim GO — motivou a regra de GO |
| 4 | ts-shop | `--fast` | 12/13 (13/13 real) | 29/37 | GO (simulado) | 1.975 s (~33 min) | 269.008 | 10/10 especialistas; 79 subagentes; **5 contornos manuais**; STALE falso positivo |
| 4 | py-billing | `--fast` | — | — | pausada | — | — | parou em validate.3 |
| 4 | go-polyglot | `--fast` | — | — | pausada | — | — | parou em validate.2 |

Agregado da iteração 2 (`iteration-2/benchmark-q.md`, 3 runs por config):

| Métrica | with_skill | without_skill | Delta |
|---|---|---|---|
| [Q] pass rate | 100% ± 0% | 74% ± 4% | +0,26 |
| [S] pass rate | 75% ± 4% | 3% ± 0% | +0,72 |
| Tempo | 2.938 s ± 934 s | 425 s ± 42 s | +2.513 s |
| Tokens (orquestrador) | 357.836 ± 35.446 | 90.036 ± 3.168 | +267.800 |

### Leitura

- **Qualidade**: com a skill, [Q] 13/13 (real) em todas as execuções que chegaram ao fim, contra 9–10/13 da
  baseline. As falhas típicas da baseline são cobertura de território, histórico real (hotspots, co-change,
  commits de correção), versões exatas do lockfile e invariantes de ADR entregues a todos os donos.
- **Modo**: na py-billing (iteração 3), `--fast` e `--full` deram o mesmo [Q] 13/13; mesa redonda e refino mudam
  a certificação (G2/G4), não a qualidade (`iteration-3/RESULTADOS.json5 → leitura`; premissa PR-26). Daí o
  `--fast` como padrão.
- **Decisão**: até a iteração 3 as decisões foram dominadas por defeitos da própria skill. Na iteração 4 só a
  ts-shop concluiu (GO simulado) e precisou de 5 contornos manuais; o critério de parada da campanha
  ("≥2/3 GO; zero contornos manuais; [Q] ≥ baseline nos 3; testes verdes") **não foi cumprido**
  (`iteration-4/RESULTADOS-E-DEFEITOS.json5`).
- **Custo**: ~3–4× o tempo e o número de tokens da baseline só no orquestrador, mais dezenas de subagentes.

## 3. Limites conhecidos do corretor

De `evals/README.md` e das rodadas:

- **Negação**: o corretor erra em frases como "X não existe" lidas como afirmação. Casos medidos: go-polyglot
  iteração 3 (2 falsos positivos) e ts-shop iteração 4 (STALE: "playwright" citado para dizer que **não**
  existe) — defeito P2 aberto. `PROXIMA-RODADA.md` manda conferir à mão ≥2 asserções por configuração antes de
  confiar.
- `NEG_RE` casa `no` como palavra inteira: em português "no" (em + o) faz linhas como "TypeScript no front"
  serem descartadas por NEG/FIX/STALE (leniente). Conhecido; não corrigido para não mudar notas publicadas.
- INV casa palavra-chave: paráfrase correta sem o termo reprova.
- O cosseno do G3 é léxico; o limiar 0,35 foi calibrado com os cartões genéricos de referência
  (`evals/reference/generic-cards/`) e deve ser recalibrado com repositório de controle.
- Latência do G8 usa o `ms` informado pelo `cs-mem`, sem o tempo de subir o processo.
- Os cenários G8–G16 dependem dos nomes de subcomando do harness; quando a CLI diverge, a evidência mostra o
  comando e a saída — ajusta-se `harness_scenarios.json`, não o corretor. `G16.fresh-subagent-disk-only` só passa
  num alvo em que a execução chegou a `validate` fechado.
- `cs-state`, `cs-route` e `cs-mem stats` não têm saída JSON: os cenários casam texto.
- G14 não cobre "gate ≥ tier do autor" por cenário (o `cs-route recommend` não expõe o tier do autor).
- Mudança no corretor numa campanha só com justificativa e evidência (`PROXIMA-RODADA.md`: `ac.py oracle change
  --why --evidence`, da skill `auto-correcao`).
