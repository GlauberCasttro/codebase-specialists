"""Classificador ÚNICO de referências em texto de cartão/core/painel (iteração 3, contrato `refs`).

kind ∈ {path, symbol, command, glob, package, prose}. Usado por `probes existence` (G2), `team core
from-panel`, `panel consolidate` e `probes anticola` — antes cada um tinha sua heurística e `//` (operador),
`Money.percent` (símbolo) ou `@shop/shared` (pacote) viravam "caminho inexistente".

  classify(token, backticked=True) → kind
  extract(text) → [(kind, value, line|None, marked)]   (determinístico, sem duplicata, em ordem)
  split_alternatives(token) → ["a", "b"] para `Money.percent/Money.allocate`, `go.mod/go.sum`

Regras (sintáticas; existência é decidida por quem chama):
  package  `@escopo/pacote` ou nome de pacote de workspace
  command  trecho com espaço iniciado por executável conhecido (`npm test`, `./scripts/x.sh a`)
  glob     contém `*`, `?` ou `[...]` e parece caminho
  path     tem `/` com segmentos de caminho, ou nome de arquivo com extensão conhecida, ou Makefile & cia.
  symbol   identificador com Maiúscula interna, `_`, `.membro` ou `()` (`Journal.post`, `charge_customer()`)
  prose    o resto: operadores (`//`, `->`), palavras, números, URLs, regex
Em texto SEM crase só path/glob com extensão conhecida (ou diretório terminado em `/`) contam.

forbidden  símbolo/comando entre crases logo depois de uma PROIBIÇÃO ("nunca use `pickle.load`", "never call
           `os.system` or `subprocess.call`", "proibido: `eval()`"): é o que NÃO deve existir, não uma afirmação de
           existência — `extract` devolve kind `forbidden` e G2 não o confere (iteração 3: "símbolo inexistente").
           Só vale quando entre a proibição e o token há apenas outros tokens entre crases e separadores
           ("nunca entregue sem `make test`" continua sendo comando a verificar).
"""
import re

EXECUTABLES = frozenset([
    "python", "python3", "pip", "pip3", "pytest", "tox", "nox", "uv", "poetry", "pdm", "hatch", "ruff",
    "mypy", "black", "flake8", "pylint", "npm", "npx", "yarn", "pnpm", "bun", "deno", "node", "tsc",
    "jest", "vitest", "eslint", "prettier", "make", "go", "cargo", "rustc", "mvn", "mvnw", "./mvnw",
    "gradle", "./gradlew", "gradlew", "dotnet", "ruby", "bundle", "rake", "rspec", "php", "composer",
    "phpunit", "mix", "elixir", "swift", "xcodebuild", "java", "javac", "docker", "docker-compose",
    "kubectl", "helm", "terraform", "bash", "sh", "git", "just", "task", "cmake", "ctest", "bazel",
    "sbt", "lein", "flutter", "dart", "cs.py", "cs-mem", "golangci-lint", "shellcheck", "psql", "sqlc",
    "buf", "protoc", "alembic", "django-admin", "manage.py", "./manage.py"])
FILE_NAMES = frozenset(["Makefile", "GNUmakefile", "Dockerfile", "Containerfile", "Jenkinsfile", "Procfile",
                        "Gemfile", "Rakefile", "Justfile", "Vagrantfile", "Taskfile.yml", "CODEOWNERS",
                        "LICENSE", "README"])
