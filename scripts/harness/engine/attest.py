"""attest — atestado do que a FERRAMENTA escreveu no alvo (B-13, 0.10.1), lido pelo pre-commit (`check-diff`).

`cs.py harness install` e `cs.py emit` (e, por eles, o `cs.py upgrade`) gravam aqui o sha256 de cada arquivo que
deixaram no alvo (remoção = null). O `check-diff` libera um arquivo que barraria (área protegida ou fora de
allowed_paths) SÓ se ele está atestado E o conteúdo staged (ou da árvore, sem --staged) tem exatamente o sha256
atestado. Edição à mão depois da ferramenta muda o sha ⇒ barra; arquivo que a ferramenta não escreveu ⇒ barra.

Não reutilizável: cada caminho guarda só a ÚLTIMA escrita da ferramenta; a cada gravação saem as entradas que já
batem com o HEAD (consumidas pelo commit). Um 2º commit com o arquivo mudado à mão tem sha ≠ atestado ⇒ barra.

Contra forja:
- mora em <git-dir>/codebase-specialists/atestado.json: fora da árvore versionada (nunca entra num commit nem vai
  para outro clone) e sob `.git/`, área protegida do guard (Write/Edit/Bash do modelo bloqueados, como o motor);
- âncora no harness-ledger (encadeado): cada gravação anexa {kind: "attest", sha256: <sha do arquivo>}; o
  check-diff só confia no atestado cujo sha256 é o do ÚLTIMO `attest` de um ledger com a cadeia íntegra. Editar
  o atestado sem refazer a cadeia ⇒ atestado ignorado ⇒ barra (fail-closed);
- mesmo válido, só libera caminhos que a ferramenta gera (ATTESTABLE_*) e nunca estado do motor (zonas, eventos,
  ledgers, memória): estado continua passando pelo validate.
Python 3.9+ stdlib (copiado para <alvo>/.swarm/harness/ junto do motor).
"""
import json
import os
import subprocess

import hcore

ATTEST_DIR = "codebase-specialists"
ATTEST_FILE = "atestado.json"
SCHEMA = 1
# caminhos que install/emit geram (fora disso o atestado é ignorado, mesmo forjado)
ATTESTABLE_PREFIXES = (hcore.STATE_DIR + "/", ".claude/", ".cursor/", ".codex/", ".agents/", ".github/agents/",
                       ".github/instructions/", ".github/skills/")
ATTESTABLE_FILES = ("CLAUDE.md", "AGENTS.md", "Makefile", "specialists.mk", ".github/copilot-instructions.md")
# estado do motor: nunca atestado (o validate decide)
STATE_PREFIXES = tuple("%s/%s/" % (hcore.STATE_DIR, z) for z in hcore.TREE_ZONES) + (
    "%s/%s/" % (hcore.STATE_DIR, hcore.TREE_RUNTIME), hcore.STATE_DIR + "/memory/",
    hcore.STATE_DIR + "/events.jsonl", hcore.STATE_DIR + "/INDEX.md")


def attestable(rel):
    if not isinstance(rel, str) or not rel or rel.startswith(STATE_PREFIXES):
        return False
    return rel.startswith(ATTESTABLE_PREFIXES) or rel in ATTESTABLE_FILES or rel.endswith("/AGENTS.md")


