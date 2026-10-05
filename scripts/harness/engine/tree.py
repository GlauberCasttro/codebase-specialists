"""tree — estado do harness como ÁRVORE DE PASTAS: épico → sprint → feature → (story) → task.

Layout (relativo a <STATE_DIR>/): backlog/ (esperando) · state/ (executando) · archive/ (fechado, mesma árvore) ·
events.jsonl (cadeia append-only na RAIZ) · INDEX.md (gerado) · state/sessoes/ (carimbos de cs-session).
O motor continua o ÚNICO escritor: todo item nasce/move/fecha por evento encadeado (ops tput/tdel/tmeta aplicadas à
projeção <STATE_DIR>/.engine/projection.json5, que é o antigo board) e as pastas são MATERIALIZADAS a partir da
projeção depois do commit. Edição à mão, órfão e fechado fora de archive/ são acusados por `cs-state validate`.
M2 (dispatch/submit/verify/review/accept/escalate) roda sobre a task M2 criada no `start` com o id da árvore.
"""
import copy
import json
import os
import posixpath
import re
import shutil
import time
import unicodedata

import hcore
import j5
import engine
from hcore import Refused, StateError

HEADER = "gerado por cs-state (motor único) — não editar à mão: cs-state validate acusa a edição"
ITEM_FILE = {"epico": "epico.json5", "sprint": "sprint.json5", "feature": "feature.json5", "story": "story.json5"}
ITEM_FILES = tuple(ITEM_FILE.values())
TIPOS = ("US", "BUG", "FIX", "CHORE")
STORY_TIPOS = ("US", "BUG", "FIX")
M2_DONE = ("ACCEPTED", "DROPPED")
M2_FLIGHT = ("DISPATCHED", "RETURNED", "VERIFIED", "REVIEWED")
AVULSA, BKL = "AVULSA", "BKL"
ZONES = hcore.TREE_ZONES
SESSOES = "state/sessoes"


# ================================================================ util
def sd_rel(path):
    """caminho relativo ao alvo (o que `criado ... em <path>` imprime)."""
    return "%s/%s" % (hcore.STATE_DIR, path)


def zone_of(path):
    return path.split("/", 1)[0]


def rest_of(path):
    return path.split("/", 1)[1] if "/" in path else ""


def slugify(text):
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii").lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:48].rstrip("-") or "item"


def today():
    return time.strftime("%Y-%m-%d")


def render(item):
    return j5.dumps(item, header=HEADER)


def tree_root(root):
    return os.path.join(root, hcore.STATE_DIR)


def is_item_file(relpath):
    """Arquivo de ITEM dentro de uma zona (relativo a <STATE_DIR>/)."""
    if relpath.startswith(SESSOES + "/") or not relpath.endswith(".json5"):
        return False
    parts = relpath.split("/")
    return parts[-1] in ITEM_FILES or "tasks" in parts[1:-1]


def disk_items(root):
    """{relpath (rel a <STATE_DIR>): abspath} dos arquivos de item nas três zonas."""
    out = {}
    base = tree_root(root)
    for z in ZONES:
        for dp, dns, fs in os.walk(os.path.join(base, z)):
            dns.sort()
            for f in sorted(fs):
                p = os.path.join(dp, f)
                r = os.path.relpath(p, base).replace(os.sep, "/")
                if is_item_file(r):
                    out[r] = p
    return out


def run_test(root, cfg, test_id, timeout=600):
    cmd = engine.resolve_test(cfg, test_id) or test_id
    return engine.run_cmd(root, cmd, timeout)


def run_shell(root, cmd, timeout=900):
    return engine.run_cmd(root, cmd, timeout)


# ================================================================ visão de trabalho sobre a projeção
class T(object):
    """Cópia de trabalho da árvore dentro de um build (nunca muta ctx.board: o commit aplica as ops)."""

    def __init__(self, ctx, dry=False):
        self.ctx = ctx
        self.root = ctx.root
        self.items = copy.deepcopy(ctx.board.get("tree") or {})
        self.meta = copy.deepcopy(ctx.board.get("tree_meta") or {})
        self.ops = []
        self.board_ops = []
        self.dry = dry
        self.actor = ctx.actor

    # ---- leitura
    def get(self, ident):
        if not ident:
            return None
        if ident in self.items:
            return self.items[ident]
        for it in self.items.values():
            if ident in (it.get("aliases") or []):
                return it
        return None

    def need(self, ident, kinds=None, what=None):
        it = self.get(ident)
        if it is None:
            raise Refused("%s %s inexistente (cs-state find %s)" % (what or "item", ident, ident))
        if kinds and it["kind"] not in kinds:
            raise Refused("%s é %s; esperado %s" % (ident, it["kind"], "|".join(kinds)))
        return it

    def by_kind(self, kind, zone=None):
        return sorted([it for it in self.items.values() if it["kind"] == kind and (zone is None or zone_of(it["path"]) == zone)],
                      key=lambda x: x["path"])

    def folder(self, it):
        return posixpath.dirname(it["path"])

    def descendants(self, it):
        """Itens dentro da pasta do item (mesma zona), sem o próprio; task não tem descendentes."""
        if it["kind"] not in ITEM_FILE:
            return []
        pre = self.folder(it) + "/"
        return sorted([x for x in self.items.values() if x["id"] != it["id"] and x["path"].startswith(pre)],
                      key=lambda x: x["path"])

    def same_rest(self, it, kind=None):
        """Itens (qualquer zona) cuja parte depois da zona começa pela pasta do item (fechados em archive/ inclusive)."""
        pre = rest_of(self.folder(it)) + "/"
        return [x for x in self.items.values() if rest_of(x["path"]).startswith(pre) and x["id"] != it["id"]
                and (kind is None or x["kind"] == kind)]

    def container_of(self, it):
        """Item-pai pelo caminho (pasta acima de tasks/, stories/, features/, sprints/)."""
        d = posixpath.dirname(it["path"])
        if it["kind"] in ITEM_FILE:
            d = posixpath.dirname(d)
        if posixpath.basename(d) in ("tasks", "stories", "features", "sprints"):
            d = posixpath.dirname(d)
        for x in self.items.values():
            if x["kind"] in ITEM_FILE and self.folder(x) == d:
                return x
        return None

    def m2(self, it):
        return self.ctx.find("task", it.get("m2") or "") if it.get("m2") else None

    def m2_status(self, it):
        t = self.m2(it)
        if not t:
            return None, None
        d = engine.latest_deleg(t)
        return t["status"], (d or {}).get("state")

    def in_progress(self, it):
        """task iniciada e ainda não fechada pelo M2 (D-0-12: "em andamento")."""
        if it["kind"] != "task" or zone_of(it["path"]) == "archive":
            return False
        st, _ = self.m2_status(it)
        return st is not None and st not in M2_DONE

    # ---- escrita (ops)
    def put(self, it):
        self.items[it["id"]] = it
        self.ops.append(["tput", it["id"], None, copy.deepcopy(it)])

    def delete(self, ident):
        del self.items[ident]
        self.ops.append(["tdel", ident, None, None])

    def counter(self, key):
        n = int(self.meta.get(key) or 0) + 1
        self.meta[key] = n
        self.ops.append(["tmeta", key, None, n])
        return n

    def note(self, it, acao, reason=None, **kw):
        h = {"at": hcore.now_iso(), "acao": acao, "by": self.actor}
        if reason:
            h["reason"] = reason
        h.update(kw)
        it.setdefault("historico", []).append(h)

    def event(self, acao, entity, data=None):
        ev = engine.Event("arvore.%s" % acao, entity, self.board_ops + self.ops, data or {})
        self.ops, self.board_ops = [], []
        return ev

    # ---- caminhos
    def move_subtree(self, it, new_folder):
        old = self.folder(it)
        moved = [it] + self.descendants(it)
        for x in moved:
            x = self.items[x["id"]]
            x["path"] = new_folder + x["path"][len(old):]
            self.put(x)

    def archive_path(self, path, it):
        if it["kind"] == "task" and it.get("parent") == AVULSA:
            ident = it["id"]
            return "archive/tasks/%s/%s/%s" % (ident[:4], ident[5:7], posixpath.basename(path))
        return "archive/" + rest_of(path)


def new_item(kind, ident, title, path, actor, **kw):
    it = {"id": ident, "kind": kind, "title": title, "path": path, "created_at": hcore.now_iso(), "created_by": actor,
          "aliases": [], "historico": []}
    it.update({k: v for k, v in kw.items() if v not in (None, [], "")})
    return it


