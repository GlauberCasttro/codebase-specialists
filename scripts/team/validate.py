"""cs.py team validate — as 8 regras do team-schema.md, mecanicamente.

Estágio: `derive` (cartões nulos permitidos; regras de cartão 5/6/7-cartão viram N/A) ou `final`
(cartão obrigatório, banco de sondas obrigatório para a regra 6). `auto` = derive se nenhum cartão.
Saída: .swarm/team-validation.json5; exit 1 se houver erro.
"""
import os
import re

from team._shared_tmp.cardtext import render_card, walk_strings
from team._shared_tmp.common import (find_doc, VERDICT_LIKE, CsError, expand, is_reserved, read_json, sp_path,
                                     write_json)
from team._shared_tmp.factsio import Facts, fact_files

NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,40}$")
KINDS = ("dev", "gate", "design", "product", "ops")
WRITE = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def _foreign_verdicts(text, enum):
    plain = re.sub(r"`[^`]*`", " ", text)
    return sorted(set(t for t in VERDICT_LIKE.findall(plain) if t not in enum))


def validate(target, stage="auto", team=None, write=True):
    team = team if team is not None else read_json(sp_path(target, "team.json5"), "team.json5")
    facts = Facts(target)
    agents = team.get("agents") or []
    res = {str(i): {"rule": i, "errors": [], "warnings": [], "status": "PASS"} for i in range(1, 9)}

    def err(rule, msg):
        res[str(rule)]["errors"].append(msg)

    def warn(rule, msg):
        res[str(rule)]["warnings"].append(msg)

    if not agents:
        err(3, "team.json5 sem agentes (estado vazio não é válido)")
    has_cards = any(a.get("card") for a in agents)
    explicit_derive = stage == "derive"
    if stage == "auto":
        stage = "final" if has_cards else "derive"
    enum = team.get("veredito_enum") or []
    if not enum:
        err(2, "veredito_enum ausente")

    # 1. nomes
    seen = set()
    for a in agents:
        n = a.get("name")
        if not isinstance(n, str) or not NAME_RE.match(n):
            err(1, "nome inválido: %r" % (n,))
        if n in seen:
            err(1, "nome duplicado: %s" % n)
        seen.add(n)

    # 2. kind, tools de gate, vereditos
    for a in agents:
        if a.get("kind") not in KINDS:
            err(2, "%s: kind fora do enum: %r" % (a.get("name"), a.get("kind")))
        if a.get("kind") == "gate":
            bad = sorted(set(a.get("tools") or []) & WRITE)
            if bad:
                err(2, "%s: gate com ferramenta de escrita %s" % (a.get("name"), bad))
            if a.get("territory"):
                err(2, "%s: gate com território de escrita" % a.get("name"))
            text = "\n".join(s for _, s in walk_strings(a.get("card") or {}))
            fv = _foreign_verdicts(text, enum)
            if fv:
                err(2, "%s: veredito fora do enum citado no cartão: %s" % (a.get("name"), fv))

    # 3. territórios disjuntos por expansão real + cobertura 100%
    product = facts.product_files()
    owners = {}
    for a in agents:
        terr = a.get("territory") or []
        for g in terr:
            if not isinstance(g, str) or g.startswith("!"):
                err(3, "%s: padrão de território inválido/negação não suportada: %r" % (a.get("name"), g))
            elif not expand([g], facts.all_files()):
                warn(3, "%s: glob de território não casa nenhum arquivo: %s" % (a.get("name"), g))
            res_hit = [r for r in facts.all_files() if is_reserved(r) and expand([g], [r])]
            if res_hit:
                err(3, "%s: território cobre path reservado ao harness (%s)" % (a.get("name"), res_hit[0]))
        if terr and a.get("kind") != "gate":
            for p in expand(terr, facts.ownable_files()):  # exemplo pode ter dono; sobreposição vale para ele
                owners.setdefault(p, []).append(a.get("name"))
    overlaps = sorted((p, o) for p, o in owners.items() if len(o) > 1)
    for p, o in overlaps[:50]:
        err(3, "sobreposição de escrita em %s: %s" % (p, ", ".join(sorted(o))))
    if len(overlaps) > 50:
        err(3, "... e mais %d sobreposições" % (len(overlaps) - 50))
    uncovered = [p for p in product if p not in owners]
    for p in uncovered[:50]:
        err(3, "arquivo de produto sem dono: %s" % p)
    if len(uncovered) > 50:
        err(3, "... e mais %d sem dono" % (len(uncovered) - 50))
    res["3"]["coverage"] = round((len(product) - len(uncovered)) / float(len(product) or 1), 4)
    res["3"]["overlaps"] = len(overlaps)

    # 4. fatos citados existem no índice
    try:
        ids = facts.index_ids()
    except CsError as exc:
        err(4, exc.message)
        ids = set(facts.by_id)

    def fact_refs(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("facts", "facts_used", "invariants", "supports") and isinstance(v, list):
                    for x in v:
                        yield x
                else:
                    for x in fact_refs(v):
                        yield x
        elif isinstance(obj, list):
            for v in obj:
                for x in fact_refs(v):
                    yield x
    for ref in sorted(set(str(x) for x in fact_refs({"core": team.get("core"), "agents": agents}))):
        if ref not in ids:
            err(4, "fato inexistente no index.json5: %s" % ref)

    # 5. existência (só com cartões); comandos verified|unverified
    if stage == "derive" and (explicit_derive or not has_cards):
        # `--stage derive` é o check do roster (specialize.1): não muda de regra quando os cartões chegam
        # (antes o check que passou em specialize.1 passava a falhar depois de specialize.3)
        res["5"]["status"] = "N/A"
    else:
        from probes.existence import existence_report
        rep = existence_report(target, team)
        for name, r in sorted(rep["agents"].items()):
            for m in r["missing"]:
                err(5, "%s: %s %s em %s (%s)" % (name, m["type"], m["value"], m["where"], m["why"]))
        for m in rep["core"]["missing"]:
            err(5, "core: %s %s (%s)" % (m["type"], m["value"], m["why"]))
        res["5"]["existence_ratio"] = rep["ratio"]
        for a in agents:
            if a.get("card") and not re.search(r"`[^`]+`", a["card"].get("done_when") or ""):
                err(5, "%s: done_when sem comando entre crases" % a.get("name"))

    # 6. anti-cola
    bank = sp_path(target, "probes", "bank.json5")
    if not os.path.isfile(find_doc(bank)):
        if stage == "final":
            err(6, "probes/bank.json5 ausente: anti-cola não pode ser provada")
        else:
            res["6"]["status"] = "N/A"
    else:
        from probes.anticola import anticola_report
        rep = anticola_report(target, team=team)
        for v in rep["violations"]:
            err(6, "%s: resposta canônica %s (%s) literal em %s" % (v["agent"], v["probe"], v["kind"], v["where"]))

    # 7. tamanhos
    lines = (team.get("core") or {}).get("lines") or []
    if len(lines) > 40:
        err(7, "core.lines = %d > 40" % len(lines))
    for a in agents:
        if stage == "final" and not a.get("card"):
            err(7, "%s: cartão ausente no estágio final" % a.get("name"))
        n = len(render_card(a.get("card")))
        if n > 150:
            err(7, "%s: cartão renderizado com %d linhas > 150" % (a.get("name"), n))
        desc = (a.get("card") or {}).get("description") or ""
        if len(desc) > 300:
            err(7, "%s: description com %d > 300 caracteres" % (a.get("name"), len(desc)))

    # 8. invariantes chegam a todos os donos; gates recebem todos (+ decisões de ADR); o gate de segurança
    #    (gate_scope: security) recebe os de segurança — precedência: qualquer FAIL vence
    from team.derive import gate_required
    inv_facts = facts.rules() + facts.interview_invariants() + list(facts.facts.get("business_rules", []))
    terr_files = {a.get("name"): set(expand(a.get("territory") or [], product)) for a in agents}
    for a in agents:
        if a.get("kind") != "gate":
            continue
        scope = a.get("gate_scope") or ("security" if a.get("name") == "security" else "all")
        have = set(a.get("invariants") or [])
        for fid in gate_required(facts, scope):
            if fid not in have:
                err(8, "gate %s sem invariante %s" % (a.get("name"), fid))
    for fx in inv_facts:
        sc = fx.get("scope") or []
        touched = set(fact_files(fx)) | set(expand(sc, product) if sc else [])
        for a in agents:
            have = set(a.get("invariants") or [])
            if a.get("kind") == "gate":
                continue
            elif terr_files[a.get("name")] & touched and fx["id"] not in have:
                err(8, "%s: invariante %s toca o território mas não está em invariants" % (a.get("name"), fx["id"]))

    ok = True
    for r in res.values():
        if r["errors"]:
            r["status"] = "FAIL"
            ok = False
    out = {"schema_version": 1, "stage": stage, "pass": ok, "rules": res}
    if write:
        write_json(target, sp_path(target, "team-validation.json5"), out)
    return out
