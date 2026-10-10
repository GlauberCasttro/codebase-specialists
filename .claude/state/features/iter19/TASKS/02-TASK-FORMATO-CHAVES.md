# 02-TASK-FORMATO-CHAVES — Estado em JSON, ordem de leitura e chaves em inglês

id: 02-TASK-FORMATO-CHAVES
feature: iter19
tipo: CORRECAO
grupo: G1
agente: corretor (papel; executor e model reais vão para o Handoff)
CA: CA-01, CA-02, CA-06
depends: 01-TASK-ORACULO (o oráculo congelado é a régua da correção)
status: DONE
gate: PASS
complexidade: normal

## Goal
O motor grava estado de entidade e projeção como JSON padrão (`.json`, indent 2, um item por linha, ordem de leitura,
`history` por último, `_generated_by` como campo, bytes determinísticos) com chaves em inglês pelo mapa POR CAMINHO
da E2 F3, e lê os dois formatos/idiomas. NÃO mudar `hcore.canonical`, logs JSONL, config JSON5, memória, chaves do
mandato M5 (só o formato das visões dele); NÃO remover `j5`.

## Contexto
CA-01, CA-02, CA-06. Âncoras: j5.py:124-141, hcore.py:137-174, 229-238, 514-535; tree.py:24, 60-70, 226-229,
380-468, 836-851, 1338-1369; session.py:440-467; auto.py:2916-2960; autonomy.py:27, 232, 385; selftest.py:293.

## Subtasks
1. Rodar TestCA01/TestCA02/TestCA06 do oráculo e ver falhar (RED).
2. `write_json` com ordem por kind + mapa pt→en por caminho (topo × history), aliases pt na leitura; `.json`/`.json5`
   aceitos em `is_item_file`, caminhos e validate (órfão `.json5` acusado).
3. Trocar os escritores de estado (tree, hcore, session, autonomy, auto-visões, selftest) para o formato novo.
4. Ajustar os 2 testes existentes que citam `.json5` de estado; rodar oráculo e suítes nos 2 Pythons (GREEN).

## Invariants
- `canonical()` e a cadeia de eventos intactos; validate verde; nenhum `def` removido.
- Chaves do mandato M5 continuam pt (selo, auto.py:58).

## Scope IN / OUT
IN: serialização e leitura de estado no motor. OUT: amend/show (task 03), migração (04/05), docs (06).

## Arquivos permitidos
- `scripts/harness/engine/hcore.py`
- `scripts/harness/engine/tree.py`
- `scripts/harness/engine/session.py`
- `scripts/harness/engine/validate.py`
- `scripts/harness/engine/autonomy.py`
- `scripts/harness/engine/auto.py`
- `scripts/harness/engine/selftest.py`
- `scripts/harness/engine/guard.py`
- `scripts/harness/engine/views.py`
- `scripts/harness/tests/test_iter19_estado.py`
- `scripts/harness/tests/test_iter20_atestado.py`
- `scripts/harness/tests/test_workflow_e2e.py`

## AC
- TestCA01, TestCA02 e TestCA06 (exceto a parte de VERSION) verdes nos 2 Pythons; nenhum teste enfraquecido.

## DoD
- Régua seletiva verde (`/e2e-loop`); diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
cd campanhas/iter19/oraculo && python3 -m unittest test_iter19.TestCA01 test_iter19.TestCA02
```

## Handoff
- Executor: general-purpose · sonnet (ciclo 1). Revisor: general-purpose · opus, instância isolada · APPROVED (snapshot:
  não escreveu). Independência: instâncias distintas.
- Arquivos: hcore.py (mapa pt→en por caminho ITEM_SCHEMA/SESSION_SCHEMA, item_to_en/item_to_pt, READ_ORDER, write_json,
  write_item_json, read_state, pick_state_file), tree.py, session.py, autonomy.py, validate.py, selftest.py, auto.py;
  tests: test_iter19_estado.py (novo, 9), test_iter20_atestado.py (casos .json).
- Desenho: forma interna e eventos tput seguem com chaves pt; tradução só na borda (gravar/ler); canonical e cadeia
  intactos; mandato M5 com chaves pt, só formato .json.
- Oráculo: TestCA01 7/7; TestCA02 4/6 — os 2 restantes falham só no `cs-state find` (state.py:349, sufixo de alias
  depois do caminho), fora desta task; PASS comprovado em cópia de rascunho com a linha trocada ⇒ RESSALVA: a correção
  vai na 03 e o CA-02 só fecha lá. TestCA06: só version/catálogo falham (task 06).
- Régua do tech-lead (cópia, 2 Pythons): harness 327 OK (16 skip), upgrade 8 OK (7 skip, pré-existentes), memory 14 OK.
  Oráculos iter18 R1–R7 (34) e iter20 (24) verdes (executor). Privacidade: 0.
- Findings do revisor (MENOR) roteados: #3 validate aceita chave pt inserida antes da en e #find + state.py:717 → task 03;
  #1 migrate plano→árvore sem os .json → task 04; #2 OWN_RESIDUE sem selftest.json → task 05; #4 texto
  "autonomy.json5" em validate.py:178-187 → ressalva (cosmético).
