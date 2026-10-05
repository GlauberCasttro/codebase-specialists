#!/usr/bin/env python3
"""cs.py — CLI única da skill codebase-specialists.

Uso: python3 cs.py [--target <repo>] <subcomando> [opções]

Cada pacote em scripts/<pkg>/ expõe `cli.py` com `register(subparsers)`; o registro chama
`parser.set_defaults(func=handler)` e o handler recebe `args` (com `args.target` já resolvido para
realpath) e devolve o exit code. Pacotes ausentes são ignorados.

Raiz do alvo: --target > $CLAUDE_PROJECT_DIR > cwd. Nunca o diretório deste script.
"""

import argparse
import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from cslib import CsError  # noqa: E402
from cslib import paths  # noqa: E402

PACKAGES = ("stage", "scan", "team", "probes", "emit", "harness", "memory")


def discover_packages():
    """Pacotes conhecidos primeiro (ordem fixa), depois qualquer outro scripts/<pkg>/cli.py."""
    extra = sorted(d for d in os.listdir(HERE)
                   if d not in PACKAGES and d != "cslib" and not d.startswith((".", "_"))
                   and os.path.isfile(os.path.join(HERE, d, "cli.py")))
    return list(PACKAGES) + extra


def build_parser():
    parser = argparse.ArgumentParser(prog="cs.py", description="codebase-specialists CLI")
    parser.add_argument("--target", default=None,
                        help="raiz do repositório-alvo (default: $CLAUDE_PROJECT_DIR ou cwd)")
    sub = parser.add_subparsers(dest="command", metavar="<subcomando>")
    loaded = []
    for pkg in discover_packages():
        if not os.path.isfile(os.path.join(HERE, pkg, "cli.py")):
            continue
        try:
            mod = importlib.import_module(pkg + ".cli")
        except ImportError as exc:
            sys.stderr.write("aviso: pacote %s ignorado (import falhou: %s)\n" % (pkg, exc))
            continue
        if not hasattr(mod, "register"):
            sys.stderr.write("aviso: %s/cli.py sem register(subparsers); ignorado\n" % pkg)
            continue
        mod.register(sub)
        loaded.append(pkg)
    # --target também aceito depois do subcomando (sem sobrescrever o global quando omitido).
    for sp in sub.choices.values():
        if not any("--target" in a.option_strings for a in sp._actions):
            sp.add_argument("--target", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    _add_replace_flags(sub)
    parser.set_defaults(_loaded=loaded)
    return parser


def _subparser(sub, *names):
    """Subparser aninhado por nome (ex.: ("harness", "install")) ou None."""
    sp = sub.choices.get(names[0]) if sub is not None else None
    for n in names[1:]:
        if sp is None:
            return None
        nested = [a for a in sp._actions if isinstance(a, argparse._SubParsersAction)]
        sp = nested[0].choices.get(n) if nested else None
    return sp


def _add_replace_flags(sub):
    """Harness único (SWARM-DIR-2/4): `init` e `harness install` ganham --replace-harness (e o init, --allow-outside,
    porque a substituição escreve fora de .swarm/)."""
    for names in (("init",), ("harness", "install")):
        sp = _subparser(sub, *names)
        if sp is None:
            continue
        opts = set(o for a in sp._actions for o in a.option_strings)
        if "--replace-harness" not in opts:
            sp.add_argument("--replace-harness", action="store_true",
                            help="substitui OUTRO harness detectado no alvo (backup fiel em "
                                 ".swarm/backups/harness-anterior/; exige --allow-outside)")
        if "--allow-outside" not in opts:
            sp.add_argument("--allow-outside", action="store_true",
                            help="autoriza escrita fora de .swarm/ (exigido por --replace-harness)")


def _harness_gate(args):
    """Porteiro do harness único antes de `init`/`harness install` que ESCREVEM. → None (siga) ou exit code."""
    cmd = getattr(args, "command", None)
    if cmd == "init":
        if getattr(args, "check", False) or getattr(args, "check_repo", False):
            return None
        kind = "init"
    elif cmd == "harness" and getattr(args, "harness_cmd", None) == "install":
        if getattr(args, "dry_run", False):
            return None
        kind = "install"
    else:
        return None
    from harness import replace
    return replace.gate(args.target, replace=getattr(args, "replace_harness", False),
                        allow_outside=getattr(args, "allow_outside", False), cmd=kind)


def _legacy_gate(args):
    """U-4: alvo ainda no diretório legado (paths.LEGACY_STATE_DIR com run.json5, sem `.swarm/run.json5`): os
    comandos do harness só operam em `.swarm/` e criariam a pasta nova do nada (resíduo que bloqueia o upgrade).
    Recusa sem escrever (exit 3), apontando `cs.py upgrade`. `harness install` fica com o porteiro do harness único
    (_harness_gate, que já recusa o legado desta skill apontando o upgrade). → None (siga) ou exit code."""
    if getattr(args, "command", None) != "harness" or getattr(args, "harness_cmd", None) == "install":
        return None
    t = args.target
    if not os.path.isfile(os.path.join(t, paths.LEGACY_STATE_DIR, "run.json5")) \
            or os.path.isfile(os.path.join(t, paths.STATE_DIR, "run.json5")):
        return None
    sys.stderr.write("cs.py harness %s recusado (nada escrito): o alvo ainda está no diretório legado %s/ e o "
                     "harness só opera em %s/\nrode `cs.py upgrade` (plano) e `cs.py upgrade --apply` para migrar "
                     "%s/ → %s/\n" % (getattr(args, "harness_cmd", None) or "", paths.LEGACY_STATE_DIR,
                                       paths.STATE_DIR, paths.LEGACY_STATE_DIR, paths.STATE_DIR))
    return 3


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None) or not hasattr(args, "func"):
        parser.print_help(sys.stderr)
        return 2
    try:
        args.target = paths.resolve_target(args.target)
        rc = _legacy_gate(args)
        if rc is None:
            rc = _harness_gate(args)
        if rc is not None:
            return rc
        return int(args.func(args) or 0)
    except CsError as exc:
        sys.stderr.write(exc.render() + "\n")
        return exc.code
    except KeyboardInterrupt:
        sys.stderr.write("interrompido\n")
        return 130


if __name__ == "__main__":
    sys.exit(main())
