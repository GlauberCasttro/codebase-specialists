# 02-TASK-GRAVADOR-JSON — Gravador JSON único, validado e atômico, com leitura de JSON5 legado

id: 02-TASK-GRAVADOR-JSON
feature: harness-evolucao
tipo: CORRECAO
grupo: G3
agente: corretor (papel; o executor real e o model passado vão para o Handoff)
CA: CA-18
depends: 01-TASK-ORACULO (o oráculo congelado é a régua da correção)
status: DONE
gate: PASS
complexidade: normal

## Goal
Criar o gravador único de documentos do harness: `json.dumps(indent=2, ensure_ascii=False, allow_nan=False)` com
`\n` final, ordem de chaves semântica (id, kind, title, status primeiro), roundtrip (`json.loads(texto) == obj`)
antes do replace atômico (mkstemp no mesmo diretório + fsync + os.replace) e `formatVersion`; um resolvedor de nome
que prefere `.json` e cai em `.json5`. Os 4 escritores JSON5 (`cslib/json5io.py`, `engine/j5.py`, `emit/j5.py` e o
`write_json5` do `hcore.py`) viram fachada e continuam existindo. NÃO renomear arquivos de estado aqui (é a 11 e a 03),
NÃO tocar JSONL, NÃO remover nenhum `def`.

## Contexto
CA-18. Âncoras: `scripts/cslib/json5io.py:285` (objeto ≤ 3 campos inline), `scripts/harness/engine/j5.py:125`,
`scripts/harness/engine/hcore.py:213,229` (atômico sem validação), `scripts/cslib/jsonio.py:38`; achados F26, F28.

## Subtasks
1. Rodar o oráculo congelado (`-k CA18`) e ver falhar (RED).
2. Implementar `dumps_json`/`write_json` em `cslib/jsonio.py` e espelho autocontido em `engine/j5.py` (o motor no alvo
   não importa `cslib`); `hcore.write_json5` e `state_paths` passam a usar o resolvedor e o gravador.
3. Fachadas nos escritores antigos; testes em `scripts/cslib/tests/test_jsonio_formato.py` (indent, roundtrip,
   atômico, UTF-8, legado lido); README do cslib.
4. Rodar o oráculo e as suítes de `cslib`, `harness` e `emit` nos 2 Pythons (GREEN no que cabe a esta task).

## Invariants
- O motor instalado no alvo continua autocontido (RNF-05). Nenhum `def` existente some (RNF-02).
- Arquivo inválido nunca chega ao disco: falha de roundtrip levanta antes do replace.

## Scope IN / OUT
IN: gravação e leitura dos documentos. OUT: migração (03), nomes dos itens da árvore (11), memória (05), JSONL.

## Arquivos permitidos
- `scripts/cslib/jsonio.py`
- `scripts/cslib/json5io.py`
- `scripts/cslib/README.md`
- `scripts/cslib/tests/test_jsonio_formato.py`
- `scripts/harness/engine/j5.py`
- `scripts/harness/engine/hcore.py`
- `scripts/emit/j5.py`

## AC
- Documento gravado pelo gravador passa em `json.loads`, tem indent 2 e uma propriedade por linha; leitura de `.json5`
  legado devolve o mesmo objeto.

## DoD
- Régua seletiva verde (cslib, harness, emit) nos 2 Pythons; diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA18
```

## Handoff
- Executores: ciclo 1 exec-02-TASK-GRAVADOR-JSON (general-purpose, sonnet, 42 turnos); ciclo 2 exec2-02 (general-purpose,
  opus, 19 turnos) para os 3 MENOR·REGRESSÃO do revisor. Custo em `logs/custo.jsonl`.
- Arquivos: `scripts/cslib/jsonio.py` (FORMAT_VERSION, _ordered, dumps_json, write_json, resolve_name),
  `scripts/cslib/json5io.py` (dump_json, fachada), `scripts/harness/engine/j5.py` (espelho autocontido:
  dumps_json/write_json/resolve_name, mkstemp+fsync+os.replace, roundtrip antes do replace), `scripts/harness/engine/
  hcore.py` (write_json5 = fachada de j5.write_json, sem header; state_paths resolve board/autonomy/selftest/config;
  team/run fora — artefatos do pipeline), `scripts/emit/j5.py` (fachadas), `scripts/cslib/README.md`,
  `scripts/cslib/tests/test_jsonio_formato.py` (11 testes).
- Escopo conferido por snapshot (só os arquivos permitidos); privacidade 0 achados; nenhum `def` removido (contra HEAD).
- Régua do tech-lead (WSL, python3 e /usr/bin/python3, cópia com as tasks 02/04/07): cslib 28 OK, emit 55 OK, harness
  317 OK (16 skips; base HEAD 306/16), memory 39 com 1 falha que não é desta task (test_mem.py:131, comportamento
  antigo da promovida — task 04/06). Saída: `local/tech-lead/harness-evolucao/regua-onda1-ciclo2-wsl.out`.
- Oráculo (Windows, CS_DEV_SKILL_DIR=cópia) `-k CA18`: 4 testes, 3 OK; `test_estado_gravado_em_json_formatado` RED
  esperado (nomes `.json5` — tasks 05 e 11).
- Revisão isolada: ciclo 1 APPROVED com 3 MENOR (team/run preferindo .json legado; formatVersion null no espelho;
  README); ciclo 2 APPROVED sem findings (revisores opus, instâncias distintas do executor).
- Limites: `json5io.dump`, `emit/j5.dumps` e `engine/j5.dumps` seguem gravando JSON5 (test_json5io fixa o header); os
  escritores diretos (mem.py, tree.py:61, auto.py:2938, install.py:137) mudam nas tasks 05/11; caminhos com
  "board.json5" fixo no código (tree.py, install.py, mem.py, upgrade/core.py, selftest.py) são das tasks 05/11/03.
- Para as próximas: gravador `cslib.jsonio.write_json/dumps_json`; no motor `j5.write_json/dumps_json/resolve_name`.
