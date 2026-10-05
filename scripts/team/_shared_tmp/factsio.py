"""Leitura tolerante das camadas do scan (.swarm/facts/*.json5).

ÚNICO ponto que conhece a forma interna das camadas. Formato-base: fato do ARCHITECTURE §4.
Cada arquivo de camada pode ser (a) uma lista de fatos ou (b) um objeto com "facts": [...] e chaves
estruturadas extras. Campos extras lidos (todos opcionais; ver references/probes.md):

  inventory: files[] (str | {path, class|classification|category|tags}), manifests[]
  graph:     nodes[] ({id|path|file, pagerank, community}), edges[] ([a,b] | {src|from|source,
             dst|to|target}), communities ({id:[paths]} | [[paths]]), symbols[] ({name, kind,
             path|file, line, signature?, doc?}); fatos com data.symbol também viram símbolos
  rules:     fatos; data.{kind, pattern, count, tool}; negativa = data.count == 0 ou kind negativo
  operations:fatos com data.{command|cmd, status|verified, kind|purpose}; ou commands[]
  history:   fatos com data.{sha, subject, files, kind}; ou fix_commits[]
  rationale: fatos com evidence file:line e data.{topic|decision, key_terms[]}
  glossary:  fatos com data.{term|canonical, category business|technical, synonyms[], never_use[],
             definition?}; evidence[0] = onde é definido (arquivo:linha)
  business_rules: fatos com data.{subject, kind (limit|state|validation|transition|...), value?,
             test?}; evidence = onde é imposta (arquivo:linha)
"""
import os
import re

from team._shared_tmp.common import (find_doc, CsError, IGNORED_CLASSES, list_repo_files, path_class,
                                     read_json, read_lines, sp_path)

LAYERS = ("inventory", "graph", "architecture", "conventions", "rules", "history", "rationale",
          "operations", "stack", "glossary", "business_rules")


