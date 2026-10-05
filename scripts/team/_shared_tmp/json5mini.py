"""Fallback mínimo do subconjunto JSON5 do ARCHITECTURE §8-decies, usado SÓ enquanto
scripts/cslib/json5io.py não existe. Aceita: comentários // e /* */, chaves identificador sem aspas,
vírgula final, strings com aspas duplas. Rejeita aspas simples, hex, NaN/Infinity, '+' inicial.
Escrita: chaves ordenadas, indent 1, comentário de 1 linha no topo (JSON válido = JSON5 válido).
"""
import json
import re

_IDENT = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")


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
        elif c == "'":
            raise ValueError("JSON5 fora do subconjunto: string com aspas simples (pos %d)" % i)
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            if j < 0:
                raise ValueError("comentário /* sem fechamento")
            i = j + 2
        elif c == ",":
            j = i + 1
            while j < n:
                if text[j].isspace():
                    j += 1
                elif text.startswith("//", j):
                    k = text.find("\n", j)
                    j = n if k < 0 else k
                elif text.startswith("/*", j):
                    k = text.find("*/", j + 2)
                    j = n if k < 0 else k + 2
                else:
                    break
            if j < n and text[j] in "]}":
                i += 1
                continue
            out.append(c)
            i += 1
        else:
            m = _IDENT.match(text, i)
            if m and (not out or not re.search(r"[\w$]$", "".join(out[-1:]))):
                word = m.group(0)
                j = m.end()
                while j < n and text[j].isspace():
                    j += 1
                if j < n and text[j] == ":":
                    out.append(json.dumps(word))
                    i = m.end()
                    continue
                if word in ("NaN", "Infinity"):
                    raise ValueError("JSON5 fora do subconjunto: %s" % word)
                out.append(word)
                i = m.end()
                continue
            out.append(c)
            i += 1
    return "".join(out)


def loads(text):
    if isinstance(text, bytes):
        text = text.decode("utf-8")
    return json.loads(_to_json(text))


def dumps(obj, comment=None):
    body = json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False, allow_nan=False)
    head = ("// %s\n" % " ".join(comment.split())) if comment else ""
    return head + body + "\n"
