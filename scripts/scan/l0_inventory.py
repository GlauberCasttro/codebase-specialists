"""L0 inventário: arquivos, linguagens, manifestos, lockfiles, LOC; marca fixture/vendor/generated."""

from cslib import paths
from cslib.evidence import ev_file, slug
from . import represent

LAYER = "inventory"

MANIFESTS = {
    "package.json": "node", "pyproject.toml": "python", "setup.py": "python", "setup.cfg": "python",
    "Pipfile": "python", "go.mod": "go", "Cargo.toml": "rust", "Gemfile": "ruby",
    "composer.json": "php", "pom.xml": "java", "build.gradle": "java", "build.gradle.kts": "java",
    "Makefile": "make", "justfile": "just", "Justfile": "just", "tox.ini": "python",
    "Dockerfile": "docker", "deno.json": "node", "tsconfig.json": "node",
}
# linguagens que não são "código" para o grafo de imports mas são FONTE do produto (inventariadas)
SOURCE_LANGS = frozenset(["sql"])
LOCKFILES = {
    "poetry.lock": "python", "uv.lock": "python", "Pipfile.lock": "python",
    "package-lock.json": "node", "pnpm-lock.yaml": "node", "yarn.lock": "node",
    "npm-shrinkwrap.json": "node", "go.sum": "go", "Cargo.lock": "rust", "Gemfile.lock": "ruby",
    "composer.lock": "php", "packages.lock.json": "dotnet", "gradle.lockfile": "java",
}


def manifest_kind(rel):
    base = rel.rsplit("/", 1)[-1]
    if base in MANIFESTS:
        return MANIFESTS[base]
    if base.endswith(".csproj") or base.endswith(".fsproj"):
        return "dotnet"
    if base.startswith("requirements") and base.endswith(".txt"):
        return "python"
    return None


def lockfile_kind(rel):
    base = rel.rsplit("/", 1)[-1]
    if base in LOCKFILES:
        return LOCKFILES[base]
    if base.startswith("requirements") and base.endswith(".txt"):
        return "python"  # tratado como lock quando tem pins (L8 decide)
    return None


def loc(ctx, rel):
    if ctx.is_binary(rel):
        return 0
    return sum(1 for ln in ctx.lines(rel) if ln.strip())


