# ESPEC — oráculo campanha-iter18 (achados de uso real: segunda cobaia .NET)

Oráculo `test_iter18.py` (unittest puro, Python 3.9+, repos git temporários, CLI real em subprocesso — nada de mock
do motor). Skill sob teste: `$CS_SKILL_DIR` (padrão: a raiz deste projeto). Rodar (desta pasta):
`python3 -m unittest -v test_iter18`; placar por requisito: `python3 medir.py`. Base medida em `base.txt`
(HEAD d61527e, python3 3.13 e /usr/bin/python3 3.9.6, resultados iguais): **26 D falham, 12 R passam**.

Legenda: **D** = defeito (falha no HEAD d61527e, passa depois da correção). **R** = não-regressão/sem brecha
(passa nos dois). Recusa = exit ≠ 0 e ≠ 2 (2 = argparse). `medir.py` classifica R pelo nome do teste
(`regressao|controle|continua|intacta`).

Fixture comum (`TreeRepo`): repo git com estado em árvore (`cs-state init`), time dev-billing (`src/billing/**`),
dev-users (`src/users/**`), gates reviewer/security; `.gitignore` de projeto .NET (`bin/`, `obj/`); tasks avulsas
(`cs-state new task --avulsa`) levadas pela M2 inteira (start → dispatch --manual → submit → verify → review →
accept). Escopo da task A = `src/billing/discount/**` (diretório estreito; não colide com R7).

| req | D (hoje) | R (hoje) | total hoje |
|---|---|---|---|
| R1 tree_sha256 × artefato ignorado | 0/1 | 4/4 | 4/5 |
| R2 reverify em VERIFIED/REVIEWED | 0/5 | 1/1 | 1/6 |
| R3 cartão do gate registra veredito | 0/2 | 2/2 | 2/4 |
| R4 orquestrador não dita veredito | 0/3 | — | 0/3 |
| R5 pre-commit só depois do ACCEPTED | 0/4 | 3/3 | 3/7 |
| R6 git somente leitura no bashscan | 0/2 | 1/1 | 1/3 |
| R7 allowed_paths ≠ território inteiro | 0/5 | 1/1 | 1/6 |
| R8 versão 0.10.0 | 0/4 | — | 0/4 |
| total | 0/26 | 12/12 | 12/38 |

## R1 — tree_sha256 ignora artefato ignorado pelo git
Defeito: `engine.files_in_scope` percorre o FS (inclui `bin/`/`obj/`), `cmds.verify` grava `tree_files`/`tree_sha256`
com eles e `g_tree` (`tree_unchanged`) recusa o accept quando a build de OUTRA task regrava o artefato.
Observação de critério: `tree_files` é fixado no verify; arquivo criado DEPOIS do verify não entra no hash hoje — por
isso o arquivo ignorado do teste já existe no verify (`obj/x.dll`) e é regravado depois (e um novo `bin/…` é criado).
"Outra task compilou" é simulado (escrita direta do artefato), como o requisito permite.

| Requisito | Teste | Tipo |
|---|---|---|
| artefato IGNORADO no escopo regravado/criado depois do verify não trava o accept | `TestR1….test_r1a_artefato_ignorado_regravado_nao_trava_o_accept` | D |
| arquivo RASTREADO no escopo (fora dos files_changed) mudado → accept recusado | `test_r1b_arquivo_rastreado_mudado_continua_recusando` | R |
| arquivo dos files_changed mudado → accept recusado | `test_r1b_files_changed_mudado_continua_recusando` | R |
| não rastreado e NÃO ignorado (existente antes do dispatch) mudado → accept recusado | `test_r1c_nao_rastreado_nao_ignorado_continua_contando` | R |
| controle: árvore intacta → accept | `test_r1_controle_arvore_intacta_aceita` | R |

Sem git o comportamento atual fica (o verify já exige git: `require_git_diff_check`) — não testado.

## R2 — sem impasse em VERIFIED/REVIEWED (`cs-state reverify --task`)
Impasse: verify, review PASS, a árvore muda no escopo FORA dos files_changed (`helper.py`, rastreado) → accept
recusado e, hoje, nenhuma transição sai de VERIFIED/REVIEWED (reverify só de REJECTED|ESCALATED).

