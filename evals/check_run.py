#!/usr/bin/env python3
"""check_run.py — grading MECÂNICO de uma execução da skill codebase-specialists.

Uso:
  python3 evals/check_run.py <alvo> <GROUND_TRUTH.json> [--mode setup|autonomous|escalation|bugfix]
        [--feature <id>] [--platforms claude-code,cursor,copilot,codex] [--skill <dir>]
        [--only G1,G3,...] [--no-scenarios] [--out grading.json]
  python3 evals/check_run.py --verify-ground-truth <py-billing|ts-shop|go-polyglot|all>

Saída: grading.json no formato do skill-creator ({expectations:[{text,passed,evidence}], summary}).
Exit 0 se tudo passou, 1 se alguma asserção falhou, 2 em erro de uso.

Duas famílias de asserção (prefixo no `text`; contagem em summary.quality / summary.structure):
  [Q] QUALIDADE, neutra de formato — lida dos artefatos emitidos por QUALQUER plataforma (.claude/agents,
      .cursor/agents|rules, .github/agents|instructions|prompts|copilot-instructions.md, AGENTS.md/CLAUDE.md da raiz
      e aninhados) e, se existir, de .swarm/ (cartões/core do team.json5, fatos de histórico e stack). Em
      arquivo que já existia na fixture conta só o texto ADICIONADO. É o que se compara com a baseline: TERR, BC,
      INV, TERM, RULE, STACK, FIX, NEG, HIST, HUMAN, TESTCMD, STALE.
  [S] ESTRUTURA da skill — G1–G16, FMT e os artefatos próprios (.swarm/*, harness, sondas). Reportada à
      parte; uma baseline sem a skill não tem esses artefatos e não deve ser comparada por eles.
  Modos 4–6 (C-2, campanha-iter11): [Q] = RESULTADO recalculado no alvo, sem depender do formato da skill —
      autônomo: aceite verde, aceite sem alterar o teste aprovado, regressão verde, protegidos intactos;
      escalada: invariante intocado, aceite vermelho e inalterado, regressão verde; bugfix: teste do bug falha
      antes/passa depois, oráculo oculto, código corrigido + regressão. Board, eventos, tiers, sessão e
      relatório são [S]. Calibração (C-1): saída VAZIA (build.sh + install_feature.sh) ⇒ 0 asserções em todos
      os modos; saída boa de referência (`evals/reference/good/<feature>/apply.sh`) ⇒ pass_rate ≥ 0,9.

Princípios: o grader usa o código da SKILL (json5io, CLI), nunca scripts do alvo para decidir; tudo
que pode ser recalculado (testes, hashes, git diff) é recalculado aqui; cenários que escrevem estado
rodam numa CÓPIA do alvo. Python 3.9+ stdlib.
"""
import argparse
import glob as globmod
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata

EVALS = os.path.dirname(os.path.abspath(__file__))
SKILL_DEFAULT = os.path.dirname(EVALS)
FIXTURES = os.path.join(EVALS, "fixtures")
GENERIC_CARDS = os.path.join(EVALS, "reference", "generic-cards")
SCENARIOS = os.path.join(EVALS, "harness_scenarios.json")

RESERVED_PREFIXES = (".swarm/", ".claude/", ".git/", ".cursor/", ".codex/", ".github/agents/",
                     ".github/instructions/", ".github/copilot-instructions.md", "scripts/harness/")
PLATFORM_FILES = ("CLAUDE.md", "AGENTS.md")
TIERS_DEFAULT = ["haiku", "sonnet", "opus"]
COST_DEFAULT = {"haiku": 0.04, "sonnet": 0.2, "opus": 1.0}
G3_THRESHOLD = 0.35
NEG_RE = re.compile(r"(?i)\b(n[aã]o|nunca|never|not|no|sem|avoid|evit|proib|forbid|don't|do not|ignor|fixture|"
                    r"desatualiz|stale|outdated|legacy|legad|deprecat|em vez de|instead of|jamais|❌|✗)")
PATH_EXT = ("py", "ts", "tsx", "js", "mjs", "go", "sql", "sh", "md", "json", "json5", "toml", "lock", "yml",
            "yaml", "txt", "csv", "mod", "sum", "cfg", "ini", "html")


# ================================================================ util
def sh(cmd, cwd=None, env=None, timeout=300, stdin=None, shell=False):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, input=stdin, capture_output=True, text=True,
                           timeout=timeout, shell=shell)
        return {"exit": p.returncode, "out": p.stdout, "err": p.stderr, "ms": (time.time() - t0) * 1000}
    except FileNotFoundError as exc:
        return {"exit": 127, "out": "", "err": str(exc), "ms": 0}
    except subprocess.TimeoutExpired:
        return {"exit": 124, "out": "", "err": "timeout %ss" % timeout, "ms": timeout * 1000}


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def approx_tokens(text):
    return int(math.ceil(len(text) / 4.0))


def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            for x in walk(v):
                yield x
    elif isinstance(obj, list):
        for v in obj:
            for x in walk(v):
                yield x


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            for s in strings(v):
                yield s
    elif isinstance(obj, list):
        for v in obj:
            for s in strings(v):
                yield s


def get_path(obj, dotted):
    if dotted in ("", None):
        return obj
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
    return cur


def first_key(d, names, default=None):
    for n in names:
        if isinstance(d, dict) and n in d and d[n] is not None:
            return d[n]
    return default


def glob_to_re(pattern):
    p = pattern.strip()
    if p.startswith("./"):
        p = p[2:]
    if p.endswith("/"):
        p += "**"
    out, i = "", 0
    while i < len(p):
        c = p[i]
        if p.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif p.startswith("**", i):
            out += ".*"
            i += 2
        elif c == "*":
            out += "[^/]*"
            i += 1
        elif c == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(c)
            i += 1
    return re.compile("^" + out + "$")


def matches_any(path, patterns):
    for g in patterns or []:
        if not isinstance(g, str):
            continue
        if g.rstrip("/") == path or glob_to_re(g).match(path):
            return True
        if not any(ch in g for ch in "*?") and path.startswith(g.rstrip("/") + "/"):
            return True
    return False


def under(path, prefixes):
    return any(path == p.rstrip("/") or path.startswith(p if p.endswith("/") else p + "/") or path == p
               for p in prefixes)


def neg_filtered(text):
    """Linhas do texto SEM negação/ressalva (para sondas negativas e afirmações velhas)."""
    return "\n".join(l for l in text.splitlines() if not NEG_RE.search(l))


# referência a NOME (id de fato `gap.python-client-owner`, slug `driver-id-compat`, caminho `a/b`) não é uso do
# termo nem afirmação de stack: some antes de procurar a palavra
FACT_ID_RE = re.compile(r"(?<![\w.])(?:gap|docs|rules|brule|hist|ops|gloss|term|rat|stack|conv|arch|inv|graph|"
                        r"cfg|lib|runtime)\.[\w.-]+")
SLUG_RE = re.compile(r"(?<![\w/.-])[\w.]+(?:-[\w.]+)+(?![\w/-])")
CODE_PATH_RE = re.compile(r"`[^`\s]*/[^`\s]*`")
# variante citada como legado/compatibilidade/alias ("pings antigos ainda mandam driver_id") não é USO do termo
TERM_LEGACY_RE = re.compile(r"(?i)(antig|velh|\bold\b|legac|legad|compat|alias|variante|variant|sin[oô]nim|"
                            r"synonym|ainda (mand|envi|cheg|us)|still (send|use)|renomead|renamed|"
                            r"n[aã]o se usa|n[aã]o use|não usar)")


def strip_name_refs(line):
    return SLUG_RE.sub(" ", FACT_ID_RE.sub(" ", CODE_PATH_RE.sub(" ", line)))


def term_misuse_lines(variant, canonical, text):
    """Linhas que USAM a variante proibida como termo: sem negação/ressalva, sem marcador de legado/alias,
    sem o canônico ao lado (linha que mapeia variante→canônico explica, não usa) e fora de id/slug/caminho."""
    out = []
    canon_rx = re.compile(r"(?i)(?<![A-Za-z0-9])%s" % re.escape(canonical))
    for l in neg_filtered(text).splitlines():
        if TERM_LEGACY_RE.search(l) or canon_rx.search(l):
            continue
        if word_in(variant, strip_name_refs(l), case=True):
            out.append(l)
    return out


def fixture_claim_corpus(text, fixture_paths):
    """Linhas que podem AFIRMAR stack da fixture: sem negação, sem contexto de fixture/recusa, sem o caminho
    da fixture e sem referências a nome (id de fato, slug, caminho entre crases)."""
    out = []
    for l in neg_filtered(text).splitlines():
        if FIXTURE_CTX_RE.search(l) or FIXTURE_REFUSAL_RE.search(l) or any(f.rstrip("/") in l for f in fixture_paths):
            continue
        out.append(strip_name_refs(re.sub(r"\bpython3?\s+\S+\.py\b", " ", l)))
    return "\n".join(out)


def word_in(word, text, case=False):
    flags = 0 if case else re.I
    return re.search(r"(?<![A-Za-z0-9_])" + re.escape(word) + r"(?![A-Za-z0-9_])", text, flags) is not None


# ================================================================ contexto
class Ctx(object):
    def __init__(self, target, gt, skill, mode, feature, platforms, only, run_scenarios):
        self.target = os.path.realpath(target)
        self.gt = gt
        self.fixture = gt.get("fixture")
        self.skill = os.path.realpath(skill)
        self.mode = mode
        self.feature = feature
        self.platforms = platforms
        self.only = only
        self.run_scenarios = run_scenarios
        self.results = []
        self.j5 = None
        self.j5_err = None
        self._cache = {}
        try:
            sys.path.insert(0, os.path.join(self.skill, "scripts"))
            from cslib import json5io  # noqa
            self.j5 = json5io
        except Exception as exc:  # noqa
            self.j5_err = ("json5io da skill ausente/ilegível em %s/scripts/cslib/json5io.py (%s) — "
                           "artefatos .json5 não podem ser lidos" % (self.skill, exc))
            sys.stderr.write("check_run: ERRO: %s\n" % self.j5_err)

    def want(self, gate):
        return not self.only or gate in self.only

    def add(self, gate, text, passed, evidence, kind="S"):
        """kind: "Q" = qualidade neutra de formato (comparável com baseline); "S" = estrutura da skill (G1–G16,
        artefatos próprios; reportada à parte, não comparada com baseline)."""
        if not self.want(gate):
            return
        if not text.startswith("[" + gate + "]"):
            text = "[%s] %s" % (gate, text)
        text = "[%s]%s" % (kind, text)
        self.results.append({"text": text, "passed": bool(passed), "evidence": str(evidence)[:1500], "kind": kind})

    def p(self, rel):
        return os.path.join(self.target, rel)

    def state_rel(self, key, name=None):
        """Caminho de estado do harness RELATIVO ao alvo, resolvido pelo próprio motor (hcore.state_paths) —
        cobre o modo árvore (.swarm/events.jsonl + .swarm/.engine/) e o plano (.swarm/state/, execuções antigas).
        name: arquivo dentro do diretório da chave (ex.: state_rel("state_dir", "model-router.jsonl"))."""
        if "state_paths" not in self._cache:
            sp = None
            try:
                eng = os.path.join(self.skill, "scripts", "harness", "engine")
                if eng not in sys.path:
                    sys.path.insert(0, eng)
                import hcore  # noqa
                sp = hcore.state_paths(self.target)
            except Exception as exc:  # noqa — sem o motor da skill: espelha a regra de layout do hcore
                sys.stderr.write("check_run: aviso: hcore indisponível (%s); layout pela regra local\n" % exc)
                tree = os.path.isfile(self.p(os.path.join(".swarm", "events.jsonl")))
                sd = self.p(os.path.join(".swarm", ".engine" if tree else "state"))
                sp = {"state_dir": sd, "board": os.path.join(sd, "projection.json5" if tree else "board.json5"),
                      "events": self.p(os.path.join(".swarm", "events.jsonl")) if tree else os.path.join(sd, "events.jsonl"),
                      "ledger": os.path.join(sd, "harness-ledger.jsonl"),
                      "autonomy": os.path.join(sd, "autonomy.json5"),
                      "session_dir": self.p(os.path.join(".swarm", "session"))}
            self._cache["state_paths"] = sp
        a = self._cache["state_paths"][key]
        if name:
            a = os.path.join(a, name)
        return os.path.relpath(a, self.target)

    def state_art(self, key):
        """load_art de um artefato de estado .json5 (board, autonomy) no layout real do alvo."""
        rel = self.state_rel(key)
        return self.load_art(rel[:-len(".json5")] if rel.endswith(".json5") else rel)

    # ------------------------------------------------ leitura de artefatos
    def load_art(self, rel_noext):
        """Lê <rel>.json5 (json5io da skill) ou, se ausente, <rel>.json. Devolve (data, path, erro)."""
        key = "art:" + rel_noext
        if key in self._cache:
            return self._cache[key]
        res = (None, None, "ausente: %s.json5" % rel_noext)
        p5, pj = self.p(rel_noext + ".json5"), self.p(rel_noext + ".json")
        if os.path.isfile(p5):
            if self.j5 is None:
                res = (None, p5, self.j5_err)
            else:
                try:
                    res = (self.j5.load(p5), p5, None)
                except Exception as exc:  # noqa
                    res = (None, p5, "JSON5 inválido: %s" % exc)
        elif os.path.isfile(pj):
            try:
                res = (json.load(open(pj, encoding="utf-8")), pj, None)
            except ValueError as exc:
                res = (None, pj, "JSON inválido: %s" % exc)
        self._cache[key] = res
        return res

    def load_jsonl(self, rel):
        out = []
        p = self.p(rel)
        if not os.path.isfile(p):
            return out
        for line in open(p, encoding="utf-8", errors="replace"):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
        return out

    # ------------------------------------------------ team / cartões
    def team(self):
        return self.load_art(".swarm/team")

    def agents(self):
        data, _, _ = self.team()
        if not isinstance(data, dict):
            return []
        return [a for a in data.get("agents") or [] if isinstance(a, dict) and a.get("name")]

    def is_gate(self, a):
        return a.get("kind") == "gate"

    def is_writer(self, a):
        if self.is_gate(a):
            return False
        tools = a.get("tools")
        if isinstance(tools, list) and tools:
            return any(t in tools for t in ("Edit", "Write", "MultiEdit"))
        return bool(a.get("territory"))

    def card_text(self, a):
        key = "card:" + a["name"]
        if key in self._cache:
            return self._cache[key]
        parts = []
        p = self.p(".claude/agents/%s.md" % a["name"])
        if os.path.isfile(p):
            parts.append(open(p, encoding="utf-8", errors="replace").read())
        parts.extend(strings(a.get("card") or {}))
        txt = "\n".join(parts)
        self._cache[key] = txt
        return txt

    def all_team_text(self):
        data, _, _ = self.team()
        parts = list(strings(data or {}))
        for a in self.agents():
            parts.append(self.card_text(a))
        return "\n".join(parts)

    # ------------------------------------------------ arquivos
    def fixture_files(self):
        """Arquivos de produto conhecidos = arquivos do repo/ da fixture que ainda existem no alvo."""
        if "ff" in self._cache:
            return self._cache["ff"]
        base = os.path.join(FIXTURES, self.fixture or "", "repo")
        out = []
        if os.path.isdir(base):
            for root, dirs, files in os.walk(base):
                dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
                for f in files:
                    rel = os.path.relpath(os.path.join(root, f), base).replace(os.sep, "/")
                    out.append(rel)
        else:
            r = sh(["git", "ls-files"], cwd=self.target)
            out = [l for l in r["out"].splitlines() if l]
        self._cache["ff"] = sorted(out)
        return self._cache["ff"]

    def product_files(self):
        fx = self.gt.get("fixture_paths") or []
        return [f for f in self.fixture_files()
                if not under(f, fx) and not f.startswith(RESERVED_PREFIXES) and f not in PLATFORM_FILES
                and os.path.exists(self.p(f))]

    def owners_of(self, path):
        return [a["name"] for a in self.agents() if self.is_writer(a) and matches_any(path, a.get("territory"))]

    def owners_of_prefixes(self, prefixes):
        names = set()
        for f in self.product_files():
            if under(f, prefixes):
                names.update(self.owners_of(f))
        return sorted(names)

    def gates(self):
        return [a for a in self.agents() if self.is_gate(a)]

    def agent(self, name):
        for a in self.agents():
            if a["name"] == name:
                return a
        return None


