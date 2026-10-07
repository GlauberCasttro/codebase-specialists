#!/usr/bin/env python3
"""campanha.py — atalhos mecânicos da skill auto-correcao sobre o motor EMBUTIDO (.claude/tools/ac/ac.py).

Três subcomandos e só eles (nenhum roda gate, preauth ou frase: são do founder, no terminal dele):
  etapa <f> [--json|--brief]
        etapa corrente da campanha campanhas/<f>, sub-etapas pendentes {id, ctx, do} lidas do ciclo.json5 do motor
        (feita = já em `done` ou `ac.py check <sub>` ok) e o próximo passo; ctx "user" = portão do founder.
  mudanca-oficial <f> --porque TXT --evidencia TXT [--dry-run]
        exige patch (*.patch) e PORQUE*.md em campanhas/<f>/oraculo/mudanca-oficial/ e monta
        `oracle change --why --evidence` com TODOS os --file congelados (passar só um substituiria a lista).
  fechar <f> --relatorio ARQ --config C --decisao D [--dry-run] [--concluir]
        front report → done correcao → set integration.tests_green true → done integracao → run record
        → done remedicao → set decision/report → (FOUNDER: frase conferir, no terminal dele) → done decisao
        (só com --concluir, depois da conferência).
Saída: texto, --json ou --brief (≤ 40 linhas). Exit: 0 ok · 1 recusa (motor recusou, falta mudança oficial) · 3 uso.
Variáveis de teste: CS_DEV_SKILL_DIR, CS_DEV_AC (o --json mostra o motor usado).
"""
import argparse
import glob
import importlib.util
import json
import os
import shlex
import sys
import time

sys.dont_write_bytecode = True
TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import estado_lib as L  # noqa: E402

AC_LITERAL = "python3 .claude/tools/ac/ac.py"


