#!/usr/bin/env python3
"""cs.py harness <install|selftest|validate|status> — instala e verifica o harness no repositório-alvo.

Convenção da skill: register(subparsers) + executável direto (python3 scripts/harness/cli.py install --target X).
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(HERE, "engine"), os.path.join(os.path.dirname(HERE), "memory"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _target(args):
    t = getattr(args, "target", None) or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return os.path.realpath(t)


def cmd_install(args):
    import install
    import hcore
    try:
        res = install.install(_target(args), platforms=[p for p in (args.platforms or "").split(",") if p],
                              settings=not args.no_settings, makefile=not args.no_makefile, git_hook=args.git_hook,
                              path_env=args.path_env and not args.no_path_env, dry_run=args.dry_run,
                              allow_outside=args.allow_outside)
    except install.OutsideRefused as e:
        sys.stderr.write(install.render_outside(e.steps) + "\n")
        sys.stderr.write("nada foi instalado: %d escrita(s) FORA de .swarm/ exigem --allow-outside "
                         "(mostre a lista ao usuário antes; `--dry-run` só lista)\n" % len(e.steps))
        return 3
    except hcore.StateError as e:
        sys.stderr.write("harness install: %s\n" % e)
        return 2
    if res.get("dry_run"):
        print("plano (dry-run; nada escrito) em %s: %d escrita(s)" % (res["root"], len(res["changes"])))
        for c in res["changes"]:
            print("  " + c)
        print(install.render_outside(res["outside"]))
        return 0
    print("harness instalado em %s" % res["root"])
    for c in res["changes"] or ["(nada mudou — idempotente)"]:
        print("  " + c)
    print("próximo: cs.py harness selftest (gate G6)")
    return 0


def _installed_engine(root, name):
    """Selftest/validate usam o motor DA SKILL (lição: nunca um script do alvo), apontado ao alvo."""
    import importlib
    return importlib.import_module(name)


def cmd_selftest(args):
    selftest = _installed_engine(_target(args), "selftest")
    res = selftest.run(_target(args), drift=args.drift)
    for r in res["results"]:
        print("%s %s%s" % ("OK   " if r["ok"] else "FALHA", r["probe"], ("  — " + str(r.get("msg"))) if r.get("msg") and not r["ok"] else ""))
    print("G6 %s" % ("VERDE" if res["ok"] else "VERMELHO"))
    return 0 if res["ok"] else 1


def cmd_validate(args):
    import validate
    ok, errs, _ = validate.run(_target(args), strict=args.strict, allow_empty=args.allow_empty)
    print("validate: %s" % ("OK" if ok else "FALHOU"))
    for e in errs:
        print("  - " + e)
    return 0 if ok else 1


def cmd_status(args):
    import engine
    import hcore
    import views
    root = _target(args)
    print(views.status(engine.Ctx(root, hcore.load_board(root))))
    return 0


def register(subparsers):
    p = subparsers.add_parser("harness", help="instala/verifica o harness (estado, guards, hooks, memória)")
    sub = p.add_subparsers(dest="harness_cmd", metavar="<install|selftest|validate|status>")
    i = sub.add_parser("install", help="instala motor, hooks, wrappers, Makefile e estado no alvo")
    i.add_argument("--platforms", default="", help="adapters advisory: cursor,copilot,codex")
    i.add_argument("--no-settings", action="store_true")
    i.add_argument("--no-makefile", action="store_true")
    i.add_argument("--path-env", action="store_true",
                   help="grava env.PATH com .swarm/bin no settings.json (desligado por padrão)")
    i.add_argument("--no-path-env", action="store_true", help=argparse.SUPPRESS)  # compat: já é o padrão
    i.add_argument("--git-hook", action="store_true", help="liga .git/hooks/pre-commit → cs-precommit")
    i.add_argument("--dry-run", action="store_true",
                   help="só lista o que seria escrito, com o bloco `outside` (escritas fora de .swarm/)")
    i.add_argument("--allow-outside", action="store_true",
                   help="permite escrever fora de .swarm/ (.claude/, Makefile, specialists.mk, .git/hooks); "
                        "mostre a lista do --dry-run ao usuário antes")
    i.set_defaults(func=cmd_install)
    s = sub.add_parser("selftest", help="gate G6: sondas negativas contra os guards instalados")
    s.add_argument("--drift", action="store_true")
    s.set_defaults(func=cmd_selftest)
    v = sub.add_parser("validate")
    v.add_argument("--strict", action="store_true")
    v.add_argument("--allow-empty", action="store_true")
    v.set_defaults(func=cmd_validate)
    st = sub.add_parser("status")
    st.set_defaults(func=cmd_status)
    for sp in (i, s, v, st):
        if not any("--target" in a.option_strings for a in sp._actions):
            sp.add_argument("--target", default=argparse.SUPPRESS)
    p.set_defaults(func=lambda a: (p.print_help(sys.stderr), 2)[1])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="harness")
    ap.add_argument("--target", default=None)
    sub = ap.add_subparsers(dest="command")
    register(sub)
    a = ap.parse_args(["harness"] + list(argv if argv is not None else sys.argv[1:]))
    return int(a.func(a) or 0)


if __name__ == "__main__":
    sys.exit(main())