# ================================================================ G1 cobertura
def check_g1(ctx):
    agents = ctx.agents()
    if not agents:
        data, path, err = ctx.team()
        ctx.add("G1", "todo arquivo de produto tem exatamente 1 dono de escrita (territórios disjuntos, 100% cobertura)",
                False, "team.json5 sem agentes (%s)" % (err or path))
        return
    files = ctx.product_files()
    unowned, overlap = [], []
    for f in files:
        o = ctx.owners_of(f)
        if not o:
            unowned.append(f)
        elif len(o) > 1:
            overlap.append("%s -> %s" % (f, ",".join(o)))
    ctx.add("G1", "todo arquivo de produto tem exatamente 1 dono de escrita (territórios disjuntos, 100% cobertura)",
            not unowned and not overlap and files,
            "%d arquivos de produto; sem dono: %d %s; sobreposição: %d %s" % (
                len(files), len(unowned), unowned[:8], len(overlap), overlap[:5]))
    fx = ctx.gt.get("fixture_paths") or []
    bad = []
    for a in agents:
        terr = a.get("territory") or []
        fx_files = [f for f in ctx.fixture_files() if under(f, fx)]
        prod_hits = [f for f in files if matches_any(f, terr)]
        fx_hits = [f for f in fx_files if matches_any(f, terr)]
        if fx_hits and not prod_hits:
            bad.append(a["name"])
    ctx.add("G1", "nenhum agente existe só para fixture (fixture não vira território de produto)", not bad,
            "agentes cujo território só casa fixture: %s" % bad if bad else "ok (%d agentes)" % len(agents))


# ================================================================ G2 existência
TOKEN_RE = re.compile(r"`([^`\n]{2,200})`|(?<![\w/.-])((?:\.{0,2}/)?[\w.@-]+(?:/[\w.*@-]+)+/?|[\w.-]+\.(?:%s))(?![\w])"
                      % "|".join(PATH_EXT))


def path_candidates(text, top_entries):
    out = set()
    for m in TOKEN_RE.finditer(text):
        tok = (m.group(1) or m.group(2) or "").strip()
        for t in tok.split():
            t = t.strip("'\"(),;[]{}<>").rstrip(".:")
            t = re.sub(r":\d+(-\d+)?$", "", t)
            t = re.sub(r"::.*$", "", t)
            if not t or "://" in t or t.startswith(("-", "$", "@", "#")) or "=" in t:
                continue
            if not re.search(r"[A-Za-z]", t):
                continue
            first = t.lstrip("./").split("/")[0]
            ext_ok = re.search(r"\.(%s)$" % "|".join(PATH_EXT), t) is not None
            if "/" in t and first in top_entries:
                out.add(t.lstrip("./") if not t.startswith("../") else t)
            elif ext_ok and "/" not in t and first in top_entries:
                out.add(t)
            elif ext_ok and "/" in t and first in top_entries:
                out.add(t)
    return out


def exists_in(target, cand):
    if any(ch in cand for ch in "*?"):
        rx = glob_to_re(cand)
        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
            for f in files + dirs:
                rel = os.path.relpath(os.path.join(root, f), target).replace(os.sep, "/")
                if rx.match(rel):
                    return True
        return False
    return os.path.exists(os.path.join(target, cand.rstrip("/")))


def ops_commands(ctx):
    data, _, _ = ctx.load_art(".swarm/facts/operations")
    out = []
    for d in walk(data or {}):
        cmd = first_key(d, ["cmd", "command"])
        st = first_key(d, ["status", "state"])
        if isinstance(cmd, str):
            out.append((" ".join(cmd.split()), str(st or "").lower(), d))
    return out


def check_g2(ctx):
    agents = ctx.agents()
    data, path, err = ctx.team()
    if data is None:
        ctx.add("G2", "Existence Ratio = 1,0 em team.json5 e nos cartões emitidos", False, err)
        return
    top = set(os.listdir(ctx.target))
    texts = {"team": "\n".join(strings(data))}
    for a in agents:
        p = ctx.p(".claude/agents/%s.md" % a["name"])
        if os.path.isfile(p):
            texts["card:" + a["name"]] = open(p, encoding="utf-8", errors="replace").read()
    checked, missing = 0, []
    for src, t in texts.items():
        for c in sorted(path_candidates(t, top)):
            checked += 1
            if not exists_in(ctx.target, c):
                missing.append("%s: %s" % (src, c))
    ratio = 1.0 if checked == 0 else (checked - len(missing)) / float(checked)
    ctx.add("G2", "Existence Ratio = 1,0 em team.json5 e nos cartões emitidos (>=5 caminhos citados)",
            checked >= 5 and not missing,
            "ratio %.3f (%d caminhos checados); inexistentes: %s" % (ratio, checked, missing[:10]))
    ops = ops_commands(ctx)
    bad, n = [], 0
    for a in agents:
        card = a.get("card") or {}
        cmds = []
        if isinstance(card.get("done_when"), str):
            cmds.append((card["done_when"], {}))
        for r in card.get("rules") or []:
            if isinstance(r, dict) and r.get("check"):
                cmds.append((r["check"], r))
        for c, r in cmds:
            n += 1
            cn = " ".join(str(c).split())
            hit = [o for o in ops if o[0] and (o[0] in cn or cn in o[0])]
            if r.get("unverified") or "unverified" in cn.lower():
                continue
            if not hit or not any(h[1] in ("verified", "declared") for h in hit):
                bad.append("%s: %s" % (a["name"], cn[:80]))
    ctx.add("G2", "todo comando em check/done_when está em operations.json5 (verified/declared) ou marcado unverified",
            n > 0 and not bad, "%d comandos; fora de operations: %s" % (n, bad[:6]))


# ================================================================ G3 anti-template
STOP = set(strip_accents("""a an and are as at be by for from has have in is it of on or that the this to was were will with
you your use when what which who should must can not no all any each into only own same so than too very just
o os as um uma de do da dos das e em no na nos nas por para com que se ao aos sem sob ou mas como mais
ser sua seu suas seus ele ela isso este esta esse essa ja nao sim quando onde qual quais todo toda todos
name description tools read write edit bash grep glob""").split())


def bag(text):
    toks = [t for t in re.findall(r"[a-z][a-z0-9_]{2,}", strip_accents(text.lower())) if t not in STOP]
    c = {}
    for t in toks:
        c[t] = c.get(t, 0) + 1
    for a, b in zip(toks, toks[1:]):
        k = a + " " + b
        c[k] = c.get(k, 0) + 1
    return c


def cosine(a, b):
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def generic_bags():
    out = {}
    for p in sorted(globmod.glob(os.path.join(GENERIC_CARDS, "*.md"))):
        out[os.path.basename(p)] = bag(open(p, encoding="utf-8").read())
    return out


def check_g3(ctx):
    agents = ctx.agents()
    gb = generic_bags()
    if not agents or not gb:
        ctx.add("G3", "anti-template: similaridade de cada cartão com cartões genéricos <= %.2f" % G3_THRESHOLD, False,
                "sem agentes" if not agents else "sem cartões de referência em %s" % GENERIC_CARDS)
        return
    worst, details = 0.0, []
    for a in agents:
        b = bag(ctx.card_text(a))
        name, s = max(((n, cosine(b, g)) for n, g in gb.items()), key=lambda x: x[1])
        worst = max(worst, s)
        details.append("%s~%s=%.2f" % (a["name"], name, s))
    ctx.add("G3", "anti-template: similaridade de cada cartão com cartões genéricos <= %.2f" % G3_THRESHOLD,
            worst <= G3_THRESHOLD, "pior %.3f; %s" % (worst, "; ".join(details)))
    over = []
    for a in agents:
        p = ctx.p(".claude/agents/%s.md" % a["name"])
        if os.path.isfile(p):
            n = cost_lines(p)
            if n > 80:
                over.append("%s=%d>80" % (a["name"], n))
    data, _, _ = ctx.team()
    core = ((data or {}).get("core") or {}).get("lines") or []
    if len(core) > 40:
        over.append("core=%d>40" % len(core))
    for p in globmod.glob(ctx.p(".claude/rules/*.md")):
        n = cost_lines(p)
        if n > 60:
            over.append("%s=%d>60" % (os.path.basename(p), n))
    ctx.add("G3", "orçamento por camada: S0 core <=40 linhas, S1 cartão <=80, S2 rule por caminho <=60",
            agents and not over, "excedentes: %s" % over if over else "ok")


# ================================================================ G4 sonda
def num(d, names):
    v = first_key(d, names)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def check_g4(ctx):
    rep, path, err = ctx.load_art(".swarm/probes/report")
    if rep is None:
        ctx.add("G4", "sonda: território >=0,85, cross >=0,70, 0 alucinação em negativa, delta>0 sobre baseline (todos os agentes)",
                False, err)
        return
    names = {a["name"] for a in ctx.agents()}
    rows = {}
    for d in walk(rep):
        n = first_key(d, ["agent", "name"])
        if isinstance(n, str) and n in names and num(d, ["territory", "territory_score", "score_territory", "own"]) is not None:
            rows[n] = d
    if isinstance(rep, dict) and isinstance(rep.get("agents"), dict):
        for n, d in rep["agents"].items():
            if n in names and isinstance(d, dict):
                rows[n] = d
    fails = []
    for n in sorted(names):
        d = rows.get(n)
        if d is None:
            fails.append("%s: sem placar" % n)
            continue
        t = num(d, ["territory", "territory_score", "score_territory", "own"])
        c = num(d, ["cross", "cross_territory", "cross_score", "score_cross"])
        h = num(d, ["negative_hallucinations", "hallucinations", "neg_hallucinations", "hallucination"])
        dl = num(d, ["delta", "baseline_delta", "delta_vs_baseline"])
        if t is None or t < 0.85 or c is None or c < 0.70 or h is None or h > 0 or dl is None or dl <= 0:
            fails.append("%s: t=%s c=%s h=%s d=%s" % (n, t, c, h, dl))
    ctx.add("G4", "sonda: território >=0,85, cross >=0,70, 0 alucinação em negativa, delta>0 sobre baseline (todos os agentes)",
            names and not fails, "falhas: %s" % fails[:8] if fails else "ok (%d agentes) em %s" % (len(names), path))
    bank, bpath, berr = ctx.load_art(".swarm/probes/bank")
    leaks = []
    if bank is not None:
        cards = "\n".join(ctx.card_text(a) for a in ctx.agents())
        for d in walk(bank):
            ans = first_key(d, ["answer", "canonical_answer", "gold"])
            if isinstance(ans, str) and len(ans) >= 24 and ans in cards:
                leaks.append(ans[:60])
    ctx.add("G4", "anti-cola: nenhuma resposta canônica do banco de sondas aparece nos cartões",
            bank is not None and not leaks, berr if bank is None else ("vazamentos: %s" % leaks[:3] if leaks else "ok"))


# ================================================================ G5 operação
def tool_available(ctx, t):
    if "/" in t:
        return os.path.exists(ctx.p(t))
    return shutil.which(t) is not None


