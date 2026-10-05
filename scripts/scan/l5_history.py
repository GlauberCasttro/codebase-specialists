"""L5 histórico git: hotspots (churn × tamanho), co-change (suporte/confiança), commits de
correção (fix/bug/hotfix/revert) com arquivos tocados, ownership por autor."""

import math
import re

from cslib import CsError, gitx, paths
from cslib.evidence import ev_cmd, ev_commit, ev_file, slug

LAYER = "history"
FIX_RE = re.compile(r"\b(fix|fixes|fixed|fixup|bug|bugfix|hotfix|revert|reverts|corrige|corrigido|"
                    r"correção|correcao|conserta)\b", re.I)
MAX_FILES_PER_COMMIT = 30   # commits maiores (reformatações, imports em massa) não entram em co-change
MIN_SUPPORT = 3
MIN_CONFIDENCE = 0.5


def load_commits(ctx):
    if not hasattr(ctx, "_commits"):
        if gitx.head(ctx.target) is None:
            raise CsError("o repositório não tem commits; L5 (histórico) precisa de pelo menos um",
                          "faça um commit (`git add -A && git commit -m init`) ou rode sem L5/L6: "
                          "--layers L0,L1,L2,L3,L4,L7,L8,L9")
        ctx._commits = gitx.log_commits(ctx.target, ctx.opts.max_commits)
    return ctx._commits


