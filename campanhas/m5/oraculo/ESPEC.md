# ESPEC — oráculo campanha-M5: modo autônomo `mandato` (máquina M5) sobre a árvore de estado

Fonte: `codebase-specialists/docs/AUTONOMIA-DESENHO.md` (§5–§12, 28 cenários AUTO-*), `docs/PONTOS-DO-FOUNDER.md` (B11,
D6: "o autônomo novo nasce com os 28 cenários e cobertura 100%") e a interface da árvore FIXADA em
`campanha-iter10/oraculo/ESPEC.md` (o mandato opera tasks da árvore).
Oráculo: `test_mandato.py` (52 testes, unittest puro, Python 3.9+, repositórios temporários). Base: `base.txt`. Cobertura 100% de M5 (D6): mudança oficial em `mudanca-oficial/` (patch nos oráculos congelados
`test_cobertura_maquinas.py` + `test_maquinas_vivacidade.py` + `m5_cenarios.py` novo; `PORQUE.md`).
Quem implementa **não edita** o oráculo. Onde o desenho era ambíguo, as escolhas estão em §3 para o founder conferir.

Princípio do founder aplicado: **tudo que é mecânico é script** — próxima ação, ondas, verify, accept, close de task,
integração, progresso, orçamento, parada, escalada e retomada são decididos pelo motor (`cs-auto tick`); o modelo só
executa nós de julgamento (PLAN/REPLAN, DISPATCH, REVIEW, REFLECT, FINAL_REVIEW). **Portões humanos continuam humanos**:
o mandato nunca aprova, emenda, resolve, encerra nem aborta por conta própria.

## 0. Como o oráculo observa (nada de mock)
- Conferido contra a árvore REAL (codebase-specialists 0.7.0, commit 3127bf9): `new/start/dispatch/submit/verify/review/
  accept/close/abstain` com ids `FEA-nnn/nn`, avulsa `aaaa-mm-dd-nn` em `state/tasks/`, `events.jsonl` na raiz de `SD`,
  `state/sessoes/`, `archive/` espelhado, `ask` → `ASK-n`, `validate --strict`. Única divergência: critério de US precisa
  ser TESTÁVEL (`Dado … Quando … Então …|<test-id>`; texto curto é recusado como "vago") — o oráculo passou a usar esse
  formato também nos `--criterio` do mandato (nenhum requisito do mandato mudou).
- `cs-auto`  = `python3 <skill>/scripts/harness/engine/auto.py --root <alvo> [--actor X] ...` (subprocesso)
- `cs-state` = `python3 <skill>/scripts/harness/engine/state.py --root <alvo> ...` (árvore iter10 + M2)
- guard = `python3 <skill>/scripts/harness/engine/guard.py <modo>` com payload de hook no stdin e `CLAUDE_PROJECT_DIR`
  (modos usados: `pre-write`, `pre-bash`, `pre-agent`, `stop`, `session-start`, **`pre-compact` (novo)**)
- Pasta de estado `SD` = `cslib.paths.STATE_DIR` (basename; senão `.swarm`). Skill: `$CS_SKILL_DIR`, senão
  `~/.claude/skills/codebase-specialists`.
- Eventos: `SD/events.jsonl` (layout iter10); o oráculo também lê `SD/state/events.jsonl` (legado) — soma os dois.
- Repo de teste: git com `src/billing/total.py`, `src/users`, `src/shared`, `tests/test_billing.py` (verde; quebra se
  `total()` mudar), `spec/feature.md`, `docs/decisoes/`, um teste de aceite por critério `accept/test_ac_<n>.py`
  (verde só quando o arquivo do critério existe e contém `OK`); `SD/team.json5` (dev-billing e dev-users com
  `src/shared/**` em comum, qa `tests/**`, architect `docs/decisoes/**`, po, gates reviewer e security);
  fato `rule.billing.cents` com escopo `src/billing/**` (invariante citada); `SD/harness/config.json5` com
  `frozen_paths: ["src/shared/frozen/**"]` e `max_files_per_task: 3`. Preparação pela árvore iter10:
  `cs-state init` → `new sprint --meta` → `start SPR` → `new feature --sprint --aceite` → `start FEA` → commit.
- O "modelo" é o `Driver` do oráculo: lê `cs-auto tick --json` e executa só a ação pedida (§2.4). Toda ação humana passa
  por `cs-auto <ato> ... --by founder` + `$CS_HUMAN_PROOF_ARGS` (vazio hoje; a frase-senha é de outra campanha).

