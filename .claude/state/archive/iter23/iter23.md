# iter23 — Fluxo da árvore — descartar e emendar task não iniciada, sprint que fecha, uma sprint aberta por épico (e descarte de sprint), DoR na criação, sprint ↔ story na árvore, textos emitidos com `new`, auto-memória do Claude Code e versão visível no alvo

## Resumo
0.13.0 — fluxo da árvore sem beco sem saída, para os defeitos D1–D6 que a cobaia .NET reproduziu depois
da 0.12.2: `drop <id> --reason` de task e sprint nunca iniciadas (archive DROPPED); `amend` dos campos do DoR em task
não iniciada; sprint fecha com tasks DROPPED; uma sprint aberta por épico (new, start, move); DoR estático e área
reservada já no `new task` (e `--dry-run`); `plan <story> --sprint` por referência e `sprint plan` em árvore recusa
apontando os comandos certos; textos emitidos e Makefile com `new`/`plan`/`drop` (alvo `new-epic`); auto-memória do
Claude Code (`~/.claude/projects/<slug>/memory/**`) liberada só ao agente principal, sem porta de hardlink;
`cs-state version` e `version` no MANIFEST; upgrade 0.13.0 (harness + emit) que APONTA itens presos com o comando de
descarte/emenda, sem alterá-los, e mostra erro em vez de "nada preso" quando não consegue ler. Oráculo 16/41 → 41/41.

## Critérios de aceite
### CA-01 — descartar task da árvore não iniciada
DADO uma task da árvore nunca iniciada (com ou sem DoR
  completo), QUANDO o dono roda `cs-state drop <id> --reason <txt>`, ENTÃO ela vai para archive/ como DROPPED com o
  motivo no histórico, sai do board e do `next`, e `validate --strict` segue OK; sem `--reason` recusa; task iniciada
  continua pelo fluxo atual.
  Prova: `cd campanhas/iter23/oraculo && python3 -m unittest test_iter23.TestCA01`

### CA-02 — completar o DoR antes do start
DADO uma task da árvore não iniciada que falha no DoR, QUANDO o dono roda
  `cs-state amend <id> --field <campo>` para motivo, fixes, teste, reproducao, verify_cmd ou como/quero/para, ENTÃO o
  arquivo da task e o histórico refletem a emenda e o `start` passa a aceitar; task iniciada mantém as regras atuais.
  Prova: `cd campanhas/iter23/oraculo && python3 -m unittest test_iter23.TestCA02`

### CA-03 — sprint fecha com tasks descartadas
DADO uma sprint cujas tasks estão fechadas ou DROPPED, QUANDO o dono
  roda `cs-state close <sprint> --summary <txt>`, ENTÃO a sprint fecha; com qualquer task aberta (não fechada nem
  DROPPED) continua recusando e lista quais.
  Prova: `cd campanhas/iter23/oraculo && python3 -m unittest test_iter23.TestCA03`

### CA-04 — uma sprint aberta por épico, e descarte de sprint
DADO uma sprint aberta (não fechada) num épico, QUANDO
  se cria ou inicia outra sprint no mesmo épico, ENTÃO o motor recusa citando a aberta; e uma sprint vazia não
  iniciada pode ser descartada com `cs-state drop <SPR> --reason <txt>`.
  Prova: `cd campanhas/iter23/oraculo && python3 -m unittest test_iter23.TestCA04`

### CA-05 — DoR estático na criação
DADO um `cs-state new task` com allowed_path em área reservada do harness, ou
  sem os campos que o DoR do tipo exige, QUANDO roda o `new` (e o `new --dry-run`), ENTÃO recusa antes de criar
  qualquer item, citando o que falta; com os campos certos cria como hoje. (Partes que executam teste — BUG que
  precisa falhar — continuam no start.)
  Prova: `cd campanhas/iter23/oraculo && python3 -m unittest test_iter23.TestCA05`

### CA-06 — sprint ↔ story/task na árvore
DADO uma sprint e uma story e uma task da árvore, QUANDO o dono vincula
  com o comando da árvore (`cs-state plan <id> --sprint <SPR>`), ENTÃO a sprint passa a referenciar o item (a story
  continua dentro da feature), o board e o `next` mostram o vínculo, e o fechamento da sprint considera esses itens;
  `cs-state sprint plan` em modo árvore funciona sobre os itens da árvore ou recusa apontando o comando certo.
  Prova: `cd campanhas/iter23/oraculo && python3 -m unittest test_iter23.TestCA06`

