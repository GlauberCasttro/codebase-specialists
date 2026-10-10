# INDEX — feature win-harness

<!-- gerado por .claude/tools/feature.py a partir dos cabeçalhos das tasks; não edite à mão -->

Progresso: 3/8 · próxima: 03-TASK-SCRIPTS-SHELL

| id | entrega | tipo | grupo | CAs | depends | status |
|---|---|---|---|---|---|---|
| 01-TASK-ORACULO | Oráculo dos 14 CAs, por agente separado | ORACULO | — | CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07, CA-08, CA-09, CA-10, CA-11, CA-12, CA-13, CA-14 | — | DONE |
| 02-TASK-LANCADOR-HOOKS | Lançador de Python e hooks que falham fechados | CORRECAO | G1 | CA-01, CA-02, CA-03, CA-04 | 01-TASK-ORACULO (o oráculo congelado é a régua da correção) | DONE |
| 03-TASK-SCRIPTS-SHELL | carimbo, aprovação .ps1, /install por junção e package | CORRECAO | G1 | CA-08, CA-09, CA-10 | 01-TASK-ORACULO (o oráculo congelado é a régua da correção), 02-TASK-LANCADOR-HOOKS (usa o `_py.sh` e o `PY` do `_comum.sh`, e edita o mesmo `_comum.sh`) | IN_PROGRESS |
| 04-TASK-ESTADO-ENCODING | stdio UTF-8, gravação em LF, bash_exe e perfil temporário | CORRECAO | G2 | CA-04, CA-05, CA-07, CA-11 | 01-TASK-ORACULO (o oráculo congelado é a régua da correção) | DONE |
| 05-TASK-REGUA-PORTAO | Régua e portão com os Pythons da máquina; fechamento com nota | CORRECAO | G2 | CA-06, CA-12 | 01-TASK-ORACULO (o oráculo congelado é a régua da correção), 02-TASK-LANCADOR-HOOKS (o portao.sh usa o PY do _comum.sh), 04-TASK-ESTADO-ENCODING (e2e.py e campanha.py dependem do stdio UTF-8 e da gravação em LF do estado_lib) | IN_PROGRESS |
| 06-TASK-SUITE-HARNESS-DEV | Suíte do harness verde no Windows nativo | CORRECAO | G3 | CA-13, CA-14 | 02-TASK-LANCADOR-HOOKS (os testes chamam os hooks e guards novos), 03-TASK-SCRIPTS-SHELL (testam carimbo, aprovação e install), 04-TASK-ESTADO-ENCODING (usam o bash_exe e o stdio UTF-8), 05-TASK-REGUA-PORTAO (testam portão e régua) | IN_PROGRESS |
| 07-TASK-QA | Portão e oráculo, CA a CA, no Windows nativo e no WSL | QA | — | CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07, CA-08, CA-09, CA-10, CA-11, CA-12, CA-13, CA-14 | 06-TASK-SUITE-HARNESS-DEV (é a última correção; depende transitivamente de 02–05) | IN_PROGRESS |
| 08-TASK-REVIEW | Revisão isolada da feature | REVIEW | — | CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07, CA-08, CA-09, CA-10, CA-11, CA-12, CA-13, CA-14 | 07-TASK-QA (revisa sobre o portão verde e a matriz da QA) | IN_PROGRESS |