## 1. Cenários → testes
| Cenário (desenho §12) | Teste(s) | Negativo incluído |
|---|---|---|
| AUTO-LIVE | `TestAutoLive.*` (5) | estado sem saída; terminal com saída; inalcançável; AWAITING_HUMAN/PAUSED terminal; M2 ESCALATED/ABSTAINED sem retomar/trocar/descartar |
| AUTO-START-1 | `TestPropose.test_start1_*`, `test_proposta_*`, `test_approve_*` | alvo inexistente, spec inexistente, teste de aceite inexistente, aceite já verde, classe pergunta, 2º mandato aberto, emenda sem motivo, abort/approve não humanos, approve com aceite que ficou verde |
| AUTO-START-2 | `TestPropose.test_start2_*` | `--nos 1`, classe pequena/trivial e plano de 1 nó → "use task avulsa" |
| AUTO-PLAN-1 | `TestPlano.test_plan1_*` (2) | ciclo, critério sem nó, nó fora do território, nó > `max_files_per_task`, plano > orçamento |
| AUTO-PLAN-2 | `TestPlano.test_plan2_*` | — (ondas `[[01],[02,03],[04]]` e 02+03 em voo juntos) |
| AUTO-PLAN-3 | `TestPlano.test_plan3_*` (2) | arquivo comum e par `do_not_parallelize` nunca em voo juntos |
| AUTO-HAPPY | `TestFluxoFeliz.*` | revisão final antes do verde; revisão final pelo autor |
| AUTO-RETRY | `TestFalhaERecuperacao.test_retry_*` | reflexão sem citação; evidência que não é do sinal externo |
| AUTO-SAME-FAIL | `TestFalhaERecuperacao.test_same_fail_*` | 3ª tentativa com o mesmo agente |
| AUTO-REPLAN-1 | `TestReplano.test_replan1_*` | replano sem evidência; replano que mexe em nó ACCEPTED |
| AUTO-REPLAN-CAP | `TestReplano.test_replan_cap_*` | — |
| AUTO-REGRESS | `TestReplano.test_regress_*` | replano de regressão sem nó FIX citando o teste |
| AUTO-ESC-LOCAL | `TestEscalada.test_esc_local_*` | AWAITING_HUMAN antes de esgotar o executável; piloto resolvendo sozinho |
| AUTO-ESC-CITE | `TestEscalada.test_esc_cite_*` | escalar por mera citação de invariante |
| AUTO-ESC-RESOLVE | `TestEscalada.test_esc_resolve_*` (6: retomar, trocar-agente, emendar, descartar-ramo, encerrar, abortar) | resolve não humano, opção inexistente, sem `--decision`, agente sem território |
| AUTO-HACK | `TestEscalada.test_hack_*` (2) | subagente edita aceite/spec (Write e Bash); aceite alterado por fora (hash) |
| (escalada manual) | `TestEscalada.test_escalada_manual_*` | condição inválida |
| AUTO-BUDGET-SOFT | `TestOrcamento.test_budget_soft_*` | despacho em WRAPPING_UP |
| AUTO-BUDGET-TIME | `TestOrcamento.test_budget_time_*` | pausa de 8 h e lacuna de 8 h não contam |
| AUTO-USD | `TestOrcamento.test_usd_*` | `spend` autodeclarado não muda custo medido nem dispara parada |
| AUTO-NOPROG | `TestOrcamento.test_noprog_*` | escalar por falta de progresso; descartar ABSTAINED |
| AUTO-RESUME | `TestJanelas.test_resume_*` (2: órfã sem diff → requeue; com diff → verify) | — |
| AUTO-COMPACT | `TestJanelas.test_compact_*` | tick não idempotente |
| AUTO-STOPHOOK | `TestJanelas.test_stophook_*` (+ checagens em ESC-LOCAL/encerrar/pausas) | Stop bloqueando em AWAITING_HUMAN/PAUSED/terminal; anti-loop escalando |
| (pausas e stop humano) | `TestJanelas.test_pausa_*`, `test_stop_humano_*` | stop não humano |
| AUTO-SPRINT | `TestSprintEFaixas.test_sprint_*` | 2 features em state/; task da 2ª antes de a 1ª fechar |
| AUTO-LANE | `TestSprintEFaixas.test_lane_*` | avulsa que colide com o DAG ativo |
| AUTO-RISK | `TestSprintEFaixas.test_risk_*` | risco sem portões; despacho do nó de risco antes do humano |
| AUTO-TAMPER | `TestIntegridade.test_tamper_*` | mandato.json5 / plano.v1.json5 editados à mão; Write do modelo nesses arquivos |
| AUTO-E2E | `TestIntegridade.test_e2e_*` | relatório com verificação "pulada calada" |
| portão humano | `TestPortaoHumano.*` | piloto aprovando em PROPOSED; ato humano via Bash (principal e subagente); `--by` não humano |
| H-1 (comando do motor sem shell) | `TestH1ComandoDoMotor.*` (3) | `PYTHONPATH=src …` saindo 127; exit real não propagado; aceite verde visto como vermelho |
| instalação/prosa (D12) | `TestInstalacao.*` (2) | template que manda "seguir next até REPORTING" ou o modelo propor orçamento |
| cobertura 100% de M5 (D6) | OFICIAL: `test_cobertura_maquinas` (+14 cenários `m5_*`, `TestM5Presente`) e `test_maquinas_vivacidade.test_mandato_m5_presente_e_espera_nunca_tranca` via `mudanca-oficial/` | aresta/guarda (transição × guarda) nunca exercitada ou nunca recusando |

