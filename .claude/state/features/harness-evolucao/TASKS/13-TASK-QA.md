# 13-TASK-QA — Portão e oráculo, CA a CA, no Windows nativo e no WSL; roteiro de 23 passos

id: 13-TASK-QA
feature: harness-evolucao
tipo: QA
grupo: —
agente: QA (fase fechamento do /e2e-loop)
CA: CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07, CA-08, CA-09, CA-10, CA-11, CA-12, CA-13, CA-14, CA-15, CA-16, CA-17, CA-18, CA-19
depends: 03-TASK-MIGRACAO-JSON (última do G3), 06-TASK-CORRECT-ESCOPO (última do G1), 12-TASK-RELATORIO-AUTOCORRECAO (última do G2)
status: PENDENTE
gate: PENDENTE

## Goal
Rodar o portão da feature (cópia limpa = HEAD + só os arquivos da feature) com o oráculo congelado e os oráculos das
campanhas que tocam o escopo, no WSL (régua completa, 2 Pythons) e no Windows nativo (suítes do produto sem falha por
`/bin/sh` + oráculo), e montar a matriz CA → evidência e o placar do roteiro de 23 passos. NÃO corrigir nada: falha
volta ao corretor com a evidência.

## Contexto
Os 19 CAs do FEATURE.md; critério de parada (19/19 nos dois ambientes; suítes do produto 0 falhas no WSL; 0 falha por
`/bin/sh` no Windows; oráculos anteriores verdes ou com mudança oficial; 0 `def` removido); métrica (≥ 21 de 23 passos).

## Subtasks
1. Portão completo no WSL com o oráculo da feature e os de iter10, iter13, iter15 e m5.
2. Oráculo e suítes `harness`/`memory`/`cslib`/`upgrade` no Windows nativo.
3. Matriz CA → comando → resultado nos dois ambientes; placar dos 23 passos; `def` removido = 0; privacidade.

## Invariants
- O oráculo não muda (`oracle verify`). Só entra no relatório o que foi executado.

## Scope IN / OUT
IN: execução e relatório. OUT: qualquer mudança de código ou de teste.

## Arquivos permitidos
- `.claude/state/features/harness-evolucao/TASKS/13-TASK-QA.md`

## AC
- Portão `RESULTADO: VERDE` + `FIM` no WSL; oráculo 19/19 nos dois ambientes; matriz e placar no Handoff.

## DoD
- Handoff com a matriz, o placar e os caminhos dos `portao.out`; Aceite QA proposto.

## Verificação
```bash
bash .claude/tools/portao.sh harness-evolucao --oraculo campanhas/harness-evolucao/oraculo:test_harness_evolucao --oraculo campanhas/iter10/oraculo:test_estado_arvore --oraculo campanhas/iter15/oraculo:test_iter15 --oraculo campanhas/m5/oraculo:test_mandato --lista local/portao-harness-evolucao.lista
```

## Handoff
