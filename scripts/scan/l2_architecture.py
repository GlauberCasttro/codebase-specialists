"""L2 arquitetura: camadas/fronteiras DECLARADAS (import-linter, dependency-cruiser, ArchUnit, eslint
boundaries/no-restricted-imports, golangci depguard, ruff banned-api) × dependências REAIS entre
componentes (do grafo L1); ciclos e violações."""

import re

from cslib import paths
from cslib.evidence import ev_cmd, ev_file, slug
from cslib.jsonio import dumps
from . import golangci, l1_graph, tomlmini

LAYER = "architecture"


def _importlinter_contracts(text):
    """Contratos 'layers' de .importlinter / setup.cfg / pyproject (ini ou toml simples)."""
    contracts = []
    # INI: [importlinter:contract:x] ... type = layers ... layers = \n a \n b
    for m in re.finditer(r"\[importlinter:contract:([^\]]+)\](.*?)(?=^\[|\Z)", text, re.S | re.M):
        body = m.group(2)
        if not re.search(r"^\s*type\s*=\s*layers", body, re.M):
            continue
        lm = re.search(r"^\s*layers\s*=\s*\n((?:[ \t]+\S.*\n?)+)", body, re.M)
        if lm:
            layers = [ln.strip() for ln in lm.group(1).splitlines() if ln.strip()]
            contracts.append({"name": m.group(1).strip(), "layers": layers})
    # TOML: [[tool.importlinter.contracts]] type = "layers" layers = ["a", "b"]
    for m in re.finditer(r"\[\[tool\.importlinter\.contracts\]\](.*?)(?=^\[|\Z)", text, re.S | re.M):
        body = m.group(1)
        if not re.search(r'^\s*type\s*=\s*"layers"', body, re.M):
            continue
        lm = re.search(r"^\s*layers\s*=\s*\[(.*?)\]", body, re.S | re.M)
        nm = re.search(r'^\s*name\s*=\s*"([^"]+)"', body, re.M)
        if lm:
            layers = re.findall(r'"([^"]+)"', lm.group(1))
            contracts.append({"name": nm.group(1) if nm else "layers", "layers": layers})
    return contracts


def _module_to_prefix(mod, files):
    p = mod.replace(".", "/")
    for f in files:
        if f.startswith(p + "/") or f == p + ".py":
            return p
        idx = f.find("/" + p + "/")
        if idx >= 0:
            return f[:idx + 1] + p
    return p


def _go_imports(text):
    """[(spec, linha)] dos imports de um arquivo Go."""
    out = []
    for m in l1_graph.GO_SINGLE.finditer(text):
        out.append((m.group(1), text.count("\n", 0, m.start(1)) + 1))
    for blk in l1_graph.GO_BLOCK.finditer(text):
        for m in l1_graph.GO_LINE.finditer(blk.group(1)):
            out.append((m.group(1), text.count("\n", 0, blk.start(1) + m.start(1)) + 1))
    return sorted(set(out), key=lambda x: (x[1], x[0]))


def _depguard(ctx, rel):
    """Regras depguard do .golangci.yml → fronteiras declaradas (com conferência nos imports Go)."""
    g = golangci.parse(ctx.text(rel))
    if g.get("error"):
        return [], g["error"]
    go_files = [f for f in ctx.files if paths.lang_of(f) == "go"]
    out = []
    for r in g["depguard_rules"]:
        if not r["deny"]:
            continue
        scoped = [f for f in go_files if golangci.file_matches(f, r["files"], paths.is_test_file(f))]
        viol, users = [], []
        for f in go_files:
            imps = _go_imports(ctx.text(f))
            for spec, ln in imps:
                for d in r["deny"]:
                    if spec == d["pkg"] or spec.startswith(d["pkg"].rstrip("/") + "/"):
                        (viol if f in scoped else users).append({"file": f, "line": ln, "pkg": d["pkg"]})
        out.append({"tool": "golangci-depguard", "file": rel, "name": r["name"], "line": r["line"] or 1,
                    "files": r["files"], "deny": r["deny"], "enabled": g["depguard_enabled"],
                    "scoped_files": len(scoped), "violations": viol, "allowed_users": users})
    return out, None


