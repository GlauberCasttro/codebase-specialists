#!/usr/bin/env python3
"""router — cs-route: delegar ao modelo mais barato que resolve (ARCHITECTURE §8-undecies).

Reimplementação compacta e independente das lições do model-router do servico-parametros:
- sinal de complexidade SÓ do brief estruturado (classe, nº allowed_paths, LOC, hot_path, invariantes,
  colisão, ato) — ato entra DENTRO do score (mesmo bucket em recommend/dispatch/outcome);
- Thompson/Beta por faixa×tier com recompensa por tier, veto por evidência, exploração seedada;
- incerteza RELATIVA 1-(melhor-segundo)/(melhor+segundo);
- regras fixas: gate ≥ tier do autor; risco/security no topo; retry sobe tier; abstenção não penaliza;
- treina SÓ com procedência declarada-no-despacho|medida; correção por `anular`, nunca apagando linha.
Ledger append-only encadeado: .swarm/state/model-router.jsonl. Priors = replay do ledger (fonte única).
"""
import argparse
import hashlib
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import hcore  # noqa: E402
import j5  # noqa: E402


def cfg():
    for p in (os.path.join(HERE, "routing.json5"), os.path.join(os.path.dirname(HERE), "routing.json5")):
        if os.path.isfile(p):
            return j5.load(p)
    raise hcore.StateError("routing.json5 ausente ao lado do motor")


def ledger_path(root):
    return os.path.join(hcore.state_paths(root)["state_dir"], "model-router.jsonl")


def tiers(c=None):
    c = c or cfg()
    return list(c["platforms"][c["platform"]]["tiers"])


def tier_index(model, c=None):
    t = tiers(c)
    return t.index(model) if model in t else None


def _loc(root, paths):
    n = 0
    for p in paths:
        if any(ch in p for ch in "*?["):
            continue
        f = os.path.join(root, p)
        if os.path.isfile(f):
            try:
                with open(f, "rb") as fh:
                    n += fh.read().count(b"\n")
            except OSError:
                pass
    return n


def complexity(ctx, task, act="dev", c=None):
    c = c or cfg()
    cls = ctx.task_class(task) if hasattr(ctx, "task_class") else (task.get("class") or "pequena")
    ap = task.get("allowed_paths") or []
    inv = [i for i in (task.get("briefing") or {}).get("invariants") or [] if isinstance(i, dict) and not i.get("global")]
    flags = task.get("flags") or {}
    coll = 0.0
    try:
        import engine
        for t, d in engine.all_delegs(ctx.board):
            if t["id"] != task["id"] and d["agent"] != task["agent"] and engine.collision_reason(ctx, d["agent"], task["agent"]):
                coll = 1.0
                break
    except Exception:
        pass
    loc = _loc(ctx.root, ap)
    comp = {"class": cls, "n_paths": len(ap), "loc": loc, "hot_path": bool(flags.get("hot_path")),
            "invariants": len(inv), "collision": coll, "act": act}
    s = (0.45 * c["class_weight"].get(cls, 0.3) + 0.12 * min(len(ap) / 6.0, 1) + 0.13 * min(loc / 600.0, 1)
         + 0.1 * (1 if flags.get("hot_path") else 0) + 0.1 * min(len(inv) / 4.0, 1) + 0.05 * coll
         + c["act_adjust"].get(act, 0.0))
    s = max(0.0, min(1.0, s))
    band = "baixo" if s < c["bands"]["baixo"] else ("medio" if s < c["bands"]["medio"] else "alto")
    return round(s, 4), band, comp


def read_ledger(root):
    recs, _, _ = hcore.read_chain(ledger_path(root))
    return recs


def priors(root, c=None):
    c = c or cfg()
    recs = read_ledger(root)
    annulled = {r.get("target_at") for r in recs if r.get("event") == "anulacao"}
    pr = {}
    for b in ("baixo", "medio", "alto"):
        pr[b] = {t: [1.0, 1.0] for t in tiers(c)}
    for r in recs:
        if r.get("event") != "outcome" or not r.get("trains") or r.get("at") in annulled:
            continue
        if r.get("band") in pr and r.get("tier") in pr[r["band"]]:
            pr[r["band"]][r["tier"]][0 if r.get("success") else 1] += 1.0
    return pr


def _append(root, rec):
    p = hcore.state_paths(root)
    rec = dict(rec)
    rec.setdefault("at", hcore.now_iso())
    with hcore.file_lock(p["lock"]):
        hcore.append_chained(ledger_path(root), rec)
    return rec


