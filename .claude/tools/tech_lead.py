#!/usr/bin/env python3
"""tech_lead.py — a mecânica do tech-lead (skill tech-lead): plano derivado do disco, próxima task, roteamento de
modelo por papel e snapshot para conferir quem só lê. O tech-lead julga; este script calcula.

Subcomandos:
  plano [--modo autonomo|iterativo|status] [--feature F] [--json|--brief]
        sem --modo ⇒ exit 2 com a PERGUNTA do modo (o founder escolhe a cada invocação). Com modo: por feature ativa,
        progresso k/t, próxima, elegíveis, bloqueio, topologia, caminho crítico (cadeia mais longa de depends até a
        REVIEW), gates humanos e o despacho da próxima (papel, modelo, motivo).
  proxima [--feature F] [--json]
        elegíveis agora: depends DONE; CORRECAO só depois da aprovação do founder (`ac.py check intake.3`) ⇒ senão
        bloqueio "aprovacao_founder"; "paralelo" só com ≥2 elegíveis de arquivos disjuntos e sem `Execução:
        sequencial` no FEATURE.md.
  modelo --papel executor|revisor|qa|review|oraculo|rh:<persona> [--ciclo N] [--task ARQ] [--json]
        modelo pela tabela roteamento.json (+ personas.json para rh:); papel desconhecido ⇒ exit 2.
  snap --out ARQ [--dir D] | snap --comparar ARQ [--dir D] [--json]
        fotografa arquivos sujos/não rastreados por hash (ou toda a pasta D); --comparar sai 1 se algo mudou
        (revisor, QA e contratados são SOMENTE LEITURA: escreveu ⇒ parecer descartado).
Exit: 0 ok · 1 recusa/mudou · 2 pergunta pendente (plano sem modo) ou papel desconhecido · 3 uso.
Nunca roda gate/preauth/frase do motor. Variáveis de teste: CS_DEV_SKILL_DIR, CS_DEV_AC.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True
TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import contrato as C  # noqa: E402
import estado_lib as L  # noqa: E402

MODOS = ("autonomo", "iterativo", "status")
PAPEL_DO_TIPO = {"ORACULO": "oraculo", "CORRECAO": "executor", "QA": "qa", "REVIEW": "review"}
PERGUNTA = ("Como executo? (autônomo: task após task, parando só nos gates humanos · iterativo: uma task completa "
            "e paro para o seu ok · status: só o briefing) — responda autônomo, iterativo ou status")


def carregar_json(nome):
    with open(os.path.join(TOOLS, nome), encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------------ modelo

def modelo(papel, ciclo=1, task=None):
    rt = carregar_json("roteamento.json")["papeis"]
    if papel.startswith("rh:"):
        p = carregar_json("personas.json")["personas"].get(papel[3:])
        if not p:
            return None
        return {"papel": papel, "modelo": p["modelo"], "motivo": "persona %s em personas.json (%s)"
                % (papel[3:], p.get("quando", ""))}
    if papel not in rt:
        return None
    t = L.ler_task(task) if task else None
    cfg = rt[papel]
    if papel == "executor":
        if ciclo >= 2:
            return {"papel": papel, "modelo": cfg["ciclo_2_ou_mais"],
                    "motivo": "ciclo %d: retentativa sempre em %s" % (ciclo, cfg["ciclo_2_ou_mais"])}
        if t and (t["cab"].get("complexidade") or "").strip() == "baixa":
            ok, motivos = C.complexidade_ok(t)
            if ok:
                return {"papel": papel, "modelo": cfg["baixa"],
                        "motivo": "complexidade: baixa VÁLIDA (≤2 arquivos, sem área sensível/protocolo, verificação "
                                  "concreta)"}
            return {"papel": papel, "modelo": cfg["padrao"],
                    "motivo": "complexidade: baixa declarada mas INVÁLIDA (%s) ⇒ padrão" % "; ".join(motivos)}
        return {"papel": papel, "modelo": cfg["padrao"], "motivo": "executor ciclo 1: padrão"}
    if papel == "revisor" and t:
        sens = [a for a in L.arquivos_reais(t) if L.sensivel(a)]
        if sens:
            return {"papel": papel, "modelo": cfg["sensivel"], "motivo": "toca área sensível: %s" % ", ".join(sens)}
    return {"papel": papel, "modelo": cfg["padrao"], "motivo": cfg.get("porque", "padrão do papel")}


# ------------------------------------------------------------------ plano / próxima

def features_com_tasks(r, so=None):
    out = []
    for x in L.features(r)["ativas"]:
        if so and x["id"] != so:
            continue
        fd = L.feature_dir(x["id"], r)
        out.append((x, L.ler_tasks(fd), L.ler_feature(L.feature_md(fd))))
    return out


def sequencial_declarado(fr):
    return bool(fr) and "execução: sequencial" in fr["txt"].lower()


def proxima_de(fid, tasks, fr, r):
    el = L.elegiveis(tasks)
    bloqueio = None
    if any(t["tipo"] == "CORRECAO" for t in el) and not L.ac_ok(fid, "intake.3", r):
        el = [t for t in el if t["tipo"] != "CORRECAO"]
        bloqueio = "aprovacao_founder"
    if len(el) >= 2 and not sequencial_declarado(fr):
        arqs = [set(L.arquivos_reais(t)) for t in el]
        disj = all(not (arqs[i] & arqs[j]) for i in range(len(arqs)) for j in range(i + 1, len(arqs)))
        top = "paralelo" if disj else "sequencial"
    else:
        top = "sequencial" if el else "—"
    if not el and not bloqueio and tasks and len(L.feitas(tasks)) == len(tasks):
        bloqueio = "aceite_humano"
    return [t["stem"] for t in el], bloqueio, top


def caminho_critico(tasks):
    por_id = {t["stem"]: t for t in tasks}
    memo = {}

    def mais_longo(i, pilha=frozenset()):
        if i in memo:
            return memo[i]
        if i in pilha or i not in por_id:
            return [i] if i in por_id else []
        melhor = []
        for d, _ in por_id[i]["depends"]:
            c = mais_longo(d, pilha | {i})
            if len(c) > len(melhor):
                melhor = c
        memo[i] = melhor + [i]
        return memo[i]

    alvos = [t["stem"] for t in tasks if t["tipo"] == "REVIEW"] or [t["stem"] for t in tasks]
    melhor = []
    for a in alvos:
        c = mais_longo(a)
        if len(c) > len(melhor):
            melhor = c
    return melhor


def plano_feature(x, tasks, fr, r):
    fid = x["id"]
    if not tasks:
        return {"id": fid, "origem": x.get("origem"), "progresso": "—", "proxima": None, "elegiveis": [],
                "bloqueio": "feature_legada_sem_tasks", "topologia": "—", "caminho_critico": [],
                "gates_humanos": ["aceite_humano", "frase_conferir"], "despacho": None}
    el, bloq, top = proxima_de(fid, tasks, fr, r)
    gates = []
    if not L.ac_ok(fid, "intake.3", r):
        gates.append("aprovacao_founder")
    gates += ["aceite_humano", "frase_conferir"]
    prox = el[0] if el else None
    desp = None
    if prox:
        t = next(t for t in tasks if t["stem"] == prox)
        papel = PAPEL_DO_TIPO.get(t["tipo"], "executor")
        m = modelo(papel, 1, t["arquivo"])
        desp = {"papel": papel, "modelo": m["modelo"], "motivo": m["motivo"], "task": prox}
    return {"id": fid, "origem": x.get("origem"), "progresso": L.progresso(tasks), "proxima": prox,
            "elegiveis": el, "bloqueio": bloq, "topologia": top, "caminho_critico": caminho_critico(tasks),
            "gates_humanos": gates, "despacho": desp}


def cmd_plano(a, r):
    if not a.modo:
        obj = {"precisa_modo": True, "opcoes": list(MODOS), "pergunta": PERGUNTA}
        if a.json:
            print(json.dumps(obj, ensure_ascii=False))
        else:
            print(PERGUNTA)
        return 2
    fs = [plano_feature(x, t, fr, r) for x, t, fr in features_com_tasks(r, a.feature)]
    obj = {"modo": a.modo, "features": fs}
    linhas = ["Modo: %s · features ativas: %d" % (a.modo, len(fs))]
    for f in fs:
        linhas.append("%s · %s · próxima: %s · topologia: %s%s" % (f["id"], f["progresso"], f["proxima"] or "—",
                                                                  f["topologia"], " · BLOQUEIO: %s" % f["bloqueio"]
                                                                  if f["bloqueio"] else ""))
        if f["caminho_critico"]:
            linhas.append("  caminho crítico: " + " → ".join(f["caminho_critico"]))
        linhas.append("  gates humanos: " + ", ".join(f["gates_humanos"]))
        if f["despacho"]:
            d = f["despacho"]
            linhas.append("  despacho: %s (%s) em %s — %s" % (d["task"], d["papel"], d["modelo"], d["motivo"]))
    if not fs:
        linhas.append("nenhuma feature ativa — IDLE: pergunte ao founder qual feature criar (criar-feature)")
    t = "\n".join(linhas)
    L.saida(obj, a, t, t)
    return 0


def cmd_proxima(a, r):
    fs = features_com_tasks(r, a.feature)
    fs = [f for f in fs if f[1]] or fs
    if not fs:
        L.saida({"feature": None, "elegiveis": [], "bloqueio": "sem_feature_ativa", "topologia": "—"}, a,
                "nenhuma feature ativa")
        return 0
    x, tasks, fr = fs[0]
    el, bloq, top = proxima_de(x["id"], tasks, fr, r)
    obj = {"feature": x["id"], "elegiveis": el, "bloqueio": bloq, "topologia": top}
    L.saida(obj, a, "%s · elegíveis: %s · topologia: %s%s" % (x["id"], ", ".join(el) or "—", top,
                                                              " · bloqueio: %s" % bloq if bloq else ""))
    return 0


def cmd_modelo(a, r):
    m = modelo(a.papel, a.ciclo, a.task)
    if not m:
        print("papel desconhecido: %s (executor|revisor|qa|review|oraculo|rh:<persona>)" % a.papel, file=sys.stderr)
        return 2
    L.saida(m, a, "%s → %s (%s)" % (m["papel"], m["modelo"], m["motivo"]))
    return 0


# ------------------------------------------------------------------ snap

def fotografar(r, d=None, excluir=()):
    out = {}
    exc = {os.path.realpath(x) for x in excluir if x}
    if d:
        base = os.path.realpath(d)
        for dd, dirs, fs in os.walk(base):
            dirs[:] = [x for x in dirs if x not in (".git", "__pycache__")]
            for f in fs:
                p = os.path.join(dd, f)
                if os.path.realpath(p) in exc or f.endswith(".pyc"):
                    continue
                out[os.path.relpath(p, base)] = _hash(p)
        return out
    rc, s, _ = L.git(r, "status", "--porcelain", "--untracked-files=all")
    for linha in s.splitlines():
        if len(linha) < 4:
            continue
        p = linha[3:].split(" -> ")[-1].strip().strip('"')
        ap = os.path.join(r, p)
        if os.path.realpath(ap) in exc:
            continue
        out[p] = linha[:2] + ":" + (_hash(ap) if os.path.isfile(ap) else "<ausente>")
    return out


def _hash(p):
    try:
        with open(p, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return "<ilegivel>"


def cmd_snap(a, r):
    if a.out:
        f = fotografar(r, a.dir, (a.out,))
        L.gravar(os.path.abspath(a.out), json.dumps({"dir": a.dir or r, "arquivos": f}, ensure_ascii=False, indent=0))
        print("snapshot: %d arquivo(s) em %s" % (len(f), a.out))
        return 0
    if a.comparar:
        antes = json.loads(L.ler(a.comparar, "{}")).get("arquivos", {})
        agora = fotografar(r, a.dir, (a.comparar,))
        mudou = sorted(k for k in set(antes) | set(agora) if antes.get(k) != agora.get(k))
        L.saida({"mudou": mudou}, a, "nada mudou desde o snapshot" if not mudou else
                "MUDOU (%d): %s" % (len(mudou), ", ".join(mudou[:20])))
        return 1 if mudou else 0
    print("snap exige --out ARQ ou --comparar ARQ", file=sys.stderr)
    return 3


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tech_lead.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("plano")
    s.add_argument("--modo", choices=MODOS)
    s.add_argument("--feature")
    s.add_argument("--json", action="store_true")
    s.add_argument("--brief", action="store_true")
    s = sub.add_parser("proxima")
    s.add_argument("--feature")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("modelo")
    s.add_argument("--papel", required=True)
    s.add_argument("--ciclo", type=int, default=1)
    s.add_argument("--task")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("snap")
    s.add_argument("--out")
    s.add_argument("--comparar")
    s.add_argument("--dir")
    s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    r = L.raiz()
    fn = {"plano": cmd_plano, "proxima": cmd_proxima, "modelo": cmd_modelo, "snap": cmd_snap}.get(a.cmd)
    if not fn:
        ap.print_help()
        return 0
    return fn(a, r)


if __name__ == "__main__":
    sys.exit(main())
