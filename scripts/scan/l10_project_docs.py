"""L10 docs do projeto (§8-nonies) → facts/project_docs.json5.

Fontes: README*, docs/**, ADRs, CONTRIBUTING*, CHANGELOG*, runbooks, e instruções de agente
preexistentes (CLAUDE.md, AGENTS.md, .cursor/rules/**, .cursorrules, .github/copilot-instructions.md,
.github/instructions/**). Fixtures/vendor/gerados ficam de fora (como em todo o scan).

Cada afirmação VERIFICÁVEL é conferida contra o repo:
- comando citado (bloco de código ou `inline`): alvo de make / script npm / arquivo executado existem?
  se o comando está em operations (L7), herda o status (verified/failed/declared);
- caminho citado (`inline` ou link relativo): existe como arquivo ou pasta?
- versão citada ("Python 3.11", "react 18.2"): bate com lockfile (L8) / runtime declarado?
Status: `verified` (confere), `stale` (diverge; a divergência é anotada) ou `unverifiable`.
Doc velho nunca é repetido como verdade: o fato de uma afirmação `stale` diz o que o repo mostra.
"""

import posixpath
import re

from cslib import workspaces
from cslib.evidence import ev_cmd, ev_file, slug
from . import commands as cmdx
from . import l6_rationale
from . import toolcheck
from . import yamlmini

LAYER = "project_docs"
INSTR_FACTS = 80  # instruções de agente por arquivo que viram fato (o resto vira um fato "omitted")

AGENT_FILES = ("CLAUDE.md", "AGENTS.md", ".cursorrules", ".github/copilot-instructions.md",
               "GEMINI.md", ".windsurfrules")
AGENT_PREFIXES = (".cursor/rules/", ".github/instructions/", ".claude/rules/")
TOOLS = ("make", "npm", "npx", "yarn", "pnpm", "python", "python3", "pip", "pip3", "pytest", "uv",
         "poetry", "tox", "go", "cargo", "bash", "sh", "node", "deno", "bun", "just", "docker",
         "docker-compose", "dotnet", "mvn", "gradle", "./gradlew", "bundle", "rake", "rails",
         "composer", "php", "ruby", "ruff", "mypy", "eslint", "tsc", "jest", "vitest")
CODE_SPAN = re.compile(r"`([^`\n]{2,200})`")
MD_LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")
FENCE = re.compile(r"^\s*(```|~~~)\s*([\w+-]*)")
VERSION_CITE = re.compile(r"\b([A-Za-z][\w.@/+-]{1,40})\s+(?:v|version\s+|versão\s+|>=\s*|==\s*|\^|~)?"
                          r"(\d+\.\d+(?:\.\d+)?)\b")
RUNTIME_ALIASES = {"python": "python", "python3": "python", "node": "node", "node.js": "node",
                   "nodejs": "node", "go": "go", "golang": "go", "ruby": "ruby", "rust": "rust",
                   "java": "java", ".net": "dotnet", "dotnet": "dotnet", "php": "php"}
IMPERATIVE = re.compile(r"(?<!\w)(nunca|sempre|não\s+\w+|must|never|always|do not|don't|dont|should|"
                        r"deve|devem|precisa|precisam|proibido|obrigatório|only|apenas|somente|só\s+com|"
                        r"antes\s+de|before|after|depois\s+de|toda\s+mudança|todo\s+\w+|every|each|"
                        r"fale\s+com|talk\s+to|ask|pergunte|avise|consulte|check\s+with|without|sem\s+o|"
                        r"sem\s+a|prefer|prefira|use|usar|evite|avoid|require[sd]?|exige|needs?\s+to|"
                        r"rode|run|não\s+faça|nao\s+faca|make\s+sure|garanta)(?!\w)", re.I)
PATH_LIKE = re.compile(r"^(?:\./)?[\w.@-]+(?:/[\w.@*-]+)+/?$|^[\w.-]+\.(?:md|py|sh|js|ts|json|json5|ya?ml|"
                       r"toml|go|rs|rb|java|kt|cs|php|txt|cfg|ini|lock|mk)$")


