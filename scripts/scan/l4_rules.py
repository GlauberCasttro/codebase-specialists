"""L4 regras: configs de lint/format/CI/pre-commit/editorconfig/Makefile, asserts de teste por
unidade, invariantes negativas (padrões arriscados com 0 ocorrências no código de produto)."""

import json
import re

from cslib import paths
from cslib.evidence import ev_cmd, ev_file, slug
from . import commands as cmdx
from . import golangci
from . import tomlmini

LAYER = "rules"


def _line(lines, pat, default=1):
    rx = re.compile(pat)
    return next((i for i, ln in enumerate(lines, 1) if rx.search(ln)), default)


def _ini_sections(text):
    out, cur = {}, None
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith(("#", ";")):
            continue
        m = re.match(r"^\[([^\]]+)\]$", s)
        if m:
            cur = out.setdefault(m.group(1).strip(), {})
            continue
        if cur is not None and "=" in s and not ln.startswith((" ", "\t")):
            k, v = s.split("=", 1)
            cur[k.strip()] = v.strip()
    return out


def config_rules(ctx):
    """Lista de (id, claim, file, line, scope)."""
    rules = []
    for rel in ctx.files:
        base = rel.rsplit("/", 1)[-1]
        lines = ctx.lines(rel) if not ctx.is_binary(rel) else []
        text = "\n".join(lines)
        sc = [paths.component_of(rel) + "/**"] if "/" in rel else ["**"]
        if base == "pyproject.toml":
            data = tomlmini.loads(text)
            tool = data.get("tool") or {}
            ruff = tool.get("ruff") or {}
            if ruff:
                lint = ruff.get("lint") or {}
                sel = lint.get("select") or ruff.get("select") or []
                ign = lint.get("ignore") or ruff.get("ignore") or []
                bits = []
                if ruff.get("line-length"):
                    bits.append("line-length=%s" % ruff["line-length"])
                if ruff.get("target-version"):
                    bits.append("target=%s" % ruff["target-version"])
                if sel:
                    bits.append("select=%s" % ",".join(map(str, sel)))
                if ign:
                    bits.append("ignore=%s" % ",".join(map(str, ign)))
                rules.append(("ruff", "ruff configurado em %s: %s" % (rel, "; ".join(bits) or "padrão"),
                              rel, _line(lines, r"^\[tool\.ruff"), sc))
            if tool.get("black"):
                rules.append(("black", "black configurado (line-length=%s)" %
                              tool["black"].get("line-length", 88), rel, _line(lines, r"^\[tool\.black"), sc))
            if tool.get("mypy"):
                rules.append(("mypy", "mypy configurado%s" % (" (strict)" if tool["mypy"].get("strict")
                                                               else ""),
                              rel, _line(lines, r"^\[tool\.mypy"), sc))
            pt = (tool.get("pytest") or {}).get("ini_options") or {}
            if pt:
                rules.append(("pytest", "pytest configurado: %s" % ", ".join(
                    "%s=%s" % (k, pt[k]) for k in sorted(pt) if k in ("testpaths", "addopts", "markers"))
                    or "pytest configurado", rel, _line(lines, r"^\[tool\.pytest"), sc))
            req = (data.get("project") or {}).get("requires-python")
            if req:
                rules.append(("requires-python", "Python exigido: %s" % req, rel,
                              _line(lines, r"requires-python"), sc))
        elif base in ("ruff.toml", ".ruff.toml"):
            rules.append(("ruff", "ruff configurado em %s" % rel, rel, 1, sc))
        elif base in (".flake8", "setup.cfg", "tox.ini"):
            sec = _ini_sections(text).get("flake8")
            if sec:
                rules.append(("flake8", "flake8: %s" % ", ".join("%s=%s" % (k, sec[k]) for k in sorted(sec)
                                                                if k in ("max-line-length", "ignore",
                                                                         "select", "extend-ignore"))
                              or "flake8 configurado", rel, _line(lines, r"^\[flake8\]"), sc))
        elif base.startswith(".eslintrc") or base.startswith("eslint.config"):
            names = sorted(set(re.findall(r"['\"]((?:@[\w-]+/)?[\w-]+(?:/[\w-]+)?)['\"]\s*:\s*\[?\s*['\"]?"
                                          r"(?:error|warn|2|1)", text)))
            rules.append(("eslint", "eslint em %s com %d regras explícitas%s" % (
                rel, len(names), (": " + ", ".join(names[:12])) if names else ""), rel, 1, sc))
        elif base == ".editorconfig":
            secs = _ini_sections(text)
            for name in sorted(secs):
                kv = secs[name]
                if kv:
                    rules.append(("editorconfig.%s" % slug(name), "editorconfig [%s]: %s" % (
                        name, ", ".join("%s=%s" % (k, kv[k]) for k in sorted(kv))),
                        rel, _line(lines, re.escape("[%s]" % name)), ["**"]))
        elif base == ".pre-commit-config.yaml":
            for i, ln in enumerate(lines, 1):
                m = re.match(r"^\s*-\s+id:\s*([\w.-]+)", ln)
                if m:
                    rules.append(("pre-commit.%s" % m.group(1), "pre-commit roda o hook '%s'" % m.group(1),
                                  rel, i, ["**"]))
        elif base in ("lefthook.yml", "lefthook.yaml", ".lefthook.yml"):
            for i, ln in enumerate(lines, 1):
                m = re.match(r"^(\s+)run:\s*(.+)$", ln)
                if not m:
                    continue
                val = m.group(2).strip()
                if val in ("|", ">", "|-", ">-", "|+"):
                    ind = len(m.group(1))
                    body = []
                    for nxt in lines[i:]:
                        if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= ind:
                            break
                        if nxt.strip():
                            body.append(nxt.strip())
                    val = " ; ".join(body)[:200]
                if val:
                    rules.append(("lefthook.%s" % slug(val)[:40], "hook git (lefthook) roda: %s" % val,
                                  rel, i, ["**"]))
        elif base in (".golangci.yml", ".golangci.yaml"):
            g = golangci.parse(text)
            if g.get("error"):
                # não lido → não conta nada (contagem errada é pior que ausente)
                rules.append(("golangci", "golangci-lint configurado em %s (arquivo não lido mecanicamente: %s)"
                              % (rel, g["error"]), rel, 1, sc))
            else:
                en = g["enable"]
                extra = {"standard": "; sem disable-all/default: none, os linters padrão do golangci-lint "
                                     "também rodam",
                         "all": "; enable-all/default: all — todos os linters rodam",
                         "none": ""}.get(g["base"], "")
                rules.append(("golangci", "golangci-lint em %s: %d linters habilitados em linters.enable "
                              "(%s)%s%s" % (rel, len(en), ", ".join(en) or "nenhum", extra,
                                            ("; desabilitados: %s" % ", ".join(g["disable"])) if g["disable"]
                                            else ""),
                              rel, g.get("enable_line") or 1, sc))
        elif base in (".rubocop.yml", "rustfmt.toml", ".rustfmt.toml", "clippy.toml", ".prettierrc",
                      ".prettierrc.json", ".shellcheckrc", ".stylelintrc", "phpcs.xml", "checkstyle.xml"):
            rules.append((slug(base), "%s presente em %s" % (base, rel), rel, 1, sc))
        elif base == "tsconfig.json":
            if re.search(r'"strict"\s*:\s*true', text):
                rules.append(("tsconfig.strict", "TypeScript em modo strict (%s)" % rel, rel,
                              _line(lines, r'"strict"'), sc))
        elif base == "package.json":
            try:
                eng = (json.loads(text).get("engines") or {})
            except ValueError:
                eng = {}
            for k in sorted(eng):
                rules.append(("engines.%s" % k, "engines.%s = %s" % (k, eng[k]), rel,
                              _line(lines, '"%s"' % k), sc))
    # CI: comandos de lint/test que a CI roda
    for c in cmdx.all_commands(ctx):
        src = c["source"]["file"]
        if src.startswith(".github/workflows/") or src.endswith(".gitlab-ci.yml"):
            if c["kind"] in ("test", "lint", "check", "build", "format"):
                rules.append(("ci.%s" % slug(c["cmd"])[:60], "CI (%s) roda `%s` [%s]" % (
                    src, c["cmd"], c["kind"]), src, c["source"]["line"], ["**"]))
        elif c["source"]["file"].rsplit("/", 1)[-1] in ("Makefile", "makefile", "GNUmakefile") \
                and c["kind"] in ("test", "lint", "check"):
            rules.append(("make.%s" % slug(c["name"]), "Makefile define `%s` [%s]" % (c["cmd"], c["kind"]),
                          src, c["source"]["line"], ["**"]))
    return rules


