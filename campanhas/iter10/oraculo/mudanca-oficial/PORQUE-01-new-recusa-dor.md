# PORQUE 01 — `new task` recusa o DoR estático (D-35)

Decisão: D-35 do founder (2026-10-13), na feature iter23 (CA-05, aprovado): `cs-state new task` recusa, ANTES de
criar, a task que não passa no DoR estático do seu tipo — CHORE sem `--motivo` ou sem `--verify-cmd`, FIX sem
`--fixes`, BUG sem `--reproducao`, US sem `--criterio` — citando o campo que falta e sem criar nada.

## O que muda

Seis testes criavam a task inválida pelo `new` e esperavam que o `start` (ou o `check`) recusasse. Com a D-35 a task
inválida nem nasce, então esses testes passam a afirmar a garantia mais forte, pelo novo helper `Base.task_refused`:

- `new task` sai com rc != 0;
- a saída cita o campo que falta (as mesmas palavras que o teste antigo exigia da recusa do `start`/`check`);
- a saída não diz `criado`;
- `snapshot()` do repositório inalterado (nada criado, movido ou alterado).

Testes alterados: `test_bug_sem_teste_que_falha_nao_comeca`, `test_fix_sem_fixes_nao_comeca_e_com_fixes_comeca`,
`test_us_sem_criterio_nao_comeca_e_com_criterio_comeca` (TestTiposDeTask), `test_chore_sem_motivo_nao_comeca`,
`test_chore_sem_verify_cmd_nao_comeca` (TestChore), `test_check_por_tipo` (TestCheckDoR: US sem critério e FIX sem
fixes viram recusa do `new`; o BUG com teste que já passa, que é DoR dinâmico, continua criado e com `check` = 1
"passa"; os itens válidos continuam com `check` = 0 e o `start` da US válida continua passando).

O helper `task` foi refatorado para montar os argumentos em `_task_args` (mesmos argumentos, mesmo comportamento);
`task_refused` reusa essa montagem. Nenhum outro teste foi tocado.

## Por que não enfraquece

A garantia antiga era "a task inválida não começa". A nova é estritamente mais forte: "a task inválida não existe" —
logo não pode começar nem ser despachada. A exigência de citar o que falta foi mantida (mesmas palavras) e ganhou a
prova de que nada foi gravado. As partes positivas ("com o campo certo cria e começa", BUG com teste vermelho começa,
check 0 para itens válidos) seguem intactas. `test_bug_com_teste_que_passa_hoje_nao_comeca` (DoR dinâmico) não mudou.

## Evidência (python3 e /usr/bin/python3, idêntica nos dois)

| teste | antes: HEAD limpo | antes: cópia do portão | depois: cópia do portão | depois: HEAD limpo |
|---|---|---|---|---|
| test_bug_sem_teste_que_falha_nao_comeca | ok | FAIL | ok | FAIL |
| test_fix_sem_fixes_nao_comeca_e_com_fixes_comeca | ok | FAIL | ok | FAIL |
| test_us_sem_criterio_nao_comeca_e_com_criterio_comeca | ok | FAIL | ok | FAIL |
| test_chore_sem_motivo_nao_comeca | ok | FAIL | ok | FAIL |
| test_chore_sem_verify_cmd_nao_comeca | ok | FAIL | ok | FAIL |
| test_check_por_tipo | ok | FAIL | ok | FAIL |

O HEAD limpo falha depois porque cria a task inválida (ex.: `criado SPR-001/01 ... 01-CHORE-ajustar-timeout...`
para CHORE sem motivo) — o comportamento antigo agora é detectado.

Contagem `test_estado_arvore` contra a cópia do portão: 41 ok de 69 antes → 47 ok de 69 depois; os 6 novos ok são
exatamente os testes acima (diff das listas de ok, sem perda em nenhuma outra classe). Contra o HEAD limpo: 47 → 41.
