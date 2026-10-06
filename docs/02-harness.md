# 02 — Harness: estado, máquinas, guards e enforcement

Fontes: `references/harness.md`, `references/brief-schema.json5`, `scripts/harness/machines.json5` (fonte única
das máquinas), `scripts/harness/engine/engine.py` (guardas), `scripts/harness/engine/autonomy.py`,
`scripts/harness/engine/guard.py`, `scripts/harness/install.py`.

Lema do harness: **dados estruturados decidem; o motor é o único que escreve estado; hook bloqueia; ledger
prova.**

## 1. O que é instalado no alvo

`cs.py harness install` (etapa validate.5) copia o motor da skill para o alvo e cria o estado:

```text
.swarm/harness/   motor copiado da skill (sha256 em MANIFEST.json5; protegido):
                        hcore.py j5.py engine.py cmds.py views.py brief.py router.py autonomy.py session.py
                        state.py validate.py guard.py bashscan.py selftest.py mem.py
                        machines.json5 routing.json5 config.json5 adapters/<plataforma>.md
.swarm/bin/       cs-state, cs-mem, cs-session, cs-route, cs-precommit   (sh; qualquer plataforma)
.swarm/state/     board.json5  events.jsonl (cadeia de hash)  harness-ledger.jsonl (guards)
                        ledger.jsonl (log do cs.py)  model-router.jsonl  autonomy.json5  selftest.json5
                        evidence/  memory/agents/<agente>.json5  memory/promotions.json5
.swarm/memory/    knowledge.jsonl  episodes.jsonl  stale.json5  index/ (cache)
.swarm/session/   resume.json5
.claude/hooks/cs-guard.sh   wrapper fail-closed dos hooks
.claude/settings.json       merge dos hooks (backup em .swarm/backups/settings/settings.json.bak-<ts>; chaves alheias preservadas)
specialists.mk + bloco `include specialists.mk` no Makefile
.git/hooks/pre-commit       (com --git-hook) → .swarm/bin/cs-precommit
```

Os bins (`.swarm/bin/cs-*`) resolvem a raiz por `$CLAUDE_PROJECT_DIR`, senão pelo diretório onde estão
instalados (`.swarm/bin/../..`) — nunca pelo diretório da skill. `cs-precommit` roda o validador do estado e
`guard.py check-diff --staged` (arquivos staged × território).

Formatos: tudo que é da skill em JSON5; o que é append-only (`events.jsonl`, ledgers, memória episódica) em JSONL
com cadeia (`prev` = sha256 dos bytes da linha anterior). Nada edita `board.json5`/`events.jsonl` à mão: o
validador refaz o replay dos eventos e detecta edição manual pela cadeia.

## 1-bis. Harness único (outro harness no alvo → `--replace-harness`)

O alvo tem **um** harness. `cs.py init` e `cs.py harness install` detectam outro (cada sinal sozinho:
`.swarm/instance.json` da fábrica v8, `scripts/harness/`, `.claude/kernel/`, hook em `.claude/settings.json` cujo
comando não é `cs-guard.sh`) e saem com exit 3 sem escrever, imprimindo o plano de substituição. Não são sinais:
`settings.json` só com `permissions`/`env`, o próprio harness em `.swarm/` (reinit idempotente) e o backup.
Substituir: `cs.py init --platforms claude-code --replace-harness --allow-outside` — backup fiel (sha256) em
`.swarm/backups/harness-anterior/<caminho original>` + manifesto, remoção do harness anterior (incluindo os blocos
dele no `lefthook.yml` e no `Makefile`, preservando o resto), importação das invariantes BIZ-n do
`DOMAIN_INVARIANTS.yaml` como fatos em `.swarm/facts/`. O legado desta própria skill não é "outro harness": o
`init` aponta o `upgrade` (`09-upgrade.md`). `cs.py harness selftest` inclui a sonda **harness único**.

## 2. Um motor, várias máquinas

Todas as máquinas estão em `scripts/harness/machines.json5` e passam pelo mesmo motor (`engine.transition`): o
estado atual tem de estar em `from`; cada guarda nomeada é uma função em `engine.GUARDS` (guarda citada e não
implementada = falha); a transição vira evento em `events.jsonl`. `cs-state why <id>` explica o estado atual e a
próxima transição permitida; `cs-state next` diz ao orquestrador o que fazer agora.

Limites globais: `max_retries: 2`, `max_attempts: 3`. Veredito: `PASS | FAIL | NEEDS_SPECIALIST`. Tipos de
abstenção: `spec_ambiguous | test_suspect | out_of_territory | other`.

## 2-bis. As três faixas de interação (escolhidas pela classe da triagem)

Nem todo pedido precisa da hierarquia inteira. A classe gravada em `session triage` escolhe a faixa
(`classes.<c>.lane` em `machines.json5`, fonte única); `cs-state next` e o kernel do orquestrador
(`assets/templates/orchestrator.md`) indicam a faixa. As garantias da última coluna **nunca afrouxam**.

| Faixa | Classe | Exige | Garantias que nunca afrouxam |
|---|---|---|---|
| Consulta | `pergunta` | nada no board; delegação de consulta descartável (`ASK-n`) | agente SÓ LEITURA (guard bloqueia Write/Edit/Bash que escreve); evento na cadeia e no ledger |
| Task avulsa | `trivial`, `pequena` | SÓ a task (story implícita `STORY-AVULSA-<sessão>`, criada pelo motor) | território, `verification_command`, diff × `allowed_paths`, revisão de gate em `pequena` |
| Fluxo completo | `feature`, `risco` | épico → feature → sprint → story → task (seções 3–6) | todas |

