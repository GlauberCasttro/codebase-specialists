"""replace — harness único: detecta OUTRO harness no alvo e, só com `--replace-harness`, o substitui.

Contrato (ESPEC campanha-iter9, SWARM-DIR-2/4; PONTOS-DO-FOUNDER C4 "um harness não pode existir junto com o outro"):
- `gate()` roda ANTES de `cs.py init` e `cs.py harness install`. Sem sinal → segue. Com sinal → exit 3 sem escrever
  nada e imprime o "plano de substituição"; o diretório legado DESTA skill não é "outro harness" (é migração:
  `cs.py upgrade`).
- `--replace-harness` (+ `--allow-outside`, porque mexe fora de .swarm/): backup fiel de todo arquivo do harness
  anterior em `.swarm/backups/harness-anterior/<caminho original>` (sha256 conferido ANTES de apagar qualquer coisa),
  desinstala hooks/settings/kernel/scripts/gate de pre-commit/alvos do Makefile do anterior, importa os invariantes
  de domínio (DOMAIN_INVARIANTS.yaml do v8) como fatos com `origin` e evidência apontando a cópia no backup.
  O produto (tudo fora das zonas do harness) nunca é tocado.
"""
import hashlib
import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
for _p in (os.path.join(HERE, "engine"), SCRIPTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hcore  # noqa: E402

EXIT_REFUSED = 3
BACKUP_REL = hcore.STATE_DIR + "/backups/harness-anterior"
IMPORT_LAYER = "imported-harness"
IMPORT_PREFIX = "imported."
IMPORT_FILE = IMPORT_LAYER + ".json5"
INVARIANTS_REL = hcore.STATE_DIR + "/knowledge/DOMAIN_INVARIANTS.yaml"
# entradas de <STATE_DIR>/ que são DESTA skill (nunca vão para o backup nem são removidas)
OWN_SWARM = ("run.json5", "harness", "bin", "facts", "memory", "backups", "team.json5", "evidence", "tmp")
# entradas conhecidas do v8 em <STATE_DIR>/ (usadas quando o .swarm/ é misto)
V8_SWARM = ("instance.json", "init", "knowledge", "state/init-validation.jsonl")
LEFTHOOK_FILES = ("lefthook.yml", "lefthook.yaml", ".lefthook.yml", ".lefthook.yaml")
BLOCK_BEGIN_RE = re.compile(r"^\s*#\s*>>>.*SWARM HARNESS")
BLOCK_END_RE = re.compile(r"^\s*#\s*<<<.*SWARM HARNESS")
FOREIGN_CALL = "scripts/harness/"


# ------------------------------------------------------------------------------------------------ detecção


def classify(root):
    """→ (foreign, legacy): sinais de outro harness e do diretório legado desta skill."""
    sig = hcore.foreign_harness_signals(root)
    legacy = [s for s in sig if s[0].rstrip("/") == hcore.LEGACY_STATE_DIR]
    foreign = [s for s in sig if s not in legacy]
    return foreign, legacy


def _swarm_is_foreign(root):
    """O <STATE_DIR>/ inteiro é do outro harness (placa v8 e nada desta skill)?"""
    sw = os.path.join(root, hcore.STATE_DIR)
    if not os.path.isfile(os.path.join(sw, "instance.json")):
        return False
    return not any(os.path.lexists(os.path.join(sw, x)) for x in ("run.json5", "harness", "bin", "state/board.json5"))


def _walk_files(root, rel):
    """Arquivos/symlinks (rel ao alvo) sob `rel` (arquivo ou diretório), sem __pycache__."""
    full = os.path.join(root, rel)
    if os.path.islink(full) or os.path.isfile(full):
        return [rel]
    out = []
    if not os.path.isdir(full):
        return out
    for d, dirs, files in os.walk(full):
        keep = []
        for x in sorted(dirs):
            p = os.path.join(d, x)
            if os.path.islink(p):
                out.append(os.path.relpath(p, root))
            elif x != "__pycache__":
                keep.append(x)
        dirs[:] = keep
        for f in sorted(files):
            out.append(os.path.relpath(os.path.join(d, f), root))
    return [o.replace(os.sep, "/") for o in out]


def _swarm_entries(root):
    sw = os.path.join(root, hcore.STATE_DIR)
    if not os.path.isdir(sw):
        return []
    if _swarm_is_foreign(root):
        return sorted(hcore.STATE_DIR + "/" + x for x in os.listdir(sw) if x != "backups")
    return [hcore.STATE_DIR + "/" + x for x in V8_SWARM if os.path.lexists(os.path.join(sw, x))]


def _settings_path(root):
    return os.path.join(root, ".claude", "settings.json")


def _foreign_hook_cmds(root):
    p = _settings_path(root)
    if not os.path.isfile(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    out = []
    hooks = data.get("hooks") if isinstance(data, dict) else None
    for ev, groups in (hooks.items() if isinstance(hooks, dict) else ()):
        for g in groups or []:
            for h in (g.get("hooks") or []) if isinstance(g, dict) else []:
                cmd = (h.get("command") or "") if isinstance(h, dict) else ""
                if "cs-guard.sh" not in cmd:
                    out.append((ev, cmd))
    return out


def _lefthook(root):
    for f in LEFTHOOK_FILES:
        p = os.path.join(root, f)
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                txt = fh.read()
            if any(BLOCK_BEGIN_RE.match(l) for l in txt.splitlines()) or FOREIGN_CALL in txt:
                return f
    return None


def build_plan(root):
    """O que a substituição faria (nada é escrito): dict com backup/remove/settings/lefthook/makefile/facts."""
    foreign, legacy = classify(root)
    backup, remove = [], []
    for rel in _swarm_entries(root):
        backup += _walk_files(root, rel)
        remove.append(rel)
    for rel in ("scripts/harness", ".claude/kernel"):
        if os.path.lexists(os.path.join(root, rel)):
            backup += _walk_files(root, rel)
            remove.append(rel + "/")
    hooks_dir = os.path.join(root, ".claude", "hooks")
    if os.path.isdir(hooks_dir):
        for x in sorted(os.listdir(hooks_dir)):
            if x == "cs-guard.sh":
                continue
            rel = ".claude/hooks/" + x
            backup += _walk_files(root, rel)
            remove.append(rel + ("/" if os.path.isdir(os.path.join(root, rel)) and not os.path.islink(
                os.path.join(root, rel)) else ""))
    hook_cmds = _foreign_hook_cmds(root)
    if os.path.isfile(_settings_path(root)):
        backup.append(".claude/settings.json")
    lh = _lefthook(root)
    if lh:
        backup.append(lh)
    mk_targets = makefile_foreign_targets(root)
    if mk_targets:
        backup.append("Makefile")
    invariants = []
    inv = os.path.join(root, INVARIANTS_REL)
    if os.path.isfile(inv):
        with open(inv, "r", encoding="utf-8", errors="replace") as fh:
            invariants = parse_invariants(fh.read())
    seen = set()
    backup = [b for b in backup if not (b in seen or seen.add(b))]
    return {"root": root, "foreign": foreign, "legacy": legacy, "backup": backup, "remove": remove,
            "hook_cmds": hook_cmds, "lefthook": lh, "makefile_targets": mk_targets, "invariants": invariants,
            "backup_dir": _backup_dir(root)}


def _backup_dir(root):
    d = os.path.join(root, BACKUP_REL)
    if os.path.isdir(d) and os.listdir(d):
        return BACKUP_REL + "-" + time.strftime("%Y%m%d%H%M%S")
    return BACKUP_REL


def render_plan(plan, cmd="init"):
    lines = ["OUTRO HARNESS detectado em %s — um harness não pode existir junto com o outro." % plan["root"],
             "sinais:"]
    shown = {}
    for rel, why in plan["foreign"]:
        shown.setdefault(rel, []).append(why)
    for rel, whys in shown.items():
        lines.append("  - %s — %s%s" % (rel, whys[0], (" (+%d)" % (len(whys) - 1)) if len(whys) > 1 else ""))
    lines.append("plano de substituição (nada foi escrito):")
    lines.append("  1. backup fiel (sha256 conferido antes de apagar) de %d arquivo(s) → %s/<caminho original>"
                 % (len(plan["backup"]), plan["backup_dir"]))
    groups = {}
    for b in plan["backup"]:
        top = b.split("/")[0] if not b.startswith((".claude/", hcore.STATE_DIR + "/", "scripts/")) \
            else "/".join(b.split("/")[:2])
        groups[top] = groups.get(top, 0) + 1
    for g in sorted(groups):
        lines.append("       %s (%d)" % (g, groups[g]))
    hooks_rm = [r for r in plan["remove"] if r.startswith(".claude/hooks/")]
    rest = [r for r in plan["remove"] if r not in hooks_rm]
    if hooks_rm:
        rest.append(".claude/hooks/* (%d item(ns); só cs-guard.sh fica)" % len(hooks_rm))
    lines.append("  2. remove o harness anterior: %s" % (", ".join(rest) or "(nada)"))
    if plan["hook_cmds"]:
        lines.append("  3. .claude/settings.json: remove %d hook(s) do harness anterior (permissions/env ficam); "
                     "entram só os hooks cs-guard.sh" % len(plan["hook_cmds"]))
    else:
        lines.append("  3. .claude/settings.json: entram só os hooks cs-guard.sh")
    if plan["lefthook"]:
        lines.append("  4. %s: remove o bloco gerado do harness anterior (gate de pre-commit); o resto fica"
                     % plan["lefthook"])
    if plan["makefile_targets"]:
        lines.append("  5. Makefile: remove os alvos que chamam %s (%s); o resto fica e ganha `include specialists.mk`"
                     % (FOREIGN_CALL, ", ".join(plan["makefile_targets"])))
    if plan["invariants"]:
        lines.append("  6. importa %d invariante(s) de %s como fatos citáveis em %s/facts/%s (origin + evidência no "
                     "backup): %s" % (len(plan["invariants"]), INVARIANTS_REL, hcore.STATE_DIR, IMPORT_FILE,
                                      ", ".join(i["id"] for i in plan["invariants"])))
    lines.append("  7. instala o harness desta skill (%s/ + .claude/hooks/cs-guard.sh); produto intacto"
                 % hcore.STATE_DIR)
    if plan["legacy"]:
        lines.append("também há o diretório legado desta skill (%s/): depois da substituição rode `cs.py upgrade`"
                     % hcore.LEGACY_STATE_DIR)
    if cmd == "install":
        lines.append("para aplicar: cs.py harness install --replace-harness --allow-outside")
    else:
        lines.append("para aplicar: cs.py init --platforms <...> --replace-harness --allow-outside "
                     "(mostre este plano ao usuário antes)")
    return "\n".join(lines)


def render_legacy(legacy):
    return ("diretório legado desta skill (%s/) detectado: é o MESMO harness em versão antiga — migre com "
            "`cs.py upgrade` (plano) e `cs.py upgrade --apply --allow-outside`; não é caso de --replace-harness. "
            "Nada foi escrito." % hcore.LEGACY_STATE_DIR)


# ------------------------------------------------------------------------------------------------ invariantes


def _unquote(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] == '"':
        try:
            return json.loads(v)
        except ValueError:
            return v[1:-1]
    if len(v) >= 2 and v[0] == v[-1] == "'":
        return v[1:-1].replace("''", "'")
    return v


def parse_invariants(text):
    """Leitor mínimo (stdlib) do DOMAIN_INVARIANTS.yaml do v8: itens `- id: ...` com `chave: valor` escalares.
    → [{id, invariant, block_if, source, verifiable_as, entity, line}]."""
    out, cur = [], None
    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^\s*-\s+id:\s*(.+)$", line)
        if m:
            cur = {"id": _unquote(m.group(1)), "line": n}
            out.append(cur)
            continue
        m = re.match(r"^\s+([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if m and cur is not None and m.group(2):
            cur.setdefault(m.group(1), _unquote(m.group(2)))
    return [i for i in out if i.get("id") and i.get("invariant")]


def import_invariants(root, plan, backup_dir):
    """Invariantes do harness anterior → fatos `imported.<harness>.<id>` (layer imported-harness), evidência = a
    cópia no backup (existe e é citável). → [ids]."""
    if not plan["invariants"]:
        return []
    from cslib import evidence
    from facts import store
    ev_rel = backup_dir + "/" + INVARIANTS_REL
    fb = evidence.FactBuilder(root)
    facts = []
    for inv in plan["invariants"]:
        fid = IMPORT_PREFIX + "v8." + evidence.slug(inv["id"])
        src = inv.get("source") or "desconhecida"
        claim = "Invariante de domínio %s (importado do harness anterior; fonte: %s): %s" % (
            inv["id"], src, inv["invariant"])
        if inv.get("block_if"):
            claim += " — bloqueia se: %s" % inv["block_if"]
        data = {"source_id": inv["id"], "invariant": inv["invariant"], "source": src,
                "imported_from": "harness-anterior (v8)", "original_path": INVARIANTS_REL, "backup_path": ev_rel}
        for k in ("block_if", "verifiable_as", "entity"):
            if inv.get(k):
                data[k] = inv[k]
        facts.append(fb.fact(fid, IMPORT_LAYER, claim, [evidence.ev_file(ev_rel, inv["line"])],
                             confidence="high" if src == "founder" else "medium", origin="mechanical", data=data))
    fdir = store.facts_dir(root)
    os.makedirs(fdir, exist_ok=True)
    store.write5(root, os.path.join(fdir, IMPORT_FILE),
                 {"schema_version": 1, "layer": IMPORT_LAYER, "generator": "cs.py init --replace-harness",
                  "facts": facts},
                 "imported-harness — invariantes do harness anterior como fatos (evidência no backup); "
                 "gerado por --replace-harness")
    store.index_sync(root, IMPORT_LAYER, [f["id"] for f in facts], IMPORT_PREFIX)
    return [f["id"] for f in facts]


# ------------------------------------------------------------------------------------------------ Makefile / lefthook


_RULE_RE = re.compile(r"^([A-Za-z0-9_.\-][A-Za-z0-9_.\- ]*?)\s*::?(?!=)")


def _mk_groups(text):
    """Quebra o Makefile em grupos: ('rule', [linhas], [alvos]) | ('other', [linhas], [])."""
    lines = text.split("\n")
    groups, i = [], 0
    while i < len(lines):
        ln = lines[i]
        m = None if ln.startswith(("\t", " ", "#", ".PHONY")) or ln.startswith("override ") \
            or re.match(r"^\s*[A-Za-z0-9_]+\s*[:?+]?=", ln) else _RULE_RE.match(ln)
        if m:
            body = [ln]
            j = i + 1
            cont = ln.endswith("\\")
            while j < len(lines) and (lines[j].startswith("\t") or cont):
                cont = lines[j].endswith("\\")
                body.append(lines[j])
                j += 1
            groups.append(("rule", body, m.group(1).split()))
            i = j
        else:
            groups.append(("other", [ln], []))
            i += 1
    return groups


def makefile_foreign_targets(root):
    p = os.path.join(root, "Makefile")
    if not os.path.isfile(p):
        return []
    with open(p, "r", encoding="utf-8", errors="replace") as fh:
        txt = fh.read()
    if FOREIGN_CALL not in txt:
        return []
    out = []
    for kind, body, names in _mk_groups(txt):
        if kind == "rule" and any(FOREIGN_CALL in b for b in body):
            out += names
    return out


def clean_makefile(text):
    """Remove os alvos que chamam o harness anterior, a variável que só eles usam e os marcadores do bloco gerado;
    preserva todo o resto (DX do usuário)."""
    groups = _mk_groups(text)
    dropped = set()
    kept = []
    for kind, body, names in groups:
        if kind == "rule" and any(FOREIGN_CALL in b for b in body):
            dropped |= set(names)
            continue
        kept.append((kind, body, names))
    out = []
    for kind, body, names in kept:
        for ln in body:
            if kind == "other" and BLOCK_BEGIN_RE.match(ln):
                out.append("# (alvos do harness anterior removidos por codebase-specialists --replace-harness; "
                           "backup em %s/Makefile)" % BACKUP_REL)
                continue
            if kind == "other" and BLOCK_END_RE.match(ln):
                continue
            if kind == "other" and FOREIGN_CALL in ln:
                continue
            if ln.startswith(".PHONY") and dropped:
                names_ = [n for n in ln.split(":", 1)[1].split() if n not in dropped]
                if not names_:
                    continue
                ln = ".PHONY: " + " ".join(names_)
            out.append(ln)
    txt = "\n".join(out)
    # variável de interpretador do harness anterior que ninguém mais usa
    m = re.search(r"^override\s+([A-Z_]+)\s*:=.*$", txt, re.M)
    if m and txt.count("$(%s)" % m.group(1)) == 0:
        txt = txt[:m.start()] + txt[m.end() + 1:]
    return txt


def clean_lefthook(text):
    """Remove o bloco gerado (# >>> ... SWARM HARNESS ... # <<< ...); fora dele nada muda."""
    out, inside = [], False
    for ln in text.split("\n"):
        if not inside and BLOCK_BEGIN_RE.match(ln):
            inside = True
            continue
        if inside:
            if BLOCK_END_RE.match(ln):
                inside = False
            continue
        out.append(ln)
    return "\n".join(out)


# ------------------------------------------------------------------------------------------------ execução


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_faithful(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.islink(src):
        tgt = os.readlink(src)
        if os.path.lexists(dst):
            os.unlink(dst)
        os.symlink(tgt, dst)
        if os.path.exists(src) and not os.path.exists(dst):   # link relativo que não resolve no backup
            os.unlink(dst)
            shutil.copy2(src, dst)
        return None if not os.path.isfile(dst) else (_sha(dst) if not os.path.islink(dst) else "link")
    shutil.copy2(src, dst)
    return _sha(dst)


def _rm(path):
    if os.path.islink(path) or os.path.isfile(path):
        os.unlink(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)


def _write_text(path, text):
    hcore.atomic_write_bytes(path, text.encode("utf-8"))


def apply(root, plan=None, out=None):
    """Executa a substituição. → dict do que foi feito. Falha no backup ⇒ nada é removido."""
    out = out or sys.stdout
    plan = plan or build_plan(root)
    bdir = plan["backup_dir"]
    babs = os.path.join(root, bdir)
    manifest = []
    # 1. backup (verificado antes de qualquer remoção)
    for rel in plan["backup"]:
        src = os.path.join(root, rel)
        dst = os.path.join(babs, rel)
        got = _copy_faithful(src, dst)
        if not os.path.islink(src):
            want = _sha(src)
            if got != want:
                raise hcore.StateError("backup infiel de %s (sha %s ≠ %s): nada foi removido" % (rel, got, want))
            manifest.append({"path": rel, "sha256": want})
        else:
            manifest.append({"path": rel, "symlink": os.readlink(src)})
    os.makedirs(babs, exist_ok=True)
    _write_text(os.path.join(babs, "MANIFEST.json"), json.dumps(
        {"generator": "codebase-specialists --replace-harness", "created_at": hcore.now_iso(),
         "signals": [{"path": r, "why": w} for r, w in plan["foreign"]], "removed": plan["remove"],
         "settings_hooks_removed": [{"event": e, "command": c} for e, c in plan["hook_cmds"]],
         "lefthook_block_removed": plan["lefthook"], "makefile_targets_removed": plan["makefile_targets"],
         "files": manifest}, indent=2, ensure_ascii=False) + "\n")
    # 2. invariantes → fatos (a evidência aponta a cópia no backup)
    imported = import_invariants(root, plan, bdir)
    # 3. desinstala o anterior
    for rel in plan["remove"]:
        _rm(os.path.join(root, rel.rstrip("/")))
    sd = os.path.join(root, "scripts")
    if os.path.isdir(sd) and not os.listdir(sd):
        os.rmdir(sd)
    sp = _settings_path(root)
    if os.path.isfile(sp) and plan["hook_cmds"]:
        with open(sp, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        hooks = data.get("hooks") or {}
        new_hooks = {}
        for ev, groups in hooks.items():
            kept = []
            for g in groups or []:
                hs = [h for h in (g.get("hooks") or []) if "cs-guard.sh" in (h.get("command") or "")]
                if hs:
                    g2 = dict(g)
                    g2["hooks"] = hs
                    kept.append(g2)
            if kept:
                new_hooks[ev] = kept
        if new_hooks:
            data["hooks"] = new_hooks
        else:
            data.pop("hooks", None)
        _write_text(sp, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    if plan["lefthook"]:
        p = os.path.join(root, plan["lefthook"])
        with open(p, "r", encoding="utf-8") as fh:
            _write_text(p, clean_lefthook(fh.read()))
    if plan["makefile_targets"]:
        p = os.path.join(root, "Makefile")
        with open(p, "r", encoding="utf-8") as fh:
            _write_text(p, clean_makefile(fh.read()))
    out.write("harness anterior substituído: backup de %d arquivo(s) em %s/; removidos: %s; %d invariante(s) "
              "importado(s) como fatos (%s)\n" % (len(manifest), bdir, ", ".join(plan["remove"]) or "nada",
                                                  len(imported), ", ".join(imported) or "-"))
    return {"backup_dir": bdir, "files": len(manifest), "imported": imported}


def gate(root, replace=False, allow_outside=False, cmd="init", out=None, err=None):
    """Porteiro de `init`/`harness install`. → None (siga) ou exit code (pare)."""
    out = out or sys.stdout
    err = err or sys.stderr
    foreign, legacy = classify(root)
    if not foreign and not legacy:
        return None
    if not foreign:
        err.write(render_legacy(legacy) + "\n")
        return EXIT_REFUSED
    plan = build_plan(root)
    if not replace:
        err.write(render_plan(plan, cmd) + "\n")
        err.write("recusado (exit %d): rode de novo com --replace-harness --allow-outside para substituir o harness "
                  "anterior (com backup).\n" % EXIT_REFUSED)
        return EXIT_REFUSED
    if not allow_outside:
        err.write(render_plan(plan, cmd) + "\n")
        err.write("recusado (exit %d): --replace-harness escreve FORA de %s/ (.claude/, scripts/harness/, Makefile, "
                  "lefthook) — exige também --allow-outside. Nada foi escrito.\n" % (EXIT_REFUSED, hcore.STATE_DIR))
        return EXIT_REFUSED
    try:
        apply(root, plan, out)
    except (hcore.StateError, OSError, ValueError) as e:
        err.write("substituição do harness anterior FALHOU: %s\n(o backup em %s/ é feito e conferido antes de "
                  "qualquer remoção)\n" % (e, plan["backup_dir"]))
        return 2
    if classify(root)[1]:
        err.write("harness anterior substituído, mas o diretório legado desta skill (%s/) continua: migre-o com "
                  "`cs.py upgrade` e rode o %s de novo.\n" % (hcore.LEGACY_STATE_DIR, cmd))
        return 0
    return None
