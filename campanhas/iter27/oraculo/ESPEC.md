# Oráculo iter27 (0.15.0) — CLI e motor inteiros em inglês (B-72 + B-68 + B-71)

Exercita a skill num alvo REAL em modo árvore: fixture do emit + `cs.py init --platforms claude-code` +
`harness install` + `emit` + `cs-state init`. Comandos pelos bins do PRÓPRIO alvo (`.swarm/harness/<x>.py --root
<alvo>`: `state` = cs-state, `auto` = cs-auto, `router` = cs-route, `session` = cs-session) e pelo `scripts/cs.py` da
skill sob teste (`emit`, `harness install`, `upgrade`, `init --replace-harness`). Nada é importado do produto no
processo do teste: a forma interna (CA-08) é medida num subprocesso com `sys.path = <alvo>/.swarm/harness`.

Skill sob teste: `$CS_SKILL_DIR`, senão a raiz deste projeto. Skill 0.14.0 REAL: `$CS_OLD_SKILL_DIR` ou
`git archive 9e908e0` extraído num temporário (VERSION conferida = 0.14.0). Skill 0.13.1 REAL (só para pôr
`kind: "epico"` no disco, ver abaixo): `$CS_OLDER_SKILL_DIR` ou `git archive bac0e0f` (VERSION conferida = 0.13.1).
Temporários: `$CS_ORACLE_TMP`, senão o TMPDIR do sistema (apagados no fim; `CS_ORACLE_KEEP=1` os mantém). Env dos
subprocessos limpo de `CS_*`, `CLAUDE_PROJECT_DIR`, `GIT_DIR/WORK_TREE/INDEX_FILE`; `PYTHONDONTWRITEBYTECODE=1`.
Sem rede, sem sleep, sem data absoluta; cada teste trabalha num clone (copytree) da sua fixture.

## Fixtures (pessoa = Ana)

- **nova** (skill sob teste): EPC › SPR › FEA (iniciados); 1 task US na sprint; 1 avulsa; 1 no backlog. Criada pelas
  flags pt (valem na 0.13.1, na 0.14.0 e, como alias depreciado, na 0.15.0). Base de CA-01/02/03/05/07.
- **cadeia do mandato** (CA-02/03): a partir da nova, pelas flags pt: `propose` → `approve` (num pty real, senha de
  TESTE num registro PBKDF2 temporário fora do alvo, `$CS_SENHA_FILE` só no env do subprocesso, como a suíte do
  produto) → `tick` (PLANNING) → 2 nós + `plan submit` (RUNNING) → `escalate` (AWAITING_HUMAN) | nó rejeitado (REFLECT).
- **legado 0.14.0** (CA-04/08/09): alvo instalado e povoado pela skill 0.13.1 REAL, carimbo de sessão; depois
  `upgrade --apply --allow-outside` pela skill 0.14.0 REAL (o `kind: "epico"` fica no disco — `tree.py:1964`, F5) e
  trabalho na 0.14.0 (task nova, `move --avulsa`, carimbo). Resultado: alvo na 0.14.0 (run.json5 conferido) com
  `kind: "epico"` no disco, eventos `tput` com chaves pt e `kind: "epico"`, sessões gravadas.
  **Por que a 0.13.1 entra:** a 0.14.0 grava `kind: "epic"` em alvo novo (`hcore.py:309-310`, KIND_EN; afirmado pela
  iter26), então o único caminho REAL para um alvo 0.14.0 com `kind: "epico"` no disco é o da cobaia .NET: instalado
  antes da 0.14.0 e atualizado por ela. Nenhum arquivo é editado à mão.
- **nova 0.14.0** (CA-08 controle byte a byte): a mesma árvore da nova, gerada pela skill 0.14.0 REAL.
- **marcador** (CA-04 `init --replace-harness`): repo da fixture com `.claude/kernel/` de outro harness, sem init.

## Vocabulário (literal no teste; NÃO importado do produto)

Nome pt de hoje → nome en FIXADO na FEATURE.md:
- cs-state (CA-01): `--objetivo→--objective`, `--metrica→--metric`, `--meta→--goal`, `--epico→--epic`,
  `--aceite→--accept-cmd`, `--teste→--proving-test`, `--criterio→--criterion`, `--avulsa→--standalone`,
  `--devolver→--return`. Aliases da iter26 (contam na linha única do CA-03): `--tipo→--type`, `--como→--as-a`,
  `--quero→--i-want`, `--para→--so-that`, `--motivo→--reason`, `--reproducao→--failing-test`.
