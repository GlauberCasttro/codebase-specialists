"""Mapas em .swarm/knowledge/ (ARCHITECTURE §8-nonies + §8-decies): JSON5, grafos {nodes, edges}.

Este emissor GERA:
- tree.json5  — árvore do produto: nó por pasta com dono e ≥1 arquivo representativo; fixtures/gerados
                marcados (fonte: facts/inventory + facts/graph + team);
- stack.json5 — linguagem → ecossistema → pacote com versão do lockfile e territórios que usam
                (fonte: facts/stack_graph se existir, senão facts/stack).
Este emissor só VALIDA (são do construtor de team): deps.json5 e collision.json5.

Entradas lidas de forma defensiva (.json5, com .json aceito na transição).
"""
import posixpath
from pathlib import Path
from cslib.paths import STATE_DIR

from emit import j5
from emit.common import EmitError
from emit.knowledge import path_in

KNOW_DIR = ".swarm/knowledge"
GENERATED = ("tree.json5", "stack.json5")
EXTERNAL = ("deps.json5", "collision.json5")


def _load(root, stem, required=False):
    base = Path(root) / STATE_DIR
    for ext in (".json5", ".json"):
        p = base / (stem + ext)
        if p.is_file():
            try:
                return j5.load(p)
            except ValueError as exc:
                raise EmitError("%s ilegível: %s" % (p, exc))
    if required:
        raise EmitError(".swarm/%s.json5 ausente: rode `cs.py scan` antes de emitir" % stem)
    return None


class Data(object):
    def __init__(self, root, team):
        self.team = team
        inv = _load(root, "facts/inventory", required=True)
        self.files = sorted(f["path"] for f in inv.get("files", []) if f.get("category") == "product")
        self.loc = {f["path"]: f.get("loc", 0) for f in inv.get("files", [])}
        self.ignored = inv.get("ignored") or {}
        self.languages = inv.get("languages") or {}
        rep = inv.get("representative") or {}
        self.representative = rep if isinstance(rep, dict) else {}
        graph = _load(root, "facts/graph") or {}
        self.pagerank = {n["path"]: n.get("pagerank", 0) for n in graph.get("nodes", []) if "path" in n}
        self.external_users = graph.get("external_users") or {}
        self.stack = _load(root, "facts/stack") or {}
        self.stack_graph = _load(root, "facts/stack_graph")
        self.anchors = set()
        for ag in team["agents"]:
            self.anchors.update(ag["card"].get("anchors") or [])

    def owner(self, path):
        for ag in self.team["agents"]:
            if ag.get("territory") and path_in(path, ag["territory"]):
                return ag["name"]
        return None

    def dirs(self):
        out = {""}
        for f in self.files:
            d = posixpath.dirname(f)
            while d:
                out.add(d)
                d = posixpath.dirname(d)
        return sorted(out)

    def rep_for(self, d):
        r = self.representative.get(d) or self.representative.get(d + "/") or (
            self.representative.get(".") if d == "" else None)
        if isinstance(r, list):
            r = r[0] if r else None
        if isinstance(r, dict):
            r = r.get("path") or r.get("file")
        if r:
            return r
        direct = [f for f in self.files if posixpath.dirname(f) == d]
        pool = direct or [f for f in self.files if d == "" or f.startswith(d + "/")]
        if not pool:
            return None
        return sorted(pool, key=lambda f: (f not in self.anchors, -self.pagerank.get(f, 0),
                                           -self.loc.get(f, 0), f))[0]


# ------------------------------------------------------------------ tree.json5

def tree(data):
    nodes, edges = [], []
    for d in data.dirs():
        files = [f for f in data.files if d == "" or f.startswith(d + "/")]
        owners = sorted({data.owner(f) or "sem-dono" for f in files})
        nid = d or "."
        nodes.append({"id": nid, "kind": "dir", "owner": owners[0] if len(owners) == 1 else owners,
                      "representative": data.rep_for(d), "files": len(files)})
        if d:
            edges.append([posixpath.dirname(d) or ".", nid])
    for cat in sorted(data.ignored):
        for prefix, n in sorted(data.ignored[cat].items()):
            nodes.append({"id": prefix, "kind": cat, "files": n})
    return {"source": "facts/inventory + facts/graph + team", "nodes": nodes, "edges": edges}


# ------------------------------------------------------------------ stack.json5

def stack_packages(data):
    """[(eco, name, version, source)] — fonte de verdade para conferir versões."""
    sg = data.stack_graph
    if isinstance(sg, dict) and sg.get("nodes"):
        return sorted({(str(n.get("eco") or n.get("kind") or ""), str(n.get("name") or n.get("label") or n["id"]),
                        str(n["version"]), str(n.get("source", ""))) for n in sg["nodes"] if n.get("version")})
    pk = data.stack.get("packages") or []
    direct = [p for p in pk if p.get("direct")] or pk
    return sorted({(p["eco"], p["name"], str(p["version"]), "%s:%s" % (p.get("source", ""), p.get("line", "")))
                   for p in direct})