```text
 session start → session triage --class …
        │
        ├─ pergunta ──────▶ cs-state ask <agente> "<pergunta>" [--paths <glob>]
        │                     └─ consulta ASK-n BRIEFED ─▶ Agent(description="ASK-n: …") ─▶ guard: DISPATCHED (só leitura)
        │                          └─ SubagentStop ─▶ ANSWERED (sem submit/task/story/review) ─▶ session answer
        │
        ├─ trivial|pequena ─▶ cs-state add task --quick --agent <a> --title … --allowed-path <arq> --verify-cmd "<cmd>"
        │                     ├─ toca >1 território/agente, invariante escopado ou área congelada ─▶ RECUSA
        │                     │     "suba a classe: `cs-state session triage --class feature|risco`"
        │                     └─ task em STORY-AVULSA-<sessão>, sessão → PLANNING, delegação BRIEFED
        │                          └─ session execute ─▶ Agent ─▶ submit ─▶ verify ─▶ (pequena: 1 review) ─▶ accept
        │
        └─ feature|risco ───▶ épico → feature → story READY → add task --story … --ready (fluxo de sempre)
```

Detalhes da task avulsa: `--goal` (padrão = título), `--ref` e `--out` são opcionais; `--ac` também (padrão:
`AC-1` verificado pelo `verification_command`); `--allowed-path` e `--verify-cmd` são obrigatórios. `--quick` recusa
`--story/--sprint`, sessão ausente ou de outra classe (exit 1). Em `trivial`, 1 task com 1 arquivo explícito;
mais que isso → "suba a classe" para `pequena`. `--work-type us|bug|fix` grava o tipo da task (padrão `us`).

Guardas novas das faixas:

| Onde | Guarda / decisão | Efeito |
|---|---|---|
| `add task --quick` | sessão ativa com classe `trivial\|pequena` | senão RECUSA (exit 1), indicando a faixa certa |
| `add task --quick` | `quick_problems`: >1 território, território de outro agente, 2º agente na sessão, invariante escopado, `frozen_paths` | RECUSA com "suba a classe: `cs-state session triage --class feature\|risco`" |
| `add task --quick` | `brief_valid` (sem story real; `references`/`scope.out` opcionais) | task nasce BRIEFED; brief inválido = recusa |
| M4 `dispatch` | `consult_agent_free`, `consult_model_declared` | um trabalho em voo por agente (task ou consulta); `model` declarado |
| M2 `dispatch` | `one_in_flight_per_agent` conta também consultas em voo | o guard identifica o ator pelo `agent_type` |
| `pre-agent` | id `ASK-n` BRIEFED do MESMO agente na `description` | despacha a consulta; ANSWERED/CANCELLED não reabre (descartável); sem id continua bloqueado |
| `pre-write` / `pre-bash` | subagente com consulta DISPATCHED | toda escrita bloqueada, mesmo dentro do território |
| `pre-bash` | `cs-state ask` | só o agente principal (subagente bloqueado) |
| `subagent-stop` | consulta DISPATCHED do agente | → ANSWERED + registro `consult_answered` no ledger; não pede submit |

### M4 — consulta

| Transição | De → para | Guardas |
|---|---|---|
| (criação por `cs-state ask`) | — → BRIEFED | agente existe em `team.json5`; pergunta não vazia |
| `dispatch` (pelo `pre-agent`) | BRIEFED → DISPATCHED | `consult_agent_free`, `consult_model_declared` |
| `answer` (pelo `subagent-stop`) | DISPATCHED → ANSWERED | — |
| `cancel` (`cs-state consult cancel --id ASK-n --reason …`) | BRIEFED/DISPATCHED → CANCELLED | `reason_present` |

## 3. M1 — sessão do orquestrador (uma por pedido do usuário)

```text
                     cs-state session start --request "…"
                                  │
                                  ▼
               ┌─────────────── TRIAGE ◀──── triage (reclassifica; também em PLANNING/EXECUTING)
               │ answer           │ plan                 confirm (TRIAGE/PLANNING: grava a frase do usuário)
               │ (classe          ▼
               │  pergunta)    PLANNING ◀───────────────────── replan ─────────┐
               │                  │ execute                                    │
               │                  ▼                                            │
               │              EXECUTING ───────────────────────────────────────┤
               │                  │ verify                                     │
               │                  ▼                                            │
               │              VERIFYING ── review (gate; fica em VERIFYING) ───┘
               │                  │ report
               ▼                  ▼
            REPORTING ◀───────────┘
               │ close
               ▼
             IDLE
```

