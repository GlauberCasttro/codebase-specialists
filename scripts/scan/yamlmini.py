"""YAML mínimo (só stdlib) para configs de ferramenta: blocos por indentação.

Suporta: mapas `chave: valor`, listas `- item` (inclusive `- chave: valor` abrindo um mapa), listas e
mapas em fluxo de escalares (`[a, "b"]`, `{a: 1}`), escalares com/sem aspas, comentários `#`, blocos
`|`/`>` (lidos como texto). Âncoras, tags e documentos múltiplos NÃO são suportados → `YamlError`
(o chamador trata como "não lido" — nunca adivinha).

`load(text)` → (objeto, linhas) onde `linhas` mapeia o caminho (tupla de chaves/índices) → nº da linha
(1-based) em que o nó começa.
"""

import re


class YamlError(ValueError):
    pass


_KEY = re.compile(r"""^(?:"((?:[^"\\]|\\.)*)"|'((?:[^']|'')*)'|([^\s#'"\[\]{},][^#]*?))\s*:(?:\s+|$)(.*)$""")


def _strip_comment(s):
    out, q = [], None
    for i, ch in enumerate(s):
        if q:
            out.append(ch)
            if ch == q and (q == "'" or s[i - 1] != "\\"):
                q = None
            continue
        if ch in "\"'" and (not out or out[-1] in " \t[{,:"):
            q = ch
        elif ch == "#" and (not out or out[-1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _split_flow(body):
    items, cur, depth, q = [], [], 0, None
    for i, ch in enumerate(body):
        if q:
            cur.append(ch)
            if ch == q and (q == "'" or body[i - 1] != "\\"):
                q = None
            continue
        if ch in "\"'":
            q = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == "," and depth == 0:
            items.append("".join(cur).strip())
            cur = []
            continue
        cur.append(ch)
    if "".join(cur).strip():
        items.append("".join(cur).strip())
    return items


def scalar(tok):
    t = tok.strip()
    if not t:
        return None
    if t[0] in "&*!" or t.startswith("---"):
        raise YamlError("âncora/tag/documento múltiplo não suportado: %s" % t[:40])
    if t.startswith("[") and t.endswith("]"):
        return [scalar(x) for x in _split_flow(t[1:-1])]
    if t.startswith("{") and t.endswith("}"):
        out = {}
        for it in _split_flow(t[1:-1]):
            m = _KEY.match(it + (" " if not it.endswith(" ") else ""))
            if not m:
                raise YamlError("mapa em fluxo ilegível: %s" % it[:40])
            k = next(g for g in m.groups()[:3] if g is not None)
            out[k] = scalar(m.group(4))
        return out
    if len(t) >= 2 and t[0] == t[-1] == '"':
        return t[1:-1].encode("utf-8").decode("unicode_escape") if "\\" in t else t[1:-1]
    if len(t) >= 2 and t[0] == t[-1] == "'":
        return t[1:-1].replace("''", "'")
    low = t.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~"):
        return None
    if re.match(r"^-?\d+$", t):
        return int(t)
    if re.match(r"^-?\d+\.\d+$", t):
        return float(t)
    return t


def load(text):
    raw = text.splitlines()
    lines = []  # (lineno, indent, content)
    i = 0
    while i < len(raw):
        ln = raw[i]
        s = _strip_comment(ln)
        if s.strip() in ("---",) and not lines:
            i += 1
            continue
        if s.strip():
            if "\t" in ln[:len(ln) - len(ln.lstrip())]:
                raise YamlError("tab na indentação (linha %d)" % (i + 1))
            lines.append([i + 1, len(s) - len(s.lstrip()), s.strip()])
        i += 1
    linemap = {}
    pos = [0]

    def block_scalar(parent_indent):
        body = []
        while pos[0] < len(lines) and lines[pos[0]][1] > parent_indent:
            body.append(lines[pos[0]][2])
            pos[0] += 1
        return "\n".join(body)

    def value_after(rest, indent, path):
        rest = rest.strip()
        if rest in ("|", ">", "|-", ">-", "|+", ">+"):
            return block_scalar(indent)
        if rest:
            return scalar(rest)
        if pos[0] < len(lines) and (lines[pos[0]][1] > indent or
                                    (lines[pos[0]][1] == indent and lines[pos[0]][2].startswith("- "))):
            return node(lines[pos[0]][1], path)
        return None

    def node(indent, path):
        first = lines[pos[0]]
        if first[2] == "-" or first[2].startswith("- "):
            out = []
            while pos[0] < len(lines) and lines[pos[0]][1] == indent and \
                    (lines[pos[0]][2] == "-" or lines[pos[0]][2].startswith("- ")):
                ln_no, _, content = lines[pos[0]]
                sub = path + (len(out),)
                linemap[sub] = ln_no
                rest = content[1:].strip()
                pos[0] += 1
                if not rest:
                    out.append(node(lines[pos[0]][1], sub) if pos[0] < len(lines) and
                               lines[pos[0]][1] > indent else None)
                    continue
                m = _KEY.match(rest) if not rest.startswith(("[", "{", '"', "'")) or \
                    re.match(r"""^("[^"]*"|'[^']*')\s*:""", rest) else None
                if m:
                    # `- chave: valor` abre um mapa cujas outras chaves vêm indentadas
                    inner = indent + (len(content) - len(rest))
                    lines.insert(pos[0], [ln_no, inner, rest])
                    out.append(node(inner, sub))
                else:
                    out.append(scalar(rest))
            return out
        out = {}
        while pos[0] < len(lines) and lines[pos[0]][1] == indent:
            ln_no, _, content = lines[pos[0]]
            if content.startswith("- "):
                break
            m = _KEY.match(content)
            if not m:
                raise YamlError("linha %d ilegível: %s" % (ln_no, content[:60]))
            k = next(g for g in m.groups()[:3] if g is not None)
            if m.group(2) is not None:
                k = k.replace("''", "'")
            pos[0] += 1
            sub = path + (k,)
            linemap[sub] = ln_no
            if k in out:
                raise YamlError("chave duplicada '%s' (linha %d)" % (k, ln_no))
            out[k] = value_after(m.group(4), indent, sub)
        return out

    if not lines:
        return {}, linemap
    obj = node(lines[0][1], ())
    if pos[0] < len(lines):
        raise YamlError("indentação inconsistente na linha %d" % lines[pos[0]][0])
    return obj, linemap


def get(obj, *keys):
    for k in keys:
        if not isinstance(obj, dict) or k not in obj:
            return None
        obj = obj[k]
    return obj
