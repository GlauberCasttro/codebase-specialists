#!/usr/bin/env python3
"""package_validar.py — valida um pacote gerado (dist/codebase-specialists) como SKILL INSTALADA.

Uso:  package_validar.py <pacote> [--fixture ARQ] [--manter] [--json]
      package_validar.py --help

1. Vazamento: nenhum caminho do pacote tem componente `.claude`, `campanhas`, `local`, `tests`, `evals`, `dist`,
   `__pycache__`, `.auto-correcao` nem arquivo `*.pyc` (lista explícita; achado = reprova).
2. Instalação: copia o pacote para um HOME temporário em `$HOME/.claude/skills/codebase-specialists`.
3. Alvo: repositório git temporário montado pela fixture do projeto (`scripts/emit/tests/fixture.py`: team.json5 +
   facts mínimos) e commitado.
4. Com HOME=<temporário>, a skill INSTALADA roda no alvo: `cs.py init` → `harness install` → `emit` (4 plataformas)
   → `emit validate` → `harness selftest`. Qualquer exit != 0 reprova.
Temporários são apagados no fim (a menos que --manter). Exit 0 = pacote válido. Stdlib apenas, Python 3.9+.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
PROJETO = os.path.realpath(os.environ.get("CS_DEV_SKILL_DIR") or os.path.join(TOOLS, "..", ".."))
PROIBIDOS = {".claude", "campanhas", "local", "tests", "evals", "dist", "__pycache__", ".auto-correcao"}
PLATAFORMAS = "claude-code,cursor,copilot,codex"


def vazamentos(pacote):
    out = []
    for d, dirs, files in os.walk(pacote):
        for nome in dirs + files:
            rel = os.path.relpath(os.path.join(d, nome), pacote)
            partes = rel.split(os.sep)
            if PROIBIDOS.intersection(partes) or rel.endswith(".pyc"):
                out.append(rel)
    return sorted(set(out))


def sh(cmd, env, cwd=None):
    p = subprocess.run(cmd, env=env, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
    return p.returncode, p.stdout.decode("utf-8", "replace")


def montar_alvo(fixture_py, base):
    d = os.path.dirname(os.path.abspath(fixture_py))
    code = ("import sys, os, shutil; sys.path.insert(0, %r); import fixture; r = fixture.make_repo(); "
            "dst = os.path.join(%r, 'alvo'); shutil.move(r, dst); print(dst)") % (d, base)
    p = subprocess.run([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), timeout=120)
    if p.returncode != 0:
        raise SystemExit("fixture falhou: " + p.stderr.decode())
    alvo = p.stdout.decode().strip().splitlines()[-1]
    g = ["git", "-C", alvo, "-c", "user.email=pacote@exemplo.invalid", "-c", "user.name=pacote"]
    for a in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "alvo de validação do pacote"]):
        subprocess.run(g[:3] + a if a[0] == "init" else g + a, check=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
    return alvo


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    pacote = os.path.realpath(argv[0])
    fixture_py = os.path.join(PROJETO, "scripts", "emit", "tests", "fixture.py")
    if "--fixture" in argv:
        fixture_py = argv[argv.index("--fixture") + 1]
    manter, js = "--manter" in argv, "--json" in argv
    rel = {"pacote": pacote, "vazamentos": [], "passos": [], "ok": False}
    if not os.path.isfile(os.path.join(pacote, "SKILL.md")):
        print("pacote sem SKILL.md: %s" % pacote, file=sys.stderr)
        return 2
    rel["vazamentos"] = vazamentos(pacote)
    base = os.path.realpath(tempfile.mkdtemp(prefix="cs-pacote-"))
    try:
        home = os.path.join(base, "home")
        inst = os.path.join(home, ".claude", "skills", "codebase-specialists")
        shutil.copytree(pacote, inst)
        alvo = montar_alvo(fixture_py, base)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CS_", "CLAUDE_"))}
        env.update({"HOME": home, "PYTHONDONTWRITEBYTECODE": "1"})
        cs = [sys.executable, os.path.join(inst, "scripts", "cs.py"), "--target", alvo]
        passos = [("init", cs + ["init", "--platforms", PLATAFORMAS]),
                  ("harness install", cs + ["harness", "install", "--allow-outside", "--platforms", PLATAFORMAS]),
                  ("emit", cs + ["emit", "--platforms", PLATAFORMAS, "--allow-outside"]),
                  ("emit validate", cs + ["emit", "validate", "--platforms", PLATAFORMAS]),
                  ("harness selftest", cs + ["harness", "selftest"])]
        for nome, cmd in passos:
            rc, out = sh(cmd, env, cwd=alvo)
            ult = [x for x in out.strip().splitlines() if x.strip()][-1:] or [""]
            rel["passos"].append({"passo": nome, "exit": rc, "ultima_linha": ult[0][:200]})
            if rc != 0:
                rel["falha_saida"] = out[-3000:]
                break
        rel["instalado_em_home_temporario"] = True
        rel["ok"] = not rel["vazamentos"] and len(rel["passos"]) == len(passos) and all(
            p["exit"] == 0 for p in rel["passos"])
    finally:
        if manter:
            rel["temporario"] = base
        else:
            shutil.rmtree(base, ignore_errors=True)
    if js:
        print(json.dumps(rel, ensure_ascii=False, indent=1))
    else:
        print("vazamentos (.claude/campanhas/local/tests/evals/...): %d" % len(rel["vazamentos"]))
        for v in rel["vazamentos"][:20]:
            print("  VAZOU " + v)
        for p in rel["passos"]:
            print("  %-17s exit %d · %s" % (p["passo"], p["exit"], p["ultima_linha"]))
        if rel.get("falha_saida"):
            print(rel["falha_saida"])
        print("validação do pacote: %s" % ("OK" if rel["ok"] else "REPROVADA"))
    return 0 if rel["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