| Transição | De → para | Guardas (mecânicas) |
|---|---|---|
| `triage` | TRIAGE/PLANNING/EXECUTING → mesmo estado | `class_valid`, `why_present` |
| `confirm` | TRIAGE/PLANNING → mesmo | `note_present` |
| `answer` | TRIAGE → REPORTING | `class_is_question` |
| `plan` | TRIAGE → PLANNING | `class_set`, `class_not_question` |
| `execute` | PLANNING → EXECUTING | `plan_recorded` (tasks com brief válido), `plan_fits_class`, `waves_disjoint`, `risk_confirmed` |
| `replan` | EXECUTING/VERIFYING → PLANNING | — |
| `verify` | EXECUTING → VERIFYING | `no_delegation_in_flight`, `all_tasks_closed` (ACCEPTED, BLOCKED ou DROPPED) |
| `review` | VERIFYING → mesmo | `reviewer_is_gate`, `verdict_valid`, `findings_present` |
| `report` | VERIFYING → REPORTING | `pipeline_satisfied` (toda task ACCEPTED, DROPPED ou com delegação ESCALATED; review final PASS quando a classe exige) |
| `close` | REPORTING → IDLE | — |

### As 5 classes (proporcionalidade)

| Classe | Critério (`why` em machines.json5) | O que o motor exige |
|---|---|---|
| `pergunta` | nenhuma escrita | 0 tasks; sem review; sai por `answer` |
| `trivial` | ≤1 arquivo, diff numa frase, sem invariante tocado | 1 task; `allowed_paths` com **1 arquivo explícito** (sem glob); nenhum invariante escopado; sem review |
| `pequena` | ≤1 território, critérios claros | 1 agente dev; ≥1 review de gate (também na task avulsa) |
| `feature` | >1 território ou critério a definir | task de agente `kind: product` (po) **antes** do dev; ≥1 review de gate; review final PASS |
| `risco` | toca invariante/área congelada/segurança | como `feature` + **2 reviews de gates distintos** + `session confirm --note "<frase do usuário>"` |

Task que toca `frozen_paths` (config do harness) exige classe `risco`. Ambiguidade: o orquestrador só pergunta ao
usuário em TRIAGE quando leituras diferentes geram trabalhos materialmente diferentes; senão decide e grava a
suposição (`--assume`).

## 4. M2 — delegação (uma por despacho de subagente)

```text
 PLANNED ──ready──▶ BRIEFED ──dispatch──▶ DISPATCHED ──submit──▶ RETURNED ──verify──▶ VERIFIED ──review──▶ REVIEWED
    │                  ▲  │                    │ return (sem submission)  │  (guarda falha → REJECTED)        │ │
    │                  │  │                    ▼                          ▼                                   │ │
    │                retry│               REJECTED ◀──── reject ──── (RETURNED/VERIFIED/REVIEWED)           │ │
    │             (≤2, sobe│tier)              │                                                             │ │
    │                  └───┼───────────────────┘                                                             │ │
    │                      │                                       accept (VERIFIED ou REVIEWED) ──▶ ACCEPTED ◀┘ │
    │                      │                                                                                  │
    ├── escalate (de quase todo estado ativo) ──▶ ESCALATED ─┐                                                 │
    ├── abstain (BRIEFED/DISPATCHED/RETURNED) ──▶ ABSTAINED ─┤  aguardam a DECISÃO HUMANA (não são terminais) │
    ├── reroute (REJECTED/PLANNED/BRIEFED)    ──▶ REROUTED   │                                                 │
    └── drop (REJECTED)                       ──▶ DROPPED    │                review pode repetir: REVIEWED → REVIEWED ─┘
                                                             │
        de ESCALATED/ABSTAINED, três saídas: ────────────────┘
          retomar           retry --decision "<decisão>"         ──▶ BRIEFED   (não consome tentativa; task destravada)
          trocar de agente  reroute --agent <a> --decision "..." ──▶ REROUTED  (nova delegação PLANNED do outro agente)
          descartar         drop --reason "..."                  ──▶ DROPPED   (task DROPPED, fechada)

        verify que falhou por AMBIENTE (failure_kind: environment), de REJECTED ou ESCALATED:
          reverificar       reverify                              ──▶ RETURNED ──verify──▶ VERIFIED (ambiente consertado)
          exceção humana    waive-verify --by <humano> --evidence ──▶ VERIFIED  (verify_waiver; review de gate obrigatória)
```

Estados terminais: `ACCEPTED`, `REROUTED`, `DROPPED`. Aguardando decisão humana (`awaiting_human`): `ESCALATED`,
`ABSTAINED` — nunca terminais, sempre com as três saídas acima (oráculo `tests/test_maquinas_vivacidade.py`: nenhum
estado sem saída a não ser declarado em `terminal`; épico/feature/sprint/story declaram seus fins). Em voo:
`DISPATCHED`. `cs-state next` e `cs-state why <task|delegação>` imprimem as três saídas com o comando pronto.

