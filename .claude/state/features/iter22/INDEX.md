# INDEX — feature iter22

<!-- gerado por .claude/tools/feature.py a partir dos cabeçalhos das tasks; não edite à mão -->

Progresso: 1/5 · próxima: 02-TASK-GUARD-SHOW

| id | entrega | tipo | grupo | CAs | depends | status |
|---|---|---|---|---|---|---|
| 01-TASK-ORACULO | Oráculo da iter22 (CA-01..CA-04), escrito por agente separado | ORACULO | — | CA-01, CA-02, CA-03, CA-04 | — | DONE |
| 02-TASK-GUARD-SHOW | show em STATE_SUB, varredura subcomandos × guard e docstring do caderno | CORRECAO | G1 | CA-01, CA-02, CA-03, CA-04 | 01-TASK-ORACULO (o oráculo congelado é a régua da correção) | PENDENTE |
| 03-TASK-VERSAO | 0.12.1 com migração no catálogo e nota de upgrade | CORRECAO | G2 | CA-04 | 01-TASK-ORACULO (o oráculo congelado é a régua; o texto descreve o comportamento que o oráculo exige) | PENDENTE |
| 04-TASK-QA | Portão e oráculos, CA a CA | QA | — | CA-01, CA-02, CA-03, CA-04 | 02-TASK-GUARD-SHOW (guard corrigido), 03-TASK-VERSAO (versão e catálogo entram no portão) | PENDENTE |
| 05-TASK-REVIEW | Revisão isolada da feature | REVIEW | — | CA-01, CA-02, CA-03, CA-04 | 04-TASK-QA (a revisão parte do portão verde) | PENDENTE |
