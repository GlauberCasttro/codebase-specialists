# CHECKLIST — criação da feature iter27

<!-- gerado por .claude/tools/feature.py a partir de eventos.jsonl; não edite à mão (o hook nega; `feature.py checklist` detecta adulteração) -->

Demanda: "iter27 — CLI e motor inteiros em inglês (B-72 + B-68 + B-71)"

- [x] **E0 — Pré-condição** · OK 2026-10-19T15:48:22-0300
- [x] **E1 — Analisar a demanda** · OK 2026-10-19T15:49:21-0300 · sha f219130e29a0
- [x] **E2 — Investigação medida** · OK 2026-10-19T17:48:23-0300 · sha ee68d40b925b
- [x] **E3 — FEATURE.md (Bloco A)** · OK 2026-10-19T17:53:27-0300 · sha c5b6ab55556a
- [x] **E4 — Tasks (Bloco B)** · OK 2026-10-19T18:02:49-0300 · sha 06b0632d0ba2
- [x] **E5 — Abertura** · OK 2026-10-19T18:19:35-0300 · sha d3409476016d
- [x] **Abertura** (ac.py init, INDEX, HISTORICO, WORKFLOW) · 2026-10-19T18:19:38-0300

## Handoffs
<!-- APPEND-ONLY: uma entrada por decisão; nunca reescrita -->

### E0 — Pré-condição · CONCLUÍDA 2026-10-19T15:48:22-0300
- Demanda: "iter27 — CLI e motor inteiros em inglês (B-72 + B-68 + B-71)"
- Próxima: E1 — Analisar a demanda

### E1 — Analisar a demanda · CONCLUÍDA 2026-10-19T15:49:21-0300
- Produzido: problema enunciado; FEATURE-ID iter27
- Itens aprovados: 3: chaves internas en de ponta a ponta; tradução pt só na leitura de disco legado; upgrade normaliza kind epico
- Aprovação: "sim"
- Sha: f219130e29a03454ad5a9615308eba17a57998f3759835a2a837c406572fece7
- Próxima: E2 — investigação medida

### E2 — REJEITADA 2026-10-19T15:54:36-0300 · motivo: autocorreção da IA antes de apresentar ao founder: soma de U2 (313→312) e a frase das asserções --allow-outside
- Sha rejeitado: b82d63fb92059cea2abf7d3d4e8821238bc0403cbae0f7cb5769bfd7f253283a

### E2 — Investigação medida · CONCLUÍDA 2026-10-19T17:48:23-0300
- Produzido: investigação medida U1–U4, F1–F12
- Medido: U1 35 linhas/28 nomes; U2 312 citações (311 mudam); U3 28 chaves + kind epico; U4 194 citações em testes, 728 em 52 oráculos (congelados)
- Itens aprovados: subcomandos senha/conferir/anular fora (B-73)
- Aprovação: "ok"
- Sha: ee68d40b925b080ba9e1fe5a557a1aedaf741ffbed2e90a93d592b7302e20c09
- Próxima: E3 — FEATURE.md

### E3 — FEATURE.md (Bloco A) · CONCLUÍDA 2026-10-19T17:53:27-0300
- Produzido: FEATURE.md CA-01..CA-09; contrato PASS
- Itens aprovados: nomes en conforme tabela da E3
- Aprovação: "ok"
- Sha: c5b6ab55556afa440d76ed3e62b32e225808f454fa5f7a2ccdbe2d78955f9c8f
- Próxima: E4 — tasks

### E4 — Tasks (Bloco B) · CONCLUÍDA 2026-10-19T18:02:49-0300
- Produzido: 8 tasks; CA-01..CA-09 cobertos; contrato PASS; sonda OK
- Aprovação: "ok"
- Sha: 06b0632d0ba2f6954cce4cc85ad5352db2a68f273a4fd2ec02ccf84d4564adba
- Próxima: E5 — abertura

### E5 — Abertura · CONCLUÍDA 2026-10-19T18:19:35-0300
- Produzido: plano de abertura
- Aprovação: "ok"
- Sha: d3409476016d95393b9eb128de32ea29a32b07ed035ede67fe3269587eeefe79
- Próxima: oráculo por agente separado

### Abertura · 2026-10-19T18:19:38-0300
- Campanha: campanhas/iter27
- Tasks: 8 · primeira: 01-TASK-ORACULO
- Próxima: oráculo pelo agente separado → oracle freeze → script-aprovacao.sh (founder)
