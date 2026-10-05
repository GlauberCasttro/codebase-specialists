"""Pacotes locais de monorepo JS/TS (npm/yarn/pnpm workspaces): nome do pacote → diretório e entrada.

Uso comum: o scan resolve `import "@shop/shared"` para o arquivo do workspace (aresta interna, não
dependência externa) e nenhum consumidor confunde o NOME de um pacote (`@shop/api/inventory`) com
um caminho do repo.

API (só stdlib, sem I/O próprio — o chamador fornece a lista de arquivos e um leitor de texto):
- `discover(files, read_text)` → `{nome: {"dir", "manifest", "entries": [arquivos], "scripts": {...}}}`
  (todo `package.json` com campo `name` fora de node_modules; a raiz entra se tiver `name`).
- `split_spec(spec)` → `(nome_do_pacote, subcaminho)` para `@scope/pkg/sub` ou `pkg/sub`.
- `resolve(workspaces, spec, files)` → arquivo do repo ou None (entrada do pacote, ou subcaminho
  tentado em `<dir>/<sub>`, `<dir>/src/<sub>` com extensões JS/TS e `/index.*`).
- `looks_like_package_ref(text)` → True para `@scope/nome[/sub]` (nunca é caminho de arquivo).
"""

import json
import posixpath
import re

JS_EXTS = ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".d.ts")
SCOPED = re.compile(r"^@[a-z0-9][\w.-]*/[a-z0-9][\w.-]*(?:/[\w./-]*)?$", re.I)


def looks_like_package_ref(text):
    return bool(SCOPED.match(text.strip().rstrip("/")))


def split_spec(spec):
    parts = spec.split("/")
    if spec.startswith("@"):
        return "/".join(parts[:2]), "/".join(parts[2:])
    return parts[0], "/".join(parts[1:])


def _entry_values(data):
    vals = []
    exp = data.get("exports")
    if isinstance(exp, str):
        vals.append(exp)
    elif isinstance(exp, dict):
        dot = exp.get(".", exp if not any(k.startswith(".") for k in exp) else None)
        if isinstance(dot, str):
            vals.append(dot)
        elif isinstance(dot, dict):
            for k in ("types", "import", "default", "require", "node"):
                v = dot.get(k)
                if isinstance(v, str):
                    vals.append(v)
    for k in ("types", "typings", "module", "main", "source"):
        v = data.get(k)
        if isinstance(v, str):
            vals.append(v)
    return vals


def _first_existing(base, fileset, exts=JS_EXTS):
    base = posixpath.normpath(base) if base else base
    for e in exts:
        if base + e in fileset:
            return base + e
    for e in exts:
        if e and posixpath.join(base, "index" + e) in fileset:
            return posixpath.join(base, "index" + e)
    return None


def discover(files, read_text):
    fileset = set(files)
    out = {}
    for rel in sorted(files):
        if rel.rsplit("/", 1)[-1] != "package.json" or "node_modules/" in rel:
            continue
        try:
            data = json.loads(read_text(rel) or "")
        except ValueError:
            continue
        if not isinstance(data, dict):
            continue
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        d = posixpath.dirname(rel)
        entries = []
        for v in _entry_values(data):
            p = posixpath.normpath(posixpath.join(d, v)) if d else posixpath.normpath(v)
            hit = p if p in fileset else _first_existing(re.sub(r"\.(c|m)?js$", "", p), fileset)
            if hit and hit not in entries:
                entries.append(hit)
        if not entries:
            for cand in ("src/index", "index", "src/main", "lib/index"):
                hit = _first_existing(posixpath.join(d, cand) if d else cand, fileset)
                if hit:
                    entries.append(hit)
                    break
        scripts = data.get("scripts") if isinstance(data.get("scripts"), dict) else {}
        if name not in out:  # primeiro (ordem de path) vence; nomes duplicados são raros
            out[name] = {"dir": d, "manifest": rel, "entries": entries,
                         "scripts": {k: v for k, v in scripts.items() if isinstance(v, str)}}
    return out


def resolve(workspaces, spec, files):
    name, sub = split_spec(spec)
    ws = workspaces.get(name)
    if ws is None:
        return None
    fileset = files if isinstance(files, (set, frozenset)) else set(files)
    if not sub:
        return ws["entries"][0] if ws["entries"] else None
    d = ws["dir"]
    for base in (posixpath.join(d, sub) if d else sub, posixpath.join(d, "src", sub) if d else "src/" + sub):
        hit = _first_existing(base, fileset)
        if hit:
            return hit
    return None
