# CHECKLIST — criação da feature win-harness

<!-- gerado por .claude/tools/feature.py a partir de eventos.jsonl; não edite à mão (o hook nega; `feature.py checklist` detecta adulteração) -->

Demanda: "B-15: harness de desenvolvimento no Windows nativo (founder: siga, 2026-10-09)"

- [x] **E0 — Pré-condição** · OK 2026-10-09T09:46:23-0300
- [x] **E1 — Analisar a demanda** · OK 2026-10-09T09:49:01-0300 · sha e1218b1021b3
- [x] **E2 — Investigação medida** · OK 2026-10-09T10:05:33-0300 · sha caf9e89cba9a
- [x] **E3 — FEATURE.md (Bloco A)** · OK 2026-10-09T11:08:09-0300 · sha 7330e15bd91d
- [x] **E4 — Tasks (Bloco B)** · OK 2026-10-09T11:20:41-0300 · sha de1b4cf7e749
- [x] **E5 — Abertura** · OK 2026-10-09T11:34:32-0300 · sha 0dbfa02e7e73
- [x] **Abertura** (ac.py init, INDEX, HISTORICO, WORKFLOW) · 2026-10-09T11:34:49-0300

## Handoffs
<!-- APPEND-ONLY: uma entrada por decisão; nunca reescrita -->

### E0 — Pré-condição · CONCLUÍDA 2026-10-09T09:46:23-0300
- Demanda: "B-15: harness de desenvolvimento no Windows nativo (founder: siga, 2026-10-09)"
- Próxima: E1 — Analisar a demanda

### E1 — Analisar a demanda · CONCLUÍDA 2026-10-09T09:49:01-0300
- Produzido: problema enunciado; FEATURE-ID win-harness
- Itens aprovados: 3: .gitattributes eol=lf em .claude/** e campanhas/**; scripts gravam com \n; repositório inteiro fica com a B-14
- Aprovação: "ok"
- Sha: e1218b1021b37f61c94366cef796d899be8eb6bce2c06af4709e9ad1cffc3674
- Próxima: E2 — investigação medida

### E2 — Investigação medida · CONCLUÍDA 2026-10-09T10:05:33-0300
- Produzido: investigação medida: F1–F15 (F16, F17 descartados)
- Medido: harness-dev nativo sem atalho: 63/83 quebram (33 F, 30 E); 11/17 tools UnicodeEncodeError no --help; 22 linhas de código executam python3; 4 hooks python3; 8 arquivos CRLF gravados pelo harness; 13 shell-por-nome nos testes; guard de privacidade 0 achados em C:\Users
- Aprovação: "ok"
- Sha: caf9e89cba9a19cff791904ad7ab06fff3bb2789d163ce27b8a34e8053772f99
- Próxima: E3 — FEATURE.md

### E3 — FEATURE.md (Bloco A) · CONCLUÍDA 2026-10-09T11:08:09-0300
- Produzido: FEATURE.md: 14 CAs com Prova, 28 arquivos no Escopo de escrita; correção da contagem da E2 (10 de 16 tools)
- Itens aprovados: 3: critério de parada 14/14 no Windows nativo e WSL
- Aprovação: "ok"
- Sha: 7330e15bd91d7889f5dd3a0e36b90705f8b37d80793c06d4990a5eb2d26bfd93
- Próxima: E4 — tasks

### E4 — Tasks (Bloco B) · CONCLUÍDA 2026-10-09T11:20:41-0300
- Produzido: 8 tasks: ORACULO, 5 CORRECAO (G1: 02,03 · G2: 04,05 · G3: 06), QA, REVIEW; 14/14 CAs cobertos
- Aprovação: "ok"
- Sha: de1b4cf7e749d46567c75880f2dacb392ec5d46b70e5dc3d93ca4a06e62b9d3c
- Próxima: E5 — abertura

### E5 — Abertura · CONCLUÍDA 2026-10-09T11:34:32-0300
- Produzido: plano de abertura
- Aprovação: "ok"
- Sha: 0dbfa02e7e73075740de05e92b86abd8226c68c7f42a2b19de2cc6a066176ddc
- Próxima: oráculo por agente separado

### Abertura · 2026-10-09T11:34:49-0300
- Campanha: campanhas/win-harness
- Tasks: 8 · primeira: 01-TASK-ORACULO
- Próxima: oráculo pelo agente separado → oracle freeze → script-aprovacao.sh (founder)
