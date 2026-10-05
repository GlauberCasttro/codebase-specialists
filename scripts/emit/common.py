"""Utilidades do emissor: escrita atômica, marcadores, frontmatter YAML/TOML mínimos.

Python 3.9+ stdlib. Nenhuma dependência de outros pacotes da skill.
"""
import hashlib
import json
import os
import re
import string
import tempfile
from pathlib import Path

BEGIN = "<!-- codebase-specialists:begin -->"
END = "<!-- codebase-specialists:end -->"
GEN_MARK = "<!-- codebase-specialists:generated; não edite: altere .swarm/team.json5 e rode `cs.py emit` -->"
GEN_MARK_TOML = "# codebase-specialists:generated; não edite: altere .swarm/team.json5 e rode `cs.py emit`"
GEN_TOKEN = "codebase-specialists:generated"

DEFAULT_VEREDITO = ("PASS", "FAIL", "NEEDS_SPECIALIST")
ALL_PLATFORMS = ("claude-code", "cursor", "copilot", "codex")
WRITE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")

SKILL_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = SKILL_ROOT / "assets" / "templates"


class EmitError(Exception):
    """Erro de entrada (team.json inválido, raiz ausente). Exit 2."""


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def template(tpl_file_, **values):
    """Carrega assets/templates/<arquivo> e substitui; placeholder ausente = erro."""
    name = tpl_file_
    path = TEMPLATES / name
    if not path.is_file():
        raise EmitError("template ausente: %s" % path)
    text = path.read_text(encoding="utf-8")
    try:
        return string.Template(text).substitute(**values)
    except KeyError as exc:
        raise EmitError("template %s sem valor para %s" % (name, exc))


