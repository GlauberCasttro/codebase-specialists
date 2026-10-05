"""Arquivo representativo POR PASTA (§8-nonies): maior centralidade (PageRank L1); empate → mais
referências (importadores + menções do nome do arquivo em outros arquivos); empate → mais LOC; só
então o path (desempate final obrigatório para determinismo). Nunca escolha alfabética primária."""

import posixpath
import re

from cslib import paths

_NAME_RE = re.compile(r"[A-Za-z0-9_][\w.-]*\.[A-Za-z0-9]{1,8}\b")


def mention_counts(ctx):
    """{basename: nº de arquivos (≠ dele) que citam o nome} — calculado uma vez por scan."""
    if getattr(ctx, "_mentions", None) is not None:
        return ctx._mentions
    names = {}
    for f in ctx.files:
        names.setdefault(f.rsplit("/", 1)[-1], []).append(f)
    counts = {}
    for f in ctx.files:
        if ctx.is_binary(f):
            continue
        own = f.rsplit("/", 1)[-1]
        seen = set(m.group(0) for m in _NAME_RE.finditer(ctx.text(f)))
        for n in seen:
            if n in names and n != own:
                counts[n] = counts.get(n, 0) + 1
    ctx._mentions = counts
    return counts


def representatives(ctx, nodes=None):
    """[{dir, files, representative, reason, also, category}] para toda pasta com arquivo analisado."""
    if getattr(ctx, "_representatives", None) is not None:
        return ctx._representatives
    if nodes is None:
        nodes = ctx.layer("L1")["nodes"]
    pr = {n["path"]: n["pagerank"] for n in nodes}
    indeg = {n["path"]: n["in"] for n in nodes}
    mentions = mention_counts(ctx)
    loc = {}
    for f in ctx.files:
        loc[f] = sum(1 for ln in ctx.lines(f) if ln.strip()) if not ctx.is_binary(f) else 0
    by_dir = {}
    desc = {}
    for f in ctx.files:
        d = posixpath.dirname(f) or "."
        by_dir.setdefault(d, []).append(f)
        while d not in (".", ""):  # pastas só com subpastas usam os descendentes
            desc.setdefault(d, []).append(f)
            d = posixpath.dirname(d)
    out = []
    for d in sorted(set(by_dir) | set(desc)):
        direct = d in by_dir
        fs = by_dir.get(d) or desc[d]

        def key(f):
            refs = indeg.get(f, 0) + mentions.get(f.rsplit("/", 1)[-1], 0)
            return (-pr.get(f, 0.0), -refs, -loc[f], f)
        ranked = sorted(fs, key=key)
        best = ranked[0]
        refs = indeg.get(best, 0) + mentions.get(best.rsplit("/", 1)[-1], 0)
        if pr.get(best, 0) > 0 and any(pr.get(f, 0) != pr.get(best, 0) for f in fs if f != best):
            reason = "centralidade (PageRank %.5f)" % pr[best]
        elif refs > 0:
            reason = "referências (%d)" % refs
        elif len(fs) > 1:
            reason = "maior arquivo (%d LOC)" % loc[best]
        else:
            reason = "único arquivo da pasta"
        if not direct:
            reason = "pasta sem arquivos diretos; melhor descendente por " + reason
        cats = set(ctx.category[f] for f in fs)
        out.append({"dir": d, "files": len(by_dir.get(d, [])), "representative": best, "reason": reason,
                    "also": ranked[1:3],
                    "category": paths.CAT_RESERVED if cats == {paths.CAT_RESERVED} else paths.CAT_PRODUCT})
    ctx._representatives = out
    return out
