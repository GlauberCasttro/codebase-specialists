# harness — estado, máquinas, guards, memória, roteador, sessão, autonomia

Dono: `scripts/harness/` (motor + templates) e `scripts/memory/`. Instalado no alvo por
`cs.py harness install`; verificado por `cs.py harness selftest` (gate G6). Python 3.9+ stdlib, sh/bash 3.2.
**Dados estruturados decidem; o motor é o único que escreve estado; hook bloqueia; ledger prova.**

## 1. O que vai para o alvo

```
.swarm/harness/   motor (copiado da skill, sha256 em MANIFEST.json5; protegido)
  hcore.py j5.py engine.py cmds.py views.py brief.py router.py autonomy.py session.py
  state.py validate.py guard.py bashscan.py selftest.py mem.py
  machines.json5 routing.json5 config.json5 adapters/<plataforma>.md
.swarm/bin/       cs-state cs-mem cs-session cs-route cs-precommit   (sh; qualquer plataforma)
.swarm/state/     board.json5 events.jsonl harness-ledger.jsonl (encadeado; guards) ledger.jsonl (log do cs.py) model-router.jsonl autonomy.json5
                        selftest.json5 evidence/ memory/agents/<agente>.json5 memory/promotions.json5
.swarm/memory/    knowledge.jsonl episodes.jsonl stale.json5 index/ (cache JSON estrito)
.swarm/session/   resume.json5
.claude/hooks/cs-guard.sh   wrapper fail-closed (python3/motor ausente em modo pre-* → exit 2)
.claude/settings.json   merge (backup .bak-<ts>; chaves alheias preservadas; nossos hooks reconhecidos por "cs-guard.sh")
specialists.mk + bloco gerenciado `include specialists.mk` no Makefile (nunca sobrescreve; colisão → prefixo cs-)
```
Raiz sempre = `--root` ou `$CLAUDE_PROJECT_DIR` (os bins usam o diretório onde estão instalados como fallback
explícito, nunca o diretório da skill). Formatos: tudo nosso em JSON5 (subconjunto do §8-decies, `j5.py`);
append-only em JSONL estrito com cadeia (`prev` = sha256 dos bytes da linha anterior).

## 1-bis. Harness único (outro harness no alvo → `--replace-harness`)

O alvo tem **um** harness. `cs.py init` e `cs.py harness install` detectam outro (cada sinal sozinho:
`.swarm/instance.json` da fábrica v8, `scripts/harness/`, `.claude/kernel/`, hook em `.claude/settings.json` cujo
comando não é `cs-guard.sh`) e saem com exit 3 sem escrever, imprimindo o plano de substituição. Não são sinais:
`settings.json` só com `permissions`/`env`, o próprio harness em `.swarm/` (reinit idempotente) e o backup.
Substituir: `cs.py init --platforms claude-code --replace-harness --allow-outside` — backup fiel (sha256) em
`.swarm/backups/harness-anterior/<caminho original>` + manifesto, remoção do harness anterior (incluindo os blocos
dele no `lefthook.yml` e no `Makefile`, preservando o resto), importação das invariantes BIZ-n do
`DOMAIN_INVARIANTS.yaml` como fatos em `.swarm/facts/`. O legado desta própria skill não é "outro harness": o
`init` aponta o `upgrade` (`docs/09-upgrade.md`). `cs.py harness selftest` inclui a sonda **harness único**.

## 2. Máquinas (fonte única: `scripts/harness/machines.json5`)

Um motor (`engine.transition`) para todas: estado atual ∈ `from`, guardas nomeadas (implementadas em
`engine.GUARDS`; guarda citada e não implementada = falha), ops `create/set/append/inc` gravadas no evento;
o validador refaz o replay e recusa qualquer mudança de estado fora dos pares legais.

