# Etapa 2 — scan

**Objetivo:** fatos com evidência para todas as camadas L0–L10 + lacunas respondidas.

**Por que existe:** nenhum cartão pode afirmar algo que um fato não sustente (princípio 1 do SKILL.md). O scan é
o único produtor de conhecimento "mecânico"; o modelo só confere (spot-check) e completa o que o código não
diz (entrevista). Na iteração 1, 7 a 9 de cada 10 fatos conferidos estavam errados (`iteration-1/DEFEITOS.json5`,
"causa raiz nº 1") — por isso o spot-check é obrigatório.

```text
            ┌──────────────── cs.py scan  (uma vez; todas as camadas) ────────────────┐
            │ L0 L1 L2 L3 │ L4 L5 L6 │ L7 L8 │ L9 L10                                │
            └──────┬──────┴────┬─────┴───┬───┴────┬──────────────────────────────────┘
                   ▼           ▼         ▼        ▼
 checks:      scan.1        scan.2    scan.3   scan.4      (cs.py facts check --layers …)
                                                  │
                                                  ▼
                          scan.5 (sub) spot-check 5–10 fatos ── wrong → facts interpret --corrects
                                                  │                        + spotcheck record --verdict wrong
                                                  ▼
                          scan.6 (user) entrevista de lacunas, lotes ≤8
                              resposta → interview record --answer "…"
                              "não sei" → interview record --answer-unknown → fato gap.<slug>
                                                  │
                                    cs.py stage done scan → stages/scan.handoff.json5
```

## Sub-etapas

### scan.1–scan.4 — rodar o scan e conferir as camadas

| | |
|---|---|
| Quem | main |
| Comando | `cs.py scan` (uma vez cobre todas as camadas; `--layers L0,L1,L5` restringe) |
| Checks | scan.1 `cs.py facts check --layers L0,L1,L2,L3` · scan.2 `--layers L4,L5,L6` · scan.3 `--layers L7,L8` · scan.4 `--layers L9,L10` |
| Lê | `git ls-files`, `git log`, manifestos, lockfiles, configs, docs, e **executa** comandos declarados (L7) |
| Grava | `.swarm/facts/<camada>.json5` + `index.json5`; blobs de evidência de comandos em `.swarm/evidence/` |

`facts check` exige que as camadas estejam **presentes, válidas e frescas** (o código não mudou desde o scan).
Opções úteis de `cs.py scan`: `--no-exec` (não executa comandos do alvo; L7 fica `declared`, L8 sem
introspecção), `--no-introspect`, `--timeout` (por comando), `--max-commits` (L5/L6), `--max-deps` (L8),
`--max-exec` (L7), `--check` (não escaneia; confere que as camadas pedidas já existem e estão indexadas).

O scan computa tudo antes de escrever: se uma camada falha, nada é gravado (exceto os blobs de evidência, que
são endereçados por conteúdo). Status de comando em L7: `verified` (exit 0), `declared`, `unavailable`
(ferramenta ausente no ambiente — exit 127; **não culpa o repositório**), `failed`.

Saída real (py-billing, iteração 4):

```text
$ cs scan
L0  inventory         17 fatos → .swarm/facts/inventory.json5 (41 arquivos; ignorados: fixture=3)
L1  graph             31 fatos → .swarm/facts/graph.json5
L2  architecture       3 fatos → .swarm/facts/architecture.json5
L3  conventions       10 fatos → .swarm/facts/conventions.json5
L4  rules             14 fatos → .swarm/facts/rules.json5
L5  history           36 fatos → .swarm/facts/history.json5
L6  rationale          3 fatos → .swarm/facts/rationale.json5
L7  operations         5 fatos → .swarm/facts/operations.json5 (declared=2, failed=0, unavailable=1, verified=2)
L8  stack              5 fatos → .swarm/facts/stack.json5
L8  stack_graph        2 fatos → .swarm/facts/stack_graph.json5
L9  business_rules    40 fatos → .swarm/facts/business_rules.json5
L9  glossary          23 fatos → .swarm/facts/glossary.json5
L10 project_docs      12 fatos → .swarm/facts/project_docs.json5
index: 201 fatos → .swarm/facts/index.json5
```

### scan.5 — spot-check (conferir 5–10 fatos contra o código)

| | |
|---|---|
| Quem | sub — 1 subagente por lote de 5–10 fatos, só leitura; lotes ≤3 de uma vez |
| Entrada | `{tmp}/in/spotcheck.{lote}.json5` = `{fatos: [...], mecanicos: [ids]}`, gravado pelo orquestrador (prioriza `rules`, `business_rules`, `operations`, `glossary` e `history.fixes`) |
| Saída do subagente | `{tmp}/spotcheck/{lote}.json5` com `resultados[{fact_id, verdict: ok\|wrong, evidencia, nota, correcao}]` e `injection_attempts` |
| Registro (main, em série) | `ok`: `cs.py facts spotcheck record --fact <id> --verdict ok --note "…" --by spotcheck-<lote>`; `wrong`: **primeiro** `cs.py facts interpret --id <novo> --claim "…" --supports <ids> --evidence <arq:linha> --corrects <id>`, **depois** `cs.py facts spotcheck record --fact <id> --verdict wrong --note "…"` |
| Check | `cs.py facts spotcheck --min 5` |
| Grava | `.swarm/spotcheck.jsonl`; correções como fatos `llm_interpretation` |

