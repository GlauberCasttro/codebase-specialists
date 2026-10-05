"""Cobertura regra → teste por IMPORT + SÍMBOLO + MENSAGEM (L9).

A versão anterior só procurava a mensagem/constante no texto dos testes e declarava "sem teste que
cubra" quando não achava — falso para `formatPrice` (o teste chama a função e espera TypeError),
`parseSku` (o teste usa a regex /invalid SKU/) e regras em helpers privados chamados por métodos
públicos testados. Agora, para cada regra:

1. âncora = função que contém a regra (construtor → a classe) ou o nome da constante/tabela;
2. fecho de chamadores (≤2 saltos) entre arquivos de produto que IMPORTAM o arquivo do símbolo;
3. blocos de teste (uma função/caso de teste cada) que importam o arquivo de um símbolo do fecho e o
   citam; dentro do bloco, a asserção de exceção (assertRaises/pytest.raises/assert.throws/toThrow/
   errors.Is) e os padrões de mensagem (regex/string) da asserção.

Níveis (do mais forte ao mais fraco; `test` só é preenchido nos três primeiros):
- `message`    o teste confere a mensagem da regra (substring longa ou regex que casa);
- `exception`  o teste chama um símbolo do fecho e espera a MESMA exceção, sem ambiguidade;
- `reference`  o teste cita a constante/tabela pelo nome (importando o arquivo que a define);
- `asserted`   (só regra que não é validação: limite, formato, transição, estado, CHECK) o teste chama um
               símbolo do fecho e CONFERE o resultado — valor esperado/derivado da constante
               (`assertEqual(late_fee(..).cents, 6100)`, `if got := ETA(8, 0); got != time.Hour { t.Fatal }`)
               ou exceção/mensagem que, no fecho, só a validação ligada à regra levanta;
- `exercised`  o teste chama um símbolo do fecho, mas nada mostra mecanicamente que ele isola a regra (ou é
               ambíguo) — o fato diz "não determinado", nunca "não prova";
- `undetermined` a âncora não é chamável por nome (operador `__add__` etc.);
- `none`       nenhum teste alcança a regra por import+símbolo nem cita a mensagem; se nenhum teste
               sequer importa o módulo, a confiança é low (teste por CLI/HTTP é ponto cego).
Na dúvida o nível é o mais fraco: fato errado é pior que fato ausente.
"""

import posixpath
import re

from cslib import paths

STRONG = ("message", "exception", "reference", "asserted")
ORDER = {"message": 0, "exception": 1, "reference": 2, "asserted": 3, "exercised": 4, "undetermined": 5,
         "none": 6}
CONSTRUCTORS = frozenset(["__init__", "__post_init__", "__new__", "constructor", "init", "New"])
KEYWORDS = frozenset("""if for while switch catch return function else do try new typeof await
yield case throw delete void in of super this import export from class def lambda with elif
not and or is assert print raise except finally pass func go defer select range struct map chan
interface var const let type package""".split())
IDENT = re.compile(r"[A-Za-z_$#][\w$]*")

PY_DEF = re.compile(r"^([ \t]*)(?:async[ \t]+)?def[ \t]+(\w+)|^([ \t]*)class[ \t]+(\w+)", re.M)
JS_FUNC = re.compile(r"^[ \t]*(?:export[ \t]+)?(?:default[ \t]+)?(?:async[ \t]+)?function\*?[ \t]+([\w$]+)"
                     r"|^[ \t]*(?:export[ \t]+)?(?:const|let|var)[ \t]+([\w$]+)[ \t]*(?::[^=]+)?=[ \t]*"
                     r"(?:async[ \t]*)?(?:\([^)]*\)|[\w$]+)[ \t]*(?::[^=]+)?=>"
                     r"|^[ \t]*(?:export[ \t]+)?(?:default[ \t]+)?(?:abstract[ \t]+)?class[ \t]+([\w$]+)"
                     r"|^[ \t]+(?:(?:public|private|protected|static|async|readonly|override|get|set)[ \t]+)*"
                     r"(#?[\w$]+)[ \t]*(?:<[^>\n]*>)?\([^)\n]*\)[ \t]*(?::[^{\n]+)?\{", re.M)
