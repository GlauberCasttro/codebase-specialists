"""cs.py probes anticola — falha se resposta canônica do banco aparece literal no team.json5/cartões.

Canônicas: path:linha (±3, também `path#Lnn`), comando exato (normalizado), sha (qualquer prefixo ≥7),
valor+local de regra de negócio (path:linha). Varre só TEXTO (chaves de referência a fatos — facts,
facts_used, invariants, id — são ids, não texto; ids com prefixo de sha geram aviso).
Arquivos extras (cartões emitidos) via --cards <arquivo|diretório>.
"""
import os
import re

from team._shared_tmp.cardtext import walk_strings
from team._shared_tmp.common import norm_cmd, read_json, sp_path, write_json
from probes.generate import load_bank

TOL = 3


def _canon(bank):
    out = []
    for p in bank["probes"]:
        a = p["answer"]
        if not a.get("exists", True):
            continue
        locs = []
        if a.get("path") and a.get("line"):
            locs.append((a["path"], int(a["line"])))
        for k in ("enforced_at", "sources"):
            for s in a.get(k) or []:
                locs.append((s["file"], int(s.get("line") or 1)))
        for path, line in locs:
            out.append((p, "path:line", (path, line)))
        if a.get("command"):
            out.append((p, "command", norm_cmd(a["command"])))
        if a.get("sha"):
            out.append((p, "sha", a["sha"].lower()))
    return out


def _texts(team, extra_paths):
    for a in team.get("agents") or []:
        for where, s in walk_strings(a):
            yield a.get("name"), "team.json5:%s.%s" % (a.get("name"), where), s
    for where, s in walk_strings(team.get("core") or {}):
        yield "core", "team.json5:core.%s" % where, s
    for base in extra_paths or []:
        paths = []
        if os.path.isdir(base):
            for dp, dn, fn in os.walk(base):
                dn.sort()
                paths += [os.path.join(dp, f) for f in sorted(fn)]
        elif os.path.isfile(base):
            paths.append(base)
        for p in paths:
            try:
                with open(p, "rb") as fh:
                    yield "file", p, fh.read().decode("utf-8", "replace")
            except OSError:
                continue


def anticola_report(target, team=None, extra_paths=None):
    team = team if team is not None else read_json(sp_path(target, "team.json5"), "team.json5")
    bank = load_bank(target)
    canon = _canon(bank)
    viol, warns = [], []
    for owner, where, text in _texts(team, extra_paths):
        ntext = norm_cmd(text)
        low = text.lower()
        for p, kind, val in canon:
            hit = False
            if kind == "path:line":
                path, line = val
                for m in re.finditer(re.escape(path) + r"(?::|#L)(\d+)", text):
                    if abs(int(m.group(1)) - line) <= TOL:
                        hit = True
                        break
            elif kind == "command":
                hit = bool(val) and re.search(r"(?<![\w-])" + re.escape(val) + r"(?![\w-])", ntext) is not None
            elif kind == "sha":
                hit = any(val.startswith(s) for s in re.findall(r"\b[0-9a-f]{7,40}\b", low))
            if hit:
                viol.append({"agent": owner, "where": where, "probe": p["id"], "kind": kind,
                             "probe_agent": p["agent"]})
    shas = [v for _, k, v in canon if k == "sha"]
    for a in team.get("agents") or []:
        for fid in sorted(set((a.get("facts_used") or []) + (a.get("invariants") or []))):
            for s in re.findall(r"[0-9a-f]{7,40}", str(fid).lower()):
                if any(x.startswith(s) for x in shas):
                    warns.append({"agent": a.get("name"), "fact_id": fid,
                                  "why": "id de fato carrega prefixo de sha do gabarito; não renderize ids no cartão"})
    rep = {"schema_version": 1, "gate": "anti-cola (regra 6)", "pass": not viol,
           "violations": viol, "warnings": warns, "canonical_answers": len(canon)}
    return rep


def run_anticola(target, extra_paths=None):
    rep = anticola_report(target, extra_paths=extra_paths)
    write_json(target, sp_path(target, "probes", "anticola.json5"), rep)
    return rep
