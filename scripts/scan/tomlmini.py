"""TOML: usa tomllib (3.11+) quando existe; senão um parser mínimo (tabelas, arrays de tabelas,
strings básicas/literais/multilinha, números, bools, arrays e inline tables). Erro → {}."""

import re

try:  # pragma: no cover - depende da versão
    import tomllib as _tomllib
except ImportError:  # Python 3.9/3.10
    _tomllib = None


def loads(text):
    if _tomllib is not None:
        try:
            return _tomllib.loads(text)
        except Exception:
            return {}
    try:
        return _Mini(text).parse()
    except Exception:
        return {}


class _Mini(object):
    def __init__(self, text):
        self.s = text
        self.i = 0

    def parse(self):
        root = {}
        cur = root
        while True:
            self._ws_nl()
            if self.i >= len(self.s):
                return root
            if self.s.startswith("[[", self.i):
                self.i += 2
                keys = self._keypath("]]")
                self.i += 2
                parent = self._walk(root, keys[:-1])
                arr = parent.setdefault(keys[-1], [])
                cur = {}
                arr.append(cur)
            elif self.s[self.i] == "[":
                self.i += 1
                keys = self._keypath("]")
                self.i += 1
                cur = self._walk(root, keys)
            else:
                keys = self._keypath("=")
                self.i += 1
                self._ws()
                val = self._value()
                tgt = self._walk(cur, keys[:-1])
                tgt[keys[-1]] = val
            self._line_end()

    def _walk(self, d, keys):
        for k in keys:
            nxt = d.setdefault(k, {})
            if isinstance(nxt, list):
                nxt = nxt[-1]
            d = nxt
        return d

    def _ws(self):
        while self.i < len(self.s) and self.s[self.i] in " \t":
            self.i += 1

    def _ws_nl(self):
        while self.i < len(self.s):
            c = self.s[self.i]
            if c in " \t\r\n":
                self.i += 1
            elif c == "#":
                while self.i < len(self.s) and self.s[self.i] != "\n":
                    self.i += 1
            else:
                break

    def _line_end(self):
        self._ws()
        if self.i < len(self.s) and self.s[self.i] == "#":
            while self.i < len(self.s) and self.s[self.i] != "\n":
                self.i += 1

    def _keypath(self, stop):
        keys = []
        while True:
            self._ws()
            c = self.s[self.i]
            if c in "\"'":
                keys.append(self._string())
            else:
                m = re.compile(r"[A-Za-z0-9_-]+").match(self.s, self.i)
                keys.append(m.group(0))
                self.i = m.end()
            self._ws()
            if self.s.startswith(stop, self.i):
                return keys
            if self.s[self.i] == ".":
                self.i += 1
                continue
            raise ValueError("chave inválida")

    def _string(self):
        s = self.s
        for q in ('"""', "'''"):
            if s.startswith(q, self.i):
                end = s.index(q, self.i + 3)
                val = s[self.i + 3:end]
                self.i = end + 3
                return val.lstrip("\n")
        q = s[self.i]
        self.i += 1
        out = []
        while s[self.i] != q:
            if q == '"' and s[self.i] == "\\":
                nxt = s[self.i + 1]
                out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(nxt, nxt))
                self.i += 2
                continue
            out.append(s[self.i])
            self.i += 1
        self.i += 1
        return "".join(out)

    def _value(self):
        s = self.s
        c = s[self.i]
        if c in "\"'":
            return self._string()
        if c == "[":
            self.i += 1
            arr = []
            while True:
                self._ws_nl()
                if s[self.i] == "]":
                    self.i += 1
                    return arr
                arr.append(self._value())
                self._ws_nl()
                if s[self.i] == ",":
                    self.i += 1
        if c == "{":
            self.i += 1
            d = {}
            while True:
                self._ws()
                if s[self.i] == "}":
                    self.i += 1
                    return d
                keys = self._keypath("=")
                self.i += 1
                self._ws()
                self._walk(d, keys[:-1])[keys[-1]] = self._value()
                self._ws()
                if s[self.i] == ",":
                    self.i += 1
        m = re.compile(r"[^\s,\]}#]+").match(s, self.i)
        tok = m.group(0)
        self.i = m.end()
        if tok == "true":
            return True
        if tok == "false":
            return False
        try:
            return int(tok.replace("_", ""), 0)
        except ValueError:
            try:
                return float(tok.replace("_", ""))
            except ValueError:
                return tok