def doc_kind(rel):
    base = rel.rsplit("/", 1)[-1]
    low = rel.lower()
    if rel in AGENT_FILES or base in ("CLAUDE.md", "AGENTS.md", "GEMINI.md") or \
            any(rel.startswith(p) for p in AGENT_PREFIXES):
        return "agent_instructions"
    if l6_rationale.is_adr(rel):
        return "adr"
    if base.lower().startswith("readme"):
        return "readme"
    if base.lower().startswith("contributing"):
        return "contributing"
    if base.lower().startswith(("changelog", "changes", "history")):
        return "changelog"
    if "runbook" in low or "playbook" in low or "/ops/" in low:
        return "runbook"
    if low.startswith("docs/") or low.startswith("doc/"):
        return "doc"
    return None


def is_project_doc(rel):
    if not (rel.lower().endswith((".md", ".mdc", ".rst", ".txt")) or rel in AGENT_FILES):
        return False
    return doc_kind(rel) is not None


class Checker(object):
    def __init__(self, ctx):
        self.ctx = ctx
        self.files = set(ctx.files) | set(ctx.all_files)
        self.dirs = set()
        self.by_base = {}
        for f in sorted(self.files):
            self.by_base.setdefault(f.rsplit("/", 1)[-1], []).append(f)
        for f in self.files:
            d = posixpath.dirname(f)
            while d:
                self.dirs.add(d)
                d = posixpath.dirname(d)
        ops = ctx.layer("L7")["commands"]
        self.ops = {c["cmd"]: c for c in ops}
        self.make_targets = {}
        self.npm_scripts = {}
        self.recipes = []  # (texto normalizado, origem) — receitas de make, corpos de script, linhas de CI
        # TODAS as declarações (antes do dedup do L7): `npm run lint` declarado no CI e no package.json
        # da raiz continua sendo um script do package.json.
        for c in cmdx.all_commands(ctx):
            if c.get("script"):
                self.recipes.append((" ".join(c["script"].split()), "script %s (%s:%d)" % (
                    c["name"], c["source"]["file"], c["source"]["line"])))
            if c["name"].startswith("make:"):
                self.make_targets.setdefault(c["source"]["file"], set()).add(c["name"][5:])
            elif ":" in c["name"] and c["name"].split(":", 1)[0] in ("npm", "yarn", "pnpm"):
                self.npm_scripts.setdefault(c["source"]["file"], set()).add(c["name"].split(":", 1)[1])
        # alvos de make sem receita também contam (ex.: agregadores)
        for mf in ctx.by_basename("Makefile", "makefile", "GNUmakefile"):
            lines = ctx.lines(mf)
            targets = toolcheck.make_targets(lines)
            variables = toolcheck.make_vars(lines)
            for t, info in targets.items():
                self.make_targets.setdefault(mf, set()).add(t)
                for ln_no, text in info["recipe"]:
                    self.recipes.append((" ".join(toolcheck.subst(text, variables).split()),
                                         "receita de `make %s` (%s:%d)" % (t, mf, ln_no)))
        self.workspaces = workspaces.discover(ctx.files, ctx.text)
        stack = ctx.layer("L8")["_outputs"]
        self.packages = {}
        for p in stack["stack"]["packages"]:
            self.packages.setdefault(p["name"].lower(), []).append(p)
        self.runtimes = {}
        for n in stack["stack_graph"]["nodes"]:
            if n["kind"] == "runtime":
                self.runtimes[n["id"].split(":", 1)[1]] = n.get("versions", [])

    def path_exists(self, doc, p):
        p = p.strip().rstrip("/")
        if not p or p.startswith(("http:", "https:", "mailto:", "#", "<", "~", "$")) or "*" in p or "{" in p:
            return None
        cands = [p.lstrip("./") if p.startswith("./") else p,
                 posixpath.normpath(posixpath.join(posixpath.dirname(doc), p))]
        for c in cands:
            if c in self.files or c in self.dirs:
                return True, c
        if "/" not in p.strip("./"):
            hits = self.by_base.get(p.strip("./"), [])
            if hits:
                return True, hits[0]
        elif not p.startswith(("/", "../")):
            # caminho relativo a um pacote/módulo (ex.: ADR cita `ledger/accounts.py` de src/billing/)
            suf = "/" + p.lstrip("./")
            hits = sorted(x for x in (self.files | self.dirs) if x.endswith(suf))
            if hits:
                return True, hits[0] + (" (por sufixo; %d candidatos)" % len(hits) if len(hits) > 1 else
                                        " (por sufixo)")
        return False, cands[0]

    def package_ref(self, ref):
        """`@scope/pkg[/sub]` é NOME de pacote, nunca caminho → (status, detalhe)."""
        name, sub = workspaces.split_spec(ref.rstrip("/"))
        ws = self.workspaces.get(name)
        if ws is not None:
            if not sub:
                return "verified", "pacote do workspace em %s" % (ws["dir"] or ".")
            hit = workspaces.resolve(self.workspaces, ref, self.files)
            if hit:
                return "verified", "subcaminho do workspace %s: %s" % (name, hit)
            return "unverifiable", "workspace %s existe; subcaminho '%s' não resolvido mecanicamente" % (name, sub)
        if name.lower() in self.packages:
            return "verified", "dependência declarada (%s)" % self.packages[name.lower()][0]["source"]
        return "unverifiable", "nome de pacote (não é workspace do repo nem dependência no lockfile)"

    def in_recipe(self, cmd):
        norm = " ".join(cmd.split())
        if len(norm) < 4:
            return None
        for text, origin in self.recipes:
            if norm == text or (" " in norm and norm in text):
                return origin
        return None

    def command(self, doc, cmd):
        """(status, detalhe) ou None se não é comando de ferramenta conhecida."""
        cmd = re.sub(r"\s+#.*$", "", cmd.strip().lstrip("$ ").strip())  # comentário de shell não é argumento
        if not cmd:
            return None
        argv0 = cmd.split()
        first = argv0[0]
        if first not in TOOLS and not first.startswith("./") and not first.endswith((".sh", ".py")):
            return None
        if len(argv0) == 1 and first not in TOOLS and not first.startswith("./"):
            return None  # caminho solto (`src/x.py`) é menção de caminho, não comando
        if cmd in self.ops:
            # a doc afirma que o comando EXISTE; execução que falha ou ferramenta ausente no ambiente do
            # scan não tornam a doc velha (o status de execução é fato de L7, não de L10)
            c = self.ops[cmd]
            run = c["status"]
            if run == "failed":
                run = "failed, exit %s" % c.get("exit")
            elif run == "unavailable":
                run = "unavailable: '%s' ausente no ambiente do scan" % c.get("missing_tool")
            return "verified", "presente em %s:%d (%s)" % (c["source"]["file"], c["source"]["line"], run)
        argv = cmd.split()
        if first == "make":
            d = ""
            rest = argv[1:]
            if len(rest) >= 2 and rest[0] == "-C":
                d, rest = rest[1].rstrip("/") + "/", rest[2:]
            tgts = [a for a in rest if not a.startswith("-") and "=" not in a]
            mf = next((d + n for n in ("Makefile", "makefile", "GNUmakefile") if d + n in self.files), None)
            if mf is None:
                return "stale", "não há Makefile em %s" % (d or "raiz")
            if not tgts:
                return "verified", "Makefile existe (%s)" % mf
            missing = [t for t in tgts if t not in self.make_targets.get(mf, set())]
            if missing:
                return "stale", "alvo(s) %s não existe(m) em %s" % (", ".join(missing), mf)
            return "verified", "alvo(s) %s em %s" % (", ".join(tgts), mf)
        if first in ("npm", "yarn", "pnpm") and len(argv) >= 2:
            if argv[1] in ("run", "run-script") and len(argv) >= 3:
                script = argv[2]
            elif argv[1] in ("test", "start") or (first != "npm" and argv[1] not in ("install", "add")):
                script = argv[1]
            else:
                return "unverifiable", "subcomando do gerenciador de pacotes"
            have = set().union(*self.npm_scripts.values()) if self.npm_scripts else set()
            if script in have:
                return "verified", "script '%s' existe em package.json" % script
            return "stale", "script '%s' não existe em nenhum package.json" % script
        # executa um arquivo do repo? (python x.py, bash x.sh, ./x.sh, python -m pkg.mod)
        for i, a in enumerate(argv):
            if a.endswith((".py", ".sh", ".js", ".ts", ".rb", ".bash")) and not a.startswith("-"):
                r = self.path_exists(doc, a)
                if r is None:
                    return "unverifiable", "caminho dinâmico"
                ok, p = r
                return ("verified", "arquivo %s existe" % p) if ok else ("stale", "arquivo %s não existe" % p)
            if a == "-m" and i + 1 < len(argv) and first.startswith("python"):
                mod = argv[i + 1]
                if mod in ("pytest", "unittest", "pip", "venv", "http.server", "json.tool"):
                    return "unverifiable", "módulo de ferramenta (%s)" % mod
                p = mod.replace(".", "/")
                if p + ".py" in self.files or p + "/__init__.py" in self.files or p + "/__main__.py" in self.files \
                        or any(f.endswith("/" + p + ".py") for f in self.files):
                    return "verified", "módulo %s existe" % mod
                return "stale", "módulo %s não encontrado no repo" % mod
        origin = self.in_recipe(cmd)
        if origin:
            return "verified", "corresponde à %s" % origin
        return "unverifiable", "ferramenta externa; nenhum artefato do repo citado"

    def version(self, name, ver):
        low = name.lower().rstrip(":")
        if low in RUNTIME_ALIASES:
            eco = RUNTIME_ALIASES[low]
            decl = self.runtimes.get(eco)
            if not decl:
                return None
            vs = [d["version"] for d in decl]
            if any(_ver_compatible(ver, v) for v in vs):
                return "verified", "runtime %s declarado: %s" % (eco, ", ".join(vs))
            return "stale", "doc cita %s %s; repo declara %s" % (name, ver, ", ".join(vs))
        pk = self.packages.get(low)
        if not pk:
            return None
        vs = sorted(set(p["version"] for p in pk))
        if any(v == ver or v.startswith(ver + ".") or v.lstrip("v") == ver for v in vs):
            return "verified", "lockfile: %s %s" % (name, ", ".join(vs))
        return "stale", "doc cita %s %s; lockfile tem %s (%s)" % (name, ver, ", ".join(vs), pk[0]["source"])