def stack(data):
    pk = stack_packages(data)
    langs = sorted(k for k, v in data.languages.items() if isinstance(v, dict) and v.get("code"))
    nodes = [{"id": "lang:" + l, "kind": "language"} for l in langs]
    ecos = sorted({p[0] for p in pk})
    nodes += [{"id": "eco:" + e, "kind": "ecosystem"} for e in ecos]
    edges = []
    for e in ecos:
        for l in langs:
            if e.lower() == l.lower() or (e.lower() == "node" and l.lower() in ("javascript", "typescript")) \
                    or (e.lower() == "dotnet" and l.lower() in ("csharp", "c#", "fsharp")):
                edges.append(["lang:" + l, "eco:" + e])
    for eco, name, ver, src in pk:
        users = data.external_users.get(name) or []
        terr = sorted({data.owner(u) for u in users if data.owner(u)})
        nodes.append({"id": "pkg:%s:%s" % (eco, name), "kind": "package", "name": name, "version": ver,
                      "source": src, "territories": terr})
        edges.append(["eco:" + eco, "pkg:%s:%s" % (eco, name)])
    return {"source": "facts/stack_graph" if data.stack_graph else "facts/stack", "nodes": nodes, "edges": edges}


HEADERS = {
    "tree.json5": "codebase-specialists:generated: árvore territorial (pasta → dono + arquivo representativo); "
                  "não edite, rode `cs.py emit`",
    "stack.json5": "codebase-specialists:generated: stack (linguagem → ecossistema → pacote@versão do lockfile); "
                   "não edite, rode `cs.py emit`",
}


def build(root, team):
    data = Data(root, team)
    out = {"tree.json5": tree(data), "stack.json5": stack(data)}
    return {k: j5.dumps(v, HEADERS[k]) for k, v in out.items()}, data


# ------------------------------------------------------------------ validação (parte do G13 que é do emissor)

def check_graph(name, obj):
    errs = []
    if not isinstance(obj, dict) or not isinstance(obj.get("nodes"), list) or not isinstance(obj.get("edges"), list):
        return ["%s: precisa ser {nodes: [...], edges: [...]}" % name]
    ids = set()
    for n in obj["nodes"]:
        if not isinstance(n, dict) or not n.get("id"):
            errs.append("%s: nó sem id" % name)
        else:
            ids.add(n["id"])
    for e in obj["edges"]:
        if isinstance(e, dict):
            a, b = e.get("from") or e.get("src") or e.get("a"), e.get("to") or e.get("dst") or e.get("b")
        elif isinstance(e, list) and len(e) >= 2:
            a, b = e[0], e[1]
        else:
            errs.append("%s: aresta malformada %r" % (name, e))
            continue
        if a not in ids or b not in ids:
            errs.append("%s: aresta %r → %r aponta para nó inexistente" % (name, a, b))
    return errs


def check_maps(root, data):
    errs = []
    kdir = Path(root) / KNOW_DIR
    loaded = {}
    for name in GENERATED + EXTERNAL:
        p = kdir / name
        if not p.is_file():
            hint = "rode `cs.py emit`" if name in GENERATED else "gerado por `cs.py team`"
            errs.append("%s/%s: ausente (%s)" % (KNOW_DIR, name, hint))
            continue
        try:
            loaded[name] = j5.load(p)
        except ValueError as exc:
            errs.append("%s/%s: JSON5 inválido: %s" % (KNOW_DIR, name, exc))
            continue
        errs += ["%s/%s" % (KNOW_DIR, e) for e in check_graph(name, loaded[name])]
    t = loaded.get("tree.json5")
    if isinstance(t, dict):
        by_id = {n.get("id"): n for n in t.get("nodes", []) if isinstance(n, dict)}
        for d in data.dirs():
            n = by_id.get(d or ".")
            if not n or not n.get("representative"):
                errs.append("tree.json5: pasta de produto %r ausente ou sem arquivo representativo" % (d or "."))
            elif n["representative"] not in data.files:
                errs.append("tree.json5: representativo %r de %r não é arquivo de produto" % (n["representative"], d))
    s = loaded.get("stack.json5")
    if isinstance(s, dict):
        got = {(n.get("name"), str(n.get("version"))) for n in s.get("nodes", []) if n.get("kind") == "package"}
        for eco, name, ver, src in stack_packages(data):
            if (name, ver) not in got:
                errs.append("stack.json5: %s@%s não bate com a fonte (%s)" % (name, ver, src))
    return errs