def run(ctx):
    fb = ctx.fb
    files = []
    langs = {}
    ignored = {}
    examples = {}  # dir de exemplo → nº de arquivos (fora da análise, mas pode ter dono)
    for rel in ctx.all_files:
        cat = ctx.category[rel]
        lang = paths.lang_of(rel)
        entry = {"path": rel, "category": cat, "lang": lang}
        if cat in paths.NOT_ANALYZED_CATEGORIES:
            top = rel.split("/")
            # agrupa pelo diretório que causou a classificação (primeiro componente marcado)
            mark = rel
            for i, d in enumerate(top[:-1]):
                if d in paths.VENDOR_DIRS or d in paths.FIXTURE_DIRS or d in paths.GENERATED_DIRS \
                        or d in paths.EXAMPLE_DIRS:
                    mark = "/".join(top[:i + 1]) + "/"
                    break
            bucket = examples if cat == paths.CAT_EXAMPLE else ignored.setdefault(cat, {})
            bucket[mark] = bucket.get(mark, 0) + 1
        else:
            n = loc(ctx, rel)
            entry["loc"] = n
            if paths.is_test_file(rel):
                entry["test"] = True
            st = langs.setdefault(lang, {"files": 0, "loc": 0, "code": lang in paths.CODE_LANGS})
            st["files"] += 1
            st["loc"] += n
        files.append(entry)

    manifests = sorted(f for f in ctx.files if manifest_kind(f))
    lockfiles = sorted(f for f in ctx.files if lockfile_kind(f)
                       and not (f.rsplit("/", 1)[-1].startswith("requirements")))
    reserved = sorted(f for f in ctx.files if ctx.category[f] == paths.CAT_RESERVED)

    facts = []
    n_ign = sum(sum(v.values()) for v in ignored.values())
    facts.append(fb.fact(
        "inv.total", LAYER,
        "%d arquivos listados: %d analisáveis (%d produto, %d reservados ao harness), %d ignorados "
        "(fixture/vendor/generated)%s" % (len(ctx.all_files), len(ctx.files), len(ctx.product_files),
                                          len(reserved), n_ign,
                                          (", %d de exemplo (fora da análise, com dono possível)"
                                           % sum(examples.values())) if examples else ""),
        [ctx.ls_evidence], scope=["**"]))
    code_langs = sorted(((v["loc"], k) for k, v in langs.items() if v["code"] or k in SOURCE_LANGS),
                        reverse=True)
    for n, lang in code_langs:
        st = langs[lang]
        sample = sorted(f for f in ctx.files if paths.lang_of(f) == lang)
        comps = sorted(set(paths.component_of(f) for f in sample))
        facts.append(fb.fact(
            "inv.lang.%s" % lang, LAYER,
            "%s: %d arquivos, %d linhas não-vazias" % (lang, st["files"], st["loc"]),
            [ev_file(f) for f in sample[:5]] + [ctx.ls_evidence],
            scope=[c + "/**" if c != "." else "*" for c in comps]))
    for m in manifests:
        facts.append(fb.fact("inv.manifest.%s" % slug(m), LAYER,
                             "Manifesto %s (%s) em %s" % (m.rsplit("/", 1)[-1], manifest_kind(m), m),
                             [ev_file(m)], scope=[m]))
    for lf in lockfiles:
        facts.append(fb.fact("inv.lockfile.%s" % slug(lf), LAYER,
                             "Lockfile %s (%s) em %s" % (lf.rsplit("/", 1)[-1], lockfile_kind(lf), lf),
                             [ev_file(lf)], scope=[lf]))
    for cat in sorted(ignored):
        groups = ignored[cat]
        top = sorted(groups.items(), key=lambda kv: (-kv[1], kv[0]))
        desc = ", ".join("%s (%d)" % (k, v) for k, v in top[:8])
        facts.append(fb.fact("inv.ignored.%s" % cat, LAYER,
                             "%d arquivos %s ignorados em toda análise: %s" % (sum(groups.values()),
                                                                              cat, desc),
                             [ctx.ls_evidence], scope=sorted(k + "**" if k.endswith("/") else k
                                                             for k in groups)))
    for mark in sorted(examples):
        sample = sorted(f for f in ctx.all_files if f.startswith(mark))
        langs_ex = sorted(set(paths.lang_of(f) for f in sample if paths.is_code(f)))
        facts.append(fb.fact("inv.example.%s" % slug(mark.rstrip("/")), LAYER,
                             "%s: %d arquivos de EXEMPLO (%s) — código de uso/cliente fora do produto: "
                             "não entra em stack, regras nem convenções do scan, mas pode ter dono de "
                             "escrita (não é fixture de teste)" % (
                                 mark, examples[mark], ", ".join(langs_ex) or "sem código"),
                             [ev_file(f) for f in sample[:3]] + [ctx.ls_evidence], confidence="high",
                             scope=[mark + "**"], data={"category": paths.CAT_EXAMPLE, "dir": mark,
                                                         "files": examples[mark], "langs": langs_ex}))
    if reserved:
        prefixes = sorted(set(p for p in paths.RESERVED_PREFIXES for f in reserved
                              if f.startswith(p)))
        facts.append(fb.fact("inv.reserved", LAYER,
                             "%d arquivos sob prefixos reservados ao harness (%s): nunca entram em "
                             "território de produto" % (len(reserved), ", ".join(prefixes)),
                             [ctx.ls_evidence], scope=[p + "**" for p in prefixes]))
    if ctx.outside_links:
        facts.append(fb.fact("inv.symlinks-outside", LAYER,
                             "%d symlinks apontam para fora do alvo e foram ignorados"
                             % len(ctx.outside_links), [ctx.ls_evidence],
                             scope=ctx.outside_links))
    reps = represent.representatives(ctx)
    for r in reps:
        if r["category"] != paths.CAT_PRODUCT:
            continue
        facts.append(fb.fact("inv.dir.%s" % slug(r["dir"]), LAYER,
                             "Pasta %s (%d arquivos): representativo %s — %s" % (
                                 r["dir"], r["files"], r["representative"], r["reason"]),
                             [ev_file(r["representative"])], confidence="high",
                             scope=[r["dir"] + "/*" if r["dir"] != "." else "*"]))
    return {
        "layer": LAYER,
        "directories": reps,
        "files": files,
        "languages": langs,
        "manifests": [{"path": m, "kind": manifest_kind(m)} for m in manifests],
        "lockfiles": [{"path": m, "kind": lockfile_kind(m)} for m in lockfiles],
        "ignored": ignored,
        "examples": examples,
        "reserved_prefixes": list(paths.RESERVED_PREFIXES),
        "symlinks_outside": ctx.outside_links,
        "facts": facts,
    }