class Facts(object):
    def __init__(self, target, require_inventory=True):
        self.target = target
        self.dir = sp_path(target, "facts")
        if not os.path.isdir(self.dir):
            raise CsError("diretório de fatos ausente: %s" % self.dir, "rode `cs.py scan` antes")
        self.raw = {}
        self.facts = {}        # layer -> [fact]
        self.by_id = {}
        self.missing = []
        for layer in LAYERS:
            p = os.path.join(self.dir, layer + ".json5")
            if not os.path.isfile(find_doc(p)):
                self.missing.append(layer)
                self.raw[layer] = {}
                self.facts[layer] = []
                continue
            raw = read_json(p, "camada %s" % layer)
            facts = raw if isinstance(raw, list) else (raw.get("facts") or [])
            self.raw[layer] = raw if isinstance(raw, dict) else {}
            fl = []
            for f in facts:
                if isinstance(f, dict) and f.get("id"):
                    f.setdefault("layer", layer)
                    fl.append(f)
                    self.by_id[f["id"]] = f
            self.facts[layer] = sorted(fl, key=lambda x: x["id"])
        if require_inventory and "inventory" in self.missing:
            raise CsError("inventory.json5 ausente em %s" % self.dir,
                          "rode o scan L0; sem inventário a classificação fixture/vendor não existe")
        self._files = None
        self._all = None

    # -------------------------------------------------------------- índice
    def index_ids(self):
        """IDs do index.json5 (ausente = erro explícito)."""
        p = os.path.join(self.dir, "index.json5")
        raw = read_json(p, "facts/index.json5")
        ids = set()
        if isinstance(raw, dict):
            src = raw.get("facts", raw.get("ids", raw))
            if isinstance(src, dict):
                ids.update(k for k in src.keys() if k not in ("schema_version", "layers"))
            elif isinstance(src, list):
                for x in src:
                    ids.add(x["id"] if isinstance(x, dict) else x)
        elif isinstance(raw, list):
            for x in raw:
                ids.add(x["id"] if isinstance(x, dict) else x)
        ids.update(self.by_id.keys())
        return ids

    # -------------------------------------------------------------- inventário
    def _inventory_entries(self):
        raw = self.raw.get("inventory") or {}
        entries = raw.get("files")
        if entries is None:
            for f in self.facts.get("inventory", []):
                d = f.get("data") or {}
                if isinstance(d.get("files"), list):
                    entries = (entries or []) + d["files"]
        return entries

    def all_files(self):
        """Todos os arquivos versionados (inclui ignorados), POSIX relativo, ordenado."""
        if self._all is None:
            entries = self._inventory_entries()
            if entries is None:
                self._all = list_repo_files(self.target)
            else:
                self._all = sorted(set((e if isinstance(e, str) else (e.get("path") or e.get("file")))
                                       for e in entries if e))
        return self._all

    def product_files(self):
        """Produto = não reservado e não fixture/vendor/generated (inventário E heurística de path)."""
        if self._files is None:
            ignored = set()
            entries = self._inventory_entries() or []
            for e in entries:
                if isinstance(e, dict):
                    p = e.get("path") or e.get("file")
                    tags = set()
                    for k in ("class", "classification", "category", "kind"):
                        if isinstance(e.get(k), str):
                            tags.add(e[k])
                    if isinstance(e.get("tags"), list):
                        tags.update(e["tags"])
                    for k in IGNORED_CLASSES:
                        if e.get(k) is True:
                            tags.add(k)
                    if tags & (IGNORED_CLASSES | {"reserved"}):
                        ignored.add(p)
            self._files = [f for f in self.all_files()
                           if f not in ignored and path_class(f) == "product"]
        return self._files

    def example_files(self):
        """Categoria `example` (examples/**, samples/** fora de teste): fora da análise, mas com dono possível."""
        if getattr(self, "_examples", None) is None:
            tagged = set()
            for e in self._inventory_entries() or []:
                if isinstance(e, dict) and "example" in (e.get("category"), e.get("class"), e.get("kind")):
                    tagged.add(e.get("path") or e.get("file"))
            self._examples = sorted(f for f in self.all_files() if f in tagged or path_class(f) == "example")
        return self._examples

    def ownable_files(self):
        """Arquivos que PODEM ter dono de escrita: produto + exemplos. Cobertura 100% vale só para produto."""
        return sorted(set(self.product_files()) | set(self.example_files()))

    def reserved_files(self):
        return [f for f in self.all_files() if path_class(f) == "reserved"]

    def manifests(self):
        raw = self.raw.get("inventory") or {}
        ms = raw.get("manifests")
        out = []
        if isinstance(ms, list):
            for m in ms:
                p = m if isinstance(m, str) else (m.get("path") or m.get("file"))
                if p:
                    out.append(p)
        if not out:
            names = {"package.json", "pyproject.toml", "setup.py", "go.mod", "Cargo.toml", "pom.xml",
                     "build.gradle", "build.gradle.kts", "Gemfile", "composer.json", "mix.exs"}
            out = [f for f in self.product_files()
                   if f.rsplit("/", 1)[-1] in names or f.endswith(".csproj")]
        return sorted(set(out))

    # -------------------------------------------------------------- grafo
    def edges(self):
        raw = self.raw.get("graph") or {}
        out = set()
        for e in raw.get("edges") or []:
            if isinstance(e, (list, tuple)) and len(e) >= 2:
                a, b = e[0], e[1]
            elif isinstance(e, dict):
                a = e.get("src") or e.get("from") or e.get("source")
                b = e.get("dst") or e.get("to") or e.get("target")
            else:
                continue
            if a and b and a != b:
                out.add((a, b))
        return sorted(out)

    def has_graph(self):
        return "graph" not in self.missing

    def communities(self):
        """{path: community_id(str)}."""
        raw = self.raw.get("graph") or {}
        out = {}
        com = raw.get("communities")
        if isinstance(com, dict):
            for cid, paths in com.items():
                for p in paths or []:
                    out[p] = str(cid)
        elif isinstance(com, list):
            for i, paths in enumerate(com):
                if isinstance(paths, dict):
                    cid = str(paths.get("id", i))
                    paths = paths.get("files") or paths.get("members") or []
                else:
                    cid = str(i)
                for p in paths or []:
                    out[p] = cid
        for n in raw.get("nodes") or []:
            if isinstance(n, dict):
                p = n.get("id") or n.get("path") or n.get("file")
                if p and n.get("community") is not None and p not in out:
                    out[p] = str(n["community"])
        return out

    def pagerank(self):
        raw = self.raw.get("graph") or {}
        out = {}
        for n in raw.get("nodes") or []:
            if isinstance(n, dict):
                p = n.get("id") or n.get("path") or n.get("file")
                if p and isinstance(n.get("pagerank"), (int, float)):
                    out[p] = float(n["pagerank"])
        return out

    def symbols(self):
        raw = self.raw.get("graph") or {}
        out = []
        for s in raw.get("symbols") or []:
            if isinstance(s, dict) and s.get("name") and (s.get("path") or s.get("file")):
                out.append({"name": s["name"], "kind": s.get("kind") or "symbol",
                            "path": s.get("path") or s.get("file"), "line": int(s.get("line") or 1),
                            "signature": s.get("signature") or "", "doc": s.get("doc") or "",
                            "fact": s.get("fact")})
        for f in self.facts.get("graph", []):
            d = f.get("data") or {}
            sym = d.get("symbol")
            ev = [e for e in f.get("evidence") or [] if isinstance(e, dict) and e.get("file")]
            if sym and ev:
                if isinstance(sym, str):
                    sym = {"name": sym}
                out.append({"name": sym.get("name"), "kind": sym.get("kind") or d.get("kind") or "symbol",
                            "path": ev[0]["file"], "line": int(sym.get("line") or ev[0].get("line") or 1),
                            "signature": sym.get("signature") or "", "doc": sym.get("doc") or "",
                            "fact": f["id"]})
        if not out:
            out = self._regex_symbols()
        seen, res = set(), []
        for s in sorted(out, key=lambda x: (x["path"], x["line"], x["name"])):
            k = (s["path"], s["line"], s["name"])
            if k not in seen:
                seen.add(k)
                res.append(s)
        return res

    _DEF_RES = [
        (re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*(\([^)]*\))?"), "function", (".py",)),
        (re.compile(r"^\s*class\s+([A-Za-z_]\w*)"), "class", (".py", ".rb", ".java", ".kt", ".cs", ".ts", ".tsx",
                                                          ".js", ".jsx", ".php", ".swift", ".scala", ".dart")),
        (re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)\s*(\([^)]*\))?"),
         "function", (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")),
        (re.compile(r"^\s*(?:export\s+)?(?:interface|type|enum)\s+([A-Za-z_]\w*)"), "type",
         (".ts", ".tsx", ".java", ".kt", ".cs", ".swift")),
        (re.compile(r"^func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*(\([^)]*\))?"), "function", (".go",)),
        (re.compile(r"^type\s+([A-Za-z_]\w*)\s+(?:struct|interface)"), "type", (".go",)),
        (re.compile(r"^\s*(?:pub\s+)?(?:fn|struct|enum|trait)\s+([A-Za-z_]\w*)\s*(\([^)]*\))?"), "symbol", (".rs",)),
        (re.compile(r"^\s*def\s+(?:self\.)?([A-Za-z_]\w*[?!]?)\s*(\([^)]*\))?"), "method", (".rb",)),
    ]

    def _regex_symbols(self, cap=5000):
        """Fallback mecânico quando o grafo não traz símbolos: definições por regex por linguagem."""
        out = []
        for p in self.product_files():
            ext = os.path.splitext(p)[1].lower()
            res = [(rx, k) for rx, k, exts in self._DEF_RES if ext in exts]
            if not res:
                continue
            for i, ln in enumerate(read_lines(self.target, p) or []):
                for rx, kind in res:
                    m = rx.match(ln)
                    if m and not m.group(1).startswith("__"):
                        sig = ""
                        if m.lastindex and m.lastindex >= 2 and m.group(2):
                            sig = m.group(1) + m.group(2)
                        out.append({"name": m.group(1), "kind": kind, "path": p, "line": i + 1,
                                    "signature": sig, "doc": "", "fact": None})
                        break
                if len(out) >= cap:
                    return out
        return out

    # -------------------------------------------------------------- regras / ops / história / racional
    def rules(self):
        return list(self.facts.get("rules", []))

    def interview_invariants(self):
        out = []
        p = os.path.join(self.dir, "interview.json5")
        if os.path.isfile(find_doc(p)):
            raw = read_json(p, "facts/interview.json5")
            fl = raw if isinstance(raw, list) else raw.get("facts") or []
            for f in fl:
                if isinstance(f, dict) and f.get("id"):
                    f.setdefault("layer", "interview")
                    self.by_id.setdefault(f["id"], f)
                    out.append(f)
        return sorted(out, key=lambda x: x["id"])

    @staticmethod
    def is_negative(f):
        d = f.get("data") or {}
        kind = str(d.get("kind") or "").lower()
        return d.get("count") == 0 or kind in ("negative", "negative_invariant", "invariant_negative") \
            or f["id"].startswith(("rules.neg", "rule.neg"))

    def negatives(self):
        """Invariantes negativas: [{fact, regex, desc, scope}] (rules.never.* + data.pattern)."""
        raw = self.raw.get("rules") or {}
        checks = {}
        for n in raw.get("negative_checks") or []:
            if isinstance(n, dict) and n.get("pattern"):
                checks["rules.never.%s.%s" % (n.get("lang"), n.get("key"))] = n
        out = []
        for f in self.rules():
            if not self.is_negative(f):
                continue
            d = f.get("data") or {}
            n = checks.get(f["id"])
            if n:
                out.append({"fact": f["id"], "regex": n["pattern"], "desc": n.get("desc") or n["pattern"],
                            "scope": f.get("scope") or []})
            elif d.get("pattern"):
                rx = d["pattern"] if d.get("regex") else re.escape(d["pattern"])
                out.append({"fact": f["id"], "regex": rx, "desc": "`%s`" % d["pattern"],
                            "scope": f.get("scope") or []})
        return out

    def cochange(self):
        """[{a, b, support, conf_a_b, conf_b_a, fact}] do L5. TODO(integrador): usar o helper de
        co-change de cslib quando exposto; hoje lê history.json5 (raw.cochange / fatos hist.cochange.*)."""
        raw = self.raw.get("history") or {}
        out = {}
        for c in raw.get("cochange") or []:
            if isinstance(c, dict) and c.get("a") and c.get("b"):
                out[tuple(sorted((c["a"], c["b"])))] = {
                    "a": c["a"], "b": c["b"], "support": int(c.get("support") or 0),
                    "conf_a_b": float(c.get("conf_a_b") or 0), "conf_b_a": float(c.get("conf_b_a") or 0),
                    "fact": None}
        for f in self.facts.get("history", []):
            if not f["id"].startswith("hist.cochange."):
                continue
            d = f.get("data") or {}
            sc = [x for x in f.get("scope") or [] if isinstance(x, str)]
            pair = (d.get("a"), d.get("b")) if d.get("a") else (tuple(sc[:2]) if len(sc) >= 2 else None)
            if not pair or not pair[0]:
                continue
            k = tuple(sorted(pair))
            if k in out:
                out[k]["fact"] = f["id"]
                continue
            m = re.search(r"suporte (\d+); confian\w+ ([\d.]+) / ([\d.]+)", f.get("claim") or "")
            out[k] = {"a": pair[0], "b": pair[1], "support": int(d.get("support") or (m.group(1) if m else 0)),
                      "conf_a_b": float(d.get("conf_a_b") or (m.group(2) if m else 0)),
                      "conf_b_a": float(d.get("conf_b_a") or (m.group(3) if m else 0)), "fact": f["id"]}
        return [out[k] for k in sorted(out)]

    def operations(self):
        """[{command, status, kind, fact, scope}] — status verified|declared."""
        out = []
        raw = self.raw.get("operations") or {}
        by_cmd = {}
        for f in self.facts.get("operations", []):
            for e in f.get("evidence") or []:
                if isinstance(e, dict) and e.get("cmd"):
                    by_cmd.setdefault(e["cmd"], f["id"])
            m = re.match(r"^`([^`]+)`", f.get("claim") or "")
            if m:
                by_cmd.setdefault(m.group(1), f["id"])
        for c in raw.get("commands") or []:
            if isinstance(c, dict) and (c.get("command") or c.get("cmd")):
                cmd = c.get("command") or c.get("cmd")
                src = c.get("source") if isinstance(c.get("source"), dict) else {}
                purpose = c.get("purpose") or ""
                if not purpose and src.get("file"):
                    purpose = "%s (declarado em %s)" % (c.get("kind") or "comando", src["file"])
                out.append({"command": cmd,
                            "status": "verified" if (c.get("status") == "verified" or c.get("verified") is True)
                            else (c.get("status") or "declared"),
                            "kind": c.get("kind") or "comando", "purpose": purpose,
                            "fact": c.get("fact") or c.get("id") or by_cmd.get(cmd),
                            "scope": c.get("scope") or []})
        for f in self.facts.get("operations", []):
            d = f.get("data") or {}
            cmd = d.get("command") or d.get("cmd")
            if not cmd:
                continue
            st = d.get("status") or f.get("status")
            if d.get("verified") is True or f.get("verified") is True:
                st = "verified"
            out.append({"command": cmd, "status": st or "declared",
                        "kind": d.get("kind") or d.get("purpose") or "comando",
                        "purpose": d.get("purpose") or "", "fact": f["id"], "scope": f.get("scope") or []})
        seen, res = set(), []
        for o in sorted(out, key=lambda x: (x["command"], x["status"] != "verified")):
            if o["command"] not in seen:
                seen.add(o["command"])
                res.append(o)
        return res

    def fix_commits(self):
        out = []
        raw = self.raw.get("history") or {}
        for c in (raw.get("fix_commits") or []) + (raw.get("fixes") or []):
            if isinstance(c, dict) and c.get("sha"):
                fid = c.get("fact") or c.get("id")
                if not fid and ("hist.fix.%s" % c["sha"][:12]) in self.by_id:
                    fid = "hist.fix.%s" % c["sha"][:12]
                out.append({"sha": c["sha"], "subject": c.get("subject") or "", "files": c.get("files") or [],
                            "fact": fid})
        for f in self.facts.get("history", []):
            d = f.get("data") or {}
            if d.get("sha") and str(d.get("kind") or "fix").lower() in ("fix", "bugfix", "correction", "revert"):
                files = d.get("files") or [e["file"] for e in f.get("evidence") or []
                                           if isinstance(e, dict) and e.get("file")]
                out.append({"sha": d["sha"], "subject": d.get("subject") or f.get("claim") or "",
                            "files": files, "fact": f["id"]})
        seen, res = set(), []
        for c in sorted(out, key=lambda x: x["sha"]):
            if c["sha"] not in seen:
                seen.add(c["sha"])
                res.append(c)
        return res

    def rationale(self):
        out = []
        for f in self.facts.get("rationale", []):
            d = f.get("data") or {}
            ev = [e for e in f.get("evidence") or [] if isinstance(e, dict) and e.get("file")]
            if not ev:
                continue
            terms = d.get("key_terms") or ([d["key_term"]] if d.get("key_term") else [])
            topic = d.get("topic") or d.get("decision")
            if not topic:
                m = re.match(r"^Decis\w+ '([^']+)'", f.get("claim") or "")
                topic = ("foi tomada a decisão \"%s\"" % m.group(1)) if m else f.get("claim", "")
            out.append({"fact": f["id"], "topic": topic,
                        "key_terms": [t for t in terms if t],
                        "sources": [{"file": e["file"], "line": int(e.get("line") or 1)} for e in ev]})
        return out


    def glossary(self):
        out = []
        for f in self.facts.get("glossary", []):
            d = f.get("data") or {}
            canon = d.get("canonical") or d.get("term")
            ev = [e for e in f.get("evidence") or [] if isinstance(e, dict) and e.get("file")]
            if not canon:
                continue
            out.append({"fact": f["id"], "term": canon, "category": d.get("category") or "technical",
                        "synonyms": sorted(set(x for x in d.get("synonyms") or [] if x and x != canon)),
                        "never_use": sorted(set(x for x in d.get("never_use") or [] if x)),
                        "definition": d.get("definition") or "",
                        "defined_at": ({"file": ev[0]["file"], "line": int(ev[0].get("line") or 1)}
                                       if ev else None),
                        "scope": f.get("scope") or []})
        return out

    def business_rules(self):
        out = []
        for f in self.facts.get("business_rules", []):
            d = f.get("data") or {}
            ev = [e for e in f.get("evidence") or [] if isinstance(e, dict) and e.get("file")]
            if not ev:
                continue
            out.append({"fact": f["id"], "subject": d.get("subject") or f.get("claim", ""),
                        "kind": d.get("kind") or "regra", "value": d.get("value"),
                        "test": d.get("test"), "coverage": d.get("coverage") or ("test" if d.get("test") else None),
                        "exercised_by": d.get("exercised_by"), "source": d.get("source") or f.get("source"),
                        "sources": [{"file": e["file"], "line": int(e.get("line") or 1)} for e in ev],
                        "scope": f.get("scope") or []})
        return out


def fact_files(f):
    return sorted(set(e["file"] for e in f.get("evidence") or [] if isinstance(e, dict) and e.get("file")))
