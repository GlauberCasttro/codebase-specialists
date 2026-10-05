"""cs.py probes antitemplate --control <team.json5 de controle> — gate G3.

Similaridade entre o cartão de cada agente e o cartão do MESMO papel gerado para o repo de controle:
  line_jaccard    = Jaccard de linhas normalizadas (minúsculas, sem pontuação de markdown, espaços colapsados)
  shingle_jaccard = Jaccard de 5-shingles de palavras do cartão inteiro
  similarity      = max dos dois (conservador). Passa se ≤ limiar (0,35 por padrão; calibrar).
Mesmo papel = mesmo `name`; senão mesmo `kind` (dev: pior caso contra todos os devs do controle).
"""
import os
import re

from team._shared_tmp.cardtext import render_card
from team._shared_tmp.common import CsError, read_json, sp_path, write_json
from cslib.paths import STATE_DIR

THRESHOLD = 0.35
SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CONTROL = os.path.join(SKILL_ROOT, "evals", "reference", "generic-cards")
KIND_BY_NAME = (("review", "gate"), ("security", "gate"), ("devops", "ops"), ("ops", "ops"), ("qa", "dev"),
                ("tech-lead", "design"), ("architect", "design"), ("product", "product"), ("po", "product"))


def _md_agent(path):
    with open(path, "rb") as fh:
        text = fh.read().decode("utf-8", "replace")
    name = os.path.splitext(os.path.basename(path))[0]
    desc = ""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            for ln in parts[1].splitlines():
                k, _, v = ln.partition(":")
                if k.strip() == "name" and v.strip():
                    name = v.strip()
                if k.strip() == "description":
                    desc = v.strip()
            text = parts[2]
    kind = next((k for frag, k in KIND_BY_NAME if frag in name), "dev")
    return {"name": name, "kind": kind, "card": {"description": desc, "mission": text}}


def load_control(path):
    """Controle de G3: team.json5 (de um repo de controle), repo com .swarm/team.json5, ou diretório de
    cartões genéricos .md (default: evals/reference/generic-cards da skill — leitura só)."""
    path = path or DEFAULT_CONTROL
    if os.path.isdir(path):
        tj = os.path.join(path, STATE_DIR, "team.json5")
        if os.path.isfile(tj):
            return read_json(tj, "team.json5 de controle")
        mds = sorted(f for f in os.listdir(path) if f.endswith(".md"))
        if not mds:
            raise CsError("controle sem cartões: %s" % path, "passe --control <team.json5|repo|dir de .md>")
        return {"agents": [_md_agent(os.path.join(path, f)) for f in mds]}
    return read_json(path, "team.json5 de controle")


def norm_line(s):
    s = s.lower()
    s = re.sub(r"[`*_#>\[\]()|:;,.!?\"'—–-]+", " ", s)
    s = re.sub(r"^\s*\d+\s+", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _lines(card):
    return set(x for x in (norm_line(l) for l in render_card(card)) if x)


def _shingles(card, n=5):
    words = " ".join(norm_line(l) for l in render_card(card)).split()
    if len(words) < n:
        return set([" ".join(words)]) if words else set()
    return set(" ".join(words[i:i + n]) for i in range(len(words) - n + 1))


def jaccard(a, b):
    if not a and not b:
        return 0.0
    return len(a & b) / float(len(a | b))


def similarity(card_a, card_b):
    lj = jaccard(_lines(card_a), _lines(card_b))
    sj = jaccard(_shingles(card_a), _shingles(card_b))
    return round(lj, 4), round(sj, 4), round(max(lj, sj), 4)


def antitemplate_report(team, control, threshold=THRESHOLD):
    ctrl = [a for a in control.get("agents") or [] if a.get("card")]
    if not ctrl:
        raise CsError("team.json5 de controle sem cartões", "gere os cartões do repo de controle antes")
    rep = {"schema_version": 1, "gate": "G3", "threshold": threshold, "agents": {}}
    ok = True
    for a in team.get("agents") or []:
        if not a.get("card"):
            rep["agents"][a.get("name")] = {"pass": False, "why": "cartão ausente"}
            ok = False
            continue
        same = [c for c in ctrl if c.get("name") == a.get("name")] or \
            [c for c in ctrl if c.get("kind") == a.get("kind")]
        if not same:
            rep["agents"][a["name"]] = {"pass": True, "control_agent": None, "similarity": 0.0,
                                        "why": "sem papel equivalente no controle"}
            continue
        best = None
        for c in same:
            lj, sj, sim = similarity(a["card"], c["card"])
            if best is None or sim > best["similarity"]:
                best = {"control_agent": c.get("name"), "line_jaccard": lj, "shingle_jaccard": sj,
                        "similarity": sim}
        best["pass"] = best["similarity"] <= threshold
        ok = ok and best["pass"]
        rep["agents"][a["name"]] = best
    rep["pass"] = ok
    return rep


def run_antitemplate(target, control_path=None, threshold=THRESHOLD):
    team = read_json(sp_path(target, "team.json5"), "team.json5")
    control_path = control_path or DEFAULT_CONTROL
    control = load_control(control_path)
    rep = antitemplate_report(team, control, threshold)
    rep["control"] = control_path
    write_json(target, sp_path(target, "probes", "antitemplate.json5"), rep)
    return rep