- cs-auto (CA-02): `--objetivo→--objective`, `--nos→--nodes`, `--criterio→--criterion`, `--regressao→--regression`,
  `--classe→--class`, `--portao→--gate`, `--orcamento→--budget`, `--escalada→--escalation`, `--tipo→--type`,
  `--cobre→--covers`, `--teste→--proving-test`, `--motivo→--reason`, `--evidencia→--evidence`, `--texto→--text`,
  `--condicao→--condition`, `--no→--node`.
- cs-route (CA-02): `--procedencia→--provenance`, `--motivo→--reason`.
- cs.py (CA-04): `--allow-outside→--include-emitted`.
- Nomes pt varridos (CA-05/09), 27: objetivo metrica meta epico aceite teste criterio avulsa devolver nos regressao
  classe portao orcamento escalada tipo cobre motivo evidencia texto condicao no procedencia como quero para
  reproducao. Casamento: `(?<![\w-])--<nome>(?![\w-])` (nem `--no-settings`, nem `--nos` quando se procura `--no`,
  nem `--metadata`).
- Chaves pt proibidas na forma interna (CA-08), as de `ITEM_SCHEMA`/`SESSION_SCHEMA` da 0.14.0 (`hcore.py:254-310`
  no 9e908e0), por caminho: item `tipo como quero para criterios teste reproducao motivo aceite epico objetivo metrica
  meta reaberta reaberturas historico`; `criterios[].teste`; `historico[].{acao,de,para}`;
  `closed.{entregue,devolvido,metricas,origem}`; `closed.metricas.{tentativas,status_m2}` (também dentro de
  `reaberturas[].closed`); valor `kind: "epico"`; sessão `blocos`, `blocos[].{titulo,linhas}`.

## Escolhas do oráculo (o CA não nomeia; o corretor segue estas)

- **Depreciação** (CA-01/02/03/04): linha do stderr que casa `deprec|obsolet|descontinuad` (sem caixa). "Com aviso" =
  há linha assim citando o nome pt usado. Exit continua 0.
- **Linha única** (CA-03): numa chamada com N flags pt (contando os aliases da iter26), o stderr tem EXATAMENTE UMA
  linha de depreciação e ela contém cada par `pt → en` (ou `pt -> en`, o en seguido de não-palavra). pt e en da mesma
  flag juntos: o valor do en é o gravado, e a linha única cita o pt e casa `ignorad|ignored`. Vale para `--x=v` e
  `--x v`. O `--no` do `escalate` vira `--node` (o nó gravado é o mesmo: `escaladas[-1].no == "01"`, chave interna do
  mandato, D-20); um prefixo `--no-*` (ex.: `harness install --no-settings --no-makefile`) não gera aviso.
- **Mesmo efeito** (CA-01/02/04): a mesma chamada em dois clones do mesmo alvo, A pela forma en e B pela pt: exit 0 nas
  duas; stdout igual; stderr igual fora das linhas de depreciação; efeito igual — CA-01: todos os arquivos de item
  (`backlog/ state/ archive/`, por caminho, conteúdo normalizado); CA-02: pasta do mandato (`.swarm/state/mandatos/
  MAN-001/*.json[5]`) + itens, ou o ledger `.swarm/.engine/model-router.jsonl` (linhas novas) no cs-route; `approve`
  compara só `state` e `orcamento` (o atestado tem sal aleatório); CA-04: sha256 de todo arquivo FORA de `.swarm/` e
  `.git/`.
- **Help** (CA-01/02): `<subcomando> --help` sai 0, traz cada nome en do subcomando e nenhum nome pt varrido.
- **Recusa** (CA-04): sem a flag, exit ≠ 0 e a saída (stdout+stderr) cita `--include-emitted`. Plano do upgrade: cita
  `.swarm/events.jsonl` e TODA ocorrência de `events.jsonl` na saída termina em `.swarm/events.jsonl` (nem solta, nem
  `state/events.jsonl`).
