"""L1 grafo: imports por linguagem (regex) → grafo de arquivos; PageRank; comunidades.

Linguagens: Python, JS/TS, Go, Java/Kotlin, C#, Ruby, Rust, PHP, shell (`source`/`.`).
Imports não resolvidos para arquivo do repo viram `external` (nome do pacote/módulo).
Comunidades: label propagation determinístico (ordem de nós ordenada, empate → menor rótulo).
"""

import posixpath
import re

from cslib import paths, workspaces
from cslib.evidence import ev_cmd, ev_file, slug
from cslib.jsonio import dumps
from . import represent

LAYER = "graph"

PY_IMPORT = re.compile(r"^\s*import\s+([\w.]+(?:\s+as\s+\w+)?(?:\s*,\s*[\w.]+(?:\s+as\s+\w+)?)*)", re.M)
PY_FROM = re.compile(r"^[ \t]*from[ \t]+(\.*)([\w.]*)[ \t]+import[ \t]+(\([^)]*\)|[^\n#;]+)", re.M)
JS_IMPORT = re.compile(
    r"""(?:^|[;\s])(?:import|export)\s+(?:[\w*{}\s,$]+?\s+from\s+)?['"]([^'"\n]+)['"]"""
    r"""|\brequire\s*\(\s*['"]([^'"\n]+)['"]\s*\)|\bimport\s*\(\s*['"]([^'"\n]+)['"]\s*\)""", re.M)
GO_SINGLE = re.compile(r'^\s*import\s+(?:[\w.]+\s+)?"([^"]+)"', re.M)
GO_BLOCK = re.compile(r"^\s*import\s*\((.*?)\)", re.M | re.S)
GO_LINE = re.compile(r'(?:[\w.]+\s+)?"([^"]+)"')
JVM_IMPORT = re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+)(\.\*)?\s*;?", re.M)
CS_USING = re.compile(r"^\s*using\s+(?:static\s+)?(?:\w+\s*=\s*)?([\w.]+)\s*;", re.M)
CS_NAMESPACE = re.compile(r"^\s*namespace\s+([\w.]+)", re.M)  # aplicado sobre cs_blank_strings(texto) (U12)
# 1ª declaração de tipo: `using` de arquivo vem SEMPRE antes dela; depois disso, "using X;" só aparece em string
# literal (código-fonte de teste de source generator) — cobaia .NET 2026-10-05: 2 sondas com gabarito errado
CS_FIRST_TYPE = re.compile(
    r"^\s*(?:\[[^\n]*\]\s*)*(?:(?:public|internal|private|protected|static|sealed|abstract|partial|readonly|"
    r"unsafe|file|ref)\s+)*(?:class|struct|record|interface|enum|delegate)\b", re.M)


def cs_blank_strings(text):
    """Apaga (troca por espaço, preservando as quebras de linha) o conteúdo de literais de string/char C#
    — regular, verbatim `@"…"`, interpolada `$"…"` e raw (3+ aspas) — e de comentários. U12: um
    `namespace X` dentro de string (código de teste de source generator) não é declaração do arquivo."""
    out = []
    i, n = 0, len(text)

    def blank(a, b):
        out.append("".join(c if c == "\n" else " " for c in text[a:b]))

    while i < n:
        c = text[i]
        if c == "/" and text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
            continue
        if c == "/" and text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            blank(i, j)
            i = j
            continue
        if c == "'":
            j = i + 1
            while j < n and text[j] not in "'\n":
                j += 2 if text[j] == "\\" else 1
            j = min(n, j + 1)
            blank(i, j)
            i = j
            continue
        if c == '"':
            k = i
            while k < n and text[k] == '"':
                k += 1
            q = k - i
            if q >= 3:  # raw string: fecha com a mesma quantidade de aspas
                j = text.find('"' * q, k)
                j = n if j < 0 else j + q
            else:
                verbatim = i > 0 and text[i - 1] == "@" or (i > 1 and text[i - 2:i] in ("@$", "$@"))
                if q == 2:  # string vazia ""
                    j = i + 2
                else:
                    j = i + 1
                    while j < n:
                        ch = text[j]
                        if verbatim:
                            if ch == '"':
                                if j + 1 < n and text[j + 1] == '"':
                                    j += 2
                                    continue
                                break
                        else:
                            if ch == "\\":
                                j += 2
                                continue
                            if ch == '"' or ch == "\n":
                                break
                        j += 1
                    j = min(n, j + 1)
            blank(i, j)
            i = j
            continue
        out.append(c)
        i += 1
    return "".join(out)