| Requisito | Teste | Tipo |
|---|---|---|
| a recusa do accept (g_tree) cita `reverify` | `test_r2_accept_recusado_aponta_reverify` | D |
| `cs-state why <task>` no impasse cita `reverify` | `test_r2_why_aponta_reverify` | D |
| REVIEWED + files_changed iguais: reverify → accept passa SEM nova review; `attempts` não muda | `test_r2_reverify_preserva_reviews_quando_files_changed_iguais` | D |
| VERIFIED (sem review) com árvore mudada: reverify → review → accept | `test_r2_reverify_de_verified_sem_review` | D |
| files_changed mudou: reverify → accept recusado (review antiga invalidada) → nova review PASS → accept | `test_r2_reverify_invalida_reviews_quando_files_changed_mudaram` | D |
| árvore intacta: reverify de VERIFIED/REVIEWED **recusado**; o estado fica e o accept segue normal | `test_r2_reverify_com_arvore_intacta_recusado` | R |

**Critério escolhido:** reverify de VERIFIED/REVIEWED só quando `tree_unchanged` falharia (árvore intacta → recusa,
ex.: "árvore não mudou"). Hoje já é recusado (transição inexistente), por isso é R — guarda contra a correção abrir
reverify incondicional. "Preservar reviews" = o accept depois do reverify passa sem nova review; "invalidar" = o
accept recusa até nova review PASS. Não se fixa o estado intermediário (VERIFIED/REVIEWED) nem a redação.

## R3 — cartão do gate manda registrar o veredito (`scripts/emit/render.py` `verdict_lines`)
Emissão real (`emit.cli`, fixture `scripts/emit/tests/fixture.py`, 4 plataformas). Cartões do gate:
`.claude/agents/reviewer.md`, `.cursor/agents/reviewer.md`, `.github/agents/reviewer.agent.md`,
`.codex/agents/reviewer.toml`. "Bloco" = parágrafo/item de lista com espaços normalizados.

| Requisito | Teste | Tipo |
|---|---|---|
| contém `cs-state review --task` e, no mesmo bloco, `--verdict` | `test_r3_gate_manda_registrar_com_cs_state_review` | D |
| um bloco liga só-leitura (`só leitura`/`somente leitura`/`read-only`) a não editar/alterar e ao registro (`cs-state`/review/veredito); `abstain` aparece | `test_r3_so_leitura_e_nao_editar_e_comandos_de_estado_sao_do_gate` | D |
| enum `PASS` \| `FAIL` \| `NEEDS_SPECIALIST` continua | `test_r3_regressao_enum_de_veredito_continua` | R |
| cartão de dev não recebe `cs-state review --task` | `test_r3_regressao_dev_nao_recebe_comando_de_gate` | R |

## R4 — orquestrador proíbe ditar o veredito ao gate
Conferido no template `assets/templates/orchestrator.md` e nos 4 emitidos (`.claude/orchestrator.md`,
`.cursor/rules/cs-orchestrator.mdc`, `.github/copilot-instructions.md`, `AGENTS.md`). Frases-chave por bloco:

| Requisito | Teste | Tipo |
|---|---|---|
| bloco com `Nunca` + `veredito` + `gate` + ditar/escrever/redigir/passar | `test_r4_nunca_dita_o_veredito_ao_gate` | D |
| bloco com redespachar (`redespach`/`despache de novo`/`novo despacho`) + `revis` + id `.dN` (ou `mesmo id`) | `test_r4_redespacha_revisao_independente_com_mesmo_id` | D |
| bloco com negação + usuário/humano + `carimb` | `test_r4_nao_pede_ao_usuario_para_carimbar` | D |

## R5 — pre-commit (`guard.py check-diff --staged`) só depois do ACCEPTED
Investigação: `check_diff` libera allowed_paths de delegação em DISPATCHED/RETURNED/VERIFIED/REVIEWED e de ACCEPTED
com a task aberta (U5 da iter16). O caso real (commit em REVIEWED) passa. Task avulsa com allowed_paths =
`src/billing/discount/rate.py`; o arquivo é staged (`git add`) e o pre-commit roda com `--staged`.

| Requisito | Teste | Tipo |
|---|---|---|
| DISPATCHED barra (`FORA: <arquivo> `, exit 1) | `test_r5_dispatched_barra` | D |
| RETURNED barra | `test_r5_returned_barra` | D |
| VERIFIED barra | `test_r5_verified_barra` | D |
| REVIEWED barra (caso real) | `test_r5_reviewed_barra_caso_real` | D |
| ACCEPTED com task aberta libera | `test_r5_regressao_accepted_aberta_libera` | R |
| só `.swarm/**` staged (task REVIEWED em voo) libera | `test_r5_regressao_estado_do_harness_liberado` | R |
| task fechada barra | `test_r5_regressao_fechada_barra` | R |

