# 02-TASK-FLAGS-EN — Flags en com alias pt no cs-state, cs-auto e cs-route; aviso agregado; dry-run com o item

id: 02-TASK-FLAGS-EN
feature: iter27
tipo: CORRECAO
grupo: G1
agente: corretor (papel; executor e model no Handoff)
CA: CA-01, CA-02, CA-03, CA-05, CA-07
depends: 01-TASK-ORACULO (o oráculo congelado é a régua da correção)
status: PENDENTE
gate: PENDENTE
complexidade: normal

## Goal
Dar nome en a toda flag pt do cs-state (árvore), cs-auto e cs-route, com o pt como alias depreciado (fora do
`--help`), UM aviso por chamada, en vence; o `--dry-run` do `new` traz o item; as dicas e recusas destes arquivos
citam só a flag en (inclui a recusa do DoR em `tree.py:473,612`). NÃO mudar as chaves internas (task 03), NÃO mudar
chaves/valores do mandato (D-20), NÃO renomear subcomandos (`senha`, `conferir`, `anular`), NÃO trocar as chaves
`{ids, criar, mover, eventos}` do dry-run (só acrescentar), NÃO remover `def` (o `_deprecated_aliases` pode ser
generalizado, não apagado).

## Contexto
CA-01, CA-02, CA-03, CA-07 e a parte "dicas do código" do CA-05. Âncoras: F1 (`state.py:226-278`,
`auto.py:3150-3210`, `router.py:279,282`), F2 (`state.py:840,844`), F3 (`tree.py:263-264`; o item está em
`T.ops`, `tree.py:192`), alias da iter26 (`state.py:814-850`). Helper comum de alias pode ir em `hcore.py`
(ENGINE_FILES, RNF-05). Citações pt em `guard.py` (`--avulsa`, `--teste`).

## Subtasks
1. Rodar TestCA01/02/03/07 do oráculo e ver vermelho.
2. Tabela de alias por programa (cs-state, cs-auto, cs-route) num helper só; nomes en no argparse; pt reescrito com
   aviso agregado.
3. Dry-run do `new` com o item (chaves en, forma do arquivo) sem escrever.
4. Trocar as citações pt nas dicas/recusas de state.py, auto.py, router.py, tree.py e guard.py.
5. Teste novo `test_iter27_flags.py`; suíte harness nos 2 Pythons.

## Invariants
- Todo nome pt de hoje continua funcionando (RNF-02); os oráculos antigos que passam no HEAD seguem passando.
- Nenhum `def` removido; a prosa segue em português.

## Scope IN / OUT
IN: argparse, alias, aviso, dry-run e citações nestes arquivos. OUT: forma interna (03), `--allow-outside` (04),
textos de assets/docs (05).

## Arquivos permitidos
- `scripts/harness/engine/state.py`
- `scripts/harness/engine/auto.py`
- `scripts/harness/engine/router.py`
- `scripts/harness/engine/hcore.py`
- `scripts/harness/engine/tree.py`
- `scripts/harness/engine/guard.py`
- `scripts/harness/tests/test_iter27_flags.py`

## AC
- TestCA01, TestCA02, TestCA03 e TestCA07 verdes nos 2 Pythons; suíte harness verde; nenhuma flag pt no `--help`.

## DoD
- Régua seletiva verde (harness, doctests); diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
cd campanhas/iter27/oraculo && python3 -m unittest test_iter27.TestCA01 test_iter27.TestCA02 test_iter27.TestCA03 test_iter27.TestCA07 && cd ../../.. && python3 .claude/tools/e2e.py rodar --suites harness,doctests
```

## Handoff