RB_REQ = re.compile(r"""^\s*(require_relative|require|load)\s*\(?\s*['"]([^'"]+)['"]""", re.M)
RS_MOD = re.compile(r"^\s*(?:pub(?:\([\w:]+\))?\s+)?mod\s+(\w+)\s*;", re.M)
RS_USE = re.compile(r"^\s*(?:pub\s+)?use\s+((?:crate|super|self)(?:::\w+)+)", re.M)
RS_EXTERN = re.compile(r"^\s*(?:pub\s+)?use\s+(\w+)::", re.M)
PHP_REQ = re.compile(r"""\b(?:require|include)(?:_once)?\s*\(?\s*(?:__DIR__\s*\.\s*)?['"]([^'"]+)['"]""")
PHP_USE = re.compile(r"^\s*use\s+([\w\\]+)\s*;", re.M)
SH_SOURCE = re.compile(r"""^[ \t]*(?:source|\.)[ \t]+([^;&|#\n]+)""", re.M)

JS_EXTS = ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte", ".d.ts")


class Resolver(object):
    def __init__(self, files):
        self.files = set(files)
        self.py_mod = {}
        self.suffix = {}
        self.dirs = {}
        for f in sorted(files):
            d = posixpath.dirname(f)
            self.dirs.setdefault(d, []).append(f)
            stem, ext = posixpath.splitext(f)
            parts = stem.split("/")
            for i in range(len(parts)):
                key = "/".join(parts[i:])
                self.suffix.setdefault((key, ext), []).append(f)
            if ext in (".py", ".pyi"):
                mparts = parts[:-1] if parts[-1] == "__init__" else parts
                for i in range(len(mparts)):
                    self.py_mod.setdefault(".".join(mparts[i:]), []).append(f)
        self.go_module = None
        self.workspaces = {}
        self.hints = {}  # (importador, alvo) -> linha do import (evidência da aresta)

    @staticmethod
    def _pick(cands, importer):
        if not cands:
            return None
        if len(cands) == 1:
            return cands[0]
        top = importer.split("/")[0]

        def key(c):
            return (0 if c.split("/")[0] == top else 1, len(c), c)
        return sorted(cands, key=key)[0]

    def python(self, importer, module, level=0):
        if level:
            base = posixpath.dirname(importer)
            for _ in range(level - 1):
                base = posixpath.dirname(base)
            rel = (base + "/" if base else "") + module.replace(".", "/") if module else base
            for cand in (rel + ".py", rel + "/__init__.py", rel + ".pyi"):
                cand = cand.lstrip("/")
                if cand in self.files:
                    return cand
            return None
        return self._pick(self.py_mod.get(module), importer)

    def by_suffix(self, key, exts, importer):
        cands = []
        for e in exts:
            cands.extend(self.suffix.get((key, e), []))
        return self._pick(sorted(set(cands)), importer)

    def relative(self, importer, spec, exts):
        base = posixpath.normpath(posixpath.join(posixpath.dirname(importer), spec))
        if base.startswith("../"):
            return None
        for e in exts:
            if base + e in self.files:
                return base + e
        for e in exts:
            if e and base + "/index" + e in self.files:
                return base + "/index" + e
        return None


def _shell_target(importer, raw, res):
    t = raw
    # "$DIR/x.sh", "$(dirname "$0")/x.sh", "${BASH_SOURCE%/*}/x.sh" → relativo ao importador
    if "$" in t:
        m = re.search(r"[)}]/(.+)$", t) or re.search(r"\$\w+/(.+)$", t)
        if not m:
            return None
        t = m.group(1)
        cands = [posixpath.normpath(posixpath.join(posixpath.dirname(importer), t)), t]
    else:
        cands = [posixpath.normpath(posixpath.join(posixpath.dirname(importer), t)), t.lstrip("./")]
    for c in cands:
        if c in res.files:
            return c
    return None


