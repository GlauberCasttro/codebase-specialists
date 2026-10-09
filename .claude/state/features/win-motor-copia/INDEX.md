# INDEX — feature win-motor-copia

<!-- gerado por .claude/tools/feature.py a partir dos cabeçalhos das tasks; não edite à mão -->

Progresso: 5/5 · próxima: —

| id | entrega | tipo | grupo | CAs | depends | status |
|---|---|---|---|---|---|---|
| 01-TASK-ORACULO | Oráculo da cópia do motor corrigido | ORACULO | — | CA-01, CA-02, CA-03, CA-04, CA-05 | — | DONE |
| 02-TASK-MOTOR | Copiar o motor de 30e2da6, reaplicar o layout, ORIGEM e eol=lf | CORRECAO | G1 | CA-01, CA-02, CA-04, CA-05 | 01-TASK-ORACULO (o oráculo congelado é a régua da correção) | DONE |
| 03-TASK-MATCHER | Hook de aprovação do projeto vigia também a ferramenta PowerShell | CORRECAO | G2 | CA-03 | 01-TASK-ORACULO (o oráculo congelado é a régua da correção) | DONE |
| 04-TASK-QA | Portão e oráculo, CA a CA, nos dois ambientes | QA | — | CA-01, CA-02, CA-03, CA-04, CA-05 | 02-TASK-MOTOR (o motor copiado é o que se mede), 03-TASK-MATCHER (o matcher completa o CA-03) | DONE |
| 05-TASK-REVIEW | Revisão isolada da cópia do motor e do matcher | REVIEW | — | CA-01, CA-02, CA-03, CA-04, CA-05 | 04-TASK-QA (revisa o que o portão aprovou) | DONE |