def _ver_compatible(cited, declared):
    """'3.11' vs '>=3.9' / '3.11.4' / '^18' etc. — compatível se o prefixo numérico casa ou satisfaz >=."""
    d = declared.strip()
    m = re.match(r"^\s*(>=|>|~=|\^|~|==)?\s*v?(\d+(?:\.\d+)*)", d)
    if not m:
        return False
    op, dv = m.group(1) or "==", m.group(2)
    c = [int(x) for x in cited.split(".")]
    dn = [int(x) for x in dv.split(".")]
    if op in (">=", ">", "~="):
        return c >= dn[:len(c)] if len(c) <= len(dn) else c[:len(dn)] >= dn
    n = min(len(c), len(dn))
    return c[:n] == dn[:n]


def extract_claims(ctx, rel, chk):
    lines = ctx.lines(rel)
    claims = []
    in_fence, lang = False, ""
    own = own_lines(lines)
    for i, ln in enumerate(lines, 1):
        if i in own:
            continue
        f = FENCE.match(ln)
        if f:
            in_fence = not in_fence
            lang = f.group(2).lower() if in_fence else ""
            continue
        if in_fence:
            if lang in ("", "bash", "sh", "shell", "console", "zsh", "make", "text"):
                r = chk.command(rel, ln)
                if r:
                    claims.append({"kind": "command", "line": i,
                                   "text": re.sub(r"\s+#.*$", "", ln.strip().lstrip("$ "))[:200],
                                   "status": r[0], "detail": r[1]})
            continue
        for m in CODE_SPAN.finditer(ln):
            span = m.group(1).strip()
            r = chk.command(rel, span)
            if r:
                claims.append({"kind": "command", "line": i, "text": span, "status": r[0], "detail": r[1]})
                continue
            if workspaces.looks_like_package_ref(span):
                st, det = chk.package_ref(span)
                claims.append({"kind": "package", "line": i, "text": span, "status": st, "detail": det})
                continue
            if PATH_LIKE.match(span) and " " not in span:
                pr = chk.path_exists(rel, span)
                if pr is not None:
                    claims.append({"kind": "path", "line": i, "text": span,
                                   "status": "verified" if pr[0] else "stale",
                                   "detail": ("existe: %s" % pr[1]) if pr[0] else "não existe no repo: %s" % pr[1]})
        for m in MD_LINK.finditer(ln):
            target = m.group(1)
            if "://" in target:
                continue
            pr = chk.path_exists(rel, target)
            if pr is not None:
                claims.append({"kind": "path", "line": i, "text": target,
                               "status": "verified" if pr[0] else "stale",
                               "detail": ("existe: %s" % pr[1]) if pr[0] else "link quebrado: %s" % pr[1]})
        for m in VERSION_CITE.finditer(ln):
            r = chk.version(m.group(1), m.group(2))
            if r:
                claims.append({"kind": "version", "line": i, "text": m.group(0), "status": r[0],
                               "detail": r[1]})
    return claims


