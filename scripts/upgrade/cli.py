"""`cs.py upgrade [--apply [--allow-outside]]` — atualiza o MECANISMO de um alvo já gerado para a versão da skill.

Sem flags = PLANO (não escreve nada): versão do alvo × da skill, migrações no intervalo, o que muda, o que é
preservado e o que fica fora de .swarm/. `--apply`: backup em .swarm/backups/upgrade-<de>-<para>/,
roda só as ações necessárias, verifica (harness selftest, harness validate --strict --allow-empty, emit validate)
e, se algo falhar, restaura o backup e sai com 1. Sucesso grava skill_version e upgrade_history no run.json5.
Alvo no diretório legado (.specialists/): a migração rename-dir o move para .swarm/ antes das demais ações.
Exit: 0 ok/nada a fazer · 1 falhou e restaurou · 2 entrada inválida · 3 recusado sem escrever (fora/conflito).
"""

import sys

from . import core


def handler(args):
    if args.apply:
        return core.apply(args.target, allow_outside=args.allow_outside)
    if args.allow_outside:
        sys.stderr.write("aviso: --allow-outside só vale com --apply; mostrando o plano\n")
    plan = core.build_plan(args.target)
    sys.stdout.write(core.render_plan(plan) + "\n")
    return 0


def register(subparsers):
    p = subparsers.add_parser("upgrade", help="atualiza o mecanismo de um alvo gerado (plano; --apply aplica)",
                              description=__doc__)
    p.add_argument("--apply", action="store_true",
                   help="aplica: backup → ações das migrações → verificação → restauração em falha")
    p.add_argument("--allow-outside", action="store_true",
                   help="permite escrever fora de .swarm/ (.claude/, AGENTS.md, Makefile...); "
                        "mostre o plano ao usuário antes")
    p.set_defaults(func=handler)
    return p
