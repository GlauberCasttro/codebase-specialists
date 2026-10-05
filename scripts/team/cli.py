"""CLI de `cs.py team ...`. Também executável direto: python3 scripts/team/cli.py derive --target X."""
import argparse
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from team._shared_tmp.common import CsError, resolve_target  # noqa: E402


def _derive(args):
    from team.derive import derive
    target = resolve_target(getattr(args, "target", None))
    team, deriv = derive(target, force=args.force)
    for a in team["agents"]:
        print("%-22s %-8s %s" % (a["name"], a["kind"], ", ".join(a["territory"]) or "(sem escrita)"))
    warns = [d for d in deriv["decisions"] if d["level"] == "warn"]
    for w in warns:
        print("aviso: %s — %s" % (w["decision"], w["why"]))
    print("gravado: .swarm/team.json5 e .swarm/team-derivation.json5")
    return 0


def _validate(args):
    from team.validate import validate
    from team._shared_tmp.common import find_doc, sp_path
    target = resolve_target(getattr(args, "target", None))
    if args.stage == "derive" and not os.path.isfile(find_doc(sp_path(target, "team-derivation.json5"))):
        sys.stderr.write("falta: team-derivation.json5 ausente — o roster não veio de `cs.py team derive` "
                         "(specialize.1 deriva dos fatos; não escreva team.json5 à mão)\n")
        return 1
    out = validate(target, stage=args.stage)
    for k in sorted(out["rules"], key=int):
        r = out["rules"][k]
        print("regra %s: %s" % (k, r["status"]))
        for e in r["errors"][:20]:
            print("  - " + e)
        for w in r["warnings"][:10]:
            print("  ~ " + w)
    print("team validate (%s): %s" % (out["stage"], "PASS" if out["pass"] else "FAIL"))
    return 0 if out["pass"] else 1


def _maps(args):
    from team.maps import build_maps
    target = resolve_target(getattr(args, "target", None))
    deps, col = build_maps(target, threshold=args.threshold)
    print("deps: %d territórios, %d arestas entre territórios, %d ciclo(s) entre territórios" % (
        len(deps["territories"]), deps["edges_cross_territory"], len(deps["cycles"]["territory"])))
    for c in deps["cycles"]["territory"]:
        print("  ciclo: " + " → ".join(c["path"]))
    for d in col["do_not_parallelize"]:
        print("não paralelizar %s × %s (risco %.2f): %s" % (d["pair"][0], d["pair"][1], d["risk"], d["why"]))
    print("gravado: .swarm/knowledge/deps.json5 e collision.json5")
    return 0


def _approve(args):
    from team.cards import approve
    rec = approve(resolve_target(getattr(args, "target", None)), args.by, args.note,
                  simulated=getattr(args, "simulated", False))
    print("roster aprovado%s por %s (%d agentes; sha %s) → .swarm/team-approvals.jsonl" % (
        " (simulado)" if rec.get("approval") == "simulated" else "", rec["by"], len(rec["agents"]),
        rec["roster_sha256"][:12]))
    return 0


def _approved(args):
    from team.cards import approved
    ok, msg = approved(resolve_target(getattr(args, "target", None)))
    (sys.stdout if ok else sys.stderr).write(("ok: " if ok else "falta: ") + msg + "\n")
    return 0 if ok else 1


def _card_set(args):
    from team.cards import card_set
    st = card_set(resolve_target(getattr(args, "target", None)), args.agent, args.file, by=args.by,
                  force=args.force)
    d = st.get("drafted") or {}
    print("cartão de %s gravado em team.json5 (redigido; rascunho %s%s)" % (
        args.agent, (d.get("file_sha256") or "?")[:12], (", delegação %s" % d["draft_id"]) if d.get("draft_id") else ""))
    return 0


def _facts(args):
    from team.roster import agent_facts
    t = resolve_target(getattr(args, "target", None))
    doc, path = agent_facts(t, args.agent, args.out)
    (sys.stdout if path else sys.stderr).write("%s: %d fato(s) (território %s; reads %s) → %s\n" % (
        args.agent, len(doc["facts"]), ", ".join(doc["territory"]) or "-", ", ".join(doc["reads"]) or "-",
        path or "(stdout)"))
    return 0


def _card_revise(args):
    from team.cards import card_revise
    s = card_revise(resolve_target(getattr(args, "target", None)), args.agent, args.file, args.note)
    last = s.get("last") or s["revised"]
    kind = "conserto de existência" if last.get("existence_fix") else (
        "refino ciclo %s" % last["cycle"] if last.get("cycle") else "mesa redonda")
    print("revisão de %s registrada [%s] (%s)" % (args.agent, kind, "cartão alterado" if last["changed"]
                                                  else "sem mudança: " + last["note"]))
    return 0


