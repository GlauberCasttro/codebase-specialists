# CHECKLIST — criação da feature win-motor-copia

<!-- gerado por .claude/tools/feature.py a partir de eventos.jsonl; não edite à mão (o hook nega; `feature.py checklist` detecta adulteração) -->

Demanda: "recopiar o motor corrigido no Windows (auto-correcao release/version-windows) para .claude/tools/ac/ (B-16)"

- [x] **E0 — Pré-condição** · OK 2026-10-08T12:28:44-0300
- [x] **E1 — Analisar a demanda** · OK 2026-10-08T12:30:07-0300 · sha 6a5e7f19c29f
- [x] **E2 — Investigação medida** · OK 2026-10-08T12:32:26-0300 · sha 6d079be6d665
- [x] **E3 — FEATURE.md (Bloco A)** · OK 2026-10-08T12:39:26-0300 · sha 1a993d1e5f27
- [x] **E4 — Tasks (Bloco B)** · OK 2026-10-08T12:41:27-0300 · sha 65728f316db2
- [x] **E5 — Abertura** · OK 2026-10-08T12:42:35-0300 · sha dc6505960692
- [x] **Abertura** (ac.py init, INDEX, HISTORICO, WORKFLOW) · 2026-10-08T12:42:51-0300

## Handoffs
<!-- APPEND-ONLY: uma entrada por decisão; nunca reescrita -->

### E0 — Pré-condição · CONCLUÍDA 2026-10-08T12:28:44-0300
- Demanda: "recopiar o motor corrigido no Windows (auto-correcao release/version-windows) para .claude/tools/ac/ (B-16)"
- Próxima: E1 — Analisar a demanda

### E1 — Analisar a demanda · CONCLUÍDA 2026-10-08T12:30:07-0300
- Produzido: problema enunciado; FEATURE-ID win-motor-copia
- Itens aprovados: 3: matcher do hook do projeto para Bash|PowerShell; python3 do comando fica para B-15
- Aprovação: "ok"
- Sha: 6a5e7f19c29f27a16acaf6955fa1c60a12dd02be30c3362d0ed12cf022b0421f
- Próxima: E2 — investigação medida

### E2 — Investigação medida · CONCLUÍDA 2026-10-08T12:32:26-0300
- Produzido: investigação medida: 5 arquivos mudam, 4 references iguais, 10 consumidores intactos; F1-F5 (+F6 descartado)
- Medido: fonte +440/-44 em 3 arquivos; 8/8 arquivos do motor w/crlf; test_origem vermelho hoje (de78cc5a != fbd0f1cd); selftest 83/83
- Aprovação: "ok"
- Sha: 6d079be6d6657b3835b8085e06a2ae955bed11ade5a7062bbf25911e0c275c31
- Próxima: E3 — FEATURE.md

### E3 — FEATURE.md (Bloco A) · CONCLUÍDA 2026-10-08T12:39:26-0300
- Produzido: FEATURE.md: 5 CAs com Prova, escopo 6 arquivos, parada numérica; contrato PASS
- Aprovação: "ok"
- Sha: 1a993d1e5f27768f079deee4eb1aa35659f36d3a73aa971220295e176626c012
- Próxima: E4 — tasks

### E4 — Tasks (Bloco B) · CONCLUÍDA 2026-10-08T12:41:27-0300
- Produzido: 5 tasks: ORACULO, MOTOR (G1), MATCHER (G2), QA, REVIEW; contrato completo PASS, sonda OK
- Aprovação: "ok"
- Sha: 65728f316db278b332625c7bbdb3ed0b39c52873f6e649eebc7cd442782de3d2
- Próxima: E5 — abertura

### E5 — Abertura · CONCLUÍDA 2026-10-08T12:42:35-0300
- Produzido: plano de abertura
- Aprovação: "ok"
- Sha: dc650596069298825d9436486f043833f8e71fc246639844ab6284aee48f5cea
- Próxima: oráculo por agente separado

### Abertura · 2026-10-08T12:42:51-0300
- Campanha: campanhas/win-motor-copia
- Tasks: 5 · primeira: 01-TASK-ORACULO
- Próxima: oráculo pelo agente separado → oracle freeze → script-aprovacao.sh (founder)
