"""L6 racional: ADRs/docs de decisão + trechos "por quê" de commits que tocam hotspots."""

import re

from cslib import gitx
from cslib.tokenize import strip_accents
from cslib.evidence import ev_cmd, ev_commit, ev_file, slug
from . import l5_history

LAYER = "rationale"
ADR_DIRS = ("docs/adr/", "docs/adrs/", "docs/decisions/", "docs/decisoes/", "docs/architecture/decisions/",
            "doc/adr/", "adr/", "adrs/", "decisions/")
ADR_NAME = re.compile(r"(^|/)(ADR|adr)[-_ ]?\d*[-_].*\.(md|rst|txt)$|(^|/)\d{3,4}-[\w-]+\.md$")
WHY_RE = re.compile(r"[^.\n]*\b(why|because|porque|pois|since|so that|para evitar|para que|to avoid|"
                    r"in order to|motivo|reason)\b[^.\n]*", re.I)
STATUS_RE = re.compile(r"^[ \t]*(?:[-*+][ \t]+)?(?:\*\*|__)?(?:status|estado|situa[çc][ãa]o)(?:\*\*|__)?"
                       r"[ \t]*[:：][ \t]*(?:\*\*|__)?[ \t]*\**[ \t]*([^\s*_(,;:]+)", re.I | re.M)
STATUS_HEADING = re.compile(r"^#{1,4}[ \t]*(?:status|estado|situa[çc][ãa]o)[ \t]*$\n+[ \t]*(?:[-*+][ \t]+)?\**"
                            r"([^\s*_(,;:]+)", re.I | re.M)
# status canônico ← palavra inicial (minúscula, sem acento); desconhecido → "unknown" (raw guardado)
STATUS_MAP = {
    "accepted": "accepted", "aceito": "accepted", "aceita": "accepted", "aprovado": "accepted",
    "aprovada": "accepted", "approved": "accepted", "adopted": "accepted", "adotado": "accepted",
    "adotada": "accepted", "vigente": "accepted", "decided": "accepted", "decidido": "accepted",
    "decidida": "accepted", "active": "accepted", "ativo": "accepted", "ativa": "accepted",
    "implemented": "accepted", "implementado": "accepted", "implementada": "accepted",
    "proposed": "proposed", "proposto": "proposed", "proposta": "proposed", "draft": "proposed",
    "rascunho": "proposed", "em": "proposed", "pending": "proposed", "pendente": "proposed",
    "rejected": "rejected", "rejeitado": "rejected", "rejeitada": "rejected", "recusado": "rejected",
    "recusada": "rejected", "declined": "rejected",
    "superseded": "superseded", "substituido": "superseded", "substituida": "superseded",
    "superado": "superseded", "superada": "superseded", "replaced": "superseded",
    "deprecated": "deprecated", "obsoleto": "deprecated", "obsoleta": "deprecated",
    "descontinuado": "deprecated", "descontinuada": "deprecated", "revogado": "deprecated",
    "revogada": "deprecated", "retired": "deprecated",
}


def normalize_status(raw):
    """(canônico, raw) — canônico ∈ accepted|proposed|rejected|superseded|deprecated|unknown."""
    if not raw:
        return "unknown", None
    word = raw.strip().strip("*_`'\".").lower()
    key = strip_accents(word)
    return STATUS_MAP.get(key, "unknown"), word


SECTION_RE = re.compile(r"^#{1,3}\s*(decision|decisão|decisao|decided|resolução)\b.*$", re.I | re.M)


def is_adr(rel):
    low = rel.lower()
    if not low.endswith((".md", ".rst", ".txt")):
        return False
    if any(low.startswith(d) or ("/" + d) in low for d in ADR_DIRS):
        return not low.rsplit("/", 1)[-1] in ("readme.md", "index.md", "template.md")
    return bool(ADR_NAME.search(rel)) and "adr" in low


def parse_adr(ctx, rel):
    text = ctx.text(rel)
    lines = text.splitlines()
    title = next((ln.lstrip("#").strip() for ln in lines if ln.startswith("#")), rel.rsplit("/", 1)[-1])
    st = STATUS_RE.search(text) or STATUS_HEADING.search(text)
    status, status_raw = normalize_status(st.group(1) if st else None)
    decision, dline, items = None, None, []
    m = SECTION_RE.search(text)
    if m:
        dline = text.count("\n", 0, m.start()) + 1
        level = len(m.group(0)) - len(m.group(0).lstrip("#"))
        items = decision_items(lines, dline, level)
        decision = " ".join(it["text"] for it in items) or None
    return {"file": rel, "title": title[:200], "status": status, "status_raw": status_raw,
            "status_line": (text.count("\n", 0, st.start(1)) + 1) if st else None, "decision": decision,
            "decision_line": dline, "decision_items": items}


LIST_ITEM = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+(.*)$")
FENCE = re.compile(r"^\s*(```|~~~)")