- **M1 sessão** `IDLE→TRIAGE→PLANNING→EXECUTING→VERIFYING→REPORTING→IDLE`; classes `pergunta|trivial|pequena|feature|risco`
  (pipeline proporcional em `classes`): trivial = 1 arquivo explícito, sem invariante escopado, sem review;
  pequena = 1 território, ≥1 gate; feature = task de kind product (po) ACCEPTED antes do dev + review final;
  risco = feature + 2 gates distintos + `session confirm` do usuário.
- **M2 delegação** `PLANNED→BRIEFED→DISPATCHED→RETURNED→VERIFIED→REVIEWED→ACCEPTED|REJECTED`;
  REJECTED → `retry` (≤2, sobe tier) | `escalate` | `reroute` | `drop`; `abstain` de BRIEFED/DISPATCHED/RETURNED.
  M2 dirige M3 (`drives_task`). REJECTED sem retries → task BLOCKED (3 tentativas).
  Terminais: ACCEPTED, REROUTED, DROPPED. **ESCALATED e ABSTAINED esperam a decisão humana** (`awaiting_human`,
  nunca terminais) e têm três saídas: retomar `retry --decision "…"` → BRIEFED (não consome tentativa; task
  BLOCKED→READY), trocar de agente `reroute --agent A --decision "…"` → REROUTED, descartar `drop --reason "…"` →
  DROPPED (task DROPPED, fechada; não segura `session verify`/`report`). `next`/`why` imprimem as três com comando
  pronto. Oráculo `tests/test_maquinas_vivacidade.py`: estado sem saída só se declarado em `terminal`.
  Verify que falhou por AMBIENTE (`engine/envfail.py`: ferramenta/módulo ausente, exit 127, sem sinal de asserção →
  `gate_report.failure_kind: environment`): de REJECTED/ESCALATED, `reverify` → RETURNED + verify de novo, ou
  `waive-verify --by <humano> --reason --evidence` → VERIFIED com `verify_waiver` (guard bloqueia agentes; review de
  gate obrigatória depois, mesmo em trivial; nunca para teste vermelho). Nunca BLOCKED→ACCEPTED.
  Histórico de harness hotfixado: `legacy-ack --reason` (humano) grava `harness.legacy_ack`; `validate` aceita só
  os itens listados e só antes do ack. Também reconhece as incoerências de HIERARQUIA existentes no ack (story
  IN_PROGRESS com feature fora de IN_PROGRESS; feature IN_PROGRESS com épico não ACTIVE — atalho D-0-09 do motor
  antigo), uma por item em `data.args.hierarchy` (filho+estado, pai+estado): aceitas só enquanto filho e pai não
  mudarem de estado; incoerência nova continua acusada; dispatch de task da story reconhecida não tenta promover a
  feature legada. 2º ack só com algo novo a reconhecer. `cs-state validate [--strict]` = mesmo validador (só leitura).
- **M3 task** `DRAFT→READY→IN_PROGRESS→SUBMITTED→VERIFYING→ACCEPTED|REJECTED|BLOCKED|DROPPED`.
- **Processo** (terminais declarados: épico DONE/DROPPED, feature DONE/DROPPED, sprint CLOSED, story DONE)
  épico (PROPOSED/ACTIVE/DONE/DROPPED), feature (BACKLOG/READY/IN_PROGRESS/DONE/DROPPED; DoR executa os
  testes de aceite e exige VERMELHO; DoD exige stories DONE + aceite verde), sprint (PLANNED/ACTIVE/REVIEW/CLOSED;
  close devolve não entregues ao BACKLOG com motivo), story US/BUG/FIX (DoR: Gherkin+teste; BUG com teste que
  falha hoje; FIX com `fixes:` BUG-n|review:<task>|forensic:<arq>). Toda task do fluxo completo pertence a uma story.