# ================================================================ plano (saída de --dry-run e de `new`)
def make_plan(before, after, events):
    ids, criar, mover = [], [], []
    seen = set()
    for ev in events:
        for op in ev.ops:
            if op[0] != "tput" or op[1] in seen:
                continue
            seen.add(op[1])
            iid = op[1]
            it = after.get(iid)
            if it is None:
                continue
            if iid in before:
                if before[iid]["path"] != it["path"]:
                    mover.append({"id": iid, "de": sd_rel(before[iid]["path"]), "para": sd_rel(it["path"])})
                continue
            old = [a for a in it.get("aliases") or [] if a in before and a not in after]
            if old:
                mover.append({"id": iid, "de": sd_rel(before[old[-1]]["path"]), "para": sd_rel(it["path"]),
                              "id_anterior": old[-1]})
                continue
            ids.append(iid)
            criar.append(sd_rel(it["path"]))
    return {"ids": ids, "criar": criar, "mover": mover,
            "eventos": ["%s %s" % (ev.type, ev.entity or "") for ev in events]}


def need_tree(root):
    if not hcore.tree_mode(root):
        if os.path.isfile(os.path.join(root, hcore.STATE_DIR, "state", "board.json5")):
            raise StateError("estado em board plano (legado): rode cs-state migrate state-tree")
        raise StateError("estado em árvore ausente: rode cs-state init")


def run_build(root, actor, build, dry_run=False):
    """Executa build(T) → [Event]. dry_run: nada é escrito (devolve o plano); senão commit encadeado + materialização."""
    need_tree(root)
    holder = {}

    def wrapped(ctx):
        holder["before"] = copy.deepcopy(ctx.board.get("tree") or {})
        tv = T(ctx, dry=dry_run)
        evs = build(tv) or []
        holder["evs"] = evs
        holder["tv"] = tv
        return evs
    if dry_run:
        board = hcore.load_board(root)
        ctx = engine.Ctx(root, board, actor)
        evs = wrapped(ctx)
        trial = copy.deepcopy(board)
        for ev in evs:
            hcore.apply_ops(trial, ev.ops)
        return make_plan(holder["before"], trial.get("tree") or {}, evs), holder.get("tv")
    ctx, written = engine.commit(root, actor, wrapped)
    return make_plan(holder["before"], ctx.board.get("tree") or {}, holder.get("evs") or []), holder.get("tv")


# ================================================================ init
def init(root):
    """Cria o estado em árvore. False se já existe (idempotente)."""
    sp = tree_root(root)
    legacy = os.path.join(sp, "state", "board.json5")
    if hcore.tree_mode(root):
        return False
    if os.path.isfile(legacy):
        try:
            b = hcore.load_board(root)
        except StateError:
            return None
        if any(b.get(lst) for lst in hcore.BOARD_LISTS.values()):
            return None  # board plano COM histórico: migração explícita (cs-state migrate state-tree), com backup
        migrate(root, "install")  # board plano recém-instalado (vazio): vira árvore sem perder a cadeia (backup feito)
        return True
    p = hcore.tree_paths(root)
    os.makedirs(p["state_dir"], exist_ok=True)
    for z in ZONES:
        os.makedirs(os.path.join(sp, z), exist_ok=True)
    with hcore.file_lock(p["lock"]):
        board = hcore.new_board()
        board["tree"], board["tree_meta"] = {}, {}
        h, seq = hcore.append_chained(p["events"], {"at": hcore.now_iso(), "actor": "install", "type": "init", "entity": None,
                                                    "ops": [], "data": {"schema_version": hcore.SCHEMA_VERSION,
                                                                        "layout": "tree"}})
        board["event_count"], board["last_event_hash"] = seq + 1, h
        hcore.save_board(root, board)
        write_index(root, board)
    return True


# ================================================================ materialização (só o motor chama, sob o lock)
def materialize(root, before, board):
    after = board.get("tree") or {}
    base = tree_root(root)
    removed_dirs = set()
    for iid, it in before.items():
        if iid not in after or after[iid]["path"] != it["path"]:
            p = os.path.join(base, it["path"])
            if os.path.isfile(p):
                os.remove(p)
            removed_dirs.add(os.path.dirname(p))
    for iid, it in after.items():
        if iid in before and before[iid] == it:
            continue
        p = os.path.join(base, it["path"])
        os.makedirs(os.path.dirname(p), exist_ok=True)
        hcore.atomic_write_bytes(p, render(it).encode("utf-8"))
    stops = {os.path.join(base, z) for z in ZONES}
    for d in sorted(removed_dirs, key=len, reverse=True):
        cur = d
        while cur not in stops and cur.startswith(base + os.sep) and os.path.isdir(cur) and not os.listdir(cur):
            os.rmdir(cur)
            cur = os.path.dirname(cur)
    for z in ZONES:
        os.makedirs(os.path.join(base, z), exist_ok=True)
    write_index(root, board)


def write_index(root, board):
    items = board.get("tree") or {}
    L = ["# INDEX — gerado por cs-state (não editar; visão: cs-state board | tree)", ""]
    for z, title in (("state", "Em execução (state/)"), ("backlog", "Backlog (backlog/)")):
        L.append("## " + title)
        rows = sorted([it for it in items.values() if zone_of(it["path"]) == z], key=lambda x: x["path"])
        L += ["- %s %s — %s — %s" % (it["id"], it["kind"], it.get("title") or it.get("meta") or "", sd_rel(it["path"]))
              for it in rows] or ["- nenhum"]
        L.append("")
    L.append("## Fechados recentes (archive/)")
    closed = sorted([it for it in items.values() if zone_of(it["path"]) == "archive"],
                    key=lambda x: (x.get("closed") or {}).get("at") or "", reverse=True)[:15]
    L += ["- %s %s — %s — %s" % (it["id"], it["kind"], it.get("title") or it.get("meta") or "", sd_rel(it["path"]))
          for it in closed] or ["- nenhum"]
    hcore.atomic_write_bytes(hcore.tree_paths(root)["index"], ("\n".join(L) + "\n").encode("utf-8"))


# ================================================================ new
def _parent_folder(tv, pid, kinds):
    p = tv.need(pid, kinds)
    if zone_of(p["path"]) == "archive":
        raise Refused("%s está fechado (archive/): reabra antes (cs-state reopen %s --reason ...)" % (p["id"], p["id"]))
    return p


def new_epico(tv, title, objetivo, metrica=None):
    n = tv.counter("seq.EPC")
    eid = "EPC-%03d" % n
    it = new_item("epico", eid, title, "backlog/epicos/%s-%s/epico.json5" % (eid, slugify(title)), tv.actor,
                  objetivo=objetivo, metrica=metrica)
    tv.note(it, "criado")
    tv.put(it)
    return [tv.event("new", eid, {"kind": "epico"})]


def new_sprint(tv, meta, epico=None):
    if epico:
        _parent_folder(tv, epico, ("epico",))
        epico = tv.get(epico)["id"]
    n = tv.counter("seq.SPR")
    sid = "SPR-%03d" % n
    it = new_item("sprint", sid, meta, "backlog/sprints/%s/sprint.json5" % sid, tv.actor, meta=meta, epico=epico)
    tv.note(it, "criado")
    tv.put(it)
    return [tv.event("new", sid, {"kind": "sprint"})]


def new_feature(tv, title, aceite, sprint=None):
    if sprint:
        _parent_folder(tv, sprint, ("sprint",))
        sprint = tv.get(sprint)["id"]
    n = tv.counter("seq.FEA")
    fid = "FEA-%03d" % n
    it = new_item("feature", fid, title, "backlog/features/%s-%s/feature.json5" % (fid, slugify(title)), tv.actor,
                  aceite=aceite, sprint=sprint)
    tv.note(it, "criado")
    tv.put(it)
    return [tv.event("new", fid, {"kind": "feature"})]


def _criterios(items):
    out = []
    for i, it in enumerate(items or []):
        parts = [p.strip() for p in it.split("|")]
        if len(parts) == 2:
            parts = ["AC-%d" % (i + 1)] + parts
        if len(parts) == 1:
            parts = ["AC-%d" % (i + 1), parts[0], ""]
        if len(parts) != 3 or not parts[1]:
            raise Refused("--criterio deve ser 'AC-n|Dado … Quando … Então …|<test-id>'")
        out.append({"id": parts[0], "gherkin": parts[1], "teste": parts[2] or None})
    return out


def task_fields(spec):
    """Campos tipados da task (spec: dict do CLI)."""
    tipo = (spec.get("tipo") or "US").upper()
    if tipo not in TIPOS:
        raise Refused("--tipo deve ser %s" % "|".join(TIPOS))
    f = {"tipo": tipo, "agent": spec.get("agent"), "allowed_paths": [hcore.norm_rel(p) for p in spec.get("allowed_paths") or []],
         "verify_cmd": (spec.get("verify_cmd") or "").strip() or None}
    if tipo == "CHORE":
        if any(spec.get(k) for k in ("como", "quero", "para")):
            raise Refused("CHORE é manutenção técnica sem valor de usuário: sem --como/--quero/--para (use --motivo)")
        f["motivo"] = (spec.get("motivo") or "").strip() or None
    else:
        for k in ("como", "quero", "para"):
            if spec.get(k):
                f[k] = spec[k]
        crit = _criterios(spec.get("criterio"))
        if crit:
            f["criterios"] = crit
        if spec.get("reproducao"):
            f["reproducao"] = spec["reproducao"]
        if spec.get("fixes"):
            f["fixes"] = spec["fixes"]
        if spec.get("teste"):
            f["teste"] = spec["teste"]
        if spec.get("motivo"):
            f["motivo"] = spec["motivo"]
    return {k: v for k, v in f.items() if v not in (None, [], "")}