ASSERT_RE = {
    "python": re.compile(r"^\s*assert\b|\bself\.assert\w+\(|\bpytest\.raises\(|\bself\.fail\(", re.M),
    "javascript": re.compile(r"\bexpect\(|\bassert(?:\.\w+)?\("),
    "typescript": re.compile(r"\bexpect\(|\bassert(?:\.\w+)?\("),
    "go": re.compile(r"\bt\.(?:Error|Errorf|Fatal|Fatalf|Fail)\b|\bassert\.\w+\(|\brequire\.\w+\("),
    "java": re.compile(r"\bassert\w*\(|\bverify\("),
    "kotlin": re.compile(r"\bassert\w*\(|\bshould\w*\b"),
    "csharp": re.compile(r"\bAssert\.\w+\(|\.Should\(\)"),
    "ruby": re.compile(r"\bexpect\(|\bassert\w*\b"),
    "rust": re.compile(r"\bassert(?:_eq|_ne)?!\("),
    "php": re.compile(r"\$this->assert\w+\(|\bassert\w*\("),
    "shell": re.compile(r"\b(?:assert\w*|fail|die)\b|\|\|\s*(?:exit\s+1|return\s+1)|\bexit\s+1\b"),
}
TESTFN_RE = {
    "python": re.compile(r"^\s*(?:async\s+)?def\s+(test\w*)", re.M),
    "javascript": re.compile(r"\b(?:it|test)\(\s*['\"`]([^'\"`]+)"),
    "typescript": re.compile(r"\b(?:it|test)\(\s*['\"`]([^'\"`]+)"),
    "go": re.compile(r"^func\s+(Test\w+)\(", re.M),
    "java": re.compile(r"@Test[\s\S]{0,200}?\bvoid\s+(\w+)\("),
    "kotlin": re.compile(r"@Test[\s\S]{0,200}?\bfun\s+`?([^`(]+)`?\("),
    "csharp": re.compile(r"\[(?:Fact|Test|Theory|TestMethod)\][\s\S]{0,200}?\b(?:void|Task)\s+(\w+)\("),
    "ruby": re.compile(r"^\s*(?:it|test)\s+['\"]([^'\"]+)", re.M),
    "rust": re.compile(r"#\[test\]\s*(?:#\[[^\]]+\]\s*)*fn\s+(\w+)"),
    "php": re.compile(r"function\s+(test\w+)\("),
    "shell": re.compile(r"^\s*(?:function\s+)?(test_\w+)\s*\(\)", re.M),
}