def ciclo():
    """ciclo.json5 do motor em uso (ou o do embutido, se o motor não tiver references/)."""
    cands = [os.path.join(os.path.dirname(L.motor()), "references", "ciclo.json5"),
             os.path.join(os.path.dirname(os.path.dirname(L.motor())), "references", "ciclo.json5"),
             os.path.join(TOOLS, "ac", "references", "ciclo.json5")]
    p = next(c for c in cands if os.path.isfile(c))
    spec = importlib.util.spec_from_file_location("ac_embutido", os.path.join(TOOLS, "ac", "ac.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.json5_load(p)


def exige_campanha(f, r):
    if not L.ID_RE.match(f):
        raise SystemExit("nome de campanha inválido: %r" % f)
    st = L.campanha_estado(f, r)
    if st is None:
        print("RECUSADO: campanha campanhas/%s não iniciada (criar-feature abre com ac.py init)" % f, file=sys.stderr)
        sys.exit(1)
    return st


def cmd_etapa(a, r):
    st = exige_campanha(a.f, r)
    cy = ciclo()
    etapa = st.get("stage", "?")
    pend = []
    if etapa in cy["stages"]:
        for sub in cy["stages"][etapa]["substages"]:
            if (st.get("done") or {}).get(sub["id"]):
                continue
            if sub["ctx"] != "user" and L.ac(L.campanha_dir(a.f, r), "check", sub["id"], r=r)[0] == 0:
                continue
            pend.append({"id": sub["id"], "ctx": sub["ctx"], "do": sub["do"]})
    if not pend and etapa in cy["stages"]:
        prox = "%s --work campanhas/%s done %s" % (AC_LITERAL, a.f, etapa)
    elif pend and pend[0]["ctx"] == "user":
        prox = ("portão do FOUNDER (%s): gere `bash .claude/tools/script-aprovacao.sh %s` e peça que ele rode no "
                "terminal dele; você não roda gate/preauth/frase" % (pend[0]["id"], a.f))
    elif pend:
        prox = "%s (%s) — %s; depois `%s --work campanhas/%s check %s`" % (
            pend[0]["id"], pend[0]["ctx"], pend[0]["do"], AC_LITERAL, a.f, pend[0]["id"])
    else:
        prox = "campanha %s: %s" % (a.f, etapa)
    obj = {"feature": a.f, "motor": L.motor(), "etapa": etapa, "rodada": st.get("round"), "pendentes": pend,
           "proximo": prox}
    t = "campanha %s · rodada %s · etapa %s\n%s\npróximo: %s" % (
        a.f, st.get("round"), etapa, "\n".join("  [ ] %s (%s) %s" % (p["id"], p["ctx"], p["do"]) for p in pend)
        or "  (sem sub-etapa pendente)", prox)
    L.saida(obj, a, t, t)
    return 0


def cmd_mudanca(a, r):
    st = exige_campanha(a.f, r)
    d = os.path.join(L.campanha_dir(a.f, r), "oraculo", "mudanca-oficial")
    patches = sorted(glob.glob(os.path.join(d, "*.patch")))
    porques = sorted(glob.glob(os.path.join(d, "PORQUE*.md")))
    if not patches or not porques:
        print("RECUSADO: mudança oficial exige patch (*.patch) e PORQUE*.md em campanhas/%s/oraculo/mudanca-oficial/ "
              "antes do `oracle change` (o founder confere o diff e o porquê)" % a.f, file=sys.stderr)
        return 1
    files = (st.get("oracle") or {}).get("files") or []
    if not files:
        print("RECUSADO: o oráculo de %s nunca foi congelado (oracle freeze)" % a.f, file=sys.stderr)
        return 1
    rels = [L.rel(p, r) if p.startswith(r + os.sep) else p for p in files]
    args = ["oracle", "change", "--why", a.porque, "--evidence", a.evidencia]
    for x in rels:
        args += ["--file", x]
    linha = "%s --work campanhas/%s %s" % (AC_LITERAL, a.f, " ".join(shlex.quote(x) for x in args))
    print("mudança oficial: %d patch(es), %d PORQUE, %d arquivo(s) do oráculo (TODOS)" % (len(patches), len(porques),
                                                                                       len(files)))
    print(linha)
    if a.dry_run:
        return 0
    rc, out, err = L.ac(L.campanha_dir(a.f, r), *args, r=r)
    print((out + err).strip())
    return 0 if rc == 0 else 1


def cmd_fechar(a, r):
    exige_campanha(a.f, r)
    if not os.path.isfile(a.relatorio):
        print("RECUSADO: relatório não existe: %s" % a.relatorio, file=sys.stderr)
        return 1
    rel = L.rel(os.path.realpath(a.relatorio), r) if os.path.realpath(a.relatorio).startswith(r + os.sep) \
        else os.path.realpath(a.relatorio)
    passos = [["front", "report", "--file", rel, "fechamento"], ["done", "correcao"],
              ["set", "integration.tests_green", "true"], ["done", "integracao"],
              ["run", "record", "--config", a.config, "--decision", a.decisao], ["done", "remedicao"],
              ["set", "decision", a.decisao], ["set", "report", rel]]
    founder = ("FOUNDER (no terminal dele, com a senha; a IA nunca roda): %s --work campanhas/%s frase conferir"
               % (AC_LITERAL, a.f))
    final = ["done", "decisao"]

    def txt(p):
        return "%s --work campanhas/%s %s" % (AC_LITERAL, a.f, " ".join(shlex.quote(x) for x in p))

    if a.dry_run:
        for p in passos:
            print(txt(p))
        print(founder)
        print(txt(final) + "   # só com --concluir, depois da conferência do founder")
        return 0
    w = L.campanha_dir(a.f, r)
    for p in passos:
        if p[0] == "run":
            time.sleep(1.1)   # AC-09: run record no mesmo segundo do done correcao não conta para a remedição
        rc, out, err = L.ac(w, *p, r=r)
        print("%s → %s" % (txt(p), (out or err).strip().splitlines()[-1] if (out or err).strip() else rc))
        if rc != 0:
            print("RECUSADO pelo motor em `%s`: %s" % (" ".join(p[:2]), (err or out).strip()), file=sys.stderr)
            return 1
    print(founder)
    if not a.concluir:
        print("pare aqui: depois que o founder rodar a conferência, `campanha.py fechar %s … --concluir`" % a.f)
        return 0
    rc, out, err = L.ac(w, *final, r=r)
    print("%s → %s" % (txt(final), (out or err).strip()))
    return 0 if rc == 0 else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="campanha.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("etapa", help="etapa corrente e sub-etapas pendentes")
    s.add_argument("f")
    s.add_argument("--json", action="store_true")
    s.add_argument("--brief", action="store_true")
    s = sub.add_parser("mudanca-oficial", help="oracle change com todos os arquivos, depois do patch + PORQUE")
    s.add_argument("f")
    s.add_argument("--porque", required=True)
    s.add_argument("--evidencia", required=True)
    s.add_argument("--dry-run", action="store_true")
    s = sub.add_parser("fechar", help="sequência de fechamento da campanha; o humano fica com o founder")
    s.add_argument("f")
    s.add_argument("--relatorio", required=True)
    s.add_argument("--config", required=True)
    s.add_argument("--decisao", required=True)
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--concluir", action="store_true")
    a = ap.parse_args(argv)
    r = L.raiz()
    fn = {"etapa": cmd_etapa, "mudanca-oficial": cmd_mudanca, "fechar": cmd_fechar}.get(a.cmd)
    if not fn:
        ap.print_help()
        return 0
    return fn(a, r)


if __name__ == "__main__":
    sys.exit(main())