**Critério:** só o modo `--staged` (o pre-commit) é exigido. O modo sem `--staged` (árvore de trabalho, CI) não é
fixado por este oráculo — a correção pode manter o trabalho em voo livre lá. O U5 da iter16 (oráculo
`campanhas/iter16/oraculo`) continua valendo e deve ser rodado junto no portão.

## R6 — bashscan: git somente leitura
API pública usada pelo guard: `bashscan.git_effect(sub)` (`read`|`lead`|`tree`) + hook real `guard.py pre-bash`
do orquestrador (sem agent_id).

| Requisito | Teste | Tipo |
|---|---|---|
| `check-ignore`, `ls-remote`, `count-objects` → `read` | `test_r6_bashscan_classifica_como_leitura` | D |
| o guard não bloqueia `git check-ignore -v …`, `git ls-remote origin`, `git count-objects -v` | `test_r6_guard_libera_para_o_orquestrador` | D |
| `checkout/reset/clean/gc/stash` continuam `tree`; `status/log/diff/ls-files` `read` | `test_r6_regressao_escrita_continua_fora` | R |

## R7 — allowed_paths igual ao território inteiro é recusado
Investigação: `engine.brief_problems` (guard `brief_valid`, usado no `ready` da M2, que o `cs-state start` da árvore
roda; `cs-state check` roda o start em seco) só recusa `**`, `src/**` etc. e aceita `src/billing/**` para
dev-billing. O gerador da árvore (`tree.new_story`) põe `territory_paths` como allowed_paths da story simples sem
`--allowed-path` e SEMPRE nas tasks da story composta. `cs-state amend` hoje só acha task M2 (item da árvore não
iniciado → "task inexistente").

| Requisito | Teste | Tipo |
|---|---|---|
| task avulsa com `src/billing/**`: `check` exit ≠ 0; `start` recusado com dica `amend` + `allowed_paths`; nenhuma M2 criada | `test_r7_territorio_inteiro_recusado_no_start_e_no_check` | D |
| glob que contém o território (`src/billing/**/*`, `src/billing/`): recusado na criação OU no start com a dica | `test_r7_glob_que_contem_o_territorio_recusado` | D |
| a dica é acionável: `cs-state amend <item> --field allowed_paths --after '[arquivo]' --reason …` no item recusado → `start` passa | `test_r7_amend_sugerido_destrava` | D |
| gerador: `new story` sem `--allowed-path` (simples e composta) não deixa task iniciável com o território inteiro | `test_r7_gerador_story_sem_allowed_path_nao_inicia_com_territorio` | D |
| fluxo M1 (`cmds.add_task(..., ready=True)`, board plano): `src/billing/**` → `Refused` com a dica; arquivo explícito passa | `test_r7_despacho_legado_recusa_territorio_inteiro` | D |
| arquivo explícito (`src/billing/total.py`) e diretório estreito (`src/billing/discount/**`) passam no check e no start | `test_r7_regressao_arquivo_explicito_e_diretorio_estreito_passam` | R |

**Critérios escolhidos:**
- "Contém o território inteiro" = o glob casa todo arquivo que o território casa (igual, `X/**/*`, `X/`).
- Gerador: aceita QUALQUER das saídas razoáveis — (a) `new story` recusa e pede `--allowed-path`; (b) cria o item
  com allowed_paths estreitado (ex.: arquivo citado na origem) — o teste pula itens cujo allowed_paths ≠ território;
  (c) cria com o território, mas o item não passa no `check` nem no `start`. O que não pode: task iniciável com o
  território inteiro.
- Como a mensagem tem de sugerir `cs-state amend --field allowed_paths`, a sugestão tem de funcionar no ponto em que é
  dada (item da árvore ainda não iniciado). Se a correção preferir outra saída para itens da árvore, isso é mudança
  oficial deste oráculo (`oracle change`), não remendo no teste.

## R8 — versão 0.10.0
| Requisito | Teste | Tipo |
|---|---|---|
| `VERSION` = `0.10.0` | `test_r8_version` | D |
| `references/migrations.json5`: `version: "0.10.0"`, uma migração `to: "0.10.0"` (a última) com actions ⊇ {harness, emit} | `test_r8_migrations` | D |
| `README.md` cita 0.10.0 | `test_r8_readme` | D |
| `docs/09-upgrade.md` tem título `Migração 0.10.0` | `test_r8_docs_upgrade` | D |
