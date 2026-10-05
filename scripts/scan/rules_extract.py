"""Extração mecânica de regras de negócio (L9) — sinais no CÓDIGO, nunca em comentário/ADR.

- validation: raise/throw/errors.New/die com guarda `if` imediatamente anterior, aceita quando a
  mensagem tem palavra de regra OU a exceção é classe de erro DEFINIDA no repo (InsufficientStock-
  Error, LedgerImbalance, ErrNoCourier...); mensagem lida dos argumentos (multilinha);
- limit: constante nomeada de limite/parâmetro (ALL_CAPS ou Go `const MaxX = 3`) com o VALOR da
  definição inteira: `15 * 60 * 1000` → 900000 (avaliação aritmética segura); valor que depende de
  outros nomes → value None + confidence low; comentário nunca é valor;
- format: constante de padrão (`SKU_PATTERN = /.../`, `re.compile`, `regexp.MustCompile`);
- transition: tabela de transições (ALLOWED_TRANSITIONS, allowedTransitions, ORDER_TRANSITIONS...);
- state: enum de status (classe Enum, enum TS/Java, tipo Go com consts tipadas, `CREATE TYPE ... AS ENUM`);
- constraint: `CHECK (...)` de SQL.
"""

import ast
import re

from cslib import paths
from cslib.tokenize import split_identifier, strip_accents

RULE_WORDS = re.compile(
    r"\b(must|cannot|can't|can ?not|should|shall|invalid|not allowed|forbidden|required|requires|"
    r"exceed|exceeds|at least|at most|only|never|always|too (?:many|long|short|large|small)|"
    r"limit|denied|reject|mismatch|already|duplicate|conflict|expired|insufficient|unbalanced|"
    r"imbalance|deve|devem|não pode|nao pode|não é permitid|nao e permitid|inválid|invalid|"
    r"obrigatóri|obrigatori|exced|mínimo|minimo|máximo|maximo|apenas|somente|proibid|negad|recus|"
    r"bloque|nunca|sempre|exige|requer|precisa|divergen|já foi|ja foi)", re.I)
LIMIT_PARTS = frozenset("""max min maximum minimum limit limits threshold thresh timeout retry retries ttl
size count days hours minutes seconds ms percent pct rate fee fees quota cap capacity age length len
deadline prazo limite maximo minimo budget window bp bps fine interest floor ceiling grace expiry
expiration period lifetime""".split())
TECH_PARTS = frozenset("timeout retry retries buffer workers port pool cache conn connections threads "
                       "batch page backoff socket".split())
BUSINESS_HINT = re.compile(r"\b(business|regra|rule|cl[áa]usula|contract|contrato|policy|pol[íi]tica|"
                           r"limit|limite|fiscal|legal)\b", re.I)
STATE_NAME = re.compile(r"(Status|State|Stage|Phase|Estado|Situacao|Situação|Fase|Etapa)$")
TRANS_NAME = re.compile(r"(transition|allowed|next_?state|transic|transicao)", re.I)
PATTERN_NAME = re.compile(r"(PATTERN|REGEX|REGEXP|FORMAT)", re.I)  # *_RE é quase sempre parsing técnico

PY_RAISE = re.compile(r"\braise\s+([A-Z][\w.]*)\s*(\()?")
JS_THROW = re.compile(r"\bthrow\s+new\s+([A-Z][\w$.]*)\s*\(")
OTHER_EXC = {
    "java": re.compile(r"\bthrow\s+new\s+([A-Z]\w*)\(\s*(\")(.{4,}?)\""),
    "kotlin": re.compile(r"\bthrow\s+([A-Z]\w*)\(\s*(\")(.{4,}?)\""),
    "csharp": re.compile(r"\bthrow\s+new\s+([A-Z]\w*)\(\s*\$?(\")(.{4,}?)\""),
    "php": re.compile(r"\bthrow\s+new\s+\\?([A-Z][\w\\]*)\(\s*([\"'])(.{4,}?)\2"),
    "ruby": re.compile(r"\braise\s+([A-Z]\w*)(?:,|\.new\()\s*([\"'])(.{4,}?)\2"),
    "rust": re.compile(r"\b(panic!|bail!|anyhow!|Err)\(\s*(\")(.{4,}?)\""),
    "shell": re.compile(r"\b(die|fail|abort|fatal|erro|error)\s+([\"'])(.{4,}?)\2"),
}
GO_NEW_ERR = re.compile(r"\b(errors\.New|fmt\.Errorf)\(\s*\"((?:\\.|[^\"\\]){4,}?)\"")
GO_VAR_ERR = re.compile(r"^\s*(?:var\s+)?(Err\w+)\s*=\s*(?:errors\.New|fmt\.Errorf)\(\s*\"((?:\\.|[^\"\\])*)\"", re.M)
GO_TYPE_ERR = re.compile(r"^type\s+(Err\w+|\w+Error)\s+struct", re.M)
GO_RETURN_ERR = re.compile(r"\breturn\b[^\n]*?\b(Err[A-Z]\w*)\b")
SHELL_ECHO_ERR = re.compile(r"\becho\s+([\"'])(.{4,}?)\1\s*>&2")
PY_ASSERT = re.compile(r"^\s*assert\s+(.+?),\s*[rbuf]*([\"'])(.{4,}?)\2", re.M)
PY_CLASS = re.compile(r"^[ \t]*class\s+(\w+)\s*\(([^)]*)\)", re.M)
JS_CLASS = re.compile(r"\bclass\s+([\w$]+)\s+extends\s+([\w$.]+)")
JVM_CLASS = re.compile(r"\bclass\s+(\w+)\s*(?:\([^)]*\))?\s*(?:extends|:)\s*(\w+)")

