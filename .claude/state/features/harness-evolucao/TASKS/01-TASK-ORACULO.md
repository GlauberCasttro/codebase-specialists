# 01-TASK-ORACULO — Oráculo dos 19 CAs (o roteiro de validação da demanda), por agente separado

id: 01-TASK-ORACULO
feature: harness-evolucao
tipo: ORACULO
grupo: —
agente: oraculista (persona via /rh; nunca o corretor)
CA: CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07, CA-08, CA-09, CA-10, CA-11, CA-12, CA-13, CA-14, CA-15, CA-16, CA-17, CA-18, CA-19
depends: —
status: DONE
gate: PASS

## Goal
Escrever o ESPEC e os testes que provam os 19 CAs do FEATURE.md, um `class TestCA<NN>` por CA (selecionável por
`-k CA<NN>`), montando alvos de rascunho em diretório temporário e exercitando o harness pelos comandos reais
(`cs.py harness install`, `.swarm/bin/cs-state`, `cs-mem`, `cs.py upgrade`). O conjunto cobre o roteiro de 23 passos
da task de validação da demanda (épico decomposto, propagação, arquivo, reabertura, avulsa, JSON, migração, init de
memória, correct, reuso, autocorreção, relatório). Os testes têm de FALHAR no HEAD de hoje em todo CA que pede
mudança. NÃO corrigir nada do produto, NÃO escrever fora de `campanhas/harness-evolucao/oraculo/`, NÃO depender de
LLM (passos 18 e 21: só a parte mecânica).

## Contexto
CA-01..CA-19 do FEATURE.md. Âncoras da E2 (F1–F34): `scripts/memory/mem.py:955,910,858,792,784`,
`scripts/harness/engine/guard.py:261`, `scripts/harness/install.py:355`, `assets/templates/correct.md:5`,
`scripts/harness/engine/engine.py:109,929`, `scripts/harness/machines.json5:10`, `assets/templates/orchestrator.md:61`,
`scripts/harness/engine/tree.py:25,496,699,896,922,947,955,989,1052`, `scripts/cslib/json5io.py:285`,
`scripts/harness/engine/auto.py:2908`, `scripts/harness/engine/cmds.py:94`. Reproduções prontas que servem de base:
`local/levantamento-evolucao-harness/` (relatórios com comandos) — reescrever no oráculo, não importar do scratch.

## Subtasks
1. ESPEC.md: para cada CA, o alvo montado (team com ≥ 3 agentes, árvore inicializada), a entrada (comando) e o
   resultado esperado (exit, saída, arquivo gravado, evento no `events.jsonl`/ledger).
2. `_alvo.py`: helpers (alvo temporário via `scripts/harness/tests/fixture.py`, rodar CLI real, ler JSON/JSON5, achar
   eventos); `test_harness_evolucao.py`: um `TestCA<NN>` por CA, cada um com `test_calibracao_*` (resultado vazio
   reprova, resultado bom conhecido passa).
3. Rodar no HEAD no Windows nativo e no WSL; anotar no Handoff quais CAs falham (RED esperado) e por quê.

## Invariants
- Só stdlib, Python 3.9+; tudo em diretórios temporários; nada escrito no repo nem no perfil real.
- Nada privado: pessoa = "Ana"; tokens de teste fictícios montados por concatenação; caminhos com `~` ou variável.
- No Windows nativo, CA-15 testa o motor sem driver; os demais CAs podem usar o motor como está (se o verify der 127
  antes da correção, o CA falha — é RED legítimo).

## Scope IN / OUT
IN: ESPEC e testes do oráculo. OUT: qualquer arquivo do produto, suítes existentes, oráculos de outras campanhas.

## Arquivos permitidos
- `campanhas/harness-evolucao/oraculo/ESPEC.md`
- `campanhas/harness-evolucao/oraculo/_alvo.py`
- `campanhas/harness-evolucao/oraculo/test_harness_evolucao.py`

## AC
- 19 classes `TestCA01`..`TestCA19`; no HEAD todas falham em pelo menos um teste que não é de calibração.
- Nenhum teste passa trivialmente (cada um tem asserção sobre exit, saída, arquivo ou evento).

## DoD
- O tech-lead congela com `oracle freeze` (os 3 arquivos); Handoff com o RED medido por CA nos dois ambientes.

## Verificação
```bash
python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -v
```

## Handoff
- Executor: rh-oraculista-01-TASK-ORACULO-1 (general-purpose, opus; ficha `local/tech-lead/harness-evolucao/ficha-oraculista.txt`,
  conferida por `rh.py conferir`). Custo medido: 74 turnos, contexto somado ~13,9 M (`logs/custo.jsonl`; o ajuste do
  CA-09 veio depois, no mesmo agente).
- Escrita conferida por snapshot (`tech_lead.py snap --comparar`): só `campanhas/harness-evolucao/oraculo/ESPEC.md`,
  `_alvo.py` e `test_harness_evolucao.py` (o resto do diff é estado escrito pelo tech-lead e a outra sessão da
  win-harness); guard de privacidade 0 achados; sem `__pycache__`.
- Oráculo: 19 classes `TestCA01..TestCA19`, 79 testes, cada classe com `test_calibracao_*`. Nomes livres dos CAs
  fixados no ESPEC (ex.: `redacted:<int>`, `classify --json` e flags, `memory_init`, `memory_injected`,
  `lesson.recorded`, `close {auto, gatilho}`, `cascata_de`, `report`, `retry --esperado --obtido --causa --correcao`,
  `formatVersion`, `migrate json-format`).
- Revisão do tech-lead antes do freeze: 1 ajuste pedido ao oraculista — CA-09 exigia fechamento automático da avulsa
  no `accept` (não pedido pela demanda §3.2, "fechada e arquivada individualmente"); agora `close` explícito.
- RED medido pelo TECH-LEAD (reexecução própria, não a palavra do agente): Windows nativo (Py 3.12) `Ran 79` ·
  `FAILED (failures=55)` · RC 1 (`local/tech-lead/harness-evolucao/01-TASK-ORACULO/oraculo-windows.out`); WSL
  (Py 3.10) `Ran 79` · `FAILED (failures=51)` · RC 1 (`oraculo-wsl.out`); as 19 classes falham nos dois; 0
  calibrações falhando; CA-09 depois do ajuste: `Ran 4` · 3 falhas. No Windows parte do RED de CA-10/12/13/14/15/16
  vem do `/bin/sh` fixo (é o CA-15).
- Congelado: `oracle freeze` com os 3 arquivos → `e00cf3c5d927`; `oracle verify` → intacto.
- LACUNAS (do oraculista, aceitas): CA-19 sem `upgrade --apply` ponta a ponta (o verify do upgrade roda `emit
  validate`, que reprova num alvo só com harness — PRÉ-EXISTENTE); não mecanizados: permissão de escrita (CA-03),
  roundtrip antes do replace (CA-18), falha de ambiente sem lição (CA-17), área congelada (CA-09), token partido
  (CA-01), duplicata `.json`/`.json5`, passos 18 e 21 (LLM). Leniências registradas no ESPEC (evento em qualquer dos
  3 ledgers; `memory_injected` de dispatch/hook/brief; épico/sprint sem aceite propagam; close_if_open no CA-09 não
  proíbe fechamento automático). CA-19 depende do commit `7aa3cb4` no histórico git.
