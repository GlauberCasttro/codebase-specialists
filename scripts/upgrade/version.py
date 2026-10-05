"""Versão da skill (VERSION na raiz) e catálogo de migrações (references/migrations.json5).

Fonte única para `cs.py init` (grava `skill_version` no run.json5) e `cs.py upgrade` (plano/aplicação).
Overrides (testes): $CS_SKILL_VERSION_FILE e $CS_MIGRATIONS_FILE.

Esquema de references/migrations.json5:
  {version: "<semver = VERSION>",
   migrations: [{to: "<semver>", why: "<texto>", actions: [{kind: <KIND>, ...}]}]}   // `to` estritamente crescente
KINDs: harness | emit | scan (layers: [...], no_exec?) | facts-refresh (layers?) | schema (script) |
       cards (argv?) | probes (argv?) | rename-dir (from?/to? só podem ser paths.LEGACY_STATE_DIR → paths.STATE_DIR) |
       state-tree (sem parâmetros: board plano legado → árvore de pastas, via `cs-state migrate state-tree`).
"""

import os
import re

from cslib import CsError, json5io, paths

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # scripts/
SKILL_ROOT = os.path.dirname(HERE)
VERSION_FILE = os.path.join(SKILL_ROOT, "VERSION")
MIGRATIONS_FILE = os.path.join(SKILL_ROOT, "references", "migrations.json5")

LEGACY = "0.0.0-legado"
KINDS = ("harness", "emit", "scan", "facts-refresh", "schema", "cards", "probes", "rename-dir", "state-tree")
RESERVED_KINDS = ()                       # kinds previstos sem implementação (rename-dir implementado: SWARM-DIR-3)
REEXAM_KINDS = ("cards", "probes")        # sempre avisam: haverá reexame
_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z.-]+))?$")
_LAYER = re.compile(r"^L(?:[0-9]|10)$")


def version_file():
    return os.environ.get("CS_SKILL_VERSION_FILE") or VERSION_FILE


def migrations_file():
    return os.environ.get("CS_MIGRATIONS_FILE") or MIGRATIONS_FILE


def parse(v):
    """semver → chave ordenável. Pré-release (ex.: 0.0.0-legado) vem antes da release de mesmo núcleo."""
    m = _SEMVER.match(str(v or "").strip())
    if not m:
        raise CsError("versão fora de semver: %r" % (v,), "use X.Y.Z (ex.: 0.5.0)")
    pre = m.group(4)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), 0 if pre else 1, pre or "")


def current_version():
    p = version_file()
    if not os.path.isfile(p):
        raise CsError("VERSION ausente na skill (%s)" % p, "recrie o arquivo VERSION (semver) na raiz da skill")
    with open(p, "r", encoding="utf-8") as fh:
        v = fh.read().strip()
    parse(v)
    return v


def target_version(run):
    """Versão gravada no run.json5 do alvo; ausente → alvo LEGADO (gerado antes do versionamento)."""
    v = (run or {}).get("skill_version")
    return (v, False) if v else (LEGACY, True)


def validate_catalog(cat, version=None):
    """→ [erros] do catálogo de migrações (vazio = ok)."""
    errs = []
    if not isinstance(cat, dict):
        return ["migrations.json5 não é objeto"]
    try:
        parse(cat.get("version"))
    except CsError:
        errs.append("version ausente/fora de semver: %r" % (cat.get("version"),))
    if version is not None and cat.get("version") != version:
        errs.append("migrations.json5 version=%r ≠ VERSION=%r" % (cat.get("version"), version))
    migs = cat.get("migrations")
    if not isinstance(migs, list) or not migs:
        return errs + ["migrations vazio: toda versão precisa de uma entrada (a primeira documenta o estado)"]
    prev = None
    for i, m in enumerate(migs):
        where = "migrations[%d]" % i
        if not isinstance(m, dict):
            errs.append("%s não é objeto" % where)
            continue
        try:
            key = parse(m.get("to"))
        except CsError:
            errs.append("%s.to fora de semver: %r" % (where, m.get("to")))
            continue
        if key[3] == 0:
            errs.append("%s.to não pode ser pré-release" % where)
        if prev is not None and key <= prev:
            errs.append("%s.to=%s não é estritamente maior que a anterior" % (where, m.get("to")))
        prev = key
        if not str(m.get("why") or "").strip():
            errs.append("%s sem why" % where)
        acts = m.get("actions")
        if not isinstance(acts, list):
            errs.append("%s.actions não é lista" % where)
            continue
        for j, a in enumerate(acts):
            w = "%s.actions[%d]" % (where, j)
            k = (a or {}).get("kind") if isinstance(a, dict) else None
            if k not in KINDS:
                errs.append("%s.kind inválido: %r (válidos: %s)" % (w, k, ", ".join(KINDS)))
                continue
            if k == "scan":
                ls = a.get("layers")
                if not isinstance(ls, list) or not ls or not all(_LAYER.match(str(x)) for x in ls):
                    errs.append("%s: scan exige layers: [L0..L10]" % w)
            if k == "facts-refresh" and a.get("layers") is not None:
                ls = a.get("layers")
                if not isinstance(ls, list) or not all(_LAYER.match(str(x)) for x in ls):
                    errs.append("%s: facts-refresh.layers deve ser [L0..L10]" % w)
            if k == "schema" and not str(a.get("script") or "").strip():
                errs.append("%s: schema exige script (conversor idempotente)" % w)
            if k == "rename-dir":
                extra = sorted(x for x in a if x not in ("kind", "from", "to"))
                if extra or a.get("from", paths.LEGACY_STATE_DIR) != paths.LEGACY_STATE_DIR \
                        or a.get("to", paths.STATE_DIR) != paths.STATE_DIR:
                    errs.append("%s: rename-dir só renomeia %s → %s (from/to diferentes ou chaves extras %s)"
                                % (w, paths.LEGACY_STATE_DIR, paths.STATE_DIR, extra))
            if k == "state-tree" and sorted(x for x in a if x != "kind"):
                errs.append("%s: state-tree não aceita parâmetros (chaves extras %s)"
                            % (w, sorted(x for x in a if x != "kind")))
            if k in REEXAM_KINDS and a.get("argv") is not None and not (
                    isinstance(a["argv"], list) and all(isinstance(x, str) for x in a["argv"])):
                errs.append("%s: argv deve ser lista de strings (argumentos do cs.py)" % w)
    if prev is not None and cat.get("version") and _SEMVER.match(str(cat.get("version"))):
        if prev != parse(cat["version"]):
            errs.append("última migração (to=%s) ≠ version=%s: VERSION mudou sem migração correspondente"
                        % (migs[-1].get("to") if isinstance(migs[-1], dict) else "?", cat.get("version")))
    return errs


def load_catalog(check_version=True):
    p = migrations_file()
    cat = json5io.read(p)
    errs = validate_catalog(cat, current_version() if check_version else None)
    if errs:
        raise CsError("catálogo de migrações inválido (%s): %s" % (p, "; ".join(errs)),
                      "corrija references/migrations.json5 (toda mudança de VERSION exige uma entrada)")
    return cat


def pending(cat, from_version, to_version):
    """Migrações com from < to_m ≤ to, em ordem."""
    lo, hi = parse(from_version), parse(to_version)
    return [m for m in cat["migrations"] if lo < parse(m["to"]) <= hi]
