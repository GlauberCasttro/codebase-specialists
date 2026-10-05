"""Extração de comandos declarados: Makefile, package.json scripts, pyproject, tox, justfile,
CI (GitHub Actions, GitLab). Usado por L4 (regras de CI) e L7 (operação).

Cada comando: {cmd, argv|None, kind, source:{file,line}, origin: declared, name[, script]}
Só comandos DECLARADOS no repo: o scan nunca sintetiza comando (um comando inventado, rodado sem o
ambiente que o repo declara — ex.: sem o PYTHONPATH do Makefile —, vira fato falso).
argv é None quando o comando precisa de shell (pipes, &&, $VAR, redireção) — não executável.
"""

import json
import re
import shlex

from . import tomlmini

SHELL_META = re.compile(r"[|&;<>$`(){}\\*?]|\n")

KIND_PATTERNS = (
    ("test", re.compile(r"(^|[\s:/_-])(test|tests|pytest|unittest|jest|vitest|mocha|rspec|"
                        r"phpunit|ctest|bats|spec|check-tests|e2e|conformance)(\b|$)|go test|"
                        r"cargo test|dotnet test|mvn test|gradle test|npm test", re.I)),
    ("lint", re.compile(r"(^|[\s:/_-])(lint|ruff|flake8|pylint|eslint|shellcheck|golangci|"
                        r"clippy|rubocop|mypy|pyright|tsc|typecheck|type-check|vet|stylelint|"
                        r"prettier --check|black --check|validate|audit)(\b|$)", re.I)),
    ("check", re.compile(r"(^|[\s:/_-])(check|checks|verify|precommit|pre-commit)([\s:/_-]|$)", re.I)),
    ("format", re.compile(r"(^|[\s:/_-])(fmt|format|prettier|black|isort|gofmt|rustfmt)(\b|$)", re.I)),
    ("build", re.compile(r"(^|[\s:/_-])(build|compile|bundle|dist|package|tsc -b|cargo build|"
                         r"go build|dotnet build|mvn package)(\b|$)", re.I)),
)


def classify(text):
    for kind, rx in KIND_PATTERNS:
        if rx.search(text):
            return kind
    return "other"


def to_argv(cmd):
    if SHELL_META.search(cmd):
        return None
    try:
        argv = shlex.split(cmd)
    except ValueError:
        return None
    if not argv or "=" in argv[0]:
        return None
    return argv


def _mk(cmd, kind, rel, line, origin="declared", name=None, argv="auto"):
    cmd = cmd.strip()
    return {"cmd": cmd, "argv": to_argv(cmd) if argv == "auto" else argv, "kind": kind,
            "source": {"file": rel, "line": line}, "origin": origin, "name": name or cmd}


def makefile(ctx, rel):
    out = []
    lines = ctx.lines(rel)
    phony = set()
    for ln in lines:
        if ln.startswith(".PHONY:"):
            phony.update(ln.split(":", 1)[1].split())
    for i, ln in enumerate(lines, 1):
        m = re.match(r"^([A-Za-z0-9][\w.-]*)\s*:(?!=)", ln)
        if not m or ln.startswith("\t"):
            continue
        tgt = m.group(1)
        if tgt.startswith(".") or "%" in tgt:
            continue
        # tem receita?
        has_recipe = i < len(lines) and lines[i].startswith("\t")
        deps = ln.split(":", 1)[1].split("#")[0].strip()
        if not has_recipe and not deps:
            continue
        d = "" if rel.count("/") == 0 else rel.rsplit("/", 1)[0]
        cmd = "make %s" % tgt if not d else "make -C %s %s" % (d, tgt)
        out.append(_mk(cmd, classify(tgt), rel, i, name="make:%s" % tgt))
    return out


def package_json(ctx, rel, pm="npm"):
    out = []
    try:
        data = json.loads(ctx.text(rel))
    except ValueError:
        return out
    scripts = data.get("scripts") or {}
    lines = ctx.lines(rel)
    d = "" if "/" not in rel else rel.rsplit("/", 1)[0]
    for name in sorted(scripts):
        body = scripts[name]
        line = next((i for i, ln in enumerate(lines, 1) if '"%s"' % name in ln), 1)
        if pm == "npm":
            pre = "npm --prefix %s " % d if d else "npm "
            cmd = pre + ("test" if name == "test" else "run %s" % name)
        else:
            cmd = "%s run %s" % (pm, name)
        kind = classify(name) if classify(name) != "other" else classify(str(body))
        c = _mk(cmd, kind, rel, line, name="%s:%s" % (pm, name),
                argv=None if (d and pm != "npm") else "auto")
        c["script"] = str(body)
        out.append(c)
    return out