Regras congeladas respeitadas (não contraditas): ESCALATED/ABSTAINED de M2 não terminais e com retomar/trocar/descartar
(re-afirmado em AUTO-LIVE; no mandato, nó congelado = delegação ESCALATED e a saída é sempre decisão humana; ABSTAINED
nunca é descartado pelo motor — NOPROG verifica); nenhum atalho para ACCEPTED (todo nó passa por dispatch → submit →
verify do motor → review de gate → accept do motor; sob escalada global o que estava em voo é verificado, não aceito);
gates humanos só humanos (approve/amend/resolve/stop/abort exigem `--by` humano e o guard bloqueia o modelo de rodá-los);
`waive-verify`/`legacy-ack` nunca aparecem num fluxo do mandato; legado `cs-state autonomy` não é tocado (os oráculos
congelados ainda o exercitam).

## 2. Interfaces FIXADAS

### 2.1 Máquina M5 (fonte única: `scripts/harness/machines.json5`)
Mora em `machines.json5 → machines.mandato` (DENTRO de `machines`, como o desenho §5), portanto sob a vivacidade e a
cobertura oficiais (estendidas pela mudança oficial; ver decisão 1).
Campos: `field: "state"`, `states` (= exatamente os 12 abaixo), `initial: "PROPOSED"`, `terminal: [DONE, HANDED_BACK,
ABORTED]`, `awaiting_human: [AWAITING_HUMAN]`, `transitions: {nome: {from: [...], to, guards: [...]}}`.
Estados: PROPOSED, CHARTERED, PLANNING, RUNNING, INTEGRATING, REPLANNING, AWAITING_HUMAN, PAUSED, WRAPPING_UP, DONE,
HANDED_BACK, ABORTED. `to: "="` = mesmo estado; **`to: "^"` = volta ao estado de onde veio** (gravado em
`data.anterior` do evento que levou a PAUSED/AWAITING_HUMAN).

| Transição | from → to | guardas (mínimo; nomes fixos) |
|---|---|---|
| propose | ∅ → PROPOSED | target_exists, class_allowed, spec_present, acceptance_executable, acceptance_red, no_open_mandate, not_trivial |
| approve | PROPOSED → CHARTERED | by_human, acceptance_red |
| amend | PROPOSED, AWAITING_HUMAN → PROPOSED | by_human, reason_present |
| abort | PROPOSED, AWAITING_HUMAN → ABORTED | by_human, reason_present |
| plan | CHARTERED → PLANNING | — |
| plan_accept | PLANNING → RUNNING | not_trivial, dag_acyclic, dag_covers_acceptance, nodes_in_territory, nodes_fit_horizon, plan_within_budget, waves_computed, lessons_consulted |
| tick | RUNNING → = | — |
| wave_closed | RUNNING → INTEGRATING | no_delegation_in_flight |
| integrate_ok | INTEGRATING → RUNNING | regression_green, pending_nodes |
| integrate_replan | INTEGRATING → REPLANNING | replan_trigger, replans_left |
| integrate_done | INTEGRATING → DONE | acceptance_all_green, final_review_pass |
| next_feature | INTEGRATING → PLANNING | acceptance_all_green, final_review_pass, next_feature_queued |
| replan_accept | REPLANNING → RUNNING | replan_cites_evidence, accepted_nodes_untouched, dag_acyclic, dag_covers_acceptance, nodes_in_territory, nodes_fit_horizon, plan_within_budget, waves_computed, plan_diff_recorded |
| escalate | PLANNING, RUNNING, INTEGRATING, REPLANNING → AWAITING_HUMAN | escalation_condition, package_recorded |
| resolve_resume | AWAITING_HUMAN → ^ | by_human, choice_in_package, decision_present |
| resolve_reroute | AWAITING_HUMAN → ^ | by_human, choice_in_package, decision_present, new_agent_valid |
| resolve_drop | AWAITING_HUMAN → ^ | by_human, choice_in_package, decision_present |
| pause | PLANNING, RUNNING, INTEGRATING, REPLANNING → PAUSED | in_flight_marked |
| resume | PAUSED → ^ | stamp_matches |
| wrap_up | PLANNING, RUNNING, INTEGRATING, REPLANNING, AWAITING_HUMAN, PAUSED → WRAPPING_UP | wrap_trigger |
| hand_back | WRAPPING_UP → HANDED_BACK | no_delegation_in_flight, report_generated, open_items_returned |

