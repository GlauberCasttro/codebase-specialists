"""`cs.py facts check --layers ...` — check de scan.1–scan.4 que prova o EFEITO (iteração 3, auditoria 1.4).

`scan --check` (frente do scan) confere arquivo legível, ≥1 fato válido e ids no index; mas aceitava fatos de
OUTRO commit com só um aviso — o código podia ter mudado desde o scan e os fatos descreviam outro repo.
Aqui: tudo do `scan --check` + frescor: se o commit do scan ≠ HEAD, nenhum arquivo de produto pode ter mudado
entre os dois (mudança só em `.swarm/` ou em arquivo reservado/gerado — .claude/, AGENTS.md… — é aceita).
"""
import io
import os
import sys

from cslib import CsError, gitx, json5io, paths


def _layer_files(layers):
    from scan.cli import OUTPUT_FILES, LAYERS
    names = dict(LAYERS)
    out = []
    for key in layers:
        for name in OUTPUT_FILES.get(key, [names[key]]):
            out.append((key, name))
    return out


def stale_layers(target, layers):
    """→ [(layer, problema)] de frescor."""
    from team._shared_tmp.common import path_class
    head = gitx.head(target)
    fdir = paths.facts_dir(target)
    probs = []
    for key, name in _layer_files(layers):
        data = json5io.read(os.path.join(fdir, name + ".json5"), required=False)
        if data is None:
            continue
        commit = data.get("repo_commit")
        if not commit or not head or commit == head:
            continue
        code, so, _ = gitx.run(target, ["diff", "--name-only", commit, head], check=False)
        if code != 0:
            probs.append((key, "%s: commit do scan %s não existe mais no repo (rebase?)" % (name, commit[:12])))
            continue
        changed = [p for p in so.decode("utf-8", "replace").splitlines()
                   if p and not p.startswith(".swarm/") and path_class(p) == "product"]
        if changed:
            probs.append((key, "%s: fatos do commit %s, mas %d arquivo(s) de produto mudaram até HEAD (ex.: %s)"
                          % (name, commit[:12], len(changed), changed[0])))
    return probs


def check(target, layers):
    from scan.cli import check_outputs
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        check_outputs(target, layers)
    finally:
        sys.stdout = old
    probs = stale_layers(target, layers)
    lines = [ln for ln in buf.getvalue().splitlines() if ln]
    if probs:
        raise CsError("facts check falhou (fatos velhos): " + "; ".join(p for _, p in probs),
                      "re-rode `cs.py scan --layers %s`" % ",".join(sorted(set(k for k, _ in probs))), code=1)
    return lines