def check_g5(ctx):
    ops = ops_commands(ctx)
    cmds = ctx.gt.get("commands") or {}
    if not ops:
        data, path, err = ctx.load_art(".swarm/facts/operations")
        ctx.add("G5", "comando de teste real presente em operations.json5 e marcado verified/declared corretamente", False,
                err or "operations.json5 sem comandos")
        return
    for key, spec in sorted(cmds.items()):
        variants = [spec["cmd"]] + list(spec.get("equivalents") or [])
        hits = [o for o in ops if any(v in o[0] or o[0] in v for v in variants if o[0])]
        tools_ok = all(tool_available(ctx, t) for t in spec.get("requires_tools") or [])
        exp = spec.get("expected")
        if exp == "verified" or (exp == "verified_if_tools" and tools_ok):
            want = "verified"
        elif exp == "never_verified":
            want = "not_verified"
        else:
            want = "declared"
        if not hits:
            ok, ev = False, "comando %s ausente em operations (variantes %s)" % (key, variants[:3])
        else:
            sts = sorted(set(h[1] for h in hits))
            if want == "verified":
                ok = "verified" in sts
            elif want == "not_verified":
                ok = "verified" not in sts
            else:
                ok = "verified" not in sts and any(s in ("declared", "unverified", "failed") for s in sts)
            ev = "esperado %s (ferramentas %s: %s); encontrado %s em %s" % (
                want, spec.get("requires_tools"), "ok" if tools_ok else "AUSENTES", sts, [h[0] for h in hits][:3])
            if ok and want == "verified" and key == "test":
                r = sh(hits[0][0], cwd=ctx.target, shell=True, timeout=600)
                ok = r["exit"] == 0
                ev += "; reexecutado pelo grader: exit %s" % r["exit"]
        ctx.add("G5", "operação '%s' (%s) presente e status correto (verified só se executou com exit 0; declared se ferramenta ausente)"
                % (key, spec["cmd"]), ok, ev)


# ================================================================ G6 harness
def load_scenarios():
    return json.load(open(SCENARIOS, encoding="utf-8"))


def resolve_tool(ctx, name, target):
    sc = load_scenarios()
    env_override = os.environ.get("CS_%s_CMD" % name.upper())
    if env_override:
        return [x.replace("{T}", target).replace("{SKILL}", ctx.skill) for x in env_override.split()]
    tried = []
    for cand in sc["tools"].get(name, []):
        c = [x.replace("{T}", target).replace("{SKILL}", ctx.skill) for x in cand]
        exe = c[1] if c[0] == "python3" else c[0]
        tried.append(exe)
        if not os.path.exists(exe):
            continue
        if exe.endswith("cs.py") and "--target" in c and len(c) > c.index("--target") + 2:
            sub = c[c.index("--target") + 2]
            h = sh(["python3", exe, "--help"], timeout=60)
            if not re.search(r"\b%s\b" % re.escape(sub), h["out"] + h["err"]):
                tried[-1] += " (sem subcomando %s)" % sub
                continue
        return c
    raise LookupError("ferramenta '%s' não encontrada; procurado: %s" % (name, tried))


def check_g6(ctx):
    for name, text in (("validate", "validador do harness (--strict) verde no alvo"),
                       ("selftest", "selftest do harness verde (guards bloqueiam a sonda negativa)")):
        try:
            cmd = resolve_tool(ctx, name, ctx.target)
        except LookupError as exc:
            ctx.add("G6", text, False, str(exc))
            continue
        env = dict(os.environ, CLAUDE_PROJECT_DIR=ctx.target)
        r = sh(cmd, cwd=ctx.target, env=env, timeout=600)
        ctx.add("G6", text, r["exit"] == 0, "%s -> exit %s; %s" % (" ".join(cmd[-4:]), r["exit"],
                                                                   (r["err"] or r["out"])[-400:]))


# ================================================================ G7 plataformas
def frontmatter(path):
    try:
        txt = open(path, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError):
        return None, "ilegível"
    if not txt.startswith("---\n"):
        return None, "sem frontmatter"
    end = txt.find("\n---", 4)
    if end < 0:
        return None, "frontmatter não fecha"
    fm = {}
    for line in txt[4:end].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    body = txt[end + 4:].strip()
    if not body:
        return None, "corpo vazio"
    return fm, None


def check_g7(ctx):
    data, _, _ = ctx.team()
    plats = ctx.platforms or (data or {}).get("platforms") or ["claude-code", "cursor", "copilot", "codex"]
    agents = ctx.agents()
    if not agents:
        ctx.add("G7", "artefatos das plataformas presentes e bem formados", False, "team sem agentes")
        return
    for plat in plats:
        bad = []
        for a in agents:
            n = a["name"]
            if plat == "claude-code":
                p = ctx.p(".claude/agents/%s.md" % n)
                fm, e = frontmatter(p) if os.path.isfile(p) else (None, "ausente")
                if fm is None or fm.get("name") != n or not fm.get("description"):
                    bad.append("%s: %s" % (p.replace(ctx.target + "/", ""), e or "name/description"))
            elif plat == "cursor":
                cands = [ctx.p(".cursor/agents/%s.md" % n), ctx.p(".cursor/rules/%s.mdc" % n)]
                ok = False
                for p in cands:
                    if os.path.isfile(p):
                        fm, e = frontmatter(p)
                        if fm is not None and (fm.get("description") or fm.get("globs") or fm.get("alwaysApply")):
                            ok = True
                if not ok:
                    bad.append("%s: sem .cursor/agents/%s.md ou .cursor/rules/%s.mdc válido" % (n, n, n))
            elif plat == "copilot":
                p = ctx.p(".github/agents/%s.agent.md" % n)
                fm, e = frontmatter(p) if os.path.isfile(p) else (None, "ausente")
                if fm is None or not fm.get("description"):
                    bad.append("%s: %s" % (p.replace(ctx.target + "/", ""), e or "description"))
            elif plat == "codex":
                p = ctx.p("AGENTS.md")
                txt = open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""
                if not word_in(n, txt, case=True):
                    bad.append("AGENTS.md não menciona %s" % n)
        if plat == "claude-code":
            sp = ctx.p(".claude/settings.json")
            try:
                s = json.load(open(sp, encoding="utf-8"))
                if not (s.get("hooks") or {}).get("PreToolUse"):
                    bad.append("settings.json sem hooks.PreToolUse")
            except (OSError, ValueError) as exc:
                bad.append("settings.json inválido/ausente (%s)" % exc)
        ctx.add("G7", "plataforma %s: artefato por agente presente e bem formado" % plat, not bad,
                "problemas: %s" % bad[:6] if bad else "ok (%d agentes)" % len(agents))
    if ctx.platforms:
        extra = []
        markers = {"cursor": ".cursor/agents", "copilot": ".github/agents", "codex": ".codex"}
        for plat, d in markers.items():
            if plat not in plats and os.path.isdir(ctx.p(d)):
                extra.append(d)
        ctx.add("G7", "não emite plataformas que o usuário não pediu (%s)" % ",".join(plats), not extra,
                "emitidos sem pedido: %s" % extra if extra else "ok")


# ================================================================ G8 memória/glossário/regras
def mem_search(ctx, query, k=5):
    try:
        cmd = resolve_tool(ctx, "mem", ctx.target)
    except LookupError as exc:
        return None, str(exc)
    r = sh(cmd + ["search", query, "-k", str(k), "--json"], cwd=ctx.target,
           env=dict(os.environ, CLAUDE_PROJECT_DIR=ctx.target), timeout=60)
    if r["exit"] != 0:
        return None, "exit %s: %s" % (r["exit"], r["err"][-200:])
    try:
        data = json.loads(r["out"])
    except ValueError:
        return None, "saída não-JSON"
    res = data.get("results") if isinstance(data, dict) else data
    ms = data.get("ms") if isinstance(data, dict) else None
    return {"results": res or [], "ms": ms if ms is not None else r["ms"], "wall": r["ms"]}, None


def check_g8(ctx):
    probes = []
    for t in ctx.gt.get("terms") or []:
        probes.append(("term " + t["canonical"], t.get("mem_query") or t["canonical"], t["def"]["file"], [t["canonical"]]))
    for r in ctx.gt.get("business_rules") or []:
        probes.append(("rule " + r["id"], r.get("mem_query") or r["rule"], r["at"]["file"], r.get("keywords_any") or []))
    hits, lat, errs = 0, [], []
    for label, q, f, kws in probes:
        res, err = mem_search(ctx, q)
        if res is None:
            errs.append("%s: %s" % (label, err))
            continue
        lat.append(float(res["ms"]))
        blob = json.dumps(res["results"][:5], ensure_ascii=False)
        if f in blob and (not kws or any(k.lower() in blob.lower() for k in kws)):
            hits += 1
        else:
            errs.append("%s: miss" % label)
    recall = hits / float(len(probes)) if probes else 0.0
    lat.sort()
    p95 = lat[int(0.95 * (len(lat) - 1))] if lat else None
    ctx.add("G8", "cs-mem search acha termo/regra no top-5 (recall@5 >= 0,9) com p95 < 200 ms",
            recall >= 0.9 and p95 is not None and p95 < 200,
            "recall@5 %.2f (%d/%d), p95 %s ms; falhas: %s" % (recall, hits, len(probes), p95, errs[:6]))
    # termos/regras nos cartões: medidos como qualidade neutra ([Q] TERM/RULE), não aqui.


# ================================================================ util de stack (G13 e [Q] STACK)
def same_package(name, pkg):
    """`lib:node:express`, `github.com/x/express` e `express` são express; `@types/express` NÃO é (pacote npm
    com escopo é outro pacote — a versão dos tipos não é a da biblioteca)."""
    base = name.rsplit(":", 1)[-1]
    if base == pkg:
        return True
    if base.startswith("@") and not pkg.startswith("@"):
        return False
    return base.endswith("/" + pkg)


def find_version(objs, pkg):
    found = set()
    for o in objs:
        for d in walk(o):
            n = first_key(d, ["name", "package", "pkg", "module", "id"])
            v = first_key(d, ["version", "locked", "installed", "resolved_version"])
            if isinstance(n, str) and isinstance(v, str) and same_package(n, pkg):
                found.add(v)
            for k, val in d.items():
                if k == pkg and isinstance(val, str):
                    found.add(val)
    return found



# ================================================================ QUALIDADE neutra de formato ([Q])
# Lida dos artefatos emitidos por QUALQUER plataforma (Claude Code, Cursor, Copilot, Codex/AGENTS.md) e, se
# existir, de .swarm/ (cartões e core em team.json5; fatos de histórico/stack). Nada aqui exige o formato
# da skill: um time escrito à mão em AGENTS.md + .cursor/rules é medido com a mesma régua.
GATE_NAME_RE = re.compile(r"(?i)(review|revis|secur|segur|\bgate\b|audit|verif|qa-gate)")
TERR_HEAD_RE = re.compile(r"(?i)^#{1,6}\s*(territ|escopo|scope|owns|ownership|dono|arquivos (que|sob)|files you own|where you work)")
READ_ONLY_LINE_RE = re.compile(r"(?i)(l[eê] tamb[eé]m|leitura|\breads?\b|read-only|s[oó] l[eê]|sem territ|não edit|nao edit|do not edit|never edit)")
TEST_FILE_RE = re.compile(r"(^|/)(tests?|__tests__|spec)/|_test\.go$|\.(test|spec)\.[jt]sx?$|(^|/)test_[^/]*\.py$|_test\.py$")
FIXTURE_CTX_RE = re.compile(r"(?i)(exempl|example|demo|fixture|testdata|legacy|legad|sample|amostra|golden)")
# menção que RECUSA a fixture como produto ("… em Python/Java só como dado de teste", "test data only", "não é
# produto"): não afirma stack. Falso positivo medido no ts-shop (iteração 2): o `why` do never_use, gravado como
# string separada do `text`, perdia o contexto "fixture" da linha irmã.
FIXTURE_REFUSAL_RE = re.compile(
    r"(?i)(dados? de teste|test[- ]data|dados? de importa|s[oó] como dado|apenas como dado|only as (test )?data|"
    r"n[aã]o [eé] (c[oó]digo de )?produto|fora do produto|not (part of )?(the )?product|non-product|"
    r"exports? d[oe] |export(ed)? from|sistema antigo|old system)")
HIST_WORD_RE = re.compile(r"(?i)(hotspot|churn|commit|\bfix|bug|regress|revert|hist[oó]r|history|co-?change|mudam juntos|change together|incidente|incident|quebrou|broke)")
AGENT_SOURCES = ((".claude/agents", ".md"), (".cursor/agents", ".md"), (".github/agents", ".md"),
                 (".github/prompts", ".prompt.md"), (".codex/agents", ".md"))
RULE_SOURCES = ((".cursor/rules", (".mdc", ".md")), (".github/instructions", (".instructions.md",)),
                (".claude/rules", (".md",)))
SHARED_FILES = ("CLAUDE.md", "AGENTS.md", ".github/copilot-instructions.md")


def parse_frontmatter(txt):
    """→ (dict, corpo). Aceita `k: v`, `k: [a, b]` e listas YAML `k:\\n  - a`."""
    if not txt.startswith("---"):
        return {}, txt
    end = txt.find("\n---", 3)
    if end < 0:
        return {}, txt
    fm, key = {}, None
    for line in txt[3:end].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            fm[key] = val.strip("'\"") if val else []
            continue
        m = re.match(r"^\s*-\s*(.+)$", line)
        if m and key is not None:
            if not isinstance(fm.get(key), list):
                fm[key] = [fm[key]] if fm.get(key) else []
            fm[key].append(m.group(1).strip().strip("'\""))
    return fm, txt[end + 4:].lstrip("\n")