| Transição | De → para | Guardas |
|---|---|---|
| `ready` | PLANNED → BRIEFED | `brief_valid` |
| `dispatch` | BRIEFED → DISPATCHED | `session_executing`, `deps_accepted`, `one_in_flight_per_agent`, `no_parallel_collision`, `class_dispatch_order`, `budget_available`, `model_declared` — só pela ferramenta Agent (hook `pre-agent`, grava `tool_use_id`); fora do Claude Code (sem hook) `cs-state dispatch --manual` (`tool_use_id: "manual:<ts>"`, `dispatch_origin: "manual"`); sem `--tool-use-id`/`--manual` o CLI recusa e o guard bloqueia qualquer `cs-state dispatch` no Bash do principal (D-1-02) |
| `return` de despacho fantasma | DISPATCHED (sem `tool_use_id`) → REJECTED | — devolve a tentativa (`attempts` −1, `phantom_dispatch`); o `retry` seguinte não conta retry: a task volta à contagem de antes do fantasma |
| `submit` | DISPATCHED → RETURNED | `submission_complete`, `files_in_allowed_paths` |
| `return` | DISPATCHED → REJECTED | — (retorno sem submission = `protocol_failure`) |
| `verify` | RETURNED → VERIFIED (falha → REJECTED) | `command_exit_zero`, `ac_tests_green`, `diff_within_allowed_paths`, `lessons_check_pass` |
| `review` | VERIFIED/REVIEWED → REVIEWED | `reviewer_is_gate`, `reviewer_not_author`, `verdict_valid`, `findings_present` |
| `accept` | VERIFIED/REVIEWED → ACCEPTED | `verify_pass`, `tree_unchanged`, `reviews_satisfy_class` |
| `reject` | RETURNED/VERIFIED/REVIEWED → REJECTED | `reason_present` |
| `retry` | REJECTED/ESCALATED/ABSTAINED → BRIEFED | `retries_left` (não se aplica de ESCALATED/ABSTAINED: decisão humana não consome tentativa), `findings_attached` (de ESCALATED/ABSTAINED exige a decisão explícita em `--decision`/`--findings`; o `reject_reason` antigo não vale), `brief_valid` |
| `escalate` | PLANNED…REJECTED → ESCALATED | `reason_present` |
| `reroute` | REJECTED/PLANNED/BRIEFED/ESCALATED/ABSTAINED → REROUTED | `reason_present` (ou `--decision`), `new_agent_valid` |
| `abstain` | BRIEFED/DISPATCHED/RETURNED → ABSTAINED | `reason_present`, `abstain_kind_valid` |
| `drop` | ESCALATED/ABSTAINED/REJECTED → DROPPED | `reason_present` |
| `reverify` | REJECTED/ESCALATED → RETURNED (e roda o verify) | `reverify_allowed` (submission da tentativa atual; de REJECTED só se a falha foi de AMBIENTE) |
| `waive_verify` | REJECTED/ESCALATED → VERIFIED | `reason_present`, `evidence_present`, `waiver_by_human` (`--by` ≠ ator, ≠ agente do time, ≠ lead/orchestrator), `verify_failed_by_environment` (último verify da tentativa é AMBIENTE e a evidência cita a ferramenta ausente), `tree_unchanged` |

**Falha de ambiente.** O `verify` classifica a falha (`engine/envfail.py`, mesma heurística do `unavailable` do
scan): ferramenta/módulo ausente (`command not found`, `No such file or directory` do make/env/sh, exit 127,
`ModuleNotFoundError` de pacote que não é do repo) **e nenhum sinal de teste/asserção** → `gate_report.failure_kind:
environment` (+ `missing_tools`); qualquer outra coisa — asserção, diff fora do território, lição violada, timeout —
é `code` e não admite exceção. `next`/`why` sugerem `reverify` e `waive-verify` em vez de só retry/escalate. O
`waive-verify` é **ato do humano**: o guard bloqueia o comando para o agente principal e para subagentes; o waiver
(motivo, quem, evidência, sha da saída) fica em `task.verify_waiver`/`waivers`, aparece em `next`, `why` e no
relatório autônomo, e torna a review de gate obrigatória mesmo em classe `trivial`.

O que as guardas conferem (`references/harness.md` §2):

- **brief válido** (`references/brief-schema.json5`): `allowed_paths` ⊆ território do agente, nunca vazio,
  nunca amplo nem reservado; `verification_command` executável (não prosa); critérios de aceite com
  `verified_by` ∈ `verification_command | test:<id> | reviewer` e runner resolvível; referências existentes;
  `scope.out` preenchido; invariantes do escopo anexados automaticamente. `verification_command` **sem**
  checagem crua da árvore sobre `protected_paths` (`git status --porcelain`/`git diff --quiet`): ela reprovaria a
  task pela sujeira legítima de uma task-irmã em voo (D-1-03). O sufixo legado é removido na geração, no `amend` e
  na execução; os `protected_paths` são provados pelo motor no **verify**.
- **dispatch**: sessão M1 em EXECUTING; dependências ACCEPTED; 1 delegação em voo por agente; sem sobreposição
  de `allowed_paths` com delegação em voo; pares `do_not_parallelize` de `.swarm/knowledge/collision.json5`
  com os números (arquivo ausente = aviso no ledger e só disjunção); ordem po→dev conforme a classe; orçamento
  do modo autônomo; `model` declarado (ver [04-roteador-de-modelos.md](04-roteador-de-modelos.md)).
- **submit**: `submission` com `files_changed`, `checks_run`, `risks`, `handoff_notes`; arquivos ⊆
  `allowed_paths`.
- **verify** — o motor **executa** o `verification_command` (sem shell quando possível, com timeout, gravando
  `exit_code`, `tree_sha256`, `command_sha256`, `output_sha256`), todo AC `test:` e confere `files_changed` × git
  (desde o baseline do dispatch) × `allowed_paths`; também executa as lições com `check` do agente.
  `protected_paths` são conferidos contra o que **esta delegação** mudou (fora do território: fotografia do
  dispatch; dentro: base da task, D-0-13), descontado o território de task-irmã em voo; a reprovação nomeia o
  arquivo: `protected_path alterado por esta delegação: <arquivo>`.