- **M4 consulta** `BRIEFED→DISPATCHED→ANSWERED` (`cancel` → CANCELLED): criada por `cs-state ask`, despachada pelo
  `pre-agent` (guardas `consult_agent_free`, `consult_model_declared`), fechada pelo `subagent-stop`. Lista
  `consults` no board (board antigo sem ela é lido como vazia).

**Três faixas** (pela classe; `classes.<c>.lane`): `pergunta` → consulta (só leitura, sem task/story/review);
`trivial|pequena` → task avulsa (`add task --quick`: story implícita `STORY-AVULSA-<sessão>`, nasce BRIEFED; brief
exige `allowed_paths` e `verification_command`, `goal`/`references`/`scope.out` opcionais; `quick_problems` recusa
com "suba a classe" se toca >1 território/agente, invariante escopado ou `frozen_paths`; `pequena` mantém ≥1 gate);
`feature|risco` → fluxo completo.

Guardas mecânicas de M2: brief válido (brief-schema.json5: allowed_paths ⊆ território e nunca amplo/reservado,
`verification_command` executável e não prosa, ACs com `verified_by` ∈ verification_command|test:<id>|reviewer
e runner resolvível, referências existentes, scope.out, invariantes do escopo anexados automaticamente);
dispatch (sessão EXECUTING, dependências ACCEPTED, 1 em voo por agente, sem sobreposição de allowed_paths com
delegação em voo, pares `do_not_parallelize` de `.swarm/knowledge/collision.json5` com os números —
arquivo ausente = aviso no ledger e só disjunção, ordem po→dev por classe, orçamento autônomo, `model` declarado);
submit (submission completa, files ⊆ allowed_paths); **verify executa** o comando (sem shell quando possível,
timeout, `exit_code`, `tree_sha256`, `command_sha256`, `output_sha256`), todo AC `test:` e confere
files_changed × git (desde o baseline do dispatch) × allowed_paths, e as lições com `check` do agente;
accept exige verify PASS da tentativa, árvore inalterada desde o verify e reviews de gate ≠ autor conforme a
classe. `protected_paths` são provados **pelo motor** no verify contra o que ESTA delegação mudou (fora do
território: fotografia do dispatch; dentro: base da task, D-0-13) — a reprovação nomeia o arquivo
(`protected_path alterado por esta delegação: …`); trabalho de task-irmã em voo no protected não conta. O
`verification_command` não leva checagem crua da árvore (`git status --porcelain`/`git diff --quiet` sobre
protected): o brief_valid a recusa, o sufixo legado é removido na geração/amend e na execução (D-1-03).
`amend` é evento formal (before/after/reason/found_by); `status_history` é derivado de events.jsonl (`why`).

## 3. Comandos reais (nomes para templates/evals)

