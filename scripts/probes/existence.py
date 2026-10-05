"""cs.py probes existence — Existence Ratio (gate G2) de todo path/glob/símbolo/comando citado em team.json5.

Existe = path é arquivo/diretório do repo (linha ≤ nº de linhas quando citada); glob casa ≥1 arquivo;
comando está em operations.json5 como `verified` (ou a regra o marca `unverified: true`); símbolo está
nos símbolos do grafo ou aparece como palavra em algum arquivo de produto.
"""
import os
import re

from team._shared_tmp.cardtext import FILE_NAMES, card_refs, extract_refs
from team._shared_tmp.common import (expand, glob_match, has_glob, norm_cmd, read_json, read_lines, sp_path,
                                     write_json)
from team._shared_tmp.factsio import Facts


READ_ONLY_BINS = frozenset(["grep", "rg", "ag", "ls", "find", "cat", "head", "tail", "wc", "awk", "cut", "sort",
                            "uniq", "stat", "file", "tree", "diff", "jq"])
READ_ONLY_GIT = frozenset(["diff", "log", "show", "grep", "ls-files", "status", "blame", "rev-parse", "shortlog",
                           "ls-tree", "cat-file"])
_WRITE_HINT = re.compile(r"(^|\s)(-i\b|--in-place|-delete\b|-exec\b)|[>|;&]")


def is_read_only(cmd):
    """Comando de inspeção (não muda nada): aceito como check/evidência sem estar em operations.json5."""
    parts = (cmd or "").split()
    if not parts or _WRITE_HINT.search(cmd):
        return False
    if parts[0] == "git":
        sub = [x for x in parts[1:] if not x.startswith("-")]
        return bool(sub) and sub[0] in READ_ONLY_GIT
    if parts[0] == "sed":
        return "-n" in parts
    return parts[0] in READ_ONLY_BINS