- **accept**: verify PASS da tentativa, árvore inalterada desde o verify, reviews de gate ≠ autor conforme a
  classe.

`amend` é evento formal (`--field --after --reason [--found-by]`), nunca edição silenciosa do brief.

### M2 dirige M3 (`drives_task`)

| Delegação | Task |
|---|---|
| PLANNED | DRAFT |
| BRIEFED | READY |
| DISPATCHED | IN_PROGRESS |
| RETURNED | SUBMITTED |
| VERIFIED, REVIEWED | VERIFYING |
| ACCEPTED | ACCEPTED |
| REJECTED | REJECTED |
| ABSTAINED, REROUTED | DRAFT |
| ESCALATED | BLOCKED |
| DROPPED | DROPPED |

REJECTED sem retries restantes → task BLOCKED (3 tentativas) → `escalate` leva ao humano, cuja decisão destrava:
`retry --decision` (task BLOCKED → READY), `reroute` (→ DRAFT) ou `drop` (→ DROPPED). Task DROPPED é fechada:
não segura `session verify`/`report` nem a story (que precisa de ≥1 task ACCEPTED e o resto ACCEPTED/DROPPED).

## 5. M3 — task (registro durável)

```text
 DRAFT ─▶ READY ─▶ IN_PROGRESS ─▶ SUBMITTED ─▶ VERIFYING ─▶ ACCEPTED
   ▲        │           │             │            │ ↺
   │        │           └─────────────┴────────────┴──▶ REJECTED ─▶ READY (retry)
   │        │                                              │
   └────────┴──── (volta a DRAFT de READY/IN_PROGRESS/      └──▶ BLOCKED ─▶ DRAFT | READY (retry com decisão)
                   SUBMITTED/REJECTED/BLOCKED)        BLOCKED alcançável de qualquer estado não final
   DRAFT/REJECTED/BLOCKED ──(drop)──▶ DROPPED (terminal, como ACCEPTED)
```

Pares legais (`machines.json5 → task.pairs`): DRAFT→READY, READY→IN_PROGRESS, IN_PROGRESS→SUBMITTED,
SUBMITTED→VERIFYING, VERIFYING→VERIFYING, VERIFYING→ACCEPTED, SUBMITTED/VERIFYING/IN_PROGRESS→REJECTED,
REJECTED→READY, REJECTED→BLOCKED, BLOCKED→DRAFT, REJECTED/READY/IN_PROGRESS/SUBMITTED→DRAFT, DRAFT→DRAFT,
DRAFT/READY/IN_PROGRESS/SUBMITTED/VERIFYING/BLOCKED→BLOCKED, BLOCKED→READY, DRAFT/REJECTED/BLOCKED→DROPPED e
REJECTED/BLOCKED→SUBMITTED|VERIFYING (reverify/waive-verify). **Nunca** BLOCKED→ACCEPTED: aceite só passa por
verify (ou waiver) + review de gate. REJECTED não é terminal (tem `retry`) e segura `session verify`.

**Harness hotfixado à mão.** Se o histórico de eventos tem transições que só um `machines.json5` editado explicaria
(ou aceite sem gate), o motor canônico reinstalado faz `validate --strict` acusar o replay. O humano reconhece esse
histórico na própria cadeia: `cs-state legacy-ack --reason "…"` grava `harness.legacy_ack` com a lista exata
(seq, entidade, de→para; tasks aceitas sem gate); o validador passa a aceitar **só** esses itens e só para eventos
anteriores ao ack — transição nova continua sujeita à máquina. O guard bloqueia `legacy-ack` para agentes. M3 só muda via M2 ou por bloqueio automático de
tentativas.

**Hierarquia incoerente de motor antigo (D-1-04).** O atalho D-0-09 do motor antigo podia deixar story IN_PROGRESS
com a feature em BACKLOG/READY (e o épico PROPOSED) — o motor novo acusa isso no `validate --strict`
(`engine.hierarchy_problems`), e não havia saída (épico/feature sem amend; `feature ready` exige teste vermelho).
O mesmo `cs-state legacy-ack --reason` reconhece também as incoerências de hierarquia **existentes no momento do
ack**, uma por item, em `data.args.hierarchy` (`{kind, id, state, parent_kind, parent, parent_state, problem}`). O
validador passa a aceitar **só** essas (viram aviso) e só **enquanto continuarem as mesmas**: qualquer mudança de
estado do filho ou do pai depois do ack caduca o reconhecimento, e incoerência nova (outra story, outra feature,
posterior ao ack) continua acusada. Despacho/verify/accept de task de uma story reconhecida seguem normais — o
despacho não tenta promover a feature legada (`feature.start` de BACKLOG seria recusada). Um 2º `legacy-ack` só é
aceito se houver algo novo a reconhecer; sem novidade, é recusado. `cs-state validate [--strict] [--allow-empty]`
roda o mesmo validador (só leitura; exit 1 se reprovar).

## 6. Processo — Épico → Feature → Sprint → Story

Toda task pertence a uma Story; toda transição de processo é feita por `cs-state` (o PO cria com `cs-state add
epic|feature|story`, nunca editando o JSON). `cs-state board` mostra a árvore com rollup.

