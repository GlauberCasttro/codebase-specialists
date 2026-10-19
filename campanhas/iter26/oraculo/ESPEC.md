# Oráculo iter26 (0.14.0) — modelo de itens canônico, sem campos mortos, telemetria por tentativa, B-49, B-67

Exercita a skill num alvo REAL em modo árvore: fixture do emit + `cs.py init` + `harness install` + `emit` +
`cs-state init`. Comandos pelo `cs-state` do próprio alvo (`.swarm/harness/state.py --root <alvo>`, o que
`.swarm/bin/cs-state` chama), pelo `cs-mem` do alvo (`.swarm/harness/mem.py --root <alvo>`) e pelo hook REAL
`CLAUDE_PROJECT_DIR=<alvo> python3 <alvo>/.swarm/harness/guard.py subagent-stop`. A task M2 é lida da projeção
(`.swarm/.engine/projection.json`, `tasks[]`); o item da árvore, do seu arquivo em `backlog/|state/|archive/`.

Fixtures (pessoa = Ana; caminhos só em TMPDIR/`$CS_ORACLE_TMP`):
- **nova** (skill sob teste): EPC › SPR › FEA › story US (2 tasks, dev-billing e dev-web; a 1ª com allowed_paths
  estreitado por `amend`); 2 tasks US na sprint; 1 avulsa; 1 no backlog. Criada com as flags pt (valem na 0.13.1 e,
  como alias depreciado, na 0.14.0). Cada teste usa um clone (copytree).
- **legado** (CA-01/02/03/07): alvo instalado pela skill 0.13.1 REAL (`git archive bac0e0f`, ou `$CS_OLD_SKILL_DIR`),
  mesma árvore + task da sprint iniciada (M2 com `dod/handoff/knowledge_context/briefing.context/scope.in`) + BUG
  antigo com os passos em `--reproducao` (gravados em `failing_test`). Depois, pela skill sob teste: `cs.py upgrade`
  e `upgrade --apply --allow-outside`.

Escolhas do oráculo (o CA não nomeia; o corretor segue estas):
- CA-03: flags en do BUG da árvore = `--repro "<passos>"` e `--failing-test <test-id>` (as mesmas do board plano,
  E/state.py:75 e :546). Disco: `repro_steps` (texto ou lista) e `failing_test` (test-id).
- CA-05: nomes livres; a lista é achada pela forma: elementos dict com tentativa (chave `attempt|tentativa`, int,
  distintos), motivo, quem (`lead`) e quando (ISO) — rejeições; tentativa, `exit*` int, sha256 hex e quando — gate
  (3 elementos, um por verify). Em qualquer lugar da task M2.
- CA-06: tokens = soma do `usage` de cada mensagem `assistant` do transcript (ids distintos): input 1100, output 250,
  cache_read 300 / cache_creation 40 (aceita 300, 40 ou 340 numa chave `*cache*`), num dict da delegação com chaves
  `*input*`/`*output*`. NOT_RUN = string `NOT_RUN` num dict da delegação com motivo (texto > 8 chars) e nenhum token 0.
  Corrompido = só linhas `usage` inválidas ⇒ marca de falha (`ERROR|FAIL|falh|erro|corromp|invalid`) num campo
  `token|usage|status|error|reason` da delegação ou numa linha nova do `.swarm/state/ledger.jsonl` com `usage|token`.
- CA-04: depreciação = stderr casa `deprec|obsolet|descontinuad`. Textos emitidos: CLAUDE.md, AGENTS.md, Makefile,
  specialists.mk, `.claude/**` (menos agent-memory), `.cursor/**`, `.github/**`, `.swarm/emit/**`; linha com
  `--tipo|--como|--quero|--para|--motivo` ou `new epico` reprova, exceto linhas do `cs-auto` (M5, fora do escopo).
- CA-08: "acusado" = linha de problema (`- ...`) do verify citando o caminho.
- CA-09: texto casa `git add (-A )?.swarm`.

Tipo: D = defeito (falha no HEAD bac0e0f / 0.13.1, passa com a entrega); R = controle (passa sempre; nome com
`controle|continua|intacta`). Versão sempre relativa (≥ 0.14.0).