def summarize(ctx, rel):
    lines = ctx.lines(rel)
    title = next((ln.lstrip("#").strip() for ln in lines if ln.startswith("#")), rel.rsplit("/", 1)[-1])
    para = []
    started = False
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith(("#", "```", "<!--", "|", "---", ">")):
            if started and para:
                break
            continue
        started = True
        para.append(s)
        if len(" ".join(para)) > 300:
            break
    return title[:160], " ".join(para)[:300]


OWN_GENERATED = "codebase-specialists:generated"
OWN_BEGIN, OWN_END = "<!-- codebase-specialists:begin -->", "<!-- codebase-specialists:end -->"
INSTR_MAX = 1200  # caracteres; acima disso o bloco não é citado (nunca cortado no meio de uma frase)


def _front_matter(lines):
    """(nº de linhas do front matter, globs declarados) — `globs` (.mdc do Cursor), `applyTo`
    (.instructions.md do Copilot), `paths` (.claude/rules). Front matter ilegível → sem globs."""
    if not lines or lines[0].strip() != "---":
        return 0, []
    for j in range(1, min(len(lines), 60)):
        if lines[j].strip() == "---":
            try:
                fm, _ = yamlmini.load("\n".join(lines[1:j]))
            except yamlmini.YamlError:
                return j + 1, []
            globs = []
            for k in ("globs", "applyTo", "paths"):
                v = fm.get(k) if isinstance(fm, dict) else None
                if isinstance(v, str):
                    v = v.split(",")
                if isinstance(v, list):
                    globs += [str(g).strip() for g in v if str(g).strip()]
            return j + 1, sorted(set(globs))
    return 0, []


