"""JSON5 — o SUBCONJUNTO exato do ARCHITECTURE.md §8-decies (stdlib; load/loads/dump/dumps).

Leitor aceita, além de JSON estrito:
  - comentários `// ...` (até o fim da linha) e `/* ... */`;
  - chaves de objeto sem aspas quando são identificador válido ([A-Za-z_$][A-Za-z0-9_$]*);
  - vírgula final (uma) em objetos e listas.
Leitor REJEITA (Json5Error com linha:coluna) tudo fora disso: aspas simples, hex, Infinity/NaN,
'+' inicial, '.5'/'5.', string multilinha, chave não-identificador sem aspas, chave duplicada,
vírgula dupla, comentário não fechado, lixo após o valor.

Escritor (determinístico — mesmo objeto → mesmos bytes):
  - comentário de 1 linha no topo (`header`): o que o arquivo é e quem gera;
  - chaves ordenadas; sem aspas quando identificador válido, senão aspas duplas;
  - strings com aspas duplas (escape JSON, UTF-8 sem \\u para não-ASCII);
  - objeto com ≤3 campos e só valores inline → uma linha `{a: 1, b: "x"}`;
    objeto com >3 campos (ou com valor multilinha) → um campo por linha, indentação de 1 espaço;
  - lista que contém objeto ou lista → uma entrada por linha; lista de escalares → uma linha;
  - sem vírgula final na escrita; NaN/Infinity/tipos não-JSON → erro; '\\n' no fim.
"""

import json
import math
import os
import re

IDENT_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
_NUM_RE = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
_IDENT_AT = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")


class Json5Error(ValueError):
    def __init__(self, msg, text=None, pos=None):
        if text is not None and pos is not None:
            line = text.count("\n", 0, pos) + 1
            col = pos - (text.rfind("\n", 0, pos) + 1) + 1
            msg = "%s (linha %d, coluna %d)" % (msg, line, col)
        super().__init__(msg)


# ------------------------------------------------------------------ leitura

class _Parser(object):
    def __init__(self, text):
        self.s = text
        self.i = 0
        self.n = len(text)

    def err(self, msg, pos=None):
        raise Json5Error(msg, self.s, self.i if pos is None else pos)

    def ws(self):
        s, n = self.s, self.n
        while self.i < n:
            c = s[self.i]
            if c in " \t\r\n﻿":
                self.i += 1
            elif s.startswith("//", self.i):
                j = s.find("\n", self.i)
                self.i = n if j < 0 else j + 1
            elif s.startswith("/*", self.i):
                j = s.find("*/", self.i + 2)
                if j < 0:
                    self.err("comentário /* não fechado")
                self.i = j + 2
            else:
                break

    def parse(self):
        self.ws()
        if self.i >= self.n:
            self.err("documento vazio")
        v = self.value()
        self.ws()
        if self.i < self.n:
            self.err("conteúdo após o valor de topo")
        return v

    def value(self):
        if self.i >= self.n:
            self.err("fim inesperado")
        c = self.s[self.i]
        if c == "{":
            return self.obj()
        if c == "[":
            return self.arr()
        if c == '"':
            return self.string()
        if c == "'":
            self.err("aspas simples fora do subconjunto (use aspas duplas)")
        if c == "-" or c.isdigit():
            return self.number()
        for lit, val in (("true", True), ("false", False), ("null", None)):
            if self.s.startswith(lit, self.i):
                end = self.i + len(lit)
                if end < self.n and (self.s[end].isalnum() or self.s[end] in "_$"):
                    break
                self.i = end
                return val
        if c in "+.":
            self.err("número fora do subconjunto ('+' inicial ou '.' sem dígito)")
        self.err("valor inválido (Infinity/NaN/identificador solto não são aceitos)")

    def number(self):
        m = _NUM_RE.match(self.s, self.i)
        if not m:
            self.err("número inválido")
        end = m.end()
        if end < self.n and (self.s[end].isalnum() or self.s[end] in "._$"):
            self.err("número fora do subconjunto (hex, '5.', sufixo)", end)
        self.i = end
        t = m.group(0)
        if "." in t or "e" in t or "E" in t:
            return float(t)
        return int(t)

    def string(self):
        start = self.i
        self.i += 1
        s, n = self.s, self.n
        out = []
        while True:
            if self.i >= n:
                self.err("string não fechada", start)
            c = s[self.i]
            if c == '"':
                self.i += 1
                return "".join(out)
            if c == "\\":
                if self.i + 1 >= n:
                    self.err("escape incompleto")
                e = s[self.i + 1]
                if e == "u":
                    hx = s[self.i + 2:self.i + 6]
                    if not re.match(r"^[0-9A-Fa-f]{4}$", hx):
                        self.err("escape \\u inválido")
                    cp = int(hx, 16)
                    self.i += 6
                    if 0xD800 <= cp <= 0xDBFF and s.startswith("\\u", self.i):
                        lo = s[self.i + 2:self.i + 6]
                        if re.match(r"^[0-9A-Fa-f]{4}$", lo) and 0xDC00 <= int(lo, 16) <= 0xDFFF:
                            cp = 0x10000 + ((cp - 0xD800) << 10) + (int(lo, 16) - 0xDC00)
                            self.i += 6
                    out.append(chr(cp))
                    continue
                m = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r",
                     "t": "\t"}.get(e)
                if m is None:
                    self.err("escape fora do subconjunto: \\%s" % e)
                out.append(m)
                self.i += 2
                continue
            if c < " ":
                self.err("caractere de controle/quebra de linha dentro de string")
            out.append(c)
            self.i += 1

    def key(self):
        if self.s[self.i] == '"':
            return self.string()
        m = _IDENT_AT.match(self.s, self.i)
        if not m:
            self.err("chave inválida (sem aspas só identificador [A-Za-z_$][A-Za-z0-9_$]*)")
        self.i = m.end()
        return m.group(0)

    def obj(self):
        self.i += 1
        out = {}
        self.ws()
        if self.i < self.n and self.s[self.i] == "}":
            self.i += 1
            return out
        while True:
            self.ws()
            if self.i >= self.n:
                self.err("objeto não fechado")
            if self.s[self.i] == "}":
                self.err("vírgula sem membro")
            kpos = self.i
            k = self.key()
            if k in out:
                self.err("chave duplicada: %s" % k, kpos)
            self.ws()
            if self.i >= self.n or self.s[self.i] != ":":
                self.err("esperado ':'")
            self.i += 1
            self.ws()
            out[k] = self.value()
            self.ws()
            if self.i >= self.n:
                self.err("objeto não fechado")
            c = self.s[self.i]
            if c == ",":
                self.i += 1
                self.ws()
                if self.i < self.n and self.s[self.i] == "}":
                    self.i += 1
                    return out
                continue
            if c == "}":
                self.i += 1
                return out
            self.err("esperado ',' ou '}'")

    def arr(self):
        self.i += 1
        out = []
        self.ws()
        if self.i < self.n and self.s[self.i] == "]":
            self.i += 1
            return out
        while True:
            self.ws()
            if self.i >= self.n:
                self.err("lista não fechada")
            if self.s[self.i] in ",]":
                self.err("vírgula sem elemento")
            out.append(self.value())
            self.ws()
            if self.i >= self.n:
                self.err("lista não fechada")
            c = self.s[self.i]
            if c == ",":
                self.i += 1
                self.ws()
                if self.i < self.n and self.s[self.i] == "]":
                    self.i += 1
                    return out
                continue
            if c == "]":
                self.i += 1
                return out
            self.err("esperado ',' ou ']'")