GO_FUNC = re.compile(r"^func[ \t]+(?:\([ \t]*\w*[ \t]*\*?(\w+)[^)]*\)[ \t]*)?(\w+)[ \t]*[\[(]", re.M)
TEST_START = {
    "python": re.compile(r"^([ \t]*)(?:async[ \t]+)?def[ \t]+(test\w*)", re.M),
    "javascript": re.compile(r"^([ \t]*)(?:it|test)(?:\.\w+)?\(\s*['\"`]([^'\"`]+)", re.M),
    "typescript": re.compile(r"^([ \t]*)(?:it|test)(?:\.\w+)?\(\s*['\"`]([^'\"`]+)", re.M),
    "go": re.compile(r"^()func[ \t]+(Test\w+)\(", re.M),
}
PY_RAISES = re.compile(r"(?:assertRaises(?:Regex|RegexpMatches)?|pytest\.raises)\(\s*([\w.]+)"
                       r"(?:\s*,\s*[rbuf]*(['\"])(.+?)\2|[^)\n]*?match\s*=\s*[rbuf]*(['\"])(.+?)\4)?")
JS_THROWS = re.compile(r"\b(?:assert\.(?:throws|rejects)|toThrow(?:Error)?|rejects\.toThrow)\(")
GO_ERR = re.compile(r"errors\.(?:Is|As)\(\s*\w+\s*,\s*&?(\w+)\)|\berr\w*\s*[!=]=\s*(Err\w+)\b")
REGEX_LIT = re.compile(r"(?<![\w)\]])/((?:\\.|[^/\n\\])+)/[gimsuy]*")
STR_LIT = re.compile(r"([\"'`])((?:\\.|(?!\1).){3,}?)\1")
BARREL = ("index", "__init__", "mod")
# contextos de asserção (valor e exceção) dentro de um bloco de teste
PY_VAL_ASSERT = re.compile(r"\bself\.assert(?!Raises)\w*\(|\bassert_\w+\(|(?<![\w.])assert\s+(?=\S)")
PY_THROW_WITH = re.compile(r"^([ \t]*)with[ \t]+(?:self\.assertRaises\w*|pytest\.raises)\(")
PY_THROW_CALL = re.compile(r"\b(?:self\.assertRaises\w*|pytest\.raises)\(")
JS_VAL_ASSERT = re.compile(r"\bassert(?:\.(?!throws\b|rejects\b)\w+)?\(|\bexpect\((?![^\n]*\.(?:rejects\.)?toThrow)")
JS_THROW_ASSERT = re.compile(r"\bassert\.(?:throws|rejects)\(|\bexpect\((?=[^\n]*\.(?:rejects\.)?toThrow)")
GO_IF = re.compile(r"^[ \t]*(?:\}[ \t]*else[ \t]+)?if[ \t]+(.*)\{[ \t]*$")
GO_FAIL = re.compile(r"\bt\.(?:Fatal|Fatalf|Error|Errorf|Fail|FailNow)\b")
GO_TESTIFY = re.compile(r"\b(?:assert|require)\.\w+\(")
ASSIGN = re.compile(r"^[ \t]*(?:(?:const|let|var)[ \t]+)?([\w$]+(?:[ \t]*,[ \t]*[\w$]+)*)[ \t]*(?::=|=(?!=))[ \t]*(.+)$")


def _line(text, pos):
    return text.count("\n", 0, pos) + 1


def _brace_end(lines, start):
    """Última linha (1-based) do bloco que abre com { na linha `start` (contagem simples)."""
    depth = 0
    opened = False
    for i in range(start - 1, len(lines)):
        ln = re.sub(r"([\"'`])(?:\\.|(?!\1).)*\1", "", lines[i])
        ln = re.sub(r"//.*$", "", ln)
        for ch in ln:
            if ch == "{":
                depth += 1
                opened = True
            elif ch == "}":
                depth -= 1
        if opened and depth <= 0:
            return i + 1
        if not opened and i > start + 2:
            return start
    return len(lines)