def recommend(ctx, task, deleg, act="dev", author_tier=None, log=True):
    c = cfg()
    ts = tiers(c)
    score, band, comp = complexity(ctx, task, act, c)
    if ts == ["inherit"]:
        rec = {"model": "inherit", "tier": 0, "band": band, "score": score, "uncertainty": 0.0,
               "reason": "plataforma sem seleção de modelo (inherit)", "platform": c["platform"]}
        return rec
    pr = priors(ctx.root, c)[band]
    seed = int(hashlib.sha256(("%s|%s|%s" % (deleg["id"], deleg.get("retries", 0), act)).encode()).hexdigest()[:12], 16)
    rng = random.Random(seed)
    vetoed = [t for t in ts if (pr[t][0] + pr[t][1] - 2) >= c["veto_min_samples"] and pr[t][0] / (pr[t][0] + pr[t][1]) < c["veto_threshold"]]
    trained = any(pr[t][0] + pr[t][1] > 2 for t in ts)
    cls = comp["class"]
    reason = []
    if not trained:
        idx = int(c["start_table"].get(cls, 1))
        samples = {}
        unc = 1.0
        reason.append("tabela de partida (%s→%s; sem amostras treináveis na faixa %s)" % (cls, ts[idx], band))
    else:
        samples = {}
        for i, t in enumerate(ts):
            if t in vetoed:
                continue
            samples[t] = rng.betavariate(pr[t][0], pr[t][1]) * c["reward_by_tier"][i]
        if not samples:
            samples = {ts[-1]: 1.0}
        ranked = sorted(samples.items(), key=lambda kv: -kv[1])
        best = ranked[0]
        second = ranked[1] if len(ranked) > 1 else (best[0], 0.0)
        unc = 1.0 - (best[1] - second[1]) / ((best[1] + second[1]) or 1.0)
        idx = ts.index(best[0])
        if rng.random() < c["exploration_rate"]:
            idx = ts.index(rng.choice(list(samples)))
            reason.append("exploração")
        reason.append("Thompson faixa %s → %s (incerteza relativa %.2f)" % (band, ts[idx], unc))
        if vetoed:
            reason.append("vetados por evidência: %s" % ",".join(vetoed))
    flags = task.get("flags") or {}
    if cls == "risco" or flags.get("security_gate") or "security" in (deleg.get("agent") or task["agent"]):
        idx = len(ts) - 1
        reason.append("regra fixa: risco/security no topo")
    r = int(deleg.get("retries") or 0)
    if r:
        idx = min(len(ts) - 1, idx + r)
        reason.append("regra fixa: retry sobe %d tier(s)" % r)
    if author_tier is not None and idx < author_tier:
        idx = author_tier
        reason.append("regra fixa: gate ≥ tier do autor")
    rec = {"model": ts[idx], "tier": idx, "band": band, "score": score, "uncertainty": round(unc, 3),
           "reason": "; ".join(reason), "platform": c["platform"], "components": comp}
    if log:
        _append(ctx.root, {"event": "recomendacao", "deleg": deleg["id"], "act": act, "model": rec["model"],
                           "band": band, "score": score})
    return rec


def expected_model(deleg):
    ov = deleg.get("route_override") or {}
    if ov.get("model"):
        return ov["model"], "override"
    return (deleg.get("route") or {}).get("model"), "recomendacao"


def dispatch_model_problems(ctx, deleg, a):
    exp, why = expected_model(deleg)
    if not exp or exp == "inherit":
        return []
    got = a.get("model")
    if not got:
        return ["despacho sem model: passe model=%r (recomendação de cs-route) ou registre override com motivo "
                "(cs-route override %s --model X --reason ...)" % (exp, deleg["id"])]
    if got != exp:
        return ["model=%r ≠ %s %r: use o recomendado ou cs-route override %s --model %s --reason ..." % (got, why, exp, deleg["id"], got)]
    return []


def review_model_problems(ctx, task, deleg, model):
    """Gate nunca abaixo do tier do autor."""
    c = cfg()
    if tiers(c) == ["inherit"]:
        return []
    if not model:
        return ["despacho de revisão sem model (gate ≥ tier do autor)"]
    author = ((deleg.get("model") or {}).get("name")) or (deleg.get("route") or {}).get("model")
    ai, gi = tier_index(author, c), tier_index(model, c)
    if gi is None:
        return ["model %r desconhecido (tiers: %s)" % (model, ", ".join(tiers(c)))]
    if ai is not None and gi < ai:
        return ["gate em %s abaixo do autor (%s): verificador mais fraco confirma ao acaso" % (model, author)]
    return []


def outcome_from_event(root, board, rec):
    typ = rec["type"]
    d = hcore.find(board, "deleg", rec["entity"])
    if d is None:
        return None
    task = hcore.task_of_deleg(board, d["id"])
    success = typ == "delegation.accept"
    c = cfg()
    m = d.get("model") or {}
    model, proc = m.get("name"), m.get("procedencia") or "desconhecido"
    if not model:
        model, proc = (d.get("route") or {}).get("model"), "recomendacao"
    band = (d.get("route") or {}).get("band")
    trains = proc in c["trainable_procedencia"] and model in tiers(c) and bool(band)
    return _append(root, {"event": "outcome", "deleg": d["id"], "task": task["id"] if task else None, "band": band,
                          "tier": model, "success": success, "procedencia": proc, "trains": trains, "source": typ})


