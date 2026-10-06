#!/usr/bin/env python3
"""cs.py emit — gera os artefatos nativos por plataforma a partir de .swarm/team.json5.

    cs.py emit [--platforms claude-code,cursor,copilot,codex] [--dry-run] [--diff] [--force] [--allow-outside]
    cs.py emit validate [--platforms ...] [--json]        # gate G7
    cs.py emit budget [--platforms ...] [--json]          # orçamento por camada (specialize.4); não escreve

Executável direto: python3 scripts/emit/cli.py [validate] --target <repo> ...
Exit: 0 ok · 1 validação falhou · 2 entrada inválida/orçamento estourado · 3 conflito com conteúdo humano
      ou escrita fora de .swarm/ sem --allow-outside (o plano lista o bloco `outside`).
"""
import argparse
import json
import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from emit import apply as A  # noqa: E402
from emit import guide, knowledge, platforms as P, render, validate as V  # noqa: E402
from emit.common import ALL_PLATFORMS, EmitError  # noqa: E402
from cslib.paths import STATE_DIR  # noqa: E402
from emit.team import load_team, resolve_invariants  # noqa: E402


def _run_platforms(root):
    """Plataformas escolhidas no init (run.json5) — fonte da verdade quando existem (iteração 3: team.json5
    derivado antes de um `init --platforms` ficava com a lista velha e o validate conferia só ela)."""
    if not root:
        return None
    p = os.path.join(root, STATE_DIR, "run.json5")
    if not os.path.isfile(p):
        return None
    try:
        from emit import j5 as _j5
        return list(_j5.load(p).get("platforms") or []) or None
    except (ValueError, OSError):
        return None


def _platforms(arg, team=None, root=None):
    run_plats = _run_platforms(root)
    if arg:
        plats = [p.strip() for p in arg.split(",") if p.strip()]
    elif run_plats:
        plats = run_plats
    elif team and team.get("platforms"):
        plats = list(team["platforms"])
    else:
        plats = list(ALL_PLATFORMS)
    bad = [p for p in plats if p not in ALL_PLATFORMS]
    if bad:
        raise EmitError("plataforma desconhecida: %s (válidas: %s)" % (bad, ", ".join(ALL_PLATFORMS)))
    return [p for p in ALL_PLATFORMS if p in plats]  # ordem canônica


def _root(args):
    root = getattr(args, "target", None) or os.environ.get("CLAUDE_PROJECT_DIR")
    if not root:
        raise EmitError("raiz do alvo ausente: passe --target <repo> ou defina CLAUDE_PROJECT_DIR")
    root = os.path.realpath(root)
    if not os.path.isdir(root):
        raise EmitError("raiz do alvo não é diretório: %s" % root)
    return root


def _refresh_team_maps(root):
    """deps/collision por território vêm de `cs.py team maps`; o caminho rápido (sem mesa redonda) e todo ajuste
    de roster os deixavam ausentes/velhos → a emissão (re)gera antes de renderizar. Sem grafo L1: mantém."""
    from team.maps import build_maps
    from team._shared_tmp.common import CsError as TeamErr
    try:
        build_maps(root)
        return True
    except TeamErr:
        return False


def run_emit(args):
    root = _root(args)
    if not args.dry_run:
        _refresh_team_maps(root)
    team = load_team(root)
    plats = _platforms(args.platforms, team, root)
    kn = knowledge.load(root)
    resolve_invariants(team, kn.facts)
    arts = P.build(team, kn, root, plats)
    governed = P.manifest_platforms(plats)
    steps = A.plan(root, arts, governed, force=args.force)
    out = sys.stdout
    outside = A.outside(steps)
    if args.dry_run:
        out.write("plano (dry-run; nada escrito) em %s para %s\n" % (root, ",".join(plats)))
        out.write(A.render_plan(steps, args.diff) + "\n")
        out.write(A.render_outside(outside) + "\n")
        return 3 if A.has_conflict(steps) else 0
    if A.has_conflict(steps):
        written = A.write_conflicts(root, steps)
        out.write(A.render_plan(steps) + "\n")
        sys.stderr.write("conflito: nada foi emitido. Propostas e diffs em:\n  %s\n"
                         "Resolva (mova o conteúdo humano para fora do caminho, ou use --force para backup + "
                         "sobrescrita)\n" % "\n  ".join(written))
        return 3
    if outside and not args.allow_outside:
        sys.stderr.write(A.render_outside(outside) + "\n")
        sys.stderr.write("nada foi emitido: %d escrita(s) FORA de .swarm/ exigem --allow-outside "
                         "(mostre a lista ao usuário antes)\n" % len(outside))
        return 3
    backups = A.apply(root, steps, arts, governed)
    out.write(A.render_plan(steps, args.diff) + "\n")
    for b in backups:
        out.write("backup: %s (+ .diff)\n" % b)
    rep = V.validate(root, plats)
    if not rep.ok:
        sys.stderr.write("emitido, mas a validação falhou:\n  - %s\n" % "\n  - ".join(rep.errors))
        return 1
    out.write("validação G7: ok (%d artefatos)\n" % rep.checked)
    return 0


