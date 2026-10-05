"""Co-change (mudança conjunta) a partir do histórico git — por arquivo, diretório ou território.

    commits = gitx.log_commits(target, max_commits=2000)
    pairs = cochange(commits, group_of=lambda p: territory_of(p))   # group_of → str | None
    pairs = cochange_dirs(target, depth=1)                           # atalho por diretório

Cada par: {"a", "b", "support", "conf_a_b", "conf_b_a", "commits_a", "commits_b", "examples": [sha]}
- a < b (ordem lexicográfica); support = nº de commits que tocam os dois grupos;
- conf_a_b = support / commits_a (P(b muda | a mudou)); conf_b_a idem;
- commits que tocam > max_files arquivos (reformatações em massa) são ignorados;
- group_of(path) devolvendo None exclui o arquivo; saída ordenada de forma determinística.
"""

from . import gitx


def cochange(commits, group_of, min_support=1, max_files=30, examples=3):
    count = {}
    pair = {}
    ex = {}
    for c in commits:
        files = [f["path"] if isinstance(f, dict) else f for f in c["files"]]
        if not files or len(files) > max_files:
            continue
        groups = sorted(set(g for g in (group_of(p) for p in files) if g is not None))
        for g in groups:
            count[g] = count.get(g, 0) + 1
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                k = (groups[i], groups[j])
                pair[k] = pair.get(k, 0) + 1
                lst = ex.setdefault(k, [])
                if len(lst) < examples:
                    lst.append(c["sha"])
    out = []
    for (a, b), sup in pair.items():
        if sup < min_support:
            continue
        out.append({"a": a, "b": b, "support": sup,
                    "conf_a_b": round(sup / float(count[a]), 4),
                    "conf_b_a": round(sup / float(count[b]), 4),
                    "commits_a": count[a], "commits_b": count[b], "examples": ex[(a, b)]})
    out.sort(key=lambda x: (-x["support"], -max(x["conf_a_b"], x["conf_b_a"]), x["a"], x["b"]))
    return out


def dir_of(path, depth=1):
    parts = path.split("/")
    if len(parts) == 1:
        return "."
    return "/".join(parts[:min(depth, len(parts) - 1)])


def cochange_dirs(target, depth=1, max_commits=2000, min_support=1, max_files=30, include=None):
    """Co-change entre diretórios (prefixo de `depth` componentes). include(path)->bool filtra."""
    commits = gitx.log_commits(target, max_commits)

    def group(p):
        if include is not None and not include(p):
            return None
        return dir_of(p, depth)
    return cochange(commits, group, min_support=min_support, max_files=max_files)


def load_cochange(target):
    """Leitor do co-change por ARQUIVO já calculado pelo scan (facts/history.json5 → `cochange`).

    Ausência de history.json5 é erro explícito (CsError). Cada item: {a, b, support, conf_a_b, conf_b_a}.
    Para agregar por território/diretório use cochange()/cochange_dirs() (lêem o git direto).
    """
    import os
    from . import json5io, paths
    data = json5io.read(os.path.join(paths.facts_dir(target), "history.json5"))
    return list(data.get("cochange") or [])