- **Tabela de alias** (CA-05, o que é isento): em texto, a linha de TABELA Markdown (começa com `|`) que traz o nome pt
  E o seu nome en; no código (`scripts/**/*.py` fora de `tests/` e `test_*.py`), as strings que são SÓ um nome de flag
  (`"--objetivo"`, chave/valor de tabela ou registro no argparse) e as docstrings. Comentários não são lidos. Todo o
  resto (dica, recusa, help, f-string, `%`-string) que cite flag pt reprova. Varridos: textos emitidos no alvo
  (CLAUDE.md, AGENTS.md, Makefile, specialists.mk, `.claude/**` fora `agent-memory`, `.cursor/**`, `.github/**`,
  `.swarm/emit/**`; `.md .mdc .mk .txt .json .json5 .sh`), SKILL.md, MODO-DE-USO.md, `references/**` fora
  `references/migrations.json5`, `docs/**/*.md`, `assets/templates/**` (fonte dos textos emitidos em todas as
  plataformas) e o código. A recusa do DoR é medida pela CLI real (`new task`/`new story` de US sem critério nem
  história): cita `--criterion` e nenhuma flag pt.
- **Doctest** (CA-06): uma citação de `cs-auto plan add-node … --flag-da-ana-inexistente x` acrescentada a
  `assets/templates/state/auto-plan.md` numa CÓPIA da skill faz `scripts/doctests/tests/test_commands_parse.py`
  reprovar citando a flag (hoje o cs-auto não é conferido); a skill limpa passa.
- **Item no dry-run** (CA-07): fora das chaves `{ids, criar, mover, eventos}` (que continuam), em qualquer chave e
  profundidade, um dict com `id` = o id criado e `kind`, IGUAL ao arquivo gravado pelo mesmo comando sem `--dry-run`
  (sem `_generated_by` e `status`, timestamps normalizados) — portanto chaves en. Nada escrito (sha256 de toda a árvore
  do alvo, `.git` fora, antes = depois).
- **Forma interna en** (CA-08): os nomes en são os do arquivo (os en de `ITEM_SCHEMA`/`SESSION_SCHEMA`) e `kind:
  "epic"`. Medida: `hcore.load_board(root)["tree"]`, `session.last_stamp(root)[1]` (carimbo em memória) e o replay
  `hcore.new_board()` + `hcore.apply_ops(...)` de cada evento de `.swarm/events.jsonl` (como o validate faz; se a
  assinatura mudar, cai para `apply_ops(board, ops)`). "Mesmo estado": a árvore em memória do motor novo é igual à da
  0.14.0 traduzida pelo `item_to_en` da própria 0.14.0, e o replay é igual à projeção carregada. Alvo medido = o
  legado atualizado pela skill sob teste (`upgrade --apply --allow-outside`, o caminho oficial; confere-se que o
  `hcore.py` instalado é o da skill).

## Normalizações (o que NÃO precisa ser igual)

Só estas: timestamp ISO (`AAAA-MM-DDThh:mm[:ss[.f]][Z|±hh:mm]`) e o compacto `AAAAMMDDThhmmss…Z` → `<T>`; data
`AAAA-MM-DD` (ids de task avulsa/backlog) → `<D>`; `run_id` (16 hex) → `<RUN>`; o caminho do alvo → `<ALVO>` na
saída; topo do mandato sem `relogio` e `updated_at`; linha do ledger do roteador sem `prev` (hash da cadeia). O
"arquivo do item byte a byte igual ao de hoje" (CA-08) compara o TEXTO de cada arquivo de item gravado pela 0.14.0 e
pela skill sob teste para as mesmas operações (populate + `move --avulsa` + task na feature + `close --devolver
--reason` + BUG com `--reproducao`), com só as três primeiras normalizações.

## Testes

Tipo: D = defeito (falha no HEAD 9e908e0 / 0.14.0 por ASSERÇÃO, passa com a entrega); R = controle/calibração (passa
no HEAD e depois; nome com `controle`). Versão sempre relativa (≥ 0.15.0).