```text
 Épico   PROPOSED ──activate──▶ ACTIVE ──done──▶ DONE          drop ─▶ DROPPED (de PROPOSED/ACTIVE)
 Feature BACKLOG ──ready──▶ READY ──start──▶ IN_PROGRESS ──done──▶ DONE      drop ─▶ DROPPED
 Sprint  PLANNED (plan: adiciona stories) ──start──▶ ACTIVE ──review──▶ REVIEW ──close──▶ CLOSED
 Story   BACKLOG ──ready──▶ READY ──start──▶ IN_PROGRESS ──review──▶ IN_REVIEW ──done──▶ DONE
                                                   └──reject (IN_PROGRESS/IN_REVIEW)──▶ REJECTED
         requeue (REJECTED/READY/IN_PROGRESS/IN_REVIEW) ──▶ BACKLOG
```

DoR e DoD mecânicos (mensagens de recusa reais de `engine.py`):

| Nível | Guarda | O que exige |
|---|---|---|
| Épico | `epic_dor` (activate) | `objective` e `metric` ("épico sem métrica de sucesso (--metric)") |
| Épico | `epic_dod` (done) | ≥1 feature; todas DONE ou DROPPED |
| Feature | `feature_dor` (ready) | épico válido; `spec` existente; arquivos de aceite existentes; ≥1 `--accept-cmd` executável; **executa os testes de aceite e exige VERMELHO** ("teste de aceite já PASSA hoje … DoR exige teste vermelho") |
| Feature | `parent_epic_active` (start) | épico em ACTIVE |
| Feature | `feature_dod` (done) | ≥1 story; todas DONE; testes de aceite **executados e verdes** |
| Sprint | `stories_have_dor` (plan) | stories adicionadas em READY |
| Sprint | `sprint_dor` (start) | meta (`--goal`), orçamento (`--budget tasks=N,attempts=2,minutes=M`), ≥1 story, todas READY/IN_PROGRESS |
| Sprint | `sprint_review_recorded` (close) | review gravada (`cs-state sprint review`) |
| Story US | `story_dor` (ready) | feature válida; `as_a`/`i_want`/`so_that`; ≥1 critério Gherkin (Dado/Quando/Então) com teste ligado resolvível |
| Story BUG | `story_dor` | passos de reprodução; severidade (`critical\|high\|medium\|low`; aceita `critica\|alta\|media\|baixa`); ambiente; `--failing-test` resolvível que **falha hoje** ("TDD de correção exige vermelho") |
| Story FIX | `story_dor` | `fixes:` válido (`BUG-n` \| `review:<task>` com achado não-PASS \| `forensic:<arquivo>` existente) e `--proving-test` resolvível |
| Story | `story_tasks_accepted` (review) | ≥1 task; todas ACCEPTED |
| Story | `story_dod` (done) | tasks ACCEPTED; testes da story verdes; BUG/FIX exigem também suíte de regressão (`--regression` ou `regression_command` na config) |

Regras de processo (ARCHITECTURE §8-septies): bug nunca é corrigido sem antes existir o teste que o reproduz;
story REJECTED volta ao BACKLOG com os achados; reabrir story DONE exige BUG novo (`--reopens`); sprint fecha
mesmo com stories não entregues — elas voltam ao backlog com motivo.

## 7. Modos de uso: assistido e autônomo

| Modo | Quem decide nos gates | Quando usar |
|---|---|---|
| `assistido` (default) | o usuário aprova plano, escaladas e aceite final | trabalho novo, área sensível, time ainda não provado |
| `autonomo` | o orquestrador, dentro de um mandato pré-aprovado | feature com spec e critérios claros, time aprovado na sonda |

### Entrada — um único toque

```text
.swarm/bin/cs-state autonomy start --feature FEAT-n --spec <arquivo> --budget tasks=6,attempts=2,minutes=90
```

(ou `--story S`; `usd=X` opcional no budget). No Claude Code, o comando emitido `/feature-autonoma <id> <spec>`
conduz esse toque. `autonomy start` **recusa** quando (código em `autonomy.py → start`):

- já existe mandato ACTIVE;
- a feature/story não existe, ou a feature não está em READY/IN_PROGRESS (DoR primeiro);
- spec inexistente; sem critérios de aceite executáveis; arquivo de aceite inexistente;
- classe `risco` ("não roda em modo autônomo");
- `--budget` sem `tasks`, `attempts` ou `minutes`;
- algum teste de aceite não é executável (exit 127) ou **já passa hoje**.

O mandato fica em `.swarm/state/autonomy.json5` com assinatura sha256 (spec, aceite, classe, orçamento,
quem aprovou), também gravada como evento `autonomy.start` — editar o arquivo à mão é detectado.

### Loop

- Hook `Stop` (Claude Code): com M1 em EXECUTING/VERIFYING, trabalho pendente, orçamento e sem condição de
  escalada, **bloqueia a parada** com `{"decision":"block","reason":"continue: cs-state next → …"}`. Anti-loop:
  3 bloqueios sem evento novo → escala `no_progress`; teto de 200 bloqueios (`max_stop_blocks`).
- Checkpoint: `cs-session save` automático a cada delegação ACCEPTED.
- Abstenção e reroute permitidos; retry ≤2 (limitado também pelo `attempts` do orçamento).

### Condições de escalada (param o loop)

`machines.json5 → autonomy.escalation_conditions`, detectadas em `detect_escalation`:

| Condição | Como é detectada |
|---|---|
| `invariant_or_frozen_touched` | task não aceita com invariante escopado ou `allowed_paths` sobre `frozen_paths` |
| `material_ambiguity` | abstenção `spec_ambiguous` |
| `same_rejection_twice` | dois motivos de reject/verify/return da mesma task com Jaccard ≥0,5 |
| `budget_exhausted` | tasks despachadas ≥ `tasks`, minutos excedidos ou USD gasto ≥ `usd` |
| `risk_class_discovered` | sessão M1 ativa com classe `risco` |
| `acceptance_test_changed` | sha256 de um arquivo de aceite mudou |
| `agent_conflict` | pedido `NEEDS_SPECIALIST` sem outro gate para quem rotear |
| `no_progress` | anti-loop do hook Stop |

A escalada grava `.swarm/state/escalation-<timestamp>.json5` com a condição, a evidência e os últimos 10
eventos, e o mandato vai a `ESCALATED`. Estados do mandato: `ACTIVE`, `ESCALATED`, `DONE`, `STOPPED` (terminais:
`DONE`, `STOPPED`; `machines.json5 → autonomy.transitions`).

`ESCALATED` espera o humano e tem duas saídas:

- **retomar** — `cs-state autonomy resume --decision "<decisão do humano>"` → `ACTIVE`. A decisão vai para a cadeia
  de eventos (`autonomy.resume`) e para `decisions[]` do mandato; a impressão digital (condição + evidência) da
  escalada fica em `acknowledged[]` e **não reescala** pela mesma evidência (evidência nova escala de novo);
  contadores anti-loop zeram. Reconhecimento sem evento `autonomy.resume` é acusado pelo validador.
- **encerrar** — `cs-state autonomy stop --reason "..."` → `STOPPED`, modo assistido.

**Nunca no autônomo:** push, merge em branch protegida, alterar teste de aceite aprovado, editar arquivo
congelado, gastar além do orçamento, desligar guard (o kill-switch é ignorado no autônomo). Saída: `cs-state
autonomy report` (relatório em `state/autonomy-report.json5`) e o modo volta a assistido.

## 8. Guards e hooks (Claude Code)

Instalados por `harness install` em `.claude/settings.json`, todos chamando
`"$CLAUDE_PROJECT_DIR"/.claude/hooks/cs-guard.sh <modo>`:

| Evento (matcher) | Modo | Timeout | Faz |
|---|---|---|---|
| PreToolUse `Write\|Edit\|MultiEdit\|NotebookEdit` | `pre-write` | 30 s | principal só escreve em `.swarm/` (não protegido) e `docs/state/`; subagente só no `allowed_paths` da sua delegação DISPATCHED (lexical **e** realpath); subagente em consulta (`ASK-n` DISPATCHED) não escreve nada; protegidos nunca; congelado só em risco confirmado |
| PreToolUse `Bash` | `pre-bash` | 30 s | análise conservadora: redirecionamentos, `tee`, `sed -i`, `rm`, `mv`, `cp`, `dd`, `touch`, `chmod`…; `$(…)`, crase, heredoc, `-c`, `eval`, `xargs`, `find -exec/-delete`, `awk` com `>` → bloqueia; git: subagente só leitura, principal sem reescrita de árvore, sem push no autônomo/branch protegida; `cs-state dispatch` no principal → bloqueia (despacho fantasma: muda o estado sem lançar subagente; despache pela ferramenta Agent com o id na `description`); permissões por ator em `cs-state`/`cs-mem`/`cs-session`/`cs-route` (subagente só `submit`/`abstain` da própria task; lição só na própria memória) |
| PreToolUse `Agent\|Task` | `pre-agent` | 60 s | só despacha com id de delegação BRIEFED (ou de consulta `ASK-n` BRIEFED) do mesmo agente na `description` e `model` = recomendação/override; executa a transição DISPATCHED (baseline git, `tool_use_id`, procedência `declarada-no-despacho`) — único despacho legítimo; revisão: gate ≠ autor e tier ≥ autor; subagente não despacha subagente |
| PostToolUse `Write\|Edit\|MultiEdit` | `post-edit` | 120 s | roda `post_edit_checks` (dos comandos verificados) e devolve diagnóstico; não bloqueia |
| SubagentStart | `subagent-start` | 30 s | injeta o pacote S3 da fase (≤10.000 caracteres, marcado DADO): checklist + ≤5 lições/≤1.500 chars + top-k BM25 |
| SubagentStop | `subagent-stop` | 30 s | consulta em voo → ANSWERED (sem submit); sem submission: bloqueia 1× pedindo submit/abstain; com `stop_hook_active` → REJECTED `protocol_failure`; lê o modelo real da transcrição quando há `agent_transcript_path` (procedência `medida`) |
| Stop | `stop` | 30 s | só no autônomo (seção 7) |
| UserPromptSubmit | `user-prompt` | 10 s | advisory: mensagem com cara de correção → lembra `cs-mem correct`; nunca bloqueia |
| SessionStart | `session-start` | 30 s | injeta `.claude/orchestrator.md` + `cs-session load` |

Propriedades de todos os guards (lições de engenharia, ARCHITECTURE §8):

- **fail-closed**: `python3` ou motor ausente em modo `pre-*` → exit 2 ("bloqueado (fail-closed)"); estado
  ausente/ilegível = bloqueio;
