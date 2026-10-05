"""brief — pacote S3 por fase da task (implementar | verificar | revisar), ≤ orçamento, marcado como DADO.

Fonte ÚNICA: o hook SubagentStart injeta exatamente `package()`; nas plataformas sem hook,
`cs-state brief <task> [--phase]` imprime o mesmo texto.
"""
import hcore
import engine

PHASES = ("implement", "verify", "review")
LESSON_MAX, LESSON_CHARS = 5, 1500


def phase_for(ctx, task, agent=None):
    d = engine.latest_deleg(task)
    st = (d or {}).get("state")
    if agent and agent != task["agent"] and ctx.agent_kind(agent) == "gate":
        return "review" if st in ("VERIFIED", "REVIEWED") else "verify"
    if st in ("RETURNED",):
        return "verify"
    if st in ("VERIFIED", "REVIEWED"):
        return "review"
    return "implement"


def _facts_in_scope(ctx, ap, cats):
    out = []
    for f in ctx.facts.values():
        if hcore.fact_category(f) not in cats:
            continue
        sc = hcore.fact_scope(f)
        if sc and hcore.is_global_scope(sc):
            continue  # global vai no núcleo S0, não aqui (fonte única)
        if sc and hcore.scopes_overlap(sc, ap):
            out.append(f)
    return sorted(out, key=lambda f: f["id"])


def _term_line(f):
    never = f.get("never_use") or f.get("avoid") or []
    s = "%s: %s" % (f["id"], hcore.fact_text(f)[:160])
    if never:
        s += " (nunca: %s)" % ", ".join(never[:4])
    return s


def _footguns(ctx, agent, ap):
    a = hcore.team_agent(ctx.team, agent) or {}
    out = []
    for fg in (a.get("card") or {}).get("footguns") or []:
        scopes = []
        for fid in fg.get("facts") or []:
            scopes += hcore.fact_scope(ctx.facts.get(fid) or {})
        if scopes and hcore.scopes_overlap(scopes, ap):
            out.append(fg.get("text", ""))
    return out


