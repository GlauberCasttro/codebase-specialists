"""`cs.py skills-guide --check|--write` — a tabela de skills do MODO-DE-USO.md é GERADA do código.

Fonte: `platforms.skills_catalog()` (as tabelas de skills de `scripts/emit/platforms.py`). Destino: o bloco entre
`<!-- skills:begin -->` e `<!-- skills:end -->` do `MODO-DE-USO.md` da própria skill (não depende de alvo).
`--check` sai 0 se o bloco é igual ao gerado; senão sai 1 e nomeia cada skill divergente. `--write` regenera só o
bloco (idempotente; o resto do arquivo fica byte a byte).
"""
import re
import sys
from pathlib import Path

from emit import platforms as P

SKILL_ROOT = Path(__file__).resolve().parents[2]
GUIDE = "MODO-DE-USO.md"
BEGIN = "<!-- skills:begin -->"
END = "<!-- skills:end -->"
HUMAN = "só o humano"
MODEL = "o modelo pode chamar sozinho"
NO_ARG = "—"
HEADER = ("| Skill | Para que serve | Quem roda | Argumento |", "|---|---|---|---|")
NOTE = ("<!-- gerado por `cs.py skills-guide --write` a partir de scripts/emit/platforms.py; "
        "não edite à mão (`cs.py skills-guide --check` reprova divergência) -->")


def _cell(text):
    return " ".join(str(text).split()).replace("|", "\\|")


def _code(text):
    return "`%s`" % _cell(text)


def rows():
    """→ [(nome, linha da tabela)] na ordem do catálogo."""
    out = []
    for s in P.skills_catalog():
        line = "| %s | %s | %s | %s |" % (_code("/" + s["name"]), _cell(s["desc"]), HUMAN if s["human"] else MODEL,
                                          _code(s["hint"]) if s["hint"] else NO_ARG)
        out.append((s["name"], line))
    return out


def render_block():
    """Conteúdo entre os marcadores (com as quebras de linha das pontas)."""
    return "\n" + "\n".join([NOTE] + list(HEADER) + [l for _, l in rows()]) + "\n"


def _split(text):
    """→ (antes, bloco, depois) ou None se não há exatamente um par de marcadores em ordem."""
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        return None
    b, e = text.index(BEGIN), text.index(END)
    if e < b:
        return None
    b += len(BEGIN)
    return text[:b], text[b:e], text[e:]


def _rows_by_name(block):
    out = {}
    for line in block.splitlines():
        if not line.strip().startswith("|"):
            continue
        first = re.split(r"(?<!\\)\|", line.strip())[1:2]
        m = re.search(r"/([a-z0-9][a-z0-9-]*)", first[0]) if first else None
        if m:
            out.setdefault(m.group(1), []).append(line.strip())
    return out


def diff(current, wanted):
    """→ [mensagens] nomeando cada skill divergente entre o bloco atual e o gerado."""
    cur, want = _rows_by_name(current), _rows_by_name(wanted)
    errs = []
    for n in want:
        if n not in cur:
            errs.append("faltando no guia: /%s" % n)
        elif cur[n] != want[n]:
            errs.append("linha de /%s diverge do código:\n    guia:   %s\n    código: %s"
                        % (n, " / ".join(cur[n]), " / ".join(want[n])))
    for n in cur:
        if n not in want:
            errs.append("sobrando no guia (o emit não gera): /%s" % n)
    if not errs and current != wanted:
        errs.append("bloco difere do gerado fora das linhas de skill (cabeçalho/nota)")
    return errs


def check(guide=None, out=sys.stdout):
    path = Path(guide or SKILL_ROOT / GUIDE)
    parts = _split(path.read_text(encoding="utf-8"))
    if parts is None:
        out.write("skills-guide: %s sem exatamente um par %s … %s; rode `cs.py skills-guide --write`\n"
                  % (path, BEGIN, END))
        return 1
    errs = diff(parts[1], render_block())
    if errs:
        out.write("skills-guide: %s diverge do código (rode `cs.py skills-guide --write`):\n" % path)
        for e in errs:
            out.write("  - %s\n" % e)
        return 1
    out.write("skills-guide: ok (%d skills)\n" % len(rows()))
    return 0


def write(guide=None, out=sys.stdout):
    path = Path(guide or SKILL_ROOT / GUIDE)
    text = path.read_text(encoding="utf-8")
    parts = _split(text)
    if parts is None:
        if BEGIN in text or END in text:
            out.write("skills-guide: marcadores %s/%s malformados em %s; corrija à mão\n" % (BEGIN, END, path))
            return 2
        new = text.rstrip("\n") + "\n\n" + BEGIN + render_block() + END + "\n"
    else:
        new = parts[0] + render_block() + parts[2]
    if new != text:
        with open(str(path), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(new)
        out.write("skills-guide: %s regenerado (%d skills)\n" % (path, len(rows())))
    else:
        out.write("skills-guide: %s já está igual ao código\n" % path)
    return 0


def handler(args):
    if args.write:
        return write()
    return check()


def register(subparsers):
    p = subparsers.add_parser("skills-guide", help="confere (--check) ou regenera (--write) a tabela de skills do "
                                                   "MODO-DE-USO.md a partir do código", description=__doc__)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="sai ≠0 nomeando a skill se o guia diverge (padrão)")
    g.add_argument("--write", action="store_true", help="regenera só o bloco entre os marcadores")
    p.set_defaults(func=handler)
    return p
