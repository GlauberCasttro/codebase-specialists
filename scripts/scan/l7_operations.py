"""L7 operação: comandos DECLARADOS em CI/Makefile/package.json/pyproject/tox/justfile; executa os de
teste/lint/check/build com timeout (subprocess com argv, sem shell) →
verified | failed | unavailable | declared.

- Só comandos declarados no repo; nunca sintetiza (inferir `python -m unittest` sem o PYTHONPATH
  que o Makefile exporta produziu um `failed` falso).
- `unavailable`: a ferramenta que o comando exige não existe no ambiente do scan (PATH ou
  node_modules/.bin; antes de executar pela receita do make/corpo do script, ou depois pela saída:
  "command not found", exit 127, módulo Python de terceiros ausente). Diz QUAL ferramenta; não é
  falha do repositório e nunca torna doc "stale".
- `failed`: executou com a ferramenta presente e saiu ≠ 0.
- `--no-exec`: nada é executado; tudo fica `declared`.
- Comando que precisa de shell (pipe, &&, $VAR...): `declared` + motivo.
- Saída (stdout+stderr) copiada para .swarm/evidence/<sha256>.txt; fato guarda o sha dos BYTES.
- Nota de determinismo: com execução, duração e saída variam entre execuções; sem execução
  (--no-exec) o arquivo é byte a byte determinístico.
"""

import os
import signal
import subprocess
import time

import posixpath
import re

from cslib import paths, workspaces
from cslib.evidence import ev_cmd, ev_file, slug, store_blob
from . import commands as cmdx
from . import toolcheck

LAYER = "operations"
EXEC_KINDS = ("test", "lint", "check", "build")
KIND_PRIORITY = {"test": 0, "lint": 1, "check": 2, "build": 3, "format": 4, "other": 5}
STATUSES = ("verified", "failed", "unavailable", "declared")
MAX_OUTPUT = 1024 * 1024


def _env():
    env = dict(os.environ)
    env.update({"CI": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_ADDOPTS": "-p no:cacheprovider",
                "NO_COLOR": "1", "TERM": "dumb", "GIT_TERMINAL_PROMPT": "0"})
    return env


def execute(target, argv, timeout):
    """Roda argv no alvo. Retorna dict {exit, duration_s, timed_out, output(bytes)}."""
    t0 = time.monotonic()
    try:
        p = subprocess.Popen(argv, cwd=target, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, env=_env(), start_new_session=True)
    except OSError as exc:
        return {"exit": 127, "duration_s": 0.0, "timed_out": False,
                "output": ("falha ao iniciar: %s" % exc).encode("utf-8")}
    timed_out = False
    try:
        out, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            p.kill()
        out, _ = p.communicate()
    return {"exit": p.returncode if not timed_out else 124, "duration_s": round(time.monotonic() - t0, 2),
            "timed_out": timed_out, "output": (out or b"")[-MAX_OUTPUT:]}


def _is_ci(src):
    return src.startswith(".github/") or src.endswith(".gitlab-ci.yml")


def _python_packages(ctx):
    out = set()
    for f in ctx.files:
        if f.endswith(".py"):
            parts = f.split("/")
            out.update(p for p in parts[:-1])
            out.add(parts[-1][:-3])
    return out


class Tools(object):
    """Ferramentas exigidas por comando declarado (estático)."""

    def __init__(self, ctx):
        self.ctx = ctx
        self._make = {}

    def _makefile(self, rel):
        if rel not in self._make:
            lines = self.ctx.lines(rel)
            self._make[rel] = (toolcheck.make_targets(lines), toolcheck.make_vars(lines))
        return self._make[rel]

    def required(self, c):
        """([(ferramenta, linha)], dir_base, pkg_dirs) — o que o comando precisa para rodar."""
        src = c["source"]["file"]
        name = c.get("name", "")
        if name.startswith("make:") and not _is_ci(src):
            targets, variables = self._makefile(src)
            return toolcheck.make_tools(targets, variables, name[5:]), posixpath.dirname(src), ()
        if "script" in c:
            d = posixpath.dirname(src)
            tools = [(t, c["source"]["line"]) for t in toolcheck.first_words(c["script"])]
            return tools, d, tuple(sorted(set([d, ""])))
        if c.get("argv"):
            return [(c["argv"][0], c["source"]["line"])], "", ()
        return [], "", ()

    def missing(self, c):
        tools, base, pkg_dirs = self.required(c)
        for tool, line in tools:
            probe = posixpath.normpath(posixpath.join(base, tool)) if "/" in tool and base else tool
            if not toolcheck.lookup(self.ctx.target, probe, pkg_dirs):
                where = " (node_modules/.bin ausente — dependências não instaladas)" if pkg_dirs else ""
                return {"tool": tool, "line": line, "where": where}
        return None