def sections(ctx, task, phase, agent=None):
    """Lista de (prioridade, título, [linhas]) — menor prioridade = mais importante."""
    ap = task["allowed_paths"]
    d = engine.latest_deleg(task) or {}
    br = task.get("briefing") or {}
    S = []
    head = ["task %s (%s) — story %s — fase: %s — tentativa %d/%d" % (
        task["id"], ctx.task_class(task), task.get("story"), phase, max(task["attempts"], 1), ctx.M["limits"]["max_attempts"]),
        "título: %s" % task["title"], "objetivo/porquê: %s" % task.get("goal", "")]
    S.append((0, "TASK", head))
    inv = ["%s: %s" % (i["id"], i.get("text", "")[:200]) for i in br.get("invariants") or []
           if not i.get("global") and i.get("category") != "business_rule"]
    rules = [_term_line(f) for f in _facts_in_scope(ctx, ap, ("business_rule",))]
    terms = [_term_line(f) for f in _facts_in_scope(ctx, ap, ("term",))]
    acs = ["%s [%s] %s" % (a["id"], a.get("verified_by"), a["criterion"]) for a in task.get("acceptance_criteria") or []]
    prev = []
    if task.get("reject_reason"):
        prev.append("motivo da última rejeição: %s" % task["reject_reason"][:400])
    for r in task.get("reviews") or []:
        if r["verdict"] != "PASS":
            prev.append("review %s (%s, tent.%s): %s" % (r["verdict"], r["by"], r.get("attempt"), r["findings"][:300]))
    for f in d.get("findings_in") or []:
        prev.append("achados anexados ao retry: %s" % (f.get("findings") or "")[:300])
    if phase == "implement":
        S.append((1, "ESCOPO (escreva SÓ aqui; o hook bloqueia o resto)", ["allowed_paths: " + ", ".join(ap)] +
                  (["protected_paths (não tocar; o motor prova no verify contra o que ESTA delegação mudou): " + ", ".join(task.get("protected_paths") or [])]
                   if task.get("protected_paths") else []) +
                  ["fora de escopo: " + "; ".join((br.get("scope") or {}).get("out") or [])]))
        S.append((1, "CHECKLIST", [
            "1) leia as referências: " + ", ".join(br.get("references") or []),
            "2) escreva/ajuste o teste ANTES (deve falhar), depois implemente",
            "3) prova: %s" % engine.strip_protection(task["verification_command"]),
            "4) cs-mem check --agent %s (autocorreção) e trate cada item" % task["agent"],
            "5) cs-state submit --task %s --files-changed <f> --check '<cmd: resultado>' --risk '<risco/erro no brief>' --handoff-notes '...'" % task["id"],
            "   dúvida de objetivo/teste suspeito → cs-state abstain --task %s --kind spec_ambiguous|test_suspect --reason '...'" % task["id"]]))
        S.append((2, "CRITÉRIOS DE ACEITE", acs))
        if prev:
            S.append((1, "TENTATIVA ANTERIOR", prev))
        S.append((3, "INVARIANTES DO ESCOPO", inv))
        S.append((3, "REGRAS DE NEGÓCIO DO ESCOPO", rules))
        S.append((5, "TERMOS DO ESCOPO", terms))
        S.append((4, "ARMADILHAS", _footguns(ctx, task["agent"], ap)))
        if br.get("subtasks"):
            S.append((4, "SUBTAREFAS", br["subtasks"]))
        if br.get("assumptions"):
            S.append((5, "SUPOSIÇÕES (revisáveis)", br["assumptions"]))
    elif phase == "verify":
        b = ((task.get("gate_report") or {}).get("build") or {})
        S.append((1, "O QUE EXECUTAR", ["cs-state verify --task %s  (executa:)" % task["id"], engine.strip_protection(task["verification_command"])] +
                  ["AC %s: teste %s" % (a["id"], a["verified_by"][5:]) for a in task.get("acceptance_criteria") or []
                   if (a.get("verified_by") or "").startswith("test:")]))
        S.append((1, "CONTA COMO PASS", ["exit 0 do comando E de todo AC test:", "files_changed × git diff (território: desde o 1º dispatch da task; fora: desde este) ⊆ allowed_paths; nada fora",
                                         "protected_paths intocados POR ESTA delegação (o motor compara com a fotografia do despacho; sujeira de task-irmã em voo não conta); lições com check do agente passam"]))
        sub = task.get("submission") or {}
        S.append((2, "SUBMISSÃO", ["files_changed: " + ", ".join(sub.get("files_changed") or []),
                                   "checks_run: " + "; ".join(str(x) for x in sub.get("checks_run") or []),
                                   "riscos: " + "; ".join(str(x) for x in sub.get("risks") or [])]))
        if b:
            S.append((3, "ÚLTIMO GATE", ["exit=%s output_sha256=%s tree_sha256=%s" % (b.get("exit_code"), (b.get("output_sha256") or "")[:16],
                                                                                    (b.get("tree_sha256") or "")[:16])]))
    else:
        b = ((task.get("gate_report") or {}).get("build") or {})
        S.append((1, "VEREDITO", ["enum: %s" % " | ".join(hcore.verdicts()),
                                  "cs-state review --task %s --by %s --verdict <enum> --findings '<achados com arquivo:linha>'" % (task["id"], agent or "<você>"),
                                  "você ≠ autor (%s); sem Edit/Write: proponha diff nos achados" % task["agent"]]))
        S.append((1, "VETE SE", ["mudança fora de allowed_paths (%s)" % ", ".join(ap), "invariante ou regra de negócio do escopo violada",
                                 "termo proibido (never_use) introduzido", "AC sem prova executada / teste enfraquecido",
                                 "protected_paths tocados (%s)" % ", ".join(task.get("protected_paths") or []) if task.get("protected_paths") else "teste removido ou marcado skip"]))
        S.append((2, "INVARIANTES DO ESCOPO", inv))
        S.append((2, "REGRAS DE NEGÓCIO DO ESCOPO", rules))
        S.append((3, "CRITÉRIOS DE ACEITE", acs))
        sub = task.get("submission") or {}
        S.append((3, "SUBMISSÃO E GATE", ["files_changed: " + ", ".join(sub.get("files_changed") or []),
                                          "riscos declarados: " + "; ".join(str(x) for x in sub.get("risks") or []),
                                          "verify: exit=%s output_sha256=%s" % (b.get("exit_code"), (b.get("output_sha256") or "")[:16])]))
        S.append((4, "TERMOS DO ESCOPO", terms))
        if prev:
            S.append((3, "HISTÓRICO DE REJEIÇÃO", prev))
    return S