def test_units(ctx):
    units = []
    for f in ctx.code_files():
        if not paths.is_test_file(f):
            continue
        lang = paths.lang_of(f)
        text = ctx.text(f)
        rx = ASSERT_RE.get(lang)
        n_assert = len(rx.findall(text)) if rx else 0
        fns = TESTFN_RE.get(lang)
        names = [m.group(1).strip() for m in fns.finditer(text)] if fns else []
        units.append({"file": f, "lang": lang, "asserts": n_assert, "tests": len(names),
                      "test_names": names[:200], "component": paths.component_of(f)})
    return units


# Padrões de BUSCA (regex sobre o código do alvo) — nada aqui é executado.
NEGATIVE = {
    "python": [
        ("eval", r"(?<![\w.])eval\(", "eval()"),
        ("exec", r"(?<![\w.])exec\(", "exec()"),
        ("shell-true", r"shell\s*=\s*True", "subprocess com shell=True"),
        ("pickle-loads", r"pickle\.loads?\(", "pickle.load(s)"),
        ("star-import", r"^\s*from\s+\S+\s+import\s+\*", "import *"),
        ("bare-except", r"^\s*except\s*:", "except: sem tipo"),
        ("os-system", r"\bos\.system\(", "os.system()"),
        ("yaml-load", r"\byaml\.load\((?![^)]*Loader)", "yaml.load sem Loader"),
    ],
    "javascript": [
        ("eval", r"(?<![\w.])eval\(", "eval()"),
        ("var", r"^\s*var\s+\w", "declaração var"),
        ("innerhtml", r"\.innerHTML\s*=", "atribuição a innerHTML"),
        ("loose-eq", r"[^=!]==[^=]", "igualdade frouxa =="),
    ],
    "typescript": [
        ("any", r":\s*any\b|<any>|as\s+any\b", "tipo any"),
        ("ts-ignore", r"@ts-ignore", "@ts-ignore"),
        ("eval", r"(?<![\w.])eval\(", "eval()"),
        ("non-null-bang", r"\w!\.", "non-null assertion (!.)"),
    ],
    "shell": [
        ("eval", r"^\s*eval\s|[;&|]\s*eval\s", "eval"),
        ("backticks", r"`[^`\n]+`", "substituição com crases"),
        ("curl-pipe-sh", r"curl[^|\n]*\|\s*(?:ba)?sh", "curl | sh"),
        ("mapfile", r"\b(?:mapfile|readarray)\b", "mapfile/readarray (bash 4+)"),
        ("assoc-array", r"declare\s+-A\b", "declare -A (bash 4+)"),
    ],
    "go": [
        ("panic", r"\bpanic\(", "panic()"),
        ("unsafe", r"\"unsafe\"", "pacote unsafe"),
    ],
    "rust": [
        ("unsafe", r"\bunsafe\s*\{", "bloco unsafe"),
        ("unwrap", r"\.unwrap\(\)", ".unwrap()"),
    ],
    "java": [("printstacktrace", r"\.printStackTrace\(\)", "printStackTrace()"),
             ("system-out", r"System\.out\.print", "System.out.print")],
    "csharp": [("async-void", r"\basync\s+void\b", "async void"),
               ("result-block", r"\.Result\b|\.Wait\(\)", ".Result/.Wait() bloqueante")],
    "ruby": [("eval", r"(?<![\w.])eval\(?\s", "eval")],
    "php": [("eval", r"(?<![\w>])eval\(", "eval()")],
}
MIN_FILES_FOR_INVARIANT = 3