def pyproject(ctx, rel):
    out = []
    text = ctx.text(rel)
    data = tomlmini.loads(text)
    tool = data.get("tool") or {}
    lines = ctx.lines(rel)

    def line_of(pat):
        return next((i for i, ln in enumerate(lines, 1) if pat in ln), 1)
    if "pytest" in tool or (isinstance(tool.get("pytest"), dict)):
        out.append(_mk("python3 -m pytest", "test", rel, line_of("[tool.pytest"), name="pytest"))
    if "ruff" in tool:
        out.append(_mk("ruff check .", "lint", rel, line_of("[tool.ruff"), name="ruff"))
    if "mypy" in tool:
        out.append(_mk("mypy .", "lint", rel, line_of("[tool.mypy"), name="mypy"))
    poe = (tool.get("poe") or {}).get("tasks") or {}
    for name in sorted(poe):
        out.append(_mk("poe %s" % name, classify(name), rel, line_of(name), name="poe:%s" % name))
    return out


def tox(ctx, rel):
    out = []
    text = ctx.text(rel)
    lines = ctx.lines(rel)
    m = re.search(r"^envlist\s*=\s*(.+(?:\n[ \t]+.+)*)", text, re.M)
    envs = re.split(r"[,\s]+", m.group(1).strip()) if m else []
    for env in [e for e in envs if e and "{" not in e]:
        line = next((i for i, ln in enumerate(lines, 1) if ln.startswith("envlist")), 1)
        out.append(_mk("tox -e %s" % env, "test" if not classify(env) in ("lint", "format")
                       else classify(env), rel, line, name="tox:%s" % env))
    return out


def justfile(ctx, rel):
    out = []
    for i, ln in enumerate(ctx.lines(rel), 1):
        m = re.match(r"^@?([A-Za-z][\w-]*)(?:\s+[^:=]*)?:(?!=)", ln)
        if m:
            out.append(_mk("just %s" % m.group(1), classify(m.group(1)), rel, i,
                           name="just:%s" % m.group(1)))
    return out


def github_actions(ctx, rel):
    """Linhas `run:` (inline ou bloco `|`/`>`), uma por comando."""
    out = []
    lines = ctx.lines(rel)
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^(\s*)(?:-\s+)?run:\s*(.*)$", ln)
        if m:
            indent = len(m.group(1))
            rest = m.group(2).strip()
            if rest in ("|", ">", "|-", ">-", "|+"):
                j = i + 1
                while j < len(lines) and (not lines[j].strip() or
                                          len(lines[j]) - len(lines[j].lstrip()) > indent):
                    c = lines[j].strip()
                    if c and not c.startswith("#"):
                        out.append(_mk(c, classify(c), rel, j + 1, name="ci:%s" % c))
                    j += 1
                i = j
                continue
            if rest:
                c = rest.strip("'\"")
                out.append(_mk(c, classify(c), rel, i + 1, name="ci:%s" % c))
        i += 1
    return out


def gitlab_ci(ctx, rel):
    out = []
    lines = ctx.lines(rel)
    in_script = None
    for i, ln in enumerate(lines, 1):
        m = re.match(r"^(\s*)(script|before_script|after_script):\s*$", ln)
        if m:
            in_script = len(m.group(1))
            continue
        if in_script is not None:
            m2 = re.match(r"^(\s*)-\s+(.*)$", ln)
            if m2 and len(m2.group(1)) >= in_script:
                c = m2.group(2).strip().strip("'\"")
                out.append(_mk(c, classify(c), rel, i, name="ci:%s" % c))
                continue
            if ln.strip() and len(ln) - len(ln.lstrip()) <= in_script:
                in_script = None
    return out


def package_manager(ctx, rel):
    d = "" if "/" not in rel else rel.rsplit("/", 1)[0] + "/"
    if ctx.exists(d + "pnpm-lock.yaml"):
        return "pnpm"
    if ctx.exists(d + "yarn.lock"):
        return "yarn"
    return "npm"


def all_commands(ctx):
    cmds = []
    for rel in ctx.files:
        base = rel.rsplit("/", 1)[-1]
        if base in ("Makefile", "makefile", "GNUmakefile"):
            cmds += makefile(ctx, rel)
        elif base == "package.json":
            cmds += package_json(ctx, rel, package_manager(ctx, rel))
        elif base == "pyproject.toml":
            cmds += pyproject(ctx, rel)
        elif base == "tox.ini":
            cmds += tox(ctx, rel)
        elif base in ("justfile", "Justfile", ".justfile"):
            cmds += justfile(ctx, rel)
        elif rel.startswith(".github/workflows/") and base.endswith((".yml", ".yaml")):
            cmds += github_actions(ctx, rel)
        elif base == ".gitlab-ci.yml":
            cmds += gitlab_ci(ctx, rel)
    return cmds
