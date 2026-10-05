"""CLI de `cs.py probes ...`. Também executável direto: python3 scripts/probes/cli.py generate --target X."""
import argparse
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from team._shared_tmp.common import CsError, resolve_target  # noqa: E402


def _t(args):
    return resolve_target(getattr(args, "target", None))


def _generate(args):
    from probes.generate import generate, rotate
    if args.rotate or args.agent:
        if not (args.rotate and args.agent):
            raise CsError("--rotate e --agent andam juntos: `probes generate --rotate --agent <agente>`",
                          "refino troca só as sondas do agente reprovado; banco inteiro = sem flags")
        bank, probes, meta = rotate(_t(args), args.agent, seed=args.seed_explicit)
        print("%s: %d sondas NOVAS (%s; território=%d cross=%d negativas=%d) — os outros agentes ficaram intactos"
              % (args.agent, len(probes), probes[0]["id"].rsplit("-", 1)[0], meta["territory"], meta["cross"],
                 meta["negatives"]))
        print("próximo: baseline (`probes baseline-filter %s`) e exame isolado (`probes exam-pack %s --out <dir>`)"
              % (args.agent, args.agent))
        return 0
    bank = generate(_t(args), seed=args.seed_explicit or "cs-probes-v1")
    for name, m in sorted(bank["agents"].items()):
        print("%-22s território=%-2d cross=%-2d negativas=%d %s" % (
            name, m["territory"], m["cross"], m["negatives"], "; ".join(m["warnings"])))
    print("gravado: .swarm/probes/bank.json5 (%d sondas) — NUNCA mostre a agentes examinados"
          % len(bank["probes"]))
    return 0


def _pack(args):
    from probes.exam import exam_pack, exam_pack_isolated
    if args.out:
        qpath, pack, n = exam_pack_isolated(_t(args), args.agent, args.out)
        print(qpath)
        sys.stderr.write("exame isolado de %s: %d perguntas; repo = %s (%d arquivos, sem .swarm/); "
                         "respostas → %s\n" % (args.agent, len(pack["questions"]), pack["repo"], n,
                                                pack["answer_file"]))
        return 0
    path, pack = exam_pack(_t(args), args.agent)
    print("exame de %s: %d perguntas → %s" % (args.agent, len(pack["questions"]), path))
    return 0


def _check(args):
    if args.examined and not args.all:
        raise CsError("--examined só vale com --all")
    if args.all or args.final:
        return _check_all(args)
    if not args.agent:
        raise CsError("informe <agente> ou --all")
    if args.allow_non_specialist and args.closed:
        raise CsError("--allow-non-specialist não vale com --closed (modo fechado é só sinal)")
    if args.allow_non_specialist and not (args.reason or "").strip():
        raise CsError("--allow-non-specialist exige --reason \"<motivo>\" (fica registrado)")
    from probes.exam import check, closed_check
    from probes.final import record_cycle, answers_path, guard_stale
    from probes.generate import load_bank
    from team._shared_tmp.common import find_doc
    t = _t(args)
    if args.closed:
        rep = closed_check(t, args.agent, args.answers)
        print("%s modo fechado (só cartão, sem repo): score=%s alucinações=%d — SINAL, não entra no G4" % (
            args.agent, rep["score"], rep["hallucinations"]))
        return 0
    bank = load_bank(t)
    canon = answers_path(t, args.agent)
    src = args.answers or canon
    if not os.path.isfile(find_doc(src)) and not os.path.isabs(src):
        src = os.path.join(t, src)
    guard_stale(t, bank, args.agent, src)
    if os.path.realpath(find_doc(src)) != os.path.realpath(find_doc(canon)):
        import shutil  # exame isolado (<out>/answers.json5) → cópia canônica, lida por `check --all`
        os.makedirs(os.path.dirname(canon), exist_ok=True)
        shutil.copyfile(find_doc(src), canon)
        src = canon
    rep = check(t, args.agent, src)
    n = record_cycle(t, bank, args.agent, rep, src)
    print("%s: território=%s cross=%s alucinações=%d delta=%s → G4 %s%s" % (
        args.agent, rep["score_territory"], rep["score_cross"], rep["hallucinations"], rep["delta"],
        rep["decision"], " (provisório: painel pendente)" if rep["provisional"] else ""))
    if rep.get("baseline_saturated"):
        print("  baseline_saturated: true — %s sem sonda discriminante; score sem filtro (não medido ≠ reprovado)"
              % ", ".join(rep.get("baseline_saturated_scopes") or []))
    for r in rep["reasons"]:
        print("  - " + r)
    if args.allow_non_specialist and rep["decision"] != "PASS":
        from probes.final import allow_agent
        allow_agent(t, bank, args.agent, args.reason, n)
        print("%s aceito como nao-especialista (registrado; com nao-especialista o verify decide NO-GO)" % args.agent)
        return 0
    return 0 if rep["decision"] == "PASS" else 1