# extensões que fazem um token SEM crase (ou com crase e sem `/`) ser arquivo; `.percent`/`.allocate` não são
FILE_EXTS = frozenset("""
py pyi pyx ipynb js jsx mjs cjs ts tsx mts cts d.ts go mod sum rs java kt kts scala sc groovy gradle cs fs vb
rb erb rake php swift m mm c h cc cpp cxx hpp hh dart vue svelte astro ex exs erl hrl clj cljs edn lua pl pm
r sql prisma graphql gql proto thrift avsc sh bash zsh fish ps1 bat cmd mk cmake bazel bzl nix tf tfvars hcl
json json5 jsonc yaml yml toml ini cfg conf env properties xml xsd html htm css scss sass less styl md mdx rst
txt adoc csv tsv lock log pem crt key svg png jpg jpeg gif webp ico pdf wasm zip gz tar jar war dll so
dylib a o lockb mjs.map map snap feature tmpl tpl j2 jinja hbs mustache ejs pug liquid twig dockerfile
gitignore dockerignore editorconfig npmrc nvmrc tool-versions eslintrc prettierrc babelrc browserslistrc
""".split())
_IDENT = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*(?:\(\))?$")
_SCOPED = re.compile(r"^@[a-z0-9][\w.-]*/[a-z0-9][\w.-]*(?:/[\w./*-]*)?$", re.I)
_BACKTICK = re.compile(r"`([^`\n]+)`")
_BARE = re.compile(r"(?<![\w/.:@-])((?:[\w.*-]+/)+[\w.*-]*(?:\.[A-Za-z0-9]{1,8}|\*\*?|/)?)(?::(\d+))?")
_BARE_FILE = re.compile(r"(?<![\w/.:@`-])([\w-]+(?:\.[\w-]+)*\.([A-Za-z0-9]{1,8}))(?::(\d+))?(?![\w/])")
_TRAIL = ".,;:!?)"
_UNVERIFIED_MARK = re.compile(r"^\s*[\[(]\s*(unverified|n[ãa]o[ -]verificado|declared|declarado|sem toolchain)\b",
                              re.I)
_LINE_SUFFIX = re.compile(r"^(.*?)(?::(\d+)(?:-\d+)?|#L(\d+)(?:-L?\d+)?)$")

try:  # nome de pacote de workspace (fonte única na frente do scan)
    from cslib.workspaces import looks_like_package_ref as _ws_pkg
except ImportError:  # pragma: no cover
    _ws_pkg = None

KINDS = ("path", "symbol", "command", "glob", "package", "prose", "forbidden")

_PROHIB_HEAD = re.compile(
    r"(?:\b(?:nunca|jamais|n[ãa]o|never|don'?t|do\s+not)\s+(?:se\s+)?(?:use|usa|usar|utilize|utilizar|chame|chamar|call|"
    r"importe|importar|import|rode|rodar|run|execute|executar|invoque|invocar|invoke|adicione|add)"
    r"|\bproibid[oa]s?|\bvedad[oa]s?|\bevite|\bavoid|\bbanned|\bforbidden|\bsem\s+usar)"
    r"(?:\s+(?:o|a|os|as|the|de|do|da))?\s*:?", re.I)
_LIST_SEP = re.compile(r"^(?:\s*(?:,|/|;|\bou\b|\be\b|\bnem\b|\bor\b|\band\b|\bnor\b)?\s*`[^`\n]+`)*\s*"
                       r"(?:,|/|\bou\b|\be\b|\bnem\b|\bor\b|\band\b|\bnor\b)?\s*$", re.I)


def is_package(tok):
    t = (tok or "").strip().rstrip(_TRAIL)
    if t.startswith("@") and _SCOPED.match(t.rstrip("*").rstrip("/")):
        return True
    if _ws_pkg is not None:
        try:
            return bool(_ws_pkg(t) or _ws_pkg(t.rstrip("*").rstrip("/")))
        except Exception:  # pragma: no cover
            return False
    return False


def _ext(name):
    base = name.rsplit("/", 1)[-1]
    if base in FILE_NAMES:
        return True
    if base.startswith(".") and base.count(".") == 1:  # .gitignore, .env
        return base[1:].lower() in FILE_EXTS or base[1:].lower().startswith("env")
    if "." not in base:
        return False
    return base.rsplit(".", 1)[-1].lower() in FILE_EXTS


def _is_globlike(t):
    return any(c in t for c in "*?") or bool(re.search(r"\[[^\]]+\]", t))


def split_alternatives(tok):
    """`Money.percent/Money.allocate` → 2 símbolos; `go.mod/go.sum` → 2 arquivos; senão [tok]."""
    segs = tok.split("/")
    if len(segs) < 2 or any(not s for s in segs):
        return [tok]
    if all(_IDENT.match(s) and "." in s and not _ext(s) for s in segs):
        return segs  # Classe.metodo/Classe.outro
    if all(_ext(s) for s in segs) and all("." in s or s in FILE_NAMES for s in segs):
        return segs  # go.mod/go.sum (alternativas coladas por barra)
    return [tok]


