#!/usr/bin/env python3
"""cs-state — único dono das transições (épico, feature, sprint, story, sessão M1, delegação M2, task M3, consulta M4).

Raiz: --root > $CLAUDE_PROJECT_DIR > $CS_ROOT (nunca o diretório do script). Saída curta; recusa com
mensagem acionável (exit 1); estado ausente/incoerente → exit 2.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(os.path.dirname(os.path.dirname(HERE)), "memory")):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import hcore  # noqa: E402
import j5  # noqa: E402
import engine  # noqa: E402
import cmds  # noqa: E402
import views  # noqa: E402

SEVERITY_ALIAS = {"critica": "critical", "crítica": "critical", "alta": "high", "media": "medium", "média": "medium",
                  "baixa": "low"}


def _csv(vals):
    out = []
    for v in vals or []:
        out.extend(x.strip() for x in v.split(",") if x.strip())
    return out


def _criteria(items):
    out = []
    for i, it in enumerate(items or []):
        parts = [p.strip() for p in it.split("|")]
        if len(parts) == 2:
            parts = ["AC-%d" % (i + 1)] + parts
        if len(parts) != 3:
            raise hcore.Refused("--criterion deve ser 'AC-n|Dado ... Quando ... Então ...|<test id>'")
        out.append({"id": parts[0], "gherkin": parts[1], "test": parts[2]})
    return out


def build_parser():
    ap = argparse.ArgumentParser(prog="cs-state", description=__doc__.splitlines()[0])
    ap.add_argument("--root")
    ap.add_argument("--actor", default=os.environ.get("CS_ACTOR", "lead"))
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("init")
    add = sub.add_parser("add").add_subparsers(dest="what")
    e = add.add_parser("epic")
    e.add_argument("--title", required=True)
    e.add_argument("--objective", required=True)
    e.add_argument("--metric")
    f = add.add_parser("feature")
    f.add_argument("--epic", required=True)
    f.add_argument("--title", required=True)
    f.add_argument("--spec")
    f.add_argument("--accept-cmd", action="append", default=[])
    f.add_argument("--accept-file", action="append", default=[])
    sp = add.add_parser("sprint")
    sp.add_argument("--goal", required=True)
    sp.add_argument("--budget", default="")
    st = add.add_parser("story")
    st.add_argument("--type", required=True, choices=["us", "bug", "fix"])
    st.add_argument("--feature")
    st.add_argument("--title", required=True)
    for k in ("as-a", "i-want", "so-that", "failing-test", "severity", "environment", "fixes", "proving-test",
              "regression", "reopens"):
        st.add_argument("--" + k)
    st.add_argument("--criterion", action="append", default=[])
    st.add_argument("--repro", action="append", default=[])
    t = add.add_parser("task")
    t.add_argument("--quick", action="store_true",
                   help="faixa avulsa: sessão trivial|pequena, story implícita STORY-AVULSA-<sessão>, já BRIEFED")
    t.add_argument("--work-type", choices=["us", "bug", "fix"], help="tipo da task avulsa (padrão us)")
    t.add_argument("--from", dest="from_file", help="brief em JSON5 (brief-schema.json5)")
    t.add_argument("--id")
    t.add_argument("--story")
    t.add_argument("--agent")
    t.add_argument("--title")
    t.add_argument("--goal")
    t.add_argument("--type")
    t.add_argument("--sprint")
    t.add_argument("--session")
    t.add_argument("--class", dest="klass")
    t.add_argument("--wave", type=int, default=1)
    t.add_argument("--depends-on", action="append", default=[])
    t.add_argument("--allowed-path", action="append", default=[])
    t.add_argument("--protected-path", action="append", default=[])
    t.add_argument("--verify-cmd")
    t.add_argument("--ac", action="append", default=[], help="'AC-n|critério|verification_command|test:<id>|reviewer'")
    t.add_argument("--ref", action="append", default=[])
    t.add_argument("--in", dest="scope_in", action="append", default=[])
    t.add_argument("--out", dest="scope_out", action="append", default=[])
    t.add_argument("--subtask", action="append", default=[])
    t.add_argument("--assume", action="append", default=[])
    t.add_argument("--context", default="")
    t.add_argument("--dod", action="append", default=[])
    t.add_argument("--hot-path", action="store_true")
    t.add_argument("--security-gate", action="store_true")
    t.add_argument("--readonly", action="store_true")
    t.add_argument("--handoff-to")
    t.add_argument("--scenario", action="append", default=[])
    t.add_argument("--ready", action="store_true")
    for lvl, trans in (("epic", ["activate", "done", "drop"]), ("feature", ["ready", "start", "done", "drop"]),
                       ("story", ["ready", "start", "review", "done", "reject", "requeue"])):
        p = sub.add_parser(lvl)
        p.add_argument("transition", choices=trans)
        p.add_argument("--id", required=True)
        p.add_argument("--reason")
        p.add_argument("--dry-run", action="store_true")
    _tree_parsers(sub)
    p = sub.add_parser("sprint")
    p.add_argument("transition", choices=["plan", "start", "review", "close"])
    p.add_argument("--id")
    p.add_argument("--goal")
    p.add_argument("--budget")
    p.add_argument("--stories", action="append", default=[])
    p.add_argument("--add", action="append", default=[])
    p.add_argument("--reason")
    p = sub.add_parser("session")
    p.add_argument("transition", choices=["start", "triage", "confirm", "answer", "plan", "execute", "replan", "verify",
                                          "review", "report", "close", "status"])
    p.add_argument("--request")
    p.add_argument("--mode", default="assistido", choices=["assistido", "autonomo"])
    p.add_argument("--class", dest="klass")
    p.add_argument("--why")
    p.add_argument("--assume", action="append", default=[])
    p.add_argument("--note")
    p.add_argument("--by")
    p.add_argument("--verdict")
    p.add_argument("--findings")
    for name in ("ready", "dispatch", "submit", "return", "verify", "review", "accept", "reject", "retry", "escalate",
                 "block", "reroute", "abstain", "delegate", "amend", "brief", "drop", "reverify", "waive-verify"):
        p = sub.add_parser(name)
        p.add_argument("task_pos", nargs="?")
        p.add_argument("--task")
        if name == "drop":
            p.add_argument("--id", dest="task_id", help="id da task ou da delegação (sinônimo de --task)")
        if name == "dispatch":
            p.add_argument("--model")
            p.add_argument("--tool-use-id", help="id do tool_use do Agent que lançou o subagente (o hook pre-agent passa); "
                           "sem ele (e sem --manual) o CLI recusa: despache pela ferramenta Agent com o id da delegação "
                           "na description")
            p.add_argument("--manual", action="store_true",
                           help="plataforma SEM hook pre-agent (Cursor, Copilot, Codex): declara a execução do "
                                "subagente; grava tool_use_id manual:<timestamp> e dispatch_origin manual (no Claude "
                                "Code o guard bloqueia: use a ferramenta Agent)")
        if name == "submit":
            p.add_argument("--files-changed", action="append", default=[])
            p.add_argument("--check", action="append", default=[])
            p.add_argument("--risk", action="append", default=[])
            p.add_argument("--handoff-notes", default="")
            p.add_argument("--from", dest="from_file")
        if name == "review":
            p.add_argument("--by", required=True)
            p.add_argument("--verdict", required=True)
            p.add_argument("--findings", default="")
        if name == "waive-verify":
            p.add_argument("--by", help="o HUMANO que assume a exceção (nunca o orquestrador nem um agente do time)")
            p.add_argument("--evidence", help="saída do verify mostrando a falha de AMBIENTE (ferramenta/módulo ausente)")
        if name in ("reject", "escalate", "block", "reroute", "abstain", "return", "drop", "waive-verify"):
            p.add_argument("--reason")
        if name == "retry":
            p.add_argument("--findings")
        if name in ("retry", "reroute"):
            p.add_argument("--decision", help="decisão do humano ao retomar/trocar de agente uma delegação ESCALATED/ABSTAINED")
        if name == "reroute":
            p.add_argument("--agent", required=True)
            p.add_argument("--allowed-path", action="append", default=[])
        if name == "abstain":
            p.add_argument("--kind", default="other")
        if name == "amend":
            p.add_argument("--field", required=True)
            p.add_argument("--after", required=True, help="valor em JSON5 (ou texto simples)")
            p.add_argument("--reason", required=True)
            p.add_argument("--found-by")
        if name == "brief":
            p.add_argument("--phase", choices=["implement", "verify", "review"])
            p.add_argument("--agent")
    p = sub.add_parser("legacy-ack", help="HUMANO: reconhece na cadeia o histórico de motor antigo/hotfix (validate --strict)")
    p.add_argument("--reason", required=True)
    p = sub.add_parser("ask", help="faixa consulta: delegação SÓ LEITURA a um especialista, sem task/story")
    p.add_argument("agent")
    p.add_argument("question")
    p.add_argument("--paths", nargs="+", action="extend", default=[], help="globs onde o especialista deve olhar")
    p = sub.add_parser("consult")
    p.add_argument("transition", choices=["cancel"])
    p.add_argument("--id", required=True)
    p.add_argument("--reason")
    p = sub.add_parser("status")
    p.add_argument("--task")
    p = sub.add_parser("board")
    p.add_argument("--json", action="store_true", help="JSON puro (todo item é um dict com id)")
    sub.add_parser("next")
    p = sub.add_parser("validate", help="SÓ LEITURA: o mesmo validador de cs-harness validate (exit 1 se reprovar)")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--allow-empty", action="store_true")
    p = sub.add_parser("why")
    p.add_argument("id")
    p = sub.add_parser("autonomy")
    p.add_argument("action", choices=["start", "status", "stop", "report", "spend", "resume"])
    p.add_argument("--feature")
    p.add_argument("--story")
    p.add_argument("--spec")
    p.add_argument("--accept-cmd", action="append", default=[])
    p.add_argument("--accept-file", action="append", default=[])
    p.add_argument("--class", dest="klass")
    p.add_argument("--budget", default="")
    p.add_argument("--usd", type=float)
    p.add_argument("--reason")
    p.add_argument("--decision", help="resume: a decisão do humano que destrava o mandato ESCALATED")
    return ap


def _tree_parsers(sub):
    """Estado em árvore: new/start/plan/move/park/promote/close/reopen/find/tree/check/migrate (+ feature drop)."""
    new = sub.add_parser("new", help="cria item da árvore (saída: `criado <ID> em <caminho>`)").add_subparsers(dest="what")
    e = new.add_parser("epico")
    e.add_argument("--title", required=True)
    e.add_argument("--objetivo", required=True)
    e.add_argument("--metrica")
    sp = new.add_parser("sprint")
    sp.add_argument("--meta", required=True)
    sp.add_argument("--epico")
    f = new.add_parser("feature")
    f.add_argument("--title", required=True)
    f.add_argument("--sprint")
    f.add_argument("--backlog", action="store_true")
    f.add_argument("--aceite", required=True)
    t = new.add_parser("task")
    st = new.add_parser("story")
    for p in (t, st):
        p.add_argument("--tipo", required=True, type=str.upper, choices=["US", "BUG", "FIX", "CHORE"])
        p.add_argument("--title", required=True)
        p.add_argument("--allowed-path", action="append", default=[])
        p.add_argument("--verify-cmd")
        for k in ("como", "quero", "para", "reproducao", "fixes", "teste", "motivo"):
            p.add_argument("--" + k)
        p.add_argument("--criterio", action="append", default=[])
    t.add_argument("--agent", required=True)
    for k in ("feature", "sprint", "story"):
        t.add_argument("--" + k)
    t.add_argument("--avulsa", action="store_true")
    t.add_argument("--backlog", action="store_true")
    st.add_argument("--feature", required=True)
    st.add_argument("--agents", action="append", default=[], required=True)
    for p in (e, sp, f, t, st):
        p.add_argument("--dry-run", action="store_true", help="mostra {ids, criar, mover, eventos} em JSON e não escreve nada")
    for name in ("start", "promote"):
        p = sub.add_parser(name)
        p.add_argument("id")
        p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("plan")
    p.add_argument("id")
    p.add_argument("--sprint", required=True)
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("move")
    p.add_argument("id")
    p.add_argument("--to")
    p.add_argument("--avulsa", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("park")
    p.add_argument("id")
    p.add_argument("--reason", required=True)
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("close")
    p.add_argument("id")
    p.add_argument("--summary", required=True)
    p.add_argument("--devolver", action="store_true")
    p.add_argument("--reason")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("reopen")
    p.add_argument("id")
    p.add_argument("--reason", required=True)
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("find")
    p.add_argument("text")
    p = sub.add_parser("tree")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("check", help="SÓ LEITURA: DoR/pré-condições do item (exit 0 pronto, 1 lista o que falta)")
    p.add_argument("id")
    p = sub.add_parser("migrate")
    p.add_argument("what", choices=["state-tree"])


TREE_M2 = ("ready", "dispatch", "submit", "return", "verify", "review", "accept", "reject", "retry", "escalate", "block",
           "reroute", "abstain", "delegate", "amend", "brief", "drop", "reverify", "waive-verify")


def _tree_m2_ids(root, a):
    """Modo árvore: o id da árvore (ou um id antigo, via alias) vale nos comandos de M2 → id da task M2."""
    import tree
    try:
        tv = tree.load_view(root)
    except (hcore.StateError, hcore.Refused):
        return
    for attr in ("task_pos", "task", "task_id"):
        v = getattr(a, attr, None)
        if not v:
            continue
        base, suf = (v[:-len(v.split(".")[-1]) - 1], "." + v.split(".")[-1]) if re.search(r"\.d\d+$", v) else (v, "")
        it = tv.get(base)
        if it is not None and it.get("kind") == "task" and it.get("m2"):
            setattr(a, attr, it["m2"] + suf)


def _plan_out(plan, verb):
    out = ["criado %s em %s" % (i, p) for i, p in zip(plan["ids"], plan["criar"])]
    out += ["%s %s: %s → %s" % (verb, m.get("id_anterior") or m["id"], m["de"], m["para"]) +
            ((" (novo id %s)" % m["id"]) if m.get("id_anterior") else "") for m in plan["mover"]]
    return out


def run_tree(root, actor, a):
    """Subcomandos do estado em árvore. None = não é comando de árvore."""
    import tree
    c = a.cmd
    dry = bool(getattr(a, "dry_run", False))
    if c == "migrate":
        return [tree.migrate(root, actor)]
    if c == "find":
        tv = tree.load_view(root)
        hits = tree.find(tv, a.text)
        if not hits:
            return ["nada encontrado para %r" % a.text]
        return ["%s [%s] %s — %s%s" % (it["id"], tree.status_of(tv, it), it.get("title") or "", tree.sd_rel(it["path"]),
                                       (" (ids anteriores: %s)" % ", ".join(it["aliases"])) if it.get("aliases") else "")
                for it in hits]
    if c == "tree":
        tv = tree.load_view(root)
        return [json.dumps(tree.tree_json(tv), ensure_ascii=False)] if a.json else [tree.tree_text(tv)]
    if c == "board":
        tv = tree.load_view(root)
        return [json.dumps(tree.board_json(tv), ensure_ascii=False)] if a.json else [tree.board_text(tv)]
    if c == "check":
        it, probs = tree.check(root, a.id)
        if probs:
            raise hcore.Refused(["%s não está pronto (DoR):" % it["id"]] + probs)
        return ["pronto: %s (%s) — DoR ok; `cs-state start %s` passa pela mesma regra" % (it["id"], it["kind"], it["id"])]
    if c == "new":
        w = a.what
        if w == "epico":
            b = lambda tv: tree.new_epico(tv, a.title, a.objetivo, a.metrica)  # noqa: E731
        elif w == "sprint":
            b = lambda tv: tree.new_sprint(tv, a.meta, a.epico)  # noqa: E731
        elif w == "feature":
            if bool(a.sprint) == bool(a.backlog):
                raise hcore.Refused("feature tem exatamente um destino: --sprint SPR-nnn | --backlog")
            b = lambda tv: tree.new_feature(tv, a.title, a.aceite, a.sprint)  # noqa: E731
        elif w in ("task", "story"):
            spec = {"tipo": a.tipo, "title": a.title, "allowed_paths": _csv(a.allowed_path), "verify_cmd": a.verify_cmd,
                    "como": a.como, "quero": a.quero, "para": a.para, "criterio": a.criterio, "reproducao": a.reproducao,
                    "fixes": a.fixes, "teste": a.teste, "motivo": a.motivo, "feature": a.feature}
            if w == "task":
                spec.update({"agent": a.agent, "sprint": a.sprint, "story": a.story, "avulsa": a.avulsa, "backlog": a.backlog})
                b = lambda tv: tree.new_task(tv, spec)  # noqa: E731
            else:
                spec["agents"] = a.agents
                b = lambda tv: tree.new_story(tv, spec)  # noqa: E731
        else:
            raise hcore.Refused("new epico|sprint|feature|task|story")
        plan, _ = tree.run_build(root, actor, b, dry)
        return [json.dumps(plan, ensure_ascii=False)] if dry else _plan_out(plan, "movido")
    if c in ("start", "plan", "move", "park", "promote", "close", "reopen") or (c == "feature" and a.transition == "drop"):
        if c == "start":
            b = lambda tv: tree.start(tv, a.id)  # noqa: E731
        elif c == "plan":
            b = lambda tv: tree.plan(tv, a.id, a.sprint)  # noqa: E731
        elif c == "move":
            if bool(a.to) == bool(a.avulsa):
                raise hcore.Refused("move <id> --to <pai> | --avulsa (exatamente um)")
            b = lambda tv: tree.move(tv, a.id, a.to, a.avulsa)  # noqa: E731
        elif c == "park":
            b = lambda tv: tree.park(tv, a.id, a.reason)  # noqa: E731
        elif c == "promote":
            b = lambda tv: tree.promote(tv, a.id)  # noqa: E731
        elif c == "close":
            b = lambda tv: tree.close(tv, a.id, a.summary, a.devolver, a.reason)  # noqa: E731
        elif c == "reopen":
            b = lambda tv: tree.reopen(tv, a.id, a.reason)  # noqa: E731
        else:
            if not a.reason:
                raise hcore.Refused("feature drop exige --reason")
            b = lambda tv: tree.feature_drop(tv, a.id, a.reason)  # noqa: E731
        plan, tv = tree.run_build(root, actor, b, dry)
        if dry:
            return [json.dumps(plan, ensure_ascii=False)]
        out = ["%s %s ok" % ("feature drop" if c == "feature" else c, a.id)] + _plan_out(plan, "movido")
        if c == "start" and tv is not None:
            it = tv.get(a.id)
            if it and it.get("kind") == "task" and it.get("m2"):
                out.append("task %s BRIEFED (wave %s, model %s) — despache: Agent(subagent_type=%r, model=%r, "
                           "description='%s.d1: ...') ou, sem hook, cs-state dispatch %s --manual --model %s" % (
                               it["id"], it.get("wave"), (it.get("route") or {}).get("model"), it.get("agent"),
                               (it.get("route") or {}).get("model"), it["m2"], it["id"], (it.get("route") or {}).get("model")))
        return out
    return None


def _tid(a):
    tid = a.task or a.task_pos or getattr(a, "task_id", None)
    if not tid:
        raise hcore.Refused("informe a task (--task <id> ou posicional)")
    return tid


def _value(s):
    try:
        return j5.loads(s)
    except ValueError:
        return s


TREE_CMDS = ("new", "start", "plan", "move", "park", "promote", "close", "reopen", "find", "tree", "check", "migrate")


def run(a):
    root = hcore.resolve_root(a.root)
    actor = a.actor
    out = []
    c = a.cmd
    tree_mode = hcore.tree_mode(root)
    if c in TREE_CMDS or (tree_mode and (c == "board" or (c == "feature" and a.transition == "drop"))):
        return run_tree(root, actor, a)
    if tree_mode and c in TREE_M2:
        _tree_m2_ids(root, a)
    if c == "init":
        import tree
        r = tree.init(root)
        if r is None:
            out.append("estado já existe em board plano legado (idempotente) — migre com: cs-state migrate state-tree")
        else:
            out.append("estado criado (árvore: backlog/ state/ archive/)" if r else "estado já existe (idempotente)")
    elif c == "add":
        w = a.what
        if w == "epic":
            _, ev = cmds.add_epic(root, actor, a.title, a.objective, a.metric)
        elif w == "feature":
            _, ev = cmds.add_feature(root, actor, a.epic, a.title, a.spec, a.accept_cmd, a.accept_file)
        elif w == "sprint":
            import autonomy
            _, ev = cmds.add_sprint(root, actor, a.goal, autonomy.parse_budget(a.budget))
        elif w == "story":
            feature = a.feature
            if not feature and a.fixes:
                b = hcore.load_board(root)
                src = hcore.find(b, "story", a.fixes) or hcore.find(b, "story", (hcore.find(b, "task", a.fixes.split(":", 1)[-1]) or {}).get("story", ""))
                feature = (src or {}).get("feature")
            if not feature:
                raise hcore.Refused("--feature obrigatório (ou --fixes BUG-n de onde herdar a feature)")
            sev = SEVERITY_ALIAS.get((a.severity or "").lower(), a.severity)
            _, ev = cmds.add_story(root, actor, a.type, feature, a.title, as_a=a.as_a, i_want=a.i_want, so_that=a.so_that,
                                   criteria=_criteria(a.criterion), repro=a.repro, failing_test=a.failing_test, severity=sev,
                                   environment=a.environment, fixes=a.fixes, proving_test=a.proving_test,
                                   regression=a.regression, reopens=a.reopens)
        elif w == "task":
            spec = j5.load(a.from_file) if a.from_file else {}
            cli = {"id": a.id, "story": a.story, "agent": a.agent, "title": a.title, "goal": a.goal, "type": a.type,
                   "sprint": a.sprint, "session": a.session, "class": a.klass, "wave": a.wave,
                   "depends_on": _csv(a.depends_on), "allowed_paths": _csv(a.allowed_path),
                   "protected_paths": _csv(a.protected_path), "verification_command": a.verify_cmd,
                   "acceptance_criteria": a.ac, "dod": a.dod, "readonly": a.readonly,
                   "flags": {"hot_path": a.hot_path, "security_gate": a.security_gate},
                   "handoff": {"to": a.handoff_to, "scenarios": a.scenario} if a.handoff_to or a.scenario else None}
            for k, v in cli.items():
                if v not in (None, [], "", {}) and not (k == "wave" and v == 1 and "wave" in spec):
                    spec[k] = v
            br = dict(spec.get("briefing") or {})
            for k, v in (("references", a.ref), ("subtasks", a.subtask), ("assumptions", a.assume)):
                if v:
                    br[k] = v
            if a.context:
                br["context"] = a.context
            if a.scope_in or a.scope_out:
                br["scope"] = {"in": a.scope_in, "out": a.scope_out}
            spec["briefing"] = br
            if a.quick:
                spec["quick"] = True
                if a.work_type:
                    spec["work_type"] = a.work_type
            if not spec.get("agent"):
                raise hcore.Refused("--agent obrigatório")
            _, ev = cmds.add_task(root, actor, spec, ready=a.ready)
            if spec.get("quick"):
                out.append("criado: %s" % ", ".join(e["entity"] for e in ev if e.get("entity")))
                ctx = engine.Ctx(root, hcore.load_board(root))
                tid = next(e["entity"] for e in ev if e["type"] == "task.add")
                d = engine.latest_deleg(ctx.find("task", tid))
                s = cmds.active_session(ctx)
                out.append("task avulsa %s (story implícita %s) BRIEFED %s — model=%s" % (
                    tid, ctx.find("task", tid)["story"], d["id"], (d.get("route") or {}).get("model")))
                if s and s["state"] == "PLANNING":
                    out.append("próximo: cs-state session execute ; depois " + views.next_for(ctx, "deleg", d))
                else:
                    out.append("próximo: " + views.next_for(ctx, "deleg", d))
                return out
        else:
            raise hcore.Refused("add epic|feature|sprint|story|task")
        out.append("criado: %s" % ", ".join(e["entity"] for e in ev if e.get("entity")))
    elif c in ("epic", "feature", "story"):
        _, ev = cmds.level_transition(root, actor, c, a.id, a.transition, {"reason": a.reason})
        out.append("%s %s → %s" % (c, a.id, a.transition))
    elif c == "sprint":
        sid = a.id
        stories = _csv(a.stories) + _csv(a.add)
        if a.transition == "plan" and not sid:
            b = hcore.load_board(root)
            planned = [s for s in b["sprints"] if s["state"] == "PLANNED"]
            if planned:
                sid = planned[-1]["id"]
            else:
                if not a.goal:
                    raise hcore.Refused("sem sprint PLANNED: passe --goal (e --budget) para criar")
                import autonomy
                _, ev = cmds.add_sprint(root, actor, a.goal, autonomy.parse_budget(a.budget or ""))
                sid = ev[0]["entity"]
        if not sid:
            b = hcore.load_board(root)
            want = {"start": "PLANNED", "review": "ACTIVE", "close": "REVIEW"}[a.transition]
            cand = [s["id"] for s in b["sprints"] if s["state"] == want]
            if not cand:
                raise hcore.Refused("nenhum sprint em %s (passe --id)" % want)
            sid = cand[-1]
        cmds.level_transition(root, actor, "sprint", sid, a.transition, {"add": stories, "reason": a.reason})
        out.append("sprint %s → %s" % (sid, a.transition))
    elif c == "session":
        if a.transition == "start":
            if not a.request:
                raise hcore.Refused("--request obrigatório (pedido do usuário, literal)")
            _, ev = cmds.session_start(root, actor, a.request, a.mode)
            out.append("sessão %s em TRIAGE → cs-state session triage --class ... --why ..." % ev[0]["entity"])
        elif a.transition == "status":
            ctx = engine.Ctx(root, hcore.load_board(root))
            s = cmds.active_session(ctx)
            out.append(views.why(ctx, s["id"]) if s else "nenhuma sessão ativa")
        else:
            cmds.session_cmd(root, actor, a.transition, {"class": a.klass, "why": a.why, "assume": a.assume, "note": a.note,
                                                         "by": a.by, "verdict": a.verdict, "findings": a.findings})
            out.append("sessão: %s ok" % a.transition)
    elif c == "ready":
        cmds.ready(root, actor, _tid(a))
        ctx = engine.Ctx(root, hcore.load_board(root))
        d = engine.latest_deleg(ctx.find("task", _tid(a)))
        out.append("BRIEFED %s — recomendação: model=%s (%s)" % (d["id"], (d.get("route") or {}).get("model"),
                                                               (d.get("route") or {}).get("band")))
        out.append("despache: " + views.next_for(ctx, "deleg", d))
    elif c == "dispatch":
        # D-1-02: o despacho legítimo é o hook pre-agent (ferramenta Agent) ou, sem hook, --manual; senão recusa
        cmds.dispatch(root, actor, _tid(a), model=a.model, tool_use_id=a.tool_use_id,
                      procedencia="declarada-cli" if a.model else None, require_tool_use_id=True,
                      manual=a.manual)
        out.append("DISPATCHED %s" % _tid(a))
    elif c == "submit":
        sub = j5.load(a.from_file) if a.from_file else {}
        if a.files_changed:
            sub["files_changed"] = _csv(a.files_changed)
        if a.check:
            sub["checks_run"] = a.check
        if a.risk:
            sub["risks"] = a.risk
        if a.handoff_notes:
            sub["handoff_notes"] = a.handoff_notes
        cmds.submit(root, actor, _tid(a), sub)
        out.append("RETURNED %s → cs-state verify --task %s" % (_tid(a), _tid(a)))
    elif c == "return":
        cmds.return_(root, actor, _tid(a), a.reason or "protocol_failure: retorno sem submission")
        out.append("REJECTED %s (protocol_failure)" % _tid(a))
    elif c == "verify":
        _, ev = cmds.verify(root, actor, _tid(a))
        probs = ev[-1]["data"].get("problems") or []
        g = ev[-1]["data"].get("gate") or {}
        if probs:
            out.append("verify REPROVOU %s (exit %s):" % (_tid(a), g.get("exit_code")))
            out += ["  - " + p for p in probs[:8]]
        else:
            out.append("verify PASS %s (exit 0, output_sha256 %s) → review por gate" % (_tid(a), g.get("output_sha256", "")[:12]))
    elif c == "review":
        cmds.review(root, actor, _tid(a), a.by, a.verdict, a.findings)
        out.append("review %s registrada" % a.verdict)
    elif c == "accept":
        cmds.accept(root, actor, _tid(a))
        out.append("ACCEPTED %s" % _tid(a))
        if tree_mode:
            out.append("próximo: cs-state close %s --summary '<o que foi entregue>' (vai para archive/)" % (
                a.task or a.task_pos or getattr(a, "task_id", None)))
    elif c == "reject":
        cmds.reject(root, actor, _tid(a), a.reason)
        out.append("REJECTED %s" % _tid(a))
    elif c == "retry":
        cmds.retry(root, actor, _tid(a), a.findings, a.decision)
        out.append("BRIEFED de novo (retry) %s" % _tid(a))
        ctx = engine.Ctx(root, hcore.load_board(root))
        t = ctx.find("task", cmds.resolve_task_id(ctx, _tid(a)))
        out.append("próximo: " + (views.next_for(ctx, "deleg", engine.latest_deleg(t)) or "cs-state next"))
    elif c in ("escalate", "block"):
        cmds.escalate(root, actor, _tid(a), a.reason)
        out.append("ESCALATED %s (task BLOCKED) — aguarda a decisão do humano; saídas:" % _tid(a))
        ctx = engine.Ctx(root, hcore.load_board(root))
        out += ["  " + x for x in views.exits_for(ctx, ctx.find("task", cmds.resolve_task_id(ctx, _tid(a))), "ESCALATED")]
    elif c == "reverify":
        _, ev = cmds.reverify(root, actor, _tid(a))
        probs = ev[-1]["data"].get("problems") or []
        g = ev[-1]["data"].get("gate") or {}
        if probs:
            out.append("reverify REPROVOU %s (exit %s, falha de %s):" % (_tid(a), g.get("exit_code"), g.get("failure_kind")))
            out += ["  - " + p for p in probs[:8]]
        else:
            out.append("reverify PASS %s (exit 0) → review por gate" % _tid(a))
        ctx = engine.Ctx(root, hcore.load_board(root))
        t = ctx.find("task", cmds.resolve_task_id(ctx, _tid(a)))
        out.append("próximo: " + (views.next_for(ctx, "deleg", engine.latest_deleg(t)) or "cs-state next"))
    elif c == "waive-verify":
        cmds.waive_verify(root, actor, _tid(a), a.reason, a.by, a.evidence or "")
        out.append("VERIFIED %s por EXCEÇÃO DE AMBIENTE (verify_waiver de %s) → review por gate obrigatória" % (_tid(a), a.by))
    elif c == "legacy-ack":
        _, ev = cmds.legacy_ack(root, actor, a.reason)
        args = ev[-1]["data"]["args"]
        out.append("histórico reconhecido (evento harness.legacy_ack): %d transição(ões), %d aceite(s) sem gate, "
                   "%d incoerência(s) de hierarquia" % (len(args["transitions"]), len(args["accepted"]),
                                                       len(args.get("hierarchy") or [])))
        out += ["  seq %s %s: %s→%s" % (x["seq"], x["ref"], x["from"], x["to"]) for x in args["transitions"][:20]]
        out += ["  ACCEPTED sem gate: %s (tentativa %s)" % (x["task"], x["attempt"]) for x in args["accepted"][:20]]
        out += ["  hierarquia: %s" % x["problem"] for x in (args.get("hierarchy") or [])[:20]]
    elif c == "drop":
        cmds.drop(root, actor, _tid(a), a.reason)
        out.append("DROPPED %s (task descartada e fechada)" % _tid(a))
    elif c == "reroute":
        cmds.reroute(root, actor, _tid(a), a.agent, a.reason, _csv(a.allowed_path) or None, a.decision)
        out.append("REROUTED %s → %s (nova delegação PLANNED: cs-state ready --task %s)" % (_tid(a), a.agent, _tid(a)))
    elif c == "abstain":
        cmds.abstain(root, actor, _tid(a), a.kind, a.reason)
        out.append("ABSTAINED %s (conta contra cobertura, não precisão) — aguarda a decisão do humano; saídas:" % _tid(a))
        out += ["  " + x for x in views.human_exits(_tid(a), abstained=True)]
    elif c == "delegate":
        cmds.delegate(root, actor, _tid(a))
        out.append("nova delegação PLANNED para %s" % _tid(a))
    elif c == "amend":
        cmds.amend(root, actor, _tid(a), a.field, _value(a.after), a.reason, a.found_by)
        out.append("emenda registrada em %s.%s" % (_tid(a), a.field))
    elif c == "brief":
        import brief
        ctx = engine.Ctx(root, hcore.load_board(root))
        t = ctx.find("task", cmds.resolve_task_id(ctx, _tid(a)))
        out.append(brief.package(ctx, t, a.phase, a.agent))
    elif c == "ask":
        cid = cmds.ask(root, actor, a.agent, a.question, _csv(a.paths))
        ctx = engine.Ctx(root, hcore.load_board(root))
        out.append(views.next_for(ctx, "consult", ctx.find("consult", cid)))
        out.append("(%s: consulta SÓ LEITURA a %s; fecha sozinha ao terminar — sem task, story ou review)" % (cid, a.agent))
    elif c == "consult":
        cmds.consult_cancel(root, actor, a.id, a.reason)
        out.append("consulta %s CANCELLED" % a.id)
    elif c == "status":
        out.append(views.status(engine.Ctx(root, hcore.load_board(root)), a.task))
    elif c == "board":
        out.append(views.board_tree(engine.Ctx(root, hcore.load_board(root))))
    elif c == "next":
        if tree_mode:
            import session
            import tree
            out += session._steps(tree.load_view(root))
        else:
            out += views.next_lines(engine.Ctx(root, hcore.load_board(root)))
    elif c == "why":
        out.append(views.why(engine.Ctx(root, hcore.load_board(root)), a.id))
    elif c == "autonomy":
        import autonomy
        if a.action == "start":
            m = autonomy.start(root, actor, a.feature or a.story, autonomy.parse_budget(a.budget), a.spec, a.accept_cmd or None,
                               a.accept_file or None, a.klass)
            out.append("mandato ACTIVE para %s (assinatura %s). Loop: cs-state next" % (m["target"], m["signature"][:12]))
        elif a.action == "status":
            m = autonomy.load(root)
            if not m:
                out.append("modo assistido (sem mandato)")
            else:
                b = hcore.load_board(root)
                esc = autonomy.detect_escalation(root, b, m) if m["state"] == "ACTIVE" else None
                out.append("mandato %s [%s] alvo %s orçamento %s" % (m["signature"][:12], m["state"], m["target"], m["budget"]))
                if m.get("escalation"):
                    out.append("escalada: %s" % m["escalation"]["condition"])
                elif esc:
                    out.append("condição de escalada detectada: %s" % esc[0])
        elif a.action == "resume":
            m = autonomy.resume(root, actor, a.decision)
            out.append("mandato %s ACTIVE de novo (decisão registrada). Loop: cs-state next" % m["signature"][:12])
        elif a.action == "stop":
            autonomy.stop(root, actor, a.reason or "parado")
            out.append("modo assistido; relatório em .swarm/state/autonomy-report.json5")
        elif a.action == "report":
            rep = autonomy.report(root)
            out.append(j5.dumps({k: rep[k] for k in ("target", "state", "elapsed_min", "acceptance_after", "escalation")}))
        elif a.action == "spend":
            m = autonomy.load(root)
            if not m:
                raise hcore.Refused("sem mandato")
            m.setdefault("spent", {})["usd"] = float(m["spent"].get("usd", 0)) + float(a.usd or 0)
            autonomy.save(root, m)
            out.append("gasto registrado: usd=%s" % m["spent"]["usd"])
    else:
        return None
    return out


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help(sys.stderr)
        return 2
    if a.cmd == "validate":
        import validate
        try:
            root = hcore.resolve_root(a.root)
        except hcore.StateError as e:
            sys.stderr.write("cs-state: ESTADO: %s\n" % e)
            return 2
        return validate.main(["--root", root] + (["--strict"] if a.strict else []) +
                             (["--allow-empty"] if a.allow_empty else []))
    try:
        out = run(a)
    except hcore.Refused as e:
        sys.stderr.write(e.render() + "\n")
        return 1
    except hcore.StateError as e:
        sys.stderr.write("cs-state: ESTADO: %s\n" % e)
        return 2
    if out is None:
        ap.print_help(sys.stderr)
        return 2
    print("\n".join(x for x in out if x))
    return 0


if __name__ == "__main__":
    sys.exit(main())