def _check_all(args):
    from probes.final import check_all
    if args.agent:
        raise CsError("--all não aceita <agente>")
    if args.allow_non_specialist and not args.final:
        raise CsError("--allow-non-specialist com --all só vale com --final (ou por agente: "
                      "`probes check <agente> --allow-non-specialist --reason ...`)")
    if args.allow_non_specialist and not (args.reason or "").strip():
        raise CsError("--allow-non-specialist exige --reason \"<motivo>\" (fica registrado)")
    if args.examined and args.final:
        raise CsError("--examined (validate.3) e --final (validate.4) são checks diferentes; use um")
    ok, lines, problems, summ = check_all(_t(args), final=args.final,
                                          allow_reason=args.reason if args.allow_non_specialist else None,
                                          examined=args.examined)
    for ln in lines:
        print(ln)
    for p in problems:
        sys.stderr.write("falta: %s\n" % p)
    if args.final and summ.get("non_specialist"):
        print("nao-especialista: %s%s" % (", ".join(summ["non_specialist"]),
                                          (" (aceito: %s)" % summ["allowed"]["reason"]) if summ.get("allowed") else ""))
    print("probes check --all%s: %s" % (" --final" if args.final else " --examined" if args.examined else "",
                                        "ok" if ok else "FALHOU"))
    return 0 if ok else 1


def _anticola(args):
    from probes.anticola import run_anticola
    rep = run_anticola(_t(args), extra_paths=args.cards)
    for v in rep["violations"]:
        print("VIOLAÇÃO %s: %s (%s) em %s" % (v["agent"], v["probe"], v["kind"], v["where"]))
    for w in rep["warnings"]:
        print("aviso %s: %s — %s" % (w["agent"], w["fact_id"], w["why"]))
    print("anticola: %s" % ("PASS" if rep["pass"] else "FAIL"))
    return 0 if rep["pass"] else 1


def _baseline(args):
    if args.check:
        from probes.final import baseline_check
        ok, problems = baseline_check(_t(args))
        for p in problems:
            sys.stderr.write("falta: %s\n" % p)
        print("baseline-filter --check: %s" % ("ok" if ok else "FALHOU"))
        return 0 if ok else 1
    if not args.agent:
        raise CsError("informe <agente> (ou --check)")
    from probes.exam import baseline_filter
    b = baseline_filter(_t(args), args.agent, args.answers)
    print("baseline %s: score=%s, %d sonda(s) não discriminativa(s) excluída(s) do score" % (
        args.agent, b["score"], b["non_discriminative"]))
    return 0


def _existence(args):
    from probes.existence import run_existence, feed_problems
    rep = run_existence(_t(args))
    for name, r in sorted(rep["agents"].items()):
        for m in r["missing"]:
            print("%s: %s `%s` em %s — %s" % (name, m["type"], m["value"], m["where"], m["why"]))
    print("Existence Ratio = %s (%d/%d) → G2 %s" % (rep["ratio"], rep["existing"], rep["cited"],
                                                   "PASS" if rep["pass"] else "FAIL"))
    if args.feed and not rep["pass"]:
        probs = feed_problems(_t(args), rep)
        for p_ in probs:
            sys.stderr.write("falta: %s\n" % p_)
        print("existence --feed: %s" % ("faltas medidas e entregues ao autor (somem até rt.4)" if not probs
                                         else "FALHOU"))
        return 1 if probs else 0
    return 0 if rep["pass"] else 1


def _antitemplate(args):
    from probes.antitemplate import run_antitemplate
    rep = run_antitemplate(_t(args), args.control, args.threshold)
    for name, r in sorted(rep["agents"].items()):
        print("%-22s sim=%s (linhas=%s shingles=%s vs %s) %s" % (
            name, r.get("similarity"), r.get("line_jaccard"), r.get("shingle_jaccard"), r.get("control_agent"),
            "ok" if r["pass"] else "TEMPLATE"))
    print("anti-template (≤%s): %s" % (rep["threshold"], "PASS" if rep["pass"] else "FAIL"))
    return 0 if rep["pass"] else 1