Guardas extras são permitidas (precisam ser vistas OK); transições extras precisam ser exercitadas pelos cenários.

### 2.2 Eventos e recusas (o que a cobertura OFICIAL mede)
- Implementação observável pelo oráculo congelado: toda transição de M5 com entidade passa por
  `engine.transition(ctx, kind, eid, tname, a)` com `hcore.KIND_MACHINE[kind] == "mandato"` (mesmo `engine.commit`,
  nada de motor paralelo); toda guarda de M5 é registrada em `engine.GUARDS` (decorador `@guard`) e a recusa imprime o
  problema no stderr. Alternativa recusada = `engine.transition` cujo `Refused` o motor captura. `propose` é transição
  de CRIAÇÃO (`from: []`): evento `mandato.propose` com `data.guardas`; recusa com `guarda <nome>:` no stderr.
- Toda transição de M5 = evento encadeado em `events.jsonl` com `type: "mandato.<transição>"`, `entity: "MAN-nnn"` e
  `data: {de: <origem | null no propose>, para: <destino>, guardas: [<guardas avaliadas OK>], ...}`.
- Recusa pela CLI: exit 1 e uma linha `guarda <nome>: <problema>` no **stderr** por guarda que recusou.
- Recusa interna (o motor tenta e escolhe outra saída): o evento escolhido grava `data.guardas_recusadas:
  [{transicao, guarda, problema}]`. Obrigatório na saída da INTEGRATING: o motor avalia `integrate_done`,
  `integrate_ok`, `integrate_replan` (nessa ordem) e grava as recusadas no evento vencedor (ou no `escalate`).
- Campos de evento lidos: `approve.data.assinatura` (sha256 hex); `amend.data.assinatura_anterior` (= a assinatura
  vigente); `wrap_up.data.gatilho` ∈ {`budget_soft`, `budget_hard`, `no_progress`, `stop_humano`, `criterios_orfaos`,
  `encerrar`}; eventos de resolve/amend/abort/wrap_up por decisão humana contêm o texto do `--decision`.
- Cobertura (D6, oficial): critério do `test_cobertura_maquinas` (aresta transição × origem; cada (transição, guarda)
  vista OK e vista RECUSANDO). Exclusões M5 (`m5_cenarios.EXCLUSOES_M5`, só recusa, 14 chaves, ativas apenas quando
  `machines.mandato` existe): plan_accept/{waves_computed, lessons_consulted}, replan_accept/{waves_computed,
  plan_diff_recorded}, wave_closed/no_delegation_in_flight, integrate_replan/replan_trigger,
  next_feature/next_feature_queued, escalate/package_recorded, pause/in_flight_marked, resume/stamp_matches,
  wrap_up/wrap_trigger, hand_back/{no_delegation_in_flight, report_generated, open_items_returned}.

