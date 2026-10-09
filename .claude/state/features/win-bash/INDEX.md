# INDEX — feature win-bash

<!-- gerado por .claude/tools/feature.py a partir dos cabeçalhos das tasks; não edite à mão -->

Progresso: 0/4 · próxima: 01-TASK-ORACULO

| id | entrega | tipo | grupo | CAs | depends | status |
|---|---|---|---|---|---|---|
| 01-TASK-ORACULO | Oráculo da escolha do bash no fechamento | ORACULO | — | CA-01, CA-02, CA-03, CA-04, CA-05 | — | PENDENTE |
| 02-TASK-BASH | bash_exe() no feature.py e conferir_commit usando-a | CORRECAO | G1 | CA-01, CA-02, CA-03, CA-04, CA-05 | 01-TASK-ORACULO (o oráculo congelado é a régua da correção) | PENDENTE |
| 03-TASK-QA | Portão, oráculo e o fechamento real da win-motor-copia | QA | — | CA-01, CA-02, CA-03, CA-04, CA-05 | 02-TASK-BASH (o bash_exe é o que se mede) | PENDENTE |
| 04-TASK-REVIEW | Revisão isolada da escolha do bash | REVIEW | — | CA-01, CA-02, CA-03, CA-04, CA-05 | 03-TASK-QA (revisa o que o portão aprovou) | PENDENTE |