def _card_status(args):
    from team.cards import card_status
    rows = card_status(resolve_target(getattr(args, "target", None)))
    key = "problems_revised" if args.all_revised else "problems_drafted"
    bad = []
    for r in rows:
        probs = r[key] if (args.all_revised or args.all_drafted) else r["problems_revised"]
        state = "revisado" if r["revised"] else ("redigido" if r["drafted"] else "pendente")
        print("%-24s %-9s %s" % (r["agent"], state, "; ".join(probs)))
        if r[key]:
            bad.append(r["agent"])
    if not rows:
        sys.stderr.write("falta: team.json5 sem agentes\n")
        return 1
    if (args.all_drafted or args.all_revised) and bad:
        sys.stderr.write("falta: %d agente(s) sem cartão %s: %s\n" % (
            len(bad), "revisado" if args.all_revised else "redigido", ", ".join(bad)))
        return 1
    return 0


def _roster(args):
    from team import roster as R
    t = resolve_target(getattr(args, "target", None))
    c = args.roster_cmd
    if c == "move":
        files = R.move(t, args.glob, args.to)
        print("%d arquivo(s) de %s → %s" % (len(files), args.glob, args.to))
    elif c == "rename":
        R.rename(t, args.old, args.new)
        print("%s → %s" % (args.old, args.new))
    elif c == "add":
        ag = R.add(t, args.name, args.kind, args.territory or [], reads=args.reads, tools=None)
        print("agente %s (%s) adicionado" % (ag["name"], ag["kind"]))
    elif c == "remove":
        moved = R.remove(t, args.name, args.to)
        print("%s removido%s" % (args.name, (" (%d arquivo(s) → %s)" % (len(moved), args.to)) if args.to else ""))
    elif c == "set":
        team = R.set_roster(t, args.file)
        print("roster gravado (%d agentes)" % len(team["agents"]))
    from team.cards import load_team
    for a in load_team(t)["agents"]:
        print("  %-22s %-8s %s" % (a["name"], a["kind"], ", ".join(a.get("territory") or []) or "(sem escrita)"))
    print("revalidado (regras 1–4, 8); aprovação INVALIDADA → `cs.py team approve --by <nome>`")
    return 0


def _core(args):
    from team import roster as R
    t = resolve_target(getattr(args, "target", None))
    if args.core_cmd == "set":
        lines = R.core_set(t, args.file)
        print("core.lines gravado: %d linha(s)" % len(lines))
    else:
        lines, dropped, used_panel, refused = R.core_from_panel(t)
        print("core.lines gravado: %d linha(s) (%s)" % (
            len(lines), "painel + s0_core" if used_panel else "sem painel consolidado: só s0_core dos cartões"))
        for d in refused:
            print("  recusada: %s — %s" % (d["text"][:100], d["why"]))
        print("registro: .swarm/panel/core-promotion.json5")
    return 0


def _wrap(fn):
    def run(args):
        try:
            return fn(args)
        except CsError as exc:
            sys.stderr.write(exc.render() + "\n")
            return exc.code
    return run


