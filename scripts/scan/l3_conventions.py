"""L3 convenções: contagem de padrões com proporção (lei ≥90%, maioria ≥60%, misto) + exceções."""

import re

from cslib import paths
from cslib.evidence import ev_cmd, ev_file, slug
from cslib.jsonio import dumps

LAYER = "conventions"
MIN_SAMPLE = 3

STYLES = (
    ("snake_case", re.compile(r"^[a-z0-9]+(_[a-z0-9]+)+$")),
    ("kebab-case", re.compile(r"^[a-z0-9]+(-[a-z0-9]+)+$")),
    ("camelCase", re.compile(r"^[a-z]+[a-z0-9]*([A-Z][a-z0-9]*)+$")),
    ("PascalCase", re.compile(r"^([A-Z][a-z0-9]+)+[A-Z]?$")),
    ("lowercase", re.compile(r"^[a-z][a-z0-9]*$")),
    ("UPPER_CASE", re.compile(r"^[A-Z0-9]+(_[A-Z0-9]+)*$")),
)
# estilos "compatíveis": uma palavra minúscula não contradiz snake/kebab/camel
COMPAT = {"snake_case": {"lowercase"}, "kebab-case": {"lowercase"}, "camelCase": {"lowercase"}}



OPENER = re.compile(r"[:{(\[]\s*(?://.*|#.*)?$|=>\s*$")


