"""`probes check --all [--final]` e `probes baseline-filter --check` (validate.2–validate.4).

Ciclos: .swarm/probes/cycles.json5 = {<agente>: [{at, probes_sha256, answers_sha256, decision, retakes}]}.
Um ciclo = um exame com um conjunto de sondas DIFERENTE dos anteriores (sondas novas a cada refino).
Re-pontuar o mesmo conjunto (respostas novas para as mesmas sondas) não abre ciclo: conta como `retakes`.
Regra de 2 ciclos (--final): exame inicial + MAX_REFINE_CYCLES refinos; agente que ainda reprova depois
disso vira `nao-especialista` no report.json5 e o check falha, salvo `--allow-non-specialist --reason`
(registrado em report.json5 `final.allowed` para exatamente aquele conjunto de agentes).
"""
import hashlib
import json
import os

from cslib import log as cslog
from team._shared_tmp.common import CsError, find_doc, read_json, sp_path, write_json
from probes.generate import load_bank

MAX_REFINE_CYCLES = 2


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def answers_path(target, agent):
    return sp_path(target, "probes", "exams", "%s.answers.json5" % agent)


def cycles_path(target):
    return sp_path(target, "probes", "cycles.json5")


def load_cycles(target):
    p = cycles_path(target)
    return read_json(p, "cycles.json5") if os.path.isfile(find_doc(p)) else {}


def bank_agents(bank):
    names = set(bank.get("agents") or {}) | set(p["agent"] for p in bank.get("probes") or [])
    return sorted(names)


def agent_probes_sha(bank, agent):
    return _sha([{k: p.get(k) for k in ("id", "question", "answer")} for p in bank["probes"] if p["agent"] == agent])


