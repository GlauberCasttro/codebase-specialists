#!/usr/bin/env python3
"""sessao.py — dono ÚNICO da fórmula do carimbo de sessão e do frescor (skills carregar-sessao e salvar-sessao).

Carimbo (no RESUME.md, bloco `<!-- resume-stamp … -->`), só com campos COMPARÁVEIS:
  FEATURES  ids das features ativas (features.json) ou —
  BRANCH   branch atual
  HEAD     sha curto na gravação (comparado POR REGRA: igual, ou avançou só com commits em .claude/state/ e
           campanhas/ — o próprio salvar commita, e um arquivo não contém o hash do commit que o contém)
  PRODUTO  sha1 do conteúdo do produto (SKILL.md MODO-DE-USO.md VERSION LICENSE scripts assets references docs evals
           .claude/package) — é o que o portão mede
  ESTADO   sha1 de features.json + features/** (a máquina de estado das features)
  GATE     VERDE (todas as ativas com local/portao-<id>/portao.out VERDE+FIM) | PENDENTE | — (sem feature ativa)
Nunca reimplemente um campo fora daqui: uma fórmula paralela dá cache-miss falso e silencioso.

Subcomandos:
  carimbo [--write] [--json] [--field F]   imprime o carimbo; --write regrava o bloco no RESUME.md
  frescor [--json|--brief]                 veredito: sem-state | sem-carimbo | bate | cache-miss (FEATURES/BRANCH/
                                           HEAD/ESTADO divergem) | produto-mudou (só PRODUTO/GATE: régua PENDENTE)
  briefing [--json|--brief]                as duas sequências (macro: features; micro: tasks com ← PRÓXIMA e o porquê
                                           do elo) + "Retomo daqui?"
  salvar --resumo TXT [--feature F] [--feito TXT]… [--commit --mensagem ARQ] [--dry-run]
                                           carimbo no RESUME + linha em logs/sessoes.jsonl (+ bloco no log da
                                           feature) → privacidade → commit SÓ de .claude/state/** num índice
                                           temporário (terceiros intactos; nunca push) → auto-teste (frescor = bate)
Exit: 0 ok · 1 recusa (privacidade, auto-teste, sem estado) · 3 uso. Variável de teste: CS_DEV_SKILL_DIR.
"""
import argparse
import json
import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True
TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import estado_lib as L  # noqa: E402

CAMPOS = ("FEATURES", "BRANCH", "HEAD", "PRODUTO", "ESTADO", "GATE")
PRODUTO = ("SKILL.md", "MODO-DE-USO.md", "VERSION", "LICENSE", "scripts", "assets", "references", "docs", "evals",
           ".claude/package")
CARVE_OUT = (".claude/state/", "campanhas/")
BLOCO_RE = re.compile(r"<!-- resume-stamp\n(.*?)-->\n?", re.S)


# ------------------------------------------------------------------ carimbo

def calcular(r):
    d = L.features(r)
    ids = [x["id"] for x in d["ativas"]]
    branch = L.git(r, "branch", "--show-current")[1] or "?"
    head = L.git(r, "rev-parse", "--short", "HEAD")[1] or "?"
    st = L.state(r)
    estado = L.sha_arvore(st, L.raizes_estado(r))
    if ids:
        verdes = []
        for i in ids:
            t = L.ler(os.path.join(r, "local", "portao-" + i, "portao.out"), "")
            ls = t.rstrip().splitlines()
            verdes.append(bool(ls) and "RESULTADO: VERDE" in ls and ls[-1] == "FIM")
        gate = "VERDE" if all(verdes) else "PENDENTE"
    else:
        gate = "—"
    return {"FEATURES": ",".join(ids) or "—", "BRANCH": branch, "HEAD": head,
            "PRODUTO": L.sha_arvore(r, PRODUTO), "ESTADO": estado, "GATE": gate}


def bloco(c):
    return "<!-- resume-stamp\n" + "".join("%s: %s\n" % (k, c[k]) for k in CAMPOS) + "-->\n"


def ler_carimbo(r):
    t = L.ler(os.path.join(L.state(r), "RESUME.md"))
    if t is None:
        return None
    m = BLOCO_RE.search(t)
    if not m:
        return None
    out = {}
    for linha in m.group(1).splitlines():
        if ":" in linha:
            k, v = linha.split(":", 1)
            out[k.strip()] = v.strip()
    if L.LEGADO_CARIMBO in out:  # COMPAT: carimbo antigo (FRENTES:) vale como FEATURES
        out.setdefault("FEATURES", out.pop(L.LEGADO_CARIMBO))
    return out if all(k in out for k in CAMPOS) else None


