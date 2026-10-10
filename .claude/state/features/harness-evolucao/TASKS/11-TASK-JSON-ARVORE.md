# 11-TASK-JSON-ARVORE — Itens, projeção, sessão e autonomia em .json; migração do estado em árvore pelo motor

id: 11-TASK-JSON-ARVORE
feature: harness-evolucao
tipo: CORRECAO
grupo: G2
agente: corretor (papel; o executor real e o model passado vão para o Handoff)
CA: CA-18, CA-19
depends: 10-TASK-CICLO-VIDA (edita o mesmo tree.py, session.py, auto.py e teste), 02-TASK-GRAVADOR-JSON (grava pelo gravador e resolve nomes pelo resolvedor)
status: PENDENTE
gate: PENDENTE
complexidade: normal

## Goal
Itens da árvore (`epico|sprint|feature|story.json`, `tasks/NN-TIPO-slug.json`), projeção, sessão/resume, autonomia,
relatórios e escalações passam a ser gravados em `.json` pelo gravador da 02; `is_item_file`/`ITEM_FILE`/regex
aceitam `.json` e `.json5` (legado), `.json` vence em duplicata e o `validate` aponta o duplicado; novo
`cs-state migrate json-format`: valida antes, faz backup, reescreve conteúdo e extensão, emite evento `arvore.migrate
{formato: json}` com novo `path` por item (cadeia de hash íntegra), idempotente. NÃO reescrever `events.jsonl`, NÃO
converter artefatos do pipeline.

## Contexto
CA-18, CA-19 (lado do motor). Âncoras: `scripts/harness/engine/tree.py:25,68-73,1351` (extensão fixa),
`:1481` (precedente `migrate state-tree`), `scripts/harness/engine/session.py:147,304,461,467`,
`scripts/harness/engine/autonomy.py:27,232,385`, `scripts/harness/engine/auto.py:1899,2938,3094`,
`scripts/harness/engine/state.py:288` (migrate só state-tree); achados F25, F26.

## Subtasks
1. Rodar o oráculo (`-k CA18`, `-k CA19`) e ver falhar (RED).
2. Nomes `.json` e leitura dual em tree/session/autonomy/auto; `validate` com duplicata.
3. `cs-state migrate json-format` com evento e backup; testes em `scripts/harness/tests/test_evolucao_arvore.py`.
4. Oráculo, suíte `harness`, oráculos iter10, iter13 e m5 nos 2 Pythons (oráculo congelado que compara `.json5` por
   nome: registrar mudança oficial com PORQUE, nunca editar).

## Invariants
- Cadeia de hash do `events.jsonl` íntegra; `validate` OK antes e depois da migração.
- Alvo com motor antigo não é convertido antes do motor novo (ordem garantida pela 03).

## Scope IN / OUT
IN: nomes e formato dos arquivos do motor; migração do estado em árvore. OUT: upgrade/migrations (03), memória (05).

## Arquivos permitidos
- `scripts/harness/engine/tree.py`
- `scripts/harness/engine/session.py`
- `scripts/harness/engine/autonomy.py`
- `scripts/harness/engine/auto.py`
- `scripts/harness/engine/state.py`
- `scripts/harness/tests/test_evolucao_arvore.py`

## AC
- Alvo novo grava só `.json` válido no estado; alvo em `.json5` migra por `cs-state migrate json-format` com `validate`
  OK e segunda execução sem mudança.

## DoD
- Régua seletiva verde (harness) nos 2 Pythons; oráculos afetados verdes ou com mudança oficial; Handoff preenchido.

## Verificação
```bash
python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA18
python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA19
```

## Handoff
