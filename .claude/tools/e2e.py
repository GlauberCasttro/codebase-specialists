#!/usr/bin/env python3
"""e2e.py — a régua do desenvolvimento (skill e2e-loop): lista as suítes, seleciona pelo arquivo tocado e roda nos
2 Pythons.

Subcomandos:
  regua [--json|--brief]
        suítes {nome, dir}: `harness-dev` (.claude/tools/tests), cada scripts/<x> com tests/, `evals` (evals/tests);
        pythons (regua.json) e verificações extras do portão.
  selecionar (--arquivos A … | --lista ARQ) [--fechamento] [--json]
        {"suites", "completa", "porque"}: `.claude/**` ⇒ só harness-dev; `scripts/<x>/**` ⇒ x; desconhecido ou
        --fechamento ⇒ TODAS (completa: true). A completa roda no fechamento e no portão; durante a frente, a seletiva.
  rodar --suites a,b [--pythons "p1 p2"] [--dry-run]
        `<py> -m unittest discover -s tests` dentro de cada suíte, em cada Python; resumo Ran/OK/FAILED por linha.
        Python ausente ⇒ NOT_RUN (não é PASS nem FAIL). --dry-run imprime os comandos.
Exit: 0 ok/verde · 1 alguma suíte vermelha ou NOT_RUN · 3 uso. Variável de teste: CS_DEV_SKILL_DIR.
"""
import argparse
import fnmatch
import json
import os
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import estado_lib as L  # noqa: E402


def cfg():
    with open(os.path.join(TOOLS, "regua.json"), encoding="utf-8") as fh:
        return json.load(fh)


def suites(r):
    c = cfg()
    out = [dict(c["suite_harness"])]
    sd = os.path.join(r, "scripts")
    if os.path.isdir(sd):
        for x in sorted(os.listdir(sd)):
            if os.path.isdir(os.path.join(sd, x, "tests")):
                out.append({"nome": x, "dir": "scripts/%s/tests" % x})
    if os.path.isdir(os.path.join(r, "evals", "tests")):
        out.append({"nome": "evals", "dir": "evals/tests"})
    return out


def selecionar(r, arquivos, fechamento=False):
    todas = [s["nome"] for s in suites(r)]
    if fechamento:
        return {"suites": todas, "completa": True, "porque": ["--fechamento: régua completa"]}
    escolhidas, porque = [], []
    for a in arquivos:
        a = a.replace(os.sep, "/")
        while a.startswith("./"):
            a = a[2:]
        regra_ok = None
        for regra in cfg()["mapa"]:
            g = regra["glob"]
            if "{x}" in g:
                pre = g.split("{x}")[0]
                resto = a[len(pre):] if a.startswith(pre) else ""
                x = resto.split("/")[0] if "/" in resto else ""
                if x in todas:
                    regra_ok = dict(regra, suites=[s.replace("{x}", x) for s in regra["suites"]])
            elif fnmatch.fnmatch(a, g):
                regra_ok = regra
            if regra_ok:
                break
        if not regra_ok:
            return {"suites": todas, "completa": True,
                    "porque": ["%s: nenhuma regra cobre ⇒ régua completa (por segurança)" % a]}
        if regra_ok.get("completa"):
            return {"suites": todas, "completa": True, "porque": ["%s → completa (%s)" % (a, regra_ok["porque"])]}
        escolhidas += regra_ok["suites"]
        porque.append("%s → %s (%s)" % (a, ",".join(regra_ok["suites"]), regra_ok["porque"]))
    sel = [s for s in todas if s in escolhidas]
    return {"suites": sel, "completa": sorted(sel) == sorted(todas), "porque": porque}


def comando(r, s, py):
    base = os.path.dirname(os.path.join(r, s["dir"]))
    return base, [py, "-m", "unittest", "discover", "-s", "tests"]


def cmd_regua(a, r):
    c = cfg()
    obj = {"suites": suites(r), "pythons": c["pythons"], "verificacoes": c["verificacoes"]}
    t = "régua: %d suítes × %s\n%s\nverificações: %s" % (
        len(obj["suites"]), " e ".join(c["pythons"]), "\n".join("  - %s (%s)" % (s["nome"], s["dir"])
                                                                  for s in obj["suites"]),
        "; ".join(x.split(" (")[0] for x in c["verificacoes"]))
    L.saida(obj, a, t, t)
    return 0


def cmd_selecionar(a, r):
    arqs = list(a.arquivos or [])
    if a.lista:
        arqs += [x.strip() for x in (L.ler(a.lista, "") or "").splitlines() if x.strip()]
    if not arqs and not a.fechamento:
        print("passe --arquivos … ou --lista ARQ (ou --fechamento)", file=sys.stderr)
        return 3
    j = selecionar(r, arqs, a.fechamento)
    L.saida(j, a, "suítes: %s%s\n%s" % (",".join(j["suites"]), " (COMPLETA)" if j["completa"] else "",
                                         "\n".join("  " + x for x in j["porque"])))
    return 0


def cmd_rodar(a, r):
    pys = (a.pythons or " ".join(cfg()["pythons"])).split()
    por_nome = {s["nome"]: s for s in suites(r)}
    pedidas = [x for x in a.suites.split(",") if x]
    falta = [x for x in pedidas if x not in por_nome]
    if falta:
        print("suíte desconhecida: %s (e2e.py regua)" % ", ".join(falta), file=sys.stderr)
        return 3
    ruim = False
    for py in pys:
        for n in pedidas:
            base, cmd = comando(r, por_nome[n], py)
            rel = L.rel(base, r)
            if a.dry_run:
                print("(cd %s && PYTHONDONTWRITEBYTECODE=1 %s)   # %s · %s" % (rel, " ".join(cmd), n, py))
                continue
            if not shutil.which(py) and not os.path.isfile(py):
                print("NOT_RUN %s %s: python ausente" % (py, n))
                ruim = True
                continue
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", CS_SKILL_DIR=r, CS_SKILL=r)
            p = subprocess.run(cmd, cwd=base, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL)
            linhas = [x for x in p.stdout.decode("utf-8", "replace").splitlines()
                      if x.startswith(("Ran ", "OK", "FAILED"))]
            res = " ".join(linhas) or "SEM RESULTADO"
            ok = p.returncode == 0 and "OK" in res
            ruim = ruim or not ok
            print("%s %s %s: %s" % ("PASS" if ok else "FAIL", py, n, res))
    if not a.dry_run:
        print("RESULTADO: %s" % ("VERMELHO" if ruim else "VERDE"))
    return 1 if ruim else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="e2e.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("regua")
    s.add_argument("--json", action="store_true")
    s.add_argument("--brief", action="store_true")
    s = sub.add_parser("selecionar")
    s.add_argument("--arquivos", nargs="+")
    s.add_argument("--lista")
    s.add_argument("--fechamento", action="store_true")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("rodar")
    s.add_argument("--suites", required=True)
    s.add_argument("--pythons")
    s.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    fn = {"regua": cmd_regua, "selecionar": cmd_selecionar, "rodar": cmd_rodar}.get(a.cmd)
    if not fn:
        ap.print_help()
        return 0
    return fn(a, L.raiz())


if __name__ == "__main__":
    sys.exit(main())