def _task_slot(tv, parent_kind, parent_id, tipo, title):
    """(id, path, parent) da próxima task no pai (nn nunca reaproveitado)."""
    slug = slugify(title)
    if parent_kind == "avulsa":
        d = today()
        n = tv.counter("nn." + d)
        tid = "%s-%02d" % (d, n)
        return tid, "state/tasks/%s-%s-%s.json5" % (tid, tipo, slug), AVULSA
    if parent_kind == "backlog":
        n = tv.counter("nn." + BKL)
        return "%s/%02d" % (BKL, n), "backlog/tasks/%02d-%s-%s.json5" % (n, tipo, slug), BKL
    p = _parent_folder(tv, parent_id, (parent_kind,))
    n = tv.counter("nn." + p["id"])
    return "%s/%02d" % (p["id"], n), "%s/tasks/%02d-%s-%s.json5" % (tv.folder(p), n, tipo, slug), p["id"]


def _parent_args(spec):
    got = [(k, spec.get(k)) for k in ("feature", "sprint", "story") if spec.get(k)]
    if spec.get("avulsa"):
        got.append(("avulsa", True))
    if spec.get("backlog"):
        got.append(("backlog", True))
    if len(got) != 1:
        raise Refused("task tem exatamente UM pai: --feature F | --sprint S | --story US-nnn | --avulsa | --backlog "
                      "(veio: %s)" % (", ".join("--" + k for k, _ in got) or "nenhum"))
    return got[0]


def add_task_item(tv, spec, title, parent_kind, parent_id, extra=None):
    fields = task_fields(spec)
    if not fields.get("agent"):
        raise Refused("--agent obrigatório")
    tid, path, parent = _task_slot(tv, parent_kind, parent_id, fields["tipo"], title)
    it = new_item("task", tid, title, path, tv.actor, parent=parent, **fields)
    if extra:
        it.update(extra)
    tv.note(it, "criado")
    tv.put(it)
    return it


def new_task(tv, spec):
    pk, pv = _parent_args(spec)
    title = spec.get("title") or ""
    if not title.strip():
        raise Refused("--title obrigatório")
    it = add_task_item(tv, spec, title, pk, pv if pk not in ("avulsa", "backlog") else None)
    return [tv.event("new", it["id"], {"kind": "task", "tipo": it["tipo"]})]


def territory_paths(tv, agent):
    terr = tv.ctx.territory(agent)
    if not terr:
        raise Refused("agente %s sem território em team.json5 (passe --allowed-path)" % agent)
    return terr


def new_story(tv, spec):
    tipo = (spec.get("tipo") or "US").upper()
    if tipo not in STORY_TIPOS:
        raise Refused("story é US|BUG|FIX (CHORE só como task)")
    agents = []
    for a in spec.get("agents") or []:
        agents += [x.strip() for x in a.split(",") if x.strip()]
    if not agents:
        raise Refused("--agents a[,b] obrigatório")
    for a in agents:
        if not hcore.team_agent(tv.ctx.team, a):
            raise Refused("agente %r não existe em team.json5" % a)
    feat = _parent_folder(tv, spec.get("feature"), ("feature",))
    title = spec.get("title") or ""
    if len(agents) == 1:
        s = dict(spec)
        s["agent"] = agents[0]
        s["allowed_paths"] = spec.get("allowed_paths") or territory_paths(tv, agents[0])
        it = add_task_item(tv, s, title, "feature", feat["id"])
        return [tv.event("new", it["id"], {"kind": "story-simples", "tipo": tipo})]
    n = tv.counter("seq." + tipo)
    stid = "%s-%03d" % (tipo, n)
    fields = task_fields(dict(spec, tipo=tipo, agent=agents[0]))
    st = new_item("story", stid, title, "%s/stories/%s-%s/story.json5" % (tv.folder(feat), stid, slugify(title)), tv.actor,
                  tipo=tipo, agents=agents, como=fields.get("como"), quero=fields.get("quero"), para=fields.get("para"),
                  criterios=fields.get("criterios"), verify_cmd=fields.get("verify_cmd"),
                  reproducao=fields.get("reproducao"), fixes=fields.get("fixes"), teste=fields.get("teste"))
    tv.note(st, "criado")
    tv.put(st)
    for a in agents:
        s = dict(spec, tipo=tipo, agent=a, allowed_paths=territory_paths(tv, a))
        add_task_item(tv, s, "%s (%s)" % (title, a), "story", stid)
    return [tv.event("new", stid, {"kind": "story", "tipo": tipo, "agents": agents})]


# ================================================================ DoR (check e start usam a MESMA regra)
def task_dor(tv, it, run=True):
    P = []
    tipo = it.get("tipo")
    if tipo == "US":
        if not it.get("criterios"):
            P.append("US sem critério de aceite: --criterio 'AC-n|Dado … Quando … Então …|<test-id>'")
        for k in ("como", "quero", "para"):
            if not it.get(k):
                P.append("US sem --%s (história: como/quero/para)" % k)
    elif tipo == "BUG":
        r = it.get("reproducao")
        if not r:
            P.append("BUG sem --reproducao <test-id>: o teste de reprodução precisa FALHAR hoje")
        elif run:
            res = run_test(tv.root, tv.ctx.cfg, r)
            if res["exit_code"] == 0:
                P.append("o teste de reprodução %s já passa hoje: o BUG não reproduz (exige teste vermelho)" % r)
    elif tipo == "FIX":
        fx = it.get("fixes")
        if not fx:
            P.append("FIX sem --fixes <id do BUG> (o que esta correção conserta)")
        elif it.get("mandato") and str(fx) == "%s:regressao" % it["mandato"]:
            pass  # M5: nó FIX de replano de regressão — o motor preenche `fixes` com a regressão do mandato (decisão 17)
        else:
            bug = tv.get(fx)
            if bug is None or bug.get("kind") != "task" or bug.get("tipo") != "BUG":
                P.append("fixes %s não é um BUG da árvore (cs-state find %s)" % (fx, fx))
        if not it.get("teste"):
            P.append("FIX sem --teste <test-id> (o teste que prova a correção)")
    elif tipo == "CHORE":
        if not it.get("motivo"):
            P.append("CHORE sem motivo: --motivo '<por que a manutenção técnica é necessária>'")
        if not it.get("verify_cmd"):
            P.append("CHORE sem verify-cmd: --verify-cmd '<prova executável da manutenção>'")
    if tipo != "CHORE" and not it.get("verify_cmd"):
        P.append("task sem --verify-cmd (prova executável)")
    if not it.get("allowed_paths"):
        P.append("task sem --allowed-path (território da escrita)")
    return P


def feature_dor(tv, it, run=True):
    P = []
    if not it.get("aceite"):
        P.append("feature sem --aceite <cmd> (teste de aceite)")
    elif run:
        res = run_shell(tv.root, it["aceite"])
        if res["exit_code"] == 0:
            P.append("o teste de aceite já passa hoje (%s exit 0): feature sem aceite vermelho não tem o que entregar"
                     % it["aceite"])
    return P


# ================================================================ sincronia M2 → arquivo da task (reroute/retry/ready)
SYNC_FIELDS = ("agent", "route")


def _route_view(r):
    return {"model": r.get("model"), "band": r.get("band")} if isinstance(r, dict) else None


def item_of_m2(board, m2_id):
    """Item de task da árvore cuja task M2 é `m2_id` (None fora do modo árvore ou task sem item)."""
    for it in (board.get("tree") or {}).values():
        if it.get("kind") == "task" and it.get("m2") == m2_id:
            return it
    return None


def sync_m2_event(board, ev, m2_id, actor, acao, **fields):
    """O comando M2 (reroute/retry/ready) mudou `agent`/`route` da delegação: o MESMO evento grava o arquivo da task
    (op tput, motor = escritor único) e registra `data.de`/`data.para` (convenção de `arvore.move`), em objetos.
    Sem item de árvore (board plano) não faz nada; sem mudança, só o de/para (o arquivo já está coerente).
    Devolve o evento."""
    it = item_of_m2(board, m2_id)
    if it is None:
        return ev
    new = copy.deepcopy(it)
    de, para = {}, {}
    for k in SYNC_FIELDS:
        if k not in fields:
            continue
        val = _route_view(fields[k]) if k == "route" else fields[k]
        de[k] = _route_view(it.get(k)) if k == "route" else it.get(k)
        para[k] = val
        if val is None:
            new.pop(k, None)
        else:
            new[k] = val
    if new != it:  # sem mudança (ex.: retomada no mesmo tier) o arquivo fica; o evento registra de/para assim mesmo
        h = {"at": hcore.now_iso(), "acao": acao, "by": actor}
        h.update({"de": de, "para": para})
        new.setdefault("historico", []).append(h)
        ev.ops.append(["tput", it["id"], None, new])
    ev.data = dict(ev.data or {})
    ev.data.update({"arvore": it["id"], "m2": m2_id, "de": de, "para": para})
    return ev


