"""`cs.py panel ...` — mesa redonda estruturada (rt.1–rt.3).

  cs.py panel plan
  cs.py panel record <agente> --reviewer <revisor> --file objecoes.json5
  cs.py panel status [--all-reviewed]                    check: exit 0 ok · 1 falta · 2 entrada inválida
  cs.py panel consolidate [--check]
  cs.py panel why <agente> --probe <id> --verdict PASS|FAIL   (mérito de sonda POR-QUÊ → probes/panel/)
  cs.py panel why pack <agente> --out <dir>                   (pacote dos 3 juízes POR-QUÊ: <dir>/pack.json5)
  cs.py panel why tally <agente> --from <dir>                 (maioria de <dir>/j*.json5 → probes/panel/)
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
    if not getattr(args, "probe", None) or not getattr(args, "verdict", None):
        raise CsError("`panel why <agente>` exige --probe <id> e --verdict PASS|FAIL",
                      "ou use `panel why pack <agente> --out <dir>` / `panel why tally <agente> --from <dir>`")
    core.why_verdict(args.target, args.agent, args.probe, args.verdict)
    print("mérito de %s: %s → .swarm/probes/panel/%s.json5" % (args.probe, args.verdict, args.agent))
    return 0


def h_why_pack(args):
    from panel import core
    out, doc = core.why_pack(args.target, args.agent, args.out)
    print("pacote dos juízes POR-QUÊ de %s: %d sonda(s) → %s/pack.json5" % (args.agent, len(doc["items"]), out))
    print("despache %d juízes (cada um grava %s/j<N>.json5); depois: %s" % (doc["judges"], out, doc["tally_cmd"]))
    return 0


def h_why_tally(args):
    from panel import core
    res, n = core.why_tally(args.target, args.agent, args.src)
    for pid, (v, n_pass, tot) in sorted(res.items()):
        print("%-24s %s (%d/%d PASS)" % (pid, v, n_pass, tot))
    print("maioria de %d juízes → .swarm/probes/panel/%s.json5; depois: cs.py probes check %s"
          % (n, args.agent, args.agent))
    return 0


class _AnyChoice(object):
    """`choices` do subcomando `why` que aceita qualquer 1º argumento (o nome do agente da forma antiga); lista
    os subcomandos reais em mensagens/ajuda. A resolução é feita por `_WhyAction` no mapa verdadeiro."""

    def __init__(self, names):
        self._names = names

    def __contains__(self, key):
        return True

    def __iter__(self):
        return iter(self._names)

    def __len__(self):
        return len(self._names)


class _WhyAction(argparse._SubParsersAction):
    """`panel why <pack|tally> ...` ou, para qualquer outro 1º argumento, a forma antiga
    `panel why <agente> --probe <id> --verdict PASS|FAIL` (vira o subcomando `verdict`)."""

    def __init__(self, *args, **kwargs):
        super(_WhyAction, self).__init__(*args, **kwargs)
        self.choices = _AnyChoice(self._name_parser_map)

    def __call__(self, parser, namespace, values, option_string=None):
        if values and values[0] not in self._name_parser_map:
            values = ["verdict"] + list(values)
        return super(_WhyAction, self).__call__(parser, namespace, values, option_string)


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
    s5 = sub.add_parser("why", help="mérito de sonda POR-QUÊ: <agente> --probe --verdict | pack | tally",
                        description="cs.py panel why <agente> --probe <id> --verdict PASS|FAIL  (um veredito)\n"
                                    "cs.py panel why pack <agente> --out <dir>   (pacote dos 3 juízes)\n"
                                    "cs.py panel why tally <agente> --from <dir> (maioria → probes/panel/)",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    s5.register("action", "why_parsers", _WhyAction)
    wsub = s5.add_subparsers(dest="why_cmd", metavar="<agente|pack|tally>", action="why_parsers")
    wsub.required = True
    w0 = wsub.add_parser("verdict", help="(forma antiga, sem a palavra `verdict`) um veredito de juiz")
    w0.add_argument("agent")
    # --probe/--verdict valem nos dois níveis (`why <a> --probe ..` e `why --probe .. <a>`); h_why exige os dois
    for sp_ in (s5, w0):
        sp_.add_argument("--probe", default=argparse.SUPPRESS, help="id da sonda (forma `panel why <agente>`)")
        sp_.add_argument("--verdict", default=argparse.SUPPRESS, choices=["PASS", "FAIL"])
    w0.set_defaults(func=h_why)
    w1 = wsub.add_parser("pack", help="pacote dos juízes: sondas why do agente + resposta do exame + gabarito_fonte")
    w1.add_argument("agent")
    w1.add_argument("--out", required=True, help="diretório (em <alvo>/.swarm/tmp/ ou fora do alvo)")
    w1.set_defaults(func=h_why_pack)
    w2 = wsub.add_parser("tally", help="maioria dos juízes (<dir>/j*.json5, ≥3 e ímpar) → probes/panel/<agente>.json5")
    w2.add_argument("agent")
    w2.add_argument("--from", dest="src", required=True, help="diretório do `panel why pack` com os j*.json5")
    w2.set_defaults(func=h_why_tally)
    s6 = sub.add_parser("pack", help="cópia isolada do alvo sem .swarm/ + cartão como dado (cético)")
    s6.add_argument("agent")
    s6.add_argument("--role", required=True, choices=["cetico", "adjacente"])
    s6.add_argument("--out", required=True, help="fora do alvo ou em <alvo>/.swarm/tmp/")
    s6.add_argument("--reviewer", default=None, help="adjacente: inclui o cartão do revisor")
    s6.set_defaults(func=h_pack)
    s5.add_argument("--target", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    for sp_ in (s1, s2, s3, s4, s6, w0, w1, w2):
        sp_.add_argument("--target", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        sp_.set_defaults(func=_team_err(sp_.get_default("func")))
    return p