### 2.3 `cs-auto` — subcomandos
Códigos: 0 sucesso; 1 recusa semântica (acionável); 2 só argparse/estado incoerente. `--json` = JSON puro no stdout.
| Comando | Quem | Contrato |
|---|---|---|
| `propose (--feature FEA-nnn \| --sprint SPR-nnn) --spec P --objetivo T --nos N [--criterio 'AC-n\|texto\|<test-id ou comando>']... [--regressao CMD] [--classe feature\|risco\|…] [--portao <glob>]... [--rigor lean\|standard\|paranoid]` | modelo/motor | imprime `MAN-nnn`; → PROPOSED com orçamento DERIVADO (despachos ≥ N, tentativas ≥ despachos, replanos, minutos; todos > 0). Critério: 3º campo com espaço = comando; senão test-id unittest (resolve para arquivo; inexistente → `acceptance_executable`). QUALQUER critério já verde → `acceptance_red` citando o id. `--nos <2` ou classe pequena/trivial → recusa com "task avulsa". `--sprint`: critérios = `--aceite` de cada feature (um `AC-1` por feature) |
| `approve --by H [--orcamento despachos=,tentativas=,replanos=,minutos=,usd=]` | HUMANO | assina; grava baseline (aceite por critério + regressão, com `output_sha256`) e o HEAD (ponto seguro) |
| `amend --by H --reason R [--orcamento ..]` | HUMANO | → PROPOSED; assinatura encadeada |
| `abort --by H --reason R` · `stop --by H --reason R` | HUMANO | → ABORTED · → WRAPPING_UP (`gatilho: stop_humano`) |
| `resolve --choice retomar\|trocar-agente\|emendar\|descartar-ramo\|encerrar\|abortar --by H --decision D [--agent A] [--escalada ID]` | HUMANO | retomar → `resolve_resume` (nó volta a BRIEFED com a decisão no brief; a condição não reescala); trocar-agente → `resolve_reroute`; emendar → `amend`; descartar-ramo → `resolve_drop` (nós congelados DROPPED, critérios órfãos); encerrar → `wrap_up`; abortar → `abort` |
| `tick [--json]` | piloto | UMA ação (§2.4); faz sozinho tudo que é mecânico; idempotente sem ação do modelo; texto ≤ 30 linhas com o objetivo |
| `status [--json \| --brief]` | qualquer | §2.5; sem mandato: `{"mandato": null}` exit 0; `--brief` ≤ 20 linhas com objetivo, estado e o comando do 1º passo (`cs-auto …`) |
| `plan add-node --id ID --tipo US\|BUG\|FIX --agent A --title T --path P... [--deps a,b] --cobre AC-1[,AC-2] [--verify-cmd C] [--teste <test-id>]` | modelo | só SINTAXE (exit 0); todas as regras são guardas do `submit` |
| `plan edit-node --id ID [...]` · `plan reset` · `plan submit [--motivo M --evidencia REF]` | modelo | `edit-node` também só sintaxe (editar nó ACCEPTED é recusado no `submit`, guarda `accepted_nodes_untouched`); `submit` dispara `plan_accept` (PLANNING) ou `replan_accept` (REPLANNING); recusa = exit 1 + `guarda X:`; `reset` descarta o rascunho |
| `reflect <task> --texto T --evidencia REF` | modelo | REF tem de ser um `evidencia[].ref` do tick (ou `arquivo:linha` existente); sem isso exit 1 |
| `orphan <task>` | modelo | trata órfã: sem diff nos paths → requeue (novo despacho, conta tentativa); com diff → verify, sem redespacho |
| `final-review --by G --verdict PASS\|FAIL --findings F` | gate | só em INTEGRATING com aceite 100% verde; G gate e ≠ autores dos nós (senão `final_review_pass`); FAIL → replano |
| `escalate --condicao C --evidencia REF [--no ID]` | modelo | escalada suave sinalizada (ex.: `material_ambiguity`); condição fora do enum → `escalation_condition` |
| `pause [--motivo M]` · `resume` | motor/modelo/humano | PAUSED ↔ estado anterior; pause com delegação em voo marca `orphan_watch` |
| `spend --usd X` | — | recusado (1) ou registrado só como `autodeclarado`; nunca muda `medido` nem dispara parada |
| `report [--json]` | qualquer | §2.6 |