def _memory(args):
    from probes.memory_recall import memory_recall
    rep = memory_recall(_t(args), args.mem)
    for m in rep["misses"]:
        print("miss %s: esperado %s" % (m["id"], m["expected"]))
    print("recall@5=%s p95=%sms (parede %sms) → G8 %s" % (rep["recall_at_5"], rep["latency_p95_ms"],
                                                       rep["wall_p95_ms"], "PASS" if rep["pass"] else "FAIL"))
    return 0 if rep["pass"] else 1


def register(subparsers):
    p = subparsers.add_parser("probes", help="sonda de maestria e gates G2/G3/G4/G8")
    sub = p.add_subparsers(dest="probes_cmd")
    sub.required = True

    def mk(name, fn, hlp, agent=False):
        s = sub.add_parser(name, help=hlp)
        s.add_argument("--target", "--root", dest="target", default=argparse.SUPPRESS)
        if agent:
            s.add_argument("agent")
        s.set_defaults(func=fn)
        return s
    g = mk("generate", _generate, "gera probes/bank.json5 a partir dos fatos")
    g.add_argument("--seed", dest="seed_explicit", default=None, help="semente (default cs-probes-v1; rotação: <semente>-rN)")
    g.add_argument("--rotate", action="store_true", help="refino: troca só as sondas de --agent por sondas novas")
    g.add_argument("--agent", default=None)
    ep = mk("exam-pack", _pack, "pacote do exame SEM respostas (--out: cópia isolada do alvo sem .swarm/)",
            agent=True)
    ep.add_argument("--out", default=None, help="<alvo>/.swarm/tmp/exam/<agente> ou diretório fora do alvo: "
                                            "<out>/repo/ (clone local com histórico, sem .swarm/) + "
                                            "<out>/questions.json5")
    c = mk("check", _check, "pontua respostas e decide G4 (<agente> ou --all [--final])")
    c.add_argument("agent", nargs="?", default=None)
    c.add_argument("--answers", default=None)
    c.add_argument("--all", action="store_true", help="todos os agentes do banco")
    c.add_argument("--final", action="store_true", help="aplica a regra de 2 refinos (nao-especialista)")
    c.add_argument("--allow-non-specialist", action="store_true",
                   help="aceita o(s) nao-especialista(s) sem refino possível — ciclos esgotados, validate.4 pulado "
                        "(--fast) ou rotação esgotada; por agente ou com --all --final (exige --reason; registrado)")
    c.add_argument("--reason", default=None)
    c.add_argument("--closed", action="store_true",
                   help="pontua o exame em MODO FECHADO (só cartão, sem repo): sinal em report.json5 closed_mode, fora do G4")
    c.add_argument("--examined", action="store_true",
                   help="com --all: check de validate.3 — todo agente examinado nas sondas atuais (reprovado vai ao refino)")
    a = mk("anticola", _anticola, "resposta canônica literal em team.json5/cartões reprova")
    a.add_argument("--cards", action="append", default=[], help="arquivo/diretório de cartões emitidos")
    b = mk("baseline-filter", _baseline, "marca sondas acertadas pelo baseline sem cartão (<agente> | --check)")
    b.add_argument("agent", nargs="?", default=None)
    b.add_argument("--answers", default=None)
    b.add_argument("--check", action="store_true", help="check: todo agente com baseline e sondas classificadas")
    ex = mk("existence", _existence, "Existence Ratio (G2)")
    ex.add_argument("--feed", action="store_true",
                    help="check de rt.2: antes da revisão do autor, falta medida e entregue ao autor (consolidado) "
                         "basta; depois de rt.4 vale o G2 (ratio 1,0)")
    t = mk("antitemplate", _antitemplate, "similaridade com cartões do repo de controle (G3)")
    t.add_argument("--control", default=None,
                   help="team.json5, repo ou dir de cartões .md (default: evals/reference/generic-cards da skill)")
    t.add_argument("--threshold", type=float, default=0.35)
    m = mk("memory-recall", _memory, "recall@5 e p95 da busca de memória (G8)")
    m.add_argument("--mem", default=None)
    for sp_ in sub.choices.values():
        fn = sp_.get_default("func")
        sp_.set_defaults(func=_wrap(fn))
    return p


def _wrap(fn):
    def run(args):
        try:
            return fn(args)
        except CsError as exc:
            sys.stderr.write(exc.render() + "\n")
            return exc.code
    return run


def main(argv=None):
    ap = argparse.ArgumentParser(prog="probes")
    sub = ap.add_subparsers(dest="cmd")
    sub.required = True
    register(sub)
    args = ap.parse_args(["probes"] + list(sys.argv[1:] if argv is None else argv))
    try:
        return args.func(args)
    except CsError as exc:
        sys.stderr.write(exc.render() + "\n")
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