def _indent_end(lines, start, indent):
    end = start
    for i in range(start, len(lines)):
        ln = lines[i]
        if not ln.strip():
            continue
        if len(ln) - len(ln.lstrip()) <= indent and not ln.lstrip().startswith((")", "]", "}")):
            break
        end = i + 1
    return end


def symbols(text, lang):
    """[{name, kind, start, end, cls}] — funções/métodos/classes com faixa de linhas."""
    lines = text.splitlines()
    out = []
    if lang == "python":
        for m in PY_DEF.finditer(text):
            ln = _line(text, m.start())
            if m.group(2):
                ind = len(m.group(1).expandtabs())
                out.append({"name": m.group(2), "kind": "func", "start": ln,
                            "end": _indent_end(lines, ln, ind), "indent": ind})
            else:
                ind = len(m.group(3).expandtabs())
                out.append({"name": m.group(4), "kind": "class", "start": ln,
                            "end": _indent_end(lines, ln, ind), "indent": ind})
    elif lang in ("javascript", "typescript"):
        for m in JS_FUNC.finditer(text):
            name = m.group(1) or m.group(2) or m.group(3) or m.group(4)
            if not name or name in KEYWORDS:
                continue
            ln = _line(text, m.start())
            out.append({"name": name, "kind": "class" if m.group(3) else "func", "start": ln,
                        "end": _brace_end(lines, ln)})
    elif lang == "go":
        for m in GO_FUNC.finditer(text):
            ln = _line(text, m.start())
            out.append({"name": m.group(2), "kind": "func", "start": ln, "end": _brace_end(lines, ln),
                        "recv": m.group(1)})
    for s in out:
        if s["kind"] == "func":
            owner = [c for c in out if c["kind"] == "class" and c["start"] < s["start"] <= c["end"]]
            s["cls"] = owner[-1]["name"] if owner else s.get("recv")
    return out


def enclosing(syms, line):
    best = None
    for s in syms:
        if s["kind"] == "func" and s["start"] <= line <= s["end"]:
            if best is None or s["start"] >= best["start"]:
                best = s
    return best


def enclosing_class(syms, line):
    best = None
    for s in syms:
        if s["kind"] == "class" and s["start"] <= line <= s["end"]:
            if best is None or s["start"] >= best["start"]:
                best = s
    return best


def _call_args(text, open_pos):
    """Argumentos (top-level) da chamada cujo '(' está em open_pos."""
    depth, args, cur = 0, [], []
    i = open_pos
    while i < len(text) and i < open_pos + 600:
        ch = text[i]
        if ch in "([{":
            depth += 1
            if depth > 1:
                cur.append(ch)
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                args.append("".join(cur))
                return args
            cur.append(ch)
        elif ch == "," and depth == 1:
            args.append("".join(cur))
            cur = []
        elif ch in "\"'`":
            j = i + 1
            while j < len(text) and text[j] != ch:
                j += 2 if text[j] == "\\" else 1
            cur.append(text[i:j + 1])
            i = j
        else:
            cur.append(ch)
        i += 1
    args.append("".join(cur))
    return args


def code_only(text, lang):
    """Texto sem literais de string e sem comentários (identificador citado em mensagem não conta)."""
    t = re.sub(r"(?s)([\"'`])(?:\\.|(?!\1).)*?\1", '""', text)
    if lang == "python":
        t = re.sub(r"#[^\n]*", "", t)
    else:
        t = re.sub(r"//[^\n]*", "", t)
        t = re.sub(r"(?s)/\*.*?\*/", "", t)
    return t


def _words(text):
    from cslib.tokenize import split_identifier
    out = set()
    for w in re.findall(r"[A-Za-z][A-Za-z0-9_]*", text or ""):
        out.update(p.lower() for p in split_identifier(w) if len(p) >= 3)
    return out - NAME_STOP


