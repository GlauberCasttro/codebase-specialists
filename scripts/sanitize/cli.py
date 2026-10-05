"""CLI de `cs.py sanitize [--apply|--check] [--json]` (approve.4)."""
import json
import sys

from cslib.errors import CsError


def _run(args):
    from sanitize import core
    if args.apply and args.check:
        raise CsError("--apply e --check são modos diferentes; use um",
                      "plano: `cs.py sanitize`; aplicar: `--apply`; check de approve.4: `--check`")
    if args.check:
        ok, problems, warnings = core.check(args.target)
        for w in warnings:
            print("aviso: " + w)
        for p in problems:
            sys.stderr.write("falta: %s\n" % p)
        print("sanitize --check: %s" % ("ok" if ok else "FALHOU — rode `cs.py sanitize --apply`"))
        return 0 if ok else 1
    rep = core.apply(args.target) if args.apply else core.plan(args.target)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for ln in core.render(rep):
            print(ln)
    return 0


def register(subparsers):
    p = subparsers.add_parser("sanitize", help="saneamento ao fim do init (approve.4): plano | --apply | --check")
    p.add_argument("--apply", action="store_true",
                   help="apaga tmp/ inteiro e todo __pycache__ da pasta da skill, grava .gitignore "
                        "(scripts deixados em tmp/ saem no relatório como DEFEITO antes de apagar)")
    p.add_argument("--check", action="store_true",
                   help="check de approve.4: tmp/ vazio, .gitignore completo, nenhum .git aninhado fora de tmp/")
    p.add_argument("--json", action="store_true", help="relatório em JSON (plano ou --apply)")
    p.set_defaults(func=_run)
