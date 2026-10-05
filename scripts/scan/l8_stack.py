"""L8 stack: versões exatas de lockfiles por ecossistema + inventário de API pública da versão
INSTALADA (introspecção) das N dependências críticas; fallback `declared`.

Também classifica imports externos (de L1) em stdlib × terceiros (Python, Node).
"""

import json
import os
import re
import shutil
import subprocess
import sys

from cslib.evidence import ev_cmd, ev_file, slug
from . import tomlmini

LAYER = "stack"

PY_STDLIB_FALLBACK = frozenset("""
__future__ abc argparse array ast asyncio base64 bisect builtins bz2 calendar cgi cmath code codecs
collections colorsys concurrent configparser contextlib contextvars copy copyreg cProfile csv ctypes
curses dataclasses datetime dbm decimal difflib dis doctest email encodings enum errno faulthandler
fcntl filecmp fileinput fnmatch fractions ftplib functools gc getopt getpass gettext glob graphlib
grp gzip hashlib heapq hmac html http imaplib importlib inspect io ipaddress itertools json keyword
linecache locale logging lzma mailbox marshal math mimetypes mmap multiprocessing netrc numbers
operator optparse os pathlib pdb pickle pkgutil platform plistlib poplib posix posixpath pprint
profile pstats pty pwd py_compile pyclbr pydoc queue quopri random re readline reprlib resource
rlcompleter runpy sched secrets select selectors shelve shlex shutil signal site smtplib socket
socketserver sqlite3 ssl stat statistics string stringprep struct subprocess symtable sys sysconfig
syslog tabnanny tarfile tempfile termios textwrap threading time timeit tkinter token tokenize tomllib
trace traceback tracemalloc tty turtle types typing unicodedata unittest urllib uuid venv warnings
wave weakref webbrowser winreg wsgiref xml xmlrpc zipapp zipfile zipimport zlib zoneinfo _thread
""".split())
NODE_BUILTINS = frozenset("""
assert async_hooks buffer child_process cluster console constants crypto dgram diagnostics_channel dns
domain events fs http http2 https inspector module net os path perf_hooks process punycode querystring
readline repl stream string_decoder sys timers tls trace_events tty url util v8 vm wasi worker_threads
zlib test
""".split())


def py_stdlib():
    names = getattr(sys, "stdlib_module_names", None)
    return frozenset(names) if names else PY_STDLIB_FALLBACK


def _norm_py(name):
    return re.sub(r"[-_.]+", "-", name).lower()


# ---------------- parsers de lockfile: (name, version, line) ----------------

def _lines_find(lines, needle, start=0):
    for i in range(start, len(lines)):
        if needle in lines[i]:
            return i + 1
    return 1


def parse_toml_packages(ctx, rel):
    """poetry.lock, uv.lock, Cargo.lock: [[package]] name/version."""
    out = []
    lines = ctx.lines(rel)
    cur = None
    for i, ln in enumerate(lines, 1):
        if ln.strip() == "[[package]]":
            cur = {"line": i}
            continue
        if cur is None:
            continue
        m = re.match(r'^(name|version)\s*=\s*"([^"]+)"', ln)
        if m:
            cur[m.group(1)] = m.group(2)
            if "name" in cur and "version" in cur:
                out.append((cur["name"], cur["version"], cur["line"]))
                cur = None
    return out


def parse_requirements(ctx, rel):
    out = []
    for i, ln in enumerate(ctx.lines(rel), 1):
        s = ln.split("#", 1)[0].strip()
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?\s*===?\s*([^\s;,]+)", s)
        if m:
            out.append((m.group(1), m.group(2), i))
    return out


def parse_pipfile_lock(ctx, rel):
    out = []
    try:
        data = json.loads(ctx.text(rel))
    except ValueError:
        return out
    lines = ctx.lines(rel)
    for sec in ("default", "develop"):
        for name, spec in sorted((data.get(sec) or {}).items()):
            v = (spec or {}).get("version", "")
            if v.startswith("=="):
                out.append((name, v[2:], _lines_find(lines, '"%s"' % name)))
    return out