def loads(text):
    if isinstance(text, bytes):
        text = text.decode("utf-8")
    return _Parser(text).parse()


def load(path):
    """Lê um .json5. Erros de sintaxe viram Json5Error com path:linha:coluna."""
    with open(path, "rb") as fh:
        data = fh.read()
    try:
        return loads(data)
    except Json5Error as exc:
        raise Json5Error("%s: %s" % (path, exc))


# ------------------------------------------------------------------ escrita

def _key(k):
    if not isinstance(k, str):
        raise Json5Error("chave não-string: %r" % (k,))
    return k if IDENT_RE.match(k) else json.dumps(k, ensure_ascii=False)


def _scalar(v):
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            raise Json5Error("NaN/Infinity não são permitidos")
        return json.dumps(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    raise Json5Error("tipo não serializável em JSON5: %s" % type(v).__name__)


def _is_container(v):
    return isinstance(v, (dict, list, tuple))


def _inline(v):
    """Representação em uma linha, ou None se o valor precisa de várias linhas."""
    if isinstance(v, dict):
        if len(v) > 3:
            return None
        parts = []
        for k in sorted(v):
            iv = _inline(v[k])
            if iv is None:
                return None
            parts.append("%s: %s" % (_key(k), iv))
        return "{" + ", ".join(parts) + "}"
    if isinstance(v, (list, tuple)):
        if any(_is_container(x) for x in v):
            return None if v else "[]"
        return "[" + ", ".join(_scalar(x) for x in v) + "]"
    return _scalar(v)


def _emit(v, depth, out):
    iv = _inline(v)
    if iv is not None:
        out.append(iv)
        return
    pad = " " * (depth + 1)
    if isinstance(v, dict):
        out.append("{\n")
        keys = sorted(v)
        for idx, k in enumerate(keys):
            out.append(pad + _key(k) + ": ")
            _emit(v[k], depth + 1, out)
            out.append(",\n" if idx < len(keys) - 1 else "\n")
        out.append(" " * depth + "}")
    else:
        out.append("[\n")
        for idx, x in enumerate(v):
            out.append(pad)
            _emit(x, depth + 1, out)
            out.append(",\n" if idx < len(v) - 1 else "\n")
        out.append(" " * depth + "]")


def dumps(obj, header=None):
    """Serializa no formato canônico. header: comentário de 1 linha (sem '//' e sem quebra)."""
    out = []
    if header is not None:
        if "\n" in header or "\r" in header:
            raise Json5Error("header deve ter uma linha")
        out.append("// " + header.strip() + "\n")
    _emit(obj, 0, out)
    out.append("\n")
    return "".join(out)


def dump(obj, path, header, target=None):
    """Grava atomicamente (com guard de .swarm/ quando target é passado)."""
    from . import jsonio
    if not header:
        raise Json5Error("dump exige header (o que o arquivo é e quem gera)")
    jsonio.write_bytes_atomic(path, dumps(obj, header).encode("utf-8"), target=target)


def read(path, required=True, default=None):
    """Como load(), mas ausência com required=True vira CsError acionável."""
    from .errors import CsError
    if not os.path.exists(path):
        if required:
            raise CsError("arquivo obrigatório ausente: %s" % path,
                          "rode a fase que o produz (ex.: `cs.py scan`) antes desta")
        return default
    try:
        return load(path)
    except (Json5Error, UnicodeDecodeError) as exc:
        raise CsError("JSON5 ilegível: %s" % exc,
                      "o arquivo está corrompido ou fora do subconjunto; regenere com a fase que o produz")
