"""stack_graph.json5 (§8-nonies): linguagem → runtime → framework → lib, com versão do lockfile e as
pastas onde cada lib é importada. Grafo `{nodes:[...], edges:[...]}` (sem Mermaid)."""

import posixpath
import re

from cslib.evidence import ev_cmd, ev_file, slug
from cslib.jsonio import dumps

LAYER = "stack_graph"

FRAMEWORKS = {
    "python": {"django", "flask", "fastapi", "starlette", "pyramid", "tornado", "aiohttp", "celery",
               "sqlalchemy", "pydantic", "pytest", "scrapy", "streamlit", "torch", "tensorflow",
               "pandas", "numpy", "airflow", "dagster", "langchain"},
    "node": {"react", "next", "vue", "nuxt", "@angular/core", "svelte", "@sveltejs/kit", "express",
             "fastify", "koa", "@nestjs/core", "electron", "react-native", "jest", "vitest", "mocha",
             "vite", "webpack", "prisma", "@prisma/client", "typeorm", "mongoose", "remix", "astro"},
    "go": {"github.com/gin-gonic/gin", "github.com/labstack/echo/v4", "github.com/gofiber/fiber/v2",
           "google.golang.org/grpc", "gorm.io/gorm", "github.com/spf13/cobra"},
    "rust": {"tokio", "actix-web", "axum", "rocket", "serde", "diesel", "sqlx", "bevy"},
    "ruby": {"rails", "sinatra", "rspec", "sidekiq", "hanami"},
    "php": {"laravel/framework", "symfony/symfony", "symfony/framework-bundle", "phpunit/phpunit"},
    "java": {"org.springframework.boot:spring-boot-starter", "org.springframework:spring-core",
             "io.quarkus:quarkus-core", "io.micronaut:micronaut-core", "org.junit.jupiter:junit-jupiter"},
    "dotnet": {"Microsoft.AspNetCore.App", "Microsoft.EntityFrameworkCore", "xunit", "NUnit",
               "MediatR", "Microsoft.NET.Sdk.Web"},
}
LANG_ECO = {"python": "python", "javascript": "node", "typescript": "node", "vue": "node",
            "svelte": "node", "go": "go", "rust": "rust", "ruby": "ruby", "php": "php", "java": "java",
            "kotlin": "java", "csharp": "dotnet"}
RUNTIME_NAME = {"python": "cpython", "node": "node", "go": "go", "rust": "rustc", "ruby": "ruby",
                "php": "php", "java": "jvm", "dotnet": "dotnet"}
PY_IMPORT_ALIAS = {"pyyaml": "yaml", "beautifulsoup4": "bs4", "pillow": "PIL", "scikit-learn": "sklearn",
                   "python-dateutil": "dateutil", "opencv-python": "cv2", "attrs": "attr",
                   "protobuf": "google", "msgpack-python": "msgpack", "pyjwt": "jwt",
                   "python-dotenv": "dotenv", "psycopg2-binary": "psycopg2"}


def runtime_decls(ctx):
    """[(eco, versão, arquivo, linha, fonte)] declarados no repo."""
    out = []
    simple = {".python-version": "python", ".nvmrc": "node", ".node-version": "node",
              ".ruby-version": "ruby", "rust-toolchain": "rust", ".java-version": "java"}
    for rel in ctx.files:
        base = rel.rsplit("/", 1)[-1]
        lines = ctx.lines(rel) if not ctx.is_binary(rel) else []
        if base in simple and lines:
            out.append((simple[base], lines[0].strip(), rel, 1, base))
        elif base == ".tool-versions":
            for i, ln in enumerate(lines, 1):
                m = re.match(r"^(python|nodejs|golang|ruby|rust|java|php)\s+(\S+)", ln)
                if m:
                    eco = {"nodejs": "node", "golang": "go"}.get(m.group(1), m.group(1))
                    out.append((eco, m.group(2), rel, i, base))
        elif base == "pyproject.toml":
            for i, ln in enumerate(lines, 1):
                m = re.match(r'^\s*requires-python\s*=\s*"([^"]+)"', ln) or \
                    re.match(r'^\s*python\s*=\s*"([^"]+)"', ln)
                if m:
                    out.append(("python", m.group(1), rel, i, "pyproject"))
                    break
        elif base == "package.json":
            for i, ln in enumerate(lines, 1):
                m = re.match(r'^\s*"node"\s*:\s*"([^"]+)"', ln)
                if m:
                    out.append(("node", m.group(1), rel, i, "engines"))
        elif base == "go.mod":
            for i, ln in enumerate(lines, 1):
                m = re.match(r"^go\s+(\S+)", ln)
                if m:
                    out.append(("go", m.group(1), rel, i, "go.mod"))
        elif base == "rust-toolchain.toml":
            m = re.search(r'channel\s*=\s*"([^"]+)"', "\n".join(lines))
            if m:
                out.append(("rust", m.group(1), rel, 1, base))
        elif base == "global.json":
            m = re.search(r'"version"\s*:\s*"([^"]+)"', "\n".join(lines))
            if m:
                out.append(("dotnet", m.group(1), rel, 1, "global.json"))
        elif base.endswith(".csproj"):
            for i, ln in enumerate(lines, 1):
                m = re.search(r"<TargetFrameworks?>([^<]+)<", ln)
                if m:
                    out.append(("dotnet", m.group(1), rel, i, "TargetFramework"))
        elif base == "Gemfile":
            for i, ln in enumerate(lines, 1):
                m = re.match(r"^\s*ruby\s+['\"]([^'\"]+)", ln)
                if m:
                    out.append(("ruby", m.group(1), rel, i, "Gemfile"))
    return sorted(set(out))


