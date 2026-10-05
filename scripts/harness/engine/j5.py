"""j5 — subconjunto JSON5 do ARCHITECTURE.md §8-decies (stdlib, autocontido: copiado para o alvo).

Aceita: comentários // e /* */, chaves sem aspas (identificador), vírgula final, strings com aspas
duplas. Rejeita: aspas simples, hex, NaN/Infinity, +n, .5 — qualquer coisa fora do subconjunto.
Escrita determinística: chaves ordenadas; comentário de 1 linha no topo.
TODO(unificação): quando scripts/cslib/json5io.py existir, manter os dois com os mesmos testes
(este é copiado para o alvo, onde cslib não existe).
"""
import json
import re

_IDENT = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")


class J5Error(ValueError):
    pass


def _strip(text):
    """Remove comentários e vírgulas finais fora de strings; põe aspas em chaves identificador."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == '"':
                    break
                if text[j] == "\n":
                    raise J5Error("string com quebra de linha na posição %d" % i)
                j += 1
            if j >= n:
                raise J5Error("string não terminada na posição %d" % i)
            out.append(text[i:j + 1])
            i = j + 1
        elif c == "'":
            raise J5Error("aspas simples fora do subconjunto (posição %d)" % i)
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            if j < 0:
                raise J5Error("comentário /* não terminado")
            i = j + 2
        elif c == ",":
            j = i + 1
            while j < n:
                if text[j] in " \t\r\n":
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
                i += 1  # vírgula final
            else:
                out.append(c)
                i += 1
        elif _IDENT.match(text, i) and _prev_sig(out) in ("{", ","):
            m = _IDENT.match(text, i)
            word = m.group(0)
            j = m.end()
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j < n and text[j] == ":":
                out.append('"%s"' % word)
            else:
                out.append(word)
            i = m.end()
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _prev_sig(out):
    for chunk in reversed(out):
        s = chunk.strip()
        if s:
            return s[-1]
    return ""


def _reject_const(name):
    raise J5Error("constante fora do subconjunto: %s" % name)


def loads(text):
    if isinstance(text, bytes):
        text = text.decode("utf-8")
    if text.startswith("﻿"):
        text = text[1:]
    try:
        return json.loads(_strip(text), parse_constant=_reject_const)
    except J5Error:
        raise
    except ValueError as e:
        raise J5Error("JSON5 inválido: %s" % e)


def load(path):
    with open(path, "rb") as f:
        return loads(f.read())


def _key(k):
    return k if _IDENT.fullmatch(k) else json.dumps(k, ensure_ascii=False)


def _dump(obj, ind, level):
    pad = " " * (ind * (level + 1))
    end = " " * (ind * level)
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = ["%s: %s" % (_key(k), _dump(obj[k], ind, level + 1)) for k in sorted(obj)]
        if len(obj) <= 3 and all("\n" not in it for it in items):
            return "{" + ", ".join(items) + "}"
        return "{\n" + "".join(pad + it + ",\n" for it in items) + end + "}"
    if isinstance(obj, list):
        if not obj:
            return "[]"
        items = [_dump(x, ind, level + 1) for x in obj]
        if any(isinstance(x, (dict, list)) for x in obj) or sum(len(x) for x in items) > 100:
            return "[\n" + "".join(pad + it + ",\n" for it in items) + end + "]"
        return "[" + ", ".join(items) + "]"
    return json.dumps(obj, ensure_ascii=False, allow_nan=False)


def dumps(obj, header=None):
    body = _dump(obj, 1, 0) + "\n"
    if header:
        return "// " + " ".join(header.split()) + "\n" + body
    return body