### 2.4 `tick --json`
`{mandato, estado, frente: "SPR-nnn › FEA-nnn", feature, objetivo, acao, alvo, no, agente, model, paths, comando,
progresso: "aceite x/y …", orcamento, por_que, evidencia: [{tipo: E1|E2|evento, ref, ...}], criterios, licoes, escalada,
opcoes}` (campos conforme a ação). `acao` ∈ {PLAN, REPLAN, DISPATCH, IDLE_WAIT, REVIEW, REFLECT, ANSWER_ORPHAN,
FINAL_REVIEW, RESUME, REPORT, ASK_HUMAN, FIM}:
- PLAN traz `feature`, `criterios`, `licoes` (lista; busca de memória feita pelo motor). DISPATCH traz `alvo` (task da
  árvore), `no`, `agente`, `model`. REVIEW/FINAL_REVIEW trazem `agente` (gate). REFLECT/REPLAN trazem `evidencia`
  (REPLAN de regressão cita o test-id que quebrou). PROPOSED e AWAITING_HUMAN → `ASK_HUMAN`; PAUSED → `RESUME`;
  terminal → `FIM`. Nenhuma ação ≠ ASK_HUMAN tem `comando` com ato humano.
- O motor faz no próprio tick: `plan`, criar/`start` das tasks dos nós na feature, verify (roda o `--verify-cmd` do nó,
  padrão = `--regressao`), accept, close da task, `wave_closed`, integração (regressão + aceite por critério), start/
  close de feature (sprint), wrap-up/hand-back e escaladas detectadas. **Não existe ação VERIFY nem WRITE_BRIEF.**

### 2.5 `status --json`
`{mandato, estado, alvo, feature_ativa, objetivo, pasta (relativa ao alvo), classe, rigor,
orcamento: {despachos|tentativas|replanos|minutos: {usado, limite}, usd: {medido, autodeclarado, limite}},
aceite: {verdes, total}, baseline: {aceite: [{id, verde, output_sha256}], regressao: {exit, output_sha256}, head},
plano: {versao, ondas: [[ids]], nos: [{id, task, agente, paths, deps, cobre, estado (status M3 da task), congelado}]},
congelados: [ids], escaladas: [{id, tipo: dura_global|dura_local|suave, condicao, nos, opcoes, pacote, aberta}],
licoes_candidatas: [{task, no, texto, sinal}]}`. `plano.nos[].task` existe desde o `plan_accept`.
Condições fixadas: `acceptance_changed` (tentativa ou alteração de spec/aceite/verificador → dura_global),
`frozen_write` (nó que ESCREVE em `frozen_paths` → dura_local, congela nó + descendentes), `risk_gate` (nó que casa
`--portao`), `replans_exhausted` e `material_ambiguity` (suave). Citar invariante não é condição.
Opções do pacote (guarda `choice_in_package`): escalada com nó → as 6; escalada SEM nó (`material_ambiguity` sem `--no`,
`replans_exhausted`) → retomar, emendar, encerrar, abortar (sem trocar-agente/descartar-ramo); `acceptance_changed`
com o arquivo de aceite/spec ALTERADO (hash ≠ assinatura) → sem `retomar` (só emendar, encerrar, abortar).

### 2.6 `report --json`
`{mandato, resultado: DONE|HANDED_BACK|ABORTED, criterios: [{id, verde, output_sha256}], verificacoes: [{nome, executada,
output_sha256?, motivo?}], devolvidos, criterios_orfaos, revisao_final: {by}, restaurar (comando git do ponto seguro,
em ABORTED)}`. Toda verificação prevista e não executada tem `motivo`.

### 2.7 Arquivos, hooks, relógio, instalação
- Pasta do mandato (`status.pasta`, sob `SD/state/mandatos/MAN-nnn/` enquanto ativo): `mandato.json5` (visão do último
  evento), `plano.v<N>.json5` (com `anterior_sha` e `motivo`), `escalada-<ts>.json5` (`pacote`), relatório. Editados à
  mão → `cs-state validate` exit 1 citando o arquivo; o guard bloqueia Write do modelo neles.
- Nós abertos no HANDED_BACK voltam ao `SD/backlog/` (arquivo com o título do nó e motivo).
- `guard.py stop`: bloqueia (`{"decision":"block","reason": <ação + alvo/comando>}`) em estado de trabalho com ação
  pendente; nunca em AWAITING_HUMAN, PAUSED ou terminal; 3 bloqueios seguidos sem transição de M5/M2 → `pause`.
- `guard.py session-start`: PAUSED → `resume`; injeta objetivo + próximo comando `cs-auto …`.
- `guard.py pre-compact` (novo): `pause` + checkpoint (`cs-session save` → novo `SD/state/sessoes/*.json5`); exit 0
  sem mandato. `guard.py pre-bash`: bloqueia (2) `cs-auto approve|amend|resolve|abort|stop` do principal e de
  subagente (inclusive `SD/bin/cs-auto` e `python3 …/auto.py`); `cs-auto tick` do principal passa.