# ================================================================ start
def _m2_task(tv, it, wave):
    ctx = tv.ctx
    ap = list(it.get("allowed_paths") or [])
    acs = []
    for c in it.get("criterios") or []:
        t = c.get("teste")
        vb = "test:%s" % t if t and engine.resolve_test(ctx.cfg, t) else "verification_command"
        acs.append({"id": c["id"], "criterion": c["gherkin"], "verified_by": vb})
    if not acs:
        acs = [{"id": "AC-1", "criterion": "%s %s — verification_command com exit 0" % (it["tipo"], it["title"]),
                "verified_by": "verification_command"}]
    n = int(it.get("reaberta") or 0)
    mid = it["id"] if not n else "%s-r%d" % (it["id"], n)
    while ctx.find("task", mid):
        n += 1
        mid = "%s-r%d" % (it["id"], n)
    story_txt = ", ".join("%s %s" % (k, it[k]) for k in ("como", "quero", "para") if it.get(k))
    goal = it["title"] + (" — " + story_txt if story_txt else "") + (" — motivo: " + it["motivo"] if it.get("motivo") else "")
    now = hcore.now_iso()
    t = {"id": mid, "tree": True, "tree_id": it["id"], "story": it.get("parent") or AVULSA, "sprint": None, "session": None,
         "agent": it["agent"], "title": it["title"], "goal": goal, "class": "pequena", "wave": wave, "depends_on": [],
         "flags": {"hot_path": False, "security_gate": False}, "readonly": False, "allowed_paths": ap,
         "protected_paths": [], "work_type": it["tipo"],
         "briefing": {"references": [], "scope": {"in": [it["title"]], "out": []},
                      "invariants": engine.required_invariants(ctx, ap) if ap else [], "context": story_txt},
         "acceptance_criteria": acs, "dod": [], "verification_command": it.get("verify_cmd") or "",
         "knowledge_context": [], "handoff": {}, "status": "DRAFT", "attempts": 0, "amendments": [], "submission": None,
         "reviews": [], "gate_report": {"build": None, "verdict": None, "by": None, "at": None},
         "created_at": now, "updated_at": now}
    d = {"id": "%s.d1" % mid, "agent": it["agent"], "state": "PLANNED", "retries": 0, "created_at": now}
    return t, d


def _wave(tv, it):
    ctx = tv.ctx
    w = 0
    for x in tv.items.values():
        if x["id"] == it["id"] or x["kind"] != "task" or not tv.in_progress(x) or not x.get("wave"):
            continue
        clash = hcore.scopes_overlap(x.get("allowed_paths") or [], it.get("allowed_paths") or [])
        if not clash and x.get("agent") != it.get("agent"):
            clash = bool(engine.collision_reason(ctx, x.get("agent"), it.get("agent")))
        if clash:
            w = max(w, int(x["wave"]))
    return w + 1


def start_task(tv, it):
    z = zone_of(it["path"])
    if z == "archive":
        raise Refused("%s está fechada: cs-state reopen %s --reason ..." % (it["id"], it["id"]))
    if z == "backlog":
        raise Refused("%s está no backlog: planeje antes (cs-state plan %s --sprint SPR-nnn | cs-state move %s --avulsa)"
                      % (it["id"], it["id"], it["id"]))
    st, _ = tv.m2_status(it)
    if st is not None and not (st in M2_DONE and it.get("reaberta")):
        raise Refused("%s já iniciada (M2 %s): siga o pipeline (cs-state board)" % (it["id"], st))
    if not it.get("mandato") and tv.ctx.board.get("mandatos"):
        import auto  # M5: task fora do mandato cujo allowed_path colide com o DAG ativo não inicia
        clash = auto.dag_collision(tv, it)
        if clash:
            raise Refused("%s: %s" % (it["id"], clash))
    P = task_dor(tv, it, run=True)
    if P:
        raise Refused(["DoR de %s (%s) não atendido:" % (it["id"], it.get("tipo"))] + P,
                      hint="corrija criando a task de novo com os campos (cs-state new task ... --dry-run mostra antes)")
    import router
    wave = _wave(tv, it)
    t, d = _m2_task(tv, it, wave)
    ops = [["create", "task", None, t], ["create", "deleg", t["id"], d]]
    ctx2 = engine.Ctx(tv.root, copy.deepcopy(tv.ctx.board), tv.actor)
    hcore.apply_ops(ctx2.board, ops)
    rec = {}

    def extra(to, probs):
        rec.update(router.recommend(ctx2, t, d, act="dev", log=not tv.dry))
        return [["set", engine.ref("deleg", d["id"]), "route", rec]]
    ev = engine.transition(ctx2, "deleg", d["id"], "ready", {}, extra)
    tv.board_ops += ops + ev.ops
    it = tv.items[it["id"]]
    it["m2"], it["wave"], it["started_at"] = t["id"], wave, hcore.now_iso()
    it["route"] = {"model": rec.get("model"), "band": rec.get("band")}
    tv.note(it, "start", wave=wave)
    tv.put(it)
    return [tv.event("start", it["id"], {"kind": "task", "m2": t["id"], "wave": wave, "delegacao": d["id"]})]


def start(tv, ident):
    it = tv.need(ident)
    k = it["kind"]
    if k == "task":
        return start_task(tv, it)
    if k == "story":
        raise Refused("story composta não inicia sozinha: inicie cada task (cs-state start %s/01 ...)" % it["id"])
    if zone_of(it["path"]) != "backlog":
        raise Refused("%s não está no backlog (%s): nada a iniciar" % (it["id"], zone_of(it["path"])))
    if k == "epico":
        if not it.get("objetivo"):
            raise Refused("DoR do épico: --objetivo ausente")
        tv.move_subtree(it, "state/epicos/" + posixpath.basename(tv.folder(it)))
    elif k == "sprint":
        if not it.get("meta"):
            raise Refused("DoR da sprint: --meta ausente")
        dest = "state/sprints/" + it["id"]
        if it.get("epico"):
            ep = tv.need(it["epico"], ("epico",))
            if zone_of(ep["path"]) != "state":
                raise Refused("sprint %s pertence ao épico %s, que não está em execução: cs-state start %s" % (
                    it["id"], ep["id"], ep["id"]))
            dest = "%s/sprints/%s" % (tv.folder(ep), it["id"])
        tv.move_subtree(it, dest)
    elif k == "feature":
        act = [f for f in tv.by_kind("feature", "state") if f["id"] != it["id"]]
        if act:
            a = act[0]
            raise Refused("feature %s já está ativa em state/ (UMA feature por vez): feche (cs-state close %s --summary ...) "
                          "ou estacione (cs-state park %s --reason ...) antes de iniciar %s" % (a["id"], a["id"], a["id"], it["id"]))
        if not it.get("sprint"):
            raise Refused("feature %s sem sprint: toda feature executa dentro de uma sprint "
                          "(cs-state move %s --to SPR-nnn)" % (it["id"], it["id"]))
        sp = tv.need(it["sprint"], ("sprint",))
        if zone_of(sp["path"]) != "state":
            raise Refused("sprint %s da feature %s não está em execução: cs-state start %s" % (sp["id"], it["id"], sp["id"]))
        P = feature_dor(tv, it, run=True)
        if P:
            raise Refused(["DoR da feature %s não atendido:" % it["id"]] + P)
        tv.move_subtree(it, "%s/features/%s" % (tv.folder(sp), posixpath.basename(tv.folder(it))))
    it = tv.items[it["id"]]
    tv.note(it, "start")
    tv.put(it)
    return [tv.event("start", it["id"], {"kind": k})]


# ================================================================ check (SÓ LEITURA)
def check(root, ident):
    need_tree(root)
    board = hcore.load_board(root)
    ctx = engine.Ctx(root, board)
    tv = T(ctx, dry=True)
    it = tv.need(ident)
    started = it["kind"] == "task" and tv.m2(it) is not None and not it.get("reaberta")
    if it["kind"] == "task" and (started or zone_of(it["path"]) != "state"):
        P = task_dor(tv, it, run=not started)
    elif it["kind"] == "feature" and zone_of(it["path"]) != "backlog":
        P = feature_dor(tv, it, run=False)
    elif it["kind"] in ("story",) or zone_of(it["path"]) == "archive":
        P = []
    else:
        try:
            start(tv, ident)
            P = []
        except Refused as e:
            P = [p for p in e.problems if not p.endswith("não atendido:")]
    return it, P