def gravar_carimbo(r, c):
    p = os.path.join(L.state(r), "RESUME.md")
    t = L.ler(p)
    if t is None:
        t = "# RESUME\n\n## Onde paramos\n- (preencha)\n\n## Próximos passos\n1. (preencha)\n"
    novo = bloco(c)
    if BLOCO_RE.search(t):
        t2 = BLOCO_RE.sub(lambda _m: novo, t, count=1)
    else:
        t2 = novo + "\n" + t
    if t2 != t:
        L.gravar(p, t2)


def head_por_regra(r, salvo, atual):
    """bate se igual, ou se `salvo` é ancestral e o intervalo só tocou o carve-out (.claude/state/, campanhas/)."""
    if salvo == atual:
        return True, []
    if L.git(r, "merge-base", "--is-ancestor", salvo, "HEAD")[0] != 0:
        return False, ["HEAD %s não é ancestral do atual (branch trocada, rebase ou sha desconhecido)" % salvo]
    rc, out, _ = L.git(r, "diff", "--name-only", salvo, "HEAD")
    if rc != 0:
        return False, ["git diff falhou"]
    fora = [x for x in out.splitlines() if x and not x.startswith(CARVE_OUT)]
    return not fora, fora[:5]


def frescor(r):
    if not os.path.isdir(L.state(r)):
        return {"veredito": "sem-state", "divergentes": [], "motivo": ".claude/state/ não existe (salvar-sessao)"}
    salvo = ler_carimbo(r)
    atual = calcular(r)
    if not salvo:
        return {"veredito": "sem-carimbo", "divergentes": list(CAMPOS), "atual": atual,
                "motivo": "RESUME.md sem bloco resume-stamp"}
    div = []
    for k in ("FEATURES", "BRANCH", "ESTADO", "PRODUTO", "GATE"):
        if salvo.get(k) != atual[k]:
            div.append(k)
    ok_head, fora = head_por_regra(r, salvo.get("HEAD"), atual["HEAD"])
    if not ok_head:
        div.append("HEAD")
    contexto = [k for k in div if k in ("FEATURES", "BRANCH", "HEAD", "ESTADO")]
    if contexto:
        v = "cache-miss"
    elif div:
        v = "produto-mudou"
    else:
        v = "bate"
    return {"veredito": v, "divergentes": div, "salvo": salvo, "atual": atual, "head_fora_do_carve_out": fora}


def texto_frescor(j):
    v = j["veredito"]
    acao = {"bate": "confie no RESUME; não leia logs",
            "cache-miss": "reconstrua Onde paramos/Próximos passos do log da feature e regrave o carimbo "
                          "(sessao.py carimbo --write); rodapé: _contexto reconstruído do log_",
            "produto-mudou": "contexto vale; o produto mudou desde o save — régua PENDENTE (portão/e2e-loop antes "
                             "de commit de produto)",
            "sem-carimbo": "RESUME sem carimbo: rode `sessao.py carimbo --write` (ou salvar-sessao)",
            "sem-state": "estado nunca inicializado: rode a skill salvar-sessao"}[v]
    linhas = ["frescor: %s%s" % (v, " (%s)" % ", ".join(j["divergentes"]) if j["divergentes"] and v != "sem-carimbo"
                                  else ""), "ação: " + acao]
    for k in j.get("divergentes", []):
        if j.get("salvo") and k in j["salvo"]:
            linhas.append("  %s: salvo %s · atual %s" % (k, j["salvo"][k][:16], j["atual"][k][:16]))
    return "\n".join(linhas)


# ------------------------------------------------------------------ briefing

def secao_resume(r, nome):
    t = L.ler(os.path.join(L.state(r), "RESUME.md"), "")
    return L.secoes(t).get(nome, "").strip()


