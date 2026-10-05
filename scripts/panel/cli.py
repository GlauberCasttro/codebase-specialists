"""`cs.py panel ...` — mesa redonda estruturada (rt.1–rt.3).

  cs.py panel plan
  cs.py panel record <agente> --reviewer <revisor> --file objecoes.json5
  cs.py panel status [--all-reviewed]                    check: exit 0 ok · 1 falta · 2 entrada inválida
  cs.py panel consolidate [--check]
  cs.py panel why <agente> --probe <id> --verdict PASS|FAIL   (mérito de sonda POR-QUÊ → probes/panel/)
"""
import argparse
import sys

from cslib import CsError


def _team_err(fn):
    def run(args):
        from team._shared_tmp.common import CsError as TeamErr
        try:
            return fn(args)
        except TeamErr as exc:
            raise CsError(exc.message, exc.hint, exc.code)
    return run


def h_plan(args):
    from panel import core
    doc = core.plan(args.target)
    for a, v in sorted(doc["agents"].items()):
        print("%-24s ← %s" % (a, ", ".join("%s(%s)" % (r["name"], r["role"]) for r in v["reviewers"])))
    print("gravado: .swarm/panel/plan.json5")
    return 0


def h_record(args):
    from panel import core
    agent = args.card or args.agent
    if not agent or (args.card and args.agent and args.card != args.agent):
        raise CsError("informe o agente revisado (posicional ou --card)")
    args.agent = agent
    core.record(args.target, agent, args.reviewer, args.file, role=args.role)
    print("objeções de %s sobre %s gravadas" % (args.reviewer, args.agent))
    return 0


def h_pack(args):
    from panel import core
    out, n = core.pack(args.target, args.agent, args.role, args.out, reviewer=args.reviewer)
    print("pacote isolado de %s (%s): %d arquivo(s) do alvo sem .swarm/ → %s" % (args.agent, args.role, n, out))
    print("despache o revisor com `%s/repo` como raiz e card.json5/facts.json5 como dado" % out)
    return 0


def h_status(args):
    from panel import core
    missing, pl = core.review_status(args.target)
    total = sum(len(v["reviewers"]) for v in pl["agents"].values())
    for m in missing:
        sys.stderr.write("falta: %s\n" % m)
    print("painel: %d/%d revisões gravadas" % (total - len([m for m in missing if "←" in m]), total))
    return 1 if (args.all_reviewed and missing) else 0


def h_consolidate(args):
    from panel import core
    if args.check:
        probs = core.consolidate_check(args.target)
        if args.core:
            from team import roster
            probs += roster.core_check(args.target)
        for p in probs:
            sys.stderr.write("falta: %s\n" % p)
        print("panel consolidate --check: %s" % ("ok" if not probs else "FALHOU"))
        return 1 if probs else 0
    res, cands = core.consolidate(args.target)
    for a, r in sorted(res.items()):
        print("%-24s %s (%d confirmada(s), %d descartada(s))" % (a, r["verdict"], r["n_confirmed"], len(r["rejected"])))
    print("candidatas a core: %d → .swarm/panel/core-candidates.json5" % len(cands))
    return 0


def h_why(args):
    from panel import core
    core.why_verdict(args.target, args.agent, args.probe, args.verdict)
    print("mérito de %s: %s → .swarm/probes/panel/%s.json5" % (args.probe, args.verdict, args.agent))
    return 0


def register(subparsers):
    p = subparsers.add_parser("panel", help="mesa redonda: plan | record | status | consolidate | why")
    sub = p.add_subparsers(dest="panel_cmd", metavar="<plan|record|status|consolidate|why|pack>")
    sub.required = True
    s1 = sub.add_parser("plan", help="2 revisores adjacentes (deps.json5) + 1 cético por agente")
    s1.set_defaults(func=h_plan)
    s2 = sub.add_parser("record", help="grava objeções JSON5 de um revisor")
    s2.add_argument("agent", nargs="?")
    s2.add_argument("--card", default=None, help="agente revisado (alternativa ao posicional)")
    s2.add_argument("--reviewer", required=True)
    s2.add_argument("--role", default=None, help="cetico|adjacente (conferido contra o plano)")
    s2.add_argument("--file", "--from", dest="file", required=True,
                    help="JSON5 do revisor (schema do prompt rt.1 ou o interno); relativo ao alvo")
    s2.set_defaults(func=h_record)
    s3 = sub.add_parser("status", help="revisões gravadas × plano")
    s3.add_argument("--all-reviewed", action="store_true", help="check: falha se falta alguma revisão")
    s3.set_defaults(func=h_status)
    s4 = sub.add_parser("consolidate", help="confirma objeções mecanicamente; grava panel/<agente>.json5")
    s4.add_argument("--check", action="store_true", help="check: consolidado presente e fresco")
    s4.add_argument("--core", action="store_true",
                    help="com --check: exige também a promoção ao core registrada (`team core from-panel`)")
    s4.set_defaults(func=h_consolidate)
    s5 = sub.add_parser("why", help="mérito de sonda POR-QUÊ (formato lido por probes check)")
    s5.add_argument("agent")
    s5.add_argument("--probe", required=True)
    s5.add_argument("--verdict", required=True, choices=["PASS", "FAIL"])
    s5.set_defaults(func=h_why)
    s6 = sub.add_parser("pack", help="cópia isolada do alvo sem .swarm/ + cartão como dado (cético)")
    s6.add_argument("agent")
    s6.add_argument("--role", required=True, choices=["cetico", "adjacente"])
    s6.add_argument("--out", required=True, help="fora do alvo ou em <alvo>/.swarm/tmp/")
    s6.add_argument("--reviewer", default=None, help="adjacente: inclui o cartão do revisor")
    s6.set_defaults(func=h_pack)
    for sp_ in (s1, s2, s3, s4, s5, s6):
        sp_.add_argument("--target", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        sp_.set_defaults(func=_team_err(sp_.get_default("func")))
    return p