def run_validate(args):
    root = _root(args)
    team = load_team(root)
    plats = _platforms(args.platforms, team, root)
    rep = V.validate(root, plats)
    if args.json:
        sys.stdout.write(json.dumps({"gate": "G7", "ok": rep.ok, "checked": rep.checked,
                                     "platforms": plats, "errors": rep.errors}, ensure_ascii=False, indent=2) + "\n")
    elif rep.ok:
        sys.stdout.write("G7 ok: %d artefatos válidos (%s)\n" % (rep.checked, ",".join(plats)))
    else:
        sys.stderr.write("G7 FALHOU (%d erro(s)):\n  - %s\n" % (len(rep.errors), "\n  - ".join(rep.errors)))
    return 0 if rep.ok else 1


def _core_by_command(root, team):
    """specialize.4 (efeito): núcleo gravado por `team core set|from-panel` (registro em
    panel/core-promotion.json5 com as MESMAS linhas) — core escrito à mão no team.json5 não conta."""
    lines = [" ".join(str(l.get("text", "")).split()) for l in (team.get("core") or {}).get("lines") or []
             if isinstance(l, dict)]
    if not lines:
        return "core.lines vazio — grave o núcleo com `team core from-panel` ou `team core set --file`"
    p = os.path.join(root, STATE_DIR, "panel", "core-promotion.json5")
    if not os.path.isfile(p):
        return "core.lines sem registro de `team core set|from-panel` (team.json5 editado à mão?)"
    from emit import j5 as _j5
    try:
        rec = _j5.load(p)
    except ValueError:
        return "panel/core-promotion.json5 ilegível"
    got = [" ".join(str(x.get("text", "")).split()) for x in rec.get("promoted") or []]
    if sorted(got) != sorted(lines):
        return "core.lines difere do último `team core set|from-panel` (editado à mão depois?)"
    return None


def run_budget(args):
    from emit.budget import check_budget
    root = _root(args)
    team = load_team(root)
    if getattr(args, "require_core", False):
        why = _core_by_command(root, team)
        if why:
            sys.stderr.write("falta: %s\n" % why)
            sys.stdout.write("orçamento por camada: núcleo não gravado por comando\n")
            return 1
    rep = check_budget(root, _platforms(args.platforms, team, root))
    if args.json:
        sys.stdout.write(json.dumps(rep, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    else:
        for layer, m in sorted(rep["layers"].items()):
            sys.stdout.write("%-8s máx %3d / %3d linhas (%s)\n" % (layer, m["max"], m["limit"], m["worst"]))
        for e in rep["errors"]:
            sys.stderr.write("falta: %s\n" % e)
        sys.stdout.write("orçamento por camada: %s\n" % ("ok" if rep["ok"] else "ESTOURADO"))
    return 0 if rep["ok"] else 1


def handler(args):
    try:
        if getattr(args, "emit_action", "run") == "budget":
            return run_budget(args)
        if getattr(args, "emit_action", "run") == "validate":
            return run_validate(args)
        return run_emit(args)
    except EmitError as exc:
        sys.stderr.write("emit: %s\n" % exc)
        return 2


def _add_args(p, with_target):
    p.add_argument("emit_action", nargs="?", choices=["run", "validate", "budget"], default="run",
                   help="run (padrão) emite; validate confere os artefatos (gate G7); budget mede as camadas")
    p.add_argument("--platforms", default=None,
                   help="lista separada por vírgula (padrão: team.json.platforms ou todas)")
    p.add_argument("--dry-run", action="store_true", help="mostra o plano sem escrever")
    p.add_argument("--diff", action="store_true", help="inclui diff unificado no plano")
    p.add_argument("--force", action="store_true",
                   help="sobrescreve arquivo humano no caminho de um artefato (com backup + diff)")
    p.add_argument("--json", action="store_true", help="saída JSON (validate)")
    p.add_argument("--allow-outside", action="store_true",
                   help="autoriza escrever FORA de .swarm/ (.claude/, .cursor/, .github/, AGENTS.md, CLAUDE.md…)")
    p.add_argument("--require-core", action="store_true", help="budget: falha se core.lines está vazio (specialize.4)")
    if with_target:
        p.add_argument("--target", default=None, help="raiz do repositório-alvo")
    p.set_defaults(func=handler)


def register(subparsers):
    p = subparsers.add_parser("emit", help="emite agentes/regras/núcleo por plataforma; `emit validate` = G7",
                              description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    _add_args(p, with_target=False)  # cs.py injeta --target
    guide.register(subparsers)  # `cs.py skills-guide --check|--write` (tabela de skills do MODO-DE-USO.md)
    return p


def main(argv=None):
    parser = argparse.ArgumentParser(prog="emit", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    _add_args(parser, with_target=True)
    args = parser.parse_args(argv)
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