- `CS_NOW=<ISO-8601 UTC>`: relógio do motor (auto.py, state.py, guard.py) para eventos e minutos ativos.
- `install.py`: `ENGINE_FILES` com `auto.py`, `BINS` com `cs-auto`, `HOOKS` com `("PreCompact", …, "pre-compact", …)`.
  Templates: `feature-autonoma.md` cita `cs-auto propose` e `cs-auto tick`, sem "até REPORTING" nem "Proponha o
  orçamento"; `orchestrator.md` cita `cs-auto tick`.

### 2.8 Regras mecânicas fixadas
- Ondas = camadas topológicas × coloração (arquivo comum, par `do_not_parallelize`, mesmo agente); ids em ordem estável.
- `nodes_fit_horizon`: nº de paths do nó ≤ `config.max_files_per_task` (padrão 5). `plan_within_budget`: nós ≤ despachos
  restantes. `dag_covers_acceptance`: todo critério em `cobre` de ≥1 nó. Ordem de classe de M2
  (`require_kinds_before_dev`) não se aplica a nós do mandato (decisão 9).
- Retry: verify reprovado → REFLECT (reflexão ancorada) → retry com achados + reflexão no brief; aceito após retry →
  lição candidata. Mesma falha 2× (mesmo comando + saída normalizada) → reroute para outro agente do território ou
  REPLANNING; nunca 3ª tentativa com o mesmo agente.
- Integração: regressão vermelha vs baseline ou aceite sem avanço com DAG esgotado ou nó ABSTAINED/BLOCKED → replano
  (se houver replanos; senão escalada suave `replans_exhausted`). Replano de regressão exige nó `--tipo FIX --teste
  <test-id que quebrou>`. Nós ACCEPTED são imutáveis no replano. No replano, `dag_covers_acceptance` exige que todo
  critério ainda VERMELHO seja coberto por ≥1 nó não ACCEPTED (replano que não ataca o vermelho é recusado).
- Orçamento: `budget_soft` quando qualquer dimensão atinge ≥ 80% do limite (o despacho que atinge já está em voo e
  fecha) → WRAPPING_UP sem despacho novo (M2 `dispatch` recusa); 100% idem. Minutos = só tempo ativo (pausas e
  lacunas longas não contam). Custo = só medido.
- Sem progresso: integrações seguidas sem aumentar aceite verde e sem nó novo ACCEPTED → um replano; persistindo →
  WRAPPING_UP (`no_progress`), nunca escalada.
- Sprint: uma feature em `state/` por vez; o motor fecha a atual (DoD + revisão final) antes de iniciar a próxima.
- Consulta (`cs-state ask`) durante o mandato é permitida e conta 1 despacho; avulsa cujo `allowed_path` colide com o
  DAG ativo é recusada (no `new` ou no `start`, citando o path ou o MAN).

### 2.9 Execução de comandos pelo motor (defeito H-1)
`engine.run_cmd` (e tudo que roda verify-cmd, `--aceite`, critério-comando e `--regressao`) executa via shell
(`/bin/sh -c`) com `cwd` = raiz do alvo, para QUALQUER comando: atribuição de variável (`PYTHONPATH=src python3 -m …`),
`&&`, aspas e pipes funcionam, e o exit code REAL é propagado (0, 3, 4, 7, 1, 127 nos casos do oráculo). Hoje (0.7.0)
`PYTHONPATH=src python3 -m unittest …` vira execve("PYTHONPATH=src") → 127: o verify reprova código certo e um aceite
verde parece vermelho (o `check` de feature aceita o 127 como "aceite vermelho"). O oráculo prova por `engine.run_cmd`
(subprocesso), por `cs-state verify` de uma task e por `cs-state check` de uma feature.

## 3. Decisões do escritor do oráculo (para o founder conferir)
1. **Onde mora M5** (revisto a pedido do integrador): DENTRO de `machines.machines`, como o desenho. A 1ª versão a
   punha no topo para não avermelhar o `test_cobertura_maquinas` congelado — recusado por contornar o oráculo e tirar
   a M5 da vivacidade. Agora a mudança oficial (`mudanca-oficial/`, aplicar com `patch -p0` em `~/.claude/skills/`)
   ESTENDE os dois oráculos congelados à M5 sem afrouxar asserção existente; medido: no código atual 128/128 antigos
   seguem verdes e só os 16 testes novos de M5 falham (produto ausente); com a M5 do §2.1 injetada, a vivacidade passa
   e duas M5 quebradas (AWAITING_HUMAN terminal; sem emendar/abortar) são reprovadas. O teste de cobertura que existia
   neste oráculo foi removido (a medida é a oficial).