def negative_invariants(ctx):
    out = []
    for lang in sorted(NEGATIVE):
        fs = [f for f in ctx.code_files([lang])]
        prod = [f for f in fs if not paths.is_test_file(f)]
        if len(prod) < MIN_FILES_FOR_INVARIANT:
            continue
        for key, pat, desc in NEGATIVE[lang]:
            rx = re.compile(pat, re.M)
            hits = []
            for f in prod:
                text = ctx.text(f)
                tl = None
                for m in rx.finditer(text):
                    ln = text.count("\n", 0, m.start()) + 1
                    tl = tl if tl is not None else text.splitlines()
                    line_txt = tl[ln - 1] if ln - 1 < len(tl) else ""
                    if line_txt.lstrip().startswith(("#", "//", "*")):
                        continue
                    hits.append((f, ln))
            out.append({"lang": lang, "key": key, "pattern": pat, "desc": desc,
                        "files": len(prod), "hits": len(hits), "examples": sorted(hits)[:10],
                        "scope_files": prod})
    return out


def run(ctx):
    fb = ctx.fb
    facts = []
    cfg = config_rules(ctx)
    seen = set()
    for rid, claim, rel, line, sc in cfg:
        key = (rid, rel, line)
        if key in seen:
            continue
        seen.add(key)
        facts.append(fb.fact("rules.cfg.%s" % slug(rid), LAYER, claim, [ev_file(rel, line)],
                             scope=sc, data={"kind": "config", "tool": rid}))
    units = test_units(ctx)
    by_comp = {}
    for u in units:
        by_comp.setdefault(u["component"], []).append(u)
    for comp in sorted(by_comp):
        us = by_comp[comp]
        na = sum(u["asserts"] for u in us)
        nt = sum(u["tests"] for u in us)
        langs = sorted(set(u["lang"] for u in us))
        top = sorted(us, key=lambda u: (-u["asserts"], u["file"]))[:5]
        facts.append(fb.fact("rules.tests.%s" % slug(comp), LAYER,
                             "%s: %d arquivos de teste (%s), %d casos, %d asserts; maiores: %s" % (
                                 comp, len(us), ", ".join(langs), nt, na,
                                 ", ".join("%s (%d)" % (u["file"], u["asserts"]) for u in top[:3])),
                             [ev_file(u["file"]) for u in top],
                             confidence="high", scope=[comp + "/**" if comp != "." else "*"],
                             data={"kind": "tests", "component": comp, "files": len(us), "cases": nt,
                                   "asserts": na}))
    zero = [u for u in units if u["asserts"] == 0]
    if zero:
        facts.append(fb.fact("rules.tests.no-asserts", LAYER,
                             "%d arquivos de teste sem assert detectável: %s" % (
                                 len(zero), ", ".join(u["file"] for u in zero[:5])),
                             [ev_file(u["file"]) for u in zero[:5]], confidence="medium",
                             scope=[u["file"] for u in zero]))
    if not units:
        facts.append(fb.fact("rules.tests.none", LAYER, "Nenhum arquivo de teste encontrado",
                             [ev_cmd("scan:L4 busca de arquivos de teste", 1, b"")], scope=["**"]))
    negs = negative_invariants(ctx)
    for n in negs:
        scope = sorted(set((paths.component_of(f) + "/**") if "/" in f else f for f in n["scope_files"]))
        listing = "\n".join(n["scope_files"]).encode("utf-8")
        if n["hits"] == 0:
            facts.append(fb.fact("rules.never.%s.%s" % (n["lang"], n["key"]), LAYER,
                                 "Invariante: %s tem 0 ocorrências em %d arquivos %s de produto (não "
                                 "introduzir)" % (n["desc"], n["files"], n["lang"]),
                                 [ev_cmd("scan:grep -E '%s' (%d arquivos %s)" % (n["pattern"], n["files"],
                                                                                n["lang"]),
                                         1, b""),
                                  ev_cmd("scan:lista de arquivos verificados", 0, listing)],
                                 confidence="high" if n["files"] >= 10 else "medium", scope=scope,
                                 data={"kind": "negative", "pattern": n["pattern"], "regex": True,
                                       "count": 0, "lang": n["lang"], "desc": n["desc"],
                                       "files_checked": n["files"]}))
        elif n["hits"] <= 2 and n["files"] >= 10:
            facts.append(fb.fact("rules.rare.%s.%s" % (n["lang"], n["key"]), LAYER,
                                 "%s é raro (%d ocorrências em %d arquivos %s): %s" % (
                                     n["desc"], n["hits"], n["files"], n["lang"],
                                     ", ".join("%s:%d" % e for e in n["examples"])),
                                 [ev_file(f, ln) for f, ln in n["examples"]],
                                 confidence="medium", scope=scope,
                                 data={"kind": "rare", "pattern": n["pattern"], "regex": True,
                                       "count": n["hits"], "lang": n["lang"], "desc": n["desc"]}))
    for n in negs:
        n.pop("scope_files", None)
    if not facts:
        facts.append(fb.fact("rules.none", LAYER, "Nenhuma regra mecânica detectada",
                             [ev_cmd("scan:L4", 1, b"")], scope=["**"]))
    return {"layer": LAYER, "configs": [{"id": r[0], "claim": r[1], "file": r[2], "line": r[3]}
                                        for r in cfg],
            "test_units": units, "negative_checks": negs,
            "facts": facts}