O prompt completo é `references/prompts.json5 → prompts["scan.5"]`. O subagente marca `wrong` quando o trecho
sustenta só parte do fato, a linha mudou, o arquivo é fixture/vendor/gerado, a contagem não bate, ou o comando
falhou por ferramenta ausente e o fato culpa o repositório. `wrong` sem apoio mecânico fica sem correção e é
explicado na nota — o orquestrador não grava `wrong` sem correção.

Registro real (py-billing, iteração 4):

```text
$ cs facts spotcheck record --fact ops.lint.make-lint --verdict ok --note Makefile:9 declara o alvo lint, que roda ruff (linhas 10-11); `which ruff` retornou 'ruff not found', e o fato atribui a ausência ao ambiente, não ao repositório. --by spotcheck-A
$ cs facts spotcheck record --fact docs.stale.readme.md.14 --verdict ok --note README.md:14 cita httpx 0.26.0, mas uv.lock:69 fixa 0.27.0 (pyproject.toml:8 também está em 0.27.0). --by spotcheck-B
```

Desconfie (SKILL.md): comando `failed` por ferramenta ausente (exit 127 é ambiente), status de ADR em
português, "sem teste" para regra testada. Fixture, vendor e gerado nunca são produto.

### scan.6 — entrevista de lacunas (toque humano)

| | |
|---|---|
| Quem | user |
| Comandos | `cs.py interview ask --id <q> --question "…" [--context "…"] [--scope "<glob>"]` · `cs.py interview record --id <q> --answer "<literal>"` ou `--answer-unknown` · `cs.py interview status` |
| Check | `cs.py interview status --no-pending` (falha se há pergunta sem resposta) |
| Grava | `.swarm/interview.jsonl` (append-only), `facts/interview.json5`, `facts/gaps.json5` |

Só se pergunta o que o scan não alcança: o porquê, exceções, o que nunca pode quebrar, áreas congeladas, quem
decide. **Lotes de até 8** perguntas pendentes; respostas **literais**. Sem resposta: `--answer-unknown` vira o
fato `gap.<slug>` (lacuna citável, nunca conhecimento — ver [../01-conceitos.md](../01-conceitos.md)).

`--scope` recebe **um glob por flag** (repita a flag); vírgula é recusada, porque `"a/**,b/**"` não casaria
nada e a lacuna não chegaria ao dono (`references/team-schema.md`, "Entrevista: escopo"). `cs.py interview
sync` regrava `facts/interview.json5` e `facts/gaps.json5` a partir do log.

Perguntas reais (py-billing, iteração 4; todas respondidas `--answer-unknown --by eval-sim` por falta de
usuário):

```text
$ cs interview ask --id late-fee-basis --question Qual a base (contrato/lei) e quem decide mudanças na multa de 2% + juros de 1% ao mês pro rata die (mês de 30 dias)? --scope src/billing/invoices/** --context src/billing/invoices/late_fees.py
$ cs interview ask --id freeze-scope --question O congelamento de deploy entre dia 28 e dia 2 vale só para payments ou também para ledger e invoices? --scope src/billing/** --context CLAUDE.md:4
$ cs interview record --id late-fee-basis --answer-unknown --by eval-sim
```

### Fechamento

```text
cs.py stage done scan
```

O handoff traz os números por camada. Exemplo real (ts-shop, iteração 4, `stages/scan.handoff.json5`):
`facts.business_rules: 16`, `facts.gaps: 6`, `facts.history: 32`, `facts.operations: 14`, … e a nota
`[sem usuário] 6 lacunas registradas com --answer-unknown (gap.*)`.

## Erros comuns e como resolver

| Sintoma | Origem | Resolução |
|---|---|---|
| Não há comando que monte `{tmp}/in/spotcheck.{lote}.json5` | defeito aberto (iteração 4, P1: "sem comando que monta os pacotes de entrada de spot-check…") | o orquestrador monta o arquivo lendo `.swarm/facts/*.json5` (na iteração 4 o executor usou um script curto); **o registro continua só pela CLI** |
| `make test`/`make lint` ficaram `unavailable` | ferramenta (`go`, `ruff`, `golangci-lint`) ausente na máquina | não é defeito do repo; o G5 aceita como declaração explícita; instale a ferramenta e rode `cs.py scan` de novo se quiser `verified` |
| fato de regra "não prova" uma regra que é testada | heurística de cobertura (iterações 1–3) | spot-check marca `wrong` e corrige com `facts interpret`; premissa PR-29: o scan deve dizer "não determinável", nunca "não prova" por palpite |
| `--scope "a/**,b/**"` recusado | vírgula não é aceita | repita a flag: `--scope "a/**" --scope "b/**"` |
| glob expandido pelo shell | glob sem aspas | sempre entre aspas |
| subagente gravou saída de outro lote | violação da regra de escrita | cada subagente grava só `{tmp}/spotcheck/{lote}.json5`; descarte a saída alheia e redespache o lote |

## O que muda no `--fast`

Nada. Spot-check e entrevista rodam nos dois modos.
