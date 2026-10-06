#!/usr/bin/env python3
"""pareado.py — comparação PAREADA POR ITEM de duas configurações (critério de decisão da campanha-iter11).

Uso:
  python3 pareado.py <runs> --a with_skill_fast --b without_skill [--kind Q] [--seed 11] [--boot 10000]
                     [--margin 0.05] [--json <saida.json>]

Lê <runs>/eval-<id>-<fixture>/<config>/run-*/grading.json (layout do summarize.py). Item = (fixture, asserção
[Q] identificada pelo gate entre colchetes + 60 primeiros caracteres sem números). Para cada item comum às duas
configs: p_a, p_b = fração de execuções que passaram; d = p_a − p_b. Estatística = média de d sobre os itens; IC95%
por bootstrap percentil reamostrando ITENS (e, à parte, reamostrando FIXTURES — sensibilidade). Também:
média de [Q] por fixture e config; itens com d ≤ −0,5 (regressão). Python 3.9+, stdlib. Determinístico (seed).

Decisão impressa (ESPEC §9):
  GANHO        IC95% (itens) com limite inferior > 0, [Q]_a ≥ [Q]_b em cada fixture e nenhum item com d ≤ −0,5
  EQUIVALENTE  IC95% inteiro dentro de [−margin, +margin]
  PIORA        IC95% com limite superior < 0
  INCONCLUSIVO caso contrário
"""
import argparse
import glob
import json
import os
import random
import re
import sys


def item_key(text):
    t = re.sub(r"^\[[QS]\]", "", text)
    gate = re.match(r"^\[([A-Z0-9]+)\]", t)
    body = re.sub(r"\d+([.,]\d+)?", "#", t)[:60]
    return (gate.group(1) if gate else "?") + "|" + body


def collect(runs, config, kind):
    """→ {(fixture, item): [passed...]} e {fixture: [q_passed/q_total por run]}"""
    items, per_fix = {}, {}
    pat = os.path.join(runs, "eval-*", config, "run-*", "grading.json")
    for gp in sorted(glob.glob(pat)):
        ev = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(gp))))
        fixture = re.sub(r"^eval-\d+-", "", ev)
        with open(gp, encoding="utf-8") as fh:
            g = json.load(fh)
        exp = [e for e in g.get("expectations") or [] if str(e.get("text", "")).startswith("[%s]" % kind)]
        if not exp:
            continue
        per_fix.setdefault(fixture, []).append(sum(1 for e in exp if e.get("passed")) / float(len(exp)))
        for e in exp:
            items.setdefault((fixture, item_key(e["text"])), []).append(bool(e.get("passed")))
    return items, per_fix


def mean(xs):
    return sum(xs) / float(len(xs)) if xs else float("nan")


def boot_ci(values, groups, n, rng):
    """Percentil 2,5–97,5 da média; reamostra unidades (groups=None → itens; senão grupos = fixtures)."""
    if groups is None:
        units = [[v] for v in values]
    else:
        by = {}
        for v, g in zip(values, groups):
            by.setdefault(g, []).append(v)
        units = list(by.values())
    stats = []
    for _ in range(n):
        pick = [units[rng.randrange(len(units))] for _ in units]
        flat = [v for u in pick for v in u]
        stats.append(mean(flat))
    stats.sort()
    return stats[int(0.025 * n)], stats[int(0.975 * n) - 1]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("runs")
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--kind", default="Q", choices=["Q", "S"])
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--margin", type=float, default=0.05)
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    ia, fa = collect(a.runs, a.a, a.kind)
    ib, fb = collect(a.runs, a.b, a.kind)
    common = sorted(set(ia) & set(ib))
    if not common:
        sys.stderr.write("pareado: nenhum item comum entre %s e %s em %s\n" % (a.a, a.b, a.runs))
        return 2
    d = [mean(ia[k]) - mean(ib[k]) for k in common]
    fixtures = [k[0] for k in common]
    rng = random.Random(a.seed)
    lo, hi = boot_ci(d, None, a.boot, rng)
    flo, fhi = boot_ci(d, fixtures, a.boot, random.Random(a.seed + 1))
    regress = [{"fixture": k[0], "item": k[1], "d": round(x, 3)} for k, x in zip(common, d) if x <= -0.5]
    fix_ok = {f: (mean(fa.get(f, [])), mean(fb.get(f, []))) for f in sorted(set(fixtures))}
    every_fix = all(x >= y for x, y in fix_ok.values())
    if lo > 0 and every_fix and not regress:
        verdict = "GANHO"
    elif -a.margin <= lo and hi <= a.margin:
        verdict = "EQUIVALENTE"
    elif hi < 0:
        verdict = "PIORA"
    else:
        verdict = "INCONCLUSIVO"
    res = {"a": a.a, "b": a.b, "kind": a.kind, "items": len(common), "mean_d": round(mean(d), 4),
           "ci95_items": [round(lo, 4), round(hi, 4)], "ci95_fixtures": [round(flo, 4), round(fhi, 4)],
           "runs_a": {f: len(v) for f, v in fa.items()}, "runs_b": {f: len(v) for f, v in fb.items()},
           "per_fixture": {f: {"a": round(x, 4), "b": round(y, 4)} for f, (x, y) in fix_ok.items()},
           "regressions": regress, "only_a": len(set(ia) - set(ib)), "only_b": len(set(ib) - set(ia)),
           "verdict": verdict, "seed": a.seed, "boot": a.boot, "margin": a.margin}
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
