# Oráculo iter23 (0.13.0) — árvore sem itens presos, comandos certos, auto-memória e versão visível

Exercita a skill num alvo REAL em modo árvore: fixture do emit + `cs.py init` + `harness install` + `emit` +
`cs-state init` (`.swarm/events.jsonl` presente). Comandos pelo `cs-state` do próprio alvo
(`.swarm/harness/state.py --root <alvo>`, o que `.swarm/bin/cs-state` chama); guard pelo hook real
(`CLAUDE_PROJECT_DIR=<alvo> python3 <alvo>/.swarm/harness/guard.py pre-write`), principal = payload sem `agent_id`,
subagente = `agent_id`/`agent_type` com delegação DISPATCHED de verdade (start + hook `pre-agent`).

Fixtures (pessoa = Ana; nenhum caminho real):
- **nova**: alvo instalado pela skill sob teste, sem itens; cada teste usa um clone (copytree).
- **legado**: alvo instalado pela skill 0.12.x REAL (`git archive b757d1f` = 0.12.2, ou `$CS_OLD_SKILL_DIR`),
  com os itens presos da cobaia criados pelo `new` antigo: EPC-001 ativo › SPR-001 ativa com tasks FIX sem
  `--fixes/--teste`, CHORE sem `--motivo`, US com allowed_path `.claude/agent-memory/...` (reservado), US sem
  como/quero/para, BUG sem `--reproducao`, US sem `--verify-cmd`, uma US pronta e uma US iniciada (BRIEFED);
  FEA-001 no backlog com FIX presa e story composta; SPR-002 ativa sem épico só com CHORE/FIX presas; SPR-003 do
  EPC-001 no backlog (2ª sprint aberta no épico). A fixture confere que cada item preso falha no `check` antigo.
  Depois: `cs.py upgrade` (plano) e `upgrade --apply --allow-outside` pela skill sob teste; os testes de CA-01..04
  rodam em clones do legado ATUALIZADO (motor novo, itens presos herdados).

Tipo: D = defeito (falha no HEAD 21c6164 / 0.12.2, passa com a entrega); R = controle (passa sempre; nome com
`controle|continua`). Versão sempre relativa (≥ 0.13.0).

