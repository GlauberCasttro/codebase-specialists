"""`cs.py facts ...` — conferência de fatos contra o código (sub-etapa scan.5).

  cs.py facts spotcheck --min N                                       check: exit 0 ok · 1 falta · 2 entrada inválida
  cs.py facts spotcheck record --fact <id> --verdict ok|wrong --note "<o que foi conferido>" [--by X]
  cs.py facts spotcheck pack --out <arq> [--n N] [--batch K/M]        pacote de entrada dos subagentes de scan.5
  cs.py facts interpret --id <id> --claim "..." --supports a,b --evidence arq:linha [--evidence ...]
                        [--corrects <id do fato errado>] [--scope <glob>] [--confidence high|medium|low]
"""

import argparse
import sys

from cslib import CsError


def h_spotcheck(args):
    from facts import spotcheck
    if getattr(args, "spot_cmd", None) == "pack":
        out, doc = spotcheck.write_pack(args.target, args.out, n=args.n, batch=args.batch)
        sys.stdout.write("pacote: %d fato(s)%s → %s\n" % (len(doc["facts"]), (" (lote %s)" % doc["batch"])
                                                          if doc["batch"] else "", out))
        sys.stdout.write("registre cada um: %s\n" % doc["record_cmd"])
        return 0
    if getattr(args, "spot_cmd", None) == "record":
        rec = spotcheck.record(args.target, args.fact, args.verdict, args.note, by=args.by)
        sys.stdout.write("registrado: %s %s%s\n" % (rec["verdict"], rec["fact"],
                                                   (" (correção: %s)" % ", ".join(rec["correction"]))
                                                   if rec.get("correction") else ""))
        return 0
    if args.min is None:
        raise CsError("informe --min N (check) ou use `facts spotcheck record ...`")
    if args.min < 1:
        raise CsError("--min deve ser ≥ 1")
    ok, lines, problems, n = spotcheck.status(args.target, args.min)
    for ln in lines:
        sys.stdout.write(ln + "\n")
    for p in problems:
        sys.stderr.write("falta: %s\n" % p)
    sys.stdout.write("spotcheck: %d fato(s) conferido(s) (mínimo %d) → %s\n" % (n, args.min, "ok" if ok else "FALHOU"))
    return 0 if ok else 1


def h_interpret(args):
    from facts import spotcheck
    sup = [s.strip() for s in ",".join(args.supports or []).split(",") if s.strip()]
    f = spotcheck.interpret(args.target, args.id, args.claim, sup, args.evidence or [], corrects=args.corrects,
                            scope=args.scope or [], confidence=args.confidence)
    sys.stdout.write("gravado: %s (llm_interpretation; supports %s) → .swarm/facts/interpretation.json5\n"
                     % (f["id"], ", ".join(f["supports"])))
    return 0


def h_check(args):
    from facts import freshness
    from scan.cli import parse_layers
    for ln in freshness.check(args.target, parse_layers(args.layers)):
        sys.stdout.write(ln + "\n")
    sys.stdout.write("facts check (%s): ok — fatos presentes, válidos e do código atual\n" % args.layers)
    return 0


def register(subparsers):
    p = subparsers.add_parser("facts", help="conferência de fatos contra o código e correções llm_interpretation")
    sub = p.add_subparsers(dest="facts_cmd", metavar="<spotcheck|interpret|check>")
    sub.required = True
    s = sub.add_parser("spotcheck", help="check: --min N; registro: spotcheck record ...")
    s.add_argument("--min", type=int, default=None, help="mínimo de fatos conferidos (check)")
    s.set_defaults(func=h_spotcheck)
    ss = s.add_subparsers(dest="spot_cmd", metavar="[record|pack]")
    r = ss.add_parser("record", help="registra a conferência de um fato")
    r.add_argument("--fact", required=True)
    r.add_argument("--verdict", required=True, choices=["ok", "wrong"])
    r.add_argument("--note", required=True)
    r.add_argument("--by", default="orquestrador")
    r.set_defaults(func=h_spotcheck)
    pk = ss.add_parser("pack", help="pacote de entrada (JSON5) com N fatos a conferir; --batch K/M divide em lotes")
    pk.add_argument("--out", required=True, help="arquivo JSON5 (em <alvo>/.swarm/tmp/ ou fora do alvo)")
    pk.add_argument("--n", type=int, default=10, help="fatos no pacote inteiro (default 10; scan.5 confere 5–10)")
    pk.add_argument("--batch", default=None, help="K/M: só o lote K de M (lotes disjuntos; união = pacote)")
    pk.set_defaults(func=h_spotcheck)
    i = sub.add_parser("interpret", help="grava fato llm_interpretation (ex.: correção de fato errado)")
    i.add_argument("--id", required=True)
    i.add_argument("--claim", required=True)
    i.add_argument("--supports", action="append", required=True, help="ids mecânicos (vírgula ou repetido)")
    i.add_argument("--evidence", action="append", required=True, help="arquivo[:linha] conferido no código")
    i.add_argument("--corrects", default=None)
    i.add_argument("--scope", action="append", default=[])
    i.add_argument("--confidence", default="medium", choices=["high", "medium", "low"])
    i.set_defaults(func=h_interpret)
    c = sub.add_parser("check", help="check de scan.1–4: camadas presentes, válidas e FRESCAS (código não mudou)")
    c.add_argument("--layers", required=True, help="ex.: L0,L1,L2,L3")
    c.set_defaults(func=h_check)
    for sp_ in (s, r, pk, i, c):
        sp_.add_argument("--target", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    return p
