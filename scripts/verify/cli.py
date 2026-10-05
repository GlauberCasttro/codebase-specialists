"""`cs.py verify` (G1–G16 → acceptance.json5) e `cs.py approve` (decisão do founder).

  cs.py verify [--control <team.json5 do repo de controle>] [--json]   exit 0 só com GO
  cs.py verify --recorded                                               check de validate.6 (não roda gates)
  cs.py approve --by <nome> --decision GO|NO-GO [--note "..."] [--simulated]
  cs.py approve --check [--recorded]                                     exit 0 · 1 falta · 2 entrada inválida
  cs.py report [--check]                                                 relatório → .swarm/report.md
"""
import argparse
import os
import sys

from cslib import CsError


def h_verify(args):
    from verify import gates
    if args.recorded:
        ok, msg = gates.recorded_check(args.target)
        (sys.stdout if ok else sys.stderr).write(("ok: " if ok else "falta: ") + msg + "\n")
        return 0 if ok else 1
    doc = gates.verify(args.target, control=args.control)
    if args.json:
        sys.stdout.write(gates.dumps(doc))
    else:
        for g in doc["gates"]:
            print("%-4s %-5s %s — %s" % (g["id"], "ok" if g["passed"] else "FALHA", g["name"], g["evidence"][:200]))
        print("enforcement: %s" % ", ".join("%s=%s" % kv for kv in sorted(doc["enforcement"].items())))
        print("decisão: %s → .swarm/acceptance.json5" % doc["decision"])
    return 0 if doc["decision"] == "GO" else 1


def h_approve(args):
    from verify import gates
    if args.check:
        ok, msg = gates.approve_check(args.target, recorded=args.recorded)
        (sys.stdout if ok else sys.stderr).write(("ok: " if ok else "falta: ") + msg + "\n")
        return 0 if ok else 1
    if args.recorded:
        raise CsError("--recorded só vale com --check")
    if not args.by or not args.decision:
        raise CsError("informe --by e --decision GO|NO-GO (ou --check)")
    rec, acc = gates.approve(args.target, args.by, args.decision, args.note, simulated=args.simulated)
    print("decisão %s%s de %s registrada sobre acceptance %s (sha %s) → .swarm/approvals.jsonl" % (
        rec["decision"], " (simulado)" if args.simulated else "", rec["by"], acc.get("decision"),
        rec["acceptance_sha256"][:12]))
    from verify import report
    if os.path.isfile(report.report_path(args.target)):
        report.write(args.target)
        print("relatório atualizado: .swarm/report.md")
    if rec["decision"] == "GO" and acc.get("decision") != "GO":
        sys.stderr.write("aviso: acceptance é %s — `approve --check` continuará falhando\n" % acc.get("decision"))
    return 0


def h_report(args):
    from verify import report
    if args.check:
        ok, msg = report.check(args.target)
        (sys.stdout if ok else sys.stderr).write(("ok: " if ok else "falta: ") + msg + "\n")
        return 0 if ok else 1
    text = report.write(args.target)
    sys.stdout.write(text)
    sys.stderr.write("gravado: .swarm/report.md\n")
    return 0


def register(subparsers):
    v = subparsers.add_parser("verify", help="roda G1–G16 e grava .swarm/acceptance.json5")
    v.add_argument("--control", default=None, help="team.json5 (ou repo) de controle para G3")
    v.add_argument("--json", action="store_true")
    v.add_argument("--recorded", action="store_true",
                   help="check de validate.6: verify já rodou sobre o estado atual (GO ou NO-GO); não roda os gates")
    v.set_defaults(func=h_verify)
    r = subparsers.add_parser("report", help="relatório final (decisão, time, garantias por plataforma, lacunas, pulos)")
    r.add_argument("--check", action="store_true", help="check de approve.1: report.md gerado sobre o acceptance atual")
    r.set_defaults(func=h_report)
    a = subparsers.add_parser("approve", help="decisão do founder sobre acceptance.json5 (ou --check)")
    a.add_argument("--by", default=None)
    a.add_argument("--decision", default=None, choices=["GO", "NO-GO"])
    a.add_argument("--note", default="")
    a.add_argument("--check", action="store_true")
    a.add_argument("--simulated", action="store_true",
                   help="sem humano (eval/CI): registra approval=simulated; o relatório mostra `GO (simulado)`")
    a.add_argument("--recorded", action="store_true",
                   help="com --check (approve.2): decisão GO|NO-GO registrada sobre o acceptance atual")
    a.set_defaults(func=h_approve)
    return v