NAME_STOP = frozenset("test tests the and with when should must cannot can not for are from that this "
                      "into only invalid error".split())


def test_blocks(ctx, rel):
    lang = paths.lang_of(rel)
    rx = TEST_START.get(lang)
    text = ctx.text(rel)
    if not rx or not text:
        return []
    lines = text.splitlines()
    starts = [(m.start(), _line(text, m.start()), len(m.group(1).expandtabs()), m.group(2))
              for m in rx.finditer(text)]
    out = []
    for k, (pos, ln, ind, name) in enumerate(starts):
        if lang == "python":
            end = _indent_end(lines, ln, ind)
        elif lang == "go":
            end = _brace_end(lines, ln)
        else:
            end = (starts[k + 1][1] - 1) if k + 1 < len(starts) else len(lines)
        body = "\n".join(lines[ln - 1:end])
        out.append(_analyze_block(rel, lang, name, ln, end, body))
    return out


def _analyze_block(rel, lang, name, start, end, body):
    excs, pats, assert_lines = set(), [], []
    if lang == "python":
        for m in PY_RAISES.finditer(body):
            excs.add(m.group(1).split(".")[-1])
            for g in (m.group(3), m.group(5)):
                if g:
                    pats.append(("re", g))
            assert_lines.append(start + body.count("\n", 0, m.start()))
    elif lang in ("javascript", "typescript"):
        for m in JS_THROWS.finditer(body):
            args = _call_args(body, m.end() - 1)
            rest = args if m.group(0).startswith(("toThrow", "rejects.toThrow")) else args[1:]
            for a in rest:
                a = a.strip()
                excs.update(re.findall(r"\b([A-Z]\w*(?:Error|Exception))\b", a))
                for rm in REGEX_LIT.finditer(a):
                    pats.append(("re", rm.group(1)))
                for sm in STR_LIT.finditer(a):
                    pats.append(("str", sm.group(2)))
                if re.match(r"^[A-Z]\w*$", a):
                    excs.add(a)
            assert_lines.append(start + body.count("\n", 0, m.start()))
    elif lang == "go":
        for m in GO_ERR.finditer(body):
            excs.add(m.group(1) or m.group(2))
            assert_lines.append(start + body.count("\n", 0, m.start()))
    idents = set(IDENT.findall(code_only(body, lang)))
    val_ids, thr_ids = _assert_contexts(body, lang)
    return {"file": rel, "name": name, "start": start, "end": end, "body": body, "excs": excs,
            "patterns": pats, "assert_lines": assert_lines, "idents": idents,
            "val_ids": val_ids, "thr_ids": thr_ids}


def _ids(text, lang):
    return set(IDENT.findall(code_only(text, lang)))


def _assert_contexts(body, lang):
    """(val_ids, thr_ids): identificadores cujo RESULTADO o teste confere (valor) e os chamados dentro de
    uma expectativa de exceção. Variável atribuída de uma chamada e depois conferida conta para a chamada
    (`got, err := PickCourier(..)` + `if got.ID != "c2" { t.Fatal }`)."""
    lines = body.splitlines()
    val, thr = set(), set()
    assigns = {}
    for ln in lines:
        m = ASSIGN.match(ln)
        if m and not ln.lstrip().startswith(("if ", "for ", "return ", "assert")):
            for v in re.split(r"[ \t]*,[ \t]*", m.group(1)):
                assigns.setdefault(v, set()).update(_ids(m.group(2), lang))
    if lang == "python":
        for m in PY_VAL_ASSERT.finditer(body):
            if m.group(0).rstrip().endswith("("):
                val.update(_ids(" ".join(_call_args(body, m.end() - 1)), lang))
            else:
                val.update(_ids(body[m.end():].split("\n", 1)[0], lang))
        for m in PY_THROW_CALL.finditer(body):
            args = _call_args(body, m.end() - 1)
            thr.update(_ids(" ".join(args[1:]), lang))  # forma chamável: assertRaises(E, f, *args)
        for i, ln in enumerate(lines):
            m = PY_THROW_WITH.match(ln)
            if m:
                ind = len(m.group(1).expandtabs())
                end = _indent_end(lines, i + 1, ind)
                thr.update(_ids("\n".join(lines[i + 1:end]), lang))
    elif lang in ("javascript", "typescript"):
        for rx, out in ((JS_VAL_ASSERT, val), (JS_THROW_ASSERT, thr)):
            for m in rx.finditer(body):
                out.update(_ids(" ".join(_call_args(body, m.end() - 1)), lang))
    elif lang == "go":
        for i, ln in enumerate(lines):
            m = GO_IF.match(ln)
            if m:
                end = _brace_end(lines, i + 1)
                if GO_FAIL.search("\n".join(lines[i + 1:end])):
                    val.update(_ids(m.group(1), lang))
        for m in GO_TESTIFY.finditer(body):
            val.update(_ids(" ".join(_call_args(body, m.end() - 1)), lang))
    for _ in range(2):  # variável conferida → chamada que a produziu (2 níveis)
        for v, src in assigns.items():
            if v in val:
                val |= src
    return val, thr