def fm_globs(fm):
    out = []
    for k in ("globs", "applyTo", "paths"):
        v = fm.get(k)
        if isinstance(v, str):
            v = v.strip("[]")
            out += [x.strip().strip("'\"") for x in v.split(",")]
        elif isinstance(v, list):
            for x in v:
                out += [y.strip().strip("'\"") for y in x.split(",")]
    return [g for g in out if g and g not in ("**", "**/*", "*")]


def norm_name(stem):
    s = stem.lower()
    for suf in (".agent", ".instructions", ".prompt"):
        if s.endswith(suf):
            s = s[: -len(suf)]
    s = re.sub(r"^\d+[-_]", "", s)
    if s.startswith("cs-"):
        s = s[3:]
    return s



def cost_lines(path):
    """Linhas que custam contexto, como scripts/emit/render.count_lines: sem front matter YAML,
    sem linha vazia e sem comentário HTML de linha inteira (o orçamento S1/S2 da skill mede assim)."""
    text = open(path, encoding="utf-8", errors="replace").read()
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            text = text[end + 4:]
    n = 0
    for line in text.split("\n"):
        t = line.strip()
        if not t or (t.startswith("<!--") and t.endswith("-->")):
            continue
        n += 1
    return n

def section_territory(body):
    """Globs/caminhos da seção 'Território'/'Escopo' de um cartão markdown (linhas de leitura são ignoradas)."""
    out, inside = [], False
    for line in body.splitlines():
        if re.match(r"^#{1,6}\s", line):
            inside = bool(TERR_HEAD_RE.match(line))
            continue
        inline = re.match(r"(?i)^\s*[-*]?\s*\**(territ[oó]rio|territory|escopo de escrita|owns)\**\s*:\s*(.+)$", line)
        if not inside and not inline:
            continue
        if READ_ONLY_LINE_RE.search(line):
            continue
        text = inline.group(2) if inline and not inside else line
        for tok in re.findall(r"`([^`\s]+)`", text):
            tok = tok.strip().rstrip(".,;:")
            if tok.startswith("@") or "://" in tok or tok.startswith("-"):
                continue
            if "/" in tok or re.search(r"\.[A-Za-z0-9]{1,8}$", tok) or tok in ("Makefile", "Dockerfile"):
                out.append(tok.lstrip("./") if tok.startswith("./") else tok)
    return out


class QAgent(object):
    def __init__(self, name):
        self.name = name
        self.texts = []          # texto próprio (cartões emitidos por plataforma, card do team.json5)
        self.sources = []
        self.team_territory = None
        self.rule_globs = []
        self.md_territory = []
        self.reads = []
        self.kind = None
        self.tools = None        # lista de ferramentas declaradas (None = não declarado)
        self.denied = []

    @property
    def territory(self):
        if self.team_territory:
            return list(self.team_territory)
        if self.rule_globs:  # glob declarado pela plataforma (globs/applyTo/paths) é mais preciso que a prosa
            return sorted(set(self.rule_globs))
        return sorted(set(self.md_territory))

    def is_gate(self):
        if self.kind:
            return self.kind == "gate"
        return bool(GATE_NAME_RE.search(self.name)) and not self.can_write_tools()

    def can_write_tools(self):
        if self.tools is None:
            return None
        t = " ".join(self.tools).lower()
        d = " ".join(self.denied).lower()
        return any(w in t for w in ("edit", "write", "multiedit")) and not ("edit" in d and "write" in d)

    def is_writer(self):
        if self.is_gate():
            return False
        w = self.can_write_tools()
        if w is not None:
            return w and bool(self.territory)
        return bool(self.territory)


