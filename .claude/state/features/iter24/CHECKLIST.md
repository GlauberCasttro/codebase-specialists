# CHECKLIST — criação da feature iter24

<!-- gerado por .claude/tools/feature.py a partir de eventos.jsonl; não edite à mão (o hook nega; `feature.py checklist` detecta adulteração) -->

Demanda: "hotfix de segurança do guard (B-44, B-45, B-47) antes da iter23"

- [x] **E0 — Pré-condição** · OK 2026-10-12T15:42:21-0300
- [x] **E1 — Analisar a demanda** · OK 2026-10-12T15:43:00-0300 · sha e608f9cc630b
- [x] **E2 — Investigação medida** · OK 2026-10-12T15:44:09-0300 · sha e58555f43b9f
- [x] **E3 — FEATURE.md (Bloco A)** · OK 2026-10-12T15:45:50-0300 · sha 5d91513f4ffc
- [x] **E4 — Tasks (Bloco B)** · OK 2026-10-12T15:46:40-0300 · sha fd5ae1e76bf9
- [x] **E5 — Abertura** · OK 2026-10-12T15:47:22-0300 · sha d99d9b717f88
- [x] **Abertura** (ac.py init, INDEX, HISTORICO, WORKFLOW) · 2026-10-12T16:58:55-0300

## Handoffs
<!-- APPEND-ONLY: uma entrada por decisão; nunca reescrita -->

### E0 — Pré-condição · CONCLUÍDA 2026-10-12T15:42:21-0300
- Demanda: "hotfix de segurança do guard (B-44, B-45, B-47) antes da iter23"
- Próxima: E1 — Analisar a demanda

### E1 — Analisar a demanda · CONCLUÍDA 2026-10-12T15:43:00-0300
- Produzido: problema enunciado; FEATURE-ID iter24
- Itens aprovados: 1: B-46 entra; 2: recusar harness por forma indireta + inline/stdin fail-closed; 3: troca de branch fica fora
- Aprovação: "ok"
- Sha: e608f9cc630beb9a616b959ba273651045cfb991038dd70ce3fe98a93db10613
- Próxima: E2 — investigação medida

### E2 — Investigação medida · CONCLUÍDA 2026-10-12T15:44:09-0300
- Produzido: investigação F1–F9
- Medido: 8 portas confirmadas às cegas; 0 oráculos/testes cobrem essas formas
- Aprovação: "ok"
- Sha: e58555f43b9f7db380fa1219e2f65f8ff683c84c04a9f59594282b7603150cc9
- Próxima: E3 — FEATURE.md

### E3 — FEATURE.md (Bloco A) · CONCLUÍDA 2026-10-12T15:45:50-0300
- Produzido: FEATURE.md (7 CAs, contrato PASS)
- Aprovação: "ok"
- Sha: 5d91513f4ffcb75bcf584ec87220ff1f85b4e311950653de7df8f6a1e4525967
- Próxima: E4 — tasks

### E4 — Tasks (Bloco B) · CONCLUÍDA 2026-10-12T15:46:40-0300
- Produzido: 5 tasks (ORACULO, 2 CORRECAO G1/G2, QA, REVIEW)
- Aprovação: "ok"
- Sha: fd5ae1e76bf9ec796638c19a6c3a4ec90b53c2fb4f249c84469f73cb134e4e16
- Próxima: E5 — abertura

### E5 — Abertura · CONCLUÍDA 2026-10-12T15:47:22-0300
- Produzido: plano de abertura (após fechar iter22)
- Aprovação: "ok"
- Sha: d99d9b717f88e5521256676adeb5ed8f93cd5ca84ea9c5aca1536877ca87e376
- Próxima: abrir após /fechar-feature da iter22; oráculo por agente separado

### Abertura · 2026-10-12T16:58:55-0300
- Campanha: campanhas/iter24
- Tasks: 5 · primeira: 01-TASK-ORACULO
- Próxima: oráculo pelo agente separado → oracle freeze → script-aprovacao.sh (founder)