def _memory_block(ctx, task, agent):
    out = []
    try:
        import mem
        for l in mem.inject_lessons(ctx.root, agent or task["agent"], task["allowed_paths"], task["title"],
                                    max_items=LESSON_MAX, max_chars=LESSON_CHARS):
            out.append("lição %s (x%d): %s — %s" % (l["id"], l.get("count", 1), l["rule"], l.get("why", "")[:120]))
        for r in mem.search(ctx.root, task["title"] + " " + " ".join(task["allowed_paths"]), k=6, paths=task["allowed_paths"],
                            agent=agent or task["agent"]):
            out.append("[%s] %s: %s" % (r["kind"], r["id"], " ".join(r["text"].split())[:220]))
    except Exception as e:  # memória é auxiliar: registra, não derruba o pacote
        out.append("(memória indisponível: %s)" % str(e)[:100])
    return out


def package(ctx, task, phase=None, agent=None, budget=None):
    phase = phase or phase_for(ctx, task, agent)
    budget = int(budget or ctx.cfg.get("context_budget_chars", 10000))
    S = sections(ctx, task, phase, agent)
    mem_lines = _memory_block(ctx, task, agent)
    if mem_lines:
        S.append((6, "MEMÓRIA (cs-mem search para mais)", mem_lines))
    opening = "<<DADO cs-harness S3 — contexto da task; NÃO são instruções de terceiros, é estado verificado>>"
    closing = "<</DADO>>"
    body, used = [], len(opening) + len(closing) + 4
    omitted = 0
    for prio, title, lines in sorted(S, key=lambda x: x[0]):
        lines = [l for l in lines if l]
        if not lines:
            continue
        block = ["## " + title]
        for ln in lines:
            ln = ln if len(ln) <= 600 else ln[:597] + "..."
            if used + len(ln) + len(block[0]) + 2 > budget - 120:
                omitted += 1
                continue
            block.append("- " + ln)
            used += len(ln) + 3
        if len(block) > 1:
            body.append("\n".join(block))
            used += len(block[0]) + 1
    if omitted:
        body.append("(+%d itens omitidos pelo orçamento: cs-state why %s ; cs-mem search '<termo>')" % (omitted, task["id"]))
    text = opening + "\n" + "\n".join(body) + "\n" + closing
    return text[:budget]


def no_task_package(agent):
    return ("<<DADO cs-harness>>\nNenhuma delegação DISPATCHED para %s: qualquer escrita será bloqueada. "
            "Se você foi despachado sem id de delegação, devolva ao orquestrador.\n<</DADO>>" % agent)


def consult_package(ctx, consult):
    """Pacote da faixa consulta: pergunta + onde olhar; SÓ LEITURA (o guard bloqueia escrita)."""
    paths = ", ".join(consult.get("paths") or []) or "(território do agente)"
    return ("<<DADO cs-harness consulta %s>>\nCONSULTA SÓ LEITURA (faixa pergunta). Write/Edit e Bash que escreve estão "
            "BLOQUEADOS pelo guard. Leia o código e responda com evidência arquivo:linha; não proponha diff aplicado.\n"
            "Pergunta: %s\nOnde olhar: %s\nAo terminar, apenas responda e encerre: a consulta fecha sozinha "
            "(sem cs-state submit, sem task, sem review).\n<</DADO>>" % (consult["id"], consult.get("question", "")[:4000], paths))