def _ruff_banned(ctx, rel):
    """ruff flake8-tidy-imports.banned-api (ruff.toml / pyproject [tool.ruff]) → APIs proibidas."""
    data = tomlmini.loads(ctx.text(rel))
    base = rel.rsplit("/", 1)[-1]
    if base == "pyproject.toml":
        data = (data.get("tool") or {}).get("ruff") or {}
    lint = data.get("lint") if isinstance(data.get("lint"), dict) else {}
    tidy = lint.get("flake8-tidy-imports") or data.get("flake8-tidy-imports") or {}
    banned = tidy.get("banned-api") if isinstance(tidy, dict) else None
    if not isinstance(banned, dict) or not banned:
        return None
    lines = ctx.lines(rel)
    items = []
    for api in sorted(banned):
        v = banned[api] if isinstance(banned[api], dict) else {}
        ln = next((i for i, x in enumerate(lines, 1) if ('"%s"' % api) in x or ("'%s'" % api) in x), 1)
        items.append({"api": api, "msg": str(v.get("msg") or ""), "line": ln})
    return {"tool": "ruff-banned-api", "file": rel, "name": "banned-api", "line": items[0]["line"],
            "banned": items}


def _js_spans(text):
    """Pares (abre, fecha) de { } e [ ] fora de strings/comentários."""
    spans, stack, i, n = [], [], 0, len(text)
    while i < n:
        c = text[i]
        if c in "\"'`":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            i = j + 1
            continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c in "{[":
            stack.append(i)
        elif c in "}]" and stack:
            spans.append((stack.pop(), i))
        i += 1
    return spans


def _eslint_restricted(text):
    """Blocos `no-restricted-imports` / `import/no-restricted-paths` com o `files` do objeto de config
    que os contém. Sem `files` no objeto → vale para todos os arquivos do config."""
    spans = _js_spans(text)
    out = []
    for m in re.finditer(r"""["']?(no-restricted-imports|import/no-restricted-paths|"""
                         r"""@typescript-eslint/no-restricted-imports)["']?\s*:\s*\[""", text):
        open_pos = m.end() - 1
        close = next((c for o, c in spans if o == open_pos), None)
        if close is None:
            continue
        body = text[open_pos:close + 1]
        # objeto de config mais interno que contém a regra E declara `files` no seu nível
        files = None
        for o, c in sorted((sp for sp in spans if sp[0] < m.start() and sp[1] > close and text[sp[0]] == "{"),
                           key=lambda sp: sp[1] - sp[0]):
            inner = [sp for sp in spans if o < sp[0] < c and text[sp[0]] == "{"]
            top = text[o:c]
            fm = None
            for fx in re.finditer(r"""(?:^|[\s{,])["']?files["']?\s*:\s*\[""", top):
                pos = o + fx.end() - 1
                if not any(io < pos < ic for io, ic in inner):
                    fm = pos
                    break
            if fm is not None:
                fc = next((cc for oo, cc in spans if oo == fm), None)
                if fc is not None:
                    files = re.findall(r"""["']([^"']+)["']""", text[fm:fc])
                break
        groups = []
        for gm in re.finditer(r"""["']?(?:group|name|from)["']?\s*:\s*(\[[^\]]*\]|["'][^"']+["'])""", body):
            groups += re.findall(r"""["']([^"']+)["']""", gm.group(1))
        if not groups:
            groups = [g for g in re.findall(r"""^\[\s*["'](?:error|warn)["']\s*,\s*((?:["'][^"']+["']\s*,?\s*)+)\]""",
                                            body)
                      for g in re.findall(r"""["']([^"']+)["']""", g)]
        msgs = re.findall(r"""["']?message["']?\s*:\s*["']([^"']+)["']""", body)
        out.append({"rule": m.group(1), "line": text.count("\n", 0, m.start()) + 1, "files": files,
                    "denied": sorted(set(groups)), "message": msgs[0] if msgs else ""})
    return out