def parse_package_lock(ctx, rel):
    out = []
    try:
        data = json.loads(ctx.text(rel))
    except ValueError:
        return out
    lines = ctx.lines(rel)
    pk = data.get("packages")
    if isinstance(pk, dict):
        for key in sorted(pk):
            if not key.startswith("node_modules/") or "/node_modules/" in key[13:]:
                continue
            v = (pk[key] or {}).get("version")
            if v:
                out.append((key[13:], v, _lines_find(lines, '"%s"' % key)))
    else:
        for name, spec in sorted((data.get("dependencies") or {}).items()):
            if spec.get("version"):
                out.append((name, spec["version"], _lines_find(lines, '"%s"' % name)))
    return out


def parse_pnpm(ctx, rel):
    out = []
    in_pk = False
    for i, ln in enumerate(ctx.lines(rel), 1):
        if re.match(r"^(packages|snapshots):\s*$", ln):
            in_pk = ln.startswith("packages")
            continue
        if re.match(r"^\S", ln):
            in_pk = False
        if not in_pk:
            continue
        m = re.match(r"^  '?/?((?:@[^/@\s]+/)?[^@\s/']+)[@/]([0-9][^:()'\s]*)", ln)
        if m:
            out.append((m.group(1), m.group(2), i))
    return out


def parse_yarn(ctx, rel):
    out = []
    lines = ctx.lines(rel)
    cur = None
    for i, ln in enumerate(lines, 1):
        if ln and not ln.startswith((" ", "#")) and ln.rstrip().endswith(":"):
            first = ln.split(",")[0].strip().strip('"')
            m = re.match(r"^((?:@[^/@]+/)?[^@]+)@", first)
            cur = (m.group(1), i) if m else None
            continue
        if cur:
            m = re.match(r'^\s+version:?\s+"?([^"\s]+)"?', ln)
            if m:
                out.append((cur[0], m.group(1), cur[1]))
                cur = None
    return out


def parse_go_mod(ctx, rel):
    out = []
    in_req = False
    for i, ln in enumerate(ctx.lines(rel), 1):
        s = ln.strip()
        if s.startswith("require ("):
            in_req = True
            continue
        if in_req and s == ")":
            in_req = False
            continue
        m = re.match(r"^(?:require\s+)?([\w.\-/~]+)\s+(v[\w.\-+]+)(\s*//\s*indirect)?", s) \
            if (in_req or s.startswith("require ")) else None
        if m:
            out.append((m.group(1), m.group(2), i, bool(m.group(3))))
    return out


def parse_gemfile_lock(ctx, rel):
    out = []
    for i, ln in enumerate(ctx.lines(rel), 1):
        m = re.match(r"^    ([A-Za-z0-9_.-]+) \(([^)]+)\)$", ln)
        if m:
            out.append((m.group(1), m.group(2), i))
    return out


def parse_composer_lock(ctx, rel):
    out = []
    try:
        data = json.loads(ctx.text(rel))
    except ValueError:
        return out
    lines = ctx.lines(rel)
    for sec in ("packages", "packages-dev"):
        for p in data.get(sec) or []:
            if p.get("name") and p.get("version"):
                out.append((p["name"], p["version"], _lines_find(lines, '"%s"' % p["name"])))
    return out


def parse_nuget_lock(ctx, rel):
    out = []
    try:
        data = json.loads(ctx.text(rel))
    except ValueError:
        return out
    lines = ctx.lines(rel)
    seen = set()
    for tfm in sorted((data.get("dependencies") or {})):
        for name, spec in sorted(data["dependencies"][tfm].items()):
            if spec.get("resolved") and name not in seen:
                seen.add(name)
                out.append((name, spec["resolved"], _lines_find(lines, '"%s"' % name)))
    return out


