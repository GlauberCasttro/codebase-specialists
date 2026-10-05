# cslib — API comum (Python 3.9+, só stdlib)

Importe com `scripts/` no `sys.path` (o `cs.py` já faz isso): `from cslib import paths, json5io, ...`.
Toda falha acionável é `cslib.CsError(message, hint=None, code=2)`; `cs.py` imprime
`erro: ...` + `como resolver: ...` e sai com `code`. Testes: `python3 -m unittest discover -s scripts/cslib/tests`.

## Formato (ARCHITECTURE §8-decies)
Tudo que é nosso é **JSON5** (`*.json5`); append-only é **JSONL**. Nenhum componente usa `json.load`
em `.json5`.

## `cslib.json5io` — JSON5 no subconjunto do §8-decies
| Função | Contrato |
|---|---|
| `loads(text\|bytes)` | aceita JSON + `//`, `/* */`, chave sem aspas se identificador `[A-Za-z_$][A-Za-z0-9_$]*`, vírgula final. Rejeita (`Json5Error`, com linha/coluna) aspas simples, hex, `Infinity`/`NaN`, `+1`, `.5`, `5.`, string multilinha, chave duplicada, vírgula dupla, lixo após o valor |
| `load(path)` | idem, erro prefixado pelo path |
| `read(path, required=True, default=None)` | como `load`, mas ausência/corrupção vira `CsError` acionável (use em consumidores) |
| `dumps(obj, header=None)` | canônico e determinístico: comentário `// header` no topo, chaves ordenadas (sem aspas quando identificador), objeto ≤3 campos com valores inline numa linha, objeto >3 campos um campo por linha com indentação de 1 espaço, lista que contém objeto **ou lista** uma entrada por linha, lista de escalares numa linha, sem vírgula final, `\n` final; NaN/Infinity/tipo não-JSON → `Json5Error` |
| `dump(obj, path, header, target=None)` | escrita atômica; `header` obrigatório ("o que é — gerado por quem"); com `target`, só grava em `<target>/.swarm/**` |
| `Json5Error` | subclasse de `ValueError` |

## `cslib.paths` — raiz, `.swarm/`, classificação, globs
- `resolve_target(arg=None)` → realpath; ordem `arg` > `$CLAUDE_PROJECT_DIR` > cwd (nunca o dir do script).
- `specialists_dir(t)`, `facts_dir(t)`, `state_dir(t)`, `evidence_dir(t)`.
- `ensure_inside_specialists(target, path)` → guard de escrita (realpath do pai, recusa symlink); `CsError` se fora.
- `is_within(root, path)`, `rel_to_target(target, path)` (realpath; erro se escapar).
- `classify(rel, head=None)` → `product|fixture|vendor|generated|reserved|example` (prioridade:
  vendor > fixture > example > generated > reserved > product). `head` = primeiros bytes p/ marcador
  "Code generated"/"@generated". `examples/`/`samples/` fora de pasta de teste = `example` (cliente de
  parceiro, demo: fora da análise do scan, mas PODE ter dono de escrita); sob `tests/` = fixture.
  Constantes: `IGNORED_CATEGORIES` (fixture, vendor, generated — nunca análise nem território),
  `NOT_ANALYZED_CATEGORIES` (ignoradas + example — fora da análise), `VENDOR_DIRS`, `FIXTURE_DIRS`,
  `EXAMPLE_DIRS`, `GENERATED_DIRS`, `RESERVED_PREFIXES`.
- `is_reserved(rel)` — **prefixo de path** (`.swarm/`, `.claude/`, `.cursor/`, `.codex/`,
  `.github/agents/`, `.github/instructions/`, `scripts/harness/`), nunca por componente.
- `lang_of(rel)`, `is_code(rel)`, `is_test_file(rel)`, `component_of(rel)` (1º dir; 2 níveis sob
  `src/ lib/ packages/ apps/ services/ internal/ pkg/ cmd/ modules/`).
- `glob_to_regex(p)`, `glob_match(rel, p)`, `expand_globs(files, patterns)` — `**` cruza `/`, `*`/`?` não.

