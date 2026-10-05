#!/usr/bin/env python3
"""summarize.py — agrega [Q] e [S] SEPARADOS por configuração (o aggregate do skill-creator mistura os dois e o
pass rate total engana: a baseline nem tem os artefatos [S]).

Uso:
  python3 evals/summarize.py <iteração>/runs [--out-dir <iteração>]

Lê <runs>/eval-*/<config>/run-*/grading.json (summary.quality/structure, ou o prefixo [Q]/[S] de cada
expectation) e timing.json (total_duration_seconds|duration_ms, total_tokens). Grava benchmark-q.json e
benchmark-q.md em --out-dir (default: pai de <runs>). Python 3.9+ stdlib.
"""
import argparse
import glob
import json
import math
import os
import sys


def mean_sd(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None, 0
    m = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) if len(xs) > 1 else 0.0
    return m, sd, len(xs)


def counts(grading, kind):
    part = (grading.get("summary") or {}).get({"Q": "quality", "S": "structure"}[kind])
    if isinstance(part, dict) and "total" in part:
        return part.get("passed", 0), part.get("total", 0)
    exp = [e for e in grading.get("expectations") or [] if str(e.get("text", "")).startswith("[%s]" % kind)]
    return sum(1 for e in exp if e.get("passed")), len(exp)


def load(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def collect(runs_dir):
    rows = []
    for gp in sorted(glob.glob(os.path.join(runs_dir, "eval-*", "*", "run-*", "grading.json"))):
        run_dir = os.path.dirname(gp)
        config = os.path.basename(os.path.dirname(run_dir))
        ev = os.path.basename(os.path.dirname(os.path.dirname(run_dir)))
        g = load(gp) or {}
        t = load(os.path.join(run_dir, "timing.json")) or {}
        secs = t.get("total_duration_seconds")
        if secs is None and t.get("duration_ms") is not None:
            secs = t["duration_ms"] / 1000.0
        qp, qt = counts(g, "Q")
        sp, st = counts(g, "S")
        rows.append({
            "eval": ev, "config": config, "run": os.path.basename(run_dir),
            "q_passed": qp, "q_total": qt, "q_rate": (qp / float(qt)) if qt else None,
            "s_passed": sp, "s_total": st, "s_rate": (sp / float(st)) if st else None,
            "q_failed": [e["text"] for e in g.get("expectations") or []
                         if str(e.get("text", "")).startswith("[Q]") and not e.get("passed")],
            "seconds": secs, "tokens": t.get("total_tokens"), "timing_note": t.get("note"),
        })
    return rows


def summarize(rows):
    out = {}
    cfgs = sorted(set(r["config"] for r in rows), key=lambda c: (c != "with_skill", c))  # with_skill primeiro
    for cfg in cfgs:
        rs = [r for r in rows if r["config"] == cfg]
        agg = {}
        for k in ("q_rate", "s_rate", "seconds", "tokens"):
            m, sd, n = mean_sd([r[k] for r in rs])
            agg[k] = {"mean": m, "sd": sd, "n": n}
        agg["runs"] = len(rs)
        out[cfg] = agg
    return out


def fmt(a, pct=False, unit=""):
    if a["mean"] is None:
        return "—"
    if pct:
        return "%.0f%% ± %.0f%%" % (a["mean"] * 100, a["sd"] * 100)
    return "%.0f%s ± %.0f%s" % (a["mean"], unit, a["sd"], unit)


def render_md(rows, summ, runs_dir):
    cfgs = list(summ)
    L = ["# Benchmark Q/S — codebase-specialists", "",
         "Fonte: `%s` (%d runs). [Q] = qualidade neutra de formato (comparável com a baseline); "
         "[S] = estrutura da skill (a baseline não tem esses artefatos — não compare por ela)." % (runs_dir, len(rows)),
         "", "| Métrica | " + " | ".join(cfgs) + (" | Delta (%s − %s) |" % (cfgs[0], cfgs[1]) if len(cfgs) == 2 else " |"),
         "|---|" + "---|" * len(cfgs) + ("---|" if len(cfgs) == 2 else "")]
    for key, label, pct, unit in (("q_rate", "[Q] pass rate", True, ""), ("s_rate", "[S] pass rate", True, ""),
                                  ("seconds", "Tempo", False, "s"), ("tokens", "Tokens", False, "")):
        cells = [fmt(summ[c][key], pct, unit) for c in cfgs]
        delta = ""
        if len(cfgs) == 2:
            a, b = summ[cfgs[0]][key]["mean"], summ[cfgs[1]][key]["mean"]
            if a is not None and b is not None:
                delta = (" %+.2f |" % (a - b)) if pct else (" %+.0f |" % (a - b))
            else:
                delta = " — |"
        L.append("| %s | %s |%s" % (label, " | ".join(cells), delta))
    L += ["", "## Por run", "", "| eval | config | [Q] | [S] | tempo (s) | tokens | [Q] falhas |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append("| %s | %s | %d/%d | %d/%d | %s | %s | %s |" % (
            r["eval"], r["config"], r["q_passed"], r["q_total"], r["s_passed"], r["s_total"],
            "—" if r["seconds"] is None else "%.0f" % r["seconds"], r["tokens"] if r["tokens"] is not None else "—",
            "; ".join(t[:70] for t in r["q_failed"]) or "—"))
    notes = sorted(set(r["timing_note"] for r in rows if r.get("timing_note")))
    if notes:
        L += ["", "Notas de timing.json:"] + ["- " + n for n in notes]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("runs_dir")
    ap.add_argument("--out-dir", default=None)
    a = ap.parse_args(argv)
    runs = os.path.abspath(a.runs_dir)
    rows = collect(runs)
    if not rows:
        sys.stderr.write("summarize: nenhum grading.json em %s/eval-*/<config>/run-*/\n" % runs)
        return 2
    summ = summarize(rows)
    out_dir = os.path.abspath(a.out_dir or os.path.dirname(runs))
    with open(os.path.join(out_dir, "benchmark-q.json"), "w", encoding="utf-8") as fh:
        json.dump({"runs_dir": runs, "configurations": summ, "runs": rows}, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    md = render_md(rows, summ, runs)
    with open(os.path.join(out_dir, "benchmark-q.md"), "w", encoding="utf-8") as fh:
        fh.write(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
