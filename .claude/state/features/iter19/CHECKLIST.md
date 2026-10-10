# CHECKLIST — criação da feature iter19

<!-- gerado por .claude/tools/feature.py a partir de eventos.jsonl; não edite à mão (o hook nega; `feature.py checklist` detecta adulteração) -->

Demanda: "B-14: estado em JSON padrão, ordem de leitura, chaves em inglês, amend refletido no arquivo, cs-state show, migração automática no upgrade"

- [x] **E0 — Pré-condição** · OK 2026-10-07T11:32:50-0300
- [x] **E1 — Analisar a demanda** · OK 2026-10-07T12:01:06-0300 · sha 2b5df20bdf41
- [x] **E2 — Investigação medida** · OK 2026-10-07T12:08:50-0300 · sha e6800c9cbede
- [x] **E3 — FEATURE.md (Bloco A)** · OK 2026-10-07T12:14:04-0300 · sha 594d69e946bc
- [x] **E4 — Tasks (Bloco B)** · OK 2026-10-07T12:16:52-0300 · sha 2e1bf90a7a98
- [x] **E5 — Abertura** · OK 2026-10-07T12:27:41-0300 · sha 3d9863636cab
- [x] **Abertura** (ac.py init, INDEX, HISTORICO, WORKFLOW) · 2026-10-07T12:27:44-0300

## Handoffs
<!-- APPEND-ONLY: uma entrada por decisão; nunca reescrita -->

### E0 — Pré-condição · CONCLUÍDA 2026-10-07T11:32:50-0300
- Demanda: "B-14: estado em JSON padrão, ordem de leitura, chaves em inglês, amend refletido no arquivo, cs-state show, migração automática no upgrade"
- Próxima: E1 — Analisar a demanda

### E1 — Analisar a demanda · CONCLUÍDA 2026-10-07T12:01:06-0300
- Produzido: problema enunciado; FEATURE-ID iter19
- Itens aprovados: 1: mandato M5 fora da tradução (só formato); 2: memória cs-mem fora; 3: migração por evento novo encadeado
- Aprovação: "ok"
- Sha: 2b5df20bdf41883fc4ee2e9291c718374a493bc432fab0a803468b05751148e3
- Próxima: E2 — investigação medida

### E2 — Investigação medida · CONCLUÍDA 2026-10-07T12:08:50-0300
- Produzido: investigação medida (local/criar-iter19/E2.md)
- Medido: 1324 linhas json5: 77 mudam, 117 config/produto, 21 legado, 20 memória (fora), 14 infra, 495 fábrica, 580 testes; ~16 arquivos de produto
- Aprovação: "ok"
- Sha: e6800c9cbede207dd5c81ff472b16081a78b5e4d16fbbec92bd7a3535623b670
- Próxima: E3 — FEATURE.md

### E3 — FEATURE.md (Bloco A) · CONCLUÍDA 2026-10-07T12:14:04-0300
- Produzido: FEATURE.md com CA-01..CA-06 (contrato PASS)
- Aprovação: "ok"
- Sha: 594d69e946bc67eee73fb4d901f3da6e7d8b50ccd3848ae95dcd475a43349ed3
- Próxima: E4 — tasks

### E4 — Tasks (Bloco B) · CONCLUÍDA 2026-10-07T12:16:52-0300
- Produzido: 8 tasks (ORACULO, 5 CORRECAO em G1/G2/G3, QA, REVIEW); contrato completo PASS, sonda OK
- Aprovação: "ok"
- Sha: 2e1bf90a7a98dfb3548b71d584c9dab67f37905a4d9be9b8ee35f93d4ef53c58
- Próxima: E5 — abertura

### E5 — Abertura · CONCLUÍDA 2026-10-07T12:27:41-0300
- Produzido: plano de abertura
- Aprovação: "ok"
- Sha: 3d9863636cab43a3e0a7c574f713cca72d0f18734a136b5f389d3f2ca41cd6d8
- Próxima: oráculo por agente separado

### Abertura · 2026-10-07T12:27:44-0300
- Campanha: campanhas/iter19
- Tasks: 8 · primeira: 01-TASK-ORACULO
- Próxima: oráculo pelo agente separado → oracle freeze → script-aprovacao.sh (founder)