# ================================================================ close / park / drop / reopen
def _closed(tv, summary, entregue=None, devolvido=None, metricas=None, origem=None):
    c = {"at": hcore.now_iso(), "by": tv.actor, "summary": summary, "entregue": entregue or [],
         "devolvido": devolvido or [], "metricas": metricas or {}}
    if origem:
        c["origem"] = origem
    return c


def _to_archive(tv, it, closed):
    """Move o item (e a subárvore ainda fora de archive/) para archive/ no mesmo caminho."""
    it = tv.items[it["id"]]
    origin = zone_of(it["path"])
    closed["origem"] = origin
    if it["kind"] == "task":
        it["path"] = tv.archive_path(it["path"], it)
        it["closed"] = closed
        tv.put(it)
        return
    old = tv.folder(it)
    new = "archive/" + rest_of(old)
    for x in [it] + tv.descendants(it):
        x = tv.items[x["id"]]
        x["path"] = new + x["path"][len(old):]
        if x["id"] == it["id"]:
            x["closed"] = closed
        elif not x.get("closed"):
            x["closed"] = _closed(tv, "fechado junto com %s" % it["id"], origem=origin)
        tv.put(x)


def _open_tasks_under(tv, it):
    return [x for x in tv.descendants(it) if x["kind"] == "task" and not x.get("closed")]


def _to_backlog_task(tv, x, reason):
    """task aberta (não iniciada) volta ao backlog/tasks com novo id BKL/nn (id antigo continua resolvendo)."""
    old_id = x["id"]
    nx = copy.deepcopy(tv.items[old_id])
    n = tv.counter("nn." + BKL)
    nid = "%s/%02d" % (BKL, n)
    base = re.sub(r"^(\d{4}-\d{2}-\d{2}-)?\d{2}-", "", posixpath.basename(nx["path"]))
    nx.update({"id": nid, "path": "backlog/tasks/%02d-%s" % (n, base), "parent": BKL})
    nx["aliases"] = list(nx.get("aliases") or []) + [old_id]
    for k in ("wave", "started_at", "route"):
        nx.pop(k, None)
    tv.note(nx, "devolvido", reason)
    tv.delete(old_id)
    tv.put(nx)
    return nid


def close(tv, ident, summary, devolver=False, reason=None):
    it = tv.need(ident)
    k = it["kind"]
    z = zone_of(it["path"])
    if z == "archive":
        raise Refused("%s já está fechado (archive/)" % it["id"])
    if devolver and not (reason or "").strip():
        raise Refused("--devolver exige --reason (o motivo vai para o item devolvido)")
    if k == "task":
        st, ds = tv.m2_status(it)
        if st != "ACCEPTED" and st != "DROPPED":
            raise Refused("%s: M2 %s/%s — close só depois de ACCEPTED (dispatch → submit → verify → review → accept); "
                          "nenhum atalho para o aceite" % (it["id"], st or "não iniciada", ds or "-"))
        if it.get("tipo") == "FIX":
            tests = []
            bug = tv.get(it.get("fixes") or "")
            if bug and bug.get("reproducao"):
                tests.append(bug["reproducao"])
            if it.get("teste") and it["teste"] not in tests:
                tests.append(it["teste"])
            red = [(x, run_test(tv.root, tv.ctx.cfg, x)["exit_code"]) for x in tests]
            red = [(x, c) for x, c in red if c != 0]
            if red:
                raise Refused(["FIX %s não fecha: o teste do BUG segue vermelho: %s" % (
                    it["id"], ", ".join("%s (exit %s)" % rc for rc in red))])
        if it.get("tipo") == "CHORE":
            r = run_shell(tv.root, it.get("verify_cmd") or "false")
            if r["exit_code"] != 0:
                raise Refused("CHORE %s não fecha: verify-cmd vermelho agora: %s (exit %s)" % (
                    it["id"], it.get("verify_cmd"), r["exit_code"]))
        t = tv.m2(it)
        b = (t.get("gate_report") or {}).get("build") or {}
        met = {"tentativas": t.get("attempts"), "wave": it.get("wave"), "verify_exit": b.get("exit_code"),
               "reviews": len(t.get("reviews") or []), "m2": t["id"], "status_m2": st}
        entregue = list((t.get("submission") or {}).get("files_changed") or [])
        _to_archive(tv, it, _closed(tv, summary, entregue=entregue, metricas=met))
        return [tv.event("close", it["id"], {"kind": "task"})]
    if k == "story":
        pend = [x["id"] for x in _open_tasks_under(tv, it)]
        if pend:
            raise Refused(["story %s tem tasks pendentes:" % it["id"]] + pend,
                          hint="feche cada task (cs-state close <task> --summary ...) antes da story")
        _to_archive(tv, it, _closed(tv, summary, metricas={"tasks": len(tv.same_rest(it, "task"))}))
        return [tv.event("close", it["id"], {"kind": "story"})]
    if k == "feature":
        busy = [x["id"] for x in _open_tasks_under(tv, it) if tv.in_progress(x)]
        pend = [x["id"] for x in _open_tasks_under(tv, it)] + [x["id"] for x in tv.descendants(it)
                                                                 if x["kind"] == "story" and not x.get("closed")]
        if pend and (not devolver or busy):
            raise Refused(["feature %s tem itens abertos:" % it["id"]] + (busy or pend),
                          hint="feche-os ou use --devolver --reason (só para o que não está em andamento)")
        devolvido = []
        if devolver:
            for x in _open_tasks_under(tv, it):
                devolvido.append({"id": x["id"], "novo_id": _to_backlog_task(tv, x, reason), "reason": reason})
            for x in tv.descendants(it):
                if x["kind"] == "story" and not x.get("closed"):
                    x = tv.items[x["id"]]
                    x["closed"] = _closed(tv, "devolvida: " + reason)
                    tv.put(x)
        elif z == "state":
            r = run_shell(tv.root, it.get("aceite") or "false")
            if r["exit_code"] != 0:
                raise Refused("feature %s não fecha: teste de aceite vermelho: %s (exit %s)" % (
                    it["id"], it.get("aceite"), r["exit_code"]))
        n = len(tv.same_rest(it, "task"))
        _to_archive(tv, it, _closed(tv, summary, devolvido=devolvido, metricas={"tasks": n}))
        return [tv.event("close", it["id"], {"kind": "feature", "devolvido": devolvido})]
    if k == "sprint":
        feats = [x for x in tv.descendants(it) if x["kind"] == "feature" and not x.get("closed")]
        bfeats = [x for x in tv.by_kind("feature", "backlog") if x.get("sprint") == it["id"]]
        tasks = [x for x in tv.descendants(it) if x["kind"] == "task" and not x.get("closed")
                 and tv.container_of(x) and tv.container_of(x)["id"] == it["id"]]
        busy = [x["id"] for x in tv.descendants(it) if x["kind"] == "task" and tv.in_progress(x)]
        pend = [x["id"] for x in feats + bfeats + tasks]
        if pend and (not devolver or busy):
            raise Refused(["sprint %s tem itens abertos:" % it["id"]] + (busy or pend),
                          hint="feche-os, ou cs-state close %s --summary ... --devolver --reason ... (devolve ao backlog o "
                               "que não está em andamento)" % it["id"])
        devolvido = []
        for f in feats:
            f = tv.items[f["id"]]
            for x in [y for y in tv.descendants(f) if y["kind"] == "task" and not y.get("closed")]:
                devolvido.append({"id": x["id"], "novo_id": _to_backlog_task(tv, x, reason), "reason": reason})
            f = tv.items[f["id"]]
            tv.move_subtree(f, "backlog/features/" + posixpath.basename(tv.folder(f)))
            f = tv.items[f["id"]]
            f["sprint"] = None
            tv.note(f, "devolvido", reason)
            tv.put(f)
            devolvido.append({"id": f["id"], "reason": reason})
        for f in bfeats:
            f = tv.items[f["id"]]
            f["sprint"] = None
            tv.note(f, "devolvido", reason)
            tv.put(f)
            devolvido.append({"id": f["id"], "reason": reason})
        for x in tasks:
            devolvido.append({"id": x["id"], "novo_id": _to_backlog_task(tv, x, reason), "reason": reason})
        n = len(tv.same_rest(it, "task"))
        _to_archive(tv, it, _closed(tv, summary, devolvido=devolvido, metricas={"tasks": n}))
        return [tv.event("close", it["id"], {"kind": "sprint", "devolvido": devolvido})]
    if k == "epico":
        sps = [x["id"] for x in tv.descendants(it) if x["kind"] == "sprint" and not x.get("closed")]
        sps += [x["id"] for x in tv.by_kind("sprint", "backlog") if x.get("epico") == it["id"]]
        if sps:
            raise Refused(["épico %s tem sprints abertas:" % it["id"]] + sps,
                          hint="feche as sprints (cs-state close SPR-nnn --summary ...) antes do épico")
        _to_archive(tv, it, _closed(tv, summary, metricas={"sprints": len(tv.same_rest(it, "sprint"))}))
        return [tv.event("close", it["id"], {"kind": "epico"})]
    raise Refused("close não se aplica a %s" % k)