def atomic_write(path, content):
    """Escreve bytes UTF-8 com LF via arquivo temporário + os.replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8") if isinstance(content, str) else content
    fd, tmp = tempfile.mkstemp(prefix=".cs-emit-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def read_text(path):
    return Path(path).read_bytes().decode("utf-8")


def safe_dest(root, rel):
    """Resolve <root>/<rel> por realpath e garante que fica dentro da raiz.

    Retorna (Path, motivo_de_recusa|None). Destino que é symlink é recusado.
    """
    root_real = Path(os.path.realpath(str(root)))
    dest = root_real / rel
    if dest.is_symlink():
        return dest, "destino é symlink (recusado)"
    real = Path(os.path.realpath(str(dest)))
    try:
        real.relative_to(root_real)
    except ValueError:
        return dest, "destino resolve fora da raiz (%s)" % real
    return dest, None


# ---------------------------------------------------------------- blocos gerenciados

def find_block(text):
    """Retorna (start, end) do bloco incluindo marcadores, None se sem marcadores.

    Levanta ValueError se os marcadores estiverem malformados.
    """
    nb, ne = text.count(BEGIN), text.count(END)
    if nb == 0 and ne == 0:
        return None
    if nb != 1 or ne != 1:
        raise ValueError("marcadores malformados (begin=%d end=%d)" % (nb, ne))
    b = text.index(BEGIN)
    e = text.index(END)
    if e < b:
        raise ValueError("marcador end antes de begin")
    return b, e + len(END)


def render_block(inner):
    return "%s\n%s\n%s" % (BEGIN, inner.strip("\n"), END)


def block_inner(text):
    span = find_block(text)
    if span is None:
        return None
    b, e = span
    return text[b + len(BEGIN):e - len(END)].strip("\n")


def merge_block(existing, inner):
    """Substitui o bloco (ou acrescenta ao fim). Conteúdo fora do bloco intacto."""
    block = render_block(inner)
    if existing is None:
        return block + "\n"
    span = find_block(existing)
    if span is None:
        base = existing
        if base and not base.endswith("\n"):
            base += "\n"
        sep = "\n" if base.strip() else ""
        return base + sep + block + "\n"
    b, e = span
    return existing[:b] + block + existing[e:]


def expand_braces(globs):
    """`src/*.{ts,tsx}` -> [`src/*.ts`, `src/*.tsx`] (formatos que separam padrões por vírgula)."""
    out = []
    for g in globs:
        stack = [g]
        while stack:
            cur = stack.pop(0)
            m = re.search(r"\{([^{}]*)\}", cur)
            if not m:
                if cur not in out:
                    out.append(cur)
                continue
            for alt in m.group(1).split(","):
                stack.append(cur[:m.start()] + alt + cur[m.end():])
    return out


# ---------------------------------------------------------------- YAML mínimo

def yq(value):
    """Escalar YAML em aspas duplas (string JSON é escalar YAML válido)."""
    return json.dumps(one_line(value), ensure_ascii=False)


def one_line(value):
    return re.sub(r"\s+", " ", str(value)).strip()


def frontmatter(pairs):
    """pairs: lista de (chave, valor_já_formatado | list[str]). Ordem preservada."""
    out = ["---"]
    for key, val in pairs:
        if isinstance(val, list):
            out.append("%s:" % key)
            for item in val:
                out.append("  - %s" % yq(item))
        else:
            out.append("%s: %s" % (key, val))
    out.append("---")
    return "\n".join(out)


class FrontmatterError(ValueError):
    pass


def parse_frontmatter(text):
    """Parser do subconjunto YAML que emitimos (e o que humanos costumam escrever).

    Suporta: `k: escalar`, `k: "json"`, `k: 'x'`, `k: [a, b]`/JSON, `k:` + itens `- x`,
    booleanos true/false. Retorna (dict, corpo). Sem frontmatter -> FrontmatterError.
    """
    if not text.startswith("---\n"):
        raise FrontmatterError("arquivo não começa com frontmatter '---'")
    end = text.find("\n---\n", 3)
    if end < 0:
        if text.endswith("\n---"):
            end = len(text) - 4
        else:
            raise FrontmatterError("frontmatter sem '---' de fechamento")
    raw = text[4:end]
    body = text[end + 5:]
    data = {}
    current = None
    for n, line in enumerate(raw.split("\n"), start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m_item = re.match(r"^\s+-\s+(.*)$", line)
        if m_item:
            if current is None or not isinstance(data.get(current), list):
                raise FrontmatterError("linha %d: item de lista sem chave" % n)
            data[current].append(_scalar(m_item.group(1), n))
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s+(.*))?$", line)
        if not m:
            raise FrontmatterError("linha %d não é 'chave: valor': %r" % (n, line))
        key, val = m.group(1), (m.group(2) or "").strip()
        if key in data:
            raise FrontmatterError("linha %d: chave duplicada %r" % (n, key))
        if val == "":
            data[key] = []
            current = key
        else:
            data[key] = _scalar(val, n, allow_list=True)
            current = None
    return data, body


def _scalar(val, n, allow_list=False):
    val = val.strip()
    if val.startswith('"'):
        try:
            return json.loads(val)
        except ValueError:
            raise FrontmatterError("linha %d: string entre aspas inválida" % n)
    if val.startswith("'"):
        if not val.endswith("'") or len(val) < 2:
            raise FrontmatterError("linha %d: aspas simples não fechadas" % n)
        return val[1:-1].replace("''", "'")
    if allow_list and val.startswith("["):
        if not val.endswith("]"):
            raise FrontmatterError("linha %d: lista não fechada" % n)
        inner = val[1:-1].strip()
        if not inner:
            return []
        return [_scalar(x, n) for x in _split_flow(inner)]
    low = val.lower()
    if low in ("true", "false"):
        return low == "true"
    return val


def _split_flow(inner):
    parts, buf, quote = [], "", None
    for ch in inner:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            buf += ch
        elif ch == ",":
            parts.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf.strip())
    return parts


# ---------------------------------------------------------------- TOML mínimo

def toml_str(value):
    return json.dumps(one_line(value), ensure_ascii=False)


def toml_multiline(value):
    text = str(value).replace("\\", "\\\\").replace('"""', '""\\"')
    return '"""\n%s"""' % (text if text.endswith("\n") else text + "\n")


def parse_toml(text):
    """Usa tomllib (3.11+); senão um parser do subconjunto emitido (chave = string)."""
    try:
        import tomllib  # type: ignore
        return tomllib.loads(text)
    except ImportError:
        pass
    data, lines, i = {}, text.split("\n"), 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line.startswith("#"):
            continue
        m = re.match(r'^([A-Za-z0-9_-]+)\s*=\s*(.*)$', line)
        if not m:
            raise ValueError("TOML: linha %d inesperada: %r" % (i, line))
        key, val = m.group(1), m.group(2)
        if val.startswith('"""'):
            buf = val[3:]
            while '"""' not in buf.replace('\\"', ""):
                if i >= len(lines):
                    raise ValueError("TOML: string multilinha não fechada")
                buf += "\n" + lines[i]
                i += 1
            idx = buf.rfind('"""')
            raw = buf[:idx]
            if raw.startswith("\n"):
                raw = raw[1:]
            data[key] = raw.replace('\\"', '"').replace("\\\\", "\\")
        elif val.startswith('"'):
            data[key] = json.loads(val)
        elif val in ("true", "false"):
            data[key] = val == "true"
        else:
            raise ValueError("TOML: valor não suportado em %r" % key)
    return data