def import_name(eco, pkg):
    if eco == "python":
        low = pkg.lower()
        return PY_IMPORT_ALIAS.get(low, re.sub(r"[-.]", "_", low))
    if eco == "go":
        return pkg
    return pkg


def build(ctx, stack):
    g = ctx.layer("L1")
    langs = ctx.layer("L0")["languages"]
    nodes, edges = {}, set()

    def node(nid, **kw):
        if nid not in nodes:
            d = {"id": nid}
            d.update(kw)
            nodes[nid] = d
        return nid
    ecos_present = {}
    for lang, st in sorted(langs.items()):
        eco = LANG_ECO.get(lang)
        if st["code"] and eco:
            ecos_present.setdefault(eco, []).append(lang)
            node("lang:%s" % lang, kind="language", name=lang, files=st["files"], loc=st["loc"])
    for eco, decl_list in [(e, [d for d in runtime_decls(ctx) if d[0] == e]) for e in sorted(ecos_present)]:
        rid = node("runtime:%s" % eco, kind="runtime", name=RUNTIME_NAME.get(eco, eco),
                   versions=[{"version": v, "file": f, "line": ln, "source": src} for _, v, f, ln, src in decl_list])
        for lang in ecos_present[eco]:
            edges.add(("lang:%s" % lang, rid))
    # usos de import externo (do L1): (eco, nome) → pastas que importam
    used = {}
    for lang, names in sorted(getattr(ctx, "_ext_users", {}).items()):
        eco = LANG_ECO.get(lang)
        if not eco:
            continue
        for name, files in names.items():
            used.setdefault((eco, name.lower()), set()).update(posixpath.dirname(f) or "." for f in files)
    for p in stack["packages"]:
        if p.get("direct") is False:
            continue
        eco = p["eco"]
        imp = import_name(eco, p["name"]).lower()
        dirs = sorted(used.get((eco, imp), set()) | used.get((eco, p["name"].lower()), set()))
        is_fw = p["name"] in FRAMEWORKS.get(eco, ()) or p["name"].lower() in FRAMEWORKS.get(eco, ())
        nid = node("%s:%s:%s" % ("framework" if is_fw else "lib", eco, p["name"]),
                   kind="framework" if is_fw else "lib", eco=eco, name=p["name"],
                   version=p["version"], lock=p["source"], line=p["line"], dirs=dirs)
        rid = "runtime:%s" % eco
        if rid not in nodes:
            node(rid, kind="runtime", name=RUNTIME_NAME.get(eco, eco), versions=[])
        edges.add((rid, nid))
    # frameworks → libs do mesmo ecossistema que compartilham pastas de uso
    fws = [n for n in nodes.values() if n["kind"] == "framework"]
    for n in list(nodes.values()):
        if n["kind"] != "lib":
            continue
        for fw in fws:
            if fw["eco"] == n["eco"] and set(fw["dirs"]) & set(n["dirs"]):
                edges.add((fw["id"], n["id"]))
    # stdlib como nó explícito (mostra uso real mesmo sem lockfile)
    for eco, split in sorted(stack.get("imports_split", {}).items()):
        if split.get("stdlib"):
            dirs = sorted(set(d for name in split["stdlib"] for d in used.get((eco, name.lower()), ())))
            sid = node("lib:%s:stdlib" % eco, kind="lib", eco=eco, name="stdlib", version="runtime",
                       modules=sorted(split["stdlib"]), dirs=dirs)
            edges.add(("runtime:%s" % eco, sid))
    node_list = [nodes[k] for k in sorted(nodes)]
    edge_list = [{"from": a, "to": b} for a, b in sorted(edges)]
    fb = ctx.fb
    facts = []
    ev_graph = ev_cmd("scan:stack_graph", 0, dumps({"nodes": node_list, "edges": edge_list}).encode("utf-8"))
    for n in node_list:
        if n["kind"] == "runtime":
            ver = ", ".join("%s (%s:%d)" % (v["version"], v["file"], v["line"]) for v in n["versions"]) \
                or "versão não declarada"
            ev = [ev_file(v["file"], v["line"]) for v in n["versions"][:3]] or [ev_graph]
            facts.append(fb.fact("stackg.runtime.%s" % slug(n["id"].split(":", 1)[1]), LAYER,
                                 "Runtime %s: %s" % (n["name"], ver), ev, scope=["**"]))
        elif n["kind"] == "framework":
            facts.append(fb.fact("stackg.framework.%s" % slug(n["name"]), LAYER,
                                 "Framework %s %s (%s:%d) usado em: %s" % (
                                     n["name"], n["version"], n["lock"], n["line"],
                                     ", ".join(n["dirs"][:8]) or "nenhuma pasta (só declarado)"),
                                 [ev_file(n["lock"], n["line"])],
                                 scope=[d + "/**" if d != "." else "*" for d in n["dirs"]] or ["**"]))
    facts.append(fb.fact("stackg.summary", LAYER,
                         "Stack: %d linguagens, %d runtimes, %d frameworks, %d libs" % tuple(
                             sum(1 for n in node_list if n["kind"] == k)
                             for k in ("language", "runtime", "framework", "lib")),
                         [ev_graph], scope=["**"]))
    return {"layer": LAYER, "nodes": node_list, "edges": edge_list, "facts": facts}
