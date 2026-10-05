"""Texto de cartões: render determinístico, varredura de strings e extração de referências.

Referência = path (com :linha opcional), glob, comando (`entre crases` iniciando por executável) ou
símbolo (`Identificador` entre crases). Usado por team validate (regra 5/7), probes existence (G2),
anticola (regra 6) e antitemplate (G3) — um extrator só, carregado por código pelos quatro.
"""
import re

SKIP_KEYS = frozenset(["facts", "facts_used", "invariants", "id", "name", "kind", "tools", "model",
                       "supports", "fingerprint"])
EXECUTABLES = frozenset([
    "python", "python3", "pip", "pip3", "pytest", "tox", "nox", "uv", "poetry", "pdm", "hatch", "ruff",
    "mypy", "black", "flake8", "pylint", "npm", "npx", "yarn", "pnpm", "bun", "deno", "node", "tsc",
    "jest", "vitest", "eslint", "prettier", "make", "go", "cargo", "rustc", "mvn", "mvnw", "./mvnw",
    "gradle", "./gradlew", "gradlew", "dotnet", "ruby", "bundle", "rake", "rspec", "php", "composer",
    "phpunit", "mix", "elixir", "swift", "xcodebuild", "java", "javac", "docker", "docker-compose",
    "kubectl", "helm", "terraform", "bash", "sh", "git", "just", "task", "cmake", "ctest", "bazel",
    "sbt", "lein", "flutter", "dart", "cs.py", "cs-mem"])
FILE_NAMES = frozenset(["Makefile", "Dockerfile", "Jenkinsfile", "Procfile", "Gemfile", "Rakefile",
                        "Justfile", "Taskfile.yml"])
_BACKTICK = re.compile(r"`([^`\n]+)`")
_BARE_PATH = re.compile(r"(?<![\w/.:@-])((?:[\w.*-]+/)+[\w.*-]*(?:\.[A-Za-z0-9]{1,8}|\*\*?|/)?)(?::(\d+))?")
_TRAIL = ".,;:!?)"
# marcador honesto de comando declarado mas não executado (toolchain ausente): `make test` [unverified]
_UNVERIFIED_MARK = re.compile(r"^\s*[\[(]\s*(unverified|n[ãa]o[ -]verificado|declared|declarado|sem toolchain)\b",
                              re.I)
_FILELIKE = re.compile(r"^[\w.*/-]+\.[A-Za-z0-9]{1,8}$")
_IDENT = re.compile(r"^[A-Za-z_][\w]*(?:\.[A-Za-z_]\w*)*(?:\(\))?$")


try:  # fonte única do que é nome de pacote de workspace (frente do scan)
    from cslib.workspaces import looks_like_package_ref as _pkg_ref
except ImportError:  # pragma: no cover
    _pkg_ref = None


def _is_package_ref(t):
    t = t.rstrip(".,;:!?)")
    if _pkg_ref is not None:
        return _pkg_ref(t) or _pkg_ref(t.rstrip("*").rstrip("/"))
    return t.startswith("@")


def walk_strings(obj, path=""):
    """(keypath, string) de todo valor textual, pulando chaves de referência a fatos/identidade."""
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k in sorted(obj):
            if k in SKIP_KEYS:
                continue
            for x in walk_strings(obj[k], path + "." + k if path else k):
                yield x
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            for x in walk_strings(v, "%s[%d]" % (path, i)):
                yield x


def render_card(card):
    """Linhas do cartão como seriam emitidas (aproximação estável para contagem e similaridade)."""
    if not card:
        return []
    out = []
    for key in ("description", "mission"):
        if card.get(key):
            out += str(card[key]).splitlines()
    sections = [("knows", "Sabe"), ("refuses", "Recusa"), ("rules", "Regras"), ("footguns", "Armadilhas")]
    for key, title in sections:
        items = card.get(key) or []
        if items:
            out.append("## " + title)
        for it in items:
            if isinstance(it, str):
                out.append("- " + it)
                continue
            line = "- " + str(it.get("text", ""))
            if it.get("why"):
                line += " — porque " + str(it["why"])
            out.append(line)
            if it.get("check"):
                out.append("  prova: `%s`" % it["check"])
    if card.get("done_when"):
        out += ["## Feito quando", str(card["done_when"])]
    for pb in card.get("playbooks") or []:
        out.append("## Playbook: " + str(pb.get("title", "")))
        out += ["%d. %s" % (i + 1, s) for i, s in enumerate(pb.get("steps") or [])]
    if card.get("anchors"):
        out.append("## Âncoras")
        out += ["- " + str(a) for a in card["anchors"]]
    return out


def classify_token(tok):
    """'command' | 'path' | 'symbol' | None para um trecho entre crases (delegado a cslib.refs)."""
    from cslib import refs
    k = refs.classify(tok, backticked=True)
    return {"glob": "path"}.get(k, k) if k in ("path", "glob", "symbol", "command") else None


def extract_refs(text):
    """[(type, value, line|None)] de um texto livre — classificador único `cslib.refs` (glob conta como path;
    pacote e prosa não são referência verificável). Comando seguido de [unverified] traz "marked" no 3º campo."""
    from cslib import refs
    out = []
    for kind, val, line, marked in refs.extract(text):
        if kind == "glob":
            out.append(("path", val, line))
        elif kind == "path":
            out.append(("path", val, line))
        elif kind == "command":
            out.append(("command", val, "marked" if marked else None))
        elif kind == "symbol":
            out.append(("symbol", val, None))
    return out


def card_refs(agent):
    """Referências por seção relevante para a regra 5 (+ done_when/check como comandos)."""
    card = agent.get("card") or {}
    out = []
    for a in card.get("anchors") or []:
        out.append(("anchors", "path", str(a).partition(":")[0], None))
    for key in ("knows", "rules", "refuses", "footguns"):
        for it in card.get(key) or []:
            txt = it if isinstance(it, str) else " ".join(str(it.get(x, "")) for x in ("text", "why"))
            for kind, val, ln in extract_refs(txt):
                out.append((key, kind, val, ln))
            if isinstance(it, dict) and it.get("check"):
                out.append(("rules.check", "command", it["check"], bool(it.get("unverified"))))
    for pb in card.get("playbooks") or []:
        for s in pb.get("steps") or []:
            for kind, val, ln in extract_refs(s):
                out.append(("playbooks", kind, val, ln))
    for key in ("description", "mission"):
        for kind, val, ln in extract_refs(card.get(key) or ""):
            out.append((key, kind, val, ln))
    dw = card.get("done_when") or ""
    for kind, val, ln in extract_refs(dw):
        out.append(("done_when", kind, val, ln))
    return out
