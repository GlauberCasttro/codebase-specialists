"""cs.py team derive — propõe o roster a partir dos fatos (nunca de LLM).

Pipeline determinístico (cada passo registra decisão + porquê em team-derivation.json5):
  1. produto = inventário sem fixture/vendor/generated/reservados;
  2. papéis especializados reivindicam arquivos por sinal: ops (CI/IaC/Docker), qa (diretórios de
     teste de TOPO), dba (migrações), po (docs de produto), architect (ADRs/docs). Teste CO-LOCALIZADO
     (`x_test.go`, `a.test.ts`, `pkg/tests/`) é do dono do diretório de código — regra explícita
     `test_ownership` no team.json5 — para o território ser um glob de diretório (arquivo novo tem dono);
  3. o resto é fonte: unidades pela árvore de diretórios (contêineres src/apps/services/... descem um
     nível; cadeias de filho único descem) com fronteira em manifestos aninhados;
  4. utilitário compartilhado por NOME (shared/common/utils/...) vira um dev próprio (`dev-shared`), nunca
     território do architect, e entra em `reads` de todos os devs; núcleo de DOMÍNIO detectado por fan-in
     (≥60% das unidades importam) continua bounded context com dono dev (não é "utils") e entra em `reads`
     de quem o importa. Kernel de domínio ≠ utils compartilhado; architect só tem docs/ADRs;
  5. consolida prefixo repetido (billing-api + billing-worker → billing);
  6. funde unidades minúsculas na unidade mais acoplada (arestas do grafo L1), sem descer abaixo de 3 devs e
     sem fundir núcleo/compartilhado; unidade fundida é nomeada pela maior parte (nada de guarda-chuva com
     nome de uma parte pequena);
  7. limita a 3–8 devs (funde o par mais acoplado; divide a maior por subdiretório/comunidade);
  8. unidade majoritariamente UI vira `frontend`;
  9. território = compressão disjunta por construção (dir/** só quando a subárvore inteira é do dono).
"""
import math
import os
import re

from team._shared_tmp.common import (find_doc, CsError, VEREDITO_ENUM, compress, expand, glob_match, read_json,
                                     slug, sp_path, write_json)
from team._shared_tmp.factsio import Facts, fact_files

CONTAINERS = {"src", "lib", "libs", "app", "apps", "packages", "services", "pkg", "internal", "cmd",
              "modules", "components", "domains", "contexts", "source", "sources", "projects", "crates"}
SHARED = {"shared", "common", "commons", "utils", "util", "helpers", "helper", "kernel", "sharedkernel",
          "shared-kernel", "shared_kernel", "toolkit", "lib-common", "libcommon", "support"}
GENERIC_PREFIX = {"api", "app", "web", "core", "service", "services", "svc", "lib", "common", "shared",
                  "server", "client", "cmd", "pkg", "test", "tests", "src", "my", "the"}
UI_EXT = {".tsx", ".jsx", ".vue", ".svelte", ".css", ".scss", ".sass", ".less", ".html", ".astro"}
UI_DIRS = {"web", "frontend", "ui", "client", "webapp", "www", "site", "dashboard", "portal", "front"}
SOURCE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".java", ".kt", ".cs", ".rb",
              ".rs", ".php", ".swift", ".c", ".h", ".cc", ".cpp", ".hpp", ".scala", ".dart", ".vue",
              ".svelte", ".ex", ".exs", ".lua", ".sh"}
TEST_TOP = ["tests/**", "test/**", "spec/**", "specs/**", "e2e/**", "__tests__/**", "testing/**",
            "integration-tests/**", "integration_tests/**"]
TEST_COLOCATED = ["**/tests/**", "**/test/**", "**/__tests__/**", "**/e2e/**", "**/test_*.py", "**/*_test.py",
            "**/*_test.go", "**/*.test.js", "**/*.test.jsx", "**/*.test.ts", "**/*.test.tsx", "**/*.spec.js",
            "**/*.spec.ts", "**/*.spec.tsx", "**/*Test.java", "**/*Tests.java", "**/*Test.kt",
            "**/*Tests.cs", "**/*Test.cs", "**/*_spec.rb", "**/*_test.rb", "**/*Test.php", "**/*_test.rs"]
