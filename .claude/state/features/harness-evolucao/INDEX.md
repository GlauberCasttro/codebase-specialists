# INDEX — feature harness-evolucao

<!-- gerado por .claude/tools/feature.py a partir dos cabeçalhos das tasks; não edite à mão -->

Progresso: 2/14 · próxima: 04-TASK-MEMORIA-SEGURANCA

| id | entrega | tipo | grupo | CAs | depends | status |
|---|---|---|---|---|---|---|
| 01-TASK-ORACULO | Oráculo dos 19 CAs (o roteiro de validação da demanda), por agente separado | ORACULO | — | CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07, CA-08, CA-09, CA-10, CA-11, CA-12, CA-13, CA-14, CA-15, CA-16, CA-17, CA-18, CA-19 | — | DONE |
| 02-TASK-GRAVADOR-JSON | Gravador JSON único, validado e atômico, com leitura de JSON5 legado | CORRECAO | G3 | CA-18 | 01-TASK-ORACULO (o oráculo congelado é a régua da correção) | DONE |
| 03-TASK-MIGRACAO-JSON | Migração JSON5 → JSON pelo upgrade, com detecção no init e contrato revisto | CORRECAO | G3 | CA-19, CA-18 | 02-TASK-GRAVADOR-JSON (usa o gravador e o resolvedor; mesmo grupo), 11-TASK-JSON-ARVORE (a migração do estado em árvore é delegada ao `cs-state migrate json-format` do motor), 06-TASK-CORRECT-ESCOPO (o ARCHITECTURE descreve o escopo do correct entregue), 12-TASK-RELATORIO-AUTOCORRECAO (o ARCHITECTURE descreve o relatório e a autocorreção entregues) | PENDENTE |
| 04-TASK-MEMORIA-SEGURANCA | Segredo redigido, isolamento entre agentes, conflito e promoção, check portátil | CORRECAO | G1 | CA-01, CA-02, CA-05, CA-15 | 01-TASK-ORACULO (o oráculo congelado é a régua da correção) | IN_PROGRESS |
| 05-TASK-MEMORIA-INIT | O init cria, valida e repara a memória do projeto e de cada agente, em JSON | CORRECAO | G1 | CA-03, CA-18 | 04-TASK-MEMORIA-SEGURANCA (edita o mesmo mem.py e o mesmo teste), 02-TASK-GRAVADOR-JSON (os arquivos de memória nascem pelo gravador JSON) | PENDENTE |
| 06-TASK-CORRECT-ESCOPO | correct com escopo, registro do §11.4, reexecução, log de consulta e lição de falha com causa | CORRECAO | G1 | CA-04, CA-06, CA-17 | 05-TASK-MEMORIA-INIT (edita o mesmo mem.py, guard.py e teste; usa o layout criado) | PENDENTE |
| 07-TASK-SHELL-PORTAVEL | Motor executa verify, aceite e selftest sem /bin/sh fixo | CORRECAO | G2 | CA-15 | 01-TASK-ORACULO (o oráculo congelado é a régua da correção) | IN_PROGRESS |
| 08-TASK-CLASSIFY-TEXTOS | Classificação por script com classe épico; textos e CLI só pela árvore | CORRECAO | G2 | CA-07, CA-08 | 07-TASK-SHELL-PORTAVEL (edita o mesmo engine.py e o mesmo teste) | PENDENTE |
| 09-TASK-ARVORE-ESTRUTURA | Avulsa só quando pequena; cardinalidade; dependências, critérios e datas em todo nível | CORRECAO | G2 | CA-09, CA-10, CA-11 | 08-TASK-CLASSIFY-TEXTOS (edita o mesmo state.py e o mesmo teste), 07-TASK-SHELL-PORTAVEL (edita o mesmo tree.py) | PENDENTE |
| 10-TASK-CICLO-VIDA | Propagação do fechamento, reabertura em cascata e nenhum fechamento sem validação | CORRECAO | G2 | CA-12, CA-13, CA-14 | 09-TASK-ARVORE-ESTRUTURA (edita o mesmo tree.py e o mesmo teste; usa o aceite de épico/sprint) | PENDENTE |
| 11-TASK-JSON-ARVORE | Itens, projeção, sessão e autonomia em .json; migração do estado em árvore pelo motor | CORRECAO | G2 | CA-18, CA-19 | 10-TASK-CICLO-VIDA (edita o mesmo tree.py, session.py, auto.py e teste), 02-TASK-GRAVADOR-JSON (grava pelo gravador e resolve nomes pelo resolvedor) | PENDENTE |
| 12-TASK-RELATORIO-AUTOCORRECAO | Relatório final sem mandato, retry estruturado, escalada automática e lessons_checked | CORRECAO | G2 | CA-16, CA-17, CA-06 | 11-TASK-JSON-ARVORE (edita o mesmo state.py e teste; o relatório lê o estado já em JSON), 08-TASK-CLASSIFY-TEXTOS (edita o mesmo engine.py, cmds.py, machines.json5, platforms.py e harness.md), 06-TASK-CORRECT-ESCOPO (usa `mem.mark_applied` e a lição de falha com causa) | PENDENTE |
| 13-TASK-QA | Portão e oráculo, CA a CA, no Windows nativo e no WSL; roteiro de 23 passos | QA | — | CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07, CA-08, CA-09, CA-10, CA-11, CA-12, CA-13, CA-14, CA-15, CA-16, CA-17, CA-18, CA-19 | 03-TASK-MIGRACAO-JSON (última do G3), 06-TASK-CORRECT-ESCOPO (última do G1), 12-TASK-RELATORIO-AUTOCORRECAO (última do G2) | PENDENTE |
| 14-TASK-REVIEW | Revisão isolada da feature | REVIEW | — | CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07, CA-08, CA-09, CA-10, CA-11, CA-12, CA-13, CA-14, CA-15, CA-16, CA-17, CA-18, CA-19 | 13-TASK-QA (revisa sobre o portão verde e a matriz da QA) | PENDENTE |