### CA-07 — textos emitidos mandam o comando certo
DADO um alvo em modo árvore emitido pela skill, QUANDO se
  varrem CLAUDE.md, orchestrator.md, os cartões, a skill /plan-sprint e os alvos do Makefile, ENTÃO não há
  `cs-state add epic|feature|story`; todo comando de criação/planejamento citado executa com sucesso num alvo em modo
  árvore.
  Prova: `cd campanhas/iter23/oraculo && python3 -m unittest test_iter23.TestCA07`

### CA-08 — upgrade 0.13.0 aponta itens presos
DADO um alvo 0.12.x com tasks não iniciadas que não passam no DoR
  novo, QUANDO roda `cs.py upgrade` e `upgrade --apply`, ENTÃO o plano/relatório lista esses itens com o comando de
  descarte/emenda, sem alterá-los; VERSION 0.13.0 com a migração no catálogo; oráculos anteriores inteiros verdes.
  Prova: `cd campanhas/iter23/oraculo && python3 -m unittest test_iter23.TestCA08`

### CA-09 — auto-memória do Claude Code liberada ao principal
DADO o agente principal de um alvo, QUANDO escreve
  (Write/Edit) em `~/.claude/projects/<slug do próprio projeto>/memory/<arquivo>.md`, ENTÃO o guard permite; a mesma
  escrita por SUBAGENTE, ou na memória de OUTRO projeto, ou em qualquer outro caminho fora da raiz segue recusada.
  Prova: `cd campanhas/iter23/oraculo && python3 -m unittest test_iter23.TestCA09`

### CA-10 — versão instalada visível no alvo
DADO um alvo instalado ou atualizado pela skill, QUANDO o dono roda
  `cs-state version` (ou lê o MANIFEST.json5 do harness), ENTÃO vê a versão da skill que instalou o harness, igual ao
  VERSION da skill e ao `skill_version` do run.json5.
  Prova: `cd campanhas/iter23/oraculo && python3 -m unittest test_iter23.TestCA10`

## Linha do tempo
- 2026-10-13T20:15:06-0300 · inicio E0
- 2026-10-13T20:15:23-0300 · proposta E1
- 2026-10-13T20:16:03-0300 · aprovacao E1
- 2026-10-13T20:16:43-0300 · proposta E2
- 2026-10-13T20:17:04-0300 · aprovacao E2
- 2026-10-13T20:17:37-0300 · proposta E3
- 2026-10-13T20:18:11-0300 · aprovacao E3
- 2026-10-13T20:18:42-0300 · proposta E4
- 2026-10-13T20:20:55-0300 · aprovacao E4
- 2026-10-13T20:21:03-0300 · proposta E5
- 2026-10-13T20:21:20-0300 · aprovacao E5
- 2026-10-13T20:21:20-0300 · abertura abertura
- [NOTA] 2026-10-13T20:21:20-0300 — Abertura da feature iter23
- [PASS] 01-TASK-ORACULO — 2026-10-13T20:35:35-0300
- [NOTA] 02-TASK-MOTOR-ARVORE — 2026-10-13T20:37:23-0300
- [REJECT] 02-TASK-MOTOR-ARVORE — 2026-10-13T21:08:50-0300
- [PASS] 02-TASK-MOTOR-ARVORE — 2026-10-13T21:26:53-0300
- [NOTA] 03-TASK-EMISSAO — 2026-10-13T21:26:58-0300
- [NOTA] 04-TASK-UPGRADE-VERSAO — 2026-10-13T21:26:58-0300
- [REJECT] 04-TASK-UPGRADE-VERSAO — 2026-10-13T21:44:08-0300
- [PASS] 03-TASK-EMISSAO — 2026-10-13T22:10:22-0300
- [PASS] 04-TASK-UPGRADE-VERSAO — 2026-10-13T22:10:22-0300
- [NOTA] 05-TASK-QA — 2026-10-13T22:10:35-0300
- [REJECT] 05-TASK-QA — 2026-10-13T23:07:10-0300
- [REJECT] 03-TASK-EMISSAO — 2026-10-13T23:07:10-0300
- [PASS] 03-TASK-EMISSAO — 2026-10-14T19:45:29-0300
- [PASS] 05-TASK-QA — 2026-10-14T19:45:29-0300
- [PASS] 06-TASK-REVIEW — 2026-10-14T19:47:56-0300