| CA | Teste | Tipo | Critério | Por que falha no HEAD |
|---|---|---|---|---|
| CA-01 | test_ca01_new_epic_en_igual_pt | D | `new epic --objective --metric` ≡ `--objetivo --metrica` | en: exit 2 (argparse) |
| CA-01 | test_ca01_new_sprint_en_igual_pt | D | `new sprint --goal --epic` ≡ `--meta --epico` | idem |
| CA-01 | test_ca01_new_feature_en_igual_pt | D | `new feature --accept-cmd` ≡ `--aceite` | idem |
| CA-01 | test_ca01_new_task_en_igual_pt | D | `new task` (sprint) `--criterion --proving-test` ≡ pt | idem |
| CA-01 | test_ca01_new_task_standalone_en_igual_pt | D | `new task --standalone` ≡ `--avulsa` | idem |
| CA-01 | test_ca01_new_story_en_igual_pt | D | `new story` en ≡ pt | idem |
| CA-01 | test_ca01_move_standalone_en_igual_pt | D | `move --standalone` ≡ `--avulsa` | idem |
| CA-01 | test_ca01_close_return_en_igual_pt | D | `close --return --reason` ≡ `--devolver` | idem |
| CA-01 | test_ca01_pt_avisa_depreciacao | D | os 8 comandos pt: exit 0 + aviso citando cada flag pt | sem aviso |
| CA-01 | test_ca01_help_so_en | D | help de new epic/sprint/feature/task/story, move, close: en presentes, pt ausentes | help só pt |
| CA-01 | test_ca01_controle_par_pt_pt_e_deterministico | R | os 8 comandos pt × pt: mesma saída e disco (calibra a comparação) | — |
| CA-01 | test_ca01_controle_pt_continua_criando | R | `new epic` pt cria `kind: epic`, `objective`, `metric` | — |
| CA-02 | test_ca02_propose_en_igual_pt | D | `propose` en (objective nodes regression criterion class gate) ≡ pt | en: exit 2 |
| CA-02 | test_ca02_approve_budget_en_igual_pt | D | `approve --budget` (pty) ≡ `--orcamento`: estado e orçamento | en: exit 2 |
| CA-02 | test_ca02_amend_budget_en_igual_pt | D | `amend --budget` ≡ `--orcamento` | en ignorado (PROOF_CMDS): orçamento ≠ |
| CA-02 | test_ca02_plan_add_edit_submit_en_igual_pt | D | `plan add-node/edit-node` (type covers proving-test) + `submit --reason --evidence` ≡ pt | en: exit 2 |
| CA-02 | test_ca02_reflect_en_igual_pt | D | `reflect --text --evidence` ≡ pt | en: exit 2 |
| CA-02 | test_ca02_escalate_en_igual_pt | D | `escalate --condition --evidence --node` ≡ pt | en: exit 2 |
| CA-02 | test_ca02_pause_en_igual_pt | D | `pause --reason` ≡ `--motivo` | en: exit 2 |
| CA-02 | test_ca02_route_outcome_en_igual_pt | D | cs-route `outcome --provenance` ≡ `--procedencia` | en: exit 2 |
| CA-02 | test_ca02_route_anular_en_igual_pt | D | cs-route `anular --reason` ≡ `--motivo` | en: exit 2 |
| CA-02 | test_ca02_pt_avisa_depreciacao | D | propose/pause/escalate/add-node pt e `outcome --procedencia`: exit 0 + aviso | sem aviso |
| CA-02 | test_ca02_help_so_en | D | help de propose approve amend resolve plan add-node/edit-node/submit reflect escalate pause, cs-route outcome/anular | help só pt |
| CA-02 | test_ca02_controle_resolve_escalation_mesmo_efeito | R | `resolve --escalation ESC-1` ≡ `--escalada ESC-1` | — (o HEAD ignora o extra; o `--escalation` no help é o D) |
| CA-02 | test_ca02_controle_par_pt_pt_e_deterministico | R | propose, amend, plan, reflect, escalate, pause, outcome, approve pt × pt iguais | — |
| CA-02 | test_ca02_controle_chaves_internas_do_mandato_continuam | R | mandato com `objetivo nos_estimados regressao criterios classe portoes orcamento` (D-20) | — |
| CA-03 | test_ca03_uma_linha_para_n_flags_pt_no_cs_state | D | `new task` com 6 flags pt ⇒ 1 linha com os 6 pares | 4 linhas (só os aliases da iter26 avisam) |
| CA-03 | test_ca03_uma_linha_para_n_flags_pt_no_cs_auto | D | `propose` com 6 flags pt ⇒ 1 linha com os 6 pares | 0 linhas |
| CA-03 | test_ca03_en_vence_no_cs_state | D | `new epic --objective A --objetivo B` ⇒ `objective == A`, linha diz pt ignorado | exit 2 |
| CA-03 | test_ca03_en_vence_no_cs_auto | D | `propose` en + `--objetivo` ⇒ objetivo do en, linha diz pt ignorado | exit 2 |
| CA-03 | test_ca03_flag_pt_com_igual | D | `--objetivo=pix --metrica=conversao` gravam e dão 1 linha com 2 pares | 0 linhas |
| CA-03 | test_ca03_no_do_escalate_vira_node | D | `escalate --condicao … --no 01` ⇒ nó 01 e 1 linha com `--no → --node` | 0 linhas |
| CA-03 | test_ca03_controle_criterio_da_linha_unica | R | calibração: linha boa passa; a de hoje (1 por flag), vazia e sem `ignorad` reprovam | — |
| CA-03 | test_ca03_controle_prefixo_no_dash_nao_e_alias | R | `harness install --dry-run --no-settings --no-makefile`: 0 e sem aviso | — |
| CA-04 | test_ca04_emit_include_emitted_igual_alias | D | `emit --include-emitted` ≡ `--allow-outside` (fora de .swarm/) | exit 2 |
| CA-04 | test_ca04_harness_install_include_emitted_igual_alias | D | idem `harness install` | exit 2 |
| CA-04 | test_ca04_upgrade_apply_include_emitted_igual_alias | D | idem `upgrade --apply` no legado 0.14.0 | exit 2 |
| CA-04 | test_ca04_init_replace_harness_include_emitted_igual_alias | D | idem `init --replace-harness` no marcador; o outro harness sai | exit 2 |
| CA-04 | test_ca04_recusa_do_emit_cita_include_emitted | D | `emit` sem flag recusa citando `--include-emitted` | cita `--allow-outside` |
| CA-04 | test_ca04_recusa_do_harness_install_cita_include_emitted | D | idem `harness install` | cita `--allow-outside` |
| CA-04 | test_ca04_recusa_do_upgrade_cita_include_emitted | D | idem `upgrade --apply` no legado 0.14.0 | exit 0 (0.14.0→0.14.0: nada a fazer) |
| CA-04 | test_ca04_recusa_do_upgrade_de_0131_cita_include_emitted | D | idem num alvo 0.13.1 | cita `--allow-outside` |
| CA-04 | test_ca04_recusa_do_replace_harness_cita_include_emitted | D | idem `init --replace-harness` | cita `--allow-outside` |
| CA-04 | test_ca04_allow_outside_avisa_depreciacao | D | `emit --allow-outside`: exit 0 + aviso citando `--allow-outside` | sem aviso |
| CA-04 | test_ca04_plano_do_upgrade_cita_swarm_events_jsonl | D | `cs.py upgrade` no legado 0.14.0: critério do plano | "nada a fazer" (sem plano) |
| CA-04 | test_ca04_plano_do_upgrade_de_0131_cita_swarm_events_jsonl | D | idem num alvo 0.13.1 | cita `(.swarm/state/board.json5, events.jsonl)` |
| CA-04 | test_ca04_controle_par_allow_allow_e_deterministico | R | `emit` e `upgrade --apply` (0.13.1) allow × allow iguais | — |
| CA-04 | test_ca04_controle_allow_outside_continua_escrevendo | R | `emit --allow-outside` reescreve `.claude/orchestrator.md` | — |
| CA-04 | test_ca04_controle_plano_da_0140_cita_events_sem_caminho | R | o plano da 0.14.0 reprova no critério; calibração do critério | — |
| CA-05 | test_ca05_textos_emitidos_sem_flag_pt | D | alvo novo: 0 citação nos textos emitidos | specialists.mk, skills… |
| CA-05 | test_ca05_skill_e_modo_de_uso_sem_flag_pt | D | SKILL.md + MODO-DE-USO.md: 0 | 18 |
| CA-05 | test_ca05_references_sem_flag_pt | D | references/ (fora migrations.json5): 0 | 11 |
| CA-05 | test_ca05_docs_sem_flag_pt | D | docs/**/*.md: 0 | 64 |
| CA-05 | test_ca05_templates_sem_flag_pt | D | assets/templates/**: 0 | 38 |
| CA-05 | test_ca05_dicas_e_recusas_do_codigo_sem_flag_pt | D | strings do código: 0 | 55 |
| CA-05 | test_ca05_recusa_do_dor_cita_criterion | D | DoR de `new task`/`new story`: cita `--criterion`, nenhuma pt | cita `--criterio`, `--como`… |
| CA-05 | test_ca05_controle_varredura_acha_flag_pt_na_0140 | R | a varredura acha pt em todas as categorias na 0.14.0 e nos textos dela | — |
| CA-05 | test_ca05_controle_criterio_da_tabela_de_alias | R | calibração: tabela isenta; dica/f-string reprovam; docstring isenta | — |
| CA-06 | test_ca06_doctest_reprova_citacao_invalida_do_cs_auto | D | citação inválida de cs-auto ⇒ doctest reprova citando a flag | o doctest passa (cs-auto fora dos BINS) |
| CA-06 | test_ca06_controle_doctest_reprova_citacao_invalida_do_cs_state | R | a mesma injeção com cs-state reprova (a injeção é lida) | — |
| CA-06 | test_ca06_controle_doctest_passa_na_skill | R | doctest da skill limpa passa (toda citação parseia) | — |
| CA-07 | test_ca07_dry_run_{epic,sprint,feature,task,story}_mostra_o_item (5) | D | o item que seria gravado, igual ao arquivo | a saída não traz o item |
| CA-07 | test_ca07_controle_criterio_do_item | R | calibração: saída de hoje e vazia reprovam; hoje + item do arquivo passa; item com `tipo` reprova | — |
| CA-07 | test_ca07_controle_dry_run_nao_escreve | R | árvore do alvo igual antes/depois | — |
| CA-07 | test_ca07_controle_contrato_ids_criar_mover_eventos | R | as 4 chaves; `ids` tem o id; `criar` tem o caminho do arquivo | — |
| CA-08 | test_ca08_arvore_em_memoria_sem_chave_pt | D | `load_board` do legado: nenhum item com chave pt / `kind: "epico"` | memória pt |
| CA-08 | test_ca08_sessao_em_memoria_sem_chave_pt | D | carimbo em memória sem `blocos/titulo/linhas` | `blocos` |
| CA-08 | test_ca08_replay_do_historico_pt_sem_chave_pt_e_igual | D | replay do events.jsonl legado: sem erro, = projeção, sem chave pt | memória pt |
| CA-08 | test_ca08_estado_igual_ao_da_0140_em_ingles | D | memória nova = `item_to_en` da memória 0.14.0 | memória pt ≠ en |
| CA-08 | test_ca08_eventos_novos_gravam_item_en | D | `new epico`, `new task`, `start` no legado: `tput` novos sem chave pt; replay misto = projeção | `tput` pt |
| CA-08 | test_ca08_controle_criterio_forma_do_arquivo_passa | R | calibração: itens/carimbo do disco passam; forma pt reprova | — |
| CA-08 | test_ca08_controle_historico_legado_tem_chave_pt | R | o events.jsonl legado tem `tput` pt e `kind: "epico"` | — |
| CA-08 | test_ca08_controle_nenhum_def_removido | R | todo def (por arquivo, fora testes) da 0.14.0 segue; `item_to_pt`/`session_to_pt` ficam | — |
| CA-08 | test_ca08_controle_arquivo_do_item_igual_ao_da_0140 | R | mesmas operações: arquivos de item com o mesmo texto da 0.14.0 | — |
| CA-09 | test_ca09_apply_sai_0_e_validate_strict_passa | D | `upgrade --apply --include-emitted` no legado: 0; `validate --strict` 0 | exit 2 |
| CA-09 | test_ca09_disco_passa_a_kind_epic | D | todo épico com `kind: "epic"` | exit 2 |
| CA-09 | test_ca09_events_jsonl_intacto | D | `.swarm/events.jsonl` byte a byte igual | exit 2 |
| CA-09 | test_ca09_textos_emitidos_sem_flag_pt | D | textos emitidos sem flag pt | exit 2 |
| CA-09 | test_ca09_version_0150 | D | VERSION ≥ 0.15.0; uma entrada `to: "0.15.0"` no catálogo; run.json5 ≥ 0.15.0 | VERSION 0.14.0 |
| CA-09 | test_ca09_controle_legado_tem_epico_e_texto_pt | R | o legado tem `kind: "epico"`, textos pt e valida | — |

## Calibração

- Saída vazia reprova: `dep_line_problems("")`, `dry_item_problems({})`, `events_path_problems("")` dão problema
  (controles do CA-03/07/04); varredura e forma interna reprovam a forma pt (controles CA-05/08).
- Saída boa conhecida passa: a forma en implementada como a pt é simulada pelos pares pt × pt (CA-01/02) e
  allow × allow (CA-04) — mesma saída e mesmo efeito em dois clones, ou seja, a comparação não reprova por relógio,
  id ou sal; a linha única boa, o item do dry-run igual ao arquivo, a tabela de alias, o plano com `.swarm/events.jsonl`
  e o disco en passam nos critérios.
- No HEAD 9e908e0 todos os D falham por ASSERÇÃO (FAIL, 0 ERROR) e todos os R passam — base.txt, nos dois Pythons.

Rodar (desta pasta): `python3 -m unittest -v test_iter27` (e `/usr/bin/python3 -m unittest test_iter27`).
