# Walkthrough — uma execução real na fixture py-billing

Passo a passo de uma execução da skill no repositório de teste `py-billing` (serviço Python de faturamento:
faturas, pagamentos, ledger), do `init` à decisão. Todos os trechos são **reais**, recortados de duas execuções
no modo `--fast`, sem usuário na sessão (aprovações `--simulated` por `eval-sim`):

- **Execução A** — iteração 4 (versão atual da skill), de `init` até `validate.3`, onde foi pausada:
  rodada interna `rodada-4/py-billing-setup-vague/with_skill/` (`outputs/stage-log.txt` e
  `target/`).
- **Execução B** — iteração 3, completa até a decisão (NO-GO):
  rodada interna `rodada-3/py-billing-setup-vague/with_skill_fast/` (`outputs/` e
  `target/.swarm/`).

Nos logs, `cs` é a função de shell `cs() { python3 ~/.claude/skills/codebase-specialists/scripts/cs.py "$@"; }`
que o executor usou (em zsh, guardar o comando numa variável não funciona).

O prompt do eval foi: **"monta o time de agentes pra esse repo"** (eval 1, `evals/evals.json`).

## 0. O repositório

`evals/fixtures/py-billing/repo/`: `src/billing/{invoices,ledger,payments,shared}`, `tests/`, `scripts/
check_no_float_money.py`, `docs/adr/0001-money-as-integer-cents.md`, `0002-ledger-append-only.md`,
`0003-idempotent-captures.md`, `CLAUDE.md` humano, `Makefile`, `uv.lock`. O `build.sh` reconstrói 21 commits com
correções, um revert e um bump de dependência; há um bug plantado em `late_fees.py` e um README desatualizado.

## 1. init (Execução A)

```text
$ cs stage check init.1
ok init.1: confirmar que o alvo é a RAIZ de um repo git e o working tree (recomendar limpo)
$ cs stage check init.2 --answer [sem usuário] plataformas default: claude-code,cursor,copilot,codex; modo --fast (padrão). …
ok init.2: confirmar plataformas e mostrar o que será criado (4–6 linhas)
$ cs init --platforms claude-code,cursor,copilot,codex
mesclado em .swarm/run.json5 (run_id f124f41b05083906; progresso mantido): init explícito registrado
$ cs stage done init
etapa init fechada → .swarm/stages/init.handoff.json5; próxima: scan
```

## 2. scan (Execução A)

O pacote de entrada da etapa coube em ~385 tokens (`// pacote de entrada da etapa scan (~385 tokens) — cs.py
stage load`). Um único `cs scan` produziu as 13 camadas:

```text
L0  inventory         17 fatos → .swarm/facts/inventory.json5 (41 arquivos; ignorados: fixture=3)
L5  history           36 fatos → .swarm/facts/history.json5
L7  operations         5 fatos → .swarm/facts/operations.json5 (declared=2, failed=0, unavailable=1, verified=2)
L9  business_rules    40 fatos → .swarm/facts/business_rules.json5
L9  glossary          23 fatos → .swarm/facts/glossary.json5
L10 project_docs      12 fatos → .swarm/facts/project_docs.json5
index: 201 fatos → .swarm/facts/index.json5
```

Os 3 arquivos de fixture (`tests/fixtures/` com `.csproj` e `package.json` falsos) foram ignorados. `ruff` não
estava instalado: `make lint` ficou `unavailable` (ambiente), não `failed` (repositório).

Um fato real produzido (regra de negócio):

```json5
{claim: "Limite LATE_FINE_BP = 200 (business) em src/billing/invoices/late_fees.py:12; coberto por tests/test_late_fees.py:15 (…)",
 data: {kind: "limit", subject: "LATE_FINE_BP", value: "200", test: "tests/test_late_fees.py:15", …},
 evidence: [{file: "src/billing/invoices/late_fees.py", line: 12}, {file: "tests/test_late_fees.py", line: 15}],
 id: "brule.limit.late_fine_bp", layer: "business_rules", origin: "mechanical", confidence: "medium", …}
```

**Spot-check (scan.5):** 2 subagentes (lotes A e B, 5 fatos cada) conferiram os fatos no código; todos `ok`.
Dois registros:

```text
$ cs facts spotcheck record --fact docs.stale.readme.md.14 --verdict ok --note README.md:14 cita httpx 0.26.0, mas uv.lock:69 fixa 0.27.0 (pyproject.toml:8 também está em 0.27.0). --by spotcheck-B
$ cs facts spotcheck record --fact brule.validation.src-billing-ledger-journal.py.54 --verdict ok --note journal.py:53-54 levanta LedgerImbalance quando débitos != créditos, a linha 52 tem a segunda regra com a mesma exceção e test_ledger.py:19 chama post esperando LedgerImbalance, então a ressalva de ambiguidade procede. --by spotcheck-B
```

Note o fato `docs.stale.readme.md.14`: o README diz httpx 0.26.0, o lockfile diz 0.27.0. O scan registrou a
divergência em vez de repetir o README como verdade.

**Entrevista (scan.6):** 8 perguntas, só sobre o que o código não diz. Sem usuário, todas viraram lacunas:

```text
$ cs interview ask --id freeze-scope --question O congelamento de deploy entre dia 28 e dia 2 vale só para payments ou também para ledger e invoices? --scope src/billing/** --context CLAUDE.md:4
$ cs interview record --id freeze-scope --answer-unknown --by eval-sim
```

O congelamento entre os dias 28 e 2 vem do `CLAUDE.md` humano (fato L10, instrução do time); a pergunta é sobre
o **alcance** dele, que ninguém escreveu. Resultado: `gap.freeze-scope`, citável como cautela, nunca como
conhecimento.

## 3. specialize (Execução A)

**Roster derivado:**

```text
$ cs team derive
dev-invoices           dev      scripts/**, src/billing/*, src/billing/invoices/**
dev-ledger             dev      src/billing/ledger/**
dev-payments           dev      src/billing/payments/**
dev-shared             dev      src/billing/shared/**
reviewer               gate     (sem escrita)
security               gate     (sem escrita)
qa                     dev      tests/**
architect              design   .gitignore, Makefile, README.md, docs/**, pyproject.toml, ruff.toml, uv.lock
po                     product  (sem escrita)
```

**Ajuste com julgamento:** o checker de dinheiro da ADR 0001 (`scripts/check_no_float_money.py`) e o pacote raiz
(`src/billing/__init__.py`) são núcleo compartilhado, não faturas. Dois `roster move` para `dev-shared`; cada um
revalidou e **invalidou** a aprovação; depois:

```text
$ cs team approve --by eval-sim --simulated
roster aprovado (simulado) por eval-sim (9 agentes; sha f37ec497f74a) → .swarm/team-approvals.jsonl
```

**Cartões (specialize.3):** `team facts <agente> --out <alvo>/.swarm/tmp/in/<agente>.facts.json5` para os
9 agentes; 9 redatores em 3 lotes de 3, em primeiro plano; cada um gravou
`.swarm/tmp/cards/<agente>.draft.json5`; o orquestrador registrou em série com
`cs team card set <agente> --file <abs>`.

**Camadas (specialize.4):**

```text
$ cs team core from-panel
core.lines gravado: 9 linha(s) (sem painel consolidado: só s0_core dos cartões)
$ cs emit budget
CMD      máx  10 /  25 linhas (.claude/skills/feature-autonoma/SKILL.md)
ORCH     máx  60 /  80 linhas (.claude/orchestrator.md)
S0       máx  29 /  40 linhas (.cursor/rules/cs-core.mdc)
S1       máx  77 /  80 linhas (.claude/agents/reviewer.md)
S2       máx  56 /  60 linhas (.claude/rules/cs-qa.md)
orçamento por camada: ok
```

## 4. round-table (Execução A) — pulada no `--fast`

```text
$ cs stage skip rt.1 --reason --fast (padrão)
pulada rt.1: … — motivo registrado (aparece em `stage status` e no relatório)
…
$ cs stage done round-table-deep-specialize
etapa round-table-deep-specialize fechada → .swarm/stages/round-table-deep-specialize.handoff.json5; próxima: validate
```

## 5. validate

### validate.1 — emissão (Execução A)

O dry-run listou `outside: 78 escrita(s) FORA de .swarm/ (exigem --allow-outside)`, por exemplo:

```text
  append-block CLAUDE.md  (arquivo humano sem marcadores; bloco acrescentado ao fim (backup))
  create       src/billing/ledger/AGENTS.md  (novo (só bloco))
  create       .github/agents/dev-ledger.agent.md  (novo)
```