def _busy_under(tv, it):
    out = []
    for x in tv.descendants(it):
        if x["kind"] == "task" and tv.in_progress(x):
            st = tv.container_of(x)
            out.append(x["id"] + (" (story %s)" % st["id"] if st and st["kind"] == "story" else ""))
    return out


def park(tv, ident, reason):
    it = tv.need(ident, ("feature",))
    if zone_of(it["path"]) != "state":
        raise Refused("%s não está ativa em state/: nada a estacionar" % it["id"])
    busy = _busy_under(tv, it)
    if busy:
        raise Refused(["feature %s tem tasks em andamento (feche, escale ou drope antes):" % it["id"]] + busy)
    tv.move_subtree(it, "backlog/features/" + posixpath.basename(tv.folder(it)))
    it = tv.items[it["id"]]
    tv.note(it, "park", reason)
    it["park"] = {"at": hcore.now_iso(), "reason": reason}
    tv.put(it)
    return [tv.event("park", it["id"], {"reason": reason})]


def feature_drop(tv, ident, reason):
    """D-0-12: descarta a feature; recusa (cita a task/story) se houver task/story em andamento."""
    it = tv.need(ident, ("feature",))
    if zone_of(it["path"]) == "archive":
        raise Refused("%s já está fechada" % it["id"])
    busy = _busy_under(tv, it)
    if busy:
        raise Refused(["D-0-12: feature %s tem story/task em andamento — não descarta:" % it["id"]] + busy,
                      hint="feche, escale ou drope (cs-state drop) cada task antes de descartar a feature")
    devolvido = [x["id"] for x in _open_tasks_under(tv, it)]
    _to_archive(tv, it, _closed(tv, "descartada: " + reason, devolvido=devolvido, metricas={"descartada": True}))
    it = tv.items[it["id"]]
    it["dropped"] = {"at": hcore.now_iso(), "by": tv.actor, "reason": reason}
    tv.note(it, "drop", reason)
    tv.put(it)
    return [tv.event("drop", it["id"], {"reason": reason})]


def reopen(tv, ident, reason):
    it = tv.need(ident)
    if zone_of(it["path"]) != "archive":
        raise Refused("%s não está fechado (archive/): nada a reabrir" % it["id"])
    origem = (it.get("closed") or {}).get("origem") or "state"
    if it["kind"] == "task" and it.get("parent") == AVULSA:
        dest = "state/tasks/" + posixpath.basename(it["path"])
    else:
        dest = origem + "/" + rest_of(it["path"])
    probe = dict(it, path=dest)
    if it["kind"] != "epico" and it.get("parent") not in (AVULSA, BKL):
        par = tv.container_of(probe)
        if par is None or zone_of(par["path"]) == "archive":
            raise Refused("o pai de %s está fechado: reabra o pai antes" % it["id"])
    it = tv.items[it["id"]]
    it.setdefault("reaberturas", []).append({"at": hcore.now_iso(), "by": tv.actor, "reason": reason,
                                              "closed": it.pop("closed", None)})
    it["reaberta"] = int(it.get("reaberta") or 0) + 1
    it["path"] = dest
    tv.note(it, "reopen", reason)
    tv.put(it)
    return [tv.event("reopen", it["id"], {"reason": reason})]


# ================================================================ move / plan / promote
def _not_started(tv, it):
    if it["kind"] == "task" and tv.m2(it) is not None and tv.in_progress(it):
        raise Refused("%s já iniciada (M2 em andamento): não muda de pai — termine, escale ou drope antes" % it["id"])


def _rehome_task(tv, it, parent_kind, parent_id, acao, reason=None):
    old = it["id"]
    nid, npath, parent = _task_slot(tv, parent_kind, parent_id, it["tipo"], it["title"])
    nx = copy.deepcopy(tv.items[old])
    nx.update({"id": nid, "path": npath, "parent": parent})
    nx["aliases"] = list(nx.get("aliases") or []) + [old]
    for k in ("wave", "started_at", "route", "m2"):
        nx.pop(k, None)
    tv.note(nx, acao, reason, de=old)
    tv.delete(old)
    tv.put(nx)
    return nx


def move(tv, ident, to=None, avulsa=False):
    it = tv.need(ident)
    k = it["kind"]
    if zone_of(it["path"]) == "archive":
        raise Refused("%s está fechado: reabra antes" % it["id"])
    if k == "epico":
        raise Refused("épico é a raiz da árvore: não vai dentro de sprint, feature ou story")
    if avulsa:
        if k != "task":
            raise Refused("--avulsa só vale para task")
        _not_started(tv, it)
        nx = _rehome_task(tv, it, "avulsa", None, "move")
        return [tv.event("move", ident, {"para": nx["id"], "de": it["id"]})]
    if not to:
        raise Refused("informe --to <pai> ou --avulsa")
    tgt = tv.need(to)
    if zone_of(tgt["path"]) == "archive":
        raise Refused("%s está fechado" % tgt["id"])
    if k == "sprint":
        if tgt["kind"] != "epico":
            raise Refused("sprint só vai dentro de épico (não dentro de %s %s)" % (tgt["kind"], tgt["id"]))
        if zone_of(it["path"]) == "state":
            if zone_of(tgt["path"]) != "state":
                raise Refused("épico %s não está em execução: cs-state start %s" % (tgt["id"], tgt["id"]))
            tv.move_subtree(it, "%s/sprints/%s" % (tv.folder(tgt), it["id"]))
        it = tv.items[it["id"]]
        it["epico"] = tgt["id"]
    elif k == "feature":
        if tgt["kind"] != "sprint":
            raise Refused("feature só vai dentro de sprint (não dentro de %s %s)" % (tgt["kind"], tgt["id"]))
        if zone_of(it["path"]) == "state":
            busy = _busy_under(tv, it)
            if busy:
                raise Refused(["feature %s tem tasks em andamento:" % it["id"]] + busy)
            if zone_of(tgt["path"]) != "state":
                raise Refused("sprint %s não está em execução" % tgt["id"])
            tv.move_subtree(it, "%s/features/%s" % (tv.folder(tgt), posixpath.basename(tv.folder(it))))
        it = tv.items[it["id"]]
        it["sprint"] = tgt["id"]
    elif k == "story":
        if tgt["kind"] != "feature":
            raise Refused("story só vai dentro de feature")
        busy = _busy_under(tv, it)
        if busy:
            raise Refused(["story %s tem tasks em andamento:" % it["id"]] + busy)
        tv.move_subtree(it, "%s/stories/%s" % (tv.folder(tgt), posixpath.basename(tv.folder(it))))
        it = tv.items[it["id"]]
    elif k == "task":
        if tgt["kind"] not in ("feature", "sprint", "story"):
            raise Refused("task vai dentro de feature, sprint ou story (não de %s)" % tgt["kind"])
        _not_started(tv, it)
        nx = _rehome_task(tv, it, tgt["kind"], tgt["id"], "move")
        return [tv.event("move", ident, {"para": nx["id"], "de": it["id"]})]
    tv.note(it, "move", para=tgt["id"])
    tv.put(it)
    return [tv.event("move", it["id"], {"para": tgt["id"]})]


def plan(tv, ident, sprint):
    it = tv.need(ident, ("task",))
    _not_started(tv, it)
    sp = _parent_folder(tv, sprint, ("sprint",))
    nx = _rehome_task(tv, it, "sprint", sp["id"], "plan")
    return [tv.event("plan", ident, {"para": nx["id"], "sprint": sp["id"]})]


def promote(tv, ident):
    it = tv.need(ident, ("task",))
    if it.get("tipo") not in STORY_TIPOS:
        raise Refused("promote vale para US|BUG|FIX (CHORE não vira story)")
    _not_started(tv, it)
    if zone_of(it["path"]) == "archive":
        raise Refused("%s está fechada" % it["id"])
    par = tv.container_of(it)
    if par is None or par["kind"] not in ("feature", "sprint"):
        raise Refused("promote exige task dentro de feature ou sprint (avulsa/backlog: cs-state move primeiro)")
    tipo = it["tipo"]
    n = tv.counter("seq." + tipo)
    stid = "%s-%03d" % (tipo, n)
    st = new_item("story", stid, it["title"], "%s/stories/%s-%s/story.json5" % (tv.folder(par), stid, slugify(it["title"])),
                  tv.actor, tipo=tipo, agents=[it.get("agent")], como=it.get("como"), quero=it.get("quero"),
                  para=it.get("para"), criterios=it.get("criterios"), verify_cmd=it.get("verify_cmd"),
                  reproducao=it.get("reproducao"), fixes=it.get("fixes"), teste=it.get("teste"), promovida_de=it["id"])
    tv.note(st, "promote", de=it["id"])
    tv.put(st)
    nx = _rehome_task(tv, it, "story", stid, "promote")
    return [tv.event("promote", ident, {"story": stid, "para": nx["id"], "de": it["id"]})]


