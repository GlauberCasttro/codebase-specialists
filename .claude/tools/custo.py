#!/usr/bin/env python3
"""custo.py — custo MEDIDO por despacho de subagente (skill tech-lead): lê só o `usage` do transcript do subagente.

Subcomandos:
  medir <agentId> [--transcript ARQ] [--projects-dir DIR] [--json]
        acha o transcript `agent-<agentId>.jsonl` sob --projects-dir (padrão: ~/.claude/projects) — 0 ou 2+ achados
        ⇒ exit 1 (nunca chuta qual) — e soma por turno do assistente: turnos, contexto_primeiro_turno, contexto_somado
        (input + cache de criação + cache de leitura, por turno), cache_leitura, cache_escrita, saida, modelos,
        linhas_invalidas. NUNCA imprime conteúdo de mensagem.
  registrar <agentId> --feature F --task T --papel P --modelo M [--transcript|--projects-dir] [--json]
        apensa uma linha em .claude/state/logs/custo.jsonl: status OK com os números, ou NOT_RUN com o motivo e SEM
        números (nunca estimado). Sempre exit 0: falta de medida é dado, não erro.
  resumo --feature F [--json]
        por modelo PEDIDO (o que o tech-lead passou ao Agent): despachos, turnos, contexto_somado, saida, caches;
        e quantos NOT_RUN.
Exit: 0 ok · 1 não mediu · 3 uso. Variável de teste: CS_DEV_SKILL_DIR.
"""
import argparse
import json
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import estado_lib as L  # noqa: E402

NUMEROS = ("turnos", "contexto_primeiro_turno", "contexto_somado", "cache_leitura", "cache_escrita", "saida")


class SemMedida(Exception):
    pass


def achar(agent, transcript, projects):
    if transcript:
        if not os.path.isfile(transcript):
            raise SemMedida("transcript não existe: %s" % transcript)
        return transcript
    base = projects or os.path.join(os.path.expanduser("~"), ".claude", "projects")
    alvo = "agent-%s.jsonl" % agent
    achados = []
    for d, _, fs in os.walk(base):
        if alvo in fs:
            achados.append(os.path.join(d, alvo))
    if len(achados) != 1:
        raise SemMedida("%d transcript(s) %s sob %s (preciso de exatamente 1)" % (len(achados), alvo,
                                                                                    "--projects-dir" if projects else "~/.claude/projects"))
    return achados[0]


def medir(agent, transcript=None, projects=None):
    p = achar(agent, transcript, projects)
    r = {k: 0 for k in NUMEROS}
    r.update({"modelos": [], "linhas_invalidas": 0})
    vistos = set()
    with open(p, encoding="utf-8", errors="replace") as fh:
        for linha in fh:
            if not linha.strip():
                continue
            try:
                e = json.loads(linha)
            except ValueError:
                r["linhas_invalidas"] += 1
                continue
            m = e.get("message") if isinstance(e, dict) else None
            if not isinstance(m, dict) or e.get("type") != "assistant" or not isinstance(m.get("usage"), dict):
                continue
            mid = m.get("id")
            if mid:
                if mid in vistos:   # o mesmo turno pode vir em várias linhas (um bloco de conteúdo por linha)
                    continue
                vistos.add(mid)
            u = m["usage"]
            ent = int(u.get("input_tokens") or 0)
            cw = int(u.get("cache_creation_input_tokens") or 0)
            cr = int(u.get("cache_read_input_tokens") or 0)
            ctx = ent + cw + cr
            if r["turnos"] == 0:
                r["contexto_primeiro_turno"] = ctx
            r["turnos"] += 1
            r["contexto_somado"] += ctx
            r["cache_leitura"] += cr
            r["cache_escrita"] += cw
            r["saida"] += int(u.get("output_tokens") or 0)
            if m.get("model") and m["model"] not in r["modelos"]:
                r["modelos"].append(m["model"])
    return r


def cmd_medir(a):
    try:
        r = medir(a.agent, a.transcript, a.projects_dir)
    except SemMedida as e:
        print("NOT_RUN: %s" % e, file=sys.stderr)
        return 1
    L.saida(r, a, "%s: %d turnos · contexto 1º turno %d · somado %d · saída %d · modelos %s · linhas inválidas %d"
            % (a.agent, r["turnos"], r["contexto_primeiro_turno"], r["contexto_somado"], r["saida"],
               ",".join(r["modelos"]) or "—", r["linhas_invalidas"]))
    return 0


def cmd_registrar(a):
    reg = {"ts": L.agora(), "agente": a.agent, "feature": a.feature, "task": a.task, "papel": a.papel,
           "modelo": a.modelo}
    try:
        reg.update(medir(a.agent, a.transcript, a.projects_dir))
        reg["status"] = "OK"
    except SemMedida as e:
        reg["status"] = "NOT_RUN"
        reg["motivo"] = str(e)
    L.apensar(os.path.join(L.state(), "logs", "custo.jsonl"), json.dumps(reg, ensure_ascii=False) + "\n")
    L.saida(reg, a, "custo %s de %s/%s (%s, %s)%s" % (reg["status"], a.feature, a.task, a.papel, a.modelo,
                                                     " — " + reg.get("motivo", "") if reg["status"] != "OK" else
                                                     ": %d turnos · contexto %d" % (reg["turnos"], reg["contexto_somado"])))
    return 0


def cmd_resumo(a):
    por, nr = {}, 0
    t = L.ler(os.path.join(L.state(), "logs", "custo.jsonl"), "")
    for linha in t.splitlines():
        try:
            e = json.loads(linha)
        except ValueError:
            continue
        if e.get("feature", e.get("frente")) != a.feature:  # COMPAT: ledger antigo gravava "frente"
            continue
        if e.get("status") != "OK":
            nr += 1
            continue
        m = por.setdefault(e.get("modelo") or "?", {"despachos": 0, "turnos": 0, "contexto_somado": 0, "saida": 0,
                                                    "cache_leitura": 0, "cache_escrita": 0})
        m["despachos"] += 1
        for k in ("turnos", "contexto_somado", "saida", "cache_leitura", "cache_escrita"):
            m[k] += int(e.get(k) or 0)
    obj = {"feature": a.feature, "por_modelo": por, "not_run": nr}
    L.saida(obj, a, "custo da feature %s: %s · NOT_RUN %d" % (a.feature, "; ".join(
        "%s: %d despachos / %d turnos / contexto %d" % (k, v["despachos"], v["turnos"], v["contexto_somado"])
        for k, v in sorted(por.items())) or "nenhum medido", nr))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="custo.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    for n in ("medir", "registrar"):
        s = sub.add_parser(n)
        s.add_argument("agent")
        s.add_argument("--transcript")
        s.add_argument("--projects-dir")
        s.add_argument("--json", action="store_true")
        if n == "registrar":
            for f in ("--feature", "--task", "--papel", "--modelo"):
                s.add_argument(f, required=True)
    s = sub.add_parser("resumo")
    s.add_argument("--feature", required=True)
    s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    fn = {"medir": cmd_medir, "registrar": cmd_registrar, "resumo": cmd_resumo}.get(a.cmd)
    if not fn:
        ap.print_help()
        return 0
    return fn(a)


if __name__ == "__main__":
    sys.exit(main())