def parse_csproj(ctx, rel):
    out = []
    for i, ln in enumerate(ctx.lines(rel), 1):
        m = re.search(r'<PackageReference\s+Include="([^"]+)"\s+Version="([^"]+)"', ln)
        if m:
            out.append((m.group(1), m.group(2), i))
    return out


def parse_gradle_lock(ctx, rel):
    out = []
    for i, ln in enumerate(ctx.lines(rel), 1):
        m = re.match(r"^([\w.\-]+):([\w.\-]+):([\w.\-+]+)=", ln)
        if m:
            out.append(("%s:%s" % (m.group(1), m.group(2)), m.group(3), i))
    return out


def parse_pom(ctx, rel):
    out = []
    text = ctx.text(rel)
    for m in re.finditer(r"<dependency>(.*?)</dependency>", text, re.S):
        body = m.group(1)
        g = re.search(r"<groupId>([^<]+)</groupId>", body)
        a = re.search(r"<artifactId>([^<]+)</artifactId>", body)
        v = re.search(r"<version>([^<]+)</version>", body)
        if g and a and v and "${" not in v.group(1):
            out.append(("%s:%s" % (g.group(1), a.group(1)), v.group(1),
                        text.count("\n", 0, m.start()) + 1))
    return out


LOCK_PARSERS = (
    ("poetry.lock", "python", parse_toml_packages),
    ("uv.lock", "python", parse_toml_packages),
    ("Pipfile.lock", "python", parse_pipfile_lock),
    ("package-lock.json", "node", parse_package_lock),
    ("npm-shrinkwrap.json", "node", parse_package_lock),
    ("pnpm-lock.yaml", "node", parse_pnpm),
    ("yarn.lock", "node", parse_yarn),
    ("go.mod", "go", parse_go_mod),
    ("Cargo.lock", "rust", parse_toml_packages),
    ("Gemfile.lock", "ruby", parse_gemfile_lock),
    ("composer.lock", "php", parse_composer_lock),
    ("packages.lock.json", "dotnet", parse_nuget_lock),
    ("gradle.lockfile", "java", parse_gradle_lock),
    ("pom.xml", "java", parse_pom),
)


def direct_deps(ctx):
    """Dependências diretas declaradas em manifestos: {eco: set(nome normalizado)}."""
    out = {}
    for rel in ctx.files:
        base = rel.rsplit("/", 1)[-1]
        if base == "pyproject.toml":
            data = tomlmini.loads(ctx.text(rel))
            proj = data.get("project") or {}
            for d in proj.get("dependencies") or []:
                m = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)", str(d))
                if m:
                    out.setdefault("python", set()).add(_norm_py(m.group(1)))
            poetry = ((data.get("tool") or {}).get("poetry") or {}).get("dependencies") or {}
            for k in poetry:
                if k.lower() != "python":
                    out.setdefault("python", set()).add(_norm_py(k))
        elif base.startswith("requirements") and base.endswith(".txt"):
            for name, _, _ in parse_requirements(ctx, rel):
                out.setdefault("python", set()).add(_norm_py(name))
            for ln in ctx.lines(rel):
                m = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)", ln.split("#")[0])
                if m and not ln.strip().startswith("-"):
                    out.setdefault("python", set()).add(_norm_py(m.group(1)))
        elif base == "package.json":
            try:
                data = json.loads(ctx.text(rel))
            except ValueError:
                continue
            for sec in ("dependencies", "devDependencies", "peerDependencies"):
                for k in data.get(sec) or {}:
                    out.setdefault("node", set()).add(k)
        elif base == "Cargo.toml":
            data = tomlmini.loads(ctx.text(rel))
            for sec in ("dependencies", "dev-dependencies"):
                for k in data.get(sec) or {}:
                    out.setdefault("rust", set()).add(k)
        elif base == "Gemfile":
            for m in re.finditer(r"^\s*gem\s+['\"]([^'\"]+)", ctx.text(rel), re.M):
                out.setdefault("ruby", set()).add(m.group(1))
        elif base == "composer.json":
            try:
                data = json.loads(ctx.text(rel))
            except ValueError:
                continue
            for sec in ("require", "require-dev"):
                for k in data.get(sec) or {}:
                    out.setdefault("php", set()).add(k)
    return out


