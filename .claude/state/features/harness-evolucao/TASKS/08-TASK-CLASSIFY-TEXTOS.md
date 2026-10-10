# 08-TASK-CLASSIFY-TEXTOS — Classificação por script com classe épico; textos e CLI só pela árvore

id: 08-TASK-CLASSIFY-TEXTOS
feature: harness-evolucao
tipo: CORRECAO
grupo: G2
agente: corretor (papel; o executor real e o model passado vão para o Handoff)
CA: CA-07, CA-08
depends: 07-TASK-SHELL-PORTAVEL (edita o mesmo engine.py e o mesmo teste)
status: PENDENTE
gate: PENDENTE
complexidade: normal

## Goal
(1) `engine/classify.py` + `cs-state classify` (sinais estruturados: territórios/domínios tocados, entregas,
dependências, paralelizável, duração estimada, features e tasks estimadas, invariantes) que PROPÕE avulsa | feature |
epico com justificativa e sinais gravados em evento; classe `epico` nas classes de `machines.json5` (faixa completo,
guards de feature + confirmação humana); `new epico` aceita `--classificacao <evento>` e guarda `classificacao`.
(2) Em modo árvore, `add epic|feature|story`, `sprint plan` e `add task --quick` recusam com a instrução do comando da
árvore; `orchestrator.md`, `product-process.md`, `plan-sprint.md`, o `LANE_HINT`/`next` de `views.py`, o processo em
`render.py`, as skills em `platforms.py` (nova skill `classify`, template `assets/templates/state/classify.md`) e a §3
de `references/harness.md` passam a descrever só a árvore. NÃO remover o board plano legado (alvos antigos), NÃO criar
épico sem confirmação humana.

## Contexto
CA-07, CA-08. Âncoras: `scripts/harness/machines.json5:10-19`, `scripts/harness/engine/engine.py:437-445`,
`assets/templates/orchestrator.md:24,53,61-63`, `assets/templates/product-process.md:3-7`,
`assets/templates/plan-sprint.md:3-5`, `scripts/harness/engine/views.py:30,143`, `scripts/emit/render.py:253`,
`scripts/emit/platforms.py:126,137-167`, `scripts/harness/engine/state.py:464`, `references/harness.md:100-141`;
achados F8, F9, F12, F14.

## Subtasks
1. Rodar o oráculo (`-k CA07`, `-k CA08`) e ver falhar (RED).
2. `classify.py` + subcomando em `state.py` + classe `epico` em `machines.json5`/`engine.py`/`cmds.py`.
3. Recusa dos comandos legados em modo árvore; textos e skills emitidas reescritos para a árvore.
4. Testes em `scripts/harness/tests/test_evolucao_arvore.py`; oráculo e suítes `harness` e `emit` nos 2 Pythons
   (inclui o oráculo da iter15: skills geradas em verbo-objeto).

## Invariants
- Alvo legado (board plano) continua funcionando com os comandos antigos.
- Skills geradas no alvo seguem D-07 (inglês verbo-objeto), conferido pelo oráculo da iter15.

## Scope IN / OUT
IN: classificação, textos que guiam o modelo, recusa do legado em modo árvore. OUT: estrutura e ciclo de vida (09/10).

## Arquivos permitidos
- `scripts/harness/engine/classify.py`
- `scripts/harness/engine/state.py`
- `scripts/harness/engine/engine.py`
- `scripts/harness/engine/cmds.py`
- `scripts/harness/engine/views.py`
- `scripts/harness/machines.json5`
- `scripts/harness/tests/test_evolucao_arvore.py`
- `scripts/emit/platforms.py`
- `scripts/emit/render.py`
- `assets/templates/orchestrator.md`
- `assets/templates/product-process.md`
- `assets/templates/plan-sprint.md`
- `assets/templates/state/classify.md`
- `references/harness.md`

## AC
- `cs-state classify` grava a proposta com justificativa; `--class epico` aceito; nenhum texto emitido cita o caminho
  legado; `add epic` em modo árvore recusa sem criar item.

## DoD
- Régua seletiva verde (harness, emit) nos 2 Pythons; oráculo iter15 verde; Handoff preenchido.

## Verificação
```bash
python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA07
python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA08
```

## Handoff
