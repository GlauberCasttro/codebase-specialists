# HISTORICO — feature iter27

<!-- APPEND-ONLY: [NOTA] | [PASS] | [REJECT]; escrito pelo feature.py e pelo tech-lead, em série -->

## [NOTA] 2026-10-19T18:19:38-0300 — Abertura da feature iter27
- campanha: campanhas/iter27 (ac.py init; escopo: scripts/harness/engine/state.py, scripts/harness/engine/auto.py, scripts/harness/engine/router.py, scripts/harness/engine/tree.py, scripts/harness/engine/hcore.py, scripts/harness/engine/session.py, scripts/harness/engine/guard.py, scripts/harness/cli.py, scripts/harness/install.py, scripts/harness/replace.py, scripts/cs.py, scripts/upgrade/cli.py, scripts/upgrade/core.py, scripts/emit/cli.py, scripts/emit/apply.py, scripts/emit/platforms.py, scripts/harness/tests/*.py, scripts/emit/tests/*.py, scripts/stage/tests/test_iter4_stages.py, scripts/upgrade/tests/*.py, scripts/doctests/tests/test_commands_parse.py, assets/templates/*.md, assets/templates/state/*.md, SKILL.md, MODO-DE-USO.md, README.md, VERSION, references/harness.md, references/platforms.md, references/stages.json5, references/ARCHITECTURE.md, references/migrations.json5, docs/*.md, docs/fases/*.md, docs/exemplos/*.md)
- tasks: 8 · primeira: 01-TASK-ORACULO
- investigação aprovada (E2):

    # E2 — Investigação medida
    
    Medido em 2026-10-19 no HEAD 9e908e0 (0.14.0), com `grep -n`/`grep -c` sobre `git ls-files`. "Produto" = SKILL.md,
    MODO-DE-USO.md, scripts/, references/, assets/, docs/, evals/ (o que o `/package` leva). Lição B-70c aplicada: medi
    o produto, os oráculos antigos (campanhas/*/oraculo/) e os doctests (scripts/doctests/).
    
    ## Inventário
    
    **U1 — Definições de flag pt no argparse (código de produto, sem testes): 35 linhas, 5 arquivos, 28 nomes.**
    - `scripts/harness/engine/state.py` (cs-state, árvore) — 10 linhas: 226 `--objetivo`, 227 `--metrica`, 229 `--meta`,
      230 `--epico`, 235 `--aceite`, 246 `--teste` (laço `for k in ("fixes","teste")`), 248 `--criterio`, 252 `--avulsa`
      (new task), 269 `--avulsa` (move), 278 `--devolver` (close). 9 nomes.
    - `scripts/harness/engine/auto.py` (cs-auto) — 19 linhas: 3150 `--objetivo`, 3151 `--nos`, 3152 `--criterio`,
      3153 `--regressao`, 3154 `--classe`, 3155 `--portao`, 3164 `--orcamento`, 3172 `--escalada`, 3183 `--tipo`,
      3188 `--cobre`, 3190 `--teste`, 3193 `--motivo`, 3194 `--evidencia`, 3197 `--texto`, 3198 `--evidencia`,
      3206 `--condicao`, 3207 `--evidencia`, 3208 `--no` (= nó), 3210 `--motivo`. 16 nomes.
    - `scripts/harness/engine/router.py` (cs-route) — 2 linhas: 279 `--procedencia`, 282 `--motivo`.
    - `--allow-outside` — 4 linhas: `scripts/cs.py:88`, `scripts/upgrade/cli.py:31`, `scripts/harness/cli.py:98`,
      `scripts/emit/cli.py:246`. Mais 3 chamadas internas que repassam a flag: `scripts/upgrade/core.py:486,1104,1164`.
    - Já com alias desde a iter26 (só em `new task|story`): `PT_NEW_FLAGS` em `state.py:814-815` (6 nomes: --tipo,
      --como, --quero, --para, --motivo, --reproducao), via reescrita de argv em `_deprecated_aliases` (`state.py:818-850`).
    
    **U2 — Citações de flag pt em texto (dicas, recusas, skills emitidas, docs), fora dos testes: 312 ocorrências.**
    - scripts/ (dicas e recusas no código): 126 em 14 arquivos. Maiores: auto.py ~48, state.py 19, tree.py 14,
      install.py 12, upgrade/core.py 8, replace.py 6, emit/cli.py 5, cs.py 4. A recusa do DoR cita `--criterio` em
      `tree.py:473` e `tree.py:612` (B-72 b).
    - SKILL.md 9 · MODO-DE-USO.md 18 · references/ 26 em 5 arquivos (harness.md 10) · assets/ 38 em 14 arquivos (os 5
      textos `assets/templates/state/new-*.md`, `auto-plan.md:4,6`, `move.md` e mais 7) · docs/ 94 em 12 arquivos
      (06-referencia-cli.md 34) · evals/ 1.
    
    **U3 — Chaves pt da forma interna do item e da sessão (B-68).**
    - Vocabulário: `hcore.py:273-283` (`ITEM_SCHEMA`) tem 16 chaves de item (tipo, como, quero, para, criterios, teste,
      reproducao, motivo, aceite, epico, objetivo, metrica, meta, reaberta, reaberturas, historico) e 9 aninhadas
      (entregue, devolvido, metricas, origem, tentativas, status_m2; acao, de, para do histórico; teste do critério).
      `SESSION_SCHEMA` tem 3 (blocos, titulo, linhas). O valor `kind: "epico"` está em `KIND_PT` (`hcore.py:309-310`).
    - Literais pt por arquivo de produto, por contagem bruta com `grep -c`: tree.py 139, auto.py 147, hcore.py 17,
      state.py 12, session.py 11, upgrade/core.py 6, panel/core.py 3, brief.py 2 linhas, probes/generate.py 1,
      router.py 1.
    - Pontos de tradução: `item_to_pt`/`item_to_en`/`session_to_pt` em hcore.py (7), tree.py (5) e session.py (2).
      `apply_ops` normaliza toda op `tput` com `item_to_pt` (`hcore.py:816-817`). Os eventos que o motor grava hoje
      carregam o item na forma interna, em pt (`tree.py:192,704,820,1840,1926`).
    
    **U4 — Testes que dependem da forma interna ou das flags pt.**
    - Testes do produto: 194 citações de flag pt. 12 linhas de assert com `--allow-outside`, das quais 3 afirmam o texto da recusa:
      `scripts/emit/tests/test_iter3_emit.py:38`, `scripts/harness/tests/test_install_outside.py:46` e
      `scripts/stage/tests/test_iter4_stages.py:33` (as outras 9 só passam a flag). A forma interna aparece em 17
      arquivos de teste que usam `load_board`/`item_to_pt`/`.items[`. Os que leem chave pt da memória:
      `test_iter23_arvore.py:144-162,192` e `test_iter26_modelo.py:53,63-64` (este afirma `kind == "epico"` em memória).
    - Oráculos: 728 citações de flag pt em 52 arquivos (iter23 70, iter10 69, m5 49, iter19 29, iter26 20, …). Dessas,
      `--allow-outside` aparece em ~95 linhas de 17 campanhas.
    - Doctests: `scripts/doctests/tests/test_commands_parse.py:78-83` confere as flags citadas contra o parser real de
      cs-state, cs-mem, cs-session e cs-route. O **cs-auto não está em `BINS`**.
    
    ## Classificação
    
    - **U1, 35 linhas: muda 35 · não muda 0 · congelado 0.** Cada linha ganha o nome en, e o pt vira alias depreciado
      (decisão E1-1).
    - **U2, 312 ocorrências: muda 311 · não muda 1.** Muda tudo o que é citação de flag em código de produto, SKILL,
      MODO-DE-USO, references, assets e docs. Não muda a citação em `evals/reference/good/reference_run.py`, que é
      fixture de avaliação e não texto do produto (confirmar na E3).
    - **U3, chaves do motor da árvore.** Muda: o vocabulário de `ITEM_SCHEMA`/`SESSION_SCHEMA`/`KIND_PT` e todos os
      leitores dele: tree.py, state.py (as 9 chaves de spec em `state.py:239-246,433-436` e a `reaberta` de 331),
      session.py (11), upgrade/core.py (6) e a fronteira do auto.py com a árvore (`node_spec` em `auto.py:1127-1143` e
      `f.get("aceite")` em `auto.py:1493`).
      Não muda (falso positivo do grep, medido linha a linha):
      - brief.py:18-19 é lista de stopwords;
      - probes/generate.py:29,59 é título e rótulo de prosa;
      - panel/core.py:31,169-171 é o esquema dos achados de auditoria, não item da árvore;
      - router.py:240 é o ledger do roteador;
      - state.py:382,472 e o `{ids, criar, mover:{de,para}, eventos}` do dry-run em `tree.py:263-264` são o contrato
        de saída do dry-run, que o oráculo da iter10 afirma em `test_estado_arvore.py:1344-1352`.
      Congelado: o interior do mandato M5 em auto.py (`PLANO_KEYS` `auto.py:58`, critérios, escaladas, nós do plano
      `NODE_FIELDS` `auto.py:856`, relatório), cerca de 130 dos 147 literais. Entra no selo e no hash do plano (D-20,
      B-21).
    - **U4: muda** 3 testes do produto que afirmam o texto `--allow-outside` na recusa, mais
      `test_iter23_arvore.py` e `test_iter26_modelo.py` (forma interna). **Não muda** o resto das 194 citações, que
      seguem válidas pelo alias. **Congelado:** os 52 arquivos de oráculo (728 citações), que seguem verdes pelo alias.
      Nenhuma mudança oficial prevista (ver F7).
    
    ## Exclusões
    
    - `.claude/` deste harness, inclusive `.claude/tools/ac/` (o motor embutido) e os comandos do harness em pt. Não é
      produto.
    - O interior do mandato M5: chaves, nós do plano, critérios e valores de `resolve --choice`
      (`retomar|trocar-agente|emendar|descartar-ramo|encerrar|abortar`, `auto.py:48`), que são vocabulário selado
      (D-20, B-21).
    - Nomes de SUBCOMANDO em pt: `cs-auto senha definir` e `cs-auto conferir` (`auto.py:3157-3159`), `cs-route anular`
      (`router.py:280`). A demanda (B-72) fala de flags. `senha` e `conferir` estão em `HUMAN_CMDS` (`auto.py:53`), a
      superfície de segurança que o guard reconhece pelo nome. Ficam para um item novo do BACKLOG (ver a pergunta).
    - O board M2 legado (`tasks`/delegações em engine.py e cmds.py) tem 0 literais de chave pt do item da árvore. Fora.
    - A prosa: mensagens, `próximo:` e textos em português ficam (D-07). Só muda o nome de flag que a prosa cita.
    - `docs/ROADMAP-*.md` históricos entram em U2 (é texto do pacote). Não releio cada um para julgar se é histórico.
    - Não medi o tempo do portão, que é um custo conhecido de cerca de 1 h em dois Pythons.
    
    ## Achados
    
    - F1 — `scripts/harness/engine/state.py:226-278` e `scripts/harness/engine/auto.py:3150-3210`: 28 nomes de flag pt
      sem equivalente en (U1). O alias da iter26 só cobre `new task|story` (`state.py:814-823`, onde `start` só
      reconhece `new …`). Os subcomandos `new epic|sprint|feature`, `move`, `close`, todo o cs-auto e o cs-route ficam
      de fora (B-72 a–c).
    - F2 — `scripts/harness/engine/state.py:840,844`: um `sys.stderr.write` por flag pt. N flags geram N linhas de
      aviso (B-72 e). O oráculo da iter26 só exige que o stderr case com `deprec|obsolet`
      (`campanhas/iter26/oraculo/test_iter26.py:62,746`), então agregar numa linha é compatível.
    - F3 — `scripts/harness/engine/tree.py:263-264`: o `--dry-run` devolve `{ids, criar, mover, eventos}` e o item que
      seria gravado não aparece (B-72 d). O item existe em memória no `T.ops` (`tree.py:192`). O contrato atual é
      afirmado pela iter10 (`test_estado_arvore.py:1344`), então acrescentar um campo é seguro; trocar as chaves não é.
    - F4 — `scripts/harness/engine/hcore.py:254-257,309-310`: o motor mantém em memória o vocabulário pt ("segue com as
      chaves históricas") e traduz nas bordas. Os eventos novos gravam o item em pt (`tree.py:192`) e o replay normaliza
      com `item_to_pt` (`hcore.py:817`). Consequência para o desenho: o histórico (events.jsonl) dos alvos tem `tput`
      com chaves pt e não será reescrito, então a leitura pt → en tem de continuar valendo no replay, para sempre.
    - F5 — `scripts/harness/engine/tree.py:1964` e `hcore.py:398-409`: a migração preserva `kind: "epico"` no disco
      ("epico → epic fica para o motor"). Um alvo antigo segue com `"epico"` até alguém regravar o item. O upgrade não
      normaliza (B-68).
    - F6 — `scripts/harness/engine/auto.py:1127-1143`: `node_spec` monta o item da árvore a partir do nó do mandato
      com chaves pt (`tipo/como/quero/para/teste/reproducao`). É a única fronteira mandato → árvore, e é onde a
      troca de vocabulário do item encosta no mandato congelado.
    - F7 — oráculos: 728 citações de flag pt em 52 arquivos, e ~95 linhas com `--allow-outside` em 17 campanhas.
      Nenhum oráculo lê a forma interna com chave pt. Os que usam `load_board` (`iter13 test_menores.py:341`,
      `iter18 test_iter18.py:197`) leem `id/m2/agent/allowed_paths/delegations`, já en. Os outros leem o disco com o
      próprio mapa (`iter23 test_iter23.py:233-241`, `iter19 test_iter19.py:254-262`). Conclusão: com alias, a troca de
      chaves internas não exige mudança oficial de oráculo. Sem alias, exigiria em pelo menos 13 campanhas.
    - F8 — `scripts/doctests/tests/test_commands_parse.py:78-83`: o cs-auto não está em `BINS`. A skill emitida
      `auto-plan` (`assets/templates/state/auto-plan.md:4,6`) cita flags que nenhum teste confere contra o parser. Foi
      assim que o `--tipo/--cobre/--motivo/--evidencia` passou pela iter26 (o oráculo da iter26 exclui linhas com
      cs-auto: `test_iter26.py:502`).
    - F9 — `scripts/upgrade/core.py:64`: o plano diz "board e eventos (%s/state/board.json5, events.jsonl)". O log fica
      em `.swarm/events.jsonl` (B-71 b).
    - F10 — `scripts/cs.py:87-88`, `scripts/upgrade/cli.py:31`, `scripts/harness/cli.py:98`, `scripts/emit/cli.py:246`:
      `--allow-outside` é a mesma flag com 4 definições. `cs.py:87` só a adiciona se o subparser ainda não tiver
      ("if not in opts"), então o alias precisa ficar coerente nos 4 pontos (B-71 a).
    - F11 (DESCARTADO por medição) — o B-68 diz "renomear toca panel e probes". `scripts/panel/core.py:31,169-171` é o
      esquema de achados de auditoria e `scripts/probes/generate.py:29,59` é prosa. Nenhum dos dois lê item da árvore.
    - F12 (DESCARTADO por medição) — a suspeita de que a troca das chaves internas quebraria os oráculos que leem o
      board. Medi que eles só usam chaves já en (F7).
    
    ## Enforcement existente
    
    - Cobre: `scripts/harness/tests/test_iter26_modelo.py` cobre o alias de `new task|story` e `new epico`. O oráculo
      da iter26 (53 testes) cobre o mesmo, mais "textos emitidos sem flag pt" para as 5 flags da iter26
      (`test_iter26.py:60,770,1004`). O doctest `test_commands_parse.py` confere que toda flag citada em
      SKILL/MODO-DE-USO/references/assets existe no parser de cs-state, cs-mem, cs-session e cs-route.
      `test_iter19_estado.py` cobre a tradução de disco (13 chamadas `item_to_pt/en`). O portão roda os oráculos de
      todas as campanhas nos dois Pythons.
    - Não cobre:
      - as flags do cs-auto contra o parser (F8);
      - as flags pt de `new epic|sprint|feature`, `move`, `close`, cs-auto e cs-route (não existe teste de alias);
      - o dry-run mostrar o item (F3);
      - o aviso agregado (F2);
      - o upgrade normalizar `kind: "epico"` (F5);
      - "nenhuma chave pt em memória" (não existe teste que varra a forma interna).