```
cs-state init | next | board | status [--task] | why <id> | brief --task T [--phase implement|verify|review] [--agent]
cs-state add epic --title --objective [--metric]
cs-state add feature --epic --title --spec <arq> --accept-cmd <cmd>… [--accept-file <arq>…]
cs-state add sprint --goal [--budget tasks=N,attempts=2,minutes=M]
cs-state add story --type us|bug|fix [--feature F] --title [--as-a --i-want --so-that --criterion 'AC-1|Dado…Quando…Então…|<test>']
                   [--repro … --failing-test <test> --severity critical|high|medium|low|alta|media|baixa|critica --environment]
                   [--fixes BUG-n (herda a feature) --proving-test <test>] [--regression <cmd>] [--reopens US-n]
cs-state add task --story S --agent A --title --goal --allowed-path P… [--protected-path] --verify-cmd C --ac 'AC-1|crit|verified_by'…
                  --ref arq:linha… --out '…' [--in] [--wave --depends-on --class --hot-path --security-gate --type BE… --from brief.json5] [--ready]
cs-state add task --quick --agent A --title '…' --allowed-path P… --verify-cmd C [--ac … --goal … --ref … --out … --work-type us|bug|fix]
cs-state ask <agente> '<pergunta>' [--paths '<glob>'…]        (imprime Agent(... description='ASK-n: …'))
cs-state consult cancel --id ASK-n --reason '…'
cs-state epic|feature|story <transição> --id X [--reason]      (activate/done/drop | ready/start/done/drop | ready/start/review/done/reject/requeue)
cs-state sprint plan [--id] [--goal --budget] --stories US-1,BUG-2 | sprint start|review|close [--id] [--reason]
cs-state session start --request '…' [--mode] | triage --class C --why '…' [--assume] | confirm --note | answer | plan | execute
                 | replan | verify | review --by G --verdict V --findings | report | close | status
cs-state dispatch --task T --manual [--model M]   (só plataforma SEM hook pre-agent: tool_use_id manual:<ts>, dispatch_origin manual; sem --manual/--tool-use-id recusa; no Claude Code o guard bloqueia — ferramenta Agent)
cs-state ready|submit --files-changed --check --risk --handoff-notes|return|verify|review --by --verdict --findings
         |accept|reject --reason|retry [--findings|--decision]|escalate|block --reason|reroute --agent [--allowed-path] --reason|--decision
         |drop --task|--id X --reason|reverify --task|waive-verify --task --by --reason --evidence|legacy-ack --reason
         |abstain --kind spec_ambiguous|test_suspect|out_of_territory|other --reason|delegate|amend --field --after --reason [--found-by]
cs-state autonomy start --feature F|--story S --budget tasks=N,attempts=2,minutes=M[,usd=X] [--spec --accept-cmd --accept-file --class]
                  | status | stop [--reason] | report | spend --usd X | resume --decision '…'   (ESCALATED → ACTIVE; stop → STOPPED)
cs-mem add (--text … | --agent A --rule … --why … [--paths] [--check]) | correct --agent --wrong --right --why [--paths] [--evidence arq:linha]
       | check --agent [--files] | inject --agent --paths [--title] [--json] | archive | search "<q>" [--paths --kind --agent -k --json]
       | revalidate | consolidate [--agent] | stats
cs-session save --did --next [--blocked --decision --commit] | save --check | load [--brief]
cs-route recommend <id> [--act] | override <id> --model X --reason | outcome <id> [--success --procedencia] | anular --at --motivo | stats
make next|board|add-epic|add-feature|add-story|sprint-plan|…|brief ID=|dispatch ID=|verify ID=|review ID=|accept ID=|reject ID=
     |abstain ID=|session-save|session-load|mem Q=|autonomy-start FEAT=|autonomy-status|selftest|validate|drift|help   (ARGS='…')
cs.py harness install [--platforms cursor,copilot,codex --git-hook --no-settings --no-makefile --dry-run --allow-outside] | selftest [--drift] | validate | status
cs.py memory <args do cs-mem>
```
Flags globais/extras: `cs-state --actor <agente>` (simula o ator do payload em testes), `cs-mem check --no-run`
(lista sem executar checks), `cs-mem consolidate --task T`, `cs.py harness install --path-env` (desligado
por padrão: o `env` do settings só vale após trust do workspace — templates chamam `.swarm/bin/cs-*`
por caminho), `cs.py harness validate --strict | --allow-empty`.
No alvo, todo comando acima é chamado por caminho: `.swarm/bin/cs-state`, `.swarm/bin/cs-mem` etc.

## 4. Guards (Claude Code) — todos fail-closed, realpath, ledger

