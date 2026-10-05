"""`cs.py report [--check]` — relatório final (approve.1) montado do DISCO, nunca da conversa.

Ordem: decisão (GO | GO (simulado) | NO-GO | pendente) em uma linha; pulos (caminho --fast); tabela do time
(placar da sonda, status, modo fechado como SINAL); garantia por plataforma (hook × instructions); lacunas
declaradas (gap.*); gates vermelhos. Grava `.swarm/report.md` com o sha do acceptance que descreveu —
`report --check` (check de approve.1) falha se o acceptance mudou depois.
"""
import os
import re

from facts import store

MARK = "<!-- cs-report acceptance=%s -->"
MARK_RE = re.compile(r"<!-- cs-report acceptance=([0-9a-f]+|none) -->")
ENF_TEXT = {"hook": "hook: bloqueia ANTES da escrita/despacho (guards cs-guard.sh); programa arbitrário só é pego "
                    "depois (verify)",
            "instructions": "instruções + estado por CLI; nada impede a escrita na hora — `cs-state verify` e o "
                            "pre-commit (`cs-precommit`) detectam e reprovam DEPOIS"}


def report_path(target):
    return store.sp(target, "report.md")


def _decision_line(acc, run):
    if acc is None:
        return "Decisão: pendente — `cs.py verify` ainda não rodou"
    gates = acc.get("decision")
    if acc.get("approval_decision"):
        sim = " (simulado)" if acc.get("approval") == "simulated" else ""
        line = "Decisão: %s%s — gates %s; decidido por %s em %s" % (
            acc["approval_decision"], sim, gates, acc.get("approval_by"), acc.get("approval_at"))
        if sim:
            line += " (sem humano: aprovação SIMULADA, não vale como aceite do dono)"
        return line
    return "Decisão: pendente do founder — gates %s (`cs.py approve --by <nome> --decision GO|NO-GO`)" % gates


def _fmt(x):
    return "-" if x is None else str(x)


def build(target):
    from stage import engine
    from verify.gates import acceptance_sha
    acc = store.read5(store.sp(target, "acceptance.json5"), required=False, default=None)
    run = store.read5(store.sp(target, "run.json5"), required=False, default=None) or {}
    team = store.read5(store.sp(target, "team.json5"), required=False, default=None) or {}
    rep = store.read5(store.sp(target, "probes", "report.json5"), required=False, default=None) or {}
    lines = [MARK % (acceptance_sha(acc) if acc else "none"), "# Relatório codebase-specialists", "",
             _decision_line(acc, run), ""]
    skips = engine.skipped(run)
    if skips:
        lines += ["Modo: --fast (padrão: sem mesa redonda e/ou sem refino; %d sub-etapa(s) pulada(s))" % len(skips),
                  ""]
    else:
        lines += ["Modo: --full (execução certificada completa: mesa redonda e refino rodaram)", ""]
    if skips:
        lines += ["## Pulos (caminho --fast)", "",
                  "Modo --fast: sem mesa redonda e/ou com sondas reduzidas — time NÃO certificado como especialista.",
                  ""]
        lines += ["- `%s` (%s): %s" % (s["id"], s["stage"], s["reason"]) for s in skips] + [""]
    lines += ["## Time", "", "| agente | kind | território | território (sonda) | cross | alucinações | delta | status "
              "| modo fechado (sinal) |", "|---|---|---|---|---|---|---|---|---|"]
    agg = rep.get("agents") or {}
    for a in team.get("agents") or []:
        r = agg.get(a.get("name")) or {}
        cm = r.get("closed_mode") or {}
        closed = "%s / %s aluc." % (_fmt(cm.get("score")), _fmt(cm.get("hallucinations"))) if cm else "-"
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            a.get("name"), a.get("kind"), ", ".join("`%s`" % g for g in a.get("territory") or []) or "sem escrita",
            _fmt(r.get("score_territory")) + (" (baseline_saturated)" if r.get("baseline_saturated") else ""),
            _fmt(r.get("score_cross")), _fmt(r.get("hallucinations")),
            _fmt(r.get("delta")), r.get("status") or r.get("decision") or "não examinado", closed))
    if any((r or {}).get("closed_mode") for r in agg.values()):
        lines += ["", "Modo fechado = só o cartão, sem o repositório: o cartão é MAPA (aponta onde está), não "
                      "memória. Score baixo ali é esperado e NÃO entra no G4."]
    if any((r or {}).get("baseline_saturated") for r in agg.values()):
        lines += ["", "baseline_saturated: o baseline sem cartão acertou todas as sondas daquele escopo — não medido "
                      "≠ reprovado; vale o score sem filtro."]
    allowed = ((rep.get("final") or {}).get("allowed")) or None
    if allowed:
        lines += ["", "Não-especialistas aceitos: %s — motivo: %s (com nao-especialista a decisão é NO-GO)" % (
            ", ".join(allowed.get("agents") or []), allowed.get("reason"))]
    enf = (acc or {}).get("enforcement") or {}
    lines += ["", "## Garantia por plataforma", "", "| plataforma | enforcement | o que garante |", "|---|---|---|"]
    for p, mode in sorted(enf.items()):
        lines.append("| %s | %s | %s |" % (p, mode, ENF_TEXT.get(mode, mode)))
    if not enf:
        lines.append("| - | - | rode `cs.py verify` |")
    gaps = [f for fid, f in sorted(store.load_all_facts(target).items()) if fid.startswith("gap.")]
    lines += ["", "## Lacunas declaradas (o dono não soube responder)", ""]
    lines += ["- %s" % ((f.get("data") or {}).get("question") or f.get("claim")) for f in gaps] or ["- nenhuma"]
    red = [g for g in (acc or {}).get("gates") or [] if not g.get("passed")]
    if red:
        lines += ["", "## Gates vermelhos", ""] + ["- %s %s — %s" % (g["id"], g["name"], g["evidence"][:200])
                                                  for g in red]
    lines += ["", "## Como usar", "",
              "`.swarm/bin/cs-state next` · `.swarm/bin/cs-mem search \"<assunto>\"` · "
              "`.swarm/bin/cs-session save|load`", ""]
    return "\n".join(lines)


def write(target):
    text = build(target)
    p = report_path(target)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, p)
    return text


def check(target):
    """approve.1 (efeito): relatório gerado sobre o acceptance ATUAL (sem contar o registro da aprovação)."""
    from verify.gates import acceptance_sha
    p = report_path(target)
    if not os.path.isfile(p):
        return False, "report.md ausente (rode `cs.py report`)"
    with open(p, "r", encoding="utf-8") as fh:
        m = MARK_RE.search(fh.readline())
    acc = store.read5(store.sp(target, "acceptance.json5"), required=False, default=None)
    want = acceptance_sha(acc) if acc else "none"
    if not m or m.group(1) != want:
        return False, "report.md descreve outro acceptance (verify rodou depois): rode `cs.py report`"
    return True, "report.md sobre o acceptance atual"