def briefing(r):
    fr = frescor(r)
    d = L.features(r)
    head = L.git(r, "rev-parse", "--short", "HEAD")[1] or "?"
    branch = L.git(r, "branch", "--show-current")[1] or "?"
    sujos = len([x for x in L.git(r, "status", "--porcelain")[1].splitlines() if x.strip()])
    linhas = ["Estado: %s · features ativas: %s" % ("IN_PROGRESS" if d["ativas"] else "IDLE",
                                                   ", ".join(x["id"] for x in d["ativas"]) or "nenhuma"),
              "Git: %s @ %s · %d arquivo(s) sujo(s) · carimbo: %s%s" % (
                  branch, head, sujos, fr["veredito"], " (%s)" % ",".join(fr["divergentes"])
                  if fr["divergentes"] and fr["veredito"] not in ("sem-carimbo", "bate") else "")]
    escopo = secao_resume(r, "Escopo autorizado e limites")
    if escopo:
        linhas += [x for x in escopo.splitlines() if x.strip()][:3]
    onde = secao_resume(r, "Onde paramos")
    if onde:
        linhas.append("Onde paramos:")
        linhas += ["  " + x.strip() for x in onde.splitlines() if x.strip()][:3]
    linhas.append("Sequência de features (macro):")
    if d["entregues"]:
        u = d["entregues"][-1]
        linhas.append("- [x] %s — entregue %s" % (u["id"], u.get("fechada_em", "")[:10]))
    obj_features = []
    for i, x in enumerate(d["ativas"], 1):
        fd = L.feature_dir(x["id"], r)
        fr_md = L.ler_feature(L.feature_md(fd)) or {}
        tasks = L.ler_tasks(fd)
        nome = fr_md.get("nome") or ("campanha legada (adotada)" if x.get("origem") == "legado" else x["id"])
        linhas.append("- [ ] %d. %s — %s · %s tasks%s" % (i, x["id"], nome, L.progresso(tasks),
                                                          "   ← VOCÊ ESTÁ AQUI" if i == 1 else ""))
        linhas.append("      (%s)" % ("origem: %s, aberta em %s" % (x.get("origem"), x.get("aberta_em", "?")[:10])))
        obj_features.append({"id": x["id"], "nome": nome, "progresso": L.progresso(tasks)})
    cri = L.em_criacao(r)
    if cri:
        linhas.append("- [ ] criação em curso: %s · próxima etapa %s" % (cri[0], L.etapa_corrente(L.eventos(cri[0], r))
                                                                      or "abrir"))
    if not d["ativas"] and not cri:
        linhas.append("- (nenhuma feature ativa — próxima: topo do BACKLOG, via criar-feature)")
    micro = []
    for x in d["ativas"]:
        tasks = L.ler_tasks(L.feature_dir(x["id"], r))
        if not tasks:
            continue
        el = L.elegiveis(tasks)
        prox = el[0]["stem"] if el else None
        top = "paralelo" if len(el) >= 2 else "sequencial"
        linhas.append("Sequência de tasks (micro) — %s · %s · %s:" % (x["id"], top, L.progresso(tasks)))
        for t in tasks:
            marca = "x" if t["status"] == "DONE" else " "
            elo = "; ".join("%s: %s" % (dd, porque or "sem porquê") for dd, porque in t["depends"])
            linha = "- [%s] %s — %s%s" % (marca, t["stem"], t["entrega"], " (%s)" % elo if elo else "")
            if t["stem"] == prox:
                linha += "   ← PRÓXIMA"
            linhas.append(linha)
            micro.append({"feature": x["id"], "id": t["stem"], "status": t["status"], "proxima": t["stem"] == prox})
        break
    passos = secao_resume(r, "Próximos passos")
    if passos:
        linhas.append("Próximos passos:")
        linhas += ["  " + x.strip() for x in passos.splitlines() if x.strip()][:3]
    linhas.append("Retomo daqui? (sim / ajustar)")
    if len(linhas) > 40:
        linhas = linhas[:39] + ["Retomo daqui? (sim / ajustar)"]
    return {"frescor": fr["veredito"], "divergentes": fr["divergentes"], "features": obj_features, "tasks": micro,
            "texto": "\n".join(linhas)}


# ------------------------------------------------------------------ salvar

def privacidade(r, arquivos, msg):
    env = dict(os.environ, CS_DEV_SKILL_DIR=r)
    ruins = []
    alvo = [os.path.join(r, x) for x in arquivos if os.path.exists(os.path.join(r, x))]
    if alvo:
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "guard_privacidade.py")] + alvo, cwd=r, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
        if p.returncode != 0:
            ruins.append(p.stdout.decode("utf-8", "replace").strip() or "achado")
    if msg:
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "guard_privacidade.py"), "--msg", msg], cwd=r,
                           env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
        if p.returncode != 0:
            ruins.append("mensagem: " + (p.stdout.decode("utf-8", "replace").strip() or "achado"))
    return ruins


def commit_estado(r, msg):
    import feature  # noqa: E402 — reaproveita o commit em índice temporário
    rc, out, _ = L.git(r, "status", "--porcelain", "--untracked-files=all", "--", ".claude/state")
    if not out.strip():
        return None, []
    arquivos = []
    for linha in out.splitlines():
        p = linha[3:].split(" -> ")[-1].strip().strip('"')
        arquivos.append(p)
    priv = privacidade(r, arquivos, msg)
    if priv:
        raise feature.Recusa("guard de privacidade achou termo privado — nada commitado:\n" + "\n".join(priv))
    return feature.commit_indice_temporario(r, [".claude/state"], os.path.realpath(msg)), arquivos