# ================================================================ leitura: find, tree, board
def load_view(root):
    need_tree(root)
    board = hcore.load_board(root)
    return T(engine.Ctx(root, board), dry=True)


def status_of(tv, it):
    z = zone_of(it["path"])
    if z == "archive":
        return "fechado" if it["kind"] != "task" else "fechada"
    if z == "backlog":
        return "backlog"
    if it["kind"] != "task":
        return "ativo"
    st, ds = tv.m2_status(it)
    if st is None:
        return "a fazer"
    return "%s/%s" % (st, ds)


def node(tv, it):
    n = {"id": it["id"], "kind": it["kind"], "title": it.get("title"), "path": sd_rel(it["path"]),
         "zona": zone_of(it["path"]), "status": status_of(tv, it)}
    for k in ("tipo", "agent", "wave", "sprint", "epico", "legacy_id"):
        if it.get(k) is not None:
            n[k] = it[k]
    if it.get("aliases"):
        n["aliases"] = it["aliases"]
    return n


def find(tv, text):
    t = (text or "").lower()
    out = []
    for it in sorted(tv.items.values(), key=lambda x: x["path"]):
        keys = [it["id"]] + list(it.get("aliases") or []) + [it.get("legacy_id") or "", it.get("title") or "",
                                                             it.get("m2") or ""]
        if any(t == k.lower() for k in keys if k) or any(t in k.lower() for k in keys if k):
            out.append(it)
    return out


def tree_json(tv):
    zones = {}
    for z in ZONES:
        rows = sorted([it for it in tv.items.values() if zone_of(it["path"]) == z],
                      key=lambda x: (x["path"].count("/"), x["path"]))
        folders, top = {}, []
        for it in rows:
            nd = node(tv, it)
            nd["children"] = []
            d = posixpath.dirname(it["path"])
            par = None
            while d and "/" in d:
                d = posixpath.dirname(d)
                if d in folders:
                    par = folders[d]
                    break
            (par["children"] if par else top).append(nd)
            if it["kind"] in ITEM_FILE:
                folders[tv.folder(it)] = nd
        zones[z] = top
    return {"raiz": hcore.STATE_DIR, "zonas": zones}


def tree_text(tv):
    L = []

    def walk(nodes, depth):
        for nd in nodes:
            L.append("%s%s [%s] %s — %s" % ("  " * depth, nd["id"], nd["status"], nd.get("title") or "", nd["path"]))
            walk(nd["children"], depth + 1)
    tj = tree_json(tv)
    for z in ZONES:
        L.append("%s/" % z)
        if not tj["zonas"][z]:
            L.append("  (vazio)")
        walk(tj["zonas"][z], 1)
    return "\n".join(L)


def front(tv):
    """(sprint, feature) da frente atual: a feature ativa em state/ (ou a sprint ativa)."""
    fs = tv.by_kind("feature", "state")
    if fs:
        f = fs[0]
        return tv.get(f.get("sprint") or "") or tv.container_of(f), f
    sps = tv.by_kind("sprint", "state")
    return (sps[0] if sps else None), None


def board_json(tv):
    sp, f = front(tv)
    act = [node(tv, it) for it in sorted(tv.items.values(), key=lambda x: x["path"]) if zone_of(it["path"]) == "state"]
    bl = [node(tv, it) for it in sorted(tv.items.values(), key=lambda x: x["path"]) if zone_of(it["path"]) == "backlog"]
    cl = sorted([it for it in tv.items.values() if zone_of(it["path"]) == "archive"],
                key=lambda x: (x.get("closed") or {}).get("at") or "", reverse=True)[:20]
    fr = None
    if f or sp:
        fr = {"id": (f or sp)["id"], "cadeia": chain(tv, f or sp)}
    return {"frente": fr, "state": act, "backlog": bl, "fechados": [node(tv, it) for it in cl]}


def chain(tv, it):
    parts = []
    cur = it
    while cur is not None:
        parts.insert(0, cur["id"])
        if cur["kind"] == "feature":
            cur = tv.get(cur.get("sprint") or "") or tv.container_of(cur)
        elif cur["kind"] == "sprint":
            cur = tv.get(cur.get("epico") or "") if cur.get("epico") else None
        else:
            cur = tv.container_of(cur)
    return " › ".join(parts)


def board_text(tv):
    bj = board_json(tv)
    L = []
    if bj["frente"]:
        L.append("frente: %s" % bj["frente"]["cadeia"])
    for key, title in (("state", "em execução (state/)"), ("backlog", "backlog/"), ("fechados", "fechados recentes (archive/)")):
        L.append("%s:" % title)
        rows = bj[key]
        L += ["  %s [%s] %s%s" % (n["id"], n["status"], n.get("title") or "",
                                  (" — %s" % n["agent"]) if n.get("agent") else "") for n in rows] or ["  nenhum"]
    return "\n".join(L)


# ================================================================ validate (árvore × eventos × disco)
def validate(root):
    """Problemas de integridade da árvore (lista vazia = íntegra). O validador do board roda à parte."""
    E = []
    p = hcore.tree_paths(root)
    events, cerr, _ = hcore.read_chain(p["events"])
    if cerr:
        return ["events.jsonl: " + x for x in cerr]
    try:
        board = hcore.load_board(root)
    except StateError as e:
        return [str(e)]
    replay = hcore.new_board()
    import validate as V
    legacy, _ = V.legacy_acks(events)
    for ev in events[1:] if events and events[0].get("type") == "init" else events:
        try:
            hcore.apply_ops(replay, ev.get("ops") or [], check_legal=True, legacy=legacy.get(ev.get("seq")))
        except (StateError, KeyError, ValueError, TypeError, AttributeError) as e:
            return ["replay seq %s (%s): %s" % (ev.get("seq"), ev.get("type"), e)]
    items = replay.get("tree") or {}
    if hcore.canonical(items) != hcore.canonical(board.get("tree") or {}):
        E.append("projeção × events.jsonl divergem na árvore (escrita fora do cs-state)")
    if hcore.canonical(replay.get("tree_meta") or {}) != hcore.canonical(board.get("tree_meta") or {}):
        E.append("projeção × events.jsonl divergem nos contadores da árvore")
    disk = disk_items(root)
    known = {}
    for iid, it in sorted(items.items()):
        known[it["path"]] = iid
        ap = os.path.join(tree_root(root), it["path"])
        if not os.path.isfile(ap):
            E.append("item %s sem arquivo: %s (removido à mão?)" % (iid, sd_rel(it["path"])))
            continue
        try:
            data = hcore.canonical(j5.load(ap))
        except (OSError, ValueError):
            data = None
        if data != hcore.canonical(it):
            E.append("edição à mão em %s (%s): o arquivo difere do que o motor gravou — desfaça e use cs-state" % (
                sd_rel(it["path"]), iid))
        z = zone_of(it["path"])
        if z != "archive" and it.get("closed"):
            E.append("item fechado fora de archive/: %s (%s)" % (iid, sd_rel(it["path"])))
        if z == "archive" and not it.get("closed"):
            E.append("item aberto dentro de archive/: %s (%s)" % (iid, sd_rel(it["path"])))
        if it["kind"] == "feature" and z == "state" and not re.search(r"(^|/)sprints/SPR-\d{3}/features/[^/]+/feature\.json5$",
                                                                      it["path"]):
            E.append("feature %s em state/ fora de uma sprint: %s" % (iid, sd_rel(it["path"])))
    for rp, ap in sorted(disk.items()):
        if rp in known:
            continue
        msg = "arquivo órfão (sem evento na cadeia): %s" % sd_rel(rp)
        try:
            d = j5.load(ap)
        except (OSError, ValueError):
            try:
                with open(ap, encoding="utf-8") as f:
                    d = json.loads(f.read())
            except (OSError, ValueError):
                d = None
        if isinstance(d, dict) and d.get("closed") and zone_of(rp) != "archive":
            msg += " — item fechado dentro de %s/" % zone_of(rp)
        E.append(msg)
    act = [it["id"] for it in items.values() if it["kind"] == "feature" and zone_of(it["path"]) == "state"]
    if len(act) > 1:
        E.append("mais de uma feature ativa em state/: %s" % ", ".join(sorted(act)))
    for leg in ("state/board.json5", "board.json5"):
        if os.path.isfile(os.path.join(tree_root(root), leg)):
            E.append("%s existe no modo árvore (board plano legado): rode cs-state migrate state-tree" % sd_rel(leg))
    return E


# ================================================================ migrate state-tree (board plano → árvore)
def _legacy_paths(root):
    sd = os.path.join(root, hcore.STATE_DIR, "state")
    return {"board": os.path.join(sd, "board.json5"), "events": os.path.join(sd, "events.jsonl"), "dir": sd}