| Hook (matcher) | Modo | Faz |
|---|---|---|
| PreToolUse `Write\|Edit\|MultiEdit\|NotebookEdit` | pre-write | principal só em `.swarm/` (não-protegido) e `docs/state/`; subagente só no allowed_paths da sua delegação DISPATCHED (lexical **e** realpath); subagente em consulta `ASK-n` DISPATCHED não escreve nada (também via Bash); protegidos e ancestrais de protegidos nunca; congelado só em risco confirmado |
| PreToolUse `Bash` | pre-bash | análise conservadora sem snapshot (G-01): redirecionamentos, tee, sed -i, rm, mv, cp, dd, touch, chmod…, `cd` rastreado; `$(…)`, crase, heredoc, `-c`, eval, xargs, find -exec/-delete, sed `w`, awk com `>` → bloqueia; git: subagente só leitura, principal sem reescrita de árvore, sem push no autônomo/branch protegida; `cs-state dispatch` no principal → bloqueia, inclusive `--manual` (despacho fantasma, D-1-02: muda o estado sem lançar subagente; o caminho é a ferramenta Agent com o id na description); permissões por ator para cs-state/cs-mem/cs-session/cs-route (subagente só submit/abstain da própria task; review só `--by` = si e gate; lição só na própria memória — gates incluídos) |
| PreToolUse `Agent\|Task` | pre-agent | só despacha com id de delegação BRIEFED (ou de consulta `ASK-n` BRIEFED — descartável, ANSWERED não reabre) do mesmo agente na description e `model` = recomendação/override; executa a transição DISPATCHED (baseline git, tool_use_id, procedência `declarada-no-despacho`) — é o ÚNICO despacho legítimo; delegação legada DISPATCHED sem tool_use_id (fantasma) sai por `cs-state return` + `retry`, que devolvem a tentativa; revisão: gate ≠ autor em delegação VERIFIED/REVIEWED com tier ≥ autor; subagente não despacha (também `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`) |
| PostToolUse `Write\|Edit\|MultiEdit` | post-edit | roda `post_edit_checks` (de facts/operations.json5 verificados) e devolve diagnóstico; não bloqueia |
| SubagentStart | subagent-start | consulta: `brief.consult_package` (pergunta, onde olhar, SÓ LEITURA); senão pacote S3 da fase (`brief.package`, ≤10.000, marcado DADO): implementar/verificar/revisar + ≤5 lições/≤1.500 chars + top-k BM25 |
| SubagentStop | subagent-stop | consulta em voo → ANSWERED + `consult_answered` no ledger (sem submit); sem submission: bloqueia 1× pedindo submit/abstain; com `stop_hook_active` → REJECTED `protocol_failure`; lê o modelo real da transcrição quando há `agent_transcript_path` (procedência `medida`) |
| Stop | stop | autônomo: bloqueia a parada (`{"decision":"block","reason":"continue: cs-state next → …"}`) só com M1 em EXECUTING/VERIFYING, trabalho pendente, orçamento e sem escalada; anti-loop (3 bloqueios sem evento novo → escala `no_progress`; teto 200) |
| UserPromptSubmit | user-prompt | advisory: mensagem com cara de correção → lembra `cs-mem correct`; nunca bloqueia |
| SessionStart | session-start | injeta `.claude/orchestrator.md` + `cs-session load` |

Kill-switch único `CS_GUARD_OFF=1`: libera e grava `killswitch` (quem/USER, quando, tool, tool_use_id, alvo); se o
ledger não grava, bloqueia. Em modo autônomo é ignorado (`killswitch_ignored`). Bloqueio = exit 2 + stderr.

