"""Entrevista de lacunas (scan.6): perguntas do orquestrador, respostas literais do dono.

Log append-only: <alvo>/.swarm/interview.jsonl (compartilhado com `cs.py stage check --answer`,
cujos registros sem `type` são ignorados aqui):
  {type: "question", id, question, context, scope[], ts}
  {type: "answer", id, answer, unknown: bool, by, ts}
Fatos: <alvo>/.swarm/facts/interview.json5 (camada `interview`, ids `interview.<id>`), um por
pergunta com resposta conhecida (a última resposta vale). `unknown` não vira fato: é lacuna declarada.
Lote: no máximo 8 perguntas pendentes ao mesmo tempo.
"""

import os
import re

from cslib import CsError, evidence
from facts import store

LAYER = "interview"
PREFIX = "interview."
BATCH_MAX = 8
QID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
LOG_REL = ".swarm/interview.jsonl"


def log_path(target):
    return store.sp(target, "interview.jsonl")


def facts_path(target):
    return os.path.join(store.facts_dir(target), "interview.json5")


def state(target):
    """→ (questions {id: rec+line}, answers {id: (line, rec)}) — última resposta por pergunta."""
    qs, ans = {}, {}
    for line, r in store.read_jsonl(log_path(target)):
        if r.get("type") == "question" and r.get("id"):
            qs.setdefault(r["id"], dict(r, line=line))
        elif r.get("type") == "answer" and r.get("id"):
            ans[r["id"]] = (line, r)
    return qs, ans


def pending(target):
    qs, ans = state(target)
    return [q for qid, q in sorted(qs.items(), key=lambda kv: kv[1]["line"]) if qid not in ans]


def _qid(qid):
    if not QID_RE.match(qid or ""):
        raise CsError("id de pergunta inválido: %r" % qid, "use [A-Za-z0-9._-], ex.: Q-01")
    return qid


def _scope(scope):
    """Um glob por `--scope` (action=append). Iteração 3 (ts-shop): "a/**,b/**" foi gravado como UM glob que não
    casa nada e a lacuna nunca chegou ao pacote de fatos do dono — o log é append-only, então recusamos antes."""
    for g in scope or []:
        if "," in g:
            raise CsError("--scope com vírgula: %r — cada --scope recebe UM glob" % g,
                          "repita a flag: %s" % " ".join("--scope %s" % x.strip() for x in g.split(",") if x.strip()))
    return scope


def ask(target, qid, question, context="", scope=None):
    _qid(qid)
    _scope(scope)
    if not (question or "").strip():
        raise CsError("--question vazio")
    qs, _ = state(target)
    if qid in qs:
        raise CsError("pergunta %s já existe" % qid, "use outro id (perguntas são append-only)")
    pend = pending(target)
    if len(pend) >= BATCH_MAX:
        raise CsError("lote cheio: %d perguntas pendentes (máx %d)" % (len(pend), BATCH_MAX),
                      "registre as respostas (`cs.py interview record`) antes de perguntar mais")
    rec = {"type": "question", "id": qid, "question": question.strip(), "context": (context or "").strip(),
           "scope": sorted(set(scope or [])), "ts": store.now()}
    store.append_jsonl(target, log_path(target), rec)
    return rec


def record(target, qid, answer=None, unknown=False, by="founder", question=None, context="", scope=None):
    _qid(qid)
    _scope(scope)
    if unknown == (answer is not None):
        raise CsError("informe exatamente um: --answer \"<literal>\" ou --answer-unknown")
    if answer is not None and not answer.strip():
        raise CsError("--answer vazio", "sem resposta do usuário, use --answer-unknown (não invente)")
    qs, _ = state(target)
    if qid not in qs:
        if not question:
            raise CsError("pergunta %s não registrada" % qid,
                          "crie com `cs.py interview ask --id %s --question ...` ou passe --question" % qid)
        ask(target, qid, question, context, scope)
    rec = {"type": "answer", "id": qid, "answer": "unknown" if unknown else answer, "unknown": bool(unknown),
           "by": by, "ts": store.now()}
    store.append_jsonl(target, log_path(target), rec)
    sync_facts(target)
    return rec