def classify(token, backticked=True):
    t = (token or "").strip()
    if not t:
        return "prose"
    if t.startswith(("http://", "https://", "www.", "mailto:")):
        return "prose"
    if is_package(t):
        return "package"
    if " " in t or "\t" in t:
        first = t.split()[0]
        if first in EXECUTABLES or first.startswith("./") or first.endswith((".sh", ".py")) \
                or first.startswith("scripts/") or first.startswith("bin/"):
            return "command"
        return "prose"
    if not re.search(r"[A-Za-z0-9]", t):
        return "prose"  # `//`, `->`, `...`
    core = _LINE_SUFFIX.match(t)
    base = core.group(1) if core and (core.group(2) or core.group(3)) else t
    if base.startswith("/") and "/" not in base[1:]:
        return "prose"  # `/x` regex/rota solta
    if _is_globlike(base) and ("/" in base or "." in base):
        return "glob"
    if "/" in base:
        segs = [s for s in base.strip("/").split("/") if s]
        if not segs or any(not re.match(r"^[\w.@+-]+$", s) for s in segs):
            return "prose"
        alts = split_alternatives(base)
        if len(alts) > 1 and all(_IDENT.match(a) and not _ext(a) for a in alts):
            return "symbol"
        if not backticked and not (_ext(base) or base.endswith("/")):
            return "prose"
        return "path"
    if _ext(base):
        return "path"
    if _IDENT.match(base) and (re.search(r"[A-Z]", base[1:]) or "_" in base or "." in base or base.endswith("()")):
        return "symbol"
    return "prose"


def strip_line(tok):
    """`a/b.py:12` → ("a/b.py", 12); `a/b.py#L3` → ("a/b.py", 3); sem linha → (tok, None)."""
    m = _LINE_SUFFIX.match(tok)
    if m and (m.group(2) or m.group(3)):
        return m.group(1), int(m.group(2) or m.group(3))
    return tok, None


def extract(text):
    """[(kind, value, line|None, marked)] de um texto livre. `marked` = comando seguido de [unverified]."""
    out, seen = [], set()

    def add(kind, val, line=None, marked=False):
        k = (kind, val, line)
        if k not in seen:
            seen.add(k)
            out.append((kind, val, line, marked))

    text = text or ""
    for m in _BACKTICK.finditer(text):
        tok = m.group(1).strip()
        kind = classify(tok, backticked=True)
        if kind in ("symbol", "command") and _prohibited(text, m.start()):
            add("forbidden", tok)
            continue
        if kind in ("path", "glob"):
            p, ln = strip_line(tok)
            p = p.rstrip(_TRAIL) or p
            if p.startswith("./"):
                p = p[2:]
            for a in split_alternatives(p):
                add(kind, a, ln)
        elif kind == "symbol":
            for a in split_alternatives(tok):
                add("symbol", a)
        elif kind == "command":
            add("command", tok, None, bool(_UNVERIFIED_MARK.match(text[m.end():m.end() + 40])))
        elif kind == "package":
            add("package", tok)
    plain = _BACKTICK.sub(" ", text)
    for m in _BARE.finditer(plain):
        p = m.group(1)
        while p and p[-1] in _TRAIL and p[:-1]:
            p = p[:-1]
        if p.startswith(("http", "www.")) or "//" in p or re.match(r"^[A-Z_]+/[A-Z_]+$", p):
            continue
        if p.endswith("/") and p.count("/") == 1:
            continue  # "transition/" de uma regex citada em prosa
        if is_package(p):
            continue
        kind = classify(p, backticked=False)
        if kind not in ("path", "glob"):
            continue
        for a in split_alternatives(p):
            add(kind, a, int(m.group(2)) if m.group(2) else None)
    return out


def _prohibited(text, pos):
    """O token que começa em `pos` vem logo depois de uma proibição (na mesma oração), separado dela só por
    outros tokens entre crases e separadores de lista."""
    clause = re.split(r"[.;\n]\s|[\n]|—", text[:pos])[-1]
    for m in _PROHIB_HEAD.finditer(clause):
        if _LIST_SEP.match(clause[m.end():]):
            return True
    return False



def refs_by_kind(text, kinds=("path", "glob")):
    return [(k, v, ln) for k, v, ln, _ in extract(text) if k in kinds]