def register(subparsers):
    p = subparsers.add_parser("team", help="deriva e valida o roster (.swarm/team.json5)")
    sub = p.add_subparsers(dest="team_cmd")
    sub.required = True
    d = sub.add_parser("derive", help="propõe o roster a partir dos fatos")
    d.add_argument("--target", "--root", dest="target", default=argparse.SUPPRESS)
    d.add_argument("--force", action="store_true", help="sobrescreve team.json5 com cartões")
    d.set_defaults(func=_derive)
    v = sub.add_parser("validate", help="aplica as 8 regras do team-schema.md")
    v.add_argument("--target", "--root", dest="target", default=argparse.SUPPRESS)
    v.add_argument("--stage", choices=["auto", "derive", "final"], default="auto")
    v.set_defaults(func=_validate)
    m = sub.add_parser("maps", help="deps.json5 (matriz/ciclos) e collision.json5 (não paralelizar)")
    m.add_argument("--target", "--root", dest="target", default=argparse.SUPPRESS)
    m.add_argument("--threshold", type=float, default=0.30)
    m.set_defaults(func=_maps)
    ap_ = sub.add_parser("approve", help="grava a aprovação do roster atual (sha256)")
    ap_.add_argument("--by", required=True)
    ap_.add_argument("--note", default="")
    ap_.add_argument("--simulated", action="store_true",
                     help="sem humano (eval/CI): registra approval=simulated (como `cs.py approve --simulated`)")
    ap_.set_defaults(func=_approve)
    ad = sub.add_parser("approved", help="check: aprovação gravada e roster inalterado desde então")
    ad.set_defaults(func=_approved)
    cd = sub.add_parser("card", help="grava/revisa cartão devolvido por subagente")
    csub = cd.add_subparsers(dest="card_cmd", metavar="<set|revise>")
    csub.required = True
    cs_ = csub.add_parser("set", help="valida o cartão contra o schema e grava em team.json5")
    cs_.add_argument("agent")
    cs_.add_argument("--file", "--from", dest="file", required=True,
                     help="saída do subagente ({card, camadas, ...}) ou só o card; relativo ao alvo")
    cs_.add_argument("--by", default="subagente")
    cs_.add_argument("--force", action="store_true", help="grava mesmo rascunho mais velho que o registrado")
    cs_.set_defaults(func=_card_set)
    cr = csub.add_parser("revise", help="marca a revisão única do autor após o painel")
    cr.add_argument("agent")
    cr.add_argument("--file", "--from", dest="file", default=None)
    cr.add_argument("--note", default="")
    cr.set_defaults(func=_card_revise)
    fa = sub.add_parser("facts", help="fatos de um agente calculados NA LEITURA (território + reads + citados)")
    fa.add_argument("agent")
    fa.add_argument("--out", default=None, help="grava o pacote (JSON5) neste caminho (em .swarm/tmp/)")
    fa.add_argument("--target", "--root", dest="target", default=argparse.SUPPRESS)
    fa.set_defaults(func=_facts)
    st = sub.add_parser("card-status", help="estado dos cartões; check com --all-drafted|--all-revised")
    g = st.add_mutually_exclusive_group()
    g.add_argument("--all-drafted", action="store_true")
    g.add_argument("--all-revised", action="store_true")
    st.set_defaults(func=_card_status)
    ro = sub.add_parser("roster", help="ajusta o roster (revalida e invalida a aprovação)")
    rsub = ro.add_subparsers(dest="roster_cmd", metavar="<move|rename|add|remove|set>")
    rsub.required = True
    r1 = rsub.add_parser("move", help="move os arquivos de um glob para o território de um agente")
    r1.add_argument("glob")
    r1.add_argument("--to", required=True)
    r2 = rsub.add_parser("rename", help="renomeia um agente")
    r2.add_argument("old")
    r2.add_argument("new")
    r3 = rsub.add_parser("add", help="cria agente (território tirado de quem tinha os arquivos)")
    r3.add_argument("name")
    r3.add_argument("--kind", required=True, choices=["dev", "gate", "design", "product", "ops"])
    r3.add_argument("--territory", nargs="*", default=[])
    r3.add_argument("--reads", nargs="*", default=None)
    r4 = rsub.add_parser("remove", help="remove agente (--to herda o território)")
    r4.add_argument("name")
    r4.add_argument("--to", default=None)
    r5 = rsub.add_parser("set", help="substitui o roster inteiro por um JSON5 {agents:[{name,kind,territory,reads}]}")
    r5.add_argument("--file", "--from", dest="file", required=True)
    co = sub.add_parser("core", help="grava core.lines (S0): set --file | from-panel")
    csub2 = co.add_subparsers(dest="core_cmd", metavar="<set|from-panel>")
    csub2.required = True
    c1 = csub2.add_parser("set", help="grava core.lines de um JSON5 {lines:[{text, facts}]} (≤40)")
    c1.add_argument("--file", "--from", dest="file", required=True)
    c2 = csub2.add_parser("from-panel", help="core = atual + candidatas do painel + camadas.s0_core dos cartões")
    roster_parsers = [r1, r2, r3, r4, r5]
    for sp_ in roster_parsers:
        sp_.set_defaults(func=_roster)
    for sp_ in (c1, c2):
        sp_.set_defaults(func=_core)
    for sp_ in roster_parsers + [c1, c2]:
        sp_.add_argument("--target", "--root", dest="target", default=argparse.SUPPRESS)
        sp_.set_defaults(func=_wrap(sp_.get_default("func")))
    for sp_ in (ap_, ad, cs_, cr, st):
        sp_.add_argument("--target", "--root", dest="target", default=argparse.SUPPRESS)
    for sp_ in list(sub.choices.values()) + [cs_, cr]:
        fn = sp_.get_default("func")
        if fn is not None:
            sp_.set_defaults(func=_wrap(fn))
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(prog="team")
    sub = ap.add_subparsers(dest="cmd")
    sub.required = True
    register(sub)
    args = ap.parse_args(["team"] + list(sys.argv[1:] if argv is None else argv))
    try:
        return args.func(args)
    except CsError as exc:
        sys.stderr.write(exc.render() + "\n")
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