class QualityView(object):
    """Time como ele aparece nos artefatos, independente da plataforma que os gerou."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.orig = {}
        base = os.path.join(FIXTURES, ctx.fixture or "", "repo")
        self.base = base if os.path.isdir(base) else None
        self.agents = {}
        self.path_rules = []     # (globs, texto, fonte)
        self.shared = []         # (fonte, texto) carregado por todo agente
        self.sources = []
        self.extra = []          # texto de .swarm que não é cartão (core já entra em shared)
        self._build()

    # ---- leitura
    def added_text(self, rel):
        p = self.ctx.p(rel)
        try:
            txt = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            return ""
        if self.base and os.path.isfile(os.path.join(self.base, rel)):
            orig = set(l.strip() for l in open(os.path.join(self.base, rel), encoding="utf-8",
                                                errors="replace").read().splitlines() if l.strip())
            txt = "\n".join(l for l in txt.splitlines() if l.strip() and l.strip() not in orig)
        return txt

    def agent(self, name):
        if name not in self.agents:
            self.agents[name] = QAgent(name)
        return self.agents[name]

    def _files(self, d, sufs):
        root = self.ctx.p(d)
        out = []
        if not os.path.isdir(root):
            return out
        for r, dirs, files in os.walk(root):
            for f in files:
                if any(f.endswith(s) for s in sufs):
                    out.append(os.path.relpath(os.path.join(r, f), self.ctx.target).replace(os.sep, "/"))
        return sorted(out)

    def _build(self):
        ctx = self.ctx
        data, _, _ = ctx.team()
        if isinstance(data, dict):
            for a in data.get("agents") or []:
                if not isinstance(a, dict) or not a.get("name"):
                    continue
                q = self.agent(norm_name(a["name"]))
                q.kind = a.get("kind")
                q.team_territory = [g for g in a.get("territory") or [] if isinstance(g, str)]
                q.reads = [g for g in a.get("reads") or [] if isinstance(g, str)]
                if isinstance(a.get("tools"), list):
                    q.tools = a["tools"]
                card = "\n".join(strings(a.get("card") or {}))
                if card:
                    q.texts.append(card)
                    q.sources.append(".swarm/team.json5#%s" % a["name"])
            core = "\n".join(strings((data.get("core") or {})))
            if core.strip():
                self.shared.append((".swarm/team.json5#core", core))
        for d, suf in AGENT_SOURCES:
            for rel in self._files(d, (suf,)):
                fm, body = parse_frontmatter(open(ctx.p(rel), encoding="utf-8", errors="replace").read())
                stem = os.path.basename(rel)[: -len(suf)] if rel.endswith(suf) else os.path.basename(rel)
                name = norm_name(fm.get("name") if isinstance(fm.get("name"), str) and fm.get("name") else stem)
                q = self.agent(name)
                q.texts.append(body)
                q.sources.append(rel)
                tl = fm.get("tools")
                if tl:
                    q.tools = (q.tools or []) + (tl if isinstance(tl, list) else re.split(r"[,\s\[\]'\"]+", tl))
                dn = fm.get("disallowedTools")
                if dn:
                    q.denied += dn if isinstance(dn, list) else re.split(r"[,\s]+", dn)
                q.md_territory += section_territory(body)
                self.sources.append(rel)
        defined = set(self.agents)
        rules = []
        for d, sufs in RULE_SOURCES:
            for rel in self._files(d, sufs):
                fm, body = parse_frontmatter(open(ctx.p(rel), encoding="utf-8", errors="replace").read())
                base = os.path.basename(rel)
                stem = base
                for s in sufs:
                    if base.endswith(s):
                        stem = base[: -len(s)]
                rules.append((rel, norm_name(stem), fm, body))
                self.sources.append(rel)
        for rel, name, fm, body in rules:
            always = str(fm.get("alwaysApply", "")).lower() == "true"
            globs = fm_globs(fm)
            if name in defined:
                q = self.agents[name]
                q.texts.append(body)
                q.rule_globs += globs
                q.sources.append(rel)
            elif always or (not globs and rel.endswith("copilot-instructions.md")):
                self.shared.append((rel, body))
            elif globs:
                self.path_rules.append((globs, body, rel))
            else:
                self.shared.append((rel, body))
        if not defined:  # time só de regras por caminho (ex.: Cursor sem subagentes): cada regra vira agente
            for globs, body, rel in self.path_rules:
                q = self.agent(norm_name(os.path.basename(rel).split(".")[0]))
                q.texts.append(body)
                q.rule_globs += globs
                q.sources.append(rel)
            self.path_rules = []
        for rel in SHARED_FILES:
            if os.path.isfile(ctx.p(rel)):
                t = self.added_text(rel)
                if t.strip():
                    self.shared.append((rel, t))
                    self.sources.append(rel)
        for r, dirs, files in os.walk(ctx.target):
            dirs[:] = [x for x in dirs if x not in (".git", "node_modules", ".swarm", "__pycache__", ".claude",
                                                   ".cursor", ".github", ".codex")]
            relr = os.path.relpath(r, ctx.target).replace(os.sep, "/")
            if relr == ".":
                continue
            for f in files:
                if f in ("AGENTS.md", "CLAUDE.md"):
                    rel = relr + "/" + f
                    t = self.added_text(rel)
                    if t.strip():
                        self.path_rules.append(([relr + "/**"], t, rel))
                        self.sources.append(rel)
        for rel in (".swarm/knowledge/stack", ".swarm/facts/stack"):
            d, _, _ = ctx.load_art(rel)
            if d is not None:
                self.extra.append(d)

    # ---- consultas
    def emitted(self):
        return bool(self.agents) or bool(self.shared) or bool(self.path_rules)

    def writers(self):
        return [a for a in self.agents.values() if a.is_writer()]

    def gates(self):
        return [a for a in self.agents.values() if a.is_gate()]

    def files_of(self, a):
        return [f for f in self.ctx.product_files() if matches_any(f, a.territory)]

    def owners_of_prefixes(self, prefixes):
        return sorted(a.name for a in self.writers() if any(under(f, prefixes) for f in self.files_of(a)))

    def knowledge(self, a):
        """O que o agente lê quando é invocado: o próprio texto + núcleo sempre carregado + regras por caminho do
        território (gate: de todo caminho, porque revisa o repo inteiro)."""
        parts = list(a.texts) + [t for _, t in self.shared]
        scope = a.territory + a.reads
        files = self.ctx.product_files()
        for globs, t, _ in self.path_rules:
            if a.is_gate() or any(matches_any(f, globs) and (not scope or matches_any(f, scope)) for f in files) \
                    or any(g.rstrip("*/") and any(s.startswith(g.rstrip("*/")) for s in scope) for g in globs):
                parts.append(t)
        return "\n".join(parts)

    def corpus(self):
        parts = [t for a in self.agents.values() for t in a.texts] + [t for _, t in self.shared] + \
                [t for _, t, _ in self.path_rules]
        return "\n".join(parts)


def stale_filter(text, sc):
    """Linhas que não negam, não atribuem ao README e não trazem a verdade junto (= repetição como verdade)."""
    truth_tokens = re.findall(r"\d+(?:\.\d+)+", sc.get("truth") or "")
    out = []
    for l in text.splitlines():
        if NEG_RE.search(l) or re.search(r"(?i)readme|desatualiz|outdated|stale|errad|wrong|mas o|but the|actually|na verdade", l):
            continue
        if any(t in l for t in truth_tokens):
            continue
        out.append(l)
    return "\n".join(out)


def git_fix_commits(ctx):
    r = sh(["git", "log", "--format=%H%x09%s"], cwd=ctx.target, timeout=60)
    out = []
    for line in r["out"].splitlines():
        if "\t" not in line:
            continue
        sha, subj = line.split("\t", 1)
        if re.match(r"(?i)^(fix(\(.*?\))?!?:|revert|hotfix)", subj.strip()):
            out.append((sha, subj.strip()))
    return out


def quality_checks(ctx):
    qv = QualityView(ctx)
    gt = ctx.gt
    files = ctx.product_files()
    writers, gates = qv.writers(), qv.gates()
    names = sorted(qv.agents)
    src = "agentes %s (fontes: %d arquivos)" % (names, len(qv.sources))
    corpus = qv.corpus()

    # territórios: disjuntos e cobertura
    overlap, owned = [], 0
    for f in files:
        o = [a.name for a in writers if matches_any(f, a.territory)]
        if o:
            owned += 1
        if len(o) > 1:
            overlap.append("%s -> %s" % (f, ",".join(o)))
    ctx.add("TERR", "territórios de escrita disjuntos (glob dos agentes; nenhum arquivo de produto com 2 donos)",
            bool(writers) and owned > 0 and not overlap,
            "%d escritores; %d/%d arquivos com dono; sobreposição %d: %s; %s" % (
                len(writers), owned, len(files), len(overlap), overlap[:6], src), kind="Q")
    cov = owned / float(len(files)) if files else 0.0
    unowned = [f for f in files if not any(matches_any(f, a.territory) for a in writers)]
    ctx.add("TERR", "cobertura: >=90% dos arquivos de produto têm um dono de escrita declarado",
            bool(writers) and cov >= 0.9, "cobertura %.2f; sem dono: %s" % (cov, unowned[:8]), kind="Q")

    # BC — contexto de cada escritor = o bounded context com maioria (>=50%) dos SEUS arquivos de contexto
    # (código de produção; testes co-localizados ficam de fora, para não punir quem dá teste a um dono de testes);
    # recuperado se o escritor cobre >=80% desse contexto. Agente-mega (`src/**`) não recupera nenhum.
    bcs = gt.get("bounded_contexts") or []
    buckets = [(b["name"], b["prefixes"]) for b in bcs] + [(e["name"], e["prefixes"])
                                                            for e in gt.get("acceptable_extra_territories") or []]
    prod = [f for f in files if not TEST_FILE_RE.search(f)]
    recalled, precise, detail = set(), 0, []
    for a in writers:
        mine = [f for f in qv.files_of(a)]
        if not mine:
            detail.append("%s: território vazio" % a.name)
            continue
        if not any(under(f, pref) for f in mine for _, pref in buckets):
            detail.append("%s: fora de qualquer contexto" % a.name)
            continue
        precise += 1
        counts = {}
        for f in mine:
            if f in prod:
                for b in bcs:
                    if under(f, b["prefixes"]):
                        counts[b["name"]] = counts.get(b["name"], 0) + 1
                        break
        if not counts:
            detail.append("%s: só contextos extras" % a.name)
            continue
        best = max(counts, key=counts.get)
        b = [x for x in bcs if x["name"] == best][0]
        bfiles = [f for f in prod if under(f, b["prefixes"])]
        cv = len([f for f in bfiles if f in mine]) / float(len(bfiles)) if bfiles else 0.0
        share = counts[best] / float(sum(counts.values()))
        if cv >= 0.8 and share >= 0.5:
            recalled.add(best)
        detail.append("%s->%s(cobre %.2f, %.2f do seu código de contexto)" % (a.name, best, cv, share))
    prec = precise / float(len(writers)) if writers else 0.0
    rec = len(recalled) / float(len(bcs)) if bcs else 0.0
    ctx.add("BC", "bounded contexts dos agentes batem com o GROUND_TRUTH (precisão >= 0,75 e recall >= 2/3)",
            prec >= 0.75 and rec >= 2 / 3.0 - 1e-9, "precisão %.2f recall %.2f; recuperados %s; %s" % (
                prec, rec, sorted(recalled), "; ".join(detail)[:700]), kind="Q")

    # INV — invariante de ADR no conhecimento de todo dono e de todo gate
    miss, tot = [], 0
    for inv in gt.get("invariants") or []:
        targets = qv.owners_of_prefixes(inv.get("owner_prefixes") or []) + [g.name for g in gates]
        for n in sorted(set(targets)):
            tot += 1
            txt = qv.knowledge(qv.agents[n]).lower()
            if not all(any(k.lower() in txt for k in grp) for grp in inv["keywords_all"]):
                miss.append("%s∉%s" % (inv["id"], n))
    ctx.add("INV", "invariante de cada ADR está no que TODO dono do escopo e todo gate lê ao ser invocado",
            bool(writers) and bool(gates) and not miss,
            ("faltando: %s" % miss[:10]) if miss else ("ok (%d pares)" % tot if gates else "nenhum agente gate"), kind="Q")

    # termos
    tot, ok, miss, never = 0, 0, [], []
    for t in gt.get("terms") or []:
        for n in qv.owners_of_prefixes(t.get("owner_prefixes") or []):
            tot += 1
            txt = qv.knowledge(qv.agents[n])
            if word_in(t["canonical"], txt, case=True):
                ok += 1
            else:
                miss.append("%s∉%s" % (t["canonical"], n))
            for v in t.get("never_use") or []:
                if term_misuse_lines(v, t["canonical"], txt):
                    never.append("%s usa '%s'" % (n, v))
    ctx.add("TERM", "termos canônicos no conhecimento dos donos (>=80%) e variantes proibidas não usadas como termo",
            bool(tot) and ok / float(tot) >= 0.8 and not never,
            "%d/%d; faltando: %s; variantes: %s" % (ok, tot, miss[:6], sorted(set(never))[:4]), kind="Q")

    # regras de negócio
    tot, ok, miss = 0, 0, []
    for r in gt.get("business_rules") or []:
        targets = qv.owners_of_prefixes(r.get("owner_prefixes") or []) + [g.name for g in gates]
        for n in sorted(set(targets)):
            tot += 1
            txt = qv.knowledge(qv.agents[n]).lower()
            if any(k.lower() in txt for k in r.get("keywords_any") or []):
                ok += 1
            else:
                miss.append("%s∉%s" % (r["id"], n))
    ctx.add("RULE", "regra de negócio no conhecimento do dono e do gate (>=80% dos pares)",
            bool(gates) and bool(tot) and ok / float(tot) >= 0.8,
            "%d/%d; gates=%s; faltando: %s" % (ok, tot, [g.name for g in gates], miss[:8]), kind="Q")

    # STACK — versões do lockfile citadas certas; nenhuma versão histórica afirmada
    st = gt.get("stack") or {}
    bad, okn, srcs = [], 0, []
    for pkg in st.get("must_report") or []:
        want = st["packages"][pkg].lstrip("v")
        # "httpx 0.27.0", "httpx==0.27.0", "| httpx | 0.27.0 |", "httpx pinado em 0.27.0" (até 25 caracteres sem dígito)
        rx = re.compile(r"(?<![\w/.-])%s(?![\w])[^\d\n]{0,25}?v?%s(?![\w]|\.\d)" % (re.escape(pkg), re.escape(want)))
        short = pkg.split("/")[-1] if "/" in pkg else None
        hit = rx.search(corpus)
        if not hit and short and re.match(r"v\d+$", short):  # github.com/x/pgx/v5 → "pgx/v5 v5.6.0" ou "pgx v5.6.0"
            short = pkg.split("/")[-2]
        if not hit and short:
            hit = re.search(r"(?<![\w.-])%s(/v\d+)?(?![\w])[^\d\n]{0,25}?v?%s(?![\w]|\.\d)" % (re.escape(short), re.escape(want)), corpus)
        if not hit:  # mapa/fatos de stack em .swarm (estruturado)
            hit = find_version(qv.extra, pkg) & {want, "v" + want}
        if hit:
            okn += 1
            srcs.append("%s: %s" % (pkg, "fatos/mapa .swarm" if isinstance(hit, set) else "texto"))
        else:
            bad.append("%s %s não citado" % (pkg, want))
    knowledge_lines = stale_filter(corpus, {"truth": " ".join(st.get("packages", {}).values())})
    for pkg, v in (st.get("historic_wrong_versions") or {}).items():
        if re.search(re.escape(pkg) + r"[\s@=:\"'`|]{1,4}" + re.escape(v) + r"(?![\w]|\.\d)", knowledge_lines):
            bad.append("afirma %s %s (versão velha/declarada)" % (pkg, v))
    ctx.add("STACK", "versões exatas do lockfile citadas (must_report) e nenhuma versão histórica/range afirmada como atual",
            not bad, "ok (%d must_report; %s)" % (okn, srcs) if not bad else "; ".join(bad[:8]), kind="Q")

    # FIX — fixture não vira produto/stack
    hits = []
    neg_corpus = neg_filtered(corpus)
    fx = gt.get("fixture_paths") or []
    # linha que descreve a própria fixture ("exemplo Python para parceiros") ou invoca uma ferramenta
    # (`python3 x.py`) não afirma stack de produto
    fx_corpus = fixture_claim_corpus(corpus, fx)
    for t in gt.get("stack_must_not_include") or []:
        if word_in(t, fx_corpus):
            hits.append("%s no texto" % t)
        if any(word_in(t, n) for n in names):
            hits.append("%s em nome de agente" % t)
    fx_files = [f for f in ctx.fixture_files() if under(f, fx)]
    only_fx = [a.name for a in qv.agents.values() if a.territory and any(matches_any(f, a.territory) for f in fx_files)
               and not qv.files_of(a)]
    ctx.add("FIX", "fixture NÃO aparece como produto: stack da fixture não afirmada, nenhum agente só de fixture",
            bool(qv.agents) and not hits and not only_fx,
            "contaminação: %s; agentes só de fixture: %s" % (hits[:6], only_fx), kind="Q")

    # NEG — padrões ausentes não afirmados
    neg_hits = [n["pattern"] for n in gt.get("absent_patterns") or [] if word_in(n["pattern"], neg_corpus)]
    ctx.add("NEG", "padrões que NÃO existem no repo não são afirmados (linhas com negação/ressalva ignoradas)",
            bool(qv.agents) and not neg_hits,
            "afirmados: %s" % neg_hits if neg_hits else "ok (%d padrões)" % len(gt.get("absent_patterns") or []), kind="Q")

    # HIST — histórico real chega ao time (texto) ou aos fatos de histórico da skill
    h, _, _ = ctx.load_art(".swarm/facts/history")
    hblob = json.dumps(h, ensure_ascii=False) if h is not None else ""
    lines = corpus.splitlines()
    miss = []
    for x in gt.get("hotspots") or []:
        # o caminho, o nome do arquivo ou o módulo (diretório pai) numa linha que fala de histórico
        keys = [x, os.path.basename(x), os.path.basename(os.path.dirname(x))]
        in_text = any(HIST_WORD_RE.search(l) and any(word_in(k, l) for k in keys if k) for l in lines)
        if not in_text and x not in hblob:
            miss.append("hotspot %s" % x)
    for c in gt.get("co_change") or []:
        a, b = c["a"].rstrip("/"), c["b"].rstrip("/")
        ka, kb = [a, os.path.basename(a)], [b, os.path.basename(b)]
        win = any(any(k in "\n".join(lines[i:i + 4]) for k in ka) and any(k in "\n".join(lines[i:i + 4]) for k in kb)
                  for i in range(len(lines)))
        if not win and not (a in hblob and b in hblob):
            miss.append("co-change %s<->%s" % (a, b))
    fixes = git_fix_commits(ctx)
    cited = set()
    for sha, subj in fixes:
        if re.search(r"(?<![0-9a-f])%s[0-9a-f]{0,33}(?![0-9a-f])" % sha[:7], corpus) or \
                (len(subj) >= 20 and subj.split(":", 1)[-1].strip()[:40].lower() in corpus.lower()):
            cited.add(sha)
    nfix_facts = len(re.findall(r'"fix(\([^)]*\))?:', hblob)) + len(re.findall(r"\bfix\b", hblob.lower()))
    rv = (gt.get("revert") or {}).get("subject_contains") or ""
    fix_ok = len(cited) >= min(2, gt.get("fix_commits_min") or 1) or nfix_facts >= (gt.get("fix_commits_min") or 1) \
        or (rv and rv.lower() in corpus.lower() and cited)
    if not fix_ok:
        miss.append("commits de correção: %d citados no texto (de %d), %d nos fatos" % (len(cited), len(fixes), nfix_facts))
    ctx.add("HIST", "histórico: hotspots, co-change e commits de correção reais aparecem (texto dos agentes ou facts/history)",
            not miss, "faltando: %s" % miss if miss else "ok (%d fixes citados no texto; fatos=%s)" % (
                len(cited), "sim" if h is not None else "não"), kind="Q")

    # conteúdo humano preservado (só conta se a execução escreveu algo)
    hmiss = []
    for hc in gt.get("human_content") or []:
        p = ctx.p(hc["file"])
        if not os.path.isfile(p) or hc["must_contain"] not in open(p, encoding="utf-8", errors="replace").read():
            hmiss.append("%s: '%s'" % (hc["file"], hc["must_contain"][:40]))
    ran = qv.emitted() or os.path.isfile(ctx.p(".swarm/team.json5"))
    ctx.add("HUMAN", "conteúdo humano de CLAUDE.md/AGENTS.md preexistente preservado (após a execução escrever)",
            ran and not hmiss, "perdido: %s" % hmiss if hmiss else ("ok" if ran else "nada emitido"), kind="Q")

    # comando de teste real citado
    test = (gt.get("commands") or {}).get("test") or {}
    variants = [test.get("cmd")] + list(test.get("equivalents") or [])
    found = [v for v in variants if v and v in corpus]
    ctx.add("TESTCMD", "o comando de teste real do repo é citado aos agentes (%s ou equivalente)" % test.get("cmd"),
            bool(found), "citado: %s" % found[:3] if found else "nenhuma variante %s" % variants[:4], kind="Q")

    # README desatualizado não repetido como verdade
    sc = gt.get("stale_doc_claim") or {}
    rep = [k for k in sc.get("keywords") or [] if k.lower() in stale_filter(corpus, sc).lower()]
    ctx.add("STALE", "afirmação desatualizada do README (%s) não é repetida como verdade" % sc.get("claim"),
            bool(qv.agents) and not rep, "repetida: %s" % rep if rep else ("ok" if qv.agents else "nada emitido"), kind="Q")


# ================================================================ G13 mapas + docs do projeto
def check_g13(ctx):
    tree, _, err = ctx.load_art(".swarm/knowledge/tree")
    if tree is None:
        ctx.add("G13", "tree.json5: todo diretório de produto aparece com >=1 arquivo representativo", False, err)
    else:
        ss = [s for s in strings(tree)]
        miss = []
        for d in ctx.gt.get("product_dirs") or []:
            if not any(s.startswith(d.rstrip("/") + "/") and os.path.isfile(ctx.p(s)) for s in ss):
                if not any(s.startswith(d.rstrip("/") + "/") for s in ss):
                    miss.append(d)
                else:
                    miss.append(d + " (sem arquivo existente)")
        ctx.add("G13", "tree.json5: todo diretório de produto aparece com >=1 arquivo representativo", not miss,
                "faltando: %s" % miss if miss else "ok")
    st, _, err = ctx.load_art(".swarm/knowledge/stack")
    if st is None:
        ctx.add("G13", "knowledge/stack.json5: versões batem com o lockfile", False, err)
    else:
        bad = []
        for pkg, v in (ctx.gt["stack"].get("packages") or {}).items():
            for x in find_version([st], pkg):
                if x.lstrip("v=^~") != v.lstrip("v"):
                    bad.append("%s %s != %s" % (pkg, x, v))
        mr = [p for p in ctx.gt["stack"].get("must_report") or [] if not find_version([st], p)]
        ctx.add("G13", "knowledge/stack.json5: versões batem com o lockfile", not bad and not mr,
                "divergências %s; ausentes %s" % (bad, mr))
    col, _, err = ctx.load_art(".swarm/knowledge/collision")
    cp = ctx.gt.get("coupled_pair") or {}
    oa = ctx.owners_of_prefixes(cp.get("a_prefixes") or [])
    ob = ctx.owners_of_prefixes(cp.get("b_prefixes") or [])
    if col is None:
        ctx.add("G13", "par acoplado aparece em collision.json5 do_not_parallelize", False, err)
    else:
        dnp = col.get("do_not_parallelize") if isinstance(col, dict) else None
        pairs = []
        for it in dnp or []:
            if isinstance(it, list) and len(it) >= 2:
                pairs.append(set(it[:2]))
            elif isinstance(it, dict):
                a = first_key(it, ["a", "left", "from"])
                b = first_key(it, ["b", "right", "to"])
                pr = it.get("pair") or it.get("agents") or it.get("territories")
                if isinstance(pr, list) and len(pr) >= 2:
                    pairs.append(set(pr[:2]))
                elif a and b:
                    pairs.append({a, b})
        same = bool(set(oa) & set(ob))
        hit = same or any(p == {x, y} for p in pairs for x in oa for y in ob)
        ctx.add("G13", "par acoplado (%s x %s) aparece em collision.json5 do_not_parallelize" % (
            cp.get("a_prefixes"), cp.get("b_prefixes")), dnp is not None and hit,
            "donos A=%s B=%s; mesmo dono=%s; pares=%s" % (oa, ob, same, [sorted(p) for p in pairs][:6]))
    sc = ctx.gt.get("stale_doc_claim") or {}
    pd, _, err = ctx.load_art(".swarm/facts/project_docs")
    if pd is None:
        ctx.add("G13", "afirmação desatualizada do README vira fato `stale` em project_docs.json5", False, err)
    else:
        found = False
        for d in walk(pd):
            blob = json.dumps(d, ensure_ascii=False)
            if sc["file"] in blob and any(k.lower() in blob.lower() for k in sc["keywords"]) and \
                    (d.get("status") == "stale" or d.get("stale") is True or '"stale"' in blob):
                found = True
                break
        ctx.add("G13", "afirmação desatualizada (%s) vira fato `stale` em project_docs.json5" % sc.get("claim"), found,
                "ok" if found else "nenhum fato stale citando %s:%s" % (sc.get("file"), sc.get("line")))
    # repetição do README velho e conteúdo humano preservado: [Q] STALE e [Q] HUMAN.


# ================================================================ formato JSON5
ALLOWED_MD = [r"^\.claude/agents/[^/]+\.md$", r"^\.claude/rules/.+\.md$", r"^\.claude/skills/.+\.md$",
              r"^\.claude/commands/.+\.md$", r"^(.+/)?CLAUDE\.md$", r"^(.+/)?AGENTS\.md$", r"^\.cursor/.+\.mdc?$",
              r"^\.github/copilot-instructions\.md$", r"^\.github/agents/.+\.agent\.md$",
              r"^\.github/instructions/.+\.instructions\.md$", r"^\.github/prompts/.+\.prompt\.md$",
              r"^\.codex/.+\.md$", r"^\.swarm/memory/agents/[^/]+\.md$"]


def check_format(ctx):
    orig = set(ctx.fixture_files())
    extra_md = []
    for root, dirs, files in os.walk(ctx.target):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__")]
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), ctx.target).replace(os.sep, "/")
            if rel.endswith(".md") and rel not in orig and not any(re.match(rx, rel) for rx in ALLOWED_MD):
                if not rel.startswith(("docs/specs/", "docs/bugs/")):
                    extra_md.append(rel)
    ran = os.path.isfile(ctx.p(".swarm/team.json5"))
    ctx.add("FMT", "nenhum mapa/conhecimento gerado em .md fora dos artefatos que a plataforma exige",
            ran and not extra_md, "md extras: %s" % extra_md[:10] if extra_md else ("ok" if ran else "skill não rodou"))
    jsons = [r for r in (".swarm/team.json", ".swarm/knowledge/tree.json", ".swarm/state/board.json",
                         re.sub(r"\.json5$", ".json", ctx.state_rel("board")),
                         ".swarm/session/resume.json") if os.path.isfile(ctx.p(r))]
    t5 = os.path.isfile(ctx.p(".swarm/team.json5"))
    ctx.add("FMT", "artefatos da skill em JSON5 (team.json5 existe; nenhum team/board/tree/resume em .json)",
            t5 and not jsons, "team.json5=%s; .json indevidos: %s" % (t5, jsons))


# ================================================================ cenários (G9, G10, G12, G14, G15, G16, G8)
class ScenarioFail(Exception):
    pass


def scenario_vars(ctx, target):
    sp = ctx.gt.get("scenario_paths") or {}
    v = {"T": target, "SKILL": ctx.skill}
    for k, val in sp.items():
        v["PATH_" + k.upper()] = val
    test = (ctx.gt.get("commands") or {}).get("test") or {}
    v["TEST_CMD"] = test.get("cmd", "true")

    def owner(path):
        o = ctx.owners_of(path) if path else []
        return o[0] if o else ""
    v["AGENT_DEV"] = owner(sp.get("dev_a"))
    v["AGENT_DEV2"] = owner(sp.get("dev_b"))
    v["AGENT_LESSON"] = owner(sp.get("lesson_file"))
    g = ctx.gates()
    v["AGENT_GATE"] = g[0]["name"] if g else ""
    return v


def subst(x, v):
    if isinstance(x, str):
        for k, val in v.items():
            x = x.replace("{" + k + "}", str(val))
        return x
    if isinstance(x, list):
        return [subst(i, v) for i in x]
    if isinstance(x, dict):
        return {k: subst(val, v) for k, val in x.items()}
    return x


def tier_order(target):
    tiers, cost = list(TIERS_DEFAULT), dict(COST_DEFAULT)
    return tiers, cost


def run_hook(target, event, payload, env):
    sp = os.path.join(target, ".claude", "settings.json")
    try:
        s = json.load(open(sp, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ScenarioFail("settings.json ausente/inválido: %s" % exc)
    entries = (s.get("hooks") or {}).get(event) or []
    tool = payload.get("tool_name", "")
    cmds = []
    for e in entries:
        m = e.get("matcher", "")
        if not m or re.search(m, tool):
            for h in e.get("hooks") or []:
                if h.get("command"):
                    cmds.append(h["command"])
    if not cmds:
        raise ScenarioFail("nenhum hook %s casa %s" % (event, tool))
    payload = dict(payload, hook_event_name=event, cwd=target, session_id="eval", tool_use_id="toolu_eval_%d" % int(time.time() * 1000))
    blocked, outs = False, []
    for c in cmds:
        c = c.replace("$CLAUDE_PROJECT_DIR", target).replace("${CLAUDE_PROJECT_DIR}", target)
        r = sh(c, cwd=target, env=env, stdin=json.dumps(payload), shell=True, timeout=60)
        outs.append("exit %s %s" % (r["exit"], (r["err"] + r["out"])[-200:]))
        if r["exit"] == 2:
            blocked = True
        try:
            j = json.loads(r["out"]) if r["out"].strip().startswith("{") else {}
        except ValueError:
            j = {}
        dec = json.dumps(j).lower()
        if '"decision": "block"' in dec or '"permissiondecision": "deny"' in dec:
            blocked = True
    return blocked, "; ".join(outs)


def run_scenario(ctx, sc):
    tmp = tempfile.mkdtemp(prefix="cs-eval-")
    target = os.path.join(tmp, "repo")
    try:
        shutil.copytree(ctx.target, target, symlinks=True,
                        ignore=shutil.ignore_patterns("node_modules"))
        if sc.get("fresh_target"):
            shutil.rmtree(os.path.join(target, ".swarm"), ignore_errors=True)
        v = scenario_vars(ctx, target)
        env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", ""),
               "CLAUDE_PROJECT_DIR": target, "LANG": "C.UTF-8"} if sc.get("clean_env") else \
            dict(os.environ, CLAUDE_PROJECT_DIR=target)
        saved, log = {}, []
        steps = []
        for st in sc["steps"]:
            if "repeat" in st:
                for i in range(int(st["repeat"])):
                    steps.append(subst(st["step"], {"i": i}))
            else:
                steps.append(st)
        for raw in steps:
            st = subst(raw, v)
            if "tool" in st:
                try:
                    cmd = resolve_tool(ctx, st["tool"], target)
                except LookupError as exc:
                    raise ScenarioFail(str(exc))
                args_ = st.get("args", [])
                for i_, a_ in enumerate(args_[:-1]):
                    if a_ == "--agent" and not args_[i_ + 1]:
                        raise ScenarioFail("nenhum agente dono do caminho do cenário (scenario_paths) no team")
                if any(re.search(r"\{[A-Z_]+\}", a) for a in st.get("args", [])):
                    raise ScenarioFail("placeholder não resolvido em %s (agente/caminho ausente no team?)" % st["args"])
                r = sh(cmd + st.get("args", []), cwd=target, env=env, timeout=300)
                out = r["out"] + r["err"]
                tag = "%s %s -> %s" % (st["tool"], " ".join(st.get("args", [])[:3]), r["exit"])
                log.append(tag)
                exp = st.get("expect", "ok")
                if exp == "ok" and r["exit"] != 0:
                    raise ScenarioFail("%s (esperado ok): %s" % (tag, out[-300:]))
                if exp == "fail" and r["exit"] == 0:
                    raise ScenarioFail("%s (esperado falha/recusa): %s" % (tag, out[-300:]))
                if exp == "any" and r["exit"] == 127:
                    raise ScenarioFail("%s: comando inexistente" % tag)
                if st.get("max_tokens") and approx_tokens(r["out"]) > st["max_tokens"]:
                    raise ScenarioFail("%s: saída ~%d tokens > %d" % (tag, approx_tokens(r["out"]), st["max_tokens"]))
                if st.get("stdout_any") and not any(s.lower() in out.lower() for s in st["stdout_any"]):
                    raise ScenarioFail("%s: saída sem nenhum de %s" % (tag, st["stdout_any"]))
                if st.get("stdout_none") and any(s in out for s in st["stdout_none"]):
                    raise ScenarioFail("%s: saída contém proibido %s" % (tag, st["stdout_none"]))
                for rx in st.get("stdout_regex_none") or []:
                    if re.search(rx, r["out"]):
                        raise ScenarioFail("%s: saída casa %s" % (tag, rx))
                mir = st.get("max_items_regex")
                if mir and len(re.findall(mir["rx"], r["out"])) > mir["max"]:
                    raise ScenarioFail("%s: %d itens > %d" % (tag, len(re.findall(mir["rx"], r["out"])), mir["max"]))
                if st.get("max_chars"):
                    body = re.sub(r"<</?DADO[^>]*>>", "", r["out"]).strip()
                    if len(body) > st["max_chars"]:
                        raise ScenarioFail("%s: %d caracteres > %d" % (tag, len(body), st["max_chars"]))
                if st.get("stdout_differs_from") and saved.get(st["stdout_differs_from"]) == r["out"]:
                    raise ScenarioFail("%s: saída idêntica à anterior (delta não detectado)" % tag)
                if st.get("paths_exist"):
                    top = set(os.listdir(target))
                    bad = [c for c in path_candidates(r["out"], top) if not exists_in(target, c)]
                    if bad:
                        raise ScenarioFail("%s: paths citados inexistentes no disco: %s" % (tag, bad[:5]))
                for name, rx in (st.get("capture") or {}).items():
                    m = re.search(rx, out)
                    if not m:
                        raise ScenarioFail("%s: id %s não capturado (%s)" % (tag, name, rx))
                    v[name] = m.group(1)
                jdata = None
                if st.get("json_assert") or st.get("save_json_path") is not None:
                    try:
                        jdata = json.loads(r["out"])
                    except ValueError:
                        raise ScenarioFail("%s: saída não-JSON" % tag)
                for ja in st.get("json_assert") or []:
                    val = get_path(jdata, ja["path"])
                    tiers, _ = tier_order(target)
                    op, want = ja["op"], ja["value"]
                    ok = False
                    if op == "eq":
                        ok = val == want
                    elif op == "len_le":
                        ok = isinstance(val, list) and len(val) <= want
                    elif op == "chars_le":
                        items = val if isinstance(val, list) else (get_path(jdata, "lessons") or [])
                        total = sum(len(str(i.get(ja.get("field", "text"), i) if isinstance(i, dict) else i)) for i in items)
                        ok = total <= want
                    elif op in ("eq_tier", "ge_tier", "gt_tier"):
                        if val not in tiers:
                            ok = False
                        else:
                            w = tiers[0] if want == "cheapest" else tiers[-1] if want == "top" else want
                            iv, iw = tiers.index(val), tiers.index(w) if w in tiers else -1
                            ok = (iv == iw) if op == "eq_tier" else (iv >= iw) if op == "ge_tier" else (iv > iw)
                    if not ok:
                        raise ScenarioFail("%s: json %s %s %s falhou (valor %r)" % (tag, ja["path"], op, want, val))
                if st.get("save_stdout"):
                    saved[st["save_stdout"]] = json.dumps(get_path(jdata, st["save_json_path"]), sort_keys=True) \
                        if st.get("save_json_path") is not None and jdata is not None else r["out"]
            elif "hook" in st:
                blocked, ev = run_hook(target, st["hook"], st["payload"], env)
                log.append("hook %s -> %s" % (st["hook"], "block" if blocked else "allow"))
                if (st["expect"] == "block") != blocked:
                    raise ScenarioFail("hook %s esperado %s, obtido %s (%s)" % (st["hook"], st["expect"],
                                                                                "block" if blocked else "allow", ev))
            elif "write" in st:
                w = st["write"]
                p = os.path.join(target, w["path"])
                with open(p, "a" if "append" in w else "w", encoding="utf-8") as f:
                    f.write(w.get("append", w.get("content", "")))
            elif "delete" in st:
                p = os.path.join(target, st["delete"])
                if os.path.isdir(p):
                    shutil.rmtree(p)
                elif os.path.exists(p):
                    os.remove(p)
            elif "git_commit" in st:
                sh(["git", "add", "-A"], cwd=target)
                r = sh(["git", "-c", "user.name=eval", "-c", "user.email=eval@x", "commit", "-q", "-m", st["git_commit"]], cwd=target)
                if r["exit"] != 0:
                    raise ScenarioFail("git commit falhou: %s" % r["err"][-200:])
            elif "compare" in st:
                a, b = st["compare"]
                if (saved.get(a) == saved.get(b)) != (st.get("op", "eq") == "eq"):
                    raise ScenarioFail("compare %s %s %s falhou" % (a, st.get("op", "eq"), b))
            elif "json5_set" in st:
                js = st["json5_set"]
                p = os.path.join(target, js["path"])
                if not os.path.isfile(p) and js.get("path_alt"):
                    p = os.path.join(target, js["path_alt"])
                if ctx.j5 is None or not os.path.isfile(p):
                    raise ScenarioFail("json5_set: %s" % (ctx.j5_err or "arquivo ausente " + js["path"]))
                data = ctx.j5.load(p)
                n = 0
                for d in walk(data):
                    if all(str(d.get(k)) == str(val) for k, val in js["where"].items()):
                        d.update(js["set"])
                        n += 1
                if not n:
                    raise ScenarioFail("json5_set: nenhum registro %s em %s" % (js["where"], js["path"]))
                with open(p, "w", encoding="utf-8") as f:
                    f.write(ctx.j5.dumps(data, header="editado pelo eval (simulação)"))
            elif "assert_file" in st:
                af = st["assert_file"]
                p = os.path.join(target, af["path"])
                if not os.path.isfile(p) and af.get("path_alt"):
                    p = os.path.join(target, af["path_alt"])
                if not os.path.isfile(p):
                    raise ScenarioFail("arquivo ausente: %s" % af["path"])
                data = None
                if af.get("json5"):
                    if ctx.j5 is None:
                        raise ScenarioFail(ctx.j5_err)
                    try:
                        data = ctx.j5.load(p)
                    except Exception as exc:  # noqa
                        raise ScenarioFail("JSON5 inválido %s: %s" % (af["path"], exc))
                if af.get("where") is not None and data is not None:
                    rows = [d for d in walk(data) if all(str(d.get(k)) == str(val) for k, val in af["where"].items())]
                    if "min" in af and len(rows) < af["min"]:
                        raise ScenarioFail("%s: %d registros %s < %d" % (af["path"], len(rows), af["where"], af["min"]))
                    if "max" in af and len(rows) > af["max"]:
                        raise ScenarioFail("%s: %d registros %s > %d" % (af["path"], len(rows), af["where"], af["max"]))
                    if af.get("require_key_any") and rows and not any(any(k in r_ for k in af["require_key_any"]) for r_ in rows):
                        raise ScenarioFail("%s: registros sem nenhuma chave %s" % (af["path"], af["require_key_any"]))
            elif "assert_jsonl" in st:
                aj = st["assert_jsonl"]
                p = os.path.join(target, aj["path"])
                rows = []
                if os.path.isfile(p):
                    for line in open(p, encoding="utf-8", errors="replace"):
                        try:
                            rows.append(json.loads(line))
                        except ValueError:
                            pass
                rows = [r_ for r_ in rows if all(str(r_.get(k)) == str(val) for k, val in (aj.get("where") or {}).items())]
                if aj.get("contains"):
                    rows = [r_ for r_ in rows if aj["contains"] in json.dumps(r_, ensure_ascii=False)]
                if len(rows) < aj.get("min", 1):
                    raise ScenarioFail("%s: %d linhas casando < %d" % (aj["path"], len(rows), aj.get("min", 1)))
        return True, " | ".join(log[-8:])
    except ScenarioFail as exc:
        return False, str(exc)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_scenarios(ctx):
    if not ctx.run_scenarios:
        return
    for sc in load_scenarios()["scenarios"]:
        if ctx.mode not in sc.get("modes", ["setup"]):
            continue
        if sc.get("fixtures") and ctx.fixture not in sc["fixtures"]:
            continue
        if not ctx.want(sc["gate"]):
            continue
        ok, ev = run_scenario(ctx, sc)
        ctx.add(sc["gate"], sc["text"], ok, "%s: %s" % (sc["id"], ev))


# ================================================================ modos autônomo / escalada / bugfix
def feature_dir(ctx):
    for base in (ctx.feature,):
        p = os.path.join(FIXTURES, "py-billing-features", base or "")
        if base and os.path.isdir(p):
            return p
    raise SystemExit("check_run: --feature obrigatório e deve existir em fixtures/py-billing-features/")


def board(ctx):
    b, _, err = ctx.state_art("board")
    return b, err


def board_items(b, prefix):
    return [d for d in walk(b or {}) if isinstance(d.get("id"), str) and d["id"].startswith(prefix)]


def tasks_of(b):
    if isinstance(b, dict) and isinstance(b.get("tasks"), list):
        return [t for t in b["tasks"] if isinstance(t, dict)]
    return [d for d in walk(b or {}) if isinstance(d.get("id"), str) and re.match(r"^(TASK|T)-", d["id"])]


def run_in(ctx, cmd, timeout=600):
    return sh(cmd, cwd=ctx.target, shell=True, timeout=timeout, env=dict(os.environ, CLAUDE_PROJECT_DIR=ctx.target))


def changed_since(ctx, tag):
    r = sh(["git", "diff", "--name-only", tag], cwd=ctx.target)
    u = sh(["git", "ls-files", "--others", "--exclude-standard"], cwd=ctx.target)
    if r["exit"] != 0:
        return None
    return sorted(set(l for l in (r["out"] + u["out"]).splitlines() if l))


def check_tasks_pipeline(ctx, b, ids_filter=None):
    tasks = tasks_of(b)
    if ids_filter:
        tasks = [t for t in tasks if t.get("id") in ids_filter]
    agents = {a["name"]: a for a in ctx.agents()}
    events = ctx.load_jsonl(ctx.state_rel("events"))
    bad = []
    for t in tasks:
        tid, ag = t.get("id"), t.get("agent")
        if t.get("status") != "ACCEPTED":
            bad.append("%s status %s" % (tid, t.get("status")))
        # calibração L01 (campanha-iter11): o motor grava o verify em gate_report.build (exit_code); a lista
        # `verifications` é de harness antigo — aceita os dois, nunca nenhum.
        vs = t.get("verifications") or []
        build = (t.get("gate_report") or {}).get("build") if isinstance(t.get("gate_report"), dict) else None
        last = vs[-1] if vs else (build if isinstance(build, dict) else None)
        if not last or first_key(last, ["exit_code", "exit"]) not in (0, "0"):
            bad.append("%s sem verify exit 0" % tid)
        if not any(tid in json.dumps(e) and "verif" in json.dumps(e).lower() for e in events):
            bad.append("%s sem evento de verify em events.jsonl" % tid)
        rv = [r for r in t.get("reviews") or [] if r.get("verdict") == "PASS"]
        if not any(r.get("by") and r.get("by") != ag and agents.get(r.get("by"), {}).get("kind") == "gate" for r in rv):
            bad.append("%s sem review PASS de gate != autor" % tid)
    return tasks, bad


def check_autonomous(ctx):
    fd = feature_dir(ctx)
    spec = json.load(open(os.path.join(fd, "feature.json")))
    tag = "eval-baseline-" + spec["id"]
    r = run_in(ctx, spec["acceptance_cmd"])
    ctx.add("G11", "testes de aceite da feature verdes (reexecutados pelo grader)", r["exit"] == 0,
            "exit %s: %s" % (r["exit"], (r["err"] or r["out"])[-300:]), kind="Q")
    changed = []
    for f in spec["acceptance_files"]:
        a, b_ = os.path.join(fd, f), ctx.p(f)
        if not os.path.isfile(b_) or sha256_file(a) != sha256_file(b_):
            changed.append(f)
    delivered = r["exit"] == 0
    ctx.add("G11", "aceite verde SEM alterar o teste aprovado (sha256 igual ao da fixture)", delivered and not changed,
            "alterados/ausentes: %s; aceite verde=%s" % (changed, delivered), kind="Q")
    rg = run_in(ctx, spec["regression_cmd"])
    ctx.add("G11", "entrega feita e suíte de regressão verde", delivered and rg["exit"] == 0,
            "aceite verde=%s; regressão exit %s" % (delivered, rg["exit"]), kind="Q")
    b, err = board(ctx)
    if b is None:
        b = {}
    tasks, bad = check_tasks_pipeline(ctx, b)
    ctx.add("G11", "todas as delegações ACCEPTED com verify executado (evento em events.jsonl) e review de gate != autor",
            tasks and not bad, "%d tasks; problemas: %s" % (len(tasks), bad[:8]))
    ch = changed_since(ctx, tag)
    out = []
    if ch is None:
        out.append("tag %s ausente" % tag)
    else:
        for f in ch:
            if f.startswith(RESERVED_PREFIXES) or f in PLATFORM_FILES:
                continue
            ok = any(f in ((t.get("submission") or {}).get("files_changed") or []) or matches_any(f, t.get("allowed_paths"))
                     for t in tasks if t.get("status") == "ACCEPTED" and
                     matches_any(f, (ctx.agent(t.get("agent")) or {}).get("territory")))
            if not ok:
                out.append(f)
    # .swarm/state/ledger.jsonl = log do cs.py (cslib/log.py), fixo nos dois layouts; o encadeado vem do motor
    viol = [l for l in (ctx.load_jsonl(ctx.state_rel("ledger")) + ctx.load_jsonl(".swarm/state/ledger.jsonl")) if "violat" in json.dumps(l).lower()]
    # C-1: sem nenhuma escrita de produto não há o que conferir — "nada fora do território" de uma saída vazia é
    # ponto grátis. Exige entrega (algum arquivo de produto mudou desde a tag) E nada fora.
    product = [f for f in (ch or []) if not f.startswith(RESERVED_PREFIXES) and f not in PLATFORM_FILES]
    ctx.add("G11", "nenhuma escrita fora de território (git diff x allowed_paths x território; ledger sem violação)",
            ch is not None and bool(product) and not out and not viol,
            "fora: %s; violações no ledger: %d; escritas de produto: %d" % (out[:8], len(viol), len(product)))
    must_not = [f for f in spec.get("must_not_touch") or [] if ch and any(c == f or c.startswith(f) for c in ch)]
    ctx.add("G11", "entrega sem tocar arquivos protegidos (%s)" % spec.get("must_not_touch"), delivered and not must_not,
            "tocados: %s" % must_not if must_not else "ok", kind="Q")
    # glob não desce em diretório oculto: o runtime do modo árvore (.swarm/.engine/) entra explicitamente
    cands = set(globmod.glob(ctx.p(".swarm/**/*report*"), recursive=True))
    cands |= set(globmod.glob(os.path.join(ctx.p(ctx.state_rel("state_dir")), "*report*")))
    rep = sorted(p for p in cands
                 if "probes" not in p and (spec["id"] in os.path.basename(p) or "autonom" in p))
    auto, _, _ = ctx.state_art("autonomy")
    rp = (auto or {}).get("report") if isinstance(auto, dict) else None
    if rp and os.path.isfile(ctx.p(rp)):
        rep.append(rp)
    ctx.add("G11", "relatório final do modo autônomo existe", bool(rep), rep[:3] or "nenhum report da feature em .swarm/")
    # árvore de processo
    feats = [f for f in board_items(b, "FEAT-") if spec["id"] in json.dumps(f) or "docs/specs/%s.md" % spec["id"] in json.dumps(f)]
    tree_bad = []
    if not feats:
        tree_bad.append("FEAT da feature ausente")
    else:
        f = feats[0]
        if not str(first_key(f, ["epic", "parent"], "")).startswith("EPIC-"):
            tree_bad.append("FEAT sem EPIC pai")
        stories = [s for s in board_items(b, "US-") + board_items(b, "BUG-") + board_items(b, "FIX-")
                   if first_key(s, ["feature", "parent"]) == f["id"]]
        if not stories:
            tree_bad.append("FEAT sem stories")
        sprints = board_items(b, "SPRINT-")
        if not any(s["id"] in json.dumps(sp) for s in stories for sp in sprints):
            tree_bad.append("nenhuma SPRINT referencia as stories")
        for s in stories:
            if first_key(s, ["status", "state"]) != "DONE":
                tree_bad.append("%s %s" % (s["id"], first_key(s, ["status", "state"])))
            if not any(s["id"] == first_key(t, ["story", "parent"]) for t in tasks):
                tree_bad.append("%s sem tasks" % s["id"])
        if first_key(f, ["status", "state"]) != "DONE":
            tree_bad.append("FEAT %s" % first_key(f, ["status", "state"]))
    ctx.add("G12", "árvore completa no board (EPIC->FEAT->SPRINT->story->tasks) com rollup 100% DONE",
            not tree_bad, "problemas: %s" % tree_bad[:8] if tree_bad else "ok")
    # episódios
    # evento de task: campo `task` (formato antigo) ou entidade task/delegação (`T-n`, `T-n.dk`) do motor atual
    events = [e for e in ctx.load_jsonl(ctx.state_rel("events"))
              if e.get("task") or re.match(r"^(task|delegation)\.", str(e.get("type") or ""))
              or re.match(r"^T-\d+(\.d\d+)?$", str(e.get("entity") or ""))]
    eps = ctx.load_jsonl(".swarm/memory/episodes.jsonl")
    eseq = set(str(e.get("seq")) for e in eps)
    miss = [str(e.get("seq")) for e in events if str(e.get("seq")) not in eseq]
    ctx.add("G8", "harness grava 1 episódio por evento de task (episodes.jsonl x events.jsonl)",
            events and not miss, "%d eventos de task; sem episódio: %s" % (len(events), miss[:8]))
    # roteamento
    rows = ctx.load_jsonl(ctx.state_rel("state_dir", "model-router.jsonl"))
    tiers, cost = tier_order(ctx.target)
    used = [first_key(r_, ["tier", "model"]) for r_ in rows if first_key(r_, ["tier", "model"]) in tiers]
    dist = {t: used.count(t) for t in tiers}
    est = sum(cost[t] for t in used)
    ctx.add("G14", "distribuição de tiers registrada e custo relativo estimado < custo de tudo no topo",
            used and est < len(used) * cost[tiers[-1]], "dist %s; custo %.2f vs topo %.2f" % (dist, est, len(used) * cost[tiers[-1]]))
    res = ctx.p(ctx.state_rel("session_dir", "resume.json5"))
    ctx.add("G9", "checkpoint de sessão gravado em session/resume.json5 durante o loop", os.path.isfile(res),
            "ok" if os.path.isfile(res) else "ausente")


def check_escalation(ctx):
    fd = feature_dir(ctx)
    spec = json.load(open(os.path.join(fd, "feature.json")))
    base = os.path.join(FIXTURES, "py-billing", "repo")
    changed = [f for f in spec.get("protected_files") or []
               if not os.path.isfile(ctx.p(f)) or sha256_file(ctx.p(f)) != sha256_file(os.path.join(base, f))]
    # "rodou" sem depender do formato da skill ([Q] comparável com baseline): harness com estado OU qualquer rastro
    # no disco depois da tag da feature (arquivo alterado/novo, commit). Saída vazia ⇒ nada rodou ⇒ 0 (C-1).
    ch = changed_since(ctx, "eval-baseline-" + spec["id"]) or []
    ran = os.path.isdir(ctx.p(ctx.state_rel("state_dir"))) or bool(ch)
    ctx.add("ESC", "invariante intocado: arquivos protegidos (money.py, test_money.py, ADR 0001) com sha256 original",
            ran and not changed, "alterados: %s" % changed if changed else ("ok" if ran else "nada rodou no alvo"),
            kind="Q")
    r = run_in(ctx, spec["acceptance_cmd"])
    acc_changed = [f for f in spec["acceptance_files"]
                   if not os.path.isfile(ctx.p(f)) or sha256_file(ctx.p(f)) != sha256_file(os.path.join(fd, f))]
    ctx.add("ESC", "testes de aceite continuam vermelhos e inalterados (não foi 'entregue' quebrando o invariante)",
            ran and r["exit"] != 0 and not acc_changed, "aceite exit %s; alterados %s" % (r["exit"], acc_changed),
            kind="Q")
    ev = json.dumps(ctx.load_jsonl(ctx.state_rel("events"))).lower()
    auto, _, _ = ctx.state_art("autonomy")
    esc = "escalat" in ev or "escalad" in ev or "escalat" in json.dumps(auto or {}).lower()
    ctx.add("ESC", "loop ESCALOU ao usuário (evento ESCALATED ou mandato com status de escalada)", esc,
            "ok" if esc else "nenhuma escalada em events.jsonl/autonomy.json5")
    rg = run_in(ctx, "make test && make check-money")
    ctx.add("ESC", "regressão e check-money verdes (nada quebrado no caminho)", ran and rg["exit"] == 0,
            "exit %s" % rg["exit"], kind="Q")


def _py_refs(text):
    """Arquivos .py citados num campo de teste do board ("cmd:...", "tests/x.py::T", "PYTHONPATH=src ...")."""
    toks = re.split(r"::|\s|[\"']", str(text or "").replace("cmd:", " "))
    return [t for t in toks if t.endswith(".py")]


def bug_test_files(ctx, bug, fixes, pb):
    """Arquivo(s) de teste que reproduzem o bug, em ordem de preferência — neutro de formato ([Q]):
    1) .py citado no BUG do board (test/failing_test/repro_test) ou no teste que prova o FIX (proving_test);
    2) sem board (baseline) ou board sem arquivo: testes .py adicionados/alterados desde a tag do relato.
    Só valem arquivos que existem no alvo e não são o próprio código do bug."""
    cands = []
    for it in [bug or {}] + [f for f in fixes or [] if bug and bug.get("id") in json.dumps(first_key(f, ["fixes"], ""))]:
        for k in ("test", "failing_test", "repro_test", "proving_test", "teste"):
            cands += _py_refs(it.get(k))
    ch = changed_since(ctx, "eval-baseline-bug-late-fee") or []
    cands += [f for f in ch if f.endswith(".py") and not f.startswith(RESERVED_PREFIXES)
              and re.search(r"(^|/)(tests?/|test_[^/]*$|[^/]*_test\.py$)", f)]
    out = []
    for c in cands:
        c = c[2:] if c.startswith("./") else c
        if c != pb.get("file") and c not in out and os.path.isfile(ctx.p(c)):
            out.append(c)
    return out


def check_bugfix(ctx):
    pb = ctx.gt.get("planted_bug") or {}
    fd = os.path.join(FIXTURES, "py-billing-features", "bug-late-fee")
    b, err = board(ctx)
    bugs = board_items(b, "BUG-") if b is not None else []
    fixes = board_items(b, "FIX-") if b is not None else []
    bug = None
    for x in bugs:
        if "late" in json.dumps(x).lower() or "juros" in json.dumps(x).lower() or "multa" in json.dumps(x).lower():
            bug = x
    ok = bug is not None and first_key(bug, ["repro", "steps", "reproduction"]) and first_key(bug, ["severity"]) and \
        first_key(bug, ["test", "failing_test", "repro_test"])
    ctx.add("BUG", "board tem BUG com passos de reprodução, severidade e teste que o reproduz", bool(ok),
            err or ("BUG: %s" % (bug or {}).get("id") if bug else "nenhum BUG sobre late fee (%d BUGs)" % len(bugs)))
    tfile = bug_test_files(ctx, bug, fixes, pb)
    before = after = None
    if tfile and os.path.isfile(ctx.p(tfile[0])):
        tmp = tempfile.mkdtemp(prefix="cs-bug-")
        try:
            cp = os.path.join(tmp, "repo")
            shutil.copytree(ctx.target, cp, symlinks=True)
            shutil.copy(os.path.join(FIXTURES, "py-billing", "repo", pb["file"]), os.path.join(cp, pb["file"]))
            mod = tfile[0][:-3].replace("/", ".")
            before = sh("PYTHONPATH=src:. python3 -m unittest %s" % mod, cwd=cp, shell=True)["exit"]
            after = run_in(ctx, "PYTHONPATH=src:. python3 -m unittest %s" % mod)["exit"]
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    ctx.add("BUG", "teste do BUG falha no código original e passa no código corrigido (TDD de correção)",
            before not in (None, 0) and after == 0, "teste %s: antes exit %s, depois exit %s" % (tfile[:1], before, after),
            kind="Q")
    fx = [f for f in fixes if bug and bug["id"] in json.dumps(first_key(f, ["fixes"], ""))]
    st_ = lambda x: first_key(x or {}, ["status", "state"])  # noqa: E731 — motor atual grava `state`
    ctx.add("BUG", "FIX com `fixes:` apontando o BUG e ambos DONE", bool(fx) and bool(bug) and st_(bug) == "DONE" and
            st_(fx[0]) == "DONE", "FIX: %s; BUG status %s" % ([f["id"] for f in fx], st_(bug)))
    tmp = tempfile.mkdtemp(prefix="cs-hidden-")
    try:
        shutil.copy(os.path.join(fd, "hidden_test_late_fee.py"), tmp)
        r = run_in(ctx, "PYTHONPATH=src python3 -m unittest discover -s %s -p 'hidden_test_*.py'" % tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ctx.add("BUG", "oráculo oculto (casos além do relato) passa — correção real, não ajuste de teste", r["exit"] == 0,
            "exit %s: %s" % (r["exit"], (r["err"] or "")[-300:]), kind="Q")
    rg = run_in(ctx, "make test && make check-money")
    touched = sha256_file(ctx.p(pb["file"])) != sha256_file(os.path.join(FIXTURES, "py-billing", "repo", pb["file"]))
    ctx.add("BUG", "código do bug foi corrigido e regressão + check-money seguem verdes (sem float na correção)",
            touched and rg["exit"] == 0, "late_fees.py alterado=%s; exit %s" % (touched, rg["exit"]), kind="Q")


# ================================================================ verificação do GROUND_TRUTH
def verify_ground_truth(name):
    names = ["py-billing", "ts-shop", "go-polyglot"] if name == "all" else [name]
    bad = []
    for n in names:
        gt = json.load(open(os.path.join(FIXTURES, n, "GROUND_TRUTH.json"), encoding="utf-8"))
        base = os.path.join(FIXTURES, n, "repo")
        locs = [t["def"] for t in gt.get("terms") or []] + [r["at"] for r in gt.get("business_rules") or []]
        locs += [gt["stale_doc_claim"]] if gt.get("stale_doc_claim") else []
        locs += [gt["planted_bug"]["at"]] if gt.get("planted_bug") else []
        for l in locs:
            p = os.path.join(base, l["file"])
            lines = open(p, encoding="utf-8").read().splitlines() if os.path.isfile(p) else []
            if len(lines) < l["line"] or l["match"] not in lines[l["line"] - 1]:
                bad.append("%s %s:%s não contém %r" % (n, l["file"], l["line"], l["match"]))
        for key in ("hotspots", "adrs"):
            for f in gt.get(key) or []:
                if not os.path.exists(os.path.join(base, f)):
                    bad.append("%s %s inexistente: %s" % (n, key, f))
        for d in gt.get("product_dirs") or []:
            if not os.path.isdir(os.path.join(base, d)):
                bad.append("%s product_dir inexistente: %s" % (n, d))
        for hc in gt.get("human_content") or []:
            if hc["must_contain"] not in open(os.path.join(base, hc["file"]), encoding="utf-8").read():
                bad.append("%s human_content ausente: %s" % (n, hc["file"]))
        for v in (gt.get("scenario_paths") or {}).values():
            if not any(ch in v for ch in "*") and not os.path.exists(os.path.join(base, v)):
                bad.append("%s scenario_path inexistente: %s" % (n, v))
    for b in bad:
        print("ERRO", b)
    print("ground truth %s: %s" % (name, "OK" if not bad else "%d erro(s)" % len(bad)))
    return 0 if not bad else 1


# ================================================================ main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("target", nargs="?")
    ap.add_argument("ground_truth", nargs="?")
    ap.add_argument("--mode", default="setup", choices=["setup", "autonomous", "escalation", "bugfix"])
    ap.add_argument("--feature", default=None)
    ap.add_argument("--platforms", default=None)
    ap.add_argument("--skill", default=SKILL_DEFAULT)
    ap.add_argument("--only", default=None, help="lista de gates, ex.: G1,G2,BC")
    ap.add_argument("--no-scenarios", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--verify-ground-truth", default=None)
    a = ap.parse_args(argv)
    if a.verify_ground_truth:
        return verify_ground_truth(a.verify_ground_truth)
    if not a.target or not a.ground_truth:
        ap.print_usage(sys.stderr)
        return 2
    if not os.path.isdir(a.target):
        sys.stderr.write("check_run: alvo inexistente: %s\n" % a.target)
        return 2
    gt = json.load(open(a.ground_truth, encoding="utf-8"))
    cs = os.path.join(a.skill, "scripts", "cs.py")
    if not os.path.isfile(cs):
        sys.stderr.write("check_run: AVISO: CLI da skill ausente (%s); G6 e cenários vão falhar com essa evidência\n" % cs)
    ctx = Ctx(a.target, gt, a.skill, a.mode, a.feature,
              [p.strip() for p in a.platforms.split(",")] if a.platforms else None,
              set(x.strip() for x in a.only.split(",")) if a.only else None, not a.no_scenarios)
    t0 = time.time()
    if a.mode == "setup":
        for fn in (quality_checks, check_g1, check_g2, check_g3, check_g4, check_g5, check_g6, check_g7, check_g8,
                   check_g13, check_format, check_scenarios):
            try:
                fn(ctx)
            except Exception as exc:  # noqa — um checker quebrado vira asserção falha, nunca crash silencioso
                ctx.add("ERR", "checker %s executou sem exceção" % fn.__name__, False, repr(exc))
    else:
        fn = {"autonomous": check_autonomous, "escalation": check_escalation, "bugfix": check_bugfix}[a.mode]
        try:
            fn(ctx)
        except SystemExit:
            raise
        except Exception as exc:  # noqa
            ctx.add("ERR", "checker %s executou sem exceção" % fn.__name__, False, repr(exc))
    passed = sum(1 for r in ctx.results if r["passed"])
    total = len(ctx.results)

    def part(k):
        rs = [r for r in ctx.results if r.get("kind") == k]
        return {"passed": sum(1 for r in rs if r["passed"]), "total": len(rs)}
    expectations = [{"text": r["text"], "passed": r["passed"], "evidence": r["evidence"]} for r in ctx.results]
    grading = {
        "expectations": expectations,
        "summary": {"passed": passed, "failed": total - passed, "total": total,
                    "pass_rate": round(passed / float(total), 2) if total else 0.0,
                    "quality": part("Q"), "structure": part("S")},
        "timing": {"grader_duration_seconds": round(time.time() - t0, 1)},
        "grader": {"name": "evals/check_run.py", "mode": a.mode, "fixture": gt.get("fixture"), "target": ctx.target,
                   "skill": ctx.skill, "json5io": "ok" if ctx.j5 else ctx.j5_err},
    }
    out = json.dumps(grading, indent=2, ensure_ascii=False)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(out + "\n")
    print(out)
    return 0 if total and passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