CONST_CAPS = re.compile(
    r"^[ \t]*(?:export[ \t]+)?(?:(?:public|private|protected|internal|static|final|const|readonly|val|var|"
    r"let|pub)[ \t]+)*(?:[\w<>\[\]]+[ \t]+)?([A-Z][A-Z0-9_]{2,})[ \t]*(?::[ \t]*[\w.\[\]<>| ]+?[ \t]*)?"
    r"=(?!=)[ \t]*(.+)$", re.M)
GO_CONST = re.compile(r"^[ \t]*const[ \t]+([A-Za-z_]\w*)[ \t]*(?:[\w.]+[ \t]*)?=[ \t]*(.+)$", re.M)
GO_CONST_BLOCK = re.compile(r"^const[ \t]*\((.*?)^\)", re.M | re.S)
GO_BLOCK_ITEM = re.compile(r"^[ \t]+([A-Za-z_]\w*)[ \t]*(?:([\w.]+)[ \t]*)?=[ \t]*(.+)$", re.M)
GO_TYPE = re.compile(r"^type\s+([A-Z]\w*)\s+(string|int|int8|int16|int32|int64|uint\w*|byte)\s*$", re.M)
GO_REGEX = re.compile(r"^[ \t]*(?:var[ \t]+)?(\w+)[ \t]*=[ \t]*regexp\.MustCompile\((.+)\)\s*$", re.M)
TRANS_DECL = re.compile(r"^[ \t]*(?:export[ \t]+)?(?:(?:const|let|var|val|static|final|private|public|"
                        r"readonly)[ \t]+)*([A-Za-z_]\w*)[ \t]*(?::[^=\n]+)?=(?!=)[ \t]*([^\n]*)$", re.M)
SQL_ENUM = re.compile(r"\bCREATE\s+TYPE\s+(?:\w+\.)?(\w+)\s+AS\s+ENUM\s*\(([^)]*)\)", re.I)
SQL_CHECK = re.compile(r"(?:\bCONSTRAINT\s+(\w+)\s+)?\bCHECK\s*\(", re.I)
SQL_TABLE = re.compile(r"\b(?:CREATE|ALTER)\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:\w+\.)?(\w+)", re.I)
ENUM_BASES = re.compile(r"\b(Enum|IntEnum|StrEnum|Flag|IntFlag)\b")
NUM_EXPR = re.compile(r"^[\d_.\s+\-*/()%]+$")


def _line(text, pos):
    return text.count("\n", 0, pos) + 1


def _strip_comment(rhs, lang):
    """Corta comentário de fim de linha fora de string; tira ; e , finais."""
    out, q = [], None
    i = 0
    while i < len(rhs):
        ch = rhs[i]
        if q:
            out.append(ch)
            if ch == "\\" and i + 1 < len(rhs):
                out.append(rhs[i + 1])
                i += 2
                continue
            if ch == q:
                q = None
        else:
            if ch in "\"'`":
                q = ch
            elif ch == "#" and lang in ("python", "ruby", "shell", "toml", "yaml"):
                break
            elif rhs.startswith("//", i) and lang not in ("python",) and not _inside_regex(out):
                break
            elif rhs.startswith("/*", i):
                break
            out.append(ch)
        i += 1
    return "".join(out).strip().rstrip(";,").strip()