def cmd_salvar(a, r):
    st = L.state(r)
    if not os.path.isdir(st):
        if a.dry_run:
            print("dry-run: criaria .claude/state/ (RESUME, WORKFLOW, BACKLOG, DECISIONS, logs/)")
            return 0
        for n, t in (("RESUME.md", "# RESUME\n\n## Escopo autorizado e limites\n- Autorizado: —\n- NÃO autorizado: —\n"
                                   "\n## Onde paramos\n- estado inicializado\n\n## Próximos passos\n1. —\n"),
                     ("WORKFLOW.md", "# WORKFLOW\n"), ("BACKLOG.md", "# BACKLOG\n\n| id | P | item |\n|---|---|---|\n"),
                     ("DECISIONS.md", "# Decisões\n\n| id | data | decisão | porquê | onde vale |\n|---|---|---|---|---|\n")):
            L.gravar(os.path.join(st, n), t)
        L.apensar(os.path.join(st, "logs", "sessoes.jsonl"), "")
    if a.commit and not a.mensagem:
        print("--commit exige --mensagem ARQ (mensagem em arquivo)", file=sys.stderr)
        return 3
    c = calcular(r)
    branch = c["BRANCH"]
    reg = {"evento": "sessao-salva", "data": L.agora(), "resumo": a.resumo, "branch": branch, "head": c["HEAD"],
           "features": [x for x in c["FEATURES"].split(",") if x != "—"]}
    if a.feature:
        reg["feature"] = a.feature
    if a.dry_run:
        print("dry-run: regravaria o carimbo do RESUME (%s) e apensaria em logs/sessoes.jsonl:\n  %s%s"
              % (", ".join("%s=%s" % (k, c[k][:12]) for k in CAMPOS), json.dumps(reg, ensure_ascii=False),
                 "\n  e commitaria só .claude/state/** (privacidade antes; nunca push)" if a.commit else ""))
        return 0
    gravar_carimbo(r, c)
    L.apensar(os.path.join(st, "logs", "sessoes.jsonl"), json.dumps(reg, ensure_ascii=False) + "\n")
    if a.feature:
        linhas = ["", "## %s — sessão salva" % reg["data"], "- Resumo: %s" % a.resumo]
        linhas += ["- Feito: %s" % x for x in (a.feito or [])][:18]
        L.apensar(os.path.join(st, "logs", a.feature, a.feature + ".md"), "\n".join(linhas) + "\n")
    sha = None
    if a.commit:
        import feature
        try:
            sha, arqs = commit_estado(r, a.mensagem)
        except feature.Recusa as e:
            print("RECUSADO: %s" % e, file=sys.stderr)
            return 1
    j = frescor(r)
    if j["veredito"] != "bate":
        print("O SAVE ESTÁ ERRADO: carregar imediato daria %s (%s)" % (j["veredito"], ", ".join(j["divergentes"])),
              file=sys.stderr)
        return 1
    print("sessão salva%s · carimbo %s · autoteste (carregar imediato): bate" % (
        " e commitada: %s" % sha[:12] if sha else "", c["HEAD"]))
    return 0


# ------------------------------------------------------------------ CLI

def main(argv=None):
    ap = argparse.ArgumentParser(prog="sessao.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("carimbo")
    s.add_argument("--write", action="store_true")
    s.add_argument("--json", action="store_true")
    s.add_argument("--field", choices=CAMPOS)
    for n in ("frescor", "briefing"):
        s = sub.add_parser(n)
        s.add_argument("--json", action="store_true")
        s.add_argument("--brief", action="store_true")
    s = sub.add_parser("salvar")
    s.add_argument("--resumo", required=True)
    s.add_argument("--feature")
    s.add_argument("--feito", action="append")
    s.add_argument("--commit", action="store_true")
    s.add_argument("--mensagem")
    s.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    r = L.raiz()
    if a.cmd == "carimbo":
        c = calcular(r)
        if a.field:
            print(c[a.field])
            return 0
        if a.write:
            if not os.path.isdir(L.state(r)):
                print("sem .claude/state/ — rode a skill salvar-sessao", file=sys.stderr)
                return 1
            gravar_carimbo(r, c)
        if a.json:
            print(json.dumps(c, ensure_ascii=False, indent=1))
        else:
            sys.stdout.write(bloco(c))
        return 0
    if a.cmd == "frescor":
        j = frescor(r)
        t = texto_frescor(j)
        L.saida({k: v for k, v in j.items()}, a, t, t)
        return 0
    if a.cmd == "briefing":
        j = briefing(r)
        L.saida(j, a, j["texto"], j["texto"])
        return 0
    if a.cmd == "salvar":
        return cmd_salvar(a, r)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
