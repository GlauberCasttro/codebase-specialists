# INDEX — feature iter19

<!-- gerado por .claude/tools/feature.py a partir dos cabeçalhos das tasks; não edite à mão -->

Progresso: 1/8 · próxima: 02-TASK-FORMATO-CHAVES

| id | entrega | tipo | grupo | CAs | depends | status |
|---|---|---|---|---|---|---|
| 01-TASK-ORACULO | Oráculo da iter19 (CA-01..CA-06), escrito por agente separado | ORACULO | — | CA-01, CA-02, CA-03, CA-04, CA-05, CA-06 | — | DONE |
| 02-TASK-FORMATO-CHAVES | Estado em JSON, ordem de leitura e chaves em inglês | CORRECAO | G1 | CA-01, CA-02, CA-06 | 01-TASK-ORACULO (o oráculo congelado é a régua da correção) | PENDENTE |
| 03-TASK-AMEND-SHOW | amend refletido no arquivo e cs-state show | CORRECAO | G1 | CA-03, CA-04 | 02-TASK-FORMATO-CHAVES (mesmos arquivos tree.py/state.py; o show e o history usam o formato novo) | PENDENTE |
| 04-TASK-MIGRAR-ESTADO | cs-state migrate (formato) por evento encadeado | CORRECAO | G1 | CA-05 | 03-TASK-AMEND-SHOW (mesmos arquivos tree.py/state.py; a migração grava no formato final) | PENDENTE |
| 05-TASK-UPGRADE | migração automática no cs.py upgrade --apply | CORRECAO | G2 | CA-05 | 04-TASK-MIGRAR-ESTADO (o upgrade chama o comando de migração do motor) | PENDENTE |
| 06-TASK-VERSAO-DOCS | 0.11.0, migração no catálogo e documentação do formato | CORRECAO | G3 | CA-06 | 01-TASK-ORACULO (o oráculo congelado é a régua; o texto descreve o comportamento que o oráculo exige) | PENDENTE |
| 07-TASK-QA | Portão e oráculo, CA a CA | QA | — | CA-01, CA-02, CA-03, CA-04, CA-05, CA-06 | 05-TASK-UPGRADE (última correção do motor/upgrade), 06-TASK-VERSAO-DOCS (versão e docs entram no portão) | PENDENTE |
| 08-TASK-REVIEW | Revisão isolada da feature | REVIEW | — | CA-01, CA-02, CA-03, CA-04, CA-05, CA-06 | 07-TASK-QA (a revisão parte do portão verde) | PENDENTE |
