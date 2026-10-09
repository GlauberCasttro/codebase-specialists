# CHECKLIST — criação da feature win-bash

<!-- gerado por .claude/tools/feature.py a partir de eventos.jsonl; não edite à mão (o hook nega; `feature.py checklist` detecta adulteração) -->

Demanda: "fechar feature no Windows: feature.py chama bash pelo nome e cai no bash do WSL (feature.py:548)"

- [x] **E0 — Pré-condição** · OK 2026-10-08T21:50:55-0300
- [x] **E1 — Analisar a demanda** · OK 2026-10-08T21:52:44-0300 · sha 1788df57df98
- [x] **E2 — Investigação medida** · OK 2026-10-08T21:53:52-0300 · sha 27c9ee47eeb7
- [x] **E3 — FEATURE.md (Bloco A)** · OK 2026-10-08T21:54:49-0300 · sha a00c671f5932
- [x] **E4 — Tasks (Bloco B)** · OK 2026-10-08T21:56:25-0300 · sha c57002f7a22d
- [x] **E5 — Abertura** · OK 2026-10-08T22:22:38-0300 · sha bf1aae4d2c3e
- [x] **Abertura** (ac.py init, INDEX, HISTORICO, WORKFLOW) · 2026-10-08T22:22:40-0300

## Handoffs
<!-- APPEND-ONLY: uma entrada por decisão; nunca reescrita -->

### E0 — Pré-condição · CONCLUÍDA 2026-10-08T21:50:55-0300
- Demanda: "fechar feature no Windows: feature.py chama bash pelo nome e cai no bash do WSL (feature.py:548)"
- Próxima: E1 — Analisar a demanda

### E1 — Analisar a demanda · CONCLUÍDA 2026-10-08T21:52:44-0300
- Produzido: problema enunciado; FEATURE-ID win-bash
- Itens aprovados: 2: função em feature.py; B-15 move para estado_lib
- Aprovação: "ok"
- Sha: 1788df57df98d61de83e1f3e3ac15cea71ef3f6a5b65406f39065205dfc4a4f9
- Próxima: E2 — investigação medida

### E2 — Investigação medida · CONCLUÍDA 2026-10-08T21:53:52-0300
- Produzido: 1 chamada muda (feature.py:548); F1-F3 (+F4 descartado)
- Medido: 1 chamada nos tools, 13 nos testes (B-15); which(bash)=Git Bash, subprocess bash=WSL rc 2
- Aprovação: "ok"
- Sha: 27c9ee47eeb7f02d707badc3b11705210792c5c50bf6b90bc418e4695a19901f
- Próxima: E3 — FEATURE.md

### E3 — FEATURE.md (Bloco A) · CONCLUÍDA 2026-10-08T21:54:49-0300
- Produzido: FEATURE.md: 5 CAs com Prova; escopo 2 arquivos; contrato PASS
- Aprovação: "ok"
- Sha: a00c671f5932dfde3e113ddd62d828cbeb589ba2a0e94f329d58528e6889dc06
- Próxima: E4 — tasks

### E4 — Tasks (Bloco B) · CONCLUÍDA 2026-10-08T21:56:25-0300
- Produzido: 4 tasks: ORACULO, BASH (G1), QA, REVIEW; contrato completo PASS, sonda OK
- Aprovação: "ok"
- Sha: c57002f7a22d7b2c6f0e2b777a2b61a917266335d0aaf67a92099d4c915aab83
- Próxima: E5 — abertura

### E5 — Abertura · CONCLUÍDA 2026-10-08T22:22:38-0300
- Produzido: plano de abertura
- Aprovação: "ok"
- Sha: bf1aae4d2c3eb58d1b495623b9e4e6eef6d9c4077d67a1dd6e4cf5891f9cd096
- Próxima: oráculo por agente separado

### Abertura · 2026-10-08T22:22:40-0300
- Campanha: campanhas/win-bash
- Tasks: 4 · primeira: 01-TASK-ORACULO
- Próxima: oráculo pelo agente separado → oracle freeze → script-aprovacao.sh (founder)