# ---------------- introspecção ----------------

PY_INTROSPECT = r"""
import importlib, inspect, json, sys
dist = sys.argv[1]
res = {"dist": dist, "version": None, "module": None, "api": [], "error": None}
try:
    import importlib.metadata as md
    try:
        res["version"] = md.version(dist)
        top = (md.distribution(dist).read_text("top_level.txt") or "").split()
    except Exception:
        top = []
    cands = [t for t in top if not t.startswith("_")] + [dist.replace("-", "_").lower(), dist.lower()]
    mod = None
    for c in cands:
        try:
            mod = importlib.import_module(c); res["module"] = c; break
        except Exception:
            continue
    if mod is None:
        raise ImportError("nenhum módulo importável para " + dist)
    names = getattr(mod, "__all__", None) or [n for n in dir(mod) if not n.startswith("_")]
    for n in sorted(set(map(str, names)))[:200]:
        try:
            obj = getattr(mod, n)
        except Exception:
            continue
        kind = "class" if inspect.isclass(obj) else ("function" if callable(obj) else
               ("module" if inspect.ismodule(obj) else "value"))
        sig = None
        if kind in ("class", "function"):
            try:
                sig = str(inspect.signature(obj))
            except Exception:
                sig = None
        res["api"].append({"name": n, "kind": kind, "signature": sig})
except Exception as exc:
    res["error"] = "%s: %s" % (type(exc).__name__, exc)
print(json.dumps(res, sort_keys=True))
"""

NODE_INTROSPECT = (
    "let r={api:[],error:null,version:null};"
    "try{const n=process.argv[1];const m=require(n);"
    "r.api=Object.keys(m).sort().slice(0,200).map(k=>({name:k,kind:typeof m[k]}));"
    "try{r.version=require(n+'/package.json').version}catch(e){}}"
    "catch(e){r.error=String(e&&e.message||e).slice(0,300)}"
    "console.log(JSON.stringify(r))"
)


def _python_for(target):
    for cand in (".venv/bin/python", "venv/bin/python", ".venv/Scripts/python.exe"):
        p = os.path.join(target, cand)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return shutil.which("python3") or sys.executable


def _run(argv, cwd, timeout=60):
    try:
        p = subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           stdin=subprocess.DEVNULL, timeout=timeout,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", NO_COLOR="1"))
        return p.returncode, p.stdout
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 124, str(exc).encode("utf-8")


def introspect(ctx, eco, name):
    if eco == "python":
        py = _python_for(ctx.target)
        code, out = _run([py, "-c", PY_INTROSPECT, name], ctx.target)
        cmd = "%s -c <introspecção python> %s" % (os.path.basename(py), name)
    elif eco == "node" and shutil.which("node"):
        code, out = _run(["node", "-e", NODE_INTROSPECT, name], ctx.target)
        cmd = "node -e <introspecção node> %s" % name
    elif eco == "go" and shutil.which("go"):
        code, out = _run(["go", "doc", "-short", name], ctx.target)
        cmd = "go doc -short %s" % name
        if code == 0:
            api = [{"name": ln.strip(), "kind": "decl", "signature": None}
                   for ln in out.decode("utf-8", "replace").splitlines()[:200] if ln.strip()]
            return {"status": "introspected", "api": api, "version": None, "cmd": cmd, "exit": code,
                    "out": out}
        return {"status": "declared", "error": "go doc falhou", "cmd": cmd, "exit": code, "out": out}
    else:
        return None
    try:
        data = json.loads(out.decode("utf-8", "replace").strip().splitlines()[-1])
    except (ValueError, IndexError):
        data = {"error": "saída não-JSON (exit %d)" % code}
    if data.get("error") or code != 0:
        return {"status": "declared", "error": data.get("error") or "exit %d" % code, "cmd": cmd,
                "exit": code, "out": out}
    return {"status": "introspected", "api": data.get("api", []), "version": data.get("version"),
            "module": data.get("module"), "cmd": cmd, "exit": code, "out": out}