def run(ctx):
    fb = ctx.fb
    commits = load_commits(ctx)
    analyzed = set(ctx.files)
    loc = {}
    inv = ctx.layer("L0")
    for e in inv["files"]:
        if "loc" in e:
            loc[e["path"]] = e["loc"]

    churn = {}
    authors_by_file = {}
    pair = {}
    fixes = []
    log_ev = ev_cmd("git log --no-merges --no-renames --numstat -n %d" % ctx.opts.max_commits, 0,
                    "\n".join(c["sha"] for c in commits).encode("utf-8"))
    for c in commits:
        touched = sorted(set(f["path"] for f in c["files"] if f["path"] in analyzed))
        for f in c["files"]:
            p = f["path"]
            if p not in analyzed:
                continue
            st = churn.setdefault(p, {"commits": 0, "added": 0, "deleted": 0})
            st["commits"] += 1
            st["added"] += f["added"]
            st["deleted"] += f["deleted"]
            a = authors_by_file.setdefault(p, {})
            a[c["author"]] = a.get(c["author"], 0) + 1
        if 2 <= len(touched) <= MAX_FILES_PER_COMMIT:
            for i in range(len(touched)):
                for j in range(i + 1, len(touched)):
                    k = (touched[i], touched[j])
                    pair[k] = pair.get(k, 0) + 1
        msg = c["subject"] + "\n" + c["body"]
        if FIX_RE.search(msg):
            fixes.append({"sha": c["sha"], "subject": c["subject"], "author": c["author"],
                          "ts": c["ts"], "files": touched,
                          "kind": "revert" if re.search(r"\brevert", msg, re.I) else "fix"})

    hot = []
    for p, st in churn.items():
        score = st["commits"] * math.log(1 + loc.get(p, 0))
        hot.append({"path": p, "commits": st["commits"], "added": st["added"], "deleted": st["deleted"],
                    "loc": loc.get(p, 0), "score": round(score, 4),
                    "fix_commits": sum(1 for fx in fixes if p in fx["files"])})
    hot.sort(key=lambda h: (-h["score"], h["path"]))

    cochange = []
    for (a, b), sup in pair.items():
        if sup < MIN_SUPPORT:
            continue
        ca, cb = churn[a]["commits"], churn[b]["commits"]
        conf_ab, conf_ba = sup / float(ca), sup / float(cb)
        if max(conf_ab, conf_ba) >= MIN_CONFIDENCE:
            cochange.append({"a": a, "b": b, "support": sup, "conf_a_b": round(conf_ab, 4),
                             "conf_b_a": round(conf_ba, 4)})
    cochange.sort(key=lambda x: (-x["support"], -max(x["conf_a_b"], x["conf_b_a"]), x["a"], x["b"]))

    owners = {}
    for p, a in authors_by_file.items():
        comp = paths.component_of(p)
        o = owners.setdefault(comp, {})
        for name, n in a.items():
            o[name] = o.get(name, 0) + n
    ownership = []
    for comp in sorted(owners):
        total = sum(owners[comp].values())
        ranked = sorted(owners[comp].items(), key=lambda kv: (-kv[1], kv[0]))
        ownership.append({"component": comp, "touches": total,
                          "authors": [{"name": n, "touches": k, "share": round(k / float(total), 4)}
                                      for n, k in ranked[:5]]})

    facts = []
    facts.append(fb.fact("hist.stats", LAYER,
                         "%d commits analisados (sem merges); %d arquivos atuais com histórico; %d "
                         "commits de correção/revert" % (len(commits), len(churn), len(fixes)),
                         [log_ev], scope=["**"]))
    for i, h in enumerate(hot[:20]):
        facts.append(fb.fact("hist.hotspot.%s" % slug(h["path"]), LAYER,
                             "Hotspot #%d: %s (%d commits, %d LOC, +%d/-%d, %d correções)" % (
                                 i + 1, h["path"], h["commits"], h["loc"], h["added"], h["deleted"],
                                 h["fix_commits"]),
                             [ev_file(h["path"]), log_ev],
                             confidence="high" if h["commits"] >= 5 else "medium",
                             scope=[h["path"]],
                             data={"kind": "hotspot", "path": h["path"], "commits": h["commits"],
                                   "loc": h["loc"], "score": h["score"], "fix_commits": h["fix_commits"]}))
    for cc in cochange[:40]:
        facts.append(fb.fact("hist.cochange.%s" % slug("%s--%s" % (cc["a"], cc["b"]), 120), LAYER,
                             "%s e %s mudam juntos (suporte %d; confiança %.2f / %.2f)" % (
                                 cc["a"], cc["b"], cc["support"], cc["conf_a_b"], cc["conf_b_a"]),
                             [ev_file(cc["a"]), ev_file(cc["b"]), log_ev],
                             confidence="high" if cc["support"] >= 5 else "medium",
                             scope=[cc["a"], cc["b"]],
                             data={"kind": "cochange", "a": cc["a"], "b": cc["b"], "support": cc["support"],
                                   "conf_a_b": cc["conf_a_b"], "conf_b_a": cc["conf_b_a"]}))
    for fx in fixes[:100]:
        if not fx["files"]:
            continue
        facts.append(fb.fact("hist.fix.%s" % fx["sha"][:12], LAYER,
                             "Correção %s '%s' tocou %s" % (
                                 fx["sha"][:12], fx["subject"][:140], ", ".join(fx["files"][:6]) +
                                 (" e mais %d" % (len(fx["files"]) - 6) if len(fx["files"]) > 6 else "")),
                             [ev_commit(fx["sha"], fx["files"][:20])],
                             confidence="high", scope=fx["files"][:50],
                             data={"kind": fx["kind"], "sha": fx["sha"], "subject": fx["subject"],
                                   "files": fx["files"]}))
    for o in ownership:
        if not o["authors"]:
            continue
        top = o["authors"][0]
        facts.append(fb.fact("hist.owner.%s" % slug(o["component"]), LAYER,
                             "%s: autor principal %s (%.0f%% de %d toques); outros: %s" % (
                                 o["component"], top["name"], 100 * top["share"], o["touches"],
                                 ", ".join(a["name"] for a in o["authors"][1:4]) or "nenhum"),
                             [log_ev], confidence="medium",
                             scope=[o["component"] + "/**" if o["component"] != "." else "*"]))
    return {"layer": LAYER, "commits_analyzed": len(commits), "max_commits": ctx.opts.max_commits,
            "hotspots": hot[:100], "cochange": cochange[:200], "fixes": fixes,
            "ownership": ownership, "facts": facts}
