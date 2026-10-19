# INDEX — feature iter27

<!-- gerado por .claude/tools/feature.py a partir dos cabeçalhos das tasks; não edite à mão -->

Progresso: 0/8 · próxima: 01-TASK-ORACULO

| id | entrega | tipo | grupo | CAs | depends | status |
|---|---|---|---|---|---|---|
| 01-TASK-ORACULO | Oráculo da iter27 (CA-01..CA-09), escrito por agente separado | ORACULO | — | CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07, CA-08, CA-09 | — | PENDENTE |
| 02-TASK-FLAGS-EN | Flags en com alias pt no cs-state, cs-auto e cs-route; aviso agregado; dry-run com o item | CORRECAO | G1 | CA-01, CA-02, CA-03, CA-05, CA-07 | 01-TASK-ORACULO (o oráculo congelado é a régua da correção) | PENDENTE |
| 03-TASK-MEMORIA-EN | Forma interna do item e da sessão em inglês; kind epic normalizado na migração | CORRECAO | G1 | CA-08, CA-09 | 02-TASK-FLAGS-EN (mesmos arquivos state.py/auto.py/hcore.py/tree.py: serializado) | PENDENTE |
| 04-TASK-INCLUDE-EMITTED | --include-emitted com alias --allow-outside; caminho exato do log no plano do upgrade | CORRECAO | G2 | CA-04, CA-05 | 01-TASK-ORACULO (o oráculo congelado é a régua da correção) | PENDENTE |
| 05-TASK-TEXTOS-EN | Textos do produto citando só flags en; cs-auto no doctest | CORRECAO | G3 | CA-05, CA-06 | 02-TASK-FLAGS-EN (os nomes en do cs-state/cs-auto/cs-route têm de existir para o doctest parsear), 04-TASK-INCLUDE-EMITTED (idem para --include-emitted) | PENDENTE |
| 06-TASK-VERSAO | 0.15.0: VERSION, migração (harness + item-status + emit) e docs do upgrade | CORRECAO | G3 | CA-09 | 03-TASK-MEMORIA-EN (a item-status normaliza o kind), 05-TASK-TEXTOS-EN (o upgrade reemite os textos já em inglês) | PENDENTE |
| 07-TASK-QA | QA da iter27: portão completo e matriz CA a CA | QA | — | CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07, CA-08, CA-09 | 02-TASK-FLAGS-EN (código a medir), 03-TASK-MEMORIA-EN (código a medir), 04-TASK-INCLUDE-EMITTED (código a medir), 05-TASK-TEXTOS-EN (textos a medir), 06-TASK-VERSAO (a versão que o portão confere) | PENDENTE |
| 08-TASK-REVIEW | Revisão isolada da iter27 | REVIEW | — | CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07, CA-08, CA-09 | 07-TASK-QA (revisa o que a QA aceitou, com as evidências do portão) | PENDENTE |
