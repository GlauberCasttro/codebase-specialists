"""Contexto compartilhado do scan: lista de arquivos, categorias, leitura com cache e memo de camadas.

Camadas dependem umas das outras via ctx.layer("L1"), que computa sob demanda (sem gravar).
"""

import importlib
import os

from cslib import CsError, gitx, paths
from cslib.evidence import FactBuilder, ev_cmd

MAX_READ = 2 * 1024 * 1024  # arquivos maiores não têm conteúdo analisado

LAYER_MODULES = {
    "L0": "scan.l0_inventory",
    "L1": "scan.l1_graph",
    "L2": "scan.l2_architecture",
    "L3": "scan.l3_conventions",
    "L4": "scan.l4_rules",
    "L5": "scan.l5_history",
    "L6": "scan.l6_rationale",
    "L7": "scan.l7_operations",
    "L8": "scan.l8_stack",
    "L9": "scan.l9_domain",
    "L10": "scan.l10_project_docs",
}


class Options(object):
    def __init__(self, no_exec=False, timeout=300, max_commits=2000, max_deps=8, max_exec=12,
                 introspect=True):
        self.no_exec = no_exec
        self.timeout = timeout
        self.max_commits = max_commits
        self.max_deps = max_deps
        self.max_exec = max_exec
        self.introspect = introspect and not no_exec


class ScanContext(object):
    def __init__(self, target, options=None):
        self.target = os.path.realpath(target)
        self.opts = options or Options()
        gitx.require_repo(self.target)
        self.fb = FactBuilder(self.target)
        self._bytes = {}
        self._layers = {}
        listed, _raw = gitx.ls_files(self.target)
        # evidência sobre a lista FILTRADA (sem .swarm/, que é nossa saída) → determinística
        kept = "\0".join(r for r in listed if not paths.is_self(r)).encode("utf-8")
        self.ls_evidence = ev_cmd("git ls-files -z --cached --others --exclude-standard "
                                  "(sem .swarm/)", 0, kept)
        self.all_files = []        # tudo que existe (exceto .swarm/ e symlinks para fora)
        self.category = {}         # rel -> categoria
        self.outside_links = []    # symlinks que escapam do alvo
        for rel in listed:
            if paths.is_self(rel):
                continue
            full = os.path.join(self.target, rel)
            if not os.path.isfile(full):
                continue  # deletado no working tree, ou diretório (submódulo)
            if os.path.islink(full) and not paths.is_within(self.target, full):
                self.outside_links.append(rel)
                continue
            self.all_files.append(rel)
            head = self._head(rel)
            self.category[rel] = paths.classify(rel, head)
        # analisados = produto + reservado (reservado é listado à parte e filtrado pela derivação);
        # `example` (cliente de parceiro) fica fora da análise — não é stack nem regra do produto
        self.files = [f for f in self.all_files if self.category[f] not in paths.NOT_ANALYZED_CATEGORIES]
        self.product_files = [f for f in self.files if self.category[f] == paths.CAT_PRODUCT]
        if not self.files:
            raise CsError("nenhum arquivo analisável no alvo (%d listados, todos fixture/vendor/"
                          "generated ou ausentes)" % len(listed),
                          "confira o --target; arquivos precisam estar rastreados ou não-ignorados "
                          "pelo .gitignore")
        self.files_set = frozenset(self.files)

    # ---- leitura ----
    def _head(self, rel):
        try:
            with open(os.path.join(self.target, rel), "rb") as fh:
                return fh.read(512)
        except OSError:
            return b""

    def read_bytes(self, rel):
        if rel not in self._bytes:
            full = os.path.join(self.target, rel)
            data = b""
            try:
                if os.path.getsize(full) <= MAX_READ:
                    with open(full, "rb") as fh:
                        data = fh.read()
            except OSError:
                data = b""
            self._bytes[rel] = data
        return self._bytes[rel]

    def is_binary(self, rel):
        return b"\0" in self.read_bytes(rel)[:8192]

    def text(self, rel):
        data = self.read_bytes(rel)
        if b"\0" in data[:8192]:
            return ""
        # utf-8-sig: BOM no início colava em `namespace`/`using` da linha 1 e `^\s*` não casa
        # (cobaia .NET: 71 .cs com BOM → SwiftMapException.cs com in=0 e gabarito de dependência errado)
        return data.decode("utf-8-sig", "replace")

    def lines(self, rel):
        return self.text(rel).splitlines()

    def exists(self, rel):
        return rel in self.files_set

    def code_files(self, langs=None):
        out = [f for f in self.files if paths.is_code(f)]
        if langs:
            out = [f for f in out if paths.lang_of(f) in langs]
        return out

    def by_basename(self, *names):
        s = set(names)
        return [f for f in self.files if f.rsplit("/", 1)[-1] in s]

    # ---- camadas ----
    def layer(self, key):
        """Resultado (dict) da camada, computado uma vez por execução."""
        if key not in self._layers:
            mod = importlib.import_module(LAYER_MODULES[key])
            self._layers[key] = mod.run(self)
        return self._layers[key]
