# CHECKLIST — criação da feature harness-evolucao

<!-- gerado por .claude/tools/feature.py a partir de eventos.jsonl; não edite à mão (o hook nega; `feature.py checklist` detecta adulteração) -->

Demanda: "evoluir o harness do produto: classificar demanda (épico estruturado x task avulsa), hierarquia épico/sprint/feature/task, ciclo de vida com propagação, reabertura e arquivo, JSON5→JSON com migração, memória do projeto e dos agentes no init, correct com escopo e aprendizado, validação ponta a ponta com autocorreção — tudo numa feature só"

- [x] **E0 — Pré-condição** · OK 2026-10-09T20:15:41-0300
- [x] **E1 — Analisar a demanda** · OK 2026-10-09T20:17:26-0300 · sha 0dc8c0d2224f
- [x] **E2 — Investigação medida** · OK 2026-10-09T20:20:09-0300 · sha 0939fbd049f7
- [x] **E3 — FEATURE.md (Bloco A)** · OK 2026-10-09T20:23:21-0300 · sha 4cdf25cd341b
- [x] **E4 — Tasks (Bloco B)** · OK 2026-10-09T20:28:24-0300 · sha 0966fa645955
- [x] **E5 — Abertura** · OK 2026-10-09T20:29:06-0300 · sha d927134e4105
- [x] **Abertura** (ac.py init, INDEX, HISTORICO, WORKFLOW) · 2026-10-09T20:29:18-0300

## Handoffs
<!-- APPEND-ONLY: uma entrada por decisão; nunca reescrita -->

### E0 — Pré-condição · CONCLUÍDA 2026-10-09T20:15:41-0300
- Demanda: "evoluir o harness do produto: classificar demanda (épico estruturado x task avulsa), hierarquia épico/sprint/feature/task, ciclo de vida com propagação, reabertura e arquivo, JSON5→JSON com migração, memória do projeto e dos agentes no init, correct com escopo e aprendizado, validação ponta a ponta com autocorreção — tudo numa feature só"
- Próxima: E1 — Analisar a demanda

### E1 — Analisar a demanda · CONCLUÍDA 2026-10-09T20:17:26-0300
- Produzido: problema enunciado; FEATURE-ID harness-evolucao
- Itens aprovados: 1: JSON5→JSON revoga §8-decies (documentos em JSON indent 2; JSONL mantido; migração pelo motor em 2 passos) · 2: correct com --scope agent|project|execution, revoga §8-duodecies · 3: propagação automática só com aceite do pai verde; senão 'pronto para fechar'; reabertura em cascata automática · fronteiras: casos B/C e story mantidos; épico proposto por script e confirmado pelo humano · aprovação DELEGADA pelo founder; etapas E2–E5 revisadas pela IA, não pelo founder
- Aprovação: "ok, aprovação delegada: o Claude aprova E1–E5 da feature harness-evolucao em meu nome"
- Sha: 0dc8c0d2224faf99eeaaf504b2e47c4bde744fe8f7c2ba938bf74923c2f907b4
- Próxima: E2 — investigação medida

### E2 — Investigação medida · CONCLUÍDA 2026-10-09T20:20:09-0300
- Produzido: investigação medida: 132 requisitos, 34 achados F com arquivo:linha, 1 descartado
- Medido: 132 requisitos (22/52/50/8); 22 crítico/alto confirmados; 687 .json5 em 65 .py; 47 arquivos de oráculo citam json5 em 13 campanhas; 0 testes de árvore no produto
- Itens aprovados: aprovação DELEGADA pelo founder; revisão da E2 feita pela IA
- Aprovação: "ok, aprovação delegada: o Claude aprova E1–E5 da feature harness-evolucao em meu nome"
- Sha: 0939fbd049f74c9242029ea7a54c0d93d5a68aa2947c2daf3621ed3a555b0dbc
- Próxima: E3 — FEATURE.md

### E3 — FEATURE.md (Bloco A) · CONCLUÍDA 2026-10-09T20:23:21-0300
- Produzido: FEATURE.md com 19 CAs (DADO/QUANDO/ENTÃO + Prova), contrato PASS
- Itens aprovados: aprovação DELEGADA pelo founder; FEATURE.md revisado pela IA; CA-01..CA-19
- Aprovação: "ok, aprovação delegada: o Claude aprova E1–E5 da feature harness-evolucao em meu nome"
- Sha: 4cdf25cd341bee1f3b9cae840fc3cba54ab768777eac7c424ae363a9d8237b50
- Próxima: E4 — decompor em tasks

### E4 — Tasks (Bloco B) · CONCLUÍDA 2026-10-09T20:28:24-0300
- Produzido: 14 tasks: ORACULO, 10 CORRECAO em G1 (04-06 memória), G2 (07-12 árvore), G3 (02-03 JSON), QA, REVIEW; contrato completo PASS; sonda OK
- Itens aprovados: aprovação DELEGADA pelo founder; decomposição revisada pela IA
- Aprovação: "ok, aprovação delegada: o Claude aprova E1–E5 da feature harness-evolucao em meu nome"
- Sha: 0966fa6459557029e37ead58fdc166f135e10920e1ea57d280838bcc448bd57e
- Próxima: E5 — abertura

### E5 — Abertura · CONCLUÍDA 2026-10-09T20:29:06-0300
- Produzido: plano de abertura
- Itens aprovados: aprovação DELEGADA pelo founder; plano de abertura revisado pela IA; execução só depois da win-harness
- Aprovação: "ok, aprovação delegada: o Claude aprova E1–E5 da feature harness-evolucao em meu nome"
- Sha: d927134e4105015752b13927d99213297d5df27adbdb3f0df6d1c5084b5a965a
- Próxima: oráculo por agente separado (depois da win-harness)

### Abertura · 2026-10-09T20:29:18-0300
- Campanha: campanhas/harness-evolucao
- Tasks: 14 · primeira: 01-TASK-ORACULO
- Próxima: oráculo pelo agente separado → oracle freeze → script-aprovacao.sh (founder)