OPS_PATTERNS = [".github/workflows/**", ".github/actions/**", ".gitlab-ci.yml", ".gitlab/**",
                ".circleci/**", "Jenkinsfile", "azure-pipelines.yml", ".travis.yml",
                "bitbucket-pipelines.yml", "**/Dockerfile", "**/Dockerfile.*", "**/*.dockerfile",
                "**/docker-compose*.yml", "**/docker-compose*.yaml", "**/compose.yml", "**/compose.yaml",
                "**/.dockerignore", "infra/**", "infrastructure/**", "terraform/**", "**/*.tf",
                "**/*.tfvars", "k8s/**", "kubernetes/**", "helm/**", "charts/**", "deploy/**",
                "deployment/**", "ansible/**", "Procfile", "fly.toml", "vercel.json", "netlify.toml",
                "skaffold.yaml", ".pre-commit-config.yaml"]
MIGRATION_PATTERNS = ["**/migrations/**", "**/migration/**", "**/db/migrate/**", "**/alembic/**",
                      "**/flyway/**", "**/liquibase/**", "**/db/changelog/**", "**/*.migration.sql"]
PO_PATTERNS = ["docs/product/**", "docs/requirements/**", "docs/stories/**", "docs/user-stories/**",
               "docs/refinamentos/**", "docs/prd/**", "docs/produto/**"]
ARCH_PATTERNS = ["docs/adr/**", "docs/adrs/**", "docs/decisions/**", "docs/decisoes/**", "doc/adr/**",
                 "adr/**", "adrs/**", "docs/architecture/**", "architecture/**", "docs/design/**",
                 "docs/**", "doc/**"]
WRITE_TOOLS = ["Read", "Grep", "Glob", "Bash", "Edit", "Write"]
READ_TOOLS = ["Read", "Grep", "Glob", "Bash"]
MIN_DEVS, MAX_DEVS = 3, 8
TEST_OWNERSHIP = {
    "top_level": "qa",  # diretórios de teste de topo (TEST_TOP)
    "colocated": "owner",  # teste ao lado do código = dono do diretório (glob de diretório cobre arquivo novo)
    "why": "territórios por glob de diretório: teste co-localizado novo já nasce com dono; qa não escreve no "
           "mesmo arquivo que o dev; qa é dono só dos diretórios de teste de topo",
}


def _ext(p):
    return os.path.splitext(p)[1].lower()