def _git(root, args, data=None):
    try:
        p = subprocess.run(["git"] + list(args), cwd=root, input=data, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
    except OSError:
        return None
    return p.stdout if p.returncode == 0 else None


def git_dir(root):
    """<git-dir> do repositório cuja RAIZ é `root` (pasta dentro de outro repositório: None — não é o alvo)."""
    top = _git(root, ["rev-parse", "--show-toplevel"])
    if top is None or os.path.realpath(top.decode("utf-8", "replace").strip()) != os.path.realpath(root):
        return None
    out = _git(root, ["rev-parse", "--absolute-git-dir"])
    if out is None:
        out = _git(root, ["rev-parse", "--git-dir"])
        if out is None:
            return None
        d = out.decode("utf-8", "replace").strip()
        return os.path.realpath(d if os.path.isabs(d) else os.path.join(root, d))
    return out.decode("utf-8", "replace").strip() or None


def attest_path(root):
    d = git_dir(root)
    return os.path.join(d, ATTEST_DIR, ATTEST_FILE) if d else None


def harness_state(root):
    """O harness tem estado (e ledger encadeado) neste alvo? Antes do install: não há âncora possível."""
    return hcore.tree_mode(root) or os.path.isfile(os.path.join(root, hcore.STATE_DIR, "state", "board.json5"))


def _last_anchor(root):
    """→ (sha256 do último `attest` do ledger | None, problema | None)."""
    path = hcore.state_paths(root)["ledger"]
    if not os.path.isfile(path):
        return None, None
    recs, errs, _ = hcore.read_chain(path)
    if errs:
        return None, "harness-ledger com a cadeia quebrada (%s)" % errs[0]
    for r in reversed(recs):
        if isinstance(r, dict) and r.get("kind") == "attest":
            return r.get("sha256"), None
    return None, None


def _read(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def load(root):
    """→ (files {rel: {sha256, by, version}}, problema | None). Só devolve entradas de atestado ANCORADO."""
    p = attest_path(root)
    raw = _read(p) if p else None
    if raw is None:
        return {}, None
    anchor, prob = _last_anchor(root)
    if prob:
        return {}, "atestado ignorado: %s" % prob
    if anchor != hcore.sha256_bytes(raw):
        return {}, "atestado ignorado: não confere com o último `attest` do harness-ledger"
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}, "atestado ignorado: ilegível"
    files = data.get("files") if isinstance(data, dict) else None
    return (files if isinstance(files, dict) else {}), None


def _batch(root, specs):
    """`git cat-file --batch` → {spec: bytes | None}. spec = ':rel' (index) ou 'HEAD:rel'."""
    specs = [s for s in specs if "\n" not in s]
    if not specs:
        return {}
    out = _git(root, ["cat-file", "--batch"], ("\n".join(specs) + "\n").encode("utf-8"))
    res = {}
    if out is None:
        return res
    i = 0
    for s in specs:
        j = out.find(b"\n", i)
        if j < 0:
            break
        head = out[i:j].split(b" ")
        i = j + 1
        if len(head) == 3 and head[1] == b"blob":
            n = int(head[2])
            res[s] = out[i:i + n]
            i += n + 1
        else:
            res[s] = None  # missing / não-blob
    return res


def head_blob(root, rel):
    return _batch(root, ["HEAD:" + rel]).get("HEAD:" + rel)


def pristine(root, rel, old):
    """Arquivo MESCLADO (bloco gerenciado, settings.json, Makefile): só é atestado se o conteúdo de antes da
    escrita era o do HEAD (ou não existia) — senão o atestado abençoaria edição humana ainda não commitada."""
    return old is None or old == head_blob(root, rel)


def released(root, rels, staged=True):
    """→ (set de rels liberados, problema | None). Liberado = atestado + conteúdo atual com o sha atestado
    (staged: o index; sem --staged: a árvore). Remoção atestada (null) libera só o arquivo ausente."""
    want = [r for r in rels if attestable(r)]
    if not want:
        return set(), None
    files, prob = load(root)
    if prob or not files:
        return set(), prob
    want = [r for r in want if r in files and isinstance(files[r], dict)]
    if staged:
        blobs = _batch(root, [":" + r for r in want])
        cur = {r: blobs.get(":" + r) for r in want}
    else:
        cur = {r: (_read(os.path.join(root, r)) if os.path.isfile(os.path.join(root, r)) else None) for r in want}
    ok = set()
    for r in want:
        exp = files[r].get("sha256")
        got = cur.get(r)
        if (exp is None and got is None) or (exp is not None and got is not None and hcore.sha256_bytes(got) == exp):
            ok.add(r)
    return ok, None


def record(root, written, by, version=None, adopt_unanchored=False):
    """Grava/atualiza o atestado com {rel: bytes | None (removido)} que a ferramenta `by` acabou de deixar.
    Entradas anteriores: mantidas se o atestado estava ancorado (ou se ainda não há estado do harness: antes do
    install nada é protegido); `adopt_unanchored` (install que criou o estado agora) adota as do emit anterior.
    Atestado forjado/sem âncora com o harness já instalado ⇒ descartado. → (n de entradas, problema | None)."""
    p = attest_path(root)
    if not p:
        return 0, None  # sem git: não há pre-commit a satisfazer
    state = harness_state(root)
    raw = _read(p)
    files = {}
    if raw is not None:
        anchored, _ = load(root)
        if anchored:
            files = dict(anchored)
        elif not state or adopt_unanchored:
            try:
                data = json.loads(raw.decode("utf-8"))
                if isinstance(data, dict) and not data.get("anchored"):
                    files = dict(data.get("files") or {})
            except (ValueError, UnicodeDecodeError):
                files = {}
    for rel, data in (written or {}).items():
        if attestable(rel):
            files[rel] = {"sha256": hcore.sha256_bytes(data) if data is not None else None, "by": by,
                          "version": version}
    # consumidas: o HEAD já tem o conteúdo atestado (nada a liberar; não reabre o caminho para 2º commit)
    heads = _batch(root, ["HEAD:" + r for r in files])
    for r in list(files):
        h = heads.get("HEAD:" + r)
        exp = (files[r] or {}).get("sha256")
        if (exp is None and h is None and ("HEAD:" + r) in heads) or (h is not None and hcore.sha256_bytes(h) == exp):
            del files[r]
    body = (json.dumps({"schema": SCHEMA, "anchored": bool(state), "by": by, "version": version,
                        "files": dict(sorted(files.items()))}, ensure_ascii=False, indent=1, sort_keys=True)
            + "\n").encode("utf-8")
    hcore.atomic_write_bytes(p, body)
    if state:
        try:
            hcore.ledger_append(root, {"kind": "attest", "by": by, "version": version, "files": len(files),
                                       "sha256": hcore.sha256_bytes(body)})
        except Exception as e:  # sem âncora o check-diff ignora o atestado (fail-closed)
            return len(files), "atestado sem âncora no harness-ledger (%s): o pre-commit não o aceita" % e
    return len(files), None