def _inside_regex(prev):
    s = "".join(prev).strip()
    return s.startswith("/") and s.count("/") % 2 == 1


def eval_number(expr):
    """Valor de expressão aritmética de literais (`15 * 60 * 1000`, `10_000`, `8.0`) ou None."""
    e = expr.strip()
    if not e or not NUM_EXPR.match(e) or not re.search(r"\d", e):
        return None
    try:
        tree = ast.parse(e.replace("_", ""), mode="eval")
    except (SyntaxError, ValueError):
        return None

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return n.value
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div,
                                                          ast.FloorDiv, ast.Mod)):
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Add):
                return a + b
            if isinstance(n.op, ast.Sub):
                return a - b
            if isinstance(n.op, ast.Mult):
                return a * b
            if b == 0:
                raise ZeroDivisionError
            if isinstance(n.op, ast.Div):
                return a / b
            if isinstance(n.op, ast.FloorDiv):
                return a // b
            return a % b
        raise ValueError("não aritmético")
    try:
        v = ev(tree)
    except (ValueError, ZeroDivisionError, TypeError, RecursionError):
        return None
    lit = e.replace("_", "")
    if re.match(r"^-?\d+(?:\.\d+)?$", lit):
        return lit  # literal puro: preserva a forma (8.0 continua 8.0)
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v)


def _call_args(text, open_pos, limit=800):
    depth, args, cur, i = 0, [], [], open_pos
    while i < len(text) and i < open_pos + limit:
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


def _first_string(args):
    """Mensagem = literal de string que ABRE o primeiro argumento (`"x %s" % y`, `f"..."`, template).
    `body.get("reason", "declined")` não tem mensagem literal → None (nunca a chave de um dict)."""
    if not args:
        return None
    m = re.match(r"\s*[rbuf]*([\"'`])((?:\\.|(?!\1).)*)\1", args[0], re.S)
    return m.group(2) if m else None


def _balanced(text, open_pos, limit=4000):
    depth = 0
    for i in range(open_pos, min(len(text), open_pos + limit)):
        ch = text[i]
        if ch in "{[(":
            depth += 1
        elif ch in "}])":
            depth -= 1
            if depth == 0:
                return text[open_pos:i + 1]
    return text[open_pos:open_pos + limit]


def _comment_near(lines, ln):
    """Texto de comentário na linha anterior / na própria linha (sinal de regra de negócio)."""
    out = []
    for idx in (ln - 2, ln - 1):
        if 0 <= idx < len(lines):
            m = re.search(r"(?:#|//|/\*\*?|\*)\s*(.*)$", lines[idx])
            if m:
                out.append(m.group(1))
    return " ".join(out)


def custom_errors(ctx, code_files):
    """Classes/valores de erro DEFINIDOS no repo (nome → arquivo)."""
    cand = {}
    bases = {}
    for rel in code_files:
        lang = paths.lang_of(rel)
        text = ctx.text(rel)
        if lang == "python":
            for m in PY_CLASS.finditer(text):
                bases[m.group(1)] = (rel, [b.strip().split(".")[-1] for b in m.group(2).split(",")])
        elif lang in ("javascript", "typescript"):
            for m in JS_CLASS.finditer(text):
                bases[m.group(1)] = (rel, [m.group(2).split(".")[-1]])
        elif lang in ("java", "kotlin", "csharp", "php", "scala"):
            for m in JVM_CLASS.finditer(text):
                bases[m.group(1)] = (rel, [m.group(2)])
        elif lang == "go":
            for m in GO_VAR_ERR.finditer(text):
                cand[m.group(1)] = (rel, m.group(2))
            for m in GO_TYPE_ERR.finditer(text):
                cand[m.group(1)] = (rel, None)
    errish = re.compile(r"(Error|Exception|Exceeded|Failure|Fault|Invalid\w*|Violation)$")
    known = set()
    changed = True
    while changed:
        changed = False
        for name, (rel, bs) in bases.items():
            if name in known:
                continue
            if any(b in known or errish.search(b) or b in ("Exception", "Error", "BaseException",
                                                            "RuntimeException", "ValueError")
                   for b in bs):
                known.add(name)
                changed = True
    for n in known:
        cand[n] = (bases[n][0], None)
    return cand