**Campos do payload confirmados** (https://code.claude.com/docs/en/hooks, "Common input fields", consultado
2026-10-01): `session_id`, `transcript_path`, `cwd`, `permission_mode`, `hook_event_name`; dentro de subagente
`agent_id` (presente **só** em subagente — é como distinguimos do principal) e `agent_type` (nome do agente; também
presente com `--agent` no principal, por isso o critério é `agent_id`); `tool_name`, `tool_input`, `tool_use_id`
em PreToolUse/PostToolUse; `stop_hook_active` em Stop/SubagentStop; `additionalContext` ≤10.000 caracteres;
Stop/SubagentStop bloqueiam com `{"decision":"block","reason":…}`. Ferramenta de subagente: `Agent`
(renomeada de `Task` na 2.1.63; `Task` segue como alias) com `subagent_type`, `description`, `prompt`, `model`
opcional (https://code.claude.com/docs/en/sub-agents); subagentes podem aninhar por padrão (até 3 níveis) —
por isso o guard bloqueia e o install fixa `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`.
`agent_transcript_path` em SubagentStop não está detalhado na doc: lido se presente, ignorado se não.

## 5. Escada de enforcement por plataforma (honesta)

| Nível | Significado |
|---|---|
| E0 | só prosa |
| E1 | instrução + estado por CLI (`cs-state`) que recusa transição inválida; nada impede escrita fora |
| E2 | detecção mecânica depois do fato: `verify` (git diff × allowed_paths) e `cs-precommit`/CI reprovam |
| E3 | bloqueio antes da execução por hook |

Claude Code: **E3** para Write/Edit/Agent e para Bash com alvo visível; **E2** para escrita feita por programa
arbitrário (`python foo.py`, `npm …`) — o parser não vê o que um programa escreve; o `verify` pega depois.
Cursor, Copilot, Codex: **E1 + E2** (adapters em `.swarm/harness/adapters/`, `cs-precommit` com
`--git-hook`); não instalamos hooks dessas plataformas. Mesmo pacote S3 via `cs-state brief`.

**Instale com as plataformas escolhidas no init**, primeiro em simulação:
`cs.py harness install --platforms claude-code,cursor,copilot,codex --git-hook --dry-run` lista o bloco `outside`
(settings, hook, `specialists.mk`, bloco do `Makefile`, `.git/hooks/pre-commit`); mostre ao usuário e, com o OK,
`cs.py harness install --platforms claude-code,cursor,copilot,codex --git-hook --allow-outside` (sem `--allow-outside`
nada é escrito fora de `.swarm/` — igual ao `emit`). `--git-hook` sempre que o alvo é repositório git. Sem `--platforms`, os adapters de Cursor/Copilot/Codex não
são instalados e essas plataformas ficam só com a prosa do cartão (E0) — sem o usuário saber.

**Garantia por plataforma (o relatório mostra esta tabela).** `cs.py verify` grava
`enforcement: {<plataforma>: hook|instructions}` — `hook` = bloqueio antes da execução (E3); `instructions` =
o agente é instruído e o desvio só é pego depois (E1 + E2: `verify`, `cs-precommit`, CI).

| Plataforma | `enforcement` | Bloqueia antes (hook) | Pega depois | Não garante |
|---|---|---|---|---|
| Claude Code | `hook` | Write/Edit fora do território, despacho sem brief, Bash com alvo visível | escrita por programa arbitrário (`verify`) | o que um programa escreve sem passar pelo guard até o `verify` |
| Cursor | `instructions` | nada | `verify` (git diff × allowed_paths), `cs-precommit` com `--git-hook` | escrita fora do território até o commit/verify |
| Copilot | `instructions` | nada | idem | idem |
| Codex | `instructions` | nada (`sandbox_mode = "read-only"` só no gate) | idem | idem |

## 6. Memória (S5) e autocorreção (§8-bis, §8-duodecies)

BM25 (k1=1,2; b=0,75) sobre knowledge + episodes + lições + `.swarm/facts/*.json5|*.json` (glossary →
term, business_rules → rule), tokenização de identificadores (camel/snake/kebab, acentos, composto),
boost por scope×paths e por kind, stale/archived fora. Índice incremental por fonte (tamanho+mtime) em
`memory/index/`; p95 medido < 200 ms com 10k entradas (teste). Episódio por evento de task (state → mem).
Lições por agente em `state/memory/agents/<a>.json5`: correção humana, review FAIL/NEEDS_SPECIALIST, reject e
verify reprovado, risco de brief (vai para `lead`); dedup Jaccard ≥0,5 conta só ocorrências distintas
(task#tentativa); `count ≥ 2` → `promoted` + proposta em `state/memory/promotions.json5`
(`promoted_to: card-rule|check`); teto 30 ativas (consolidação automática arquiva as menos valiosas); decaimento
20 tasks do agente ou 60 dias → archived; fingerprint mudou → stale; `check` executado no VERIFIED.

## 7. Roteador, sessão, autonomia

`cs-route`: score só do brief (classe, nº paths, LOC, hot_path, invariantes, colisão, ato) → faixa; tabela de
partida sem amostras; Thompson/Beta seedado por delegação com recompensa por tier, veto e exploração; incerteza
relativa; regras fixas (risco/security topo, retry sobe tier, gate ≥ autor). Priors = replay do ledger; só
treina procedência `declarada-no-despacho|medida`; `anular` nunca apaga linha.
`cs-session`: carimbo sha256(board + último hash + HEAD + fase); load ≤30 linhas/≤2.000 tokens; delta quando
não bate; `--check` para approve.3. Autonomia: mandato assinado (também em events.jsonl), recusa aceite verde,
classe risco e orçamento incompleto; escaladas: invariante/congelado escopado, ambiguidade (abstain
spec_ambiguous), mesma rejeição 2×, orçamento, risco descoberto, teste de aceite alterado, conflito de gates,
sem progresso; checkpoint `cs-session save` a cada ACCEPTED; relatório em `state/autonomy-report.json5`. Mandato
ESCALATED não é beco: `cs-state autonomy resume --decision '…'` → ACTIVE (decisão no evento `autonomy.resume`;
a mesma evidência fica em `acknowledged` e não reescala; validador acusa reconhecimento sem evento) ou
`cs-state autonomy stop` → STOPPED.

## 8. Aprovação humana × simulada (approve.2)

`cs.py approve --by <quem> --decision GO|NO-GO [--note "…"]` grava `.swarm/acceptance.json5` com
`approval: human`. Quando não há usuário na sessão (eval, execução autônoma), use
`cs.py approve --by <quem> --decision GO --simulated`: grava `approval: simulated` e o relatório mostra
`GO (simulado)` — nunca apresente uma aprovação simulada como do dono. NO-GO formal é sempre alcançável:
validate não fechou, ou fechou com qualquer agente `nao-especialista` (aceito com motivo ou não — o `verify`
decide NO-GO, ARCHITECTURE §9) → registre `cs.py approve --by <quem> --decision NO-GO --note "<motivo>"`.
A aprovação do roster segue a mesma regra: `cs.py team approve --by <quem>` (humana) ou
`cs.py team approve --by <quem> --simulated` (sem usuário; nunca apresentada como do dono).

| | Humana | Simulada |
|---|---|---|
| Quando | o dono leu o relatório e decidiu | sem usuário na sessão (`[sem usuário]` em `stage check`) |
| Comando | `approve --by <dono> --decision GO` | `approve --by <quem> --decision GO --simulated` |
| `acceptance.json5` | `approval: human` | `approval: simulated` |
| Relatório | `GO` | `GO (simulado)` — o dono ainda precisa aprovar |

## 9. Limitações conhecidas

- Cadeia de hashes sem segredo: detecta edição ingênua; quem reescreve a cadeia inteira por script (fora dos
  guards, ex.: programa arbitrário) não é detectado — mitigado por Bash guard + verify, não eliminado.
- Bash: programas arbitrários podem escrever (E2, não E3); comandos legítimos com `$(…)`/heredoc são bloqueados
  por design (use script em arquivo).
- Ator identificado por `agent_type`: um agente com 2 delegações em voo é bloqueado (1 em voo por agente).
- Lock por `fcntl` (Windows sem lock entre processos). BSD make não testado aqui (macOS `/usr/bin/make` é GNU 3.81).
- A confirmação de classe risco grava a frase informada pelo orquestrador; o motor não prova que o usuário disse.