def _answers_sha(answers_file):
    with open(find_doc(answers_file), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def stale_reason(target, bank, agent, answers_file):
    """Respostas produzidas para OUTRO conjunto de sondas (iteração 2: `check --all` depois de `generate`
    repontuou respostas velhas e esgotou agentes sem refino). → motivo ou None. Resposta vazia não é velha."""
    from probes.exam import _load_answers
    answers = _load_answers(answers_file)
    if not answers:
        return None
    ids = set(p["id"] for p in bank["probes"] if p["agent"] == agent)
    hit = sum(1 for k in answers if k in ids)
    if hit * 2 < len(answers):
        return "%d de %d respostas são de sondas fora do banco atual" % (len(answers) - hit, len(answers))
    psha = agent_probes_sha(bank, agent)
    asha = _answers_sha(answers_file)
    for c in load_cycles(target).get(agent) or []:
        if c.get("answers_sha256") == asha and c.get("probes_sha256") != psha:
            return "as mesmas respostas já foram pontuadas num banco anterior (ciclo de %s)" % c.get("at")
    from probes.generate import load_issued
    issued = load_issued(target).get(agent)
    try:
        mtime = os.path.getmtime(find_doc(answers_file))
    except OSError:
        mtime = None
    if issued and mtime is not None and mtime + 1.0 < float(issued):
        return "respostas gravadas antes das sondas atuais deste agente (banco reemitido depois)"
    return None


def passed_before(target, bank, agent):
    """Ciclo PASS registrado num banco ANTERIOR (sondas diferentes das atuais) → o ciclo, senão None."""
    psha = agent_probes_sha(bank, agent)
    for c in reversed(load_cycles(target).get(agent) or []):
        if c.get("decision") == "PASS" and c.get("probes_sha256") != psha:
            return c
    return None


def pack_card_drift(target, agent, shas=None):
    """Pacote de exame (`exam-pack`) emitido para OUTRO cartão: `card_sha256` gravado no pacote (mesmo hash de
    cards/status.json5 e de `card_sha256` dos ciclos) ≠ cartão atual → motivo (exame obsoleto: reexame), senão
    None. Pacote sem o campo (emitido antes desta regra) ou ausente: None (vale `card_drift` dos ciclos)."""
    p = sp_path(target, "probes", "exams", "%s.questions.json5" % agent)
    if not os.path.isfile(find_doc(p)):
        return None
    try:
        pack = read_json(p, "pacote de exame")
    except CsError:
        return None
    if "card_sha256" not in pack:
        return None
    cur = (card_shas(target) if shas is None else shas).get(agent)
    if pack["card_sha256"] != cur:
        return ("exame obsoleto: pacote emitido para o cartão %s, cartão atual %s — reexame com `cs.py probes "
                "exam-pack %s --out ...`" % (str(pack["card_sha256"])[:12], str(cur)[:12], agent))
    return None


def guard_stale(target, bank, agent, answers_file):
    drift = pack_card_drift(target, agent)
    if drift:
        raise CsError("%s: %s; nada foi pontuado nem registrado" % (agent, drift),
                      "o cartão mudou depois do exam-pack: reexamine o cartão atual (`cs.py probes exam-pack %s "
                      "--out <alvo>/.swarm/tmp/exam/%s`)" % (agent, agent), code=1)
    why = stale_reason(target, bank, agent, answers_file)
    if why:
        raise CsError("%s: respostas velhas — %s; nada foi pontuado nem registrado" % (agent, why),
                      "reexamine com as sondas atuais: `cs.py probes exam-pack %s --out "
                      "<alvo>/.swarm/tmp/exam/%s`" % (agent, agent),
                      code=1)


def card_shas(target):
    """{agente: sha256 canônico do cartão em team.json5 (o mesmo de cards/status.json5) | None sem cartão}."""
    from team.cards import _sha as card_sha
    p = sp_path(target, "team.json5")
    if not os.path.isfile(find_doc(p)):
        return {}
    team = read_json(p, "team.json5")
    return {a.get("name"): (card_sha(a["card"]) if a.get("card") else None) for a in team.get("agents") or []}


def _card_records_at(target, agent):
    """Instante ISO do registro de cartão mais recente (card set|revise) — fallback de ciclo sem hash."""
    p = sp_path(target, "cards", "status.json5")
    if not os.path.isfile(find_doc(p)):
        return None
    s = read_json(p, "cards/status.json5").get(agent) or {}
    recs = [s.get("drafted") or {}, s.get("revised") or {}] + list(s.get("refines") or []) + list(
        s.get("existence_fixes") or [])
    ats = [str(r.get("at")) for r in recs if r.get("at")]
    return max(ats) if ats else None


def card_drift(target, agent, cycle, shas=None):
    """Exame ligado ao cartão examinado (iteração 5: verify aceitou G4 com cartões consertados DEPOIS do exame).
    → motivo (G4 PENDENTE: reexame) ou None. Ciclo sem `card_sha256` (gravado antes desta regra): pendente se
    algum registro de cartão é posterior ao exame."""
    if not cycle:
        return None
    shas = card_shas(target) if shas is None else shas
    cur = shas.get(agent)
    if "card_sha256" in cycle:
        if cycle["card_sha256"] != cur:
            return ("cartão mudou depois do exame (examinado: %s; atual: %s)" % (
                str(cycle["card_sha256"])[:12], str(cur)[:12]))
        return None
    when = str(cycle.get("examined_at") or cycle.get("at") or "")
    last = _card_records_at(target, agent)
    if last and when and last > when:
        return "cartão registrado em %s, depois do exame (%s; ciclo sem hash do cartão)" % (last, when)
    return None


def pending_reexam(target):
    """Agentes cujo exame APROVADO mais recente foi feito sobre outro cartão → [(agente, motivo)] (verify)."""
    shas = card_shas(target)
    out = []
    for a, lst in sorted(load_cycles(target).items()):
        if lst and lst[-1].get("decision") == "PASS":
            why = card_drift(target, a, lst[-1], shas)
            if why:
                out.append((a, why))
    return out


def record_cycle(target, bank, agent, rep, answers_file):
    """Respostas NOVAS (ciclo novo ou retake) ligam o ciclo ao hash do cartão ATUAL (`card_sha256`); repontuar as
    MESMAS respostas (ex.: `check --all` do verify) mantém o hash do exame original — nunca o lava."""
    psha = agent_probes_sha(bank, agent)
    asha = _answers_sha(answers_file)
    csha = card_shas(target).get(agent)
    cyc = load_cycles(target)
    lst = cyc.setdefault(agent, [])
    now = cslog.now_iso()
    if lst and lst[-1]["probes_sha256"] == psha:
        last = lst[-1]
        if last["answers_sha256"] != asha:
            last["retakes"] = int(last.get("retakes") or 0) + 1
            last.update({"card_sha256": csha, "examined_at": now})
        last.update({"answers_sha256": asha, "decision": rep["decision"], "at": now})
    else:
        if any(c["probes_sha256"] == psha for c in lst):
            raise CsError("%s: sondas repetidas de um ciclo anterior" % agent,
                          "refino exige sondas NOVAS: `cs.py probes generate --seed <nova>` e novo exame")
        lst.append({"at": now, "examined_at": now, "probes_sha256": psha, "answers_sha256": asha,
                    "card_sha256": csha, "decision": rep["decision"], "retakes": 0})
    write_json(target, cycles_path(target), cyc,
               "cycles.json5 — ciclos de exame por agente (regra de 2 refinos); gerado por cs.py probes check")
    return len(lst)


def check_all(target, final=False, allow_reason=None, examined=False):
    """→ (ok, linhas, faltas, resumo). `examined` (check de validate.3): todo agente tem exame pontuado nas
    sondas ATUAIS (PASS ou FAIL; reprovado segue para o refino de validate.4) e sem painel POR-QUÊ pendente."""
    from probes.exam import check
    bank = load_bank(target)
    agents = bank_agents(bank)
    if not agents:
        raise CsError("banco sem agentes", "rode `cs.py probes generate`")
    lines, problems = [], []
    results = {}
    shas = card_shas(target)
    for a in agents:
        ap = answers_path(target, a)
        if not os.path.isfile(find_doc(ap)):
            results[a] = {"decision": "FAIL", "reasons": ["sem respostas (%s)" % os.path.basename(ap)],
                          "cycles": len(load_cycles(target).get(a) or [])}
            lines.append("%-24s FAIL sem respostas" % a)
            continue
        prev = passed_before(target, bank, a)
        if prev:  # refino só do reprovado: quem já passou num banco anterior não é repontuado
            n = len(load_cycles(target).get(a) or [])
            results[a] = {"decision": "PASS", "reasons": [], "cycles": n, "provisional": False,
                          "kept_from": prev.get("at")}
            drift = card_drift(target, a, prev, shas)
            if drift:
                results[a] = {"decision": "PENDING", "reasons": [drift], "cycles": n, "pending": True}
                lines.append("%-24s PENDENTE (reexame): %s ciclo=%d" % (a, drift, n))
                continue
            lines.append("%-24s PASS (aprovado no ciclo de %s, banco anterior; não repontuado) ciclo=%d"
                         % (a, prev.get("at"), n))
            continue
        drift = pack_card_drift(target, a, shas)
        if drift:  # pacote emitido para outro cartão: recusado (não pontuado nem registrado) — reexame
            n = len(load_cycles(target).get(a) or [])
            results[a] = {"decision": "PENDING", "reasons": [drift], "cycles": n, "pending": True}
            lines.append("%-24s PENDENTE (reexame): %s ciclo=%d" % (a, drift, n))
            continue
        why = stale_reason(target, bank, a, ap)
        if why:
            results[a] = {"decision": "FAIL", "reasons": ["respostas velhas: %s" % why],
                          "cycles": len(load_cycles(target).get(a) or []), "stale": True}
            lines.append("%-24s FAIL respostas velhas (não registrado): %s" % (a, why))
            continue
        rep = check(target, a, ap)
        n = record_cycle(target, bank, a, rep, ap)
        drift = card_drift(target, a, load_cycles(target)[a][-1], shas) if rep["decision"] == "PASS" else None
        if drift:  # exame aprovado sobre OUTRO cartão: G4 pendente até o reexame do cartão atual
            results[a] = {"decision": "PENDING", "reasons": [drift], "cycles": n, "pending": True}
            lines.append("%-24s PENDENTE (reexame): %s ciclo=%d" % (a, drift, n))
            continue
        results[a] = {"decision": rep["decision"], "reasons": rep["reasons"], "cycles": n,
                      "provisional": rep["provisional"]}
        lines.append("%-24s %s território=%s cross=%s alucinações=%d delta=%s ciclo=%d%s" % (
            a, rep["decision"], rep["score_territory"], rep["score_cross"], rep["hallucinations"], rep["delta"], n,
            " (provisório)" if rep["provisional"] else ""))
    pending = sorted(a for a, r in results.items() if r.get("pending"))
    failed = sorted(a for a, r in results.items() if r["decision"] != "PASS" and not r.get("pending"))
    summary = {"agents": results, "failed": failed, "pending": pending}
    for a in pending:
        problems.append("%s: G4 PENDENTE — %s; reexamine o cartão atual (`probes exam-pack %s --out ...` + "
                        "`probes check %s --answers ...`)" % (a, results[a]["reasons"][0], a, a))
    if examined and not final:
        for a in agents:
            r = results[a]
            if r.get("pending"):
                continue
            if r.get("stale"):
                problems.append("%s: %s — reexamine nas sondas atuais" % (a, r["reasons"][0]))
            elif r.get("kept_from"):
                continue
            elif r["reasons"] and str(r["reasons"][0]).startswith("sem respostas"):
                problems.append("%s não examinado (%s)" % (a, r["reasons"][0]))
            elif r.get("provisional"):
                problems.append("%s: painel POR-QUÊ pendente (`cs.py panel why`)" % a)
        return not problems, lines, problems, summary
    if not final:
        for a in failed:
            problems.append("%s reprovado: %s" % (a, "; ".join(results[a]["reasons"][:3])))
        return not problems, lines, problems, summary
    agg_p = sp_path(target, "probes", "report.json5")
    agg = read_json(agg_p, "report.json5") if os.path.isfile(find_doc(agg_p)) else {"schema_version": 1, "agents": {}}
    prev = (agg.get("final") or {}).get("allowed")
    per_agent = {a: (agg.get("agents") or {}).get(a, {}).get("allowed") for a in failed}
    exhausted = sorted(a for a in failed if results[a]["cycles"] >= 1 + MAX_REFINE_CYCLES)
    # sem refino possível: validate.4 pulado (--fast) ou rotação sem sonda nova — aceitável como nao-especialista
    no_refine = sorted(a for a in failed if a not in exhausted and refine_unavailable(target, bank, a))
    eligible = sorted(set(exhausted) | set(no_refine))
    accepted = set()
    if allow_reason and eligible:
        accepted = set(eligible)
        cslog.ledger(target, "allow_non_specialist", actor="cs.py probes", agents=eligible, reason=allow_reason.strip())
    else:
        if prev and set(eligible) <= set(prev.get("agents") or []):
            accepted |= set(eligible)
        accepted |= set(a for a in eligible if per_agent.get(a))
    non_specialist = sorted(exhausted + [a for a in no_refine if a in accepted])
    refining = sorted(a for a in failed if a not in non_specialist)
    for a in refining:
        if a in no_refine:
            problems.append("%s reprovado no ciclo %d e sem refino possível (%s): aceite com --allow-non-specialist "
                            "--reason \"...\" (registrado; verify decide NO-GO)" % (
                                a, results[a]["cycles"], refine_unavailable(target, bank, a)))
        else:
            problems.append("%s reprovado no ciclo %d: refino pendente (≤%d refinos com sondas novas)"
                            % (a, results[a]["cycles"], MAX_REFINE_CYCLES))
    for a in agents:
        row = agg.setdefault("agents", {}).setdefault(a, {})
        row["decision"] = results[a]["decision"]  # linha que só tinha closed_mode ganha a decisão
        row["cycles"] = results[a]["cycles"]
        row["status"] = ("especialista" if results[a]["decision"] == "PASS" else
                         "pendente-reexame" if results[a].get("pending") else
                         "nao-especialista" if a in non_specialist else "em-refino")
        if results[a]["decision"] == "PASS":
            row.pop("allowed", None)
    allowed = None
    missing = [a for a in exhausted if a not in accepted]
    if non_specialist and not missing:
        if allow_reason:
            allowed = {"agents": non_specialist, "reason": allow_reason.strip(), "at": cslog.now_iso()}
        elif prev and set(non_specialist) <= set(prev.get("agents") or []):
            allowed = prev
        else:
            allowed = {"agents": non_specialist, "at": cslog.now_iso(),
                       "reason": "; ".join("%s: %s" % (a, per_agent[a].get("reason")) for a in non_specialist
                                           if per_agent.get(a)) or (prev or {}).get("reason")}
    if missing:
        problems.append("nao-especialista após %d refinos: %s (use --allow-non-specialist --reason \"...\" "
                        "para aceitar e registrar)" % (MAX_REFINE_CYCLES, ", ".join(missing)))
    agg["final"] = {"at": cslog.now_iso(), "max_refine_cycles": MAX_REFINE_CYCLES, "non_specialist": non_specialist,
                    "refining": refining, "allowed": allowed, "pending_reexam": pending}
    write_json(target, agg_p, agg)
    summary.update({"non_specialist": non_specialist, "refining": refining, "allowed": allowed})
    return not problems, lines, problems, summary


def validate4_skipped(target):
    """validate.4 (refino) pulado explicitamente por `cs.py stage skip` (caminho --fast) → motivo ou None."""
    p = sp_path(target, "run.json5")
    if not os.path.isfile(find_doc(p)):
        return None
    run = read_json(p, "run.json5")
    rec = ((((run.get("stages") or {}).get("validate") or {}).get("substages") or {}).get("validate.4") or {})
    return ("validate.4 pulado (--fast): %s" % rec.get("reason")) if rec.get("status") == "skipped" else None


def refine_unavailable(target, bank, agent):
    """Motivo pelo qual o agente reprovado NÃO tem refino a fazer (ou None): --fast pulou validate.4, ou a
    rotação não tem mais sonda nova para ele."""
    why = validate4_skipped(target)
    if why:
        return why
    if agent in (bank.get("rotation_exhausted") or {}):
        return "rotação sem sonda nova (%s)" % bank["rotation_exhausted"][agent]
    return None


def allow_agent(target, bank, agent, reason, cycles):
    """`probes check <agente> --allow-non-specialist --reason R`: aceita ESTE agente reprovado como nao-especialista
    quando não há refino a fazer (ciclos esgotados, validate.4 pulado ou rotação esgotada). Registrado no
    report.json5 e no ledger; o verify decide NO-GO enquanto houver nao-especialista (decisoes.regra_go)."""
    if not (reason or "").strip():
        raise CsError("--allow-non-specialist exige --reason \"<motivo>\" (fica registrado)")
    why = None if cycles >= 1 + MAX_REFINE_CYCLES else refine_unavailable(target, bank, agent)
    if cycles < 1 + MAX_REFINE_CYCLES and not why:
        raise CsError("%s ainda tem refino: ciclo %d de %d" % (agent, cycles, 1 + MAX_REFINE_CYCLES),
                      "refine (`team card revise`, `probes generate --rotate --agent %s`, reexame) ou, no caminho "
                      "--fast, `cs.py stage skip validate.4 --reason ...` antes de aceitar" % agent)
    agg_p = sp_path(target, "probes", "report.json5")
    agg = read_json(agg_p, "report.json5") if os.path.isfile(find_doc(agg_p)) else {"schema_version": 1, "agents": {}}
    row = agg.setdefault("agents", {}).setdefault(agent, {})
    row["status"] = "nao-especialista"
    row["allowed"] = {"reason": reason.strip(), "at": cslog.now_iso(),
                      "why_no_refine": why or "%d refinos esgotados" % MAX_REFINE_CYCLES}
    write_json(target, agg_p, agg)
    cslog.ledger(target, "allow_non_specialist", actor="cs.py probes", agents=[agent], reason=reason.strip())
    return row["allowed"]


def baseline_check(target):
    """→ (ok, faltas): todo agente do banco tem baseline gravado e todas as suas sondas classificadas."""
    bank = load_bank(target)
    base = bank.get("baseline") or {}
    problems = []
    agents = bank_agents(bank)
    if not agents:
        problems.append("banco sem agentes")
    for a in agents:
        if a not in base:
            problems.append("%s sem baseline (rode o pacote num agente sem cartão e `probes baseline-filter %s`)"
                            % (a, a))
            continue
        bsha = base[a].get("probes_sha256")
        if bsha and bsha != agent_probes_sha(bank, a):
            problems.append("%s: baseline medido em OUTRAS sondas (banco mudou depois) — rode o baseline de novo" % a)
            continue
        if base[a].get("answered") is not None and base[a]["answered"] * 2 < int(base[a].get("probes") or 0):
            problems.append("%s: baseline respondeu %d de %d sondas — o baseline sem cartão não rodou de verdade"
                            % (a, base[a]["answered"], base[a]["probes"]))
            continue
        unk = [p["id"] for p in bank["probes"] if p["agent"] == a and p.get("discriminative") is None]
        if unk:
            problems.append("%s: %d sonda(s) sem classificação discriminativa (ex.: %s)" % (a, len(unk), unk[0]))
    return not problems, problems
