# Oráculo iter25 (hotfix 0.13.1) — `status` gravado no arquivo de cada item da árvore

Exercita a skill num alvo REAL em modo árvore: fixture do emit + `cs.py init` + `harness install` + `emit` +
`cs-state init`. Comandos pelo `cs-state` do próprio alvo (`.swarm/harness/state.py --root <alvo>`, o que
`.swarm/bin/cs-state` chama). O status DERIVADO é `tree.status_of(tree.load_view(alvo), item)` importado de
`<alvo>/.swarm/harness/` num subprocesso: o derivado vem do MESMO motor que gravou o arquivo.

Fixtures (pessoa = Ana; caminhos só em TMPDIR/`$CS_ORACLE_TMP`):
- **nova** (skill sob teste): EPC ativo › SPR ativa › FEA ativa (`--sprint`) com story; 2 tasks US direto na
  sprint; 1 task US no backlog. Cada teste usa um clone (copytree).
- **legado** (CA-05): alvo instalado pela skill 0.13.0 REAL (`git archive 3eed3b4`, ou `$CS_OLD_SKILL_DIR`), mesma
  árvore + task iniciada (state/), task e sprint vazia descartadas (archive/), task no backlog. A fixture confere
  que há itens nas 3 zonas. Depois: `cs.py upgrade` e `upgrade --apply --allow-outside` (2×) pela skill sob teste.

CANON (D-37, mudança oficial 01, definido no oráculo): o `status` GRAVADO é o código canônico em inglês; a exibição
(`tree.status_of`, board/next/show) segue em português. Mapa: "a fazer"→`TODO`, "backlog"→`BACKLOG`,
"ativo"→`ACTIVE`, "fechada"/"fechado"→`DONE`, "descartada"/"descartado"→`DROPPED`, `<M2>/<despacho>`→igual.

Tipo: D = defeito (falha no HEAD 3eed3b4 / 0.13.0, passa com a entrega); R = controle (passa sempre; nome com
`controle|continua|intacta`). Versão sempre relativa (≥ 0.13.1).

| CA | Teste | Tipo | Critério |
|---|---|---|---|
| CA-01 | test_ca01_status_no_arquivo_igual_ao_derivado | D | épico, sprint, feature, story, task da sprint e do backlog: `status` do arquivo == CANON(derivado) |
| CA-01 | test_ca01_literais_no_arquivo | D | task na sprint `TODO`; backlog `BACKLOG`; épico/sprint/feature `ACTIVE` |
| CA-01 | test_ca01_controle_derivado_continua | R | a derivação (exibição pt) de hoje dá "ativo"/"a fazer"/"backlog" (a referência do oráculo não é vácua) |
| CA-01 | test_ca01_controle_exibicao_continua_em_portugues | R | `board` mostra a task "a fazer" e o backlog "backlog" (sem `[TODO]`); `show` da task mostra "a fazer" — só o dado mudou |
| CA-02 | test_ca02_status_acompanha_cada_transicao_m2 | D | start, dispatch (`--manual --model sonnet`), submit (`--actor dev-billing`), verify, review (`--by reviewer --verdict PASS`), accept: depois de CADA comando, arquivo == CANON(derivado) |
| CA-02 | test_ca02_so_o_status_mudou_regrava | D | nas transições que só mudam o M2 (dispatch/verify/review/accept) o arquivo é regravado |
| CA-02 | test_ca02_controle_derivado_muda_a_cada_passo | R | o derivado assume ≥ 4 valores `<M2>/<despacho>` no fluxo |
| CA-03 | test_ca03_drop_de_task_nao_iniciada_descartada | D | `drop --reason` ⇒ archive/, arquivo `DROPPED`, derivado "descartada" |
| CA-03 | test_ca03_close_de_task_aceita_fechada | D | M2 até accept + `close --summary` ⇒ archive/, arquivo `DONE`, derivado "fechada" |
| CA-03 | test_ca03_drop_de_sprint_vazia_descartado | D | sprint vazia `drop` ⇒ archive/, arquivo `DROPPED`, derivado "descartado" |
| CA-03 | test_ca03_close_de_sprint_fechado | D | sprint com task descartada `close` ⇒ archive/, arquivo `DONE`, derivado "fechado"; árvore toda coerente |
| CA-04 | test_ca04_status_editado_a_mao_acusado | D | arquivo com `TODO` trocado para `DONE` (código válido, errado) ⇒ `validate --strict` ≠ 0, saída cita o ID e o valor certo `TODO` |
| CA-04 | test_ca04_status_fora_do_vocabulario_acusado | D | arquivo com "a fazer" (exibição pt, fora do vocabulário) ⇒ `validate --strict` ≠ 0, saída cita o ID e `TODO` |
| CA-04 | test_ca04_controle_sem_edicao_valida | R | sem edição (e depois de M2 + drop) `validate --strict` sai 0 — o campo novo não vira falso "edição à mão" |
| CA-05 | test_ca05_version_e_catalogo_0131 | D | VERSION ≥ 0.13.1; exatamente uma entrada `to: "0.13.1"` em references/migrations.json5 |
| CA-05 | test_ca05_plano_lista_0131 | D | `cs.py upgrade` ⇒ 0, cita "0.13.1", não altera nenhum arquivo |
| CA-05 | test_ca05_apply_grava_status_em_todos_os_itens | D | apply ⇒ 0; mesmo conjunto de itens; TODO item (3 zonas) com `status` == CANON(derivado) |
| CA-05 | test_ca05_apply_outros_campos_e_eventos_intacta | R | nenhum item muda de lugar nem de campo além de `status`; `.swarm/events.jsonl` idêntico em BYTES |
| CA-05 | test_ca05_validate_strict_continua_depois_do_upgrade | R | `validate --strict` sai 0 depois do apply |
| CA-05 | test_ca05_segundo_apply_continua_idempotente | R | 2º apply ⇒ 0 e não altera item nem events.jsonl |
| CA-05 | test_ca05_controle_fixture_sem_status | R | o alvo 0.13.0 tem itens nas 3 zonas e nenhum com `status` |

Critério de eventos escolhido (CA-05): o MAIS estrito — `events.jsonl` idêntico em bytes, nenhum evento de
migração. Um desenho razoável o cumpre: o `status` é derivado (não entra na projeção nem no replay, RNF-02), então
regravá-lo no arquivo não precisa de evento. Os R de CA-05 passam hoje porque a 0.13.0 não regrava nada; com a
entrega eles provam que a regravação não toca outro campo nem a cadeia.

Calibração (base.txt, 2 Pythons): no HEAD todos os D falham por ASSERÇÃO (FAIL, 0 ERROR), os R passam.
Mutação simulada (cópia da skill em TMPDIR, `hcore.write_item_json` grava `status` só pela zona/tipo, ignorando o
M2 — "status só na criação"): CA-01 e CA-03 passam, CA-02 continua FAIL nos 2 D (status do arquivo fica `TODO`
enquanto o derivado é `<M2>/<despacho>`), CA-04 falha (validate acusa o campo) e CA-05 falha (sem migração).

Rodar: `cd campanhas/iter25/oraculo && python3 medir.py` (ou `python3 -m unittest -v test_iter25`).