def sync_facts(target):
    """Regrava facts/interview.json5 a partir do log e sincroniza o index. Sem fatos de outras camadas."""
    qs, ans = state(target)
    fb = evidence.FactBuilder(target)
    facts = []
    for qid in sorted(ans):
        line, a = ans[qid]
        if a.get("unknown") or qid not in qs:
            continue
        q = qs[qid]
        fid = PREFIX + evidence.slug(qid)
        f = fb.fact(fid, LAYER, "Entrevista %s: %s — resposta do dono (literal): %s" % (qid, q["question"], a["answer"]),
                    [evidence.ev_file(LOG_REL, line)], confidence="high", origin="mechanical",
                    scope=q.get("scope") or [],
                    data={"question_id": qid, "question": q["question"], "context": q.get("context", ""),
                          "answer": a["answer"], "source": "founder", "by": a.get("by", "founder")})
        # fingerprint = bytes do registro da resposta (o log cresce; o registro não muda)
        f["fingerprint"] = store.sha256_obj({"q": q["question"], "a": a["answer"], "ts": a.get("ts")})
        facts.append(f)
    doc = {"schema_version": 1, "layer": LAYER, "generator": "cs.py interview", "facts": facts}
    if not os.path.isdir(store.facts_dir(target)):
        raise CsError("diretório de fatos ausente", "rode `cs.py scan` antes da entrevista")
    store.write5(target, facts_path(target), doc,
                 "interview — respostas literais do dono como fatos (layer interview); gerado por cs.py interview")
    store.index_sync(target, LAYER, [f["id"] for f in facts], PREFIX)
    sync_gaps(target, qs, ans, fb)
    return facts


GAP_LAYER = "gap"
GAP_PREFIX = "gap."


def gaps_path(target):
    return os.path.join(store.facts_dir(target), "gaps.json5")


def sync_gaps(target, qs=None, ans=None, fb=None):
    """Resposta `--answer-unknown` → fato `gap.<slug>` {question, answer: 'unknown'} (contrato `gap`): CITÁVEL em
    cartão (recusa/armadilha: "não sei X — pergunte ao dono"), mas nunca conhecimento — a memória (cs-mem) e o
    gerador de sondas não leem a camada `gap`."""
    if qs is None:
        qs, ans = state(target)
    fb = fb or evidence.FactBuilder(target)
    gaps = []
    for qid in sorted(ans):
        line, a = ans[qid]
        if not a.get("unknown") or qid not in qs:
            continue
        q = qs[qid]
        f = fb.fact(GAP_PREFIX + evidence.slug(qid), GAP_LAYER,
                    "Lacuna declarada %s: %s — o dono não soube responder (unknown); não é conhecimento" % (
                        qid, q["question"]),
                    [evidence.ev_file(LOG_REL, line)], confidence="high", origin="mechanical",
                    scope=q.get("scope") or [],
                    data={"question_id": qid, "question": q["question"], "answer": "unknown", "gap": True})
        f["fingerprint"] = store.sha256_obj({"q": q["question"], "a": "unknown", "ts": a.get("ts")})
        gaps.append(f)
    store.write5(target, gaps_path(target),
                 {"schema_version": 1, "layer": GAP_LAYER, "generator": "cs.py interview", "facts": gaps},
                 "gaps — lacunas declaradas (--answer-unknown); citáveis em cartão, nunca conhecimento nem sonda")
    store.index_sync(target, GAP_LAYER, [f["id"] for f in gaps], GAP_PREFIX)
    return gaps


def synced_problems(target):
    """Check de scan.6 (efeito): toda resposta registrada virou fato no índice (conhecida → interview.<id>,
    unknown → gap.<id>). Re-scan que regrava o index sem a entrevista não passa calado."""
    qs, ans = state(target)
    idx = store.index_ids(target)
    probs = []
    for qid in sorted(ans):
        if qid not in qs:
            continue
        unknown = ans[qid][1].get("unknown")
        fid = (GAP_PREFIX if unknown else PREFIX) + evidence.slug(qid)
        if fid not in idx:
            probs.append("%s respondida mas sem fato %s no índice (rode `cs.py interview sync`)" % (qid, fid))
    return probs