def extract(ctx, rel, res):
    """Lista de (alvo_no_repo | None, nome_externo | None)."""
    lang = paths.lang_of(rel)
    text = ctx.text(rel)
    out = []
    if not text:
        return out
    if lang == "python":
        for m in PY_IMPORT.finditer(text):
            for item in m.group(1).split(","):
                mod = item.strip().split()[0]
                t = res.python(rel, mod)
                if t is None:
                    # import a.b.c → tenta prefixos
                    parts = mod.split(".")
                    for i in range(len(parts) - 1, 0, -1):
                        t = res.python(rel, ".".join(parts[:i]))
                        if t:
                            break
                out.append((t, None if t else mod.split(".")[0]))
        for m in PY_FROM.finditer(text):
            dots, mod, names = len(m.group(1)), m.group(2), m.group(3).strip("() \t\n")
            hit = False
            for name in [n.strip().split()[0] for n in names.replace("\\", ",").split(",") if n.strip()]:
                if name == "*":
                    continue
                full = (mod + "." + name) if mod else name
                t = res.python(rel, full, dots)
                if t:
                    out.append((t, None))
                    hit = True
            if not hit:
                t = res.python(rel, mod, dots) if (mod or dots) else None
                out.append((t, None if (t or dots) else mod.split(".")[0]))
    elif lang in ("javascript", "typescript", "vue", "svelte"):
        for m in JS_IMPORT.finditer(text):
            spec = m.group(1) or m.group(2) or m.group(3)
            if spec.startswith("."):
                t = res.relative(rel, spec, JS_EXTS)
                out.append((t, None))
            elif spec.startswith("/"):
                t = None
                out.append((None, None))
            else:
                name = workspaces.split_spec(spec)[0]
                if name in res.workspaces:
                    # pacote do próprio monorepo: aresta interna (nunca dependência externa)
                    t = workspaces.resolve(res.workspaces, spec, res.files)
                    out.append((t, None))
                else:
                    t = None
                    out.append((None, name))
            if t:
                res.hints.setdefault((rel, t), text.count("\n", 0, m.start(m.lastindex)) + 1)
    elif lang == "go":
        specs = [m.group(1) for m in GO_SINGLE.finditer(text)]
        for blk in GO_BLOCK.finditer(text):
            specs += [m.group(1) for m in GO_LINE.finditer(blk.group(1))]
        for spec in specs:
            if res.go_module and (spec == res.go_module or spec.startswith(res.go_module + "/")):
                d = spec[len(res.go_module):].lstrip("/")
                tgts = [f for f in res.dirs.get(d, []) if f.endswith(".go")
                        and not f.endswith("_test.go")]
                out.extend((t, None) for t in tgts)
                if not tgts:
                    out.append((None, None))
            else:
                out.append((None, spec if "." not in spec.split("/")[0] else
                            "/".join(spec.split("/")[:3])))
    elif lang in ("java", "kotlin"):
        for m in JVM_IMPORT.finditer(text):
            name, star = m.group(1), m.group(2)
            key = name.replace(".", "/")
            if star:
                hits = [f for f in res.dirs.get(_dir_suffix(res, key), [])
                        if f.endswith((".java", ".kt"))]
                out.extend((t, None) for t in hits)
                if not hits:
                    out.append((None, ".".join(name.split(".")[:2])))
                continue
            t = res.by_suffix(key, (".java", ".kt"), rel)
            if t is None and "." in name:  # import estático: classe é o penúltimo
                t = res.by_suffix(key.rsplit("/", 1)[0], (".java", ".kt"), rel)
            out.append((t, None if t else ".".join(name.split(".")[:2])))
    elif lang == "csharp":
        first = CS_FIRST_TYPE.search(text)
        for m in CS_USING.finditer(text[:first.start()] if first else text):
            ns = m.group(1)
            hits = ctx._cs_ns.get(ns, [])
            ln = text.count("\n", 0, m.start(1)) + 1  # U6: evidência = linha do `using`
            for t in hits[:50]:
                if t != rel:
                    res.hints.setdefault((rel, t), ln)
            out.extend((t, None) for t in hits[:50] if t != rel)
            if not hits:
                out.append((None, ns.split(".")[0]))
    elif lang == "ruby":
        for m in RB_REQ.finditer(text):
            kind, spec = m.group(1), m.group(2)
            spec2 = spec if spec.endswith(".rb") else spec + ".rb"
            if kind == "require_relative" or spec.startswith("."):
                t = posixpath.normpath(posixpath.join(posixpath.dirname(rel), spec2))
                out.append((t if t in res.files else None, None))
            else:
                t = None
                for cand in ("lib/" + spec2, spec2):
                    if cand in res.files:
                        t = cand
                        break
                if t is None:
                    t = res.by_suffix(spec2[:-3], (".rb",), rel) if "/" in spec else None
                out.append((t, None if t else spec.split("/")[0]))
    elif lang == "rust":
        d = posixpath.dirname(rel)
        base = posixpath.splitext(posixpath.basename(rel))[0]
        moddir = d if base in ("mod", "lib", "main") else posixpath.join(d, base)
        for m in RS_MOD.finditer(text):
            n = m.group(1)
            t = None
            for cand in (posixpath.join(moddir, n + ".rs"), posixpath.join(moddir, n, "mod.rs")):
                if cand in res.files:
                    t = cand
                    break
            out.append((t, None))
        for m in RS_USE.finditer(text):
            segs = m.group(1).split("::")
            t = None
            if segs[0] == "crate":
                root = _rust_src_root(rel)
                for i in range(len(segs), 1, -1):
                    p = posixpath.join(root, *segs[1:i])
                    for cand in (p + ".rs", p + "/mod.rs"):
                        if cand in res.files:
                            t = cand
                            break
                    if t:
                        break
            out.append((t, None))
        for m in RS_EXTERN.finditer(text):
            n = m.group(1)
            if n not in ("crate", "super", "self", "std", "core", "alloc"):
                out.append((None, n))
    elif lang == "php":
        for m in PHP_REQ.finditer(text):
            spec = m.group(1)
            t = posixpath.normpath(posixpath.join(posixpath.dirname(rel), spec.lstrip("/")))
            out.append((t if t in res.files else None, None))
        for m in PHP_USE.finditer(text):
            key = m.group(1).replace("\\", "/")
            t = res.by_suffix(key, (".php",), rel)
            if t is None and "/" in key:
                t = res.by_suffix(key.split("/", 1)[1], (".php",), rel)
            out.append((t, None if t else m.group(1).split("\\")[0]))
    elif lang == "shell":
        for m in SH_SOURCE.finditer(text):
            raw = m.group(1).strip().replace('"', "").replace("'", "").split()
            if raw:
                spec = "".join(raw) if any("$(" in t for t in raw) else raw[0]
                out.append((_shell_target(rel, spec, res), None))
    return out