def if_present_footguns(ctx, declared):
    """Script npm que roda `--workspaces --if-present`: workspace sem o script passa em silêncio."""
    out = []
    ws = workspaces.discover(ctx.files, ctx.text)
    for c in declared:
        body = c.get("script") or ""
        if "--if-present" not in body or not re.search(r"(^|\s)(--workspaces|-ws|--workspace|-w)\b", body):
            continue
        m = re.search(r"\b(?:npm|pnpm|yarn)\s+(?:run(?:-script)?\s+)?([\w:.-]+)", body)
        script = m.group(1) if m else None
        if script in (None, "run"):
            continue
        own = posixpath.dirname(c["source"]["file"])
        members = sorted((w["dir"], n, w) for n, w in ws.items() if w["dir"] != own and
                         (not own or w["dir"].startswith(own + "/")))
        lacking = ["%s (%s)" % (d, n) for d, n, w in members if script not in w["scripts"]]
        out.append({"cmd": c["cmd"], "file": c["source"]["file"], "line": c["source"]["line"],
                    "script": script, "body": body, "lacking": lacking, "members": len(members)})
    return out


def run(ctx):
    fb = ctx.fb
    declared = cmdx.all_commands(ctx)
    # dedup por texto do comando; a declaração primária é a de Makefile/package.json/pyproject (que
    # define o comando) e não a do CI (que só o chama); todas as fontes ficam em declared_in.
    by_cmd = {}
    for c in sorted(declared, key=lambda c: (_is_ci(c["source"]["file"]), c["source"]["file"],
                                             c["source"]["line"], c["cmd"])):
        if c["cmd"] in by_cmd:
            by_cmd[c["cmd"]]["declared_in"].append("%s:%d" % (c["source"]["file"], c["source"]["line"]))
            continue
        c["declared_in"] = ["%s:%d" % (c["source"]["file"], c["source"]["line"])]
        by_cmd[c["cmd"]] = c
    uniq = list(by_cmd.values())
    for c in uniq:
        c["declared_in"].sort()
    tools = Tools(ctx)
    pypkgs = _python_packages(ctx)

    def prio(c):
        src = c["source"]["file"]
        return (KIND_PRIORITY.get(c["kind"], 9), 1 if _is_ci(src) else 0, src, c["source"]["line"], c["cmd"])
    executed = 0
    for c in sorted(uniq, key=prio):
        c["status"] = "declared"
        if c["kind"] not in EXEC_KINDS:
            c["reason"] = "tipo %s não é executado" % c["kind"]
            continue
        if ctx.opts.no_exec:
            c["reason"] = "--no-exec"
            continue
        if c["argv"] is None:
            c["reason"] = "precisa de shell (pipe/&&/variável/redireção); não executado"
            continue
        miss = tools.missing(c)
        if miss:
            c.update({"status": "unavailable", "missing_tool": miss["tool"],
                      "reason": "ferramenta '%s' ausente no ambiente do scan%s; não executado"
                                % (miss["tool"], miss["where"])})
            continue
        if executed >= ctx.opts.max_exec:
            c["reason"] = "limite --max-exec=%d atingido" % ctx.opts.max_exec
            continue
        executed += 1
        r = execute(ctx.target, c["argv"], ctx.opts.timeout)
        blob = store_blob(ctx.target, r["output"])
        status = "verified" if r["exit"] == 0 else "failed"
        c.update({"exit": r["exit"], "duration_s": r["duration_s"], "timed_out": r["timed_out"],
                  "out_sha256": ev_cmd(c["cmd"], r["exit"], r["output"])["out_sha256"],
                  "output_blob": blob})
        if status == "failed" and not r["timed_out"]:
            tool = toolcheck.diagnose_output(r["output"], r["exit"], pypkgs)
            if tool:
                status = "unavailable"
                c["missing_tool"] = tool
                c["reason"] = ("executou mas a ferramenta '%s' não existe no ambiente do scan (saída/exit "
                               "%d); não é falha do repo" % (tool, r["exit"]))
        c["status"] = status
        if r["timed_out"]:
            c["reason"] = "timeout de %ss" % ctx.opts.timeout
    uniq.sort(key=lambda c: (c["source"]["file"], c["source"]["line"], c["cmd"]))

    facts = []
    for c in uniq:
        src = c["source"]
        ev = [ev_file(src["file"], src["line"])]
        also = [x for x in c["declared_in"] if x != "%s:%d" % (src["file"], src["line"])]
        also_txt = ("; também chamado em %s" % ", ".join(also[:3])) if also else ""
        if "exit" in c:
            ev.append({"cmd": c["cmd"], "exit": c["exit"], "out_sha256": c["out_sha256"],
                       "blob": c["output_blob"]})
        if c["status"] in ("verified", "failed"):
            claim = "`%s` (%s, %s:%d): %s — exit %d em %.1fs%s%s" % (
                c["cmd"], c["kind"], src["file"], src["line"], c["status"], c["exit"], c["duration_s"],
                " (timeout)" if c.get("timed_out") else "", also_txt)
            conf = "high"
        elif c["status"] == "unavailable":
            claim = "`%s` (%s, %s:%d): unavailable — %s%s" % (
                c["cmd"], c["kind"], src["file"], src["line"], c["reason"], also_txt)
            conf = "high"
        else:
            claim = "`%s` (%s, %s:%d): declared — %s%s" % (c["cmd"], c["kind"], src["file"], src["line"],
                                                           c.get("reason", ""), also_txt)
            conf = "medium"
        d = {"command": c["cmd"], "status": c["status"], "kind": c["kind"], "origin": c["origin"],
             "purpose": "%s (declarado em %s:%d)" % (c["kind"], src["file"], src["line"]),
             "declared_in": c["declared_in"]}
        if "exit" in c:
            d["exit"] = c["exit"]
        if c.get("missing_tool"):
            d["missing_tool"] = c["missing_tool"]
        facts.append(fb.fact("ops.%s.%s" % (c["kind"], slug(c["cmd"], 70)), LAYER, claim, ev,
                             confidence=conf, scope=["**"], data=d))
    for fg in if_present_footguns(ctx, declared):
        if fg["lacking"]:
            now = "hoje sem '%s': %s" % (fg["script"], ", ".join(fg["lacking"][:10]))
        else:
            now = "hoje os %d workspaces têm '%s' (um workspace novo sem ele passaria sem rodar nada)" % (
                fg["members"], fg["script"])
        facts.append(fb.fact("ops.footgun.if-present", LAYER,
                             "Footgun: `%s` (%s:%d) roda `%s` — com --if-present, workspace sem script '%s' "
                             "é pulado em silêncio e o comando continua verde; %s" % (
                                 fg["cmd"], fg["file"], fg["line"], fg["body"], fg["script"], now),
                             [ev_file(fg["file"], fg["line"])], confidence="high", scope=["**"],
                             data={"kind": "footgun", "command": fg["cmd"], "script": fg["script"],
                                   "lacking": fg["lacking"]}))
    tests = [c for c in uniq if c["kind"] == "test"]
    if not tests:
        n_tests = sum(1 for f in ctx.files if paths.is_test_file(f))
        facts.append(fb.fact("ops.test.absent", LAYER,
                             "Nenhum comando de teste declarado (Makefile, package.json, pyproject, tox, "
                             "justfile, CI)%s — o scan não inventa comando" % (
                                 "; há %d arquivos de teste no repo" % n_tests if n_tests else ""),
                             [ev_cmd("scan:L7 busca de comandos de teste declarados", 1, b"")],
                             confidence="high", scope=["**"]))
    if not facts:
        facts.append(fb.fact("ops.none", LAYER, "Nenhum comando de operação encontrado",
                             [ev_cmd("scan:L7 busca de comandos", 1, b"")], scope=["**"]))
    summary = {s: sum(1 for c in uniq if c["status"] == s) for s in STATUSES}
    return {"layer": LAYER, "commands": uniq, "summary": summary, "executed": not ctx.opts.no_exec,
            "timeout_s": ctx.opts.timeout, "facts": facts}