def own_lines(lines):
    """Linhas (1-based) do bloco gerenciado pela própria skill (emit): não são do time; re-scan não se lê."""
    own, inside = set(), False
    for i, ln in enumerate(lines, 1):
        if OWN_BEGIN in ln:
            inside = True
        if inside:
            own.add(i)
        if OWN_END in ln:
            inside = False
    return own


def is_own_generated(ctx, rel):
    """Arquivo inteiro gerado pela própria skill (emit) — re-scan não lê a si mesmo."""
    lines = ctx.lines(rel)
    skip, _ = _front_matter(lines)
    if any(OWN_GENERATED in ln for ln in lines[:skip + 5]):
        return True
    own = own_lines(lines)
    return bool(own) and all(i in own for i, ln in enumerate(lines, 1) if ln.strip())


def instructions(ctx, rel):
    """TODA instrução de um arquivo de instruções de agente: cada bloco (item de lista com suas linhas
    de continuação, ou parágrafo) vira uma instrução com o texto inteiro — nunca a 1ª linha só (uma
    regra condicional cortada vira absoluta). `imperative` diz se o bloco é uma ordem (nunca, sempre,
    antes de, toda mudança, fale com, só com...) ou uma nota de contexto para o agente."""
    lines = ctx.lines(rel)
    skip, globs = _front_matter(lines)
    section = None
    heads = {}
    for i, ln in enumerate(lines):
        hm = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", ln)
        if hm:
            section = hm.group(1)
        heads[i + 1] = section
    own = own_lines(lines)
    out = []
    for b in l6_rationale.text_blocks(lines, skip, len(lines)):
        text = b["text"]
        if len(text) < 8 or b["line"] in own:
            continue
        out.append({"line": b["line"], "end_line": b["end_line"], "text": text,
                    "imperative": bool(IMPERATIVE.search(text)), "section": heads.get(b["line"]),
                    "complete": len(text) <= INSTR_MAX, "scope": globs})
    return out


def managed_blocks(ctx, rel):
    out = []
    lines = ctx.lines(rel)
    for i, ln in enumerate(lines, 1):
        if re.search(r"(BEGIN|>>>|INICIO|START)\b.*(managed|gerad|GENERATED|swarm|harness|bloco)", ln, re.I) \
                or re.search(r"<!--\s*(BEGIN|START)", ln):
            out.append({"line": i, "marker": ln.strip()[:120]})
    return out


