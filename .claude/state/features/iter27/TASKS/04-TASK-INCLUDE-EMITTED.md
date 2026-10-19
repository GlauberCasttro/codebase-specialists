# 04-TASK-INCLUDE-EMITTED — --include-emitted com alias --allow-outside; caminho exato do log no plano do upgrade

id: 04-TASK-INCLUDE-EMITTED
feature: iter27
tipo: CORRECAO
grupo: G2
agente: corretor (papel; executor e model no Handoff)
CA: CA-04, CA-05
depends: 01-TASK-ORACULO (o oráculo congelado é a régua da correção)
status: PENDENTE
gate: PENDENTE
complexidade: normal

## Goal
`--include-emitted` passa a ser o nome da flag que autoriza escrever fora de `.swarm/` em `emit`, `harness install`,
`upgrade --apply` e `init --replace-harness`; `--allow-outside` vira alias depreciado (aviso, fora do `--help`); toda
recusa/dica cita `--include-emitted`; as chamadas internas do upgrade passam o nome novo; o plano do upgrade cita
`.swarm/events.jsonl`; as citações de flag pt do cs-state em `install.py` (MAKE_TARGETS) passam ao nome en da task 02.
NÃO mudar o que a flag autoriza (mesma semântica), NÃO tocar no motor (`scripts/harness/engine/`), NÃO remover `def`.

## Contexto
CA-04 e a parte "dicas do código" do CA-05 nestes arquivos. Âncoras: F10 (`scripts/cs.py:87-88`,
`scripts/upgrade/cli.py:31`, `scripts/harness/cli.py:98`, `scripts/emit/cli.py:246`; repasse em
`scripts/upgrade/core.py:486,1104,1164`), F9 (`scripts/upgrade/core.py:64`); `install.py` (12 citações, 5 delas
`--allow-outside`), `replace.py` (6), `emit/apply.py` (2). Testes que afirmam o texto da recusa:
`scripts/emit/tests/test_iter3_emit.py:38`, `scripts/harness/tests/test_install_outside.py:46`,
`scripts/stage/tests/test_iter4_stages.py:33`. Os nomes en do cs-state citados em install.py são os da FEATURE.md
(CA-01), então esta task não depende da 02 para texto, só para a régua do doctest (na QA).

## Subtasks
1. Rodar TestCA04 e ver vermelho.
2. Nome novo nos 4 parsers (e no complemento de `cs.py:87`), alias com aviso, `dest` inalterado.
3. Recusas, dicas, repasse interno e o texto do plano (F9); citações pt de install.py.
4. Ajustar os 3 testes que afirmam o texto; teste novo `test_iter27_include_emitted.py`.

## Invariants
- `--allow-outside` segue funcionando (oráculos antigos usam em ~95 linhas); mesma semântica.
- Nenhum `def` removido.

## Scope IN / OUT
IN: a flag nos 4 CLIs, repasse, textos destes arquivos. OUT: motor (G1), assets/docs (05), VERSION (06).

## Arquivos permitidos
- `scripts/cs.py`
- `scripts/upgrade/cli.py`
- `scripts/upgrade/core.py`
- `scripts/harness/cli.py`
- `scripts/harness/install.py`
- `scripts/harness/replace.py`
- `scripts/emit/cli.py`
- `scripts/emit/apply.py`
- `scripts/emit/tests/test_iter3_emit.py`
- `scripts/harness/tests/test_install_outside.py`
- `scripts/stage/tests/test_iter4_stages.py`
- `scripts/upgrade/tests/test_iter27_include_emitted.py`

## AC
- TestCA04 verde nos 2 Pythons; suítes emit, harness, stage e upgrade verdes.

## DoD
- Régua seletiva verde; diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
cd campanhas/iter27/oraculo && python3 -m unittest test_iter27.TestCA04 && cd ../../.. && python3 .claude/tools/e2e.py rodar --suites emit,harness,stage,upgrade
```

## Handoff