class RepoIndex(object):
    def __init__(self, target, facts=None):
        self.target = target
        self.f = facts or Facts(target)
        self.files = list(self.f.all_files())
        self.fileset = set(self.files)
        self.dirs = set()
        for p in self.files:
            parts = p.split("/")
            for i in range(1, len(parts)):
                self.dirs.add("/".join(parts[:i]))
        ops = self.f.operations()
        self.verified = set(norm_cmd(o["command"]) for o in ops if o["status"] == "verified")
        self.declared = set(norm_cmd(o["command"]) for o in ops)
        # contrato do scan: `unavailable` = declarado no repo, toolchain ausente no scan (não é falha do repo)
        self.unavailable = set(norm_cmd(o["command"]) for o in ops if o["status"] == "unavailable")
        self.symbols = set(s["name"] for s in self.f.symbols())
        self._words = None
        self._lines = {}

    def lines(self, rel):
        if rel not in self._lines:
            self._lines[rel] = read_lines(self.target, rel)
        return self._lines[rel]

    def words(self):
        if self._words is None:
            w = set()
            for p in self.f.product_files():
                ls = self.lines(p)
                if ls is None:
                    continue
                for ln in ls:
                    w.update(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", ln))
            self._words = w
        return self._words

    PLACEHOLDER = re.compile(r"(?<![A-Za-z])(?:N{2,}|X{2,}|<[^>/]+>|\{[^}/]+\})(?![a-z])")

    def _on_disk(self, p):
        full = os.path.realpath(os.path.join(self.target, p))
        root = os.path.realpath(self.target)
        if not full.startswith(root + os.sep) or "/.git/" in full + "/":
            return False
        return os.path.exists(full)

    def path_ok(self, p, line=None):
        p = p.strip().rstrip("/") if p not in ("/",) else p
        p = p.rstrip(".,;:!?)") or p
        if p.startswith("./"):
            p = p[2:]
        if self.PLACEHOLDER.search(p):  # padrão explicativo: migrations/NNNN_*.up.sql, src/<modulo>/x.py
            p = self.PLACEHOLDER.sub("*", p)
        if has_glob(p):
            if expand([p], self.files):
                return True, ""
            if any(glob_match(d, p) for d in self.dirs):
                return True, ""
            return False, "glob sem arquivo"
        if p in self.fileset:
            if line is None:
                return True, ""
            ls = self.lines(p)
            return (ls is not None and 1 <= line <= max(len(ls), 1)), "linha fora do arquivo"
        if p in self.dirs:
            return line is None, "linha em diretório"
        if self._on_disk(p):  # fixture/testdata fora do inventário de produto, mas existe no repo
            if line is None:
                return True, ""
            ls = self.lines(p)
            return (ls is not None and 1 <= line <= max(len(ls), 1)), "linha fora do arquivo"
        # path relativo a algum diretório (ex.: nome de arquivo solto): aceita se casa por sufixo único
        if "/" not in p:
            hits = [f for f in self.files if f.rsplit("/", 1)[-1] == p]
            return len(hits) >= 1, "arquivo inexistente"
        # relativo ao território/pacote (orders/rules.ts sob packages/api/src/)
        suf = "/" + p
        if any(f.endswith(suf) for f in self.files) or any(d.endswith(suf) for d in self.dirs):
            return (line is None or any(f.endswith(suf) for f in self.files)), "linha em diretório"
        # alternativas coladas por barra (go.mod/go.sum): todas existem
        segs = p.split("/")
        if len(segs) >= 2 and all("." in x or x in FILE_NAMES for x in segs):
            names = set(f.rsplit("/", 1)[-1] for f in self.files)
            if all(x in names for x in segs):
                return line is None, "linha em lista de arquivos"
        return False, "path inexistente"

    def command_ok(self, c, unverified=False):
        n = norm_cmd(c)
        if n in self.verified:
            return True, ""
        if is_read_only(n):
            return True, "comando de leitura (inspeção)"
        if n in self.unavailable:
            return True, "declarado; toolchain ausente no scan (unavailable)"
        if unverified == "marked":  # `cmd` [unverified] no texto: honesto só se o repo DECLARA o comando
            return (n in self.declared), "comando marcado unverified mas nem declarado em operations.json5"
        if unverified:
            return True, "marcado unverified"
        return False, "comando fora de operations.json5 verified" + (" (só declared; marque `[unverified]`)"
                                                                   if n in self.declared else "")

    def symbol_ok(self, s):
        name = s.rstrip("()").split(".")[-1]
        if name in self.symbols or s.rstrip("()") in self.symbols:
            return True, ""
        return (name in self.words()), "símbolo inexistente"

    def check(self, kind, val, extra=None):
        if kind == "path":
            return self.path_ok(val, extra if isinstance(extra, int) and not isinstance(extra, bool) else None)
        if kind == "command":
            return self.command_ok(val, unverified=(extra if extra in (True, "marked") else False))
        if kind == "symbol":
            return self.symbol_ok(val)
        return True, ""


def agent_refs(agent):
    refs = []
    for g in agent.get("territory") or []:
        refs.append(("territory", "path", g, None))
    for g in agent.get("reads") or []:
        refs.append(("reads", "path", g, None))
    refs += card_refs(agent)
    return refs


def existence_report(target, team=None, idx=None):
    team = team if team is not None else read_json(sp_path(target, "team.json5"), "team.json5")
    idx = idx or RepoIndex(target)
    rep = {"agents": {}, "core": {}}
    tot_c = tot_e = 0

    def run(refs):
        missing = []
        ok = 0
        for where, kind, val, extra in refs:
            good, why = idx.check(kind, val, extra)
            if good:
                ok += 1
            else:
                missing.append({"where": where, "type": kind, "value": val, "why": why})
        return ok, missing

    core_refs = []
    for ln in (team.get("core") or {}).get("lines") or []:
        for kind, val, line in extract_refs(ln.get("text", "") if isinstance(ln, dict) else str(ln)):
            core_refs.append(("core", kind, val, line))
    ok, miss = run(core_refs)
    rep["core"] = {"cited": len(core_refs), "existing": ok, "missing": miss,
                   "ratio": round(ok / float(len(core_refs)), 4) if core_refs else 1.0}
    tot_c += len(core_refs)
    tot_e += ok
    for a in team.get("agents") or []:
        refs = agent_refs(a)
        ok, miss = run(refs)
        tot_c += len(refs)
        tot_e += ok
        rep["agents"][a.get("name")] = {"cited": len(refs), "existing": ok, "missing": miss,
                                        "ratio": round(ok / float(len(refs)), 4) if refs else 1.0}
    rep["cited"] = tot_c
    rep["existing"] = tot_e
    rep["ratio"] = round(tot_e / float(tot_c), 4) if tot_c else 0.0
    rep["gate"] = "G2"
    rep["threshold"] = 1.0
    rep["pass"] = bool(tot_c) and tot_e == tot_c
    if not tot_c:
        rep["why"] = "nada citado: team.json5 vazio não passa (validação exige estado não vazio)"
    return rep


FIX_DIR = ("probes", "existence-fix")
CORE_FIX = "_core"


def author_feedback(target, rep):
    """Resultado devolvido ao AUTOR (iteração 5, --fast): um pacote por cartão com falta de existência em
    `.swarm/probes/existence-fix/<agente>.json5` (+ `_core.json5` para core.lines) — o orquestrador entrega
    o caminho ao subagente autor, que conserta e grava com `team card revise <agente> --file` (aceito sem painel
    consolidado). Pacote de quem não tem mais falta é apagado. → {agente|_core: caminho relativo ao alvo}."""
    d = sp_path(target, *FIX_DIR)
    want = {}
    for name, r in sorted((rep.get("agents") or {}).items()):
        if r.get("missing"):
            want[name] = {"agent": name, "missing": r["missing"],
                          "fix": ("corrija SÓ estas referências no cartão (caminho/símbolo real; comando verified em "
                                  "operations.json5, de leitura, ou marcado `[unverified]` quando o repo o declara; "
                                  "ou tire a referência) e grave com `cs.py team card revise %s --file "
                                  "<cartão corrigido> --note \"conserto de existência\"` — aceito sem painel "
                                  "consolidado; a revisão recusa se ainda faltar algo" % name)}
    if (rep.get("core") or {}).get("missing"):
        want[CORE_FIX] = {"agent": None, "missing": rep["core"]["missing"],
                          "fix": "corrija as linhas do core e grave com `cs.py team core set --file <core>`"}
    if os.path.isdir(d):
        for fn in os.listdir(d):
            if fn.endswith(".json5") and fn[:-len(".json5")] not in want:
                os.remove(os.path.join(d, fn))
    out = {}
    for name, doc in sorted(want.items()):
        p = os.path.join(d, "%s.json5" % name)
        write_json(target, p, dict(doc, schema_version=1),
                   "faltas de existência de %s — devolvidas ao autor; gerado por cs.py probes existence" % name)
        out[name] = os.path.relpath(p, target)
    return out


def run_existence(target):
    rep = existence_report(target)
    rep["feedback"] = author_feedback(target, rep)
    write_json(target, sp_path(target, "probes", "existence.json5"), rep)
    return rep


def feed_problems(target, rep):
    """`probes existence --feed` (check de rt.2). Falta de existência é esperada ANTES da revisão do autor
    (rt.4) — o efeito de rt.2 é medi-la e ela CHEGAR ao autor: o `panel consolidate` a inclui como objeção
    confirmada. Depois que todos os cartões foram revisados, vale o G2 (ratio 1,0). → faltas[]."""
    import os
    from team._shared_tmp.common import find_doc, read_json, sp_path
    probs = []
    if (rep.get("core") or {}).get("missing"):
        m = rep["core"]["missing"][0]
        probs.append("core.lines cita %s `%s` inexistente (%s)" % (m["type"], m["value"], m["why"]))
    st_p = sp_path(target, "cards", "status.json5")
    status = read_json(st_p, "cards/status.json5") if os.path.isfile(find_doc(st_p)) else {}
    for name, r in sorted((rep.get("agents") or {}).items()):
        if not r.get("missing"):
            continue
        if (status.get(name) or {}).get("revised"):
            probs.append("%s já revisou (rt.4) e ainda cita %d coisa(s) inexistente(s) (ex.: %s `%s`)" % (
                name, len(r["missing"]), r["missing"][0]["type"], r["missing"][0]["value"]))
            continue
        cp = sp_path(target, "panel", "%s.json5" % name)
        if not os.path.isfile(find_doc(cp)):
            continue  # ainda não consolidado: `panel consolidate` (rt.3) inclui a falta como objeção
        doc = read_json(cp, "panel/%s.json5" % name)
        refs = set(str(it.get("ref") or "").strip("`") for it in
                   (doc.get("confirmed") or {}).get("afirmacoes_sem_evidencia") or [])
        lost = [m for m in r["missing"] if str(m["value"]).strip("`") not in refs]
        if lost:
            probs.append("%s: %d falta(s) de existência fora do consolidado (ex.: %s `%s`) — re-consolide "
                         "(`cs.py panel consolidate`)" % (name, len(lost), lost[0]["type"], lost[0]["value"]))
    return probs