def run(ctx):
    fb = ctx.fb
    chk = Checker(ctx)
    docs = []
    for rel in ctx.files:
        if not is_project_doc(rel) or ctx.is_binary(rel) or is_own_generated(ctx, rel):
            continue
        kind = doc_kind(rel)
        title, summary = summarize(ctx, rel)
        claims = extract_claims(ctx, rel, chk)
        d = {"file": rel, "kind": kind, "title": title, "summary": summary, "claims": claims,
             "counts": {s: sum(1 for c in claims if c["status"] == s)
                        for s in ("verified", "stale", "unverifiable")}}
        if kind == "agent_instructions":
            d["instructions"] = instructions(ctx, rel)
            d["managed_blocks"] = managed_blocks(ctx, rel)
        docs.append(d)
    facts = []
    prio = {"agent_instructions": 0, "readme": 1, "contributing": 2, "runbook": 3, "adr": 4,
            "changelog": 5, "doc": 6}
    for d in sorted(docs, key=lambda d: (prio[d["kind"]], d["file"]))[:150]:
        c = d["counts"]
        claim = "Doc (%s) %s — '%s'%s; afirmações verificáveis: %d verified, %d stale, %d não verificáveis" % (
            d["kind"], d["file"], d["title"], (": " + d["summary"][:200]) if d["summary"] else "",
            c["verified"], c["stale"], c["unverifiable"])
        facts.append(fb.fact("docs.%s" % slug(d["file"], 90), LAYER, claim, [ev_file(d["file"], 1)],
                             confidence="medium", scope=["**"]))
    n_stale = n_ver = 0
    for d in docs:
        for cl in d["claims"]:
            if cl["status"] == "stale" and n_stale < 300:
                n_stale += 1
                facts.append(fb.fact("docs.stale.%s.%d" % (slug(d["file"], 70), cl["line"]), LAYER,
                                     "STALE em %s:%d — doc diz `%s` (%s); repo: %s" % (
                                         d["file"], cl["line"], cl["text"][:120], cl["kind"], cl["detail"]),
                                     [ev_file(d["file"], cl["line"])], confidence="high", scope=["**"]))
            elif cl["status"] == "verified" and cl["kind"] in ("command", "version") and n_ver < 200:
                n_ver += 1
                facts.append(fb.fact("docs.verified.%s.%d" % (slug(d["file"], 70), cl["line"]), LAYER,
                                     "Conferido em %s:%d — `%s` (%s): %s" % (
                                         d["file"], cl["line"], cl["text"][:120], cl["kind"], cl["detail"]),
                                     [ev_file(d["file"], cl["line"])], confidence="high", scope=["**"]))
        instrs = d.get("instructions", [])
        for ins in instrs[:INSTR_FACTS]:
            where = "%s:%d" % (d["file"], ins["line"]) + (
                "-%d" % ins["end_line"] if ins["end_line"] != ins["line"] else "")
            what = "Instrução de agente preexistente" if ins["imperative"] else "Nota do time para agentes"
            if ins["complete"]:
                body = ins["text"]
            else:
                body = "(bloco de %d caracteres, longo demais para citar inteiro — leia %s)" % (
                    len(ins["text"]), where)
            sec = (" [seção: %s]" % ins["section"]) if ins["section"] else ""
            facts.append(fb.fact("docs.instr.%s.%d" % (slug(d["file"], 70), ins["line"]), LAYER,
                                 "%s (%s)%s: %s" % (what, where, sec, body),
                                 [ev_file(d["file"], ins["line"])],
                                 confidence="high" if ins["complete"] else "low",
                                 scope=ins["scope"] or ["**"],
                                 data={"kind": "agent_instruction", "imperative": ins["imperative"],
                                       "file": d["file"], "line": ins["line"], "end_line": ins["end_line"],
                                       "text": ins["text"] if ins["complete"] else None}))
        if len(instrs) > INSTR_FACTS:
            facts.append(fb.fact("docs.instr.%s.omitted" % slug(d["file"], 70), LAYER,
                                 "%s tem %d instruções; %d além das primeiras %d não viraram fato — leia o "
                                 "arquivo inteiro" % (d["file"], len(instrs), len(instrs) - INSTR_FACTS,
                                                      INSTR_FACTS),
                                 [ev_file(d["file"], instrs[INSTR_FACTS]["line"])], confidence="high",
                                 scope=["**"]))
    if not facts:
        facts.append(fb.fact("docs.none", LAYER,
                             "Nenhuma documentação de projeto (README, docs/, ADR, CONTRIBUTING, CHANGELOG, "
                             "runbook, instruções de agente) encontrada",
                             [ev_cmd("scan:L10 busca de docs", 1, b"")], confidence="high", scope=["**"]))
    totals = {s: sum(d["counts"][s] for d in docs) for s in ("verified", "stale", "unverifiable")}
    return {"layer": LAYER, "documents": docs, "totals": totals, "facts": facts}