def measured(root, deleg_id, model):
    return _append(root, {"event": "medicao", "deleg": deleg_id, "model": model})


def anular(root, target_at, motivo):
    if not motivo:
        raise hcore.Refused("anular exige --motivo")
    if not any(r.get("at") == target_at for r in read_ledger(root)):
        raise hcore.Refused("nenhuma linha com at=%s" % target_at)
    return _append(root, {"event": "anulacao", "target_at": target_at, "motivo": motivo})


def stats(root):
    c = cfg()
    recs = read_ledger(root)
    dist, succ, n, saved = {}, {}, {}, 0.0
    ts = tiers(c)
    for r in recs:
        if r.get("event") == "recomendacao":
            dist[r["model"]] = dist.get(r["model"], 0) + 1
            if r["model"] in ts:
                saved += c["cost"][-1] - c["cost"][ts.index(r["model"])]
        if r.get("event") == "outcome" and r.get("trains"):
            k = "%s/%s" % (r["band"], r["tier"])
            n[k] = n.get(k, 0) + 1
            succ[k] = succ.get(k, 0) + (1 if r["success"] else 0)
    return {"distribution": dist, "success_rate": {k: round(succ[k] / float(n[k]), 3) for k in n}, "samples": n,
            "untrained_outcomes": sum(1 for r in recs if r.get("event") == "outcome" and not r.get("trains")),
            "estimated_cost_avoided_vs_top": round(saved, 3),
            "priors": priors(root, c)}


def main(argv=None):
    import cmds
    import engine
    ap = argparse.ArgumentParser(prog="cs-route")
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("recommend")
    r.add_argument("id")
    r.add_argument("--act", default="dev")
    o = sub.add_parser("override")
    o.add_argument("id")
    o.add_argument("--model", required=True)
    o.add_argument("--reason", required=True)
    oc = sub.add_parser("outcome", help="registra outcome manual (sem procedência não treina)")
    oc.add_argument("id")
    oc.add_argument("--success", action="store_true")
    oc.add_argument("--procedencia", default="desconhecido")
    an = sub.add_parser("anular")
    an.add_argument("--at", required=True)
    an.add_argument("--motivo", required=True)
    sub.add_parser("stats")
    a = ap.parse_args(argv)
    try:
        root = hcore.resolve_root(a.root)
        if a.cmd == "recommend":
            ctx = engine.Ctx(root, hcore.load_board(root))
            tid = cmds.resolve_task_id(ctx, a.id)
            t = ctx.find("task", tid)
            d = engine.latest_deleg(t)
            rec = recommend(ctx, t, d, act=a.act, log=False)
            print("tier: %s (faixa %s, score %.2f, incerteza %.2f)" % (rec["model"], rec["band"], rec["score"], rec["uncertainty"]))
            print("motivo: %s" % rec["reason"][:300])
            print("despache com: Agent(subagent_type=%r, model=%r, description='%s: ...')" % (d["agent"], rec["model"], d["id"]))
        elif a.cmd == "override":
            cmds.override_model(root, os.environ.get("CS_ACTOR", "lead"), a.id, a.model, a.reason)
            _append(root, {"event": "override", "deleg": a.id, "model": a.model, "reason": a.reason})
            print("override registrado: %s → %s" % (a.id, a.model))
        elif a.cmd == "outcome":
            c = cfg()
            board = hcore.load_board(root)
            d = hcore.find(board, "deleg", a.id) or engine.latest_deleg(hcore.find(board, "task", a.id) or {})
            if not d:
                raise hcore.Refused("delegação %s inexistente" % a.id)
            band = (d.get("route") or {}).get("band")
            model = (d.get("model") or {}).get("name") or (d.get("route") or {}).get("model")
            trains = a.procedencia in c["trainable_procedencia"] and bool(band)
            _append(root, {"event": "outcome", "deleg": d["id"], "band": band, "tier": model, "success": a.success,
                           "procedencia": a.procedencia, "trains": trains, "source": "manual"})
            print("outcome registrado (treina: %s)" % trains)
        elif a.cmd == "anular":
            anular(root, a.at, a.motivo)
            print("anulado %s" % a.at)
        elif a.cmd == "stats":
            print(j5.dumps(stats(root)))
        else:
            ap.print_help(sys.stderr)
            return 2
    except hcore.Refused as e:
        sys.stderr.write(e.render() + "\n")
        return 1
    except hcore.StateError as e:
        sys.stderr.write("cs-route: %s\n" % e)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