| CA | Teste | Tipo | Critério |
|---|---|---|---|
| CA-01 | test_ca01_drop_task_nao_iniciada_com_dor_incompleto | D | `drop <id> --reason` em FIX/CHORE presas (sprint e feature) ⇒ 0; arquivo em archive/, "DROPPED" e o motivo no item; fora do board aberto e do `next`; `validate --strict` 0 |
| CA-01 | test_ca01_drop_task_nao_iniciada_com_dor_completo | D | idem com a US pronta não iniciada |
| CA-01 | test_ca01_drop_sem_reason_recusa_e_pede_o_motivo | D | sem `--reason` ⇒ ≠0, saída cita `--reason`/motivo, nada muda |
| CA-01 | test_ca01_controle_task_iniciada_continua_pelo_fluxo_atual | R | task BRIEFED: drop ⇒ ≠0, continua em state/ |
| CA-02 | test_ca02_amend_campos_do_dor_e_start_aceita | D | `amend <id> --field motivo|reproducao|como|quero|para|verify_cmd|fixes|teste --after v --reason r` ⇒ 0, campo gravado; depois `start` ⇒ 0 nas 5 tasks |
| CA-02 | test_ca02_historico_registra_a_emenda | D | o arquivo cita a emenda (campo e motivo) |
| CA-02 | test_ca02_controle_task_iniciada_mantem_regras | R | amend de motivo em task iniciada ⇒ ≠0, campo intacto |
| CA-02 | test_ca02_controle_allowed_paths_continua_emendavel | R | amend allowed_paths (já existia) ⇒ 0 |
| CA-03 | test_ca03_sprint_fecha_com_tasks_dropped | D | SPR-002: drop das 2 tasks, `close SPR-002 --summary` ⇒ 0, sprint em archive/ |
| CA-03 | test_ca03_com_task_aberta_recusa_e_lista | D | 1 drop, close ⇒ ≠0 citando a aberta |
| CA-03 | test_ca03_controle_sem_drop_recusa_listando | R | close sem drop ⇒ ≠0 listando as duas |
| CA-04 | test_ca04_segunda_sprint_aberta_no_epico_recusada_no_new | D | `new sprint --epico E` (e `--dry-run`) com sprint aberta em E ⇒ ≠0 citando a aberta; nada criado |
| CA-04 | test_ca04_start_de_segunda_sprint_no_epico_recusado | D | legado: `start SPR-003` com SPR-001 aberta ⇒ ≠0 citando SPR-001 |
| CA-04 | test_ca04_drop_de_sprint_vazia | D | `drop SPR --reason` em sprint vazia não iniciada ⇒ 0, archive/, DROPPED + motivo, validate ok |
| CA-04 | test_ca04_controle_sprint_em_outro_epico | R | sprints em épicos diferentes criam |
| CA-05 | test_ca05_new_recusa_dor_estatico | D | `new task` com allowed_path reservado, FIX sem fixes/teste, CHORE sem motivo, US sem critério, US sem como/quero/para, BUG sem reproducao, sem verify-cmd ⇒ ≠0 citando o que falta; nada criado (itens + events.jsonl idênticos) |
| CA-05 | test_ca05_new_dry_run_recusa_dor_estatico | D | idem com `--dry-run` |
| CA-05 | test_ca05_controle_campos_certos_criam | R | com os campos certos cria; BUG com teste já verde cria (parte dinâmica fica no start) |
| CA-06 | test_ca06_plan_story_na_sprint | D | `plan US-001 --sprint SPR` ⇒ 0; sprint.json cita US-001; story segue sob `features/`; board mostra US-001 na sprint (mesma linha ou indentada sob ela); `next` cita US-001 |
| CA-06 | test_ca06_close_da_sprint_considera_story | D | depois do plan, close da sprint ⇒ ≠0 citando US-001 |
| CA-06 | test_ca06_sprint_plan_na_arvore_funciona_ou_aponta_plan | D | `sprint plan --goal --budget --stories US-001` ⇒ 0 vinculando, OU ≠0 com `cs-state plan` na saída |
| CA-06 | test_ca06_controle_plan_de_task_na_sprint | R | `plan <task> --sprint` ⇒ 0 |
| CA-07 | test_ca07_textos_sem_add_epic_feature_story | D | CLAUDE.md, .claude/orchestrator.md, .claude/agents/*.md (cartões), .claude/skills/plan-sprint/SKILL.md, Makefile, specialists.mk: 0 linhas `cs-state add epic|feature|story` |
| CA-07 | test_ca07_todo_comando_citado_executa_na_arvore | D | cada `cs-state (add|new) <tipo>`, `plan`, `move`, `sprint plan` citado nesses textos executa (exit 0) num alvo em árvore com argumentos concretos; forma sem mapa (ex.: `add ...`, `add epic`) reprova |
| CA-07 | test_ca07_controle_new_citado_executa | R | varredura acha comandos; `new epico`/`new task` executam |
| CA-08 | test_ca08_version_e_catalogo_0130 | D | VERSION ≥ 0.13.0; catálogo version ≥ 0.13.0, uma entrada `to: "0.13.0"` com ação harness |
| CA-08 | test_ca08_plano_lista_itens_presos_com_comando | D | `cs.py upgrade` ⇒ 0, cita 0.13.0 e cada item preso (9) com `cs-state drop|amend <id>` até 3 linhas abaixo; nada alterado |
| CA-08 | test_ca08_apply_relata_itens_presos_sem_alterar | D | `upgrade --apply` ⇒ 0; saída (ou `.swarm/upgrade-report.md`) idem; arquivos dos itens presos byte a byte iguais |
| CA-08 | test_ca08_controle_upgrade_aplica | R | `upgrade --apply` ⇒ 0 |
| CA-09 | test_ca09_principal_escreve_na_propria_memoria | D | HOME temporário; principal Write/Edit em `<HOME>/.claude/projects/<slug>/memory/{x.md,MEMORY.md}` ⇒ 0 |
| CA-09 | test_ca09_subagente_na_memoria_continua_recusado | R | subagente na mesma memória ⇒ 2 |
| CA-09 | test_ca09_outro_projeto_continua_recusado | R | memória de outro slug ⇒ 2 |
| CA-09 | test_ca09_ponto_ponto_saindo_da_memory_continua_recusado | R | `memory/../x.md`, `memory/../../<outro>/memory/x.md`, `../../../settings.json` ⇒ 2 |
| CA-09 | test_ca09_symlink_na_memory_para_fora_continua_recusado | R | `memory/atalho -> <HOME>/fora` (dir) e `memory/nota.md -> fora/alvo.md` ⇒ 2 |
| CA-09 | test_ca09_controle_fora_da_raiz_continua_recusado | R | `<HOME>/.claude/settings.json`, `projects/<slug>/x.md` (fora de memory/), `<HOME>/fora/y.md` ⇒ 2 |
| CA-09 | test_ca09_controle_escrita_no_projeto | R | principal em .swarm/knowledge ⇒ 0; subagente no allowed_path ⇒ 0 |
| CA-10 | test_ca10_cs_state_version_alvo_instalado / _atualizado | D | `cs-state version` ⇒ 0 e mostra VERSION da skill; run.json5 skill_version == VERSION |
| CA-10 | test_ca10_manifest_version_alvo_instalado / _atualizado | D | `.swarm/harness/MANIFEST.json5` campo `version` == VERSION == run.json5 skill_version |
| CA-10 | test_ca10_controle_run_json5_skill_version | R | run.json5 skill_version == VERSION no alvo novo |

CA-09 e as R: com o HEAD, o guard já recusa tudo fora da raiz, então as R passam hoje; elas pegam a correção LARGA
demais (ver mutação B). CA-10: os dois caminhos ("`cs-state version` ou o MANIFEST") são asserções D SEPARADAS.

## Slug do Claude Code (CA-09)
Regra medida comparando os nomes em `~/.claude/projects/` com os caminhos dos projetos desta máquina (nenhum nome
copiado): `slug = caminho absoluto REAL do projeto com todo caractere fora de [A-Za-z0-9] trocado por '-'` — `/`, `.`
e `_` viram `-` (`/.claude` → `--claude`), sem colapsar repetições; o caminho é o resolvido (`/tmp/...` aparece como
`-private-tmp-...` no macOS). Nenhum nome da listagem contém `.` ou `_`. O oráculo usa
`re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(root))`. A memória é `<HOME>/.claude/projects/<slug>/memory/`;
o teste passa `HOME=<tmp>/home-ca09` ao hook.

## Calibração (2026-10-13, HEAD 21c6164)
- Base: 16/41 nos dois Pythons (3.13.3 e /usr/bin 3.9.6) — as 25 D FAIL por asserção (0 ERROR; erros de fixture
  apareceriam como ERROR no medir.py), as 16 R ok. Ver base.txt.
- Saída vazia reprova: `cs-state version` inexistente (exit 2 do argparse) reprova; plano de upgrade "nada a fazer"
  reprova; recusa sem citar o que falta reprova (CA-01 sem `--reason`, CA-05, CA-06 `sprint plan`).
- Mutação A (cópia da skill = `git archive HEAD` em TMPDIR, `CS_SKILL_DIR`): VERSION 0.13.0 + entrada `to: "0.13.0"`
  {harness} + `version` no MANIFEST (install.py copy_engine) + troca de `add epic|feature|story` por `new …` em
  install.py e orchestrator.md ⇒ viram ok: CA-08 version_e_catalogo, CA-10 manifest_alvo_instalado, CA-07 textos;
  continuam FAIL: CA-07 executa (o `sprint plan` e o `add ...` do CLAUDE.md seguem citados), CA-10 cs-state version,
  CA-08 plano/apply (a mutação não lista itens). Nessa mutação `upgrade --apply` falhou no `emit validate`
  (template mudou sem ação emit) — a R de CA-08 acusou, como deve.
- Mutação B (correção ERRADA, larga): `decide_write` libera toda escrita fora da raiz ⇒ CA-09 D vira ok, mas 5 das
  6 R de CA-09 viram FAIL (subagente, outro projeto, `..`, symlink, fora da raiz). O oráculo não aceita "liberar
  tudo".

## Fora deste oráculo
Oráculos anteriores verdes, suítes, `def` removido: o portão mede. Sprint com task FECHADA (pipeline M2 inteiro) +
DROPPED no CA-03: só DROPPED é exercitado. `start` de 2ª sprint (CA-04) só pelo legado (o `new` novo já recusaria).
O formato do vínculo sprint↔story (campo) é livre: o teste só exige que o id apareça no sprint.json.
Temporários: `$CS_ORACLE_TMP`, senão o TMPDIR do sistema — `local/` não serve porque `harness install` recusa alvo
dentro da própria skill ("alvo é a própria skill"). `CS_ORACLE_KEEP=1` mantém os temporários.
Medir: `python3 medir.py` (e `/usr/bin/python3 medir.py`). Base em base.txt.
