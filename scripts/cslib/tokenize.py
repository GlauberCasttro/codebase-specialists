"""Tokenizador que entende identificadores (para BM25, glossário e busca).

- strip_accents("Ação") -> "Acao"
- split_identifier("parseHTTPResponse_v2") -> ["parse", "http", "response", "v2"]
- tokenize("OrderItem.total_price; max-retries") -> ["order", "item", "total", "price", "max", "retries"]
  (com keep_compound=True também emite o identificador inteiro normalizado: "orderitem",
  "total_price", "max-retries" → útil para casar a forma exata).

Regras: Unicode NFKD sem marcas combinantes; fronteiras em _ - . / espaço, minúscula→Maiúscula,
SIGLA→Palavra (HTTPServer → http server), letra↔dígito NÃO quebra (v2, utf8, sha256).
Tokens com < min_len caracteres são descartados (default 2). Saída determinística, em ordem.
"""

import re
import unicodedata

_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[_\-][A-Za-z0-9]+)*|[A-Za-z0-9]+")
_CAMEL_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+[0-9]*|[A-Z]+[0-9]*|[0-9]+[a-z]*")

STOPWORDS = frozenset("""
a an and are as at be by de do da das dos e em for from in is it no na nas nos o of on or os para
por que the to um uma with self this that cls return def var let const new none null true false
""".split())


def strip_accents(text):
    norm = unicodedata.normalize("NFKD", text)
    return "".join(c for c in norm if not unicodedata.combining(c))


def split_identifier(ident):
    """Partes minúsculas de um identificador (snake, camel, Pascal, kebab, dotted)."""
    ident = strip_accents(ident)
    parts = []
    for chunk in re.split(r"[^A-Za-z0-9]+", ident):
        if not chunk:
            continue
        for m in _CAMEL_RE.findall(chunk):
            parts.append(m.lower())
    return parts


def tokenize(text, min_len=2, keep_compound=False, stopwords=STOPWORDS):
    text = strip_accents(text or "")
    out = []
    for m in _WORD_RE.finditer(text):
        word = m.group(0)
        parts = split_identifier(word)
        if keep_compound and len(parts) > 1:
            out.append(word.lower())
        for p in parts:
            if len(p) >= min_len and p not in stopwords:
                out.append(p)
    return out


def canonical_term(ident):
    """Forma canônica de um termo: partes minúsculas unidas por espaço ("OrderItem" → "order item")."""
    return " ".join(split_identifier(ident))
