"""`cs.py interview ...` — entrevista de lacunas (sub-etapa scan.6).

  cs.py interview ask --id Q-01 --question "..." [--context "o que o scan já achou"] [--scope <glob>]
  cs.py interview record --id Q-01 --answer "<resposta literal>" [--by <nome>] [--question "..."]
  cs.py interview record --id Q-01 --answer-unknown
  cs.py interview status [--no-pending] [--json]     check: exit 0 ok · 1 pendente · 2 entrada inválida
"""

import argparse
import sys

from cslib import json5io


def h_ask(args):
    from interview import core
    rec = core.ask(args.target, args.id, args.question, args.context, args.scope)
    left = core.BATCH_MAX - len(core.pending(args.target))
    sys.stdout.write("pergunta %s registrada (lote: cabem mais %d)\n" % (rec["id"], left))
    return 0


def h_record(args):
    from interview import core
    rec = core.record(args.target, args.id, answer=args.answer, unknown=args.answer_unknown, by=args.by,
                      question=args.question, context=args.context, scope=args.scope)
    sys.stdout.write("resposta de %s registrada%s → .swarm/interview.jsonl%s\n" % (
        rec["id"], " (unknown: lacuna declarada)" if rec["unknown"] else "",
        "" if rec["unknown"] else " e facts/interview.json5"))
    return 0


def h_status(args):
    from interview import core
    qs, ans = core.state(args.target)
    pend = core.pending(args.target)
    out = {"questions": len(qs), "answered": sum(1 for q in qs if q in ans),
           "unknown": sorted(q for q in qs if q in ans and ans[q][1].get("unknown")),
           "pending": [q["id"] for q in pend]}
    if args.json:
        sys.stdout.write(json5io.dumps(out, "cs.py interview status"))
    else:
        for q in pend:
            sys.stdout.write("pendente %s: %s\n" % (q["id"], q["question"]))
        sys.stdout.write("entrevista: %d pergunta(s), %d respondida(s) (%d unknown), %d pendente(s)\n"
                         % (out["questions"], out["answered"], len(out["unknown"]), len(pend)))
    if args.no_pending:
        if not qs:
            sys.stderr.write("falta: nenhuma pergunta registrada (registre as lacunas com `cs.py interview ask`)\n")
            return 1
        if pend:
            sys.stderr.write("falta: %d pergunta(s) sem resposta: %s\n" % (len(pend), ", ".join(out["pending"])))
            return 1
        probs = core.synced_problems(args.target)
        for p_ in probs:
            sys.stderr.write("falta: %s\n" % p_)
        if probs:
            return 1
    return 0


def h_sync(args):
    from interview import core
    facts = core.sync_facts(args.target)
    sys.stdout.write("fatos da entrevista regravados: %d conhecido(s), %d lacuna(s) gap.*\n"
                     % (len(facts), len(core.sync_gaps(args.target))))
    return 0


def register(subparsers):
    p = subparsers.add_parser("interview", help="entrevista de lacunas: ask | record | status")
    sub = p.add_subparsers(dest="interview_cmd", metavar="<ask|record|status>")
    sub.required = True
    a = sub.add_parser("ask", help="registra pergunta de lacuna (lote ≤8 pendentes)")
    a.add_argument("--id", required=True)
    a.add_argument("--question", required=True)
    a.add_argument("--context", default="")
    a.add_argument("--scope", action="append", default=[])
    a.set_defaults(func=h_ask)
    r = sub.add_parser("record", help="registra a resposta literal (ou --answer-unknown)")
    r.add_argument("--id", required=True)
    g = r.add_mutually_exclusive_group(required=True)
    g.add_argument("--answer", default=None)
    g.add_argument("--answer-unknown", action="store_true")
    r.add_argument("--by", default="founder")
    r.add_argument("--question", default=None, help="cria a pergunta se ainda não existe")
    r.add_argument("--context", default="")
    r.add_argument("--scope", action="append", default=[])
    r.set_defaults(func=h_record)
    s = sub.add_parser("status", help="perguntas, respostas e pendências")
    s.add_argument("--no-pending", action="store_true", help="check: falha se há pergunta sem resposta")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=h_status)
    y = sub.add_parser("sync", help="regrava facts/interview.json5 e facts/gaps.json5 a partir do log")
    y.set_defaults(func=h_sync)
    for sp in (a, r, s, y):
        sp.add_argument("--target", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    return p