def run(ctx):
    fb = ctx.fb
    g = ctx.layer("L1")
    facts = []
    declared = []

    for rel in ctx.files:
        base = rel.rsplit("/", 1)[-1]
        text = None
        if base in ("ruff.toml", ".ruff.toml", "pyproject.toml"):
            rb = _ruff_banned(ctx, rel)
            if rb:
                declared.append(rb)
        if base in (".importlinter", "setup.cfg", "pyproject.toml"):
            text = ctx.text(rel)
            if "importlinter" in text:
                for c in _importlinter_contracts(text):
                    declared.append({"tool": "import-linter", "file": rel, "name": c["name"],
                                     "layers": c["layers"]})
        elif base.startswith(".dependency-cruiser"):
            text = ctx.text(rel)
            rules = re.findall(r"name\s*:\s*['\"]([^'\"]+)['\"]", text)
            declared.append({"tool": "dependency-cruiser", "file": rel, "name": base,
                             "rules": sorted(set(rules))})
        elif paths.lang_of(rel) in ("java", "kotlin"):
            text = ctx.text(rel)
            if "com.tngtech.archunit" in text:
                layers = re.findall(r'\.layer\(\s*"([^"]+)"\s*\)\s*\.definedBy\(\s*"([^"]+)"', text)
                declared.append({"tool": "archunit", "file": rel, "name": base,
                                 "layers": [n for n, _ in layers],
                                 "packages": {n: p for n, p in layers}})
        elif base.startswith(".eslintrc") or base.startswith("eslint.config"):
            text = ctx.text(rel)
            restricted = [r for r in _eslint_restricted(text) if r["denied"]]
            for i, r in enumerate(restricted):
                declared.append({"tool": "eslint-restricted-imports", "file": rel,
                                 "name": "%s-%d" % (base, r["line"]), "line": r["line"],
                                 "boundary": {"files": r["files"], "denied": r["denied"],
                                              "message": r["message"], "rule": r["rule"]}})
            other = sorted(set(re.findall(r"(boundaries/[\w-]+)", text)))
            if other or (not restricted and ("no-restricted-imports" in text
                                             or "import/no-restricted-paths" in text)):
                declared.append({"tool": "eslint-boundaries", "file": rel, "name": base,
                                 "rules": other or sorted(set(re.findall(
                                     r"(no-restricted-imports|import/no-restricted-paths)", text)))})
        elif base in (".golangci.yml", ".golangci.yaml"):
            rules, err = _depguard(ctx, rel)
            if err:
                declared.append({"tool": "golangci-depguard", "file": rel, "name": base, "unread": err})
            declared.extend(rules)

    # dependências reais entre componentes. Prefixos reservados ao harness/plataformas (cslib/paths:
    # `.claude/`, `.cursor/`, `.codex/`, `.github/agents/`...) não são componente de topo do produto — um hook
    # instalado (`.claude/hooks/cs-guard.sh`) virava "5 componentes em vez de 4" no ts-shop (iteração 4).
    comp_edges = {}
    for e in g["edges"]:
        s, t, w = e[0], e[1], e[2]
        if paths.is_reserved(s) or paths.is_reserved(t):
            continue
        cs, ct = paths.component_of(s), paths.component_of(t)
        if cs != ct:
            comp_edges[(cs, ct)] = comp_edges.get((cs, ct), 0) + w
    comps = sorted(set(paths.component_of(n["path"]) for n in g["nodes"] if not paths.is_reserved(n["path"])))
    deps = {c: sorted(t for (s, t) in comp_edges if s == c) for c in comps}
    cycles = sorted(set(tuple(sorted((a, b))) for (a, b) in comp_edges
                        if (b, a) in comp_edges and a != b))

    # violações de contratos import-linter (camada de cima pode importar a de baixo, não o inverso)
    violations = []
    for d in declared:
        if d["tool"] != "import-linter":
            continue
        prefixes = [_module_to_prefix(m.split("|")[0].strip(), ctx.files) for m in d["layers"]]
        for e in g["edges"]:
            s, t = e[0], e[1]
            ls = next((i for i, p in enumerate(prefixes) if s.startswith(p + "/") or s == p + ".py"),
                      None)
            lt = next((i for i, p in enumerate(prefixes) if t.startswith(p + "/") or t == p + ".py"),
                      None)
            if ls is not None and lt is not None and lt < ls:
                violations.append({"contract": d["name"], "from": s, "to": t,
                                   "rule": "%s não pode importar %s" % (d["layers"][ls], d["layers"][lt])})

    matrix_ev = ev_cmd("scan:L2 agregação de arestas L1 por componente", 0,
                       dumps(sorted([a, b, w] for (a, b), w in comp_edges.items())).encode("utf-8"))
    facts.append(fb.fact("arch.components", LAYER,
                         "%d componentes de topo com código; %d dependências entre componentes; "
                         "%d ciclos entre componentes" % (len(comps), len(comp_edges), len(cycles)),
                         [matrix_ev], scope=["**"]))
    for c in comps:
        if deps[c]:
            facts.append(fb.fact("arch.deps.%s" % slug(c), LAYER,
                                 "Componente %s depende de: %s" % (c, ", ".join(deps[c])),
                                 [matrix_ev], confidence="high", scope=[c + "/**" if c != "." else "*"]))
    importers = {}
    for (s, t) in comp_edges:
        importers.setdefault(t, set()).add(s)
    for c in comps:
        if importers.get(c) and not deps[c] and len(importers[c]) >= 2:
            facts.append(fb.fact("arch.base.%s" % slug(c), LAYER,
                                 "Componente %s é base: importado por %s e não importa outros "
                                 "componentes" % (c, ", ".join(sorted(importers[c]))),
                                 [matrix_ev], confidence="medium", scope=[c + "/**"]))
    for a, b in cycles:
        ex = sorted([e[0], e[1]] for e in g["edges"]
                    if {paths.component_of(e[0]), paths.component_of(e[1])} == {a, b})[:4]
        facts.append(fb.fact("arch.cycle.%s.%s" % (slug(a), slug(b)), LAYER,
                             "Ciclo de dependência entre componentes %s ⇄ %s" % (a, b),
                             [ev_file(x) for pair in ex for x in pair][:6] or [matrix_ev],
                             confidence="high", scope=[a + "/**", b + "/**"]))
    for d in declared:
        fid = "arch.declared.%s.%s" % (slug(d["tool"]), slug(d["name"]))
        if d["tool"] == "golangci-depguard" and d.get("unread"):
            facts.append(fb.fact(fid, LAYER, "Config golangci em %s não lida mecanicamente (%s): regras depguard "
                                 "(fronteiras de import) podem existir — confira à mão" % (d["file"], d["unread"]),
                                 [ev_file(d["file"])], confidence="low", scope=["**"]))
            continue
        if d["tool"] == "golangci-depguard":
            fx = d["files"] or ["$all"]
            deny = "; ".join("%s%s" % (x["pkg"], (" (\"%s\")" % x["desc"]) if x["desc"] else "")
                             for x in d["deny"])
            claim = ("Fronteira declarada (golangci depguard, regra '%s') em %s:%d: import de %s proibido em "
                     "arquivos Go que casam %s (%d arquivos hoje)%s" % (
                         d["name"], d["file"], d["line"], deny, fx, d["scoped_files"],
                         "" if d["enabled"] else "; ATENÇÃO: depguard não está habilitado em linters.enable — "
                                                 "a regra existe mas não roda"))
            if d["violations"]:
                claim += "; %d violação(ões) hoje: %s" % (len(d["violations"]), ", ".join(
                    "%s:%d" % (v["file"], v["line"]) for v in d["violations"][:5]))
            else:
                claim += "; 0 violações nos imports Go atuais"
            if d["allowed_users"]:
                claim += "; usado só fora do escopo proibido: %s" % ", ".join(sorted(set(
                    u["file"] for u in d["allowed_users"]))[:6])
            ev = [ev_file(d["file"], d["line"])] + [ev_file(x["file"], x["line"])
                                                    for x in (d["violations"] or d["allowed_users"])[:3]]
            facts.append(fb.fact(fid, LAYER, claim, ev, confidence="high" if d["enabled"] else "medium",
                                 scope=["**"], data={"kind": "boundary", "tool": "golangci-depguard",
                                                     "rule": d["name"], "files": fx,
                                                     "deny": [x["pkg"] for x in d["deny"]],
                                                     "enforced": d["enabled"],
                                                     "violations": len(d["violations"])}))
            continue
        if d["tool"] == "eslint-restricted-imports":
            b = d["boundary"]
            claim = "Fronteira declarada (eslint %s) em %s:%d: arquivos %s não podem importar %s%s" % (
                b["rule"], d["file"], d["line"], b["files"] or "(todos do config)", ", ".join(b["denied"]),
                (" — \"%s\"" % b["message"]) if b["message"] else "")
            facts.append(fb.fact(fid, LAYER, claim, [ev_file(d["file"], d["line"])],
                                 confidence="high" if b["files"] is not None else "medium", scope=["**"],
                                 data={"kind": "boundary", "tool": "eslint", "rule": b["rule"],
                                       "files": b["files"], "deny": b["denied"]}))
            continue
        if d["tool"] == "ruff-banned-api":
            claim = "APIs proibidas declaradas (ruff flake8-tidy-imports.banned-api) em %s:%d: %s" % (
                d["file"], d["line"], "; ".join("%s%s" % (x["api"], (" (\"%s\")" % x["msg"]) if x["msg"] else "")
                                                for x in d["banned"]))
            facts.append(fb.fact(fid, LAYER, claim, [ev_file(d["file"], x["line"]) for x in d["banned"][:4]],
                                 confidence="high", scope=["**"],
                                 data={"kind": "banned_api", "tool": "ruff",
                                       "deny": [x["api"] for x in d["banned"]]}))
            continue
        facts.append(fb.fact(fid, LAYER,
                             "Arquitetura declarada (%s) em %s: %s" % (
                                 d["tool"], d["file"],
                                 " > ".join(d.get("layers") or []) or ", ".join(d.get("rules") or [])
                                 or d["name"]),
                             [ev_file(d["file"])], scope=["**"]))
    for i, v in enumerate(violations[:30]):
        facts.append(fb.fact("arch.violation.%s" % slug("%s-%s" % (v["from"], v["to"])), LAYER,
                             "Violação do contrato '%s': %s importa %s (%s)"
                             % (v["contract"], v["from"], v["to"], v["rule"]),
                             [ev_file(v["from"]), ev_file(v["to"])], scope=[v["from"]]))
    if not declared:
        facts.append(fb.fact("arch.declared.none", LAYER,
                             "Nenhuma arquitetura declarada por ferramenta (import-linter, "
                             "dependency-cruiser, ArchUnit, eslint boundaries/no-restricted-imports, golangci "
                             "depguard, ruff banned-api) — camadas só implícitas",
                             [ev_cmd("scan:L2 busca de configs de arquitetura", 1, b"")],
                             confidence="high", scope=["**"]))
    return {"layer": LAYER, "components": comps, "component_edges":
            [[a, b, w] for (a, b), w in sorted(comp_edges.items())], "cycles": [list(c) for c in cycles],
            "declared": declared, "violations": violations, "facts": facts}
