# ESPEC — oráculo da campanha iter22 (0.12.1): `cs-state show` liberado pelo guard

Defeito de uso real: no alvo, `.swarm/bin/cs-state show <id>` → `cs-guard BLOQUEOU: cs-state show desconhecido`
(o argparse do `state.py` ganhou `show` na 0.11.0, mas o `STATE_SUB` do guard não). Tudo é exercitado pelo caminho
real: o hook pre-bash INSTALADO no alvo (`.swarm/harness/guard.py pre-bash` com o payload JSON da ferramenta Bash;
sem `agent_id` = principal, com `agent_id`/`agent_type` = subagente) e o `.swarm/bin/cs-state` do alvo.

Tipos: **D** = defeito (falha no HEAD 0.12.0, passa com a entrega); **R** = não-regressão/controle (passa sempre;
nome contém `controle|continua|regressao|intacta`).

| CA | Teste (`test_iter22`) | Tipo | Critério observável |
|---|---|---|---|
| CA-01 | `TestCA01.test_ca01_principal_show_pelo_hook_liberado_e_imprime_markdown` | D | hook do principal exit 0, sem "desconhecido"; `cs-state show <id>` exit 0, linha de título Markdown (`#`) com o id, e o título da task |
| CA-01 | `TestCA01.test_ca01_principal_board_continua_liberado_controle` | R | `cs-state board` segue liberado |
| CA-02 | `TestCA02.test_ca02_subagente_show_pelo_hook_liberado` | D | mesmo `show` com payload de subagente: exit 0 e Markdown |
| CA-02 | `TestCA02.test_ca02_subagente_mutacao_continua_barrada` | R | subagente com `close`, `start`, `new task` ⇒ hook exit 2 |
| CA-03 | `TestCA03.test_ca03_todo_subcomando_do_argparse_tem_regra_no_guard` | D | para CADA subcomando listado no `--help` do cs-state instalado (lista `{...}`, ≥ 40, contém `show`), o guard com payload do principal não responde "desconhecido" (recusa explícita como `dispatch`/`legacy-ack` é regra) |
| CA-04 | `TestCA04.test_ca04_version_e_catalogo_0121_com_harness` | D | VERSION ≥ 0.12.1; `version` do catálogo ≥ 0.12.1; exatamente uma entrada `to: "0.12.1"` com ação `harness` |
| CA-04 | `TestCA04.test_ca04_upgrade_de_alvo_0120_lista_0121_e_libera_show` | D | alvo montado pela skill 0.12.0 REAL (`git archive 7fdb431` ou `$CS_OLD_SKILL_DIR`): `cs.py upgrade` exit 0 e cita 0.12.1; `--apply` exit 0, `.swarm/harness/guard.py` muda; depois o `show` passa pelo hook e imprime Markdown |
| CA-04 | `TestCA04.test_ca04_alvo_0120_show_barrado_antes_controle` | R | a fixture reproduz o defeito: no alvo 0.12.0 o hook barra o show com "desconhecido" |
| CA-04 | `TestCA04.test_ca04_docstring_do_caderno_nao_aceita_bloco_desatualizado` | D | docstring de `notebook_text_problems` (via `ast`) não contém "desatualizado mas com selo íntegro também não"; toda frase que citar "desatualizad" diz que é recusado/problema/divergente |

Versão sempre relativa (≥, B-32). Skill sob teste: `$CS_SKILL_DIR` (padrão: raiz do projeto). Temporários em
`$CS_ORACLE_TMP` ou tempdir do Python; nada é escrito no projeto. Fixture: pessoa "Ana"; time da fixture do emit.

Calibração: ver `base.txt` (base no HEAD da abertura, motivo de cada D, correção mínima em cópia ⇒ 9/9, mutação do
CA-03 ⇒ FAIL), nos dois Pythons.

Rodar: `cd campanhas/iter22/oraculo && python3 medir.py` (ou `python3 -m unittest -v test_iter22`).