def text_blocks(lines, start, stop):
    """Blocos de texto (item de lista com continuação, ou parágrafo) em lines[start:stop] (0-based).

    Cada bloco → {"line": 1-based, "end_line", "text"} com o texto INTEIRO (linhas de continuação
    juntadas; nunca cortado). Cabeçalhos, cercas de código, tabelas e comentários HTML não são blocos.
    """
    out, cur, in_fence = [], None, False

    def close():
        if cur and cur["parts"]:
            out.append({"line": cur["line"], "end_line": cur["end"],
                        "text": " ".join(" ".join(cur["parts"]).split())})

    for i in range(start, stop):
        raw = lines[i]
        s = raw.strip()
        if FENCE.match(raw):
            close()
            cur, in_fence = None, not in_fence
            continue
        if in_fence:
            continue
        if not s:
            close()
            cur = None
            continue
        if s.startswith(("#", "|", "<!--")) or re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
            close()
            cur = None
            continue
        lm = LIST_ITEM.match(raw)
        if lm:
            close()
            cur = {"line": i + 1, "end": i + 1, "parts": [lm.group(2).strip()], "indent": len(lm.group(1))}
            continue
        if cur is None:
            cur = {"line": i + 1, "end": i + 1, "parts": [s], "indent": -1}
        else:
            cur["parts"].append(s)
            cur["end"] = i + 1
    close()
    return out


def decision_items(lines, dline, level):
    """Itens da seção de decisão: do cabeçalho até o próximo cabeçalho de nível ≤ ao dela."""
    stop = len(lines)
    for j in range(dline, len(lines)):
        hm = re.match(r"^(#{1,6})\s", lines[j])
        if hm and len(hm.group(1)) <= level:
            stop = j
            break
    return text_blocks(lines, dline, stop)


def _clean(t):
    return re.sub(r"(\*\*|__)", "", t)


def run(ctx):
    fb = ctx.fb
    facts = []
    adrs = [parse_adr(ctx, f) for f in ctx.files if is_adr(f)]
    for a in adrs:
        shown = a["status"] if a["status"] != "unknown" or not a["status_raw"] else \
            "unknown — texto '%s' não reconhecido" % a["status_raw"]
        claim = "Decisão '%s' (status: %s)" % (a["title"], shown)
        items = a["decision_items"]
        base_id = "rat.adr.%s" % slug(a["file"])
        if len(items) == 1:
            claim += ": %s" % _clean(items[0]["text"])
        elif items:
            # cada item vira um fato próprio, com o texto inteiro (nunca truncado no meio)
            claim += ": %d itens de decisão (fatos %s.d1..d%d): %s" % (
                len(items), base_id, len(items), " | ".join(_clean(it["text"]) for it in items))
        ev = [ev_file(a["file"])]
        if a["status_line"]:
            ev.append(ev_file(a["file"], a["status_line"]))
        if a["decision_line"]:
            ev.append(ev_file(a["file"], a["decision_line"]))
        facts.append(fb.fact(base_id, LAYER, claim, ev,
                             confidence="high" if a["decision"] else "medium", scope=["**"],
                             data={"kind": "adr", "topic": a["title"], "decision": a["decision"],
                                   "decision_items": len(items),
                                   "status": a["status"], "status_raw": a["status_raw"]}))
        if len(items) > 1:
            for n, it in enumerate(items, 1):
                txt = _clean(it["text"])
                facts.append(fb.fact("%s.d%d" % (base_id, n), LAYER,
                                     "Decisão %d/%d do ADR '%s' (status: %s), %s:%d: %s" % (
                                         n, len(items), a["title"], shown, a["file"], it["line"], txt),
                                     [ev_file(a["file"], it["line"])],
                                     confidence="high" if a["status"] == "accepted" else "medium",
                                     scope=["**"],
                                     data={"kind": "adr_decision", "adr": a["file"], "topic": txt,
                                           "decision": txt, "status": a["status"], "item": n,
                                           "end_line": it["end_line"]}))

    whys = []
    has_commits = gitx.head(ctx.target) is not None
    hot = set(h["path"] for h in ctx.layer("L5")["hotspots"][:30]) if has_commits else set()
    for c in (l5_history.load_commits(ctx) if has_commits else []):
        files = sorted(set(f["path"] for f in c["files"]) & hot)
        if not files:
            continue
        msg = c["subject"] + "\n" + c["body"]
        snippets = []
        for m in WHY_RE.finditer(msg):
            s = " ".join(m.group(0).split())
            if len(s) >= 20:
                snippets.append(s[:300])
        if snippets:
            whys.append({"sha": c["sha"], "subject": c["subject"], "files": files,
                         "why": snippets[:3]})
    for w in whys[:60]:
        facts.append(fb.fact("rat.commit.%s" % w["sha"][:12], LAYER,
                             "Por quê (commit %s em hotspot %s): %s" % (
                                 w["sha"][:12], ", ".join(w["files"][:3]), " | ".join(w["why"])),
                             [ev_commit(w["sha"], w["files"])], confidence="medium",
                             scope=w["files"],
                             data={"kind": "commit_why", "sha": w["sha"], "topic": w["subject"],
                                   "why": w["why"]}))
    if not facts:
        facts.append(fb.fact("rat.none", LAYER,
                             "Nenhum ADR (procurado em %s e arquivos ADR-*.md) nem racional em "
                             "mensagens de commit de hotspots — racional precisa vir da entrevista"
                             % ", ".join(ADR_DIRS[:4]),
                             [ev_cmd("scan:L6 busca de ADRs e racional em commits", 1, b"")],
                             confidence="high", scope=["**"]))
    return {"layer": LAYER, "adrs": adrs, "commit_rationale": whys, "facts": facts}
