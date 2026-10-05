"""`cs.py init` e `cs.py stage status|load|check|done` (ARCHITECTURE §8-terdecies, gate G16)."""

import sys

from cslib import CsError, json5io
from . import engine


def h_init(args):
    plats = [p.strip() for p in (args.platforms or "").split(",") if p.strip()]
    if args.check_repo:
        ok, msg = engine.check_repo(args.target)
        (sys.stdout if ok else sys.stderr).write(("ok: " if ok else "falta: ") + msg + "\n")
        return 0 if ok else 1
    if args.check:
        run = engine.read_run(args.target)
        miss = [k for k in ("schema_version", "run_id", "target", "stages") if k not in run]
        if miss:
            raise CsError("run.json5 sem chaves %s" % miss, "recrie com `cs.py init --force`", code=1)
        if not run.get("initialized_by"):
            raise CsError("run.json5 criado automaticamente (stage load), sem `cs.py init` explícito",
                          "rode `cs.py init --platforms <as escolhidas em init.2>` (merge; não perde progresso)",
                          code=1)
        if not run.get("platforms"):
            raise CsError("run.json5 sem plataformas", "rode `cs.py init --platforms ...`", code=1)
        sys.stdout.write("ok: run.json5 válido (run_id %s; plataformas %s)\n" % (run["run_id"],
                                                                               ",".join(run["platforms"])))
        return 0
    run, created, changes = engine.init_run(args.target, plats, force=args.force)
    if created:
        sys.stdout.write("criado .swarm/run.json5 (run_id %s; plataformas %s)\n"
                         % (run["run_id"], ",".join(run["platforms"])))
    else:
        sys.stdout.write("mesclado em .swarm/run.json5 (run_id %s; progresso mantido): %s\n"
                         % (run["run_id"], "; ".join(changes) if changes else "nada mudou (idempotente)"))
    return 0


def h_status(args):
    cfg = engine.load_stages()
    run = engine.read_run(args.target)
    cur = run.get("current_stage") or cfg["order"][0]
    out = {"current_stage": cur, "stages": []}
    for name in cfg["order"]:
        st = engine.stage_state(run, name)
        pend = engine.pending(cfg, run, name)
        row = {"stage": name, "status": st["status"], "done": len(cfg["stages"][name]["substages"]) - len(pend),
               "pending": [s["id"] for s in pend]}
        sk = [k for k, v in sorted(st["substages"].items()) if v.get("status") == "skipped"]
        if sk:
            row["skipped"] = sk
        out["stages"].append(row)
    skips = engine.skipped(run)
    if skips:
        out["skipped"] = skips
    if cur in cfg["stages"]:
        p = engine.pending(cfg, run, cur)
        out["current_substage"] = p[0]["id"] if p else None
    sys.stdout.write(json5io.dumps(out, "cs.py stage status"))
    return 0


def h_load(args):
    cfg = engine.load_stages()
    run = engine.read_run(args.target, required=(args.stage != cfg["order"][0]))
    if run is None:
        run, _, _ = engine.init_run(args.target, explicit=False)
    pkg, text = engine.load_package(args.target, cfg, run, args.stage)
    sys.stdout.write(json5io.dumps(pkg, "pacote de entrada da etapa %s (~%d tokens) — cs.py stage load"
                                   % (args.stage, engine.est_tokens(text))))
    return 0


def h_check(args):
    cfg = engine.load_stages()
    run = engine.read_run(args.target)
    name, sub, rec = engine.check_substage(args.target, cfg, run, args.substage,
                                           answer=args.answer, note=args.note)
    ok = rec["status"] == "done"
    sys.stdout.write("%s %s: %s%s\n" % ("ok" if ok else "FALHOU", sub["id"], sub["do"],
                                        ("" if ok else " — " + (rec.get("detail") or ""))))
    return 0 if ok else 1


def h_done(args):
    cfg = engine.load_stages()
    run = engine.read_run(args.target)
    ok, failures, handoff = engine.done_stage(args.target, cfg, run, args.stage)
    if not ok:
        for sid, why in failures:
            sys.stderr.write("FALHOU %s: %s\n" % (sid, why))
        sys.stderr.write("etapa %s NÃO avançou (%d item(ns) pendente(s))\n" % (args.stage, len(failures)))
        return 1
    sys.stdout.write("etapa %s fechada → .swarm/stages/%s.handoff.json5; próxima: %s\n"
                     % (args.stage, args.stage, engine.read_run(args.target).get("current_stage")))
    return 0


def h_skip(args):
    cfg = engine.load_stages()
    run = engine.read_run(args.target)
    name, sub = engine.skip_substage(args.target, cfg, run, args.substage, args.reason)
    sys.stdout.write("pulada %s: %s — motivo registrado (aparece em `stage status` e no relatório)\n"
                     % (sub["id"], sub["do"]))
    return 0


def register(subparsers):
    pi = subparsers.add_parser("init", help="cria .swarm/run.json5 (estado da execução)")
    pi.add_argument("--platforms", default="", help="ex.: claude-code,cursor,copilot,codex")
    pi.add_argument("--force", action="store_true", help="recria run.json5 (perde o progresso)")
    pi.add_argument("--check", action="store_true",
                    help="check de init.3: run.json5 válido, criado/mesclado por `cs.py init` explícito")
    pi.add_argument("--check-repo", action="store_true", help="check de init.1: o alvo é a RAIZ de um repo git")
    pi.set_defaults(func=h_init)

    p = subparsers.add_parser("stage", help="etapas: status | load <etapa> | check <sub> | skip <sub> | done <etapa>")
    sub = p.add_subparsers(dest="stage_cmd", metavar="<ação>")
    s = sub.add_parser("status", help="etapa/sub-etapa atual e pendências")
    s.set_defaults(func=h_status)
    s = sub.add_parser("load", help="pacote de entrada ≤2k tokens; retoma na sub-etapa pendente")
    s.add_argument("stage")
    s.set_defaults(func=h_load)
    s = sub.add_parser("check", help="roda o check de uma sub-etapa e marca feito/falhou")
    s.add_argument("substage")
    s.add_argument("--answer", default=None, help="resposta literal do usuário (ctx: user)")
    s.add_argument("--note", default=None, help="registro manual para item sem check")
    s.set_defaults(func=h_check)
    s = sub.add_parser("skip", help="pulo explícito de sub-etapa (caminho --fast), com motivo registrado")
    s.add_argument("substage")
    s.add_argument("--reason", required=True)
    s.set_defaults(func=h_skip)
    s = sub.add_parser("done", help="roda todos os checks; sucesso grava handoff e avança")
    s.add_argument("stage")
    s.set_defaults(func=h_done)
    return p