## `cslib.jsonio` — JSON/JSONL e escrita atômica
- `write_bytes_atomic(path, data, target=None)`, `write_text_atomic`, `write_json_atomic` (tmp no mesmo
  dir + fsync + `os.replace`; com `target`, guard de `.swarm/`).
- `dumps(obj)` JSON canônico (sort_keys, indent 2, allow_nan=False); `dumps_line(obj)` compacto p/ JSONL.
- `append_jsonl(path, obj, target=None)` (O_APPEND + fsync); `read_json(path, required=True)` (só JSON legado).

## `cslib.evidence` — fato no formato do §4
- `FactBuilder(target).fact(id, layer, claim, evidence, confidence="high", origin="mechanical",
  scope=None, supports=None)` → dict validado; ids únicos (sufixo `-2`, `-3`… determinístico);
  `fingerprint` = sha256 de `path\0sha256(bytes)\n` dos arquivos-evidência ordenados (sem arquivo:
  sha256 do JSON canônico da evidência).
- Itens de evidência: `ev_file(rel, line=None)`, `ev_cmd(cmd, exit, out_bytes, blob=None)` (guarda
  `out_sha256` dos BYTES), `ev_commit(sha, files=None)`.
- `store_blob(target, bytes)` → copia para `.swarm/evidence/<sha256>.txt` e devolve o path relativo.
- `validate_fact(f)` → lista de erros (vazia = ok); `sha256_bytes`, `sha256_file`, `slug(text, maxlen=80)`.
- Enums: `CONFIDENCE = (high, medium, low)`, `ORIGINS = (mechanical, llm_interpretation)`;
  `llm_interpretation` exige `supports`.

## `cslib.gitx` — git sem shell
- `run(target, args, check=True)` → `(exit, stdout, stderr)`; sempre `git -C target -c core.quotepath=off`,
  `LC_ALL=C`, sem prompt. `out(target, args)` → str.
- `require_repo(target)` (CsError acionável se não é a raiz de um repo), `is_repo`, `head` (sha | None).
- `ls_files(target)` → `(lista ordenada, bytes_brutos)` (cached + others não-ignorados).
- `log_commits(target, max_commits=2000, paths=None)` → `[{sha, author, ts, subject, body, files:[{path, added, deleted}]}]`
  numa única chamada (`--no-merges --no-renames --numstat`).

## `cslib.cochange` — co-change por par (arquivo, diretório ou território)
- `cochange(commits, group_of, min_support=1, max_files=30, examples=3)` → `[{a, b, support, conf_a_b,
  conf_b_a, commits_a, commits_b, examples:[sha]}]`, `a < b`, ordenado (suporte desc). `group_of(path)`
  mapeia arquivo → grupo (diretório, território) ou `None` para excluir.
- `cochange_dirs(target, depth=1, max_commits=2000, min_support=1, max_files=30, include=None)` — atalho
  por prefixo de diretório. `dir_of(path, depth)`.

## `cslib.tokenize` — tokenizador de identificadores (BM25, glossário)
- `tokenize(text, min_len=2, keep_compound=False, stopwords=STOPWORDS)` → tokens minúsculos sem acento,
  quebrando `snake_case`, `camelCase`, `PascalCase`, `SIGLAPalavra`, `kebab-case`, `a.b/c`; dígito colado
  não quebra (`v2`, `sha256`). `keep_compound=True` também emite o identificador inteiro (`total_price`).
- `split_identifier(ident)` → partes (`"parseHTTPResponse_v2"` → `["parse","http","response","v2"]`).
- `strip_accents(text)`, `canonical_term(ident)` (`"OrderItem"` → `"order item"`), `STOPWORDS`.

## `cslib.log` — ledger
- `ledger(target, event, actor="cs.py", **fields)` → linha em `.swarm/state/ledger.jsonl`
  (`ts` UTC ISO). `read_ledger(target)`. Log do cs.py, NÃO encadeado — o ledger encadeado dos guards é
  `.swarm/state/harness-ledger.jsonl` (motor do harness). O ledger não entra em comparações de determinismo.