## Tasks
| id | entrega | tipo | grupo | status | gate |
|---|---|---|---|---|---|
| 01-TASK-ORACULO | Oráculo da iter23 (CA-01..CA-10), escrito por agente separado | ORACULO | — | DONE | PASS |
| 02-TASK-MOTOR-ARVORE | drop/amend de task não iniciada, sprint, DoR na criação e plan na árvore | CORRECAO | G1 | DONE | PASS |
| 03-TASK-EMISSAO | textos emitidos e docs com os comandos da árvore | CORRECAO | G2 | DONE | PASS |
| 04-TASK-UPGRADE-VERSAO | 0.13.0, upgrade que aponta itens presos | CORRECAO | G3 | DONE | PASS |
| 05-TASK-QA | Portão e oráculos, CA a CA | QA | — | DONE | PASS |
| 06-TASK-REVIEW | Revisão isolada da feature | REVIEW | — | DONE | PASS |

### Handoff 01-TASK-ORACULO
- Oraculista: Claude Code · general-purpose · opus (rh-oraculista-01-TASK-ORACULO-1), agente separado; não abriu a cópia do corretor.
- Arquivos: campanhas/iter23/oraculo/{ESPEC.md, test_iter23.py (41 testes: 25 D, 16 R), medir.py, base.txt}.
- Base reproduzida pelo tech-lead: 16/41 (D 0/25, R 16/16) em python3 3.13.3 e /usr/bin/python3 3.9.6; D falham por asserção.
- Calibração: mutação A (versão/catálogo/MANIFEST/textos) passa só as D correspondentes; mutação B (liberar toda escrita fora da raiz) quebra 5/6 R do CA-09.
- Congelado: oracle freeze 9580e553cc47 (4 arquivos); oracle verify intacto. Escopo por snapshot: só os 4 arquivos. Privacidade 0.
- Limites: slug do Claude Code INFERIDO (todo [^A-Za-z0-9] → '-', sobre o realpath); CA-06 exige id no sprint.json e a story sob a sprint no board; CA-03 só com DROPPED; CA-08 conta o allowed_path reservado como item preso (9 itens).

### Handoff 02-TASK-MOTOR-ARVORE
- Executores: ciclo 1 general-purpose · sonnet (motor: tree/state/guard/hcore + test_iter23_arvore 26 testes); complemento sonnet (validate.py conta board["tree"]; fixture iter19 com --motivo — D-33); ciclo 2 general-purpose · opus (auto-memória recusa hardlink nlink>1, fail-closed).
- Mudança oficial do oráculo (D-33): item() traduz as chaves en do disco; oráculo 049a727fe975.
- Escopo por snapshot: só os arquivos permitidos (views.py sem mudança); projeto vivo intocado. Privacidade 0.
- Régua (tech-lead): suíte harness 417 OK (16 skips pré-existentes) em python3 e /usr/bin/python3; oráculo iter24 OK nos 2; oráculo iter23 16/41 → 25/41 nos 2 (CA-05, CA-06, CA-09 inteiros; CA-04 3/4; CA-10 2/5).
- Pendente de outras tasks (verificado pelo revisor como NOT_RUN de legado): CA-01..CA-04 e CA-10 "atualizado" usam alvo 0.12.x atualizado e só passam com a migração 0.13.0 (task 04); MANIFEST version (task 03). Confirmar no portão.
- Revisores: ciclo 1 general-purpose · opus APPROVED com 1 achado de segurança (hardlink na auto-memória) tratado como bloqueante ⇒ ciclo 2; ciclo 2 opus APPROVED (sem findings). Independência: instâncias distintas.
- Limites: `plan <task> --sprint` mantido (move a task); "por referência" só para story; DoR estático só no `new task`; checagem de território inteiro segue no start; drop de sprint só em backlog e sem item aberto; slug da auto-memória inferido (todo [^A-Za-z0-9] → '-', realpath); TOCTOU do hook PreToolUse.