def indent_unit(lines):
    """(unidade de indentação, linha que a mostra) — medida pelo DEGRAU entre uma linha que abre bloco
    (termina em `:`, `{`, `(`, `[`, `=>`) e a seguinte, nunca pela largura absoluta (um arquivo de 2
    espaços tem muitas linhas com 4+ espaços de profundidade). Sem degrau observável → (None, None)."""
    steps = {}
    first = {}
    prev = None
    for i, ln in enumerate(lines, 1):
        if not ln.strip():
            continue
        lead = ln[:len(ln) - len(ln.lstrip(" \t"))]
        if prev is not None and OPENER.search(prev[1].rstrip()):
            plead = prev[0]
            if lead.startswith(plead) and len(lead) > len(plead):
                d = lead[len(plead):]
                v = "tabs" if set(d) == {"\t"} else ("%d espaços" % len(d) if set(d) == {" "} and
                                                      len(d) in (2, 3, 4, 8) else None)
                if v:
                    steps[v] = steps.get(v, 0) + 1
                    first.setdefault(v, i)
        prev = (lead, ln)
    if not steps:
        return None, None
    v = sorted(steps.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    return v, first[v]

def style_of(name):
    for st, rx in STYLES:
        if rx.match(name):
            return st
    return "other"


def level(ratio):
    if ratio >= 0.9:
        return "lei"
    if ratio >= 0.6:
        return "maioria"
    return "misto"


def _scope(files):
    comps = sorted(set(paths.component_of(f) for f in files))
    return [c + "/**" if c != "." else "*" for c in comps]


class Counter(object):
    """Observações (arquivo, linha, valor) de uma dimensão de convenção."""

    def __init__(self, key, desc):
        self.key, self.desc, self.obs = key, desc, []

    def add(self, rel, line, value):
        self.obs.append((rel, line, value))

    def summarize(self, compat=None):
        counts = {}
        for _, _, v in self.obs:
            counts[v] = counts.get(v, 0) + 1
        if not counts:
            return None
        dom = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        if compat and dom == "lowercase":
            # palavra única é compatível com o estilo multi-palavra: a convenção real é esse estilo
            # (snake_case com nomes de 1 palavra), nunca "lowercase com exceções snake_case"
            multi = sorted(((counts.get(st, 0), st) for st, ok in compat.items() if dom in ok
                            and counts.get(st, 0)), reverse=True)
            if multi:
                dom = multi[0][1]
        ok_vals = {dom} | (compat or {}).get(dom, set())
        conform = sum(c for v, c in counts.items() if v in ok_vals)
        total = sum(counts.values())
        exceptions = sorted((r, ln, v) for r, ln, v in self.obs if v not in ok_vals)
        return {"key": self.key, "desc": self.desc, "dominant": dom, "counts": counts,
                "conform": conform, "total": total, "ratio": round(conform / float(total), 4),
                "level": level(conform / float(total)),
                "exceptions": [{"file": r, "line": ln, "value": v} for r, ln, v in exceptions[:15]],
                "exceptions_total": len(exceptions),
                "sample": sorted(set(r for r, _, v in self.obs if v in ok_vals))[:5],
                "files": sorted(set(r for r, _, _ in self.obs))}


DEF_RE = {
    "python": [("function", re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(", re.M)),
               ("class", re.compile(r"^\s*class\s+([A-Za-z_]\w*)", re.M))],
    "javascript": [("function", re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(")),
                   ("class", re.compile(r"\bclass\s+([A-Za-z_$][\w$]*)"))],
    "typescript": [("function", re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*[(<]")),
                   ("class", re.compile(r"\bclass\s+([A-Za-z_$][\w$]*)")),
                   ("interface", re.compile(r"\binterface\s+([A-Za-z_$][\w$]*)"))],
    "go": [("function", re.compile(r"^func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*[(\[]", re.M))],
    "shell": [("function", re.compile(r"^\s*(?:function\s+)?([A-Za-z_][\w:-]*)\s*\(\)\s*\{?", re.M))],
    "java": [("class", re.compile(r"\b(?:class|interface|enum|record)\s+([A-Za-z_]\w*)"))],
    "kotlin": [("class", re.compile(r"\b(?:class|interface|object)\s+([A-Za-z_]\w*)")),
               ("function", re.compile(r"\bfun\s+(?:<[^>]+>\s*)?([A-Za-z_]\w*)\s*\("))],
    "csharp": [("class", re.compile(r"\b(?:class|interface|enum|record|struct)\s+([A-Za-z_]\w*)"))],
    "ruby": [("function", re.compile(r"^\s*def\s+(?:self\.)?([A-Za-z_]\w*[?!]?)", re.M)),
             ("class", re.compile(r"^\s*(?:class|module)\s+([A-Z]\w*)", re.M))],
    "rust": [("function", re.compile(r"\bfn\s+([A-Za-z_]\w*)")),
             ("class", re.compile(r"\b(?:struct|enum|trait)\s+([A-Za-z_]\w*)"))],
    "php": [("function", re.compile(r"\bfunction\s+([A-Za-z_]\w*)\s*\(")),
            ("class", re.compile(r"\b(?:class|interface|trait)\s+([A-Za-z_]\w*)"))],
}


def _line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def run(ctx):
    fb = ctx.fb
    code = ctx.code_files()
    counters = []

    by_lang = {}
    for f in code:
        by_lang.setdefault(paths.lang_of(f), []).append(f)

    for lang in sorted(by_lang):
        fs = by_lang[lang]
        c = Counter("naming.files.%s" % lang, "nomes de arquivo %s" % lang)
        for f in fs:
            stem = f.rsplit("/", 1)[-1].split(".")[0]
            if stem in ("__init__", "__main__", "index", "main", "mod", "lib"):
                continue
            stem = re.sub(r"^(test_|_+)", "", stem)
            c.add(f, 1, style_of(stem))
        counters.append(c)
        for kind, rx in DEF_RE.get(lang, []):
            c = Counter("naming.%s.%s" % (kind, lang), "nomes de %s em %s" % (
                {"function": "funções", "class": "classes/tipos", "interface": "interfaces"}[kind], lang))
            for f in fs:
                text = ctx.text(f)
                for m in rx.finditer(text):
                    name = m.group(1).lstrip("_")
                    if not name or (lang == "python" and name.startswith("_")) or \
                            (len(name) <= 2 and kind == "function"):
                        continue
                    if lang == "go" and kind == "function":
                        name = name[0].lower() + name[1:]  # exportado vs não: compara estilo
                    c.add(f, _line_of(text, m.start(1)), style_of(name))
            counters.append(c)
        # indentação dominante por arquivo
        c = Counter("indent.%s" % lang, "indentação em %s" % lang)
        for f in fs:
            v, ln_no = indent_unit(ctx.lines(f))
            if v:
                c.add(f, ln_no, v)
        counters.append(c)

    # testes: padrão de nome e localização
    tests = [f for f in code if paths.is_test_file(f)]
    for lang in sorted(set(paths.lang_of(f) for f in tests)):
        tf = [f for f in tests if paths.lang_of(f) == lang]
        c = Counter("tests.naming.%s" % lang, "nome de arquivo de teste %s" % lang)
        loc_c = Counter("tests.location.%s" % lang, "local dos testes %s" % lang)
        for f in tf:
            base = f.rsplit("/", 1)[-1]
            if re.match(r"^test[_-]", base):
                v = "prefixo test_"
            elif re.search(r"[_-]test\.\w+$", base):
                v = "sufixo _test"
            elif re.search(r"\.(test|spec)\.", base):
                v = "sufixo ." + re.search(r"\.(test|spec)\.", base).group(1)
            elif re.search(r"Tests?\.\w+$", base):
                v = "sufixo Test"
            else:
                v = "sem marcador no nome"
            c.add(f, 1, v)
            parts = f.split("/")[:-1]
            loc_c.add(f, 1, "diretório de testes" if any(p in ("tests", "test", "__tests__", "spec")
                                                         for p in parts) else "junto ao código")
        counters += [c, loc_c]

    # higiene de arquivo (todos de código)
    eol = Counter("files.eol", "fim de linha")
    final_nl = Counter("files.final-newline", "newline no fim do arquivo")
    for f in code:
        data = ctx.read_bytes(f)
        if not data or b"\0" in data[:8192]:
            continue
        eol.add(f, 1, "CRLF" if b"\r\n" in data else "LF")
        final_nl.add(f, 1, "sim" if data.endswith(b"\n") else "não")
    counters += [eol, final_nl]

    # shell: modo estrito
    sh = by_lang.get("shell", [])
    c = Counter("shell.strict-mode", "modo estrito em scripts shell")
    shebang = Counter("shell.shebang", "shebang de scripts shell")
    for f in sh:
        text = ctx.text(f)
        # `set -euo pipefail`: o "o" agrupado recebe o nome logo depois (não só `-o pipefail`)
        m = re.search(r"^\s*set\s+(-[a-zA-Z]+)((?:[ \t]+(?:-o[ \t]+)?[a-z]\w*)*)", text, re.M)
        v = "nenhum"
        if m:
            short, longs = m.group(1), m.group(2)
            if "e" in short and "u" in short and "pipefail" in longs:
                v = "set -euo pipefail"
            elif "e" in short:
                v = "set -e" + ("u" if "u" in short else "")
            else:
                v = "outro"
        c.add(f, _line_of(text, m.start()) if m else 1, v)
        first = text.split("\n", 1)[0]
        shebang.add(f, 1, first.strip() if first.startswith("#!") else "sem shebang")
    counters += [c, shebang]

    # python: type hints e future annotations
    py = by_lang.get("python", [])
    hints = Counter("python.type-hints", "funções Python com anotação de retorno")
    fut = Counter("python.future-annotations", "`from __future__ import annotations`")
    for f in py:
        text = ctx.text(f)
        for m in re.finditer(r"^\s*(?:async\s+)?def\s+\w+\s*\((?:[^()]|\([^()]*\))*\)\s*(->)?", text, re.M):
            hints.add(f, _line_of(text, m.start()), "anotado" if m.group(1) else "sem anotação")
        fut.add(f, 1, "sim" if re.search(r"^from __future__ import annotations", text, re.M) else "não")
    counters += [hints, fut]

    # js/ts: aspas
    js = by_lang.get("javascript", []) + by_lang.get("typescript", [])
    q = Counter("js.quotes", "aspas em imports JS/TS")
    semi = Counter("js.semicolons", "ponto-e-vírgula em imports JS/TS")
    for f in js:
        text = ctx.text(f)
        for m in re.finditer(r"""^import\s.*?(['"])[^'"]+\1(;?)\s*$""", text, re.M):
            q.add(f, _line_of(text, m.start()), "simples" if m.group(1) == "'" else "duplas")
            semi.add(f, _line_of(text, m.start()), "com ;" if m.group(2) else "sem ;")
    counters += [q, semi]

    facts = []
    summaries = []
    for c in counters:
        s = c.summarize(COMPAT if c.key.startswith("naming.") else None)
        if not s or s["total"] < MIN_SAMPLE:
            continue
        summaries.append(s)
        ev = [ev_file(f) for f in s["sample"][:3]]
        ev += [ev_file(e["file"], e["line"]) for e in s["exceptions"][:3]]
        ev.append(ev_cmd("scan:L3 contagem %s" % c.key, 0,
                         dumps(sorted(c.obs)).encode("utf-8")))
        exc = ""
        if s["exceptions_total"]:
            exc = "; exceções: " + ", ".join("%s:%d (%s)" % (e["file"], e["line"], e["value"])
                                             for e in s["exceptions"][:3])
            if s["exceptions_total"] > 3:
                exc += " e mais %d" % (s["exceptions_total"] - 3)
        conf = "high" if s["level"] == "lei" and s["total"] >= 10 else (
            "medium" if s["level"] != "misto" else "low")
        facts.append(fb.fact("conv.%s" % slug(c.key), LAYER,
                             "%s: «%s» é %s (%d/%d = %.0f%%)%s" % (
                                 c.desc[0].upper() + c.desc[1:], s["dominant"], s["level"],
                                 s["conform"], s["total"], 100 * s["ratio"], exc),
                             ev, confidence=conf, scope=_scope(s["files"])))
    if not facts:
        facts.append(fb.fact("conv.none", LAYER,
                             "Amostra insuficiente para convenções (< %d observações por dimensão)"
                             % MIN_SAMPLE, [ctx.ls_evidence], confidence="high", scope=["**"]))
    for s in summaries:
        s.pop("files", None)
    return {"layer": LAYER, "conventions": summaries, "facts": facts}