def run(ctx):
    fb = ctx.fb
    facts = []
    packages = []
    for rel in ctx.files:
        base = rel.rsplit("/", 1)[-1]
        for fname, eco, parser in LOCK_PARSERS:
            if base == fname:
                for item in parser(ctx, rel):
                    name, ver, line = item[0], item[1], item[2]
                    p = {"eco": eco, "name": name, "version": ver, "source": rel, "line": line}
                    if len(item) > 3:
                        p["indirect"] = item[3]
                    packages.append(p)
        if base.startswith("requirements") and base.endswith(".txt"):
            for name, ver, line in parse_requirements(ctx, rel):
                packages.append({"eco": "python", "name": name, "version": ver, "source": rel,
                                 "line": line})
        elif base.endswith(".csproj"):
            for name, ver, line in parse_csproj(ctx, rel):
                packages.append({"eco": "dotnet", "name": name, "version": ver, "source": rel,
                                 "line": line})
    packages.sort(key=lambda p: (p["eco"], p["name"].lower(), p["source"], p["line"]))
    direct = direct_deps(ctx)
    for p in packages:
        d = direct.get(p["eco"])
        key = _norm_py(p["name"]) if p["eco"] == "python" else p["name"]
        if p["eco"] == "go":
            p["direct"] = not p.get("indirect", False)
        else:
            p["direct"] = bool(d and key in d) if d is not None else None

    # stdlib × terceiros a partir dos imports externos do grafo
    g = ctx.layer("L1")
    ext = g["external"]
    std = py_stdlib()
    split = {}
    if "python" in ext:
        local_top = set(f.split("/")[0] for f in ctx.files)
        pys = {"stdlib": {}, "third_party": {}}
        for name, n in ext["python"].items():
            if name in local_top or name + ".py" in local_top:
                continue
            pys["stdlib" if name in std else "third_party"][name] = n
        split["python"] = pys
    for lang in ("javascript", "typescript"):
        if lang in ext:
            s = split.setdefault("node", {"stdlib": {}, "third_party": {}})
            for name, n in ext[lang].items():
                bare = name[5:] if name.startswith("node:") else name
                bucket = "stdlib" if bare in NODE_BUILTINS else "third_party"
                s[bucket][name] = s[bucket].get(name, 0) + n
    for eco in sorted(split):
        s = split[eco]
        users = []
        for lang in (("python",) if eco == "python" else ("javascript", "typescript")):
            for f in g["nodes"]:
                if f["lang"] == lang:
                    users.append(f["path"])
        top_std = sorted(s["stdlib"].items(), key=lambda kv: (-kv[1], kv[0]))[:10]
        top_tp = sorted(s["third_party"].items(), key=lambda kv: (-kv[1], kv[0]))[:10]
        ev = ev_cmd("scan:L8 classificação de imports externos (%s)" % eco, 0,
                    json.dumps(s, sort_keys=True).encode("utf-8"))
        if not s["third_party"]:
            facts.append(fb.fact("stack.%s.stdlib-only" % eco, LAYER,
                                 "%s usa só a biblioteca padrão: nenhum import de terceiros; stdlib mais "
                                 "usada: %s" % (eco, ", ".join("%s (%d)" % kv for kv in top_std)),
                                 [ev] + [ev_file(u) for u in sorted(users)[:3]], confidence="high",
                                 scope=["**"]))
        else:
            facts.append(fb.fact("stack.%s.imports" % eco, LAYER,
                                 "%s importa %d módulos de terceiros (%s) e %d da stdlib" % (
                                     eco, len(s["third_party"]),
                                     ", ".join("%s (%d)" % kv for kv in top_tp),
                                     len(s["stdlib"])),
                                 [ev], confidence="high", scope=["**"]))

    # fatos de versão: diretas (ou todas, se não há manifesto que diga quem é direta), com teto
    shown = [p for p in packages if p.get("direct") is not False][:150]
    for p in shown:
        facts.append(fb.fact("stack.%s.%s" % (p["eco"], slug(p["name"])), LAYER,
                             "%s %s %s (%s:%d%s)" % (p["eco"], p["name"], p["version"], p["source"],
                                                     p["line"], ", direta" if p.get("direct") else ""),
                             [ev_file(p["source"], p["line"])], scope=["**"]))

    # críticas: diretas mais importadas no código (L1), depois ordem alfabética
    usage = {}
    for lang, d in ext.items():
        for name, n in d.items():
            usage[name.lower()] = usage.get(name.lower(), 0) + n
    cands = [p for p in packages if p.get("direct") and p["eco"] in ("python", "node", "go")]

    def crit_key(p):
        n = p["name"].lower()
        u = max(usage.get(n, 0), usage.get(n.replace("-", "_"), 0), usage.get(n.split("/")[-1], 0))
        return (-u, p["eco"], n)
    seen, critical = set(), []
    for p in sorted(cands, key=crit_key):
        k = (p["eco"], p["name"])
        if k not in seen:
            seen.add(k)
            critical.append(p)
    critical = critical[:ctx.opts.max_deps]
    apis = []
    for p in critical:
        r = introspect(ctx, p["eco"], p["name"]) if ctx.opts.introspect else None
        entry = {"eco": p["eco"], "name": p["name"], "lock_version": p["version"]}
        if r is None:
            entry.update({"status": "declared", "reason": "--no-exec" if not ctx.opts.introspect
                          else "runtime ausente"})
        else:
            entry.update({"status": r["status"], "installed_version": r.get("version"),
                          "api": r.get("api", []), "error": r.get("error"), "cmd": r["cmd"]})
            if r["status"] == "introspected":
                match = (r.get("version") in (None, p["version"]))
                entry["matches_lock"] = match
                facts.append(fb.fact("stack.api.%s.%s" % (p["eco"], slug(p["name"])), LAYER,
                                     "API pública de %s %s (instalado %s%s): %s" % (
                                         p["name"], p["version"], r.get("version") or "?",
                                         "" if match else ", DIVERGE do lock",
                                         ", ".join(a["name"] for a in r.get("api", [])[:25])),
                                     [ev_file(p["source"], p["line"]),
                                      ev_cmd(r["cmd"], r["exit"], r["out"])],
                                     confidence="high" if match else "low", scope=["**"]))
        apis.append(entry)
    if not packages and not split:
        facts.append(fb.fact("stack.none", LAYER,
                             "Nenhum lockfile/pin nem import externo detectado",
                             [ev_cmd("scan:L8 busca de lockfiles", 1, b"")], scope=["**"]))
    langs = ctx.layer("L0")["languages"]
    main = sorted(((v["loc"], k) for k, v in langs.items() if v["code"]), reverse=True)[:5]
    if main:
        facts.append(fb.fact("stack.languages", LAYER,
                             "Linguagens principais por LOC: %s" % ", ".join("%s (%d)" % (k, n)
                                                                             for n, k in main),
                             [ctx.ls_evidence], scope=["**"]))
    stack = {"layer": LAYER, "packages": packages, "imports_split": split, "critical_api": apis,
             "introspection": bool(ctx.opts.introspect), "facts": facts}
    from . import stack_graph
    return {"_outputs": {LAYER: stack, stack_graph.LAYER: stack_graph.build(ctx, stack)}}
