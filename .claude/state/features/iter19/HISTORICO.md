# HISTORICO — feature iter19

<!-- APPEND-ONLY: [NOTA] | [PASS] | [REJECT]; escrito pelo feature.py e pelo tech-lead, em série -->

## [NOTA] 2026-10-07T12:27:44-0300 — Abertura da feature iter19
- campanha: campanhas/iter19 (ac.py init; escopo: scripts/harness/engine/*.py, scripts/harness/tests/*.py, scripts/upgrade/*.py, scripts/upgrade/tests/*.py, references/migrations.json5, references/*.md, docs/*.md, assets/templates/*.md, assets/templates/state/*.md, VERSION, README.md)
- tasks: 8 · primeira: 01-TASK-ORACULO
- investigação aprovada (E2):

    # E2 — investigação medida para a iter19 (B-14: estado legível em JSON + chaves em inglês + amend + migração)
    
    Base medida: `local/work/iter20/codebase-specialists` (VERSION 0.10.1). Todos os caminhos abaixo são relativos a essa
    cópia, salvo `campanhas/` (projeto). Só leitura: nada do produto, do estado ou das campanhas foi editado.
    Comando-base do inventário: `grep -rnIE --exclude-dir=__pycache__ 'j5\.|json5' scripts/` → **1324 linhas** (igual ao
    `rg -c` somado). Amostra real: um alvo gerado nesta máquina (nome omitido; 17 itens na árvore, 70 eventos) e um alvo de
    teste temporário (6 itens, 7 eventos).
    
    ---
    
    ## Inventário
    
    ### 1.1 Onde json5 é lido/escrito (linhas por arquivo, `rg -c`)
    Escopo do harness gerado (código copiado ao alvo + quem mexe no `.swarm` do alvo) — **249 linhas**:
    
    | arquivo | linhas | papel |
    |---|---:|---|
    | scripts/harness/engine/tree.py | 34 | itens da árvore: caminhos `*.json5` (tree.py:25, 380-468, 535, 1165, 1407-1472), `render()` (tree.py:60-61), `is_item_file` (tree.py:70), validate (tree.py:1340, 1351, 1359), migrate (tree.py:1481-1530) |
    | scripts/harness/engine/hcore.py | 29 | caminhos de estado (hcore.py:137-174), `write_json5` (hcore.py:229-230), `read_any` (hcore.py:233-238), `load_board`/`save_board` (hcore.py:514-535), máquinas/config/fatos (hcore.py:65-74, 669, 704) |
    | scripts/upgrade/core.py | 35 | PRESERVED/VERIFY (core.py:52-60), state-tree (core.py:820-845), plano (core.py:594-598), run.json5 |
    | scripts/memory/mem.py | 28 | lições `state/memory/agents/<n>.json5`, `promotions.json5`, `stale.json5` (mem.py:9-11, 170-176, 786-797, 871) |
    | scripts/harness/engine/auto.py | 17 | visões do mandato `mandato/plano.vN/relatorio/escalada-*.json5` (auto.py:2916-2960), rascunho/stop-hook (auto.py:121-125, 1887-1899, 3086-3097) |
    | scripts/harness/engine/engine.py | 16 | só referências a machines/team/config/collision (texto) |
    | scripts/harness/engine/selftest.py | 15 | MANIFEST, run.json5, `selftest.json5` (selftest.py:293) |
    | scripts/harness/engine/session.py | 12 | `resume.json5` (modo plano, session.py:35-147), carimbos `state/sessoes/*.json5` (session.py:304, 461-467) |
    | scripts/upgrade/version.py | 10 | migrations.json5 (catálogo do produto) |
    | scripts/harness/install.py | 10 | config.json5, MANIFEST.json5 |
    | scripts/harness/engine/validate.py | 9 | autonomy.json5 (validate.py:176-187) |
    | scripts/harness/engine/state.py | 6 | `--from` brief JSON5 (state.py:432, 484, 581), relatório (state.py:717-720) |
    | scripts/harness/engine/autonomy.py | 6 | autonomy.json5, escalation-*.json5, autonomy-report.json5 (autonomy.py:23-27, 231-232, 385) |
    | scripts/harness/engine/cmds.py | 5 | só texto (machines/team/brief-schema) |
    | scripts/harness/engine/router.py | 4 | routing.json5 (router.py:29-32) |
    | scripts/cs.py | 3 | run.json5 legado |
    | scripts/harness/replace.py | 3 | detecção de harness próprio |
    | scripts/harness/engine/guard.py | 2 | mensagens (guard.py:308, 378) |
    | scripts/harness/engine/j5.py | 1 | o parser |
    | scripts/harness/engine/attest.py | 1 | detecção do board legado (attest.py:77) |
    | scripts/harness/machines.json5, routing.json5, upgrade/cli.py | 1+1+1 | — |
    
    Fora do escopo do harness: **fábrica 495** (probes 105, team 91, panel 75, emit 64, stage 48, verify 43, facts 22,
    scan 21, cslib 11, interview 8, sanitize 7) e **testes 580** (team 116, harness 99, probes 87, stage 74, panel 37,
    emit 37, verify 20, cslib 20, sanitize 21, upgrade 19, memory 16, doctests 13, scan 13, interview 4, facts 4).
    Prova de isolamento: fora de `scripts/harness/`, só `upgrade/core.py` e `memory/mem.py` tocam `state_paths`,
    `events.jsonl`, `load_board` ou `TREE_ZONES` (grep sem outros resultados).
    
    ### 1.2 Arquivos de estado num `.swarm` (modo árvore = o atual; caminhos em hcore.py:132-153)
    | arquivo | natureza | quem escreve |
    |---|---|---|
    | `{backlog,state,archive}/**/epico.json5, sprint.json5, feature.json5, story.json5, tasks/*.json5` | **estado de entidade** (visão materializada da projeção) | tree.materialize (tree.py:325-345) |
    | `.engine/projection.json5` (antigo board) | **estado do motor** (projeção dos eventos) | hcore.save_board (hcore.py:533-535) |
    | `state/sessoes/*.json5` | estado (carimbo de sessão) | session.tree_save (session.py:450-468) |
    | `{state,archive}/mandatos/<id>/{mandato,plano.vN,relatorio,escalada-*}.json5` + `.engine/mandatos/{<id>.rascunho,stop-hook}.json5` | estado do mandato M5 (visões + rascunho/contador) | auto.py:2928-2942, 1899, 3094-3097 |
    | `.engine/autonomy.json5`, `autonomy-report.json5`, `escalation-*.json5`, `selftest.json5` | estado do motor | autonomy.py:27, 232, 385; selftest.py:293 |
    | `state/memory/agents/*.json5`, `state/memory/promotions.json5`, `memory/stale.json5` | estado da memória (cs-mem) | mem.py:754, 797, 871 |
    | `team.json5`, `harness/config.json5`, `run.json5`, `harness/MANIFEST.json5`, `facts/*.json5`, `knowledge/*.json5`, `cards/status.json5`, `emit/manifest.json5` | **config / artefato da fábrica** | cs.py team/init/emit, install.py:154, 209 |
    | `events.jsonl`, `.engine/harness-ledger.jsonl`, `.engine/model-router.jsonl`, `interview.jsonl`, `approvals.jsonl`, `team-approvals.jsonl`, memória `episodes/knowledge/docs.jsonl` | **log append-only** | hcore.append_chained (hcore.py:325-337) e outros |
    
    Footprint real (alvo da máquina): 21 arquivos de item + 4 sessões + 2 em `.engine/` + 6 lições = 33 `.json5` de estado,
    contra 80+ `.json5` de fábrica/config no mesmo `.swarm` (facts 17, probes 40, knowledge 13, stages 6, …).
    
    ## Classificação (as 1324 linhas)
    
    | balde | linhas | o que é |
    |---|---:|---|
    | **MUDA** — estado de entidade/motor (formato → JSON; caminho `.json5`→`.json`) | **77** | tree.py 24, auto.py 13, session.py 12, hcore.py 8, validate.py 7, autonomy.py 6, selftest.py 2, engine.py 2, upgrade/core.py 2, state.py 1 |
    | **LEGADO** — nome `state/board.json5` do board PLANO (só detecção/migração state-tree; fica) | **21** | tree.py 7, upgrade/core.py 6, selftest.py 2, hcore.py:162, guard.py:308, attest.py:77, install.py:354, replace.py:61, mem.py:174 |
    | **NÃO MUDA** — config humana / produto / artefato da fábrica | **117** | upgrade/core.py 27, hcore.py 15, engine.py 14, selftest.py 11, version.py 10, install.py 8, cmds.py 5, state.py 4, mem.py 4, auto.py 3, router.py 3, cs.py 3, tree.py 2, validate.py 2, replace.py 2, guard.py 1, machines/routing/upgrade-cli 3 |
    | **MEMÓRIA** — estado do cs-mem (decisão em Pergunta 2) | **20** | mem.py |
    | **INFRA** — parser e helpers genéricos (`j5.py`, `write_json5`, `read_any`, `_read_json`) | **14** | hcore.py 5, mem.py 3, j5.py, auto.py, router.py, state.py, tree.py, install.py (1 cada) |
    | fábrica (fora do `.swarm` de estado) | **495** | ver 1.1 |
    | testes (seção 5) | **580** | ver 1.1 |
    | **total** | **1324** | 77+21+117+20+14+495+580 |
    
    **CONGELADO (logs JSONL)**: contagem à parte, porque o regex de json5 não os pega: 56 linhas citam `*.jsonl` no
    escopo (events.jsonl 32, docs 6, model-router 4, approvals 4, knowledge 3, harness-ledger 3, episodes 3, outros 5). Nada
    muda neles: a cadeia é `canonical()` com `sort_keys` por linha (hcore.py:197-198, 330-331) e o hash é sobre os bytes da
    linha anterior (hcore.py:320-322, 340-360).
    
    Decisão "não muda" para config: `harness/config.json5` é declarado editável por humano ("protegido: só reinstalação ou
    edição humana fora do agente", install.py:209); `machines.json5` tem 27 linhas de comentário e `migrations.json5` 20 —
    JSON estrito perderia isso. `team.json5` é citado em 181 linhas, quase todas da fábrica. → ficam JSON5.
    
    Método: classificador por regex + 37 atribuições manuais por arquivo:linha (script no scratchpad desta sessão);
    nenhuma linha ficou sem balde.
    
    ## Exclusões
    - **Fábrica (495) e config (117)**: facts/knowledge/probes/team/run/config/machines/routing/migrations/MANIFEST. Não
      são estado do motor e a fábrica não lê estado do harness (1.1).
    - **Board plano legado (21)**: `state/board.json5` só existe em alvo pré-0.7.0; quem chega lá migra por `state-tree`
      (tree.py:1481-1530) antes, ou seja, o formato novo pode nascer depois. Os nomes legados ficam para a detecção.
    - **Valores em português** (não são chaves): `kind: "epico"`, pastas `epicos/`, `state/sessoes/`, `acao: "criado"`.
      B-14 fala de chaves; renomear pasta mexe em `path` de todos os itens e no guard. Fora.
    - **Flags da CLI** `--como/--quero/--para/--criterio/--motivo` (state.py:242, 375): interface, não arquivo. Ficam
      (dá para aceitar aliases em inglês depois).
    - **`resume.json5` em `.swarm/session/`**: só no modo plano (session.py:35, 238); no modo árvore a sessão vai para
      `state/sessoes/`.
    - **Backups** (`.swarm/backups/**`): cópias históricas; não se migram.
    
    ## Achados
    
    **F1 — (a) Ordem alfabética e indentação 1 nascem no serializador próprio.** `j5._dump` ordena com `sorted(obj)`
    (j5.py:124), comprime objeto de ≤3 campos numa linha (j5.py:125) e lista de escalares de ≤100 caracteres numa linha
    (j5.py:132); `dumps` chama `_dump(obj, 1, 0)` = indentação 1 (j5.py:138-139) e põe o comentário de cabeçalho
    (j5.py:140-141). Todo estado passa por aí: `hcore.write_json5` (hcore.py:229-230) e `tree.render` (tree.py:60-61).
    Daí o arquivo de task lido no alvo: `agent` primeiro, `id`/`kind` no meio, `historico` antes de `id`. O
    `emit/j5.py` e o `cslib/json5io.py` têm as mesmas regras (emit/j5.py:5, json5io.py:16), mas são da fábrica. Já é
    determinístico (mesma entrada, mesmos bytes); falta a ORDEM DE LEITURA. Proposta: `hcore.write_json(path, obj, order)`
    com `json.dumps(ordenado, indent=2, ensure_ascii=False)` mais `\n`, ordem por lista fixa por kind e as chaves
    desconhecidas em ordem alfabética no fim, e `historico/history` sempre por último. **NÃO** mexer em `hcore.canonical`
    (hcore.py:197-198, sort_keys): é a base do hash da cadeia e das comparações.
    
    **F2 — (b) Causa do amend não refletido (mecanismo completo).**
    1. `cs-state amend <id> --field acceptance_criteria …` → state.py:448: em modo árvore tenta `_tree_amend`
       (state.py:312-327).
    2. `_tree_amend` devolve None (segue para M2) quando a task JÁ FOI INICIADA (`m2_status` não None e não reaberta,
       state.py:323-325). É o caso da task da SPR-001 (zona `state/`).
    3. Cai em `cmds.amend` (state.py:664-666) → `build` (cmds.py:883-911): `_set_dotted` muda o **objeto M2**
       `board.tasks[]` (cmds.py:889, 913-937) e o evento `task.amend` leva só ops `set`/`append` sobre `ref("task", tid)`
       (cmds.py:903-909). **Nenhuma op `tput`**: o item da árvore (`board.tree[id]`, que materializa o arquivo) não muda.
    4. `materialize` só reescreve itens cujo `board.tree[id]` mudou (tree.py:336-340) ⇒ o arquivo da task continua com o
       `criterios` antigo. A CLI ainda imprime "emenda registrada" (state.py:666).
    5. O espelho M2→arquivo que já existe (`sync_m2_event`, tree.py:648-675) só cobre `SYNC_FIELDS = ("agent", "route")`
       (tree.py:633) e é chamado só por ready/retry/reroute (cmds.py:401, 784, 831). O amend não o chama.
    6. Antes do start, `tree.amend` só aceita `allowed_paths` (`TREE_AMENDABLE`, tree.py:593, 602-604): AC de task não
       iniciada é recusado (falha visível, não silenciosa).
    7. **Efeito colateral latente**: no reopen/restart, `_m2_task` gera a NOVA M2 a partir de `it["criterios"]`
       (tree.py:683-686). O AC removido por amend **volta** na próxima tentativa.
    
    Correção mínima: em `cmds.amend`, quando `tree.item_of_m2(board, tid)` existe e o campo é espelhável
    (acceptance_criteria/allowed_paths/verification_command/title), anexar ao MESMO evento uma op `tput` do item, com o
    mapeamento inverso de tree.py:683-686 (`criterion`→`gherkin`; `verified_by "test:X"`→`test: X`; `"verification_command"`
    ou `"reviewer"` (cmds.py:932)→`test: null`) e uma entrada no histórico `{action: "amend", field, before, after, reason}`,
    igual a `tree.amend` (tree.py:615). Liberar `acceptance_criteria` em `TREE_AMENDABLE` para task não iniciada.
    
    **F3 — (c) Chaves em português hoje e mapa pt→en proposto.** Medido nos 23 itens reais e em tree.py:226-229, 412-447,
    836-851, 1057; leitores fora de tree.py citados.
    
    | pt (hoje) | en proposto | onde vive / quem lê fora de tree.py | precedente |
    |---|---|---|---|
    | `tipo` | `type` | task/story; session.py, state.py:242 (spec) | board plano usava `type` (tree.py:1454) |
    | `como` / `quero` / `para` | `as_a` / `i_want` / `so_that` | task/story; `_m2_task` (tree.py:695); auto.py:1132 (spec) | board plano: `as_a/i_want/so_that` (tree.py:1460; state.py:479) |
    | `criterios[]` {`id`,`gherkin`,`teste`} | `acceptance_criteria[]` {`id`,`gherkin`,`test`} | task/story; `_m2_task` (tree.py:683) | M2 já usa `acceptance_criteria`, o mesmo nome do `--field` do amend |
    | `teste` (topo) / `reproducao` | `proving_test` / `failing_test` | task BUG/FIX; auto.py:1141 | board plano (tree.py:1461) |
    | `motivo` | `reason` | CHORE | — |
    | `aceite` | `acceptance_cmd` | feature (tree.py:406, 622-628) | — |
    | `epico` (campo) / `objetivo` / `metrica` | `epic` / `objective` / `metric` | sprint/épico (tree.py:381, 393, 776) | board plano (tree.py:1408) |
    | `meta` (sprint) | `goal` | sprint (tree.py:393) | board plano `goal` (tree.py:1415) |
    | `reaberta` / `reaberturas[]` | `reopened` / `reopenings[]` | session.py:335, state.py:324 | — |
    | `historico[]` {`acao`,`de`,`para`,…} | `history[]` {`action`,`from`,`to`,…} | auto.py:2775 | — |
    | `closed` {`entregue`,`devolvido`,`metricas`,`origem`} | `closed` {`delivered`,`returned`,`metrics`,`origin`} | session.py; tree.py:837-848, 1046 | — |
    | `metricas` {`tentativas`,`status_m2`,…} | `metrics` {`attempts`,`m2_status`,…} | tree.py | — |
    | carimbo de sessão {`blocos`[{`titulo`,`linhas`}]} | {`blocks`[{`title`,`lines`}]} | session.py:440-467 | — |
    
    **Colisão**: `para` = "so that" na story (tree.py:438) e `para` = "to" no histórico e nos eventos (tree.py:670, 1139).
    Hoje elas não se confundem só porque estão em níveis diferentes do objeto; na tradução por chave cega
    se confundem. O mapa tem de ser por caminho (topo × `history[]`). Os `data` dos eventos (`de/para`, tree.py:674,
    1098-1172) ficam como estão: são log congelado.
    
    Ordem de leitura proposta (B-14 c): `id, kind, type, title, agent, allowed_paths, protected_paths, as_a, i_want,
    so_that, acceptance_criteria, verify_cmd, status/wave/route, created_at, created_by, started_at, closed, m2, aliases,
    path, parent, …(resto em ordem alfabética), history`.
    
    **F4 — (d) Integridade: o que depende do nome `.json5` ou do conteúdo serializado.**
    1. **Cadeia `events.jsonl`**: `prev = sha256(bytes da linha anterior)` (hcore.py:325-337), conferida em `read_chain`
       (hcore.py:340-360). Os eventos trazem o item inteiro nas ops `tput`, com `path: "….json5"` e as chaves em português.
       Medido: 34 de 70 linhas do alvo real citam `.json5` (32 em `ops[][3].path`, 2 em texto livre de
       risks/findings); 6 de 7 no alvo de teste. **Reescrever qualquer linha quebra a cadeia dali em diante ⇒ a migração
       NÃO reescreve eventos.** Precedente que funciona: `tree.migrate` anexa UM evento encadeado `arvore.migrate` com
       `tput` de todos os itens (tree.py:1500-1524; "histórico preservado byte a byte", migrations.json5 0.7.0). Proposta:
       evento `arvore.format` com `tput` de cada item (chaves en, `path` `.json`) e
       `data.paths: {"<antigo>.json5": "<novo>.json"}`. Esse mapa é o que "resolve" as citações antigas em views/find. `apply_ops`
       trata `tput` como substituição opaca (hcore.py:573-575): replay de eventos antigos com chaves pt e o tput final dá a
       projeção nova.
    2. **Projeção**: `event_count`/`last_event_hash` (tree.py:1524) — atualizar no append; nome `projection.json5`
       (hcore.py:137) → `.json`, com leitura que aceite os dois durante a transição.
    3. **validate da árvore**: compara `canonical(arquivo)` × `canonical(item)` (tree.py:1338-1343), o que não depende do
       formato. Mas o campo `_generated_by` (B-14 a) **quebra** essa igualdade se não sair na comparação (ou se não entrar
       no item). Ele substitui o cabeçalho `HEADER` (tree.py:24). `is_item_file` exige `.json5` (tree.py:70): sem aceitar
       os dois sufixos, um `.json5` que sobrar não é acusado como órfão (tree.py:1356-1369). O regex da feature em
       `state/` (tree.py:1351) cita `feature\.json5`.
    4. **Mandato M5**: o nome do pacote de escalada é DADO event-sourced (`"arquivo": "escalada-…json5"`, auto.py:1220,
       dentro de `board.mandatos`). Trocar a extensão exige o mesmo evento de formato (ou resolver o nome ao materializar).
       `validate_files` compara `canonical(j5.load)` (auto.py:2944-2960). O **selo** do mandato é
       `sha256(canonical(PLANO_KEYS))` com chaves pt (auto.py:58, 1555-1560), conferido em auto.py:1616 e assinado com a
       senha do humano (senha.py:78). **Traduzir as chaves do mandato invalida o selo de todo mandato aprovado** (ver P1).
    5. **autonomy**: assinatura sobre `canonical` de chaves já em inglês (autonomy.py:31-33), conferida contra o evento
       `autonomy.start` (validate.py:176-185). Só muda o formato.
    6. **Carimbo de sessão**: `sha256(canonical(board) | last_event_hash | HEAD | fase)` (session.py:58). A projeção muda
       ⇒ o carimbo muda uma vez depois da migração (retomada "produto-mudou"). É esperado; vale documentar.
    7. **Atestado / pre-commit (B-13)**: o atestado nunca cobre estado (attest.py:34-41). No `check-diff`, tudo que fica sob
       `.swarm/state/`, `.swarm/memory/`, as zonas, `events.jsonl`, `INDEX.md` e `.engine/` passa se e só se
       `validate.run` passa (guard.py:609-616). No modo árvore, todo arquivo migrado cai nesses prefixos ⇒ **a migração
       não esbarra no pre-commit, desde que o validate termine verde**. O resto do upgrade (motor, emit) continua passando
       pelo atestado.
    8. **Upgrade**: `VERIFY` roda `harness validate --strict` só DEPOIS das ações (upgrade/core.py:52, 941-956). B-14 pede
       também ANTES; falta isso. `PRESERVED_PATHS` (upgrade/core.py:58-59) cita `state/board.json5` e `state/events.jsonl`
       (caminhos do modo PLANO) e `memory`. **No modo árvore, `.swarm/events.jsonl` não está protegido pelo snapshot de
       preservados** (lacuna pré-existente). Um kind novo precisa entrar em `EXPLICIT_KINDS` (upgrade/core.py:60, 980)
       para poder tocar a memória, e em `KINDS` (version.py:23). O padrão a copiar é `do_state_tree` (upgrade/core.py:820-845),
       que chama `cs-state migrate …` (o motor é o único escritor).
    
    **F5 — (e) O parser j5 próprio NÃO pode ser removido.** `import j5` em 15 módulos fora de teste: 9 do harness
    (auto, autonomy, hcore, router, selftest, session, state, tree, validate) + install.py + mem.py + 6 do emit (que usa a
    cópia `emit/j5.py`, diferente da do motor). Dependências que ficam em JSON5: `machines.json5` (27 comentários, hcore.py:74),
    `routing.json5` (router.py:31), `harness/config.json5` (hcore.py:669, guard.py:378), `team.json5` (hcore.py:619-628),
    `run.json5` (selftest.py:196, 208), `MANIFEST.json5` (selftest.py:37), `facts/*.json5` (hcore.py:704), brief `--from`
    (state.py:484, 581). O que sai: o uso de `j5.dumps` para ESTADO (`write_json5` → `write_json`). O `j5.load` continua
    lendo `.json` (JSON estrito é subconjunto do subconjunto aceito), o que serve para ler os dois formatos durante a
    transição. Não use `read_any` (hcore.py:233-238) para o estado novo: ele aplica `json.loads` estrito em `.json`, e um
    teste que adultere com `j5.dumps` (test_cobertura_maquinas.py:623-628 via `save_board`) passaria a gerar ilegível.
    
    **F6 — `cs-state show` não existe.** Os subcomandos da árvore são `TREE_CMDS` (state.py:437). `find` existe (state.py:281,
    344; tree.py:1207). `show <id>` entra em TREE_CMDS, lendo `tv.get(id)` (aceita aliases, tree.py:115-123) e
    renderizando Markdown.
    
    ## Enforcement existente (e o que quebra)
    
    - **Suíte do produto** (`scripts/harness/tests`, 266 `def test`; `scripts/upgrade/tests`, 8):
      - amend: test_machines.py:193-202 (M2: o amend vira evento), test_d102_d103_extra.py:169-187, test_iter18_a_escopo.py:28-30, 71
        (dica de amend), test_workflow_e2e.py:344 (amend de `wave`). **Nenhum teste confere que o amend chega ao ARQUIVO do
        item** (o B-14 e) — lacuna.
      - serialização: nenhum teste de ordem nem de bytes para o j5 do motor. O teste do JSON5 é o do cslib
        (cslib/tests/test_json5io.py, 20 linhas), que é da fábrica.
      - upgrade de estado: upgrade/tests/test_upgrade.py (19 linhas json5); test_swarm_dir.py (28; board legado e
        preservação, test_swarm_dir.py:558-647).
      - **Quebram com o caminho novo** (literais de estado `.json5`): test_iter20_atestado.py:99 (`.engine/projection.json5`)
        e test_workflow_e2e.py:761 (`session/resume.json5`, modo plano: fica se o modo plano não mudar). As 10 linhas de
        board legado em test_swarm_dir.py e as 3 em test_guards.py:58, 112-113 ficam (o nome legado fica). Testes que leem
        estado por `hcore.state_paths` e `j5.load` (test_cobertura_maquinas.py:296-302, 623-628) seguem funcionando se os
        caminhos vierem de `state_paths`.
    - **Oráculos congelados** (`campanhas/*/oraculo`; o portão só roda os passados em `--oraculo`, portao.sh:11, 28). Teto
      por regex largo de linhas que citam caminho de estado/árvore e chaves pt:
      iter10/test_estado_arvore.py **58 caminhos + 11 chaves pt** (o maior; lê os arquivos de item pelo nome);
      m5/test_mandato.py 18 + 3 visões do mandato + **48 chaves pt** (alvo/objetivo/criterios do mandato); iter9/test_swarm_dir.py 13
      (board legado); iter11/test_pacotes_entrada.py 12; iter12/test_upgrade_real.py 10 + 4; iter16/test_uso_real.py 9;
      iter10/test_upgrade_u1_u2.py 7; iter13/test_menores.py 7 + 3; iter15/test_iter15.py 6; iter14/test_senha_mandato.py 1 + 6;
      iter20/test_iter20.py 3; harness-dev 2 + 3; iter18 1; iter11/sanitize 2. Rodados de novo sem `oracle change`,
      iter10 e m5 quebram.
    - **Oráculo da 0.10.1** (iter20/test_iter20.py, 54 linhas de upgrade): cobre atestado + pre-commit depois do upgrade. É
      o guarda-costas para "não esbarrar no B-13" e deve rodar no portão da iter19 (`--oraculo campanhas/iter20/oraculo:test_iter20`).
    - **Docs que citam caminhos/chaves de estado**: 56 linhas em 15 arquivos (docs/ROADMAP-rodada-seguinte.md 19,
      references/ARCHITECTURE.md 8, docs/02-harness.md 7, docs/AUTONOMIA-DESENHO.md 6, references/harness.md 4,
      docs/05-sessao-e-retomada.md 3, outros 9 com 1 cada).
    
    ## Decisões já tomadas na E1 (aprovada pelo founder: "ok")
    
    1. Mandato M5: só formato (`.json`, ordem, indent 2); chaves pt do mandato ficam (selo com senha é hash delas,
       auto.py:58, 1555-1616). Tradução do mandato vira item novo no BACKLOG.
    2. Memória do cs-mem fora da iter19 (fica `.json5`; mem.py:202-209 já lê os dois formatos).
    3. Migração por evento novo encadeado (`arvore.format`, precedente `arvore.migrate`, tree.py:1500-1524), com
       `data.paths` mapeando cada `.json5` antigo para o `.json` novo; idempotente; dry-run por `run_build(dry_run=True)`.
    
    ## Estimativa de tamanho
    - **Código do produto: ~14 arquivos.** hcore.py (caminhos, `write_json`, ordem), tree.py (caminhos, chaves, render,
      validate, amend, `migrate state-format`, show), state.py (show, migrate, amend), cmds.py (amend → tput do item),
      session.py, autonomy.py, auto.py (só nomes e formato das visões e do escalada), validate.py, selftest.py, guard.py
      (mensagem), upgrade/core.py (kind novo, `EXPLICIT_KINDS`, validate antes, plano), upgrade/version.py (`KINDS`),
      references/migrations.json5 (0.11.0) e VERSION. j5.py não muda.
    - **Testes**: 2 edições na suíte do produto (test_iter20_atestado.py:99 e, se o modo plano mudar,
      test_workflow_e2e.py:761) + testes novos (migração de um `.swarm` realista com ≥30 eventos, amend refletido, bytes
      iguais em 2 serializações, `show`, aliases pt na leitura).
    - **Oráculos**: `oracle change` provável em iter10/test_estado_arvore (e m5, se as visões do mandato mudarem de nome)
      quando forem re-rodados.
    - **Docs**: ~15 arquivos, 56 linhas.
    - Total: **~16 arquivos de produto + ~15 de docs + testes novos**.

## [PASS] 01-TASK-ORACULO — 2026-10-07T12:48:13-0300
- status: DONE · gate: PASS
- oráculo congelado 1083cc4a985e; base 11/39 nos 2 Pythons