| CA | Teste | Tipo | Critério |
|---|---|---|---|
| CA-01 | test_ca01_task_da_sprint_sem_campos_mortos | D | `start` da task da sprint ⇒ task M2 sem `dod`, `handoff`, `knowledge_context`, `briefing.context`, `briefing.scope.in` |
| CA-01 | test_ca01_task_avulsa_sem_campos_mortos | D | idem, task `--avulsa` |
| CA-01 | test_ca01_task_de_story_sem_campos_mortos | D | idem, task de story |
| CA-01 | test_ca01_add_task_sem_campos_mortos | D | `add task --quick` (sessão `pequena`) idem |
| CA-01 | test_ca01_add_task_nao_busca_na_memoria | D | `add task --quick` com `mem.search` e `<Classe>.search` do alvo espionados: 0 chamadas |
| CA-01 | test_ca01_controle_espiao_ve_a_busca | R | o espião registra uma busca real (o D acima não é vácuo) |
| CA-01 | test_ca01_controle_task_antiga_continua_despachando_e_validando | R | legado atualizado: task antiga com campos mortos ⇒ show, dispatch, submit, verify PASS, `validate --strict` 0 |
| CA-02 | test_ca02_new_epic_grava_kind_epic | D | `new epic` ⇒ arquivo `kind: "epic"` |
| CA-02 | test_ca02_alias_new_epico_grava_kind_epic | D | `new epico` (alias) ⇒ `kind: "epic"` |
| CA-02 | test_ca02_populate_grava_epic | D | épico da fixture ⇒ `kind: "epic"` |
| CA-02 | test_ca02_controle_arquivo_antigo_epico_continua_lido | R | legado (`kind: "epico"`) depois do upgrade: kind epico ou epic; `board` e `show` do épico iguais (rc+stdout) aos de antes; `validate --strict` 0 |
| CA-02 | test_ca02_controle_demais_campos_iguais_a_0131 | R | mesmos comandos na 0.13.1 e na skill sob teste: cada item igual sem timestamps (`at`, `*_at`), exceto `kind` do épico |
| CA-03 | test_ca03_bug_grava_repro_steps_e_failing_test | D | `new task --type BUG --repro <passos> --failing-test tests.test_red` ⇒ `repro_steps` com os passos, `failing_test == "tests.test_red"` |
| CA-03 | test_ca03_bug_inicia_com_teste_vermelho | D | esse BUG passa no `start` (DoR roda o failing_test vermelho, não os passos) |
| CA-03 | test_ca03_bug_novo_show_traz_passos_e_teste | D | `show` do BUG novo traz os passos e o test-id |
| CA-03 | test_ca03_bug_antigo_show_traz_os_passos | D | BUG da 0.13.1 (passos em `failing_test`) depois do upgrade: `show` traz os passos (hoje o show os omite) |
| CA-03 | test_ca03_controle_bug_antigo_continua_com_o_texto | R | o texto continua no arquivo depois do upgrade; `validate --strict` 0 |
| CA-04 | test_ca04_flags_en_criam_task_us | D | `--type/--as-a/--i-want/--so-that` criam a US com `type/as_a/i_want/so_that` |
| CA-04 | test_ca04_flag_en_reason_cria_chore | D | `--type CHORE --reason` grava `reason` |
| CA-04 | test_ca04_flags_pt_avisam_depreciacao | D | flags pt ⇒ rc 0 e aviso de depreciação no stderr |
| CA-04 | test_ca04_new_epico_avisa_depreciacao | D | `new epico` ⇒ rc 0 e aviso no stderr |
| CA-04 | test_ca04_pt_e_en_gravam_igual | D | task criada com en e com pt: arquivos iguais (sem id/título/caminhos/timestamps) |
| CA-04 | test_ca04_help_sem_flags_pt | D | `new task --help`, `new story --help`, `new --help`: rc 0, sem flag pt nem `epico` |
| CA-04 | test_ca04_textos_emitidos_sem_flags_pt | D | textos emitidos (lista acima) sem flag pt / `new epico` |
| CA-04 | test_ca04_controle_flags_pt_continuam_criando | R | flags pt continuam criando a task |
| CA-05 | test_ca05_lista_de_rejeicoes | D | reject→retry→verify→reject→retry→verify→accept ⇒ lista com as 2 rejeições (tentativa, motivo, quem, quando) |
| CA-05 | test_ca05_lista_de_gate_por_tentativa | D | lista com o gate das 3 tentativas (tentativa, exit, sha, quando) |
| CA-05 | test_ca05_ultimo_reject_reason_igual_ao_ultimo_elemento | D | após a 2ª rejeição: `reject_reason` == 2º motivo == último elemento |
| CA-05 | test_ca05_ultimo_gate_report_igual_ao_ultimo_elemento | D | `gate_report.build.output_sha256` está no último elemento da lista de gate |
| CA-05 | test_ca05_controle_reject_reason_continua | R | `reject_reason` após cada reject; `gate_report.build.exit_code` 0; ACCEPTED |
| CA-06 | test_ca06_tokens_junto_do_modelo_medido | D | subagent-stop com transcript com `usage` ⇒ tokens somados na delegação, modelo `medida` |
| CA-06 | test_ca06_sem_transcript_not_run_com_motivo | D | sem `agent_transcript_path` ⇒ NOT_RUN com motivo, nenhum token 0 |
| CA-06 | test_ca06_transcript_corrompido_registra_falha | D | transcript com `usage` inválido ⇒ falha registrada (delegação ou ledger), nenhum token 0 |
| CA-06 | test_ca06_controle_modelo_medido_continua | R | modelo medido `sonnet/medida`; o hook segue pedindo o submit (`block`) |
| CA-07 | test_ca07_version_e_catalogo_0140 | D | VERSION ≥ 0.14.0; exatamente uma entrada `to: "0.14.0"` com ações ⊇ {harness, emit} |
| CA-07 | test_ca07_plano_lista_0140 | D | `cs.py upgrade` no legado ⇒ 0 e cita "0.14.0" |
| CA-07 | test_ca07_apply_reemite_textos_em_ingles | D | `upgrade --apply --allow-outside` ⇒ 0 e textos emitidos sem flag pt |
| CA-07 | test_ca07_controle_fixture_legada_tem_texto_pt | R | o legado 0.13.1 tem textos pt (o D acima não é vácuo) |
| CA-07 | test_ca07_controle_validate_strict_continua_depois_do_upgrade | R | `validate --strict` 0 depois do apply |
| CA-07 | test_ca07_controle_itens_antigos_continuam_legiveis | R | mesmo conjunto de itens; `show` de cada um rc 0 citando o id |
| CA-08 | test_ca08_caderno_de_outro_agente_regravado_pelo_cs_mem | D | dispatch+submit da task de dev-billing; `cs-mem correct --agent dev-web`; verify não acusa `.claude/agent-memory/dev-web/MEMORY.md` |
| CA-08 | test_ca08_caderno_do_agente_da_task_regravado_pelo_cs_mem | D | idem com `correct --agent dev-billing` (o caderno da própria task) |
| CA-08 | test_ca08_caderno_regenerado_por_notebook | D | `cs-mem add --agent dev-web --rule` + `cs-mem notebook --agent dev-web` não acusado |
| CA-08 | test_ca08_controle_caderno_adulterado_continua_acusado | R | caderno de dev-web com o bloco gerado editado à mão ⇒ acusado |
| CA-08 | test_ca08_controle_outro_arquivo_do_claude_continua_acusado | R | `.claude/orchestrator.md` alterado ⇒ acusado |
| CA-08 | test_ca08_controle_sem_escrita_extra_continua_pass | R | sem escrita extra o verify passa (PASS, rc 0) |
| CA-09 | test_ca09_orquestrador_emitido_orienta_git_add | D | `.claude/orchestrator.md` cita `git add .swarm` |
| CA-09 | test_ca09_close_de_task_orienta_git_add | D | M2 até accept + `close` da task ⇒ saída cita `git add .swarm` |
| CA-09 | test_ca09_close_de_story_orienta_git_add | D | story com as 2 tasks descartadas, `close` ⇒ idem |
| CA-09 | test_ca09_close_de_sprint_orienta_git_add | D | sprint com task descartada, `close` ⇒ idem |
| CA-09 | test_ca09_controle_close_continua_movendo_para_archive | R | `close` da story continua movendo para archive/ |

Calibração (base.txt, 2 Pythons): no HEAD bac0e0f todos os 36 D falham por ASSERÇÃO (FAIL, 0 ERROR) e os 15 R passam.
Mutações simuladas (cópia `git archive HEAD` em TMPDIR, `CS_SKILL_DIR`):
- A (B-49 ingênuo: o verify pula todo `.claude/agent-memory/`): os 3 D de CA-08 passam e o controle "caderno
  adulterado" FALHA — o oráculo não aceita a isenção cega.
- B (sem transcript grava `{status: NOT_RUN, reason, input_tokens: 0, output_tokens: 0}`): `sem_transcript` FALHA
  pelo token 0; os outros D de CA-06 seguem FAIL.
- C (saída boa conhecida: soma do `usage` por linha, NOT_RUN com motivo sem tokens, ERROR em `usage` inválido):
  TestCA06 4/4.

Rodar: `cd campanhas/iter26/oraculo && python3 medir.py` (ou `python3 -m unittest -v test_iter26`).