def _guard(lines, ln):
    """(texto da guarda, linha onde ela está) — a linha do `if` pode ser anterior à do raise/throw."""
    for back in range(0, 3):
        idx = ln - 1 - back
        if idx < 0:
            break
        g = re.search(r"\b(if|unless|elif|when|guard|case)\b\s*(.+)", lines[idx])
        if g:
            return g.group(0).strip()[:160], idx + 1
        if back == 0 and re.search(r"(\|\||&&)", lines[idx]):
            return lines[idx].strip()[:160], idx + 1
    return None, None


def _limit_ok(name, comment):
    parts = set(p.lower() for p in split_identifier(name))
    return bool(parts & LIMIT_PARTS) or bool(BUSINESS_HINT.search(comment or ""))


def _limit_class(name, comment):
    parts = set(p.lower() for p in split_identifier(name))
    if BUSINESS_HINT.search(comment or ""):
        return "business"
    return "technical" if parts & TECH_PARTS else "business"


def extract(ctx, rel, errors):
    """Lista de regras (dicts) de um arquivo de produto."""
    lang = paths.lang_of(rel)
    text = ctx.text(rel)
    if not text:
        return []
    lines = text.splitlines()
    out = []

    # ---- validações
    found = []  # (pos, exc, message)
    if lang == "python":
        for m in PY_RAISE.finditer(text):
            msg = _first_string(_call_args(text, m.end() - 1)) if m.group(2) else None
            found.append((m.start(), m.group(1).split(".")[-1], msg))
        for m in PY_ASSERT.finditer(text):
            found.append((m.start(), "assert " + m.group(1)[:80], m.group(3)))
    elif lang in ("javascript", "typescript"):
        for m in JS_THROW.finditer(text):
            found.append((m.start(), m.group(1).split(".")[-1], _first_string(_call_args(text, m.end() - 1))))
    elif lang == "go":
        for m in GO_NEW_ERR.finditer(text):
            ln = _line(text, m.start())
            if re.match(r"^\s*(?:var\s+)?Err\w+\s*=", lines[ln - 1]):
                continue  # definição de erro sentinela, não é a regra (a regra é quem o retorna)
            found.append((m.start(), m.group(1), m.group(2)))
        for m in GO_RETURN_ERR.finditer(text):
            if m.group(1) in errors:
                found.append((m.start(), m.group(1), errors[m.group(1)][1]))
    elif lang in OTHER_EXC:
        for m in OTHER_EXC[lang].finditer(text):
            found.append((m.start(), m.group(1), m.group(3)))
    if lang == "shell":
        for m in SHELL_ECHO_ERR.finditer(text):
            ln = _line(text, m.start())
            nxt = " ".join(lines[ln - 1:ln + 1])
            if re.search(r"\b(exit|return)\s+[1-9]", nxt):
                found.append((m.start(), "exit!=0", m.group(2)))
    seen = set()
    for pos, exc, msg in found:
        ln = _line(text, pos)
        if (ln, exc) in seen:
            continue
        rule_msg = bool(msg) and (RULE_WORDS.search(strip_accents(msg)) or RULE_WORDS.search(msg))
        if not rule_msg and exc not in errors:
            continue
        guard, guard_line = _guard(lines, ln)
        if lang == "go" and exc in errors and not guard:
            continue  # `return ErrX` sem guarda imediata não é uma regra localizável
        seen.add((ln, exc))
        out.append({"kind": "validation", "file": rel, "line": ln, "lang": lang, "raises": exc,
                    "exc": exc if not exc.startswith("assert ") else None,
                    "message": (msg or "")[:240], "guard": guard, "guard_line": guard_line})

    # ---- constantes (limites e padrões)
    consts = []
    if lang == "go":
        for m in GO_CONST.finditer(text):
            consts.append((m.start(), m.group(1), m.group(2)))
        for blk in GO_CONST_BLOCK.finditer(text):
            for m in GO_BLOCK_ITEM.finditer(blk.group(1)):
                consts.append((blk.start(1) + m.start(), m.group(1), m.group(3)))
        for m in GO_REGEX.finditer(text):
            out.append({"kind": "format", "file": rel, "line": _line(text, m.start()), "lang": lang,
                        "name": m.group(1), "value": _strip_comment(m.group(2), lang)[:200]})
    elif paths.is_code(rel) and lang != "shell":
        for m in CONST_CAPS.finditer(text):
            consts.append((m.start(), m.group(1), m.group(2)))
    for pos, name, rhs in consts:
        ln = _line(text, pos)
        expr = _strip_comment(rhs, lang)
        comment = _comment_near(lines, ln)
        if PATTERN_NAME.search(name) and (expr.startswith("/") or "compile(" in expr or "Regex(" in expr
                                          or expr.startswith(("r\"", "r'"))):
            out.append({"kind": "format", "file": rel, "line": ln, "lang": lang, "name": name,
                        "value": expr[:200]})
            continue
        if not _limit_ok(name, comment):
            continue
        if re.match(r"^[\"'`]", expr) or expr.startswith(("{", "[", "new ", "(")) and not NUM_EXPR.match(expr):
            continue  # string/objeto: não é limite numérico
        value = eval_number(expr)
        if value is None and not re.match(r"^[\w.\s+\-*/()]+$", expr):
            continue  # chamada/estrutura: fora do escopo de "limite"
        out.append({"kind": "limit", "file": rel, "line": ln, "lang": lang, "name": name,
                    "value": value, "expr": expr[:120], "class": _limit_class(name, comment)})

    # ---- tabelas de transição
    for m in TRANS_DECL.finditer(text):
        name, rest = m.group(1), m.group(2)
        if not TRANS_NAME.search(name):
            continue
        line_end = m.end()
        start = m.start(2)
        brace = text.find("{", start, line_end + 1)
        bracket = text.find("[", start, line_end + 1)
        if brace < 0 and bracket < 0:
            continue
        if lang == "go" or brace >= 0:
            open_pos = brace if brace >= 0 else bracket
        else:
            open_pos = bracket
        block = _balanced(text, open_pos)
        pairs = []
        for pm in re.finditer(r"[\"']?([\w.]+)[\"']?\s*:\s*(?:[\w.]+\s*\(\s*)?[\[\(\{]([^\]\)\}]*)", block):
            src = pm.group(1).split(".")[-1]
            for dst in re.findall(r"[\"']?([\w.]+)[\"']?", pm.group(2)):
                pairs.append([src, dst.split(".")[-1]])
        if pairs:
            out.append({"kind": "transition", "file": rel, "line": _line(text, m.start()), "lang": lang,
                        "name": name, "transitions": pairs[:80]})

    # ---- estados Go (tipo + consts tipadas)
    if lang == "go":
        for m in GO_TYPE.finditer(text):
            tname = m.group(1)
            if not STATE_NAME.search(tname):
                continue
            members = re.findall(r"^[ \t]*(\w+)[ \t]+%s[ \t]*=" % re.escape(tname), text, re.M)
            if members:
                out.append({"kind": "state", "file": rel, "line": _line(text, m.start()), "lang": lang,
                            "name": tname, "states": members})

    # ---- SQL
    if lang == "sql":
        for m in SQL_ENUM.finditer(text):
            vals = [v.strip().strip("'\"") for v in m.group(2).split(",") if v.strip()]
            out.append({"kind": "state", "file": rel, "line": _line(text, m.start()), "lang": lang,
                        "name": m.group(1), "states": vals})
        for m in SQL_CHECK.finditer(text):
            expr = _balanced(text, m.end() - 1, 600)[1:-1].strip()
            tables = [t for t in SQL_TABLE.finditer(text[:m.start()])]
            table = tables[-1].group(1) if tables else None
            name = m.group(1) or ("%s.check" % table if table else "check")
            out.append({"kind": "constraint", "file": rel, "line": _line(text, m.start()), "lang": lang,
                        "name": name, "table": table, "expr": " ".join(expr.split())[:200]})
    return out


def enum_states(ctx, enums):
    """Estados de enums com nome de status (glossário já achou as declarações)."""
    out = []
    for name, rel, ln, lang in enums:
        if not STATE_NAME.search(name):
            continue
        text = ctx.text(rel)
        start = sum(len(x) + 1 for x in text.splitlines()[:ln - 1])
        members = _enum_members(text, start, lang)
        if members:
            out.append({"kind": "state", "file": rel, "line": ln, "lang": lang, "name": name,
                        "states": members})
    return out


def _enum_members(text, start, lang):
    body = text[start:start + 4000]
    if lang == "python":
        out = []
        for ln in body.splitlines()[1:]:
            if ln.strip() and not ln.startswith((" ", "\t")):
                break
            m = re.match(r"^\s+([A-Z][A-Z0-9_]*)\s*=", ln)
            if m:
                out.append(m.group(1))
        return out
    m = re.search(r"\{(.*?)\}", body, re.S)
    if not m:
        return []
    return re.findall(r"^\s*([A-Z][A-Za-z0-9_]*)\s*(?:[=,(]|$)", m.group(1), re.M)