def _dir_suffix(res, key):
    for d in sorted(res.dirs):
        if d == key or d.endswith("/" + key):
            return d
    return key


def _rust_src_root(rel):
    parts = rel.split("/")
    if "src" in parts:
        return "/".join(parts[:parts.index("src") + 1])
    return posixpath.dirname(rel)


IMPORT_KW = re.compile(r"\b(import|from|require|require_relative|source|use|using|include|"
                       r"include_once|require_once|mod|load)\b|^\s*\.\s")


def edge_line(ctx, src, tgt, hints=None):
    """Linha do import em `src` que cita `tgt` (evidência da aresta); 0 se não localizada."""
    if hints and (src, tgt) in hints:
        return hints[(src, tgt)]
    base = posixpath.basename(tgt)
    stem = posixpath.splitext(base)[0]
    if stem in ("__init__", "index", "mod"):
        stem = posixpath.basename(posixpath.dirname(tgt)) or stem
    for i, ln in enumerate(ctx.lines(src), 1):
        if (stem in ln or base in ln) and IMPORT_KW.search(ln):
            return i
    return 0


def pagerank(nodes, edges, damping=0.85, iters=100, tol=1e-12):
    n = len(nodes)
    if n == 0:
        return {}
    idx = {v: i for i, v in enumerate(nodes)}
    out_w = [0.0] * n
    inc = [[] for _ in range(n)]
    for (s, t), w in sorted(edges.items()):
        out_w[idx[s]] += w
        inc[idx[t]].append((idx[s], w))
    pr = [1.0 / n] * n
    for _ in range(iters):
        dangling = sum(pr[i] for i in range(n) if out_w[i] == 0)
        new = []
        for i in range(n):
            s = sum(pr[j] * w / out_w[j] for j, w in inc[i])
            new.append((1 - damping) / n + damping * (s + dangling / n))
        delta = sum(abs(a - b) for a, b in zip(new, pr))
        pr = new
        if delta < tol:
            break
    return {v: round(pr[idx[v]], 8) for v in nodes}