Com o OK (simulado), `cs emit --allow-outside` escreveu os artefatos, fez backup do `CLAUDE.md` humano em
`.swarm/emit/backups/` e validou: `validação G7: ok (100 artefatos)`.

O núcleo S0 que entrou no `CLAUDE.md` (trecho real):

```text
<!-- codebase-specialists:begin -->
## Núcleo do repositório

- Toda mudança em valor monetário precisa de teste com centavo quebrado (ex.: 99999 cents).
- ADR 0001: todo valor monetário é int de centavos em billing.shared.money.Money; float nunca entra; percentuais em basis points, arredondamento half-even só em Money.percent, rateio via Money.allocate.
- Comandos verificados do repo: `make test` e `make check-money` (exit 0); `make lint` depende de ruff, ausente no scan.
```

O cartão emitido do `dev-ledger` (`.claude/agents/dev-ledger.md`, recorte):

```text
---
name: dev-ledger
description: "Use para mudar o ledger de partidas dobradas em src/billing/ledger/** (Journal.post/reverse, Posting, LedgerEntry, plano de contas, saldo): validação de lançamento, estorno e balanceamento. Lê src/billing/shared/** (Money, erros, clock) sem alterar."
tools: Read, Grep, Glob, Bash, Edit, Write
model: inherit
memory: project
---
## Território
- Escreve somente em: `src/billing/ledger/**`
- Lê também: `src/billing/shared/**`

## Recusas
- Não mexer no plano de contas em `src/billing/ledger/accounts.py` sem confirmação prévia da Carla (contabilidade) — devolve ao tech-lead pedindo esse contato. — porque Instrução do time no CLAUDE.md do repositório.
- Não remover ou renomear o alias legado JournalEntry (sinônimo de LedgerEntry) sem decisão explícita. — porque Ninguém sabe se o importador CSV de 2024 ainda o usa nem quando pode sair (lacuna declarada pelo dono).

## Feito quando
- `make test` sai com exit 0 e `make check-money` sai com exit 0, e o diff só contém arquivos dentro de `src/billing/ledger/**`.
```

Repare: nenhuma persona; cada recusa tem o porquê (ADR, instrução do time, lacuna); o "feito quando" usa só
comandos `verified`; a lacuna sobre `JournalEntry` aparece como **cautela**, não como conhecimento.

### validate.2 — sondas e baseline (Execução A)

```text
$ cs probes generate
dev-ledger             território=12 cross=8  negativas=3
…
gravado: .swarm/probes/bank.json5 (180 sondas) — NUNCA mostre a agentes examinados
```

Para cada agente: `cs probes exam-pack <agente> --out <alvo>/.swarm/tmp/exam/<agente>`; 9 subagentes de
baseline (sem cartão, sem repositório) em 3 lotes; `cs probes baseline-filter <agente> --answers …baseline.json5`.

### validate.3 — exame (Execução A)

9 examinados guiados (clone local do alvo com histórico, sem `.swarm/`), depois 27 juízes POR-QUÊ (3 por
agente: opus, sonnet, haiku). Pontuação do guiado:

```text
$ cs probes check dev-invoices --answers …/.swarm/tmp/answers/dev-invoices.guided.json5
dev-invoices: território=1.0 cross=1.0 alucinações=0 delta=0.7 → G4 PASS (provisório: painel pendente)
```

O primeiro `stage check validate.3` **falhou** (resultados ainda provisórios); depois dos 22 vereditos
`cs panel why <agente> --probe <id> --verdict PASS` e de um `cs probes check <agente>` por agente, passou:

```text
$ cs stage check validate.3
ok validate.3: exame por agente: guiado sobre `probes exam-pack <agente> --out …` …
```

A Execução A parou aqui (o exame em modo fechado ainda rodava). O restante vem da Execução B.

### Placar e gates (Execução B, iteração 3)

Na Execução B, 5 dos 9 agentes reprovaram no exame **só** por sondas de histórico (sha de commit) — naquela
versão o pacote do exame excluía `.git/` (defeito corrigido na iteração 4 com o clone local). Como o `--fast`
pula o refino, eles ficaram `em-refino`. Trecho de `.swarm/report.md`:

```text
| agente | kind | território | território (sonda) | cross | alucinações | delta | status | modo fechado (sinal) |
| dev-ledger | dev | `src/billing/ledger/**` | 0.8889 | 0.8333 | 0 | 0.65 | especialista | 0.2 / 1 aluc. |
| dev-invoices | dev | `src/billing/invoices/**` | 0.8 | 0.75 | 0 | 0.35 | em-refino | 0.2 / 1 aluc. |
| architect | design | `.gitignore`, `Makefile`, `README.md`, `docs/**`, … | 1.0 | 0.8571 | 0 | 0.65 | especialista | 0.35 / 1 aluc. |
```

Note a coluna "modo fechado": só com o cartão, sem o repositório, todos ficaram entre 0,15 e 0,35 — esperado
(cartão = mapa, não memória) e fora do G4.

`cs.py verify` (Execução B, `acceptance.json5`):

```text
G1  PASS  regra 3 PASS: cobertura 1.0, sobreposições 0
G2  FAIL  security: command `rg -nP --type py "pickle\.loads?\(|…" …` em rules.check — comando fora de operations.json5 verified
G3  PASS  reviewer sim=0.0 (… vs code-reviewer) ok | …
G4  FAIL  reviewer FAIL território=0.8333 cross=0.8 alucinações=0 delta=0.45 ciclo=1 | security …
G5  PASS  2 comando(s) de teste verified (ex.: `make test` exit 0)
G6  PASS  adapter cursor instalado (plataforma do run) | pre-commit → cs-precommit (E2 para codex, …)
G7  PASS  G7 ok: 99 artefatos válidos (claude-code,cursor,copilot,codex)
G8  PASS  recall@5=1.0 p95=1.6ms (parede 51.53ms) → G8 PASS
G9–G12, G14, G15 PASS (suítes da skill; G11 "parcial: eval end-to-end de evals/ não roda no verify")
G13 PASS  0 erro(s) de mapa; do_not_parallelize=8
G16 PASS  etapas init, scan, specialize, round-table-deep-specialize fechadas; Ran 42 tests
decision: NO-GO   enforcement: claude-code=hook, codex/copilot/cursor=instructions
```

Dois vermelhos, os dois típicos do `--fast` naquela versão:

- **G2** (Existence Ratio 0,9803 = 448/457): comandos `rg …` em `rules.check` sem `[unverified]` nos cartões de
  security/architect, e proibições ("nunca use `pickle.load`") lidas como símbolo inexistente — sem a mesa
  redonda, nada mediu existência antes do verify (defeito P0 ainda aberto na iteração 4).
- **G4**: agentes `em-refino` ⇒ NO-GO pela regra de GO.

## 6. approve (Execução B)

```text
Decisão: NO-GO (simulado) — gates NO-GO; decidido por eval-sim em 2026-10-03T15:58:16+00:00 (sem humano: aprovação SIMULADA, não vale como aceite do dono)
```

O relatório lista os pulos (`rt.1`–`rt.4`, `validate.4`), a garantia por plataforma, as 6 lacunas declaradas
(moedas futuras, alcance do congelamento de deploy, origem da alíquota de ISS, teto de multa/juros, remoção dos
aliases legados, provedor real do gateway), os gates vermelhos e "Como usar". Por fim,
`.swarm/bin/cs-session save --did … --next …` congelou o baseline.

Resumo da Execução B (`outputs/stage-log.txt` e `timing-notes.txt`): ~21 min de parede, 201 fatos, spot-check
10/10 ok, 6 lacunas, 9 agentes, 99 artefatos emitidos, 33 subagentes em 12 lotes (nenhum 429), 4 agentes
`especialista` e 5 `em-refino`, **NO-GO (simulado)**. Qualidade medida pelo corretor: [Q] 13/13 (baseline sem
skill: 9/13).

## 7. O que esta execução ensina

- O valor apareceu antes do GO: [Q] 13/13 contra 9/13 da baseline — território coberto, invariantes de ADR em
  todos os donos, histórico real, versões do lockfile, README velho tratado como `stale`.
- O NO-GO foi **honesto**: a regra de GO não deixa um time com agentes não provados passar, e o relatório diz
  exatamente por quê.
- Os vermelhos apontaram defeitos da skill, não do repositório — e viraram itens das iterações seguintes (clone
  com histórico no exame; existência no `--fast`, ainda aberto). Ver
  [../08-limites-e-defeitos-conhecidos.md](../08-limites-e-defeitos-conhecidos.md).
