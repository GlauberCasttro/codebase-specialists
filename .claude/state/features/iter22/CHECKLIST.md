# CHECKLIST — criação da feature iter22

<!-- gerado por .claude/tools/feature.py a partir de eventos.jsonl; não edite à mão (o hook nega; `feature.py checklist` detecta adulteração) -->

Demanda: "B-35: corrigir já o bloqueio do cs-state show pelo guard, como versão 0.12.1 rápida"

- [x] **E0 — Pré-condição** · OK 2026-10-12T14:45:18-0300
- [x] **E1 — Analisar a demanda** · OK 2026-10-12T14:49:14-0300 · sha 2c548f272919
- [x] **E2 — Investigação medida** · OK 2026-10-12T14:50:16-0300 · sha 868e92ed9cca
- [x] **E3 — FEATURE.md (Bloco A)** · OK 2026-10-12T14:51:08-0300 · sha 8eeadeec59f3
- [x] **E4 — Tasks (Bloco B)** · OK 2026-10-12T14:52:09-0300 · sha 9fad8c883c19
- [x] **E5 — Abertura** · OK 2026-10-12T14:54:10-0300 · sha a51dbe136c89
- [x] **Abertura** (ac.py init, INDEX, HISTORICO, WORKFLOW) · 2026-10-12T14:54:10-0300

## Handoffs
<!-- APPEND-ONLY: uma entrada por decisão; nunca reescrita -->

### E0 — Pré-condição · CONCLUÍDA 2026-10-12T14:45:18-0300
- Demanda: "B-35: corrigir já o bloqueio do cs-state show pelo guard, como versão 0.12.1 rápida"
- Próxima: E1 — Analisar a demanda

### E1 — Analisar a demanda · CONCLUÍDA 2026-10-12T14:49:14-0300
- Produzido: problema enunciado; FEATURE-ID iter22
- Itens aprovados: 1: varredura subcomandos×guard: sim; 2: 0.12.1 com migração no catálogo: sim
- Aprovação: "ok"
- Sha: 2c548f2729199c628c916023dff9588e69a4933391579c23ae33bc3c3d570bc8
- Próxima: E2 — investigação medida

### E2 — Investigação medida · CONCLUÍDA 2026-10-12T14:50:16-0300
- Produzido: investigação medida F1–F6
- Medido: 48 subcomandos; 42 no guard + 5 com regra explícita + 1 sem nada (show); 0 testes passam o show pelo hook
- Aprovação: "ok"
- Sha: 868e92ed9cca34d3834d70feec902d105c57509cfd974f4639f6ebe820bdd458
- Próxima: E3 — FEATURE.md

### E3 — FEATURE.md (Bloco A) · CONCLUÍDA 2026-10-12T14:51:08-0300
- Produzido: FEATURE.md (4 CAs, contrato PASS)
- Aprovação: "ok"
- Sha: 8eeadeec59f384f34794257f2f010615c2697224700609cc27ac8c572689a77b
- Próxima: E4 — tasks

### E4 — Tasks (Bloco B) · CONCLUÍDA 2026-10-12T14:52:09-0300
- Produzido: 5 tasks (ORACULO, 2 CORRECAO G1/G2, QA, REVIEW)
- Aprovação: "ok."
- Sha: 9fad8c883c1908ce15e88cf2eba5a52e7a0eec546266132c20e74bc8539191f9
- Próxima: E5 — abertura

### E5 — Abertura · CONCLUÍDA 2026-10-12T14:54:10-0300
- Produzido: plano de abertura
- Aprovação: "ok"
- Sha: a51dbe136c89654cb5d566c673236802df5af8353d96e6badf2454a13a3f7f65
- Próxima: oráculo por agente separado

### Abertura · 2026-10-12T14:54:10-0300
- Campanha: campanhas/iter22
- Tasks: 5 · primeira: 01-TASK-ORACULO
- Próxima: oráculo pelo agente separado → oracle freeze → script-aprovacao.sh (founder)