def communities(nodes, edges, max_iter=50):
    adj = {v: {} for v in nodes}
    for (s, t), w in edges.items():
        if s == t:
            continue
        adj[s][t] = adj[s].get(t, 0) + w
        adj[t][s] = adj[t].get(s, 0) + w
    label = {v: v for v in nodes}
    for _ in range(max_iter):
        changed = False
        for v in nodes:
            if not adj[v]:
                continue
            score = {}
            for u, w in adj[v].items():
                score[label[u]] = score.get(label[u], 0) + w
            best = max(score.values())
            cand = min(l for l, s in score.items() if s == best)
            if label[v] in score and score[label[v]] == best:
                cand = label[v]  # estabilidade: mantém rótulo se empatado no topo
            if cand != label[v]:
                label[v] = cand
                changed = True
        if not changed:
            break
    groups = {}
    for v in nodes:
        groups.setdefault(label[v], []).append(v)
    return sorted((sorted(m) for m in groups.values()), key=lambda m: (-len(m), m[0]))


def common_prefix(members):
    split = [m.split("/")[:-1] for m in members]
    pref = []
    for parts in zip(*split):
        if all(p == parts[0] for p in parts):
            pref.append(parts[0])
        else:
            break
    if pref:
        return "/".join(pref)
    comps = {}
    for m in members:
        c = paths.component_of(m)
        comps[c] = comps.get(c, 0) + 1
    return sorted(comps.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


GRAPH_LANGS = ("python", "javascript", "typescript", "vue", "svelte", "go", "java", "kotlin",
               "csharp", "ruby", "rust", "php", "shell")


def run(ctx):
    fb = ctx.fb
    files = ctx.code_files(GRAPH_LANGS)
    res = Resolver(files)
    res.workspaces = workspaces.discover(ctx.files, ctx.text)
    for gm in ctx.by_basename("go.mod"):
        m = re.search(r"^module\s+(\S+)", ctx.text(gm), re.M)
        if m:
            res.go_module = m.group(1)
            break
    ctx._cs_ns = {}
    for f in files:
        if paths.lang_of(f) == "csharp":
            for m in CS_NAMESPACE.finditer(cs_blank_strings(ctx.text(f))):
                ctx._cs_ns.setdefault(m.group(1), []).append(f)
    edges = {}
    external = {}
    unresolved = 0
    for f in files:
        lang = paths.lang_of(f)
        for tgt, ext in extract(ctx, f, res):
            if tgt and tgt != f:
                edges[(f, tgt)] = edges.get((f, tgt), 0) + 1
            elif ext:
                e = external.setdefault(lang, {}).setdefault(ext, set())
                e.add(f)
            elif not tgt:
                unresolved += 1
    ctx._ext_users = external
    nodes = sorted(files)
    pr = pagerank(nodes, edges)
    comms = communities(nodes, edges)
    comm_of = {}
    comm_list = []
    for i, members in enumerate(comms):
        if len(members) < 2:
            continue
        cid = "c%03d" % len(comm_list)
        for m in members:
            comm_of[m] = cid
        comm_list.append({"id": cid, "prefix": common_prefix(members), "size": len(members),
                          "members": members})
    indeg, outdeg = {}, {}
    for (s, t) in edges:
        outdeg[s] = outdeg.get(s, 0) + 1
        indeg[t] = indeg.get(t, 0) + 1
    node_list = [{"path": v, "lang": paths.lang_of(v), "pagerank": pr[v], "in": indeg.get(v, 0),
                  "out": outdeg.get(v, 0), "community": comm_of.get(v)} for v in nodes]
    edge_list = [[s, t, w, edge_line(ctx, s, t, res.hints)] for (s, t), w in sorted(edges.items())]
    ext_out = {lang: {name: len(fs) for name, fs in sorted(d.items())}
               for lang, d in sorted(external.items())}

    facts = []
    gev = ev_cmd("scan:L1 imports regex sobre %d arquivos" % len(files), 0,
                 dumps(edge_list).encode("utf-8"))
    facts.append(fb.fact("graph.stats", LAYER,
                         "Grafo de imports: %d arquivos de código, %d arestas internas, %d comunidades "
                         "(≥2 arquivos), %d imports externos distintos"
                         % (len(nodes), len(edges), len(comm_list),
                            sum(len(v) for v in ext_out.values())),
                         [gev], scope=["**"]))
    ranked = sorted((n for n in node_list if n["in"] > 0), key=lambda n: (-n["pagerank"], n["path"]))
    for i, n in enumerate(ranked[:15]):
        importers = sorted(s for (s, t) in edges if t == n["path"])
        facts.append(fb.fact("graph.central.%s" % slug(n["path"]), LAYER,
                             "%s é central (#%d por PageRank %.4f; importado por %d arquivos)"
                             % (n["path"], i + 1, n["pagerank"], n["in"]),
                             [ev_file(n["path"])] + [ev_file(s) for s in importers[:5]],
                             confidence="high" if n["in"] >= 3 else "medium",
                             scope=[n["path"]]))
    for c in comm_list[:25]:
        under = [m for m in c["members"] if c["prefix"] != "." and m.startswith(c["prefix"] + "/")]
        if c["prefix"] != "." and len(under) == c["size"]:
            where, scope = "prefixo comum '%s'" % c["prefix"], [c["prefix"] + "/**"]
        else:
            # prefixo só da maioria: dizer "comum" seria falso (ex.: testes em tests/ na mesma comunidade)
            rest = sorted(set(paths.component_of(m) for m in c["members"] if m not in under))
            where = "sem prefixo comum; maior grupo '%s' (%d/%d arquivos; demais em %s)" % (
                c["prefix"], len(under), c["size"], ", ".join(rest[:4]))
            scope = sorted(set(([c["prefix"] + "/**"] if under else []) +
                               [m for m in c["members"] if m not in under]))
        facts.append(fb.fact("graph.community.%s" % c["id"], LAYER,
                             "Comunidade %s: %d arquivos acoplados por imports, %s" % (c["id"], c["size"], where),
                             [ev_file(m) for m in c["members"][:6]],
                             confidence="medium", scope=scope))
    for lang, d in ext_out.items():
        top = sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[:15]
        for name, cnt in top:
            users = sorted(external[lang][name])
            facts.append(fb.fact("graph.external.%s.%s" % (lang, slug(name)), LAYER,
                                 "%s importa '%s' em %d arquivos" % (lang, name, cnt),
                                 [ev_file(u) for u in users[:5]],
                                 confidence="high", scope=users[:20]))
    reps = represent.representatives(ctx, node_list)
    return {"layer": LAYER, "nodes": node_list, "edge_fields": ["from", "to", "weight", "line"],
            "edges": edge_list, "communities": comm_list,
            "representatives": {r["dir"]: r["representative"] for r in reps},
            "external": ext_out, "unresolved_imports": unresolved,
            "go_module": res.go_module,
            "workspaces": {n: {"dir": w["dir"], "entries": w["entries"]}
                           for n, w in sorted(res.workspaces.items())},
            "facts": facts}