2. **12 estados**, não 11 (o resumo do desenho diz 11; a tabela §5.1 lista 12). Valeu a tabela.
3. **Destinos múltiplos viraram transições nomeadas**: `resolve` → `resolve_resume|resolve_reroute|resolve_drop`
   (+ `amend`, `wrap_up`, `abort` para emendar/encerrar/abortar); `resume` e as três `resolve_*` usam `to: "^"`
   (volta ao estado de origem — retomar uma escalada do PLANNING volta ao PLANNING). `integrate_done` vai direto a DONE
   (a revisão final é a guarda `final_review_pass`, com o mandato esperando em INTEGRATING).
4. **Transição nova `next_feature`** (INTEGRATING → PLANNING) para o mandato de sprint; o desenho não tinha como ir da
   feature 1 para a 2.
5. **Escalada local não muda o estado** enquanto há nó executável: fica em `escaladas` (aberta) com o ramo congelado;
   o mandato só vai a AWAITING_HUMAN quando nada mais roda (AUTO-ESC-LOCAL, AUTO-RISK). Nó congelado = delegação M2
   ESCALATED (saída só por decisão humana).
6. **Critério já verde recusa o propose** (qualquer um, não só "todos"): critério vazio é mandato vazio.
7. **Verify do nó ≠ aceite do mandato**: o nó roda o próprio `--verify-cmd` (padrão: regressão); o aceite do mandato é
   medido na INTEGRATING. Um nó que cobre um critério ainda dependente de outros nós não é reprovado por isso.
8. **WRITE_BRIEF e VERIFY não são ações**: o brief nasce do `add-node` (+ decisão humana/reflexão no retry, compostas
   pelo motor); verify/accept/close são do motor. Ação desconhecida reprova o tick.
9. **`require_kinds_before_dev` (PO antes do dev) não vale para nós do mandato**: a spec + critérios assinados pelo
   humano cumprem o papel do produto; o oráculo planeja sem nó de PO.
10. **Guardas sem caminho legal de recusa** entram como exclusões M5 só de "vista RECUSANDO" (lista em §2.2), com
    motivo cada, como as exclusões do oráculo congelado; continuam exigidas "vistas OK". Cobertura por (transição ×
    guarda), igual às outras máquinas — por isso fixei quando cada opção falta no pacote (`choice_in_package`) e que o
    replano precisa atacar o critério vermelho (`dag_covers_acceptance` no replano).
11. **Orçamento derivado**: o oráculo não fixa os coeficientes (sem fonte no desenho); exige só despachos ≥ nós,
    tentativas ≥ despachos e limites > 0, e que só o humano os troque (`approve/amend --orcamento`).
12. **80% conta no despacho que o atinge**: com 5 despachos, o 4º é feito e fecha; o 5º nunca.
13. **Sem progresso**: o oráculo não fixa k; exige ≥1 replano antes do encerramento, menos replanos que o teto e
    `gatilho: no_progress` sem escalada.
14. **Órfã**: `ANSWER_ORPHAN` → `cs-auto orphan <task>`; a decisão diff×paths é do motor (sem diff = requeue, com diff
    = verify sem redespacho).
15. **Humano**: `--by <humano>` (não orquestrador/agente/gate do time) + guard pre-bash; a frase-senha da campanha
    paralela entra por `$CS_HUMAN_PROOF_ARGS` sem mudar este arquivo. O oráculo NÃO testa a frase.
16. **Relógio de teste** `CS_NOW` em todo o motor (único jeito mecânico de provar "8 h de pausa não contam").
17. **FIX de regressão** (`--tipo FIX --teste <test-id>`) no replano: o motor preenche o `fixes` exigido pela árvore
    (iter10) com a referência da regressão (o oráculo não lê `fixes` desse nó).
18. **Fora do oráculo** (não testado aqui): consolidação de lições no DONE (candidatas → ativas com ≥2 confirmações),
    `diario.json5`, model do verificador ≥ autor, revisão "cega", custo medido pelo router × tabela de preço, regra
    "plataformas sem hook = semi-autônomo", rigor lean/paranoid além do aceite do flag.