def migrate_plan(root, board, actor):
    """Itens da árvore equivalentes ao board plano (ids novos; legacy_id = id antigo)."""
    items, meta = {}, {}
    now = hcore.now_iso()

    def cnt(key):
        meta[key] = int(meta.get(key) or 0) + 1
        return meta[key]

    def mk(kind, iid, title, path, **kw):
        it = new_item(kind, iid, title, path, actor, **kw)
        it["historico"] = [{"at": now, "acao": "migrado", "by": actor}]
        items[iid] = it
        return it

    def closed(summary, origem="state"):
        return {"at": now, "by": actor, "summary": summary, "entregue": [], "devolvido": [], "metricas": {},
                "origem": origem}

    ep_map = {}
    for e in board.get("epics") or []:
        eid = "EPC-%03d" % cnt("seq.EPC")
        z = {"PROPOSED": "backlog", "ACTIVE": "state"}.get(e.get("state"), "archive")
        it = mk("epico", eid, e.get("title") or e["id"], "%s/epicos/%s-%s/epico.json5" % (z, eid, slugify(e.get("title") or e["id"])),
                objetivo=e.get("objective"), metrica=e.get("metric"), legacy_id=e["id"])
        if z == "archive":
            it["closed"] = closed("migrado em %s" % e.get("state"))
        ep_map[e["id"]] = it
    for s in board.get("sprints") or []:
        sid = "SPR-%03d" % cnt("seq.SPR")
        z = {"PLANNED": "backlog", "ACTIVE": "state", "REVIEW": "state"}.get(s.get("state"), "archive")
        it = mk("sprint", sid, s.get("goal") or s["id"], "%s/sprints/%s/sprint.json5" % (z, sid), meta=s.get("goal") or s["id"],
                legacy_id=s["id"])
        if z == "archive":
            it["closed"] = closed("migrado em %s" % s.get("state"))
    feat_map = {}
    active_done = False
    for f in board.get("features") or []:
        fid = "FEA-%03d" % cnt("seq.FEA")
        title = f.get("title") or f["id"]
        folder = "%s-%s" % (fid, slugify(title))
        acc = " && ".join(f.get("acceptance") or []) or None
        st = f.get("state")
        ep = ep_map.get(f.get("epic"))
        kw = {"aceite": acc, "legacy_id": f["id"]}
        if st == "IN_PROGRESS" and not active_done:
            active_done = True
            sid = "SPR-%03d" % cnt("seq.SPR")
            sbase = "%s/sprints/%s" % (posixpath.dirname(ep["path"]), sid) if ep and zone_of(ep["path"]) == "state" \
                else "state/sprints/%s" % sid
            if ep and zone_of(ep["path"]) == "state":
                kw_s = {"epico": ep["id"]}
            else:
                kw_s = {}
            mk("sprint", sid, "migração: %s" % title, sbase + "/sprint.json5", meta="migração da feature %s (%s)" % (f["id"], title),
               **kw_s)
            it = mk("feature", fid, title, "%s/features/%s/feature.json5" % (sbase, folder), sprint=sid, **kw)
        elif st in ("DONE", "DROPPED"):
            it = mk("feature", fid, title, "archive/features/%s/feature.json5" % folder, **kw)
            it["closed"] = closed("migrado em %s" % st)
        else:
            it = mk("feature", fid, title, "backlog/features/%s/feature.json5" % folder, **kw)
            if st == "IN_PROGRESS":
                it["park"] = {"at": now, "reason": "migração: uma feature ativa por vez"}
        feat_map[f["id"]] = it
    tasks_by_story = {}
    for t in board.get("tasks") or []:
        tasks_by_story.setdefault(t.get("story"), []).append(t["id"])
    for s in board.get("stories") or []:
        f = feat_map.get(s.get("feature"))
        tipo = (s.get("type") or "us").upper()
        if tipo not in STORY_TIPOS:
            tipo = "US"
        title = s.get("title") or s["id"]
        crit = [{"id": c.get("id") or "AC-%d" % (i + 1), "gherkin": c.get("gherkin") or c.get("criterion") or "",
                 "teste": c.get("test")} for i, c in enumerate(s.get("criteria") or []) if isinstance(c, dict)]
        kw = {"tipo": tipo, "agent": None, "como": s.get("as_a"), "quero": s.get("i_want"), "para": s.get("so_that"),
              "criterios": crit, "reproducao": s.get("failing_test"), "fixes": s.get("fixes"), "teste": s.get("proving_test"),
              "legacy_id": s["id"], "legacy_tasks": tasks_by_story.get(s["id"])}
        done = s.get("state") == "DONE"
        if f is not None:
            n = cnt("nn." + f["id"])
            tid = "%s/%02d" % (f["id"], n)
            path = "%s/tasks/%02d-%s-%s.json5" % (posixpath.dirname(f["path"]), n, tipo, slugify(title))
            parent = f["id"]
        else:
            n = cnt("nn." + BKL)
            tid = "%s/%02d" % (BKL, n)
            path = "backlog/tasks/%02d-%s-%s.json5" % (n, tipo, slugify(title))
            parent = BKL
        it = mk("task", tid, title, path, parent=parent, **kw)
        if done or zone_of(path) == "archive":
            it["path"] = "archive/" + rest_of(path)
            it["closed"] = closed("migrado em %s" % s.get("state"), origem=zone_of(path))
    return items, meta


def migrate(root, actor="lead"):
    """board plano legado → árvore. Idempotente; backup do board/events antigos em <STATE_DIR>/backups/."""
    lp = _legacy_paths(root)
    tp = hcore.tree_paths(root)
    has_legacy = os.path.isfile(lp["board"])
    if hcore.tree_mode(root):
        if has_legacy:
            raise StateError("estado incoerente: %s e %s coexistem (migração interrompida?): restaure do backup" % (
                sd_rel("events.jsonl"), sd_rel("state/board.json5")))
        return "nada a migrar: estado já em árvore (idempotente)"
    if not has_legacy:
        raise StateError("sem estado para migrar (%s ausente): rode cs-state init" % sd_rel("state/board.json5"))
    import validate as V
    ok, errs, _ = V.run(root, strict=False)
    if not ok:
        raise Refused(["board legado não valida — conserte antes de migrar:"] + errs[:10])
    board = hcore.load_board(root)
    with open(lp["events"], "rb") as f:
        legacy_bytes = f.read()
    items, meta = migrate_plan(root, board, actor)
    ops = [["tput", iid, None, it] for iid, it in sorted(items.items(), key=lambda kv: kv[1]["path"])]
    ops += [["tmeta", k, None, v] for k, v in sorted(meta.items())]
    stamp = time.strftime("%Y%m%dT%H%M%S")
    bdir = os.path.join(root, hcore.STATE_DIR, "backups", "state-tree-%s" % stamp)
    os.makedirs(tp["state_dir"], exist_ok=True)
    with hcore.file_lock(tp["lock"]):
        os.makedirs(bdir, exist_ok=True)
        shutil.copy2(lp["board"], os.path.join(bdir, "board.json5"))
        shutil.copy2(lp["events"], os.path.join(bdir, "events.jsonl"))
        tmp = tp["events"] + ".tmp"
        with open(tmp, "wb") as f:
            f.write(legacy_bytes)
        rec = {"at": hcore.now_iso(), "actor": actor, "type": "arvore.migrate", "entity": None, "ops": ops,
               "data": {"de": "board plano", "backup": os.path.relpath(bdir, root).replace(os.sep, "/"),
                        "legado": {it["legacy_id"]: iid for iid, it in items.items() if it.get("legacy_id")}}}
        h, seq = hcore.append_chained(tmp, rec)
        nb = copy.deepcopy(board)
        nb.setdefault("tree", {})
        nb.setdefault("tree_meta", {})
        hcore.apply_ops(nb, ops)
        nb["event_count"], nb["last_event_hash"] = seq + 1, h
        hcore.write_json5(tp["board"], nb, "projeção do motor (antigo board) — escrita SÓ por cs-state")
        for z in ZONES:
            os.makedirs(os.path.join(tree_root(root), z), exist_ok=True)
        materialize(root, {}, nb)
        os.replace(tmp, tp["events"])
        os.remove(lp["board"])
        os.remove(lp["events"])
        for name in ("harness-ledger.jsonl", "autonomy.json5", "model-router.jsonl", "selftest.json5", "autonomy-report.json5"):
            src = os.path.join(lp["dir"], name)
            if os.path.isfile(src):
                shutil.move(src, os.path.join(tp["state_dir"], name))
        ev = os.path.join(lp["dir"], "evidence")
        if os.path.isdir(ev):
            shutil.move(ev, tp["evidence"])
    return "migrado: %d item(ns) na árvore (backup em %s)" % (len(items), os.path.relpath(bdir, root))