class CoverageIndex(object):
    def __init__(self, ctx, test_files, extra_names=()):
        self.ctx = ctx
        self.extra_names = set(extra_names)
        self.exc_sites = {}  # exceção → nº de pontos do repo que a levantam (preenchido pelo L9)
        self.validations = []  # [(arquivo, função-âncora, exceção, mensagem)] (preenchido pelo L9)
        g = ctx.layer("L1")
        self.out_edges = {}
        for e in g["edges"]:
            self.out_edges.setdefault(e[0], set()).add(e[1])
        self.syms = {}
        self.defs = {}  # nome → {arquivo}
        prod = [f for f in ctx.files if paths.is_code(f) and not paths.is_test_file(f)]
        for f in prod:
            lang = paths.lang_of(f)
            ss = symbols(ctx.text(f), lang)
            self.syms[f] = ss
            for s in ss:
                self.defs.setdefault(s["name"], set()).add(f)
        self.prod = prod
        self._users = None
        self.blocks = []
        for t in sorted(test_files):
            self.blocks.extend(test_blocks(ctx, t))

    # ---- imports
    def imports(self, src, dst):
        if src == dst:
            return True
        if paths.lang_of(src) == "go" and paths.lang_of(dst) == "go" and \
                posixpath.dirname(src) == posixpath.dirname(dst):
            return True  # mesmo pacote Go
        outs = self.out_edges.get(src, ())
        if dst in outs:
            return True
        for b in outs:
            stem = posixpath.splitext(posixpath.basename(b))[0]
            if stem in BARREL and dst in self.out_edges.get(b, ()):
                return True
        return False

    # ---- usos de nomes definidos no repo (para o fecho de chamadores)
    def users(self, name):
        if self._users is None:
            self._users = {}
            names = set(self.defs) | self.extra_names
            for f in self.prod:
                text = self.ctx.text(f)
                ss = self.syms.get(f, [])
                for i, ln in enumerate(text.splitlines(), 1):
                    for w in set(IDENT.findall(ln)) & names:
                        # usuário = função que contém o uso (inclusive default de parâmetro na linha
                        # do def); fora de função, a classe (campo/atributo de classe)
                        enc = enclosing(ss, i) or enclosing_class(ss, i)
                        if enc is not None and enc["name"] != w:
                            self._users.setdefault(w, set()).add((f, enc["name"]))
        return self._users.get(name, set())

    def closure(self, seeds, max_depth=2, cap=25):
        """{(arquivo, símbolo): profundidade} — seeds e quem os chama (≤ max_depth saltos, com import)."""
        out = {s: 0 for s in seeds}
        frontier = list(seeds)
        for depth in range(1, max_depth + 1):
            nxt = []
            for f, name in frontier:
                for uf, uname in sorted(self.users(name)):
                    key = (uf, uname)
                    if key in out or not self.imports(uf, f):
                        continue
                    out[key] = depth
                    nxt.append(key)
                    if len(out) >= cap:
                        return out
            frontier = nxt
        return out

    # ---- âncora
    def anchor(self, rel, line):
        """(seeds, undetermined) para uma regra dentro de função."""
        enc = enclosing(self.syms.get(rel, []), line)
        if enc is None:
            return [], False
        name = enc["name"]
        if name in CONSTRUCTORS and enc.get("cls"):
            return [(rel, enc["cls"])], False
        if name.startswith("__") and name.endswith("__"):
            return [], True
        return [(rel, name)], False

    def users_of_def(self, rel, name):
        """Funções que usam `name` (definido em rel), no próprio arquivo ou em quem importa rel."""
        return sorted(set((f, n) for f, n in self.users(name) if self.imports(f, rel)))

    def _block_refs(self, blk, clos):
        """Símbolos do fecho que o bloco cita e cujo arquivo o teste importa, do mais próximo da regra."""
        hits = []
        for (f, name), depth in sorted(clos.items(), key=lambda kv: (kv[1], kv[0])):
            if name in blk["idents"] and name not in [h[0] for h in hits] and self.imports(blk["file"], f):
                hits.append((name, depth))
        return hits

    def _ref_line(self, blk, names):
        lines = blk["body"].splitlines()
        for i, ln in enumerate(lines):
            if any(re.search(r"(?<![\w$])%s(?![\w$])" % re.escape(n), ln) for n in names):
                return blk["start"] + i
        return blk["start"]

    def set_validations(self, rules):
        for r in rules:
            if r["kind"] != "validation":
                continue
            enc = enclosing(self.syms.get(r["file"], []), r["line"])
            if enc is not None:
                self.validations.append((r["file"], enc["name"], r.get("exc"), r.get("message") or ""))

    def _throw_proves(self, blk, clos):
        """O bloco espera exceção/mensagem que, entre as validações do fecho da regra, só UMA levanta."""
        if not blk["excs"] and not blk["patterns"]:
            return False
        funcs = set(clos)
        hits = 0
        for f, fn, exc, msg in self.validations:
            if (f, fn) not in funcs:
                continue
            ok = bool(exc) and exc in blk["excs"]
            for kind_p, p in blk["patterns"]:
                if ok or not msg or len(p) < 4:
                    continue
                try:
                    ok = re.search(p, msg) is not None if kind_p == "re" else p in msg
                except re.error:
                    ok = p in msg
            hits += bool(ok)
        return hits == 1

    def cover(self, rule):
        """covered_by = {file, line, level, via, match, ...} | {level: none|undetermined}."""
        rel, line = rule["file"], rule["line"]
        kind = rule["kind"]
        msg = rule.get("message") or ""
        exc = rule.get("exc")
        name = rule.get("name")
        ref_names = [n for n in [name] + list(rule.get("members") or []) if n]
        seeds, undetermined = [], False
        if kind == "validation":
            seeds, undetermined = self.anchor(rel, line)
        elif name:
            seeds = self.users_of_def(rel, name)
        clos = self.closure(seeds) if seeds else {}
        if any(n.startswith("__") and n.endswith("__") and n not in CONSTRUCTORS for _, n in clos):
            undetermined = True  # alcançável por operador (+, ==, ...): chamada não aparece por nome
        unique_exc = bool(exc) and self.exc_sites.get(exc, 0) == 1
        needle = re.split(r"%[sdrfi0-9.]|\{|\$\{|\$", msg)[0].strip().strip("\"'`")
        rule_words = _words(" ".join([name or "", msg, rule.get("guard") or ""]))
        best, best_key = None, None
        exc_cands = []  # todos os blocos que casam no nível exception (para desambiguar entre regras)
        for blk in self.blocks:
            level, match, at = None, None, None
            refs = self._block_refs(blk, clos)
            if msg:
                if len(needle) >= 12 and needle in blk["body"]:
                    level, match = "message", needle
                else:
                    for kind_p, p in blk["patterns"]:
                        if len(p) < 4:
                            continue
                        try:
                            ok = re.search(p, msg) is not None if kind_p == "re" else p in msg
                        except re.error:
                            ok = p in msg
                        if ok and (refs or (exc and exc in blk["excs"])):
                            level, match = "message", p
                            break
                if level:
                    at = blk["assert_lines"][0] if blk["assert_lines"] else blk["start"]
            if level is None and kind != "validation" and self.imports(blk["file"], rel):
                cited = [n for n in ref_names if n in blk["idents"]]
                if cited:
                    level, match = "reference", cited[0]
                    at = self._ref_line(blk, cited)
            if level is None and exc and exc in blk["excs"] and (refs or (unique_exc and (
                    self.imports(blk["file"], rel) or any(self.imports(blk["file"], f) for f, _ in clos)))):
                # mesma exceção esperada + (chama o fecho, ou a exceção só é levantada neste ponto do repo)
                level, match = "exception", exc
                at = blk["assert_lines"][0]
            if level is None and refs and kind != "validation":
                # valor esperado/derivado: o teste confere o resultado de um símbolo do fecho
                val = [r_ for r_ in refs if r_[0] in blk["val_ids"]]
                thr = [r_ for r_ in refs if r_[0] in blk["thr_ids"]]
                if val or (thr and self._throw_proves(blk, clos)):
                    hit = (val or thr)[0]
                    level, match = "asserted", hit[0]
                    at = self._ref_line(blk, [hit[0]])
                    refs = [hit] + [r_ for r_ in refs if r_ != hit]
            if level is None and refs:
                level, match = "exercised", refs[0][0]
                at = self._ref_line(blk, [refs[0][0]])
            if level is None:
                continue
            depth = refs[0][1] if refs else 0
            overlap = len(rule_words & _words(blk["name"]))
            key = (ORDER[level], depth, -overlap, blk["file"], blk["start"])
            cand = {"file": blk["file"], "line": at, "level": level, "match": match,
                    "via": refs[0][0] if refs else None, "test_name": blk["name"],
                    "block": [blk["file"], blk["start"]], "_key": key,
                    "ref_line": self._ref_line(blk, [refs[0][0]]) if refs else at}
            if level == "exception":
                exc_cands.append(cand)
            if best_key is None or key < best_key:
                best_key, best = key, cand
        if best is None:
            if undetermined:
                return {"level": "undetermined"}
            importers = sorted(set(b["file"] for b in self.blocks if self.imports(b["file"], rel)))
            # nenhum teste importa o módulo: pode ser testado por CLI/HTTP/subprocess (ponto cego) → low
            return {"level": "none", "module_imported_by": importers[:3]}
        best = dict(best)
        if best["level"] == "exception":
            best["exc_cands"] = sorted(exc_cands, key=lambda c: c["_key"])
        best.pop("_key", None)
        return best


def disambiguate(rules):
    """Um bloco de teste que espera a exceção X e alcança ≥2 regras que levantam X não prova nenhuma
    delas: a regra fica com outro bloco exclusivo (se houver) ou cai para `exercised` (ambíguo)."""
    count = {}
    for r in rules:
        cov = r.get("covered_by") or {}
        for c in cov.get("exc_cands", []):
            k = (tuple(c["block"]), c["match"])
            count[k] = count.get(k, 0) + 1
    for r in rules:
        cov = r.get("covered_by") or {}
        cands = cov.pop("exc_cands", None)
        if cov.get("level") != "exception" or not cands:
            continue
        excl = [c for c in cands if count[(tuple(c["block"]), c["match"])] == 1]
        if excl:
            c = dict(excl[0])
            c.pop("_key", None)
            r["covered_by"] = c
        else:
            n = max(count[(tuple(c["block"]), c["match"])] for c in cands)
            cov["level"] = "exercised"
            cov["ambiguous"] = n
            cov["line"] = cov.get("ref_line", cov["line"])  # aponta a chamada, não a asserção
            if not cov.get("via"):
                cov["level"] = "undetermined"