- todo path passa por `realpath` (symlink não burla);
- todo bloqueio grava linha no `harness-ledger.jsonl`; bloqueio = exit 2 + stderr;
- subagente é identificado por `agent_id` no payload (presente só em subagente);
- o install fixa `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` no `env` do settings (delegação de nível único).

**Kill-switch único:** `CS_GUARD_OFF=1` libera e grava `killswitch` (quem, quando, tool, `tool_use_id`, alvo);
se o ledger não grava, bloqueia. No modo autônomo é ignorado (`killswitch_ignored`).

## 9. Enforcement por plataforma

Escada (`references/harness.md` §5):

| Nível | Significado |
|---|---|
| E0 | só prosa |
| E1 | instrução + estado por CLI (`cs-state`) que recusa transição inválida; nada impede escrita fora |
| E2 | detecção mecânica depois do fato: `cs-state verify` (git diff × `allowed_paths`) e `cs-precommit`/CI reprovam |
| E3 | bloqueio antes da execução por hook |

| Plataforma | `enforcement` (no `acceptance.json5`) | Bloqueia antes | Pega depois | Não garante |
|---|---|---|---|---|
| Claude Code | `hook` | Write/Edit fora do território, despacho sem brief, Bash com alvo visível | escrita por programa arbitrário (`python foo.py`, `npm …`) — pelo `verify` | o que um programa escreve sem passar pelo guard, até o `verify` |
| Cursor | `instructions` | nada | `verify`, `cs-precommit` (com `--git-hook`) | escrita fora do território até o commit/verify |
| Copilot | `instructions` | nada | idem | idem |
| Codex | `instructions` | nada (`sandbox_mode = "read-only"` só nos gates) | idem | idem |

Claude Code só sai `hook` se `.claude/settings.json` contém `cs-guard.sh` **e** `.claude/hooks/cs-guard.sh`
existe; instalado com `--no-settings`, ele também é `instructions`. Para Cursor/Copilot/Codex o install grava
adapters em `.swarm/harness/adapters/<plataforma>.md` com o protocolo E1 (`cs-state next` → `cs-state brief
--task <id>` → escrever só em `allowed_paths` → `cs-state submit`) — não instalamos hooks dessas plataformas.

## 10. O que é escrito fora de `.swarm/`

Sempre com consentimento: `--dry-run` lista o bloco `outside`; sem `--allow-outside` nada é escrito fora
(`emit` sai com exit 3).

| Quem | Caminho | Tipo | Desliga com |
|---|---|---|---|
| `emit` (Claude Code) | `CLAUDE.md` (bloco), `.claude/agents/<n>.md`, `.claude/rules/cs-<n>.md`, `.claude/skills/<n>-playbooks/`, `.claude/orchestrator.md`, comandos em `.claude/skills/` | bloco / arquivo | `--platforms` sem `claude-code` |
| `emit` (Cursor) | `.cursor/rules/cs-*.mdc`, `.cursor/agents/<n>.md` | arquivo | `--platforms` sem `cursor` |
| `emit` (Copilot) | `.github/copilot-instructions.md` (bloco), `.github/agents/<n>.agent.md`, `.github/instructions/cs-<n>.instructions.md` | bloco / arquivo | `--platforms` sem `copilot` |
| `emit` (Codex) | `AGENTS.md` raiz (bloco), `<dir>/AGENTS.md` aninhado, `.codex/agents/<n>.toml` | bloco / arquivo | `--platforms` sem `codex` |
| `harness install` | `.claude/settings.json` (merge + backup), `.claude/hooks/cs-guard.sh` | merge / arquivo | `--no-settings` (o wrapper `.claude/hooks/cs-guard.sh` é escrito mesmo assim) |
| `harness install` | `specialists.mk` + bloco `include specialists.mk` no `Makefile` | arquivo / bloco | `--no-makefile` |
| `harness install --git-hook` | `.git/hooks/pre-commit` | arquivo | omitir `--git-hook` |

O Makefile do alvo nunca é sobrescrito: se existe, ganha só o bloco gerenciado; alvo com colisão de nome ganha
prefixo `cs-`. Alvos de `specialists.mk` (`scripts/harness/install.py → MAKE_TARGETS`): `next`, `board`,
`add-epic`, `add-feature`, `add-story`, `sprint-plan`, `sprint-start`, `sprint-review`, `sprint-close`,
`brief ID=`, `dispatch ID=`, `verify ID=`, `review ID=`, `accept ID=`, `reject ID=`, `abstain ID=`,
`session-save`, `session-load`, `mem Q=`, `autonomy-start FEAT=`, `autonomy-status`, `selftest`, `validate`,
`drift`, e `help`; argumentos extras em `ARGS='…'`.

## 11. Verificação do próprio harness

- `cs.py harness selftest` (G6): roda sondas **negativas** contra o wrapper instalado num sandbox (escrita fora,
  Bash com redirecionamento, despacho sem brief…) e confere a integridade do motor (sha256 × `MANIFEST.json5`);
  grava `.swarm/state/selftest.json5`.
- `cs.py harness selftest --drift`: confere o motor e revalida a memória (`cs-mem revalidate` marca `stale` o
  que perdeu evidência). Use quando o código mudou.
- `cs.py harness validate [--strict] [--allow-empty]`: validador do estado (replay da cadeia).
- `cs.py harness status`.

Limitações conhecidas do harness: ver [08-limites-e-defeitos-conhecidos.md](08-limites-e-defeitos-conhecidos.md).
