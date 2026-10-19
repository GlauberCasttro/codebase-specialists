# 03-TASK-MEMORIA-EN — Forma interna do item e da sessão em inglês; kind epic normalizado na migração

id: 03-TASK-MEMORIA-EN
feature: iter27
tipo: CORRECAO
grupo: G1
agente: corretor (papel; executor e model no Handoff)
CA: CA-08, CA-09
depends: 02-TASK-FLAGS-EN (mesmos arquivos state.py/auto.py/hcore.py/tree.py: serializado)
status: PENDENTE
gate: PENDENTE
complexidade: normal

## Goal
O motor passa a guardar o item da árvore e a sessão em memória com as chaves en de `ITEM_SCHEMA`/`SESSION_SCHEMA` e
`kind: "epic"`; a leitura pt → en fica na ENTRADA (disco legado `.json5`/pt e replay dos `tput` antigos); eventos
novos gravam o item en; o arquivo gravado sai byte a byte igual ao de hoje; a migração `item-status` deixa de
preservar `kind: "epico"` e normaliza para `"epic"`. NÃO reescrever events.jsonl nem archive, NÃO mudar o interior do
mandato (só a fronteira `node_spec`, `auto.py:1127-1143`, e o `f.get("aceite")` de `auto.py:1493`), NÃO remover
`item_to_pt`/`session_to_pt` (RNF-03), NÃO mudar o formato em disco.

## Contexto
CA-08, CA-09. Âncoras: F4 (`hcore.py:254-310`, `apply_ops` `hcore.py:816-817`, `tput` em
`tree.py:192,704,820,1840,1926`), F5 (`tree.py:1964`, `hcore.py:398-409`), F6 (`auto.py:1127-1143`), leitores:
tree.py (139 literais), state.py (spec `state.py:239-246,433-436`, `reaberta` 331), session.py (11), upgrade não muda
(a normalização vai pela `item-status`). Testes do produto acoplados à forma interna: `test_iter23_arvore.py:144-162,192`,
`test_iter26_modelo.py:53,63-64`, `test_iter19_estado.py` (13 chamadas de tradução).

## Subtasks
1. Rodar TestCA08 (e a parte de kind do TestCA09) e ver vermelho.
2. Inverter a forma interna: normalização en na entrada; `item_to_en` vira identidade sobre item en; manter
   `item_to_pt`/`session_to_pt` como compatibilidade.
3. Renomear os leitores (tree, state, session, `node_spec`) para as chaves en; `item-status` normaliza o kind.
4. Ajustar os testes do produto acoplados à forma interna; teste novo `test_iter27_memoria.py` (replay misto pt/en,
   bytes do arquivo iguais, varredura "nenhuma chave pt em memória").
5. Suítes harness e upgrade nos 2 Pythons; oráculos iter19, iter23, iter25 e iter26 contra a cópia.

## Invariants
- Replay de histórico pt dá o mesmo estado (CA-08); `validate --strict` de alvo antigo segue passando.
- Nenhum `def` removido; oráculos antigos que passam no HEAD seguem passando (D-35).

## Scope IN / OUT
IN: forma interna, leitores, fronteira do mandato, migração do kind, testes acoplados. OUT: flags (02),
`--include-emitted` (04), textos (05), VERSION/migrations (06).

## Arquivos permitidos
- `scripts/harness/engine/hcore.py`
- `scripts/harness/engine/tree.py`
- `scripts/harness/engine/session.py`
- `scripts/harness/engine/state.py`
- `scripts/harness/engine/auto.py`
- `scripts/harness/tests/test_iter23_arvore.py`
- `scripts/harness/tests/test_iter26_modelo.py`
- `scripts/harness/tests/test_iter19_estado.py`
- `scripts/harness/tests/test_iter27_memoria.py`

## AC
- TestCA08 verde nos 2 Pythons; a parte de kind do TestCA09 verde depois da task 06; suítes harness e upgrade verdes.

## DoD
- Régua seletiva verde; diff só nos arquivos permitidos; Handoff com a contagem "chaves pt em memória: antes → 0".

## Verificação
```bash
cd campanhas/iter27/oraculo && python3 -m unittest test_iter27.TestCA08 && cd ../../.. && python3 .claude/tools/e2e.py rodar --suites harness,upgrade
```

## Handoff
