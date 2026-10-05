"""JSON5 para o emissor: usa scripts/cslib/json5io.py quando existir; senão um fallback do mesmo subconjunto.

Subconjunto (ARCHITECTURE §8-decies): comentários // e /* */, chaves sem aspas quando identificador,
vírgula final, strings com aspas duplas. Escrita determinística: chaves ordenadas, objeto com >3 campos
indentado com 1 espaço, uma entrada por linha em lista de objetos, comentário de 1 linha no topo.
"""
import json
import re
from pathlib import Path

try:  # implementação canônica (construtor do scan)
    from cslib import json5io as _impl  # type: ignore
except Exception:  # pragma: no cover - depende do pacote irmão
    _impl = None

IDENT = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


def loads(text):
    if _impl is not None and hasattr(_impl, "loads"):
        return _impl.loads(text)
    return json.loads(_to_json(text))


def load(path):
    return loads(Path(path).read_bytes().decode("utf-8"))


def dumps(obj, header):
    """header: 1 linha dizendo o que o arquivo é e quem gera."""
    if _impl is not None and hasattr(_impl, "dumps"):
        try:
            body = _impl.dumps(obj, header=header)
            return body if body.endswith("\n") else body + "\n"
        except TypeError:  # versão sem cabeçalho: prefixamos nós
            body = _impl.dumps(obj)
    else:
        body = _dump(obj, 0)
    return "// %s\n%s\n" % (header, body.rstrip("\n"))


# ------------------------------------------------------------------ fallback

def _key(k):
    return k if IDENT.match(k) else json.dumps(k, ensure_ascii=False)


def _dump(o, ind):
    pad = " " * ind
    if isinstance(o, dict):
        if not o:
            return "{}"
        items = ["%s: %s" % (_key(k), _dump(o[k], ind + 1)) for k in sorted(o)]
        if len(o) <= 3 and all("\n" not in i for i in items):
            return "{%s}" % ", ".join(items)
        return "{\n%s\n%s}" % (",\n".join(pad + " " + i for i in items), pad)
    if isinstance(o, list):
        if not o:
            return "[]"
        if any(isinstance(x, (dict, list)) for x in o):
            return "[\n%s\n%s]" % (",\n".join(pad + " " + _dump(x, ind + 1) for x in o), pad)
        return "[%s]" % ", ".join(_dump(x, ind) for x in o)
    return json.dumps(o, ensure_ascii=False)


def _to_json(text):
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            out.append(text[i:j + 1])
            i = j + 1
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            if j < 0:
                raise ValueError("comentário /* não fechado")
            i = j + 2
        elif c == "'":
            raise ValueError("aspas simples fora do subconjunto JSON5")
        else:
            m = re.match(r"[A-Za-z_$][A-Za-z0-9_$]*", text[i:])
            if m and _next_nonspace(text, i + m.end()) == ":" and _prev_nonspace(out) in ("{", ","):
                out.append('"%s"' % m.group(0))
                i += m.end()
            else:
                out.append(c)
                i += 1
    s = "".join(out)
    return re.sub(r",(\s*[}\]])", r"\1", s)


def _next_nonspace(text, i):
    while i < len(text) and text[i] in " \t\r\n":
        i += 1
    return text[i] if i < len(text) else ""


def _prev_nonspace(out):
    for chunk in reversed(out):
        s = chunk.rstrip()
        if s:
            return s[-1]
    return ""