### Handoff 03-TASK-EMISSAO
- Executores: ciclo 1 general-purpose · sonnet (render/templates/install MAKE_TARGETS + MANIFEST version/docs 02,06/references/harness + test_iter23_emit 5 testes); complemento sonnet (D-34: platforms.py descrição do /plan-sprint; ARCHITECTURE.md :355/:367).
- Escopo por snapshot: só os arquivos permitidos; projeto vivo intocado. Privacidade 0.
- Régua completa (tech-lead, cópia com 02+03+04): 17 suítes × python3 e /usr/bin/python3 VERDE (emit 68, doctests 19); oráculo iter23 41/41 nos 2 (CA-07 3/3, CA-10 5/5).
- Revisor: general-purpose · opus, instância isolada · APPROVED. Ressalva MENOR: alvo em board PLANO (legado) perde `make add-*`/`sprint-plan` na reinstalação e os textos emitidos mandam `cs-state new`, que o motor recusa em modo plano apontando `cs-state migrate state-tree` (não silencioso; alvo novo nasce em árvore).
- Limites: alvos antigos do Makefile só mudam num alvo instalado depois da migração 0.13.0 (ação harness+emit).
- Ciclo 2 (QA): executor opus — alvo de Makefile `new-epico` → `new-epic` (nome antigo proibido pela iter15/D-07; D-35) em install.py, test_iter23_emit, docs 02/06, references/harness e ARCHITECTURE; iter15 voltou às 4 falhas do HEAD. Portão final VERDE.

### Handoff 04-TASK-UPGRADE-VERSAO
- Executores: ciclo 1 general-purpose · sonnet (VERSION 0.13.0; catálogo to 0.13.0 harness+emit; stuck_items/render_stuck só leitura; docs/09; README); ciclo 2 general-purpose · opus (falha silenciosa: erro ≠ "nada preso"; DoR que levanta vira item; aviso em layout legado).
- Escopo por snapshot: só os arquivos permitidos; projeto vivo intocado. Privacidade 0.
- Régua: completa VERDE (34/34) + reexecução depois do ciclo 2: upgrade 32 OK (7 skip) e doctests 19 nos 2 Pythons; oráculo iter23 41/41 nos 2 (CA-01..04 e CA-08 inteiros com a migração).
- Revisores: ciclo 1 sonnet CHANGES_REQUESTED (3 MENOR de falha silenciosa ⇒ ciclo 2); ciclo 2 sonnet APPROVED com sondas reais (corrompido ⇒ erro visível; sem estado/board plano ⇒ "não verificados"; idempotente por hash).
- Ressalvas MENOR: o teste do DoR que levanta confere só o texto do snippet (o revisor provou o comportamento por sonda e deixou receita de teste de comportamento); árvore sem events.jsonl diz "rode cs-state init" (conselho enganoso).

### Handoff 05-TASK-QA
- QA 1 (sonnet): REJECT — iter10 e iter15 vermelhos. Tech-lead: base limpa (git archive HEAD) ⇒ 22+4 pré-existentes (B-61), 8 novas ⇒ D-35: mudança oficial do oráculo iter10 (oraculista opus separado: patch + PORQUE em campanhas/iter10/oraculo/mudanca-oficial/) e 03 ciclo 2.
- Re-QA (sonnet): matriz 41/41 nos 2 Pythons e comparação D-35 com 0 regressões; NOT_RUN da metade 3.9 (Mac em suspensão). Concluída pelo tech-lead: portão com os antigos (VERMELHO só por pré-existentes; harness 3.9 2/417 instável, reexecutado 417/417) e portão final sem iter10/iter15 VERDE + FIM nos 2 Pythons; oracle verify intacto.
- Limites: o oráculo iter10 não tem ledger nesta máquina (sem freeze/oracle change); a mudança oficial está nos arquivos versionados e entra no commit da feature.

### Handoff 06-TASK-REVIEW
- Revisão da feature: Claude Code · general-purpose · opus, instância nova · APPROVED; fluxo da cobaia .NET simulado ponta a ponta; matriz CA-01..10 PASS no FEATURE.md. MENOR: recusa do new sprint sugere drop de sprint já iniciada; PRÉ-EXISTENTE: sprint com tasks BRIEFED exige aceitar/escalar antes de fechar.