class Deriver(object):
    def __init__(self, facts):
        self.f = facts
        self.decisions = []
        self.product = facts.product_files()
        if not self.product:
            raise CsError("nenhum arquivo de produto no inventário",
                          "confira o scan L0 (todo arquivo classificado como fixture/vendor?)")
        self.owner = {}
        self.parts = {}  # unidade → {unidade original: nº de arquivos} (nome da unidade fundida = maior parte)
        self.shared_units, self.core_units = set(), set()
        self.edges = facts.edges() if facts.has_graph() else []
        self.comm = facts.communities() if facts.has_graph() else {}
        if not facts.has_graph():
            self.note("graph", "grafo L1 ausente", "sem fusão por acoplamento; empates por tamanho/nome",
                      level="warn")

    def note(self, step, decision, why, evidence=None, level="info"):
        self.decisions.append({"step": step, "decision": decision, "why": why,
                               "evidence": evidence or [], "level": level})

    # ------------------------------------------------------------ passo 2
    def claim(self, role, patterns, why):
        got = [f for f in self.product if f not in self.owner and any(glob_match(f, p) for p in patterns)]
        for f in got:
            self.owner[f] = role
        if got:
            self.note("roles", "%s reivindica %d arquivo(s)" % (role, len(got)), why, got[:10])
        return got

    # ------------------------------------------------------------ passo 3
    def initial_units(self, source):
        manifests = sorted((os.path.dirname(m) for m in self.f.manifests() if "/" in m),
                           key=lambda d: (-d.count("/"), d))
        units, pool = {}, []
        containers = self._containers(source)
        for p in source:
            md = next((d for d in manifests if p.startswith(d + "/")), None)
            if md:
                units.setdefault(md, []).append(p)
                continue
            key = None
            for c in containers:
                if p.startswith(c + "/"):
                    rest = p[len(c) + 1:].split("/")
                    key = (c + "/" + rest[0]) if len(rest) > 1 else None
                    break
            else:
                parts = p.split("/")
                key = parts[0] if len(parts) > 1 else None
            if key is None:
                pool.append(p)
            else:
                units.setdefault(key, []).append(p)
        if manifests:
            self.note("units", "fronteira em manifesto aninhado: %s" % ", ".join(sorted(set(manifests))),
                      "manifesto próprio = pacote/serviço independente", sorted(set(manifests)))
        self.note("units", "contêineres de código: %s" % (", ".join(containers) or "nenhum"),
                  "contêiner genérico (src/apps/services/...) desce um nível; cadeia de filho único desce")
        return units, pool

    def _containers(self, source):
        tops = sorted(set(p.split("/")[0] for p in source if "/" in p))
        out = []
        for t in tops:
            if t not in CONTAINERS:
                continue
            c = t
            while True:
                under = [p[len(c) + 1:] for p in source if p.startswith(c + "/")]
                subdirs = sorted(set(u.split("/")[0] for u in under if "/" in u))
                direct = [u for u in under if "/" not in u]
                if len(subdirs) == 1 and len(direct) <= 2:
                    nested = [u for u in under if u.startswith(subdirs[0] + "/")]
                    if any("/" in n[len(subdirs[0]) + 1:] for n in nested):
                        c = c + "/" + subdirs[0]
                        continue
                break
            out.append(c)
        return sorted(out, key=lambda x: (-x.count("/"), x))

    # ------------------------------------------------------------ helpers de grafo
    def unit_of(self, units):
        m = {}
        for u, fs in units.items():
            for p in fs:
                m[p] = u
        return m

    def coupling(self, units):
        uo = self.unit_of(units)
        c = {}
        for a, b in self.edges:
            ua, ub = uo.get(a), uo.get(b)
            if ua and ub and ua != ub:
                k = tuple(sorted((ua, ub)))
                c[k] = c.get(k, 0) + 1
        return c

    def fan_in(self, units):
        uo = self.unit_of(units)
        fi = {}
        for a, b in self.edges:
            ua, ub = uo.get(a), uo.get(b)
            if ua and ub and ua != ub:
                fi.setdefault(ub, set()).add(ua)
        return fi

    def merge(self, units, src, dst, why):
        units[dst] = sorted(units[dst] + units.pop(src))
        self.parts.setdefault(dst, {dst: 0})
        for k, v in self.parts.pop(src, {src: 0}).items():
            self.parts[dst][k] = self.parts[dst].get(k, 0) + v
        for k in (src, dst):
            if k in self.shared_units or k in self.core_units:
                (self.shared_units if k in self.shared_units else self.core_units).add(dst)
        self.note("merge", "%s → %s" % (src, dst), why)

    # ------------------------------------------------------------ pipeline
    def run(self):
        f = self.f
        # 2. papéis por sinal
        ops = self.claim("ops", OPS_PATTERNS, "sinal de CI/IaC/Docker")
        qa = self.claim("qa", TEST_TOP, "diretórios de teste de topo (teste co-localizado fica com o dono do "
                                         "diretório: test_ownership.colocated = owner)")
        dba = self.claim("dba", MIGRATION_PATTERNS, "sinal de migrações de banco")
        po = self.claim("po", PO_PATTERNS, "docs de produto/requisitos")
        arch = self.claim("architect", ARCH_PATTERNS, "ADRs e documentação de desenho")
        source = [p for p in self.product if p not in self.owner]

        # 3. unidades
        units, pool = self.initial_units(source)
        self.parts = {u: {u: len(fs)} for u, fs in units.items()}
        # 4. compartilhado por nome → dev próprio; núcleo de domínio por fan-in → continua unidade (dono dev)
        self.shared_units, self.core_units = set(), set()
        fi = self.fan_in(units)
        for u in sorted(units):
            base = u.rsplit("/", 1)[-1].lower()
            fan = len(fi.get(u, ())) if len(units) >= 4 else 0
            if base in SHARED:
                self.shared_units.add(u)
                self.note("kernel", "%s é utilitário compartilhado: dev próprio, reads de todos os devs" % u,
                          "nome de kernel/utils compartilhado (nunca território do architect)", units[u][:5])
            elif fan >= max(3, math.ceil(0.6 * (len(units) - 1))):
                self.core_units.add(u)
                self.note("kernel", "%s é núcleo de domínio: bounded context com dono dev, reads de quem importa" % u,
                          "fan-in de %d/%d unidades (grafo L1); regra de negócio central não vai ao architect"
                          % (fan, len(units) - 1), units[u][:5])
        kernel_files = []
        # 5. prefixo repetido
        groups = {}
        for u in sorted(units):
            tok = re.split(r"[-_.]", u.rsplit("/", 1)[-1].lower())[0]
            if tok and tok not in GENERIC_PREFIX and len(tok) >= 3:
                groups.setdefault((u.rsplit("/", 1)[0] if "/" in u else "", tok), []).append(u)
        for (parent, tok), us in sorted(groups.items()):
            if len(us) >= 2:
                newk = (parent + "/" if parent else "") + tok + "*"
                units[newk] = sorted(sum((units.pop(x) for x in us), []))
                self.parts[newk] = {newk: len(units[newk])}
                for x in us:
                    for flag in (self.shared_units, self.core_units):
                        if x in flag:
                            flag.add(newk)
                self.note("prefix", "consolida %s em '%s'" % (", ".join(us), tok),
                          "prefixo de nome repetido = um bounded context em várias implantações")
        # pool de arquivos soltos (raiz / direto no contêiner)
        leftovers = []
        for p in sorted(pool):
            if _ext(p) not in SOURCE_EXT:
                leftovers.append(p)
                continue
            best = self._best_unit_for_file(p, units)
            if best:
                units[best].append(p)
                self.note("pool", "%s → %s" % (p, best), "arquivo solto anexado à unidade mais acoplada")
            else:
                units.setdefault("(root)", []).append(p)
        # 6. minúsculas
        total = sum(len(v) for v in units.values()) or 1
        thr = max(3, int(math.ceil(0.02 * total)))
        protected = self.shared_units | self.core_units
        changed = True
        while changed and len(units) > MIN_DEVS:
            changed = False
            for u in sorted(units, key=lambda x: (len(units[x]), x)):
                if len(units[u]) < thr and u not in protected:
                    tgt = self._most_coupled(u, units, avoid=protected)
                    self.merge(units, u, tgt, "unidade minúscula (%d < %d arquivos); mais acoplada/irmã"
                               % (len(units[u]), thr))
                    changed = True
                    break
        # 7. limites
        while len(units) > MAX_DEVS:
            a, b = self._merge_pair(units)
            self.merge(units, a, b, "limite de %d devs: par mais acoplado" % MAX_DEVS)
        guard = 0
        while len(units) < MIN_DEVS and guard < 10:
            guard += 1
            if not self._split_largest(units):
                self.note("limits", "time com %d dev(s)" % len(units),
                          "repo pequeno demais para %d contextos sem fragmentar" % MIN_DEVS, level="warn")
                break
        # 8. nomes e frontend
        names = self._name_units(units)
        for u, n in names.items():
            for p in units[u]:
                self.owner[p] = n
        # 7-bis. sobras (arquivos de raiz não-fonte, configs)
        lo_owner = "ops" if ops else "architect"
        for p in leftovers:
            self.owner[p] = lo_owner
        if leftovers:
            self.note("leftovers", "%d arquivo(s) de raiz/config → %s" % (len(leftovers), lo_owner),
                      "config/manifesto repo-wide: ops se existe sinal de operação, senão architect",
                      leftovers[:10])
        missing = [p for p in self.product if p not in self.owner]
        if missing:
            raise CsError("bug: %d arquivo(s) de produto sem dono após derivação" % len(missing))
        return self._build(names, units, kernel_files, dict(ops=ops, qa=qa, dba=dba, po=po, arch=arch))

    def _best_unit_for_file(self, p, units):
        uo = self.unit_of(units)
        score = {}
        for a, b in self.edges:
            if a == p and b in uo:
                score[uo[b]] = score.get(uo[b], 0) + 1
            if b == p and a in uo:
                score[uo[a]] = score.get(uo[a], 0) + 1
        if not score:
            return None
        return sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

    def _most_coupled(self, u, units, avoid=()):
        c = self.coupling(units)
        cands = []
        pool = [v for v in units if v != u and v not in avoid] or [v for v in units if v != u]
        for v in pool:
            if v == u:
                continue
            w = c.get(tuple(sorted((u, v))), 0)
            sib = 1 if (u.rsplit("/", 1)[0] == v.rsplit("/", 1)[0]) else 0
            cands.append((-w, -sib, -len(units[v]), v))
        return sorted(cands)[0][3]

    def _merge_pair(self, units):
        c = self.coupling(units)
        best = None
        ks = sorted(units)
        for i, a in enumerate(ks):
            for b in ks[i + 1:]:
                w = c.get((a, b), 0) / float(min(len(units[a]), len(units[b])) or 1)
                size = len(units[a]) + len(units[b])
                key = (-w, size, a, b)
                if best is None or key < best:
                    best = key
        a, b = best[2], best[3]
        return (a, b) if len(units[a]) <= len(units[b]) else (b, a)

    def _split_largest(self, units):
        for u in sorted(units, key=lambda x: (-len(units[x]), x)):
            fs = units[u]
            prefix = os.path.commonpath(fs) if len(fs) > 1 else ""
            if prefix in fs:
                prefix = os.path.dirname(prefix)
            pre = prefix + "/" if prefix else ""
            subs = {}
            direct = []
            for p in fs:
                rest = p[len(pre):]
                if "/" in rest:
                    subs.setdefault(pre + rest.split("/")[0], []).append(p)
                else:
                    direct.append(p)
            big = {k: v for k, v in subs.items() if len(v) >= 2}
            if len(big) >= 2:
                units.pop(u)
                for k, v in sorted(subs.items()):
                    units[k] = v
                if direct:
                    tgt = sorted(subs, key=lambda k: (-len(subs[k]), k))[0]
                    units[tgt] = sorted(units[tgt] + direct)
                for k in [k for k in subs if len(subs[k]) < 2]:
                    if k in units and len(units) > 2:
                        self.merge(units, k, self._most_coupled(k, units), "sub-unidade de 1 arquivo")
                self.note("split", "divide %s por subdiretório" % u, "menos de %d devs" % MIN_DEVS)
                return True
            groups = {}
            for p in fs:
                groups.setdefault(self.comm.get(p, "?"), []).append(p)
            big = {k: v for k, v in groups.items() if len(v) >= 2 and k != "?"}
            if len(big) >= 2:
                units.pop(u)
                rest = []
                for k, v in sorted(groups.items()):
                    if k in big:
                        units["%s#c%s" % (u, k)] = v
                    else:
                        rest += v
                if rest:
                    tgt = sorted(big, key=lambda k: (-len(big[k]), k))[0]
                    units["%s#c%s" % (u, tgt)] += rest
                self.note("split", "divide %s por comunidade do grafo" % u, "menos de %d devs" % MIN_DEVS)
                return True
        return False

    def _name_units(self, units):
        names, used = {}, {"ops", "qa", "dba", "po", "architect", "reviewer", "security"}
        ui_units = [u for u in sorted(units) if self._is_ui(units[u])]
        for u in sorted(units):
            parts = self.parts.get(u) or {u: 1}
            major = sorted(parts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if parts else u
            if major != u and u not in self.shared_units:
                self.note("naming", "unidade %s nomeada pela maior parte (%s)" % (u, major),
                          "nome de uma parte pequena vira guarda-chuva enganoso", sorted(parts))
            else:
                major = u
            base = major.split("#")[0].rstrip("*")
            base = base.rsplit("/", 1)[-1] or "root"
            if base == "(root)":
                base = "core"
            if u in ui_units:
                n = "frontend" if len(ui_units) == 1 else "frontend-" + slug(base)
                self.note("frontend", "%s é UI → %s" % (u, n), "≥50% dos arquivos são UI (ext/diretório)")
            else:
                n = "dev-" + slug(base)
            n = n[:40]
            k, cand = 2, n
            while cand in used or cand in names.values():
                cand = "%s-%d" % (n[:37], k)
                k += 1
            used.add(cand)
            names[u] = cand
        return names

    def _is_ui(self, fs):
        ui = sum(1 for p in fs if _ext(p) in UI_EXT or any(d in UI_DIRS for d in p.split("/")[:-1]))
        return ui * 2 >= len(fs) and len(fs) > 0

    # ------------------------------------------------------------ montagem
    def _build(self, names, units, kernel_files, signal):
        f = self.f
        boundary = list(self.product) + f.reserved_files()
        own = dict(self.owner)
        for r in f.reserved_files():
            own[r] = "__reserved__"
        terr = compress(own, sorted(set(boundary)))
        shared_names = sorted(set(names[u] for u in units if u in self.shared_units))
        shared_reads = sorted(set(g for n in shared_names for g in terr.get(n, [])))
        dev_imports = self._imports_between(names, units)
        agents = []

        def add(name, kind, territory, reads, why, tools=None):
            files = expand(territory, self.product)
            is_gate = kind == "gate"
            inv, used = agent_fact_sets(f, name, kind, files)
            ag = {"name": name, "kind": kind, "territory": territory, "reads": reads,
                  "tools": tools or (READ_TOOLS if (is_gate or not territory) else WRITE_TOOLS),
                  "model": "inherit", "card": None, "invariants": inv, "facts_used": used}
            if is_gate:
                ag["gate_scope"] = "security" if name == "security" else "all"
            agents.append(ag)
            self.note("roster", "%s (%s): %d arquivo(s) de escrita" % (name, kind, len(files)), why)

        for u in sorted(units, key=lambda x: names[x]):
            n = names[u]
            reads = sorted((set(shared_reads) - set(terr.get(n, []))) |
                           set(g for m in sorted(dev_imports.get(n, ())) for g in terr.get(m, [])))
            why = "bounded context derivado de %s" % u
            if u in self.shared_units:
                why = "utilitário compartilhado (%s): dono dev, lido por todos os devs" % u
            elif u in self.core_units:
                why = "núcleo de domínio (%s): bounded context com dono dev" % u
            add(n, "dev", terr.get(n, []), reads, why)
        add("reviewer", "gate", [], ["**"], "gate de qualidade (sempre): julga tudo; qualquer FAIL vence")
        add("security", "gate", [], ["**"], "gate de segurança (sempre): julga só regras de segurança")
        add("qa", "dev", terr.get("qa", []), ["**"],
            "testes de topo (sempre; território vazio se não há diretório de testes de topo)" if not signal["qa"]
            else "dono dos diretórios de teste de topo (teste co-localizado é do dono do diretório)")
        add("architect", "design", terr.get("architect", []), ["**"], "desenho, ADRs e docs (sempre)")
        add("po", "product", terr.get("po", []), ["**"], "produto/requisitos (sempre)")
        if signal["ops"] or "ops" in terr:
            add("ops", "ops", terr.get("ops", []), ["**"], "sinal de CI/IaC/Docker")
        else:
            self.note("roster", "sem ops", "nenhum sinal de CI/IaC/Docker")
        if signal["dba"]:
            add("dba", "dev", terr.get("dba", []), ["**"], "sinal de migrações")
        else:
            self.note("roster", "sem dba", "nenhuma migração encontrada")
        return agents

    def _imports_between(self, names, units):
        uo = {}
        for u, fs in units.items():
            for p in fs:
                uo[p] = names[u]
        out = {}
        for a, b in self.edges:
            na, nb = uo.get(a), uo.get(b)
            if na and nb and na != nb:
                out.setdefault(na, set()).add(nb)
        return out

SECURITY_WORDS = ("secur", "segur", "secret", "segredo", "token", "auth", "password", "senha", "credential",
                  "credencia", "crypt", "cifr", "hash", "inject", "injeç", "sanitiz", "escape", "xss", "csrf",
                  "cors", "jwt", "tls", "ssl", "cert", "permiss", "privileg", "cve", "vuln", "api key", "apikey",
                  "api_key", "pii", "lgpd", "gdpr", "owasp", "bandit", "gosec", "semgrep", "sql injection")


def is_security_fact(fx):
    """Fato/invariante de segurança (para o gate `security`, que julga só isso)."""
    d = fx.get("data") or {}
    blob = " ".join(str(x) for x in (fx.get("id"), fx.get("claim"), d.get("tool"), d.get("kind"), d.get("subject"),
                                     d.get("topic"), d.get("pattern"))).lower()
    return any(w in blob for w in SECURITY_WORDS)


def is_negative_invariant(fx):
    """Invariante negativo medido pelo scan (`rules.never.*`: eval/exec/shell=True/pickle/unsafe/curl|sh… com 0
    ocorrências). O texto quase nunca tem palavra de segurança ("eval() tem 0 ocorrências"), por isso o filtro
    por palavra deixava o gate `security` sem NENHUM invariante (iteração 3, nos 3 alvos)."""
    d = fx.get("data") or {}
    return str(fx.get("id", "")).startswith("rules.never.") or str(d.get("kind") or "").lower() in (
        "negative", "negative_invariant", "never")


def gate_required(facts, scope="all"):
    """Invariantes que um gate precisa ter: regras + entrevista + regras de negócio + decisões (ADR);
    o gate `security` (gate_scope=security) só as de segurança + todos os invariantes negativos (rules.never.*)."""
    pool = facts.rules() + facts.interview_invariants() + list(facts.facts.get("business_rules", [])) + \
        list(facts.facts.get("rationale", []))
    if scope == "security":
        pool = [x for x in pool if is_security_fact(x) or is_negative_invariant(x)]
    return sorted(set(x["id"] for x in pool))


def _touching(facts_list, files):
    fs = set(files)
    out = []
    for fx in facts_list:
        sc = fx.get("scope") or []
        if bool(set(fact_files(fx)) & fs) or bool(sc and expand(sc, fs)):
            out.append(fx["id"])
    return sorted(set(out))


def agent_fact_sets(f, name, kind, files):
    """(invariants, facts_used) de um agente — fonte única para derive e `team roster`.
    dev/design/...: invariantes (rules+entrevista+regras de negócio) que tocam os arquivos do território.
    gate: todos os invariantes + decisões de ADR + histórico de correção (footguns) do repo; `security` só os
    de segurança (precedência: qualquer FAIL vence; NEEDS_SPECIALIST roteia)."""
    rules = f.rules() + f.interview_invariants()
    brules = list(f.facts.get("business_rules", []))
    gloss = list(f.facts.get("glossary", []))
    all_facts = sorted(f.by_id.values(), key=lambda x: x["id"])
    if kind == "gate":
        scope = "security" if name == "security" else "all"
        inv = gate_required(f, scope)
        hist = [x for x in f.facts.get("history", []) if str(x["id"]).startswith("hist.fix.")
                or str((x.get("data") or {}).get("kind") or "").lower() in ("fix", "bugfix", "revert")]
        if scope == "security":
            hist = [x for x in hist if is_security_fact(x)]
        used = sorted(set(inv) | set(x["id"] for x in hist))
        return inv, used
    inv = _touching(rules + brules, files)
    used = _touching(all_facts, files) if files else []
    used = sorted(set(used) | set(_touching(gloss, files)) | set(inv))
    return inv, used


def derive(target, force=False):
    facts = Facts(target)
    d = Deriver(facts)
    agents = d.run()
    tpath = sp_path(target, "team.json5")
    if os.path.isfile(find_doc(tpath)) and not force:
        old = read_json(tpath, "team.json5")
        if any((a or {}).get("card") for a in old.get("agents") or []):
            raise CsError("team.json5 já tem cartões preenchidos; derive não sobrescreve",
                          "use --force para recomeçar o roster (cartões serão perdidos)")
    run = {}
    rp = sp_path(target, "run.json5")
    if os.path.isfile(find_doc(rp)):
        run = read_json(rp, "run.json5")
    repo = {"name": os.path.basename(target), "commit": run.get("commit") or run.get("target_commit") or "",
            "root": target}
    team = {"schema_version": 1, "repo": repo, "platforms": run.get("platforms") or [],
            "veredito_enum": list(VEREDITO_ENUM), "core": {"lines": []}, "agents": agents,
            "test_ownership": dict(TEST_OWNERSHIP)}
    write_json(target, tpath, team)
    deriv = {"schema_version": 1, "decisions": d.decisions,
             "summary": {"agents": [a["name"] for a in agents],
                         "devs": sum(1 for a in agents if a["kind"] == "dev" and a["name"] not in ("qa", "dba")),
                         "product_files": len(d.product), "missing_layers": facts.missing}}
    write_json(target, sp_path(target, "team-derivation.json5"), deriv)
    return team, deriv