## Como a feature nasceu
### E0 — Pré-condição · CONCLUÍDA 2026-10-13T20:15:06-0300
- Demanda: "vamos já resolver os problemas que a cobaia informou (D1–D6 da cobaia .NET + B-59, B-60); recriar a iter23 a partir da criação suspensa"
- Próxima: E1 — Analisar a demanda

### E1 — Analisar a demanda · CONCLUÍDA 2026-10-13T20:16:03-0300
- Produzido: problema enunciado; FEATURE-ID iter23
- Itens aprovados: 1: B-48/B-49/B-50 fora (próxima feature, B-50 P0); 2: B-41 só principal, só ~/.claude/projects/<slug>/memory/**; mantidos: B-38 fora, sprint agrupa por referência, upgrade só aponta
- Aprovação: "ok"
- Sha: 561304ace04f40fc0c4b4cccb1e0573d8a2748f0b15701e8be6b3a811d9ff52f
- Próxima: E2 — investigação medida

### E2 — Investigação medida · CONCLUÍDA 2026-10-13T20:17:04-0300
- Produzido: investigação medida F1-F15 (F12 descartado)
- Medido: 13 pontos da suspensa revalidados (0 linhas de diff nos arquivos da árvore desde 92f5cf2); +3 achados (F13 sprint sem drop, F14 guard fora da raiz, F15 versão invisível); 9 linhas emitidas com add
- Aprovação: "ok"
- Sha: 72ab02506fe625929463b97c2af113a1d6e397e901751769abfde3ea1e9ecd9a
- Próxima: E3 — FEATURE.md

### E3 — FEATURE.md (Bloco A) · CONCLUÍDA 2026-10-13T20:18:11-0300
- Produzido: FEATURE.md com CA-01..CA-10; contrato PASS
- Aprovação: "ok"
- Sha: b9a01fb9f00c68d931f83b9ce949e16ae4f002fa530ebc851aa67ab6e6a88af4
- Próxima: E4 — tasks

### E4 — Tasks (Bloco B) · CONCLUÍDA 2026-10-13T20:20:55-0300
- Produzido: 6 tasks; CA-01..CA-10 cobertos; contrato PASS
- Aprovação: "ok"
- Sha: a9f6fd72332daa2535f67f08d9ec5e27094dc4a7a13967d4ea6baefdc53ccc71
- Próxima: E5 — abertura

### E5 — Abertura · CONCLUÍDA 2026-10-13T20:21:20-0300
- Produzido: plano de abertura
- Aprovação: "ok"
- Sha: 1dc11060cd448d3c04714dd2b2719cb37423b2a3b5d56dce1665e51e4af594c2
- Próxima: oráculo por agente separado

### Abertura · 2026-10-13T20:21:20-0300
- Campanha: campanhas/iter23
- Tasks: 6 · primeira: 01-TASK-ORACULO
- Próxima: oráculo pelo agente separado → oracle freeze → script-aprovacao.sh (founder)

## Campanha
- campanha: campanhas/iter23 · etapa do motor: concluida · rodada: 0
- critério de parada: Oráculo iter23 100% verde (CA-01..CA-10) em python3 e /usr/bin/python3; oráculos iter10, iter13, iter15, iter16, iter18, iter19, iter20, iter21, iter22 e iter24 inteiros verdes; suítes do produto e harness-dev verdes; 0 `def` removido; VERSION 0.13.0.
- escopo: scripts/harness/engine/tree.py, scripts/harness/engine/state.py, scripts/harness/engine/cmds.py, scripts/harness/engine/views.py, scripts/harness/engine/guard.py, scripts/harness/engine/hcore.py, scripts/harness/install.py, scripts/harness/tests/test_iter23_*.py, scripts/emit/render.py, scripts/emit/tests/test_iter23_*.py, assets/templates/orchestrator.md, assets/templates/product-process.md, assets/templates/plan-sprint.md, scripts/upgrade/core.py, scripts/upgrade/tests/test_iter23_*.py, references/migrations.json5, references/harness.md, docs/02-harness.md, docs/06-referencia-cli.md, docs/09-upgrade.md, VERSION, README.md

## Oráculo
- `campanhas/iter23/oraculo/ESPEC.md`
- `campanhas/iter23/oraculo/test_iter23.py`
- `campanhas/iter23/oraculo/medir.py`
- `campanhas/iter23/oraculo/base.txt`

## Decisões técnicas
- `drop` de task não iniciada reaproveita `_to_archive`/`feature_drop`; task iniciada segue a máquina M2 (inalterada).
- `TREE_AMENDABLE` ganhou os campos do DoR (DOR_FIELDS); o disco segue com chaves em inglês (B-14) — o oráculo foi
  corrigido por mudança oficial (D-33), não o contrato de disco.
- `validate --strict` conta `board["tree"]` (árvore sem M2 não é "estado vazio").
- DoR estático só no `new task`; a checagem de território inteiro segue no `start` (senão `new story` padrão quebraria).
- Slug da auto-memória: realpath do projeto com todo [^A-Za-z0-9] → '-' (inferido de 94 pastas reais; não lido da
  fonte do Claude Code). Hardlink (nlink>1) dentro da memory/ é recusado (fail-closed).
- `stuck_items` roda o motor DA SKILL por subprocesso `-I -c` só leitura e devolve lista | {"absent"} | {"error"}.
- Oráculos iter10/iter15 (vermelhos no HEAD desde antes) ficam fora do portão; critério D-35: nenhum teste que passa
  no HEAD limpo passa a falhar, por comparação teste a teste nos 2 Pythons. Mudança oficial do oráculo iter10 (6
  testes: `new` recusa a task inválida).

## Aprendizados
- Oráculo antigo fora do portão esconde dívida: a iter10 e a iter15 estavam vermelhas no HEAD e ninguém via; base
  limpa por `git archive HEAD` + diff teste a teste separou 26 pré-existentes de 8 novas em minutos.
- Oráculo que lê o disco tem de falar o contrato de disco (chaves en): o falso vermelho custou um ciclo e uma
  mudança oficial.
- Exceção nova no guard deve passar pelas MESMAS checagens que o caminho normal (o ramo da auto-memória pulou a de
  hardlink e reabria a porta da 0.12.2) — revisão em opus pegou por leitura de código.
- "Falhou ⇒ []" é falha silenciosa; o revisor de sonnet pegou e o ciclo 2 separou erro, ausência e nada.
- Registrar as etapas do motor (orçamento, base, calibração) ao longo da execução evitou a trava do B-17 no
  fechamento; o `campanha.py fechar` ainda grava a execução final sem nota — a sequência foi feita pelo `ac.py`.
- Mac em suspensão no meio do portão produziu 2/417 falhas espúrias em 3.9 (execuções concorrentes na mesma cópia);
  reexecutar isolado antes de concluir.
- Hook de aprovação dá falso positivo em `python3 -` com heredoc; usar Edit/awk.
- Custo medido: sonnet 12 despachos, opus 11 (+ revisões); 0 NOT_RUN.

## Arquivos da feature
- `scripts/harness/engine/tree.py`
- `scripts/harness/engine/state.py`
- `scripts/harness/engine/cmds.py`
- `scripts/harness/engine/views.py`
- `scripts/harness/engine/guard.py`
- `scripts/harness/engine/hcore.py`
- `scripts/harness/tests/test_iter23_arvore.py`
- `scripts/harness/engine/validate.py`
- `scripts/harness/tests/test_iter19_estado.py`
- `scripts/emit/render.py`
- `scripts/emit/tests/test_iter23_emit.py`
- `scripts/harness/install.py`
- `assets/templates/orchestrator.md`
- `assets/templates/product-process.md`
- `assets/templates/plan-sprint.md`
- `docs/02-harness.md`
- `docs/06-referencia-cli.md`
- `references/harness.md`
- `scripts/emit/platforms.py`
- `references/ARCHITECTURE.md`
- `scripts/upgrade/core.py`
- `scripts/upgrade/tests/test_iter23_upgrade.py`
- `references/migrations.json5`
- `docs/09-upgrade.md`
- `VERSION`
- `README.md`

## Aceite da Feature
### Aceite QA — ACCEPT
### Aceite Review — APPROVED
<!-- fechar-feature:archive-completo -->
