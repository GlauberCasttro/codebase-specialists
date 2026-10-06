"""exam-pack, check (pontuação mecânica + gate G4) e baseline-filter.

Respostas: .swarm/probes/exams/<agente>.answers.json5 = [{id, answer, evidence: ["arq:linha"|"cmd"]}].
Baseline:  .swarm/probes/exams/<agente>.baseline.json5 (mesmo formato; sem cartão e sem repo).
Painel:    .swarm/probes/panel/<agente>.json5 = {id: "PASS"|"FAIL"} (sobrepõe sondas `why`).
"""
import os
import re
from cslib.paths import STATE_DIR  # noqa: E402

from team._shared_tmp.common import CsError, find_doc, norm_cmd, read_json, read_lines, sp_path, write_json
from team._shared_tmp.factsio import Facts
from probes.generate import load_bank

G4 = {"territory": 0.85, "cross": 0.70}
LINE_TOL = 3
INSPECT_CMDS = ("git ", "grep ", "rg ", "ls ", "find ", "cat ", "sed ", "head ", "tail ", "wc ", "awk ",
                "cs.py ", "python3 scripts/", "cs-mem ")
# Resposta que É negativa (iteração 3: "Na Black Friday ..." e "no-restricted-syntax ..." contavam como NENHUM).
# Palavra negativa inequívoca (nenhum, none, não existe...) pode vir seguida de explicação; "não"/"no"/"n/a"
# só valem ISOLADAS (fim da resposta ou pontuação logo depois), nunca "Na …", "No checkout …", "no-restricted…".
NONE_RE = re.compile(r"^\s*(?:(?:nenhum[a]?|none|nothing|inexistente|n[ãa]o\s+(?:existe|h[áa])|does\s+not\s+exist)"
                     r"(?![\w-])|(?:n[ãa]o|no|n/a)(?=\s*(?:$|[.!;:,(—–]|-\s)))[\s.!]*", re.I)
EXTLESS = r"(?:Makefile|GNUmakefile|Dockerfile|Containerfile|Jenkinsfile|Procfile|Gemfile|Rakefile|Justfile|Vagrantfile)"
# dotfile sem extensão na raiz (`.editorconfig:3`) não casava: o nome depois do ponto passa de 8 caracteres;
# U2b: ponto final de frase (`… é .editorconfig.`) não impede o dotfile, e `.NET` (o stack) não é dotfile
PATH_RE = re.compile(r"((?:[\w.@-]+/)*" + EXTLESS + r"(?![\w.])|"
                     r"(?:[\w.@-]+/)*\.(?!NET\b)[A-Za-z][\w-]{1,30}(?![\w/]|\.\w)|"
                     r"(?:[\w.@-]+/)*[\w.@-]+\.[A-Za-z0-9]{1,8}|"
                     r"(?:[\w.@-]+/)+[\w.@-]+)(?::(\d+))?")
_NUMERIC = re.compile(r"^[\s\d_.,*+/()x-]+[a-zA-Z%]{0,4}$")
SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b")


def _out_allowed(root, out):
    """`--out` fora do alvo, ou dentro de `<alvo>/.swarm/tmp/` (área de rascunho, excluída da cópia).
    Em qualquer outro lugar do alvo a cópia ficaria dentro do repo examinado (e o gabarito a um `../`)."""
    if out != root and not out.startswith(root + os.sep):
        return True
    tmp = os.path.join(root, STATE_DIR, "tmp")
    return out.startswith(tmp + os.sep)


def _git(cwd, args, check=True):
    from cslib import gitx
    return gitx.run(cwd, args, check=check)


def _is_repo_root(root):
    try:
        code, out, _ = _git(root, ["rev-parse", "--show-toplevel"], check=False)
    except CsError:
        return False
    return code == 0 and os.path.realpath(out.decode("utf-8", "replace").strip()) == os.path.realpath(root)


def _history_unsafe(root):
    """Motivo pelo qual o histórico do alvo NÃO pode ir à cópia (ou None): `.swarm/` (gabarito, cartões,
    respostas) versionado em algum commit seria alcançável por `git show`/`git log -p` no exame."""
    code, out, _ = _git(root, ["log", "--all", "--format=%H", "-1", "--", STATE_DIR], check=False)
    if code != 0:
        return "git log falhou no alvo"
    if out.strip():
        return ".swarm/ aparece no histórico do alvo (commit %s)" % out.decode().strip()[:12]
    return None


def _working_files(root):
    """Arquivos do working tree do alvo (versionados + não ignorados), sem `.swarm/` e `.git/`."""
    from team._shared_tmp.common import list_repo_files
    files = None
    if _is_repo_root(root):
        try:
            from cslib import gitx
            files = gitx.ls_files(root)[0]
        except CsError:
            files = None
    if files is None:
        files = list_repo_files(root)
    return [f for f in files if not (f == STATE_DIR or f.startswith((".swarm/", ".git/")) or f == ".git")]


def copy_for_exam(root, dest):
    """Cópia do alvo para o exame guiado → (nº de arquivos, {mode, reason?}).

    Alvo git: `git clone --local --no-hardlinks --no-checkout` (histórico do ALVO, sem remote apontando de volta) +
    os arquivos do working tree copiados por cima (`.swarm/` nunca) + `git reset` (índice = HEAD); assim
    `git log/show` respondem as sondas de histórico e nunca sobem para um repositório pai.
    Sem git, ou com `.swarm/` no histórico: `git init` vazio na cópia — `git log` falha ("sem commits") em vez
    de mostrar commits de outro repositório."""
    import shutil
    files = _working_files(root)
    hist = {"mode": "none"}
    cloned = False
    if _is_repo_root(root):
        why = _history_unsafe(root)
        if why:
            hist["reason"] = why
        else:
            code, _, err = _git(os.path.dirname(dest), ["clone", "-q", "--local", "--no-hardlinks", "--no-checkout",
                                                        root, dest], check=False)
            if code == 0:
                _git(dest, ["remote", "remove", "origin"], check=False)
                cloned = True
                hist = {"mode": "clone"}
            else:
                shutil.rmtree(dest, ignore_errors=True)
                hist["reason"] = "git clone falhou: %s" % err.decode("utf-8", "replace").strip()[:200]
    else:
        hist["reason"] = "alvo sem histórico git"
    os.makedirs(dest, exist_ok=True)
    n = 0
    for rel in files:
        src = os.path.join(root, rel)
        if os.path.islink(src) or not os.path.isfile(src):
            continue
        dst = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        n += 1
    try:
        if cloned:
            _git(dest, ["reset", "-q"], check=False)  # índice = HEAD; working tree = o do alvo (sem tocar arquivo)
        else:
            _git(dest, ["init", "-q"], check=False)  # teto: `git log` aqui nunca sobe para um repo pai
    except CsError as exc:  # git ausente: sem git, também não há repo pai a alcançar
        hist.setdefault("reason", str(exc))
    return n, hist


def exam_pack_isolated(target, agent, out):
    """`probes exam-pack <agente> --out <dir>`: exame guiado ISOLADO — `<dir>/repo/` = cópia do alvo sem
    `.swarm/` (gabarito inalcançável pela cópia), COM o histórico git do alvo (clone local) para as sondas de
    histórico; + `<dir>/questions.json5`. `--out` fica fora do alvo ou em `<alvo>/.swarm/tmp/` (rascunho, nunca
    copiado). Respostas: UM caminho por agente (campanha-iter11, P-1) — o `answer_file` do pacote canônico,
    `.swarm/probes/exams/<agente>.answers.json5` (aqui em caminho absoluto), lido por `probes check <agente>`
    sem `--answers`; a iteração 4 tinha 3 caminhos (`<dir>/answers.json5`, o canônico e o do prompt)."""
    import shutil
    from cslib import json5io
    out = os.path.realpath(os.path.abspath(os.path.expanduser(out)))
    root = os.path.realpath(target)
    if not _out_allowed(root, out):
        raise CsError("--out dentro do alvo fora de .swarm/tmp/: o examinado alcançaria o gabarito "
                      "(.swarm/probes/bank.json5) e a cópia ficaria dentro do repo examinado",
                      "use `<alvo>/.swarm/tmp/exam/%s` ou um diretório fora do alvo" % agent)
    if os.path.isdir(out) and os.listdir(out):
        if not os.path.isfile(os.path.join(out, "exam.json5")):
            raise CsError("--out existe e não é um exame anterior: %s" % out, "use um diretório vazio")
        shutil.rmtree(out)
    path, pack = exam_pack(target, agent)
    os.makedirs(out, exist_ok=True)
    n, hist = copy_for_exam(root, os.path.join(out, "repo"))
    iso = dict(pack)
    iso["repo"] = os.path.join(out, "repo")
    iso["answer_file"] = os.path.join(root, pack["answer_file"])  # caminho único (o mesmo do pacote canônico)
    git_note = (" O histórico git do repositório está na cópia: use `git -C %s log|show` (leitura)." % iso["repo"]
                if hist["mode"] == "clone" else " A cópia não tem histórico git (%s): não invente sha; sonda de "
                "commit sem evidência fica `nao_sei`." % hist.get("reason"))
    iso["instructions"] = pack["instructions"] + (" Trabalhe SÓ dentro de `%s` (cópia do repositório; nunca saia "
                                                  "dela com `..`); grave as respostas SÓ em `%s` (único arquivo "
                                                  "fora da cópia que você escreve; não leia nada ao lado dele)." % (
                                                      iso["repo"], iso["answer_file"])) + git_note
    qpath = os.path.join(out, "questions.json5")
    with open(qpath, "w", encoding="utf-8") as fh:
        fh.write(json5io.dumps(iso, "perguntas do exame de %s (sem gabarito) — cs.py probes exam-pack --out" % agent))
    with open(os.path.join(out, "exam.json5"), "w", encoding="utf-8") as fh:
        fh.write(json5io.dumps({"schema_version": 1, "agent": agent, "repo": "repo/", "files": n,
                                "questions": len(pack["questions"]), "excluded": [".swarm/"],
                                "history": hist, "probes_sha256": pack.get("probes_sha256"),
                                "card_sha256": pack.get("card_sha256")},
                               "manifesto do exame isolado — cs.py probes exam-pack --out"))
    write_json(target, _copy_pointer(target, agent), {"schema_version": 1, "agent": agent, "out": out,
                                                      "repo": os.path.join(out, "repo")},
               "cópia de exame viva de %s — apagada por `probes check %s` (sanitize)" % (agent, agent))
    return qpath, iso, n


def _copy_pointer(target, agent):
    return sp_path(target, "probes", "exams", "%s.exam-copy.json5" % agent)


def remove_exam_copy(target, agent):
    """Apaga a cópia isolada (`<out>/repo/`, clone com `.git` próprio) do exame de `agent` logo após o
    `probes check` dele — 15 clones acumulados em `.swarm/tmp/exam/` somaram 86 MB no repositório-piloto (projeto-legado)
    (2026-10-03). Só apaga o que `exam-pack --out` criou: `<out>/exam.json5` do MESMO agente e `<out>/repo`, nunca
    o alvo nem um ancestral dele. → caminho apagado ou None. Nunca levanta (a pontuação já foi gravada)."""
    import shutil
    ptr = _copy_pointer(target, agent)
    try:
        info = read_json(ptr, "ponteiro da cópia de exame") if os.path.isfile(find_doc(ptr)) else None
    except CsError:
        info = None
    root = os.path.realpath(target)
    outs = []
    if info and info.get("out"):
        outs.append(info["out"])
    outs.append(os.path.join(root, STATE_DIR, "tmp", "exam", agent))  # local recomendado em validate.3
    removed = None
    for out in outs:
        out = os.path.realpath(out)
        repo = os.path.join(out, "repo")
        if not os.path.isdir(repo) or os.path.islink(repo):
            continue
        if root == repo or root.startswith(repo + os.sep):
            continue
        try:
            man = read_json(os.path.join(out, "exam.json5"), "manifesto do exame")
        except CsError:
            continue
        if man.get("agent") != agent:
            continue
        shutil.rmtree(repo, ignore_errors=True)
        if not os.path.exists(repo):
            removed = removed or repo
    if info is not None:
        try:
            os.remove(find_doc(ptr))
        except OSError:
            pass
    return removed


def exam_pack(target, agent):
    from probes.final import card_shas
    bank = load_bank(target)
    qs = [{"id": p["id"], "type": p["type"], "question": p["question"]}
          for p in bank["probes"] if p["agent"] == agent]
    if not qs:
        raise CsError("nenhuma sonda para o agente %s" % agent, "confira o nome ou rode `probes generate`")
    pack = {"schema_version": 1, "agent": agent,
            "instructions": ("Responda cada pergunta com o que você sabe deste repositório. Para cada id, "
                             "devolva {id, answer, evidence[]}; evidence = 'arquivo:linha' ou comando que "
                             "prova. Se o que foi perguntado não existe, responda NENHUM. Não invente: "
                             "afirmar algo inexistente veta o exame."),
            "answer_file": ".swarm/probes/exams/%s.answers.json5" % agent,
            "answer_format": [{"id": "P-...", "answer": "texto (arquivo:linha, comando, sha ou NENHUM)",
                               "evidence": ["arquivo:linha", "comando"]}],
            "questions": qs,
            "probes_sha256": _agent_probes_sha(bank, agent),
            # cartão examinado (mesmo hash de cards/status.json5): `probes check` recusa o exame se o cartão mudou
            "card_sha256": card_shas(target).get(agent)}
    path = sp_path(target, "probes", "exams", "%s.questions.json5" % agent)
    write_json(target, path, pack)
    return path, pack


def _agent_probes_sha(bank, agent):
    import hashlib
    import json
    probes = [{k: p.get(k) for k in ("id", "question", "answer")} for p in bank["probes"] if p["agent"] == agent]
    return hashlib.sha256(json.dumps(probes, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _text(ans):
    if ans is None:
        return ""
    if isinstance(ans, str):
        return ans
    if isinstance(ans, (list, tuple)):
        return "\n".join(_text(x) for x in ans)
    if isinstance(ans, dict):
        return "\n".join("%s" % _text(v) for k, v in sorted(ans.items()))
    return str(ans)


def is_none(text):
    """Resposta negativa: começa por NENHUM/none/não existe. Parêntese explicativo com caminho depois do NENHUM
    (`NENHUM (o comentário em a/b.ts só menciona)`) continua negativa — iteração 2 contava como alucinação."""
    t = (text or "").strip().strip("`*_").strip()
    if not t:
        return True
    m = NONE_RE.match(t)
    if not m:
        return False
    rest = t[m.end():].strip()
    return not rest or rest[0] in "(—–-:;,." or not any("/" in p for p, _ in cites(rest))


def cites(text):
    """[(path, line|None)] citados num texto."""
    out = []
    for m in PATH_RE.finditer(text or ""):
        p = m.group(1)[2:] if m.group(1).startswith("./") else m.group(1)
        out.append((p, int(m.group(2)) if m.group(2) else None))
    return out


def _digits(s):
    return re.sub(r"[_,\s]", "", s)


def value_ok(val, text):
    """Regra de negócio é julgada pelo FATO (local certo), não por string literal: só valor numérico/constante
    curta é exigido (normalizado: 900_000 = 900000); frase (nome de teste, descrição) não precisa ser repetida."""
    if val in (None, ""):
        return True
    v = str(val).strip()
    low = text.lower()
    if _NUMERIC.match(v):
        nums = re.findall(r"\d[\d_,]*(?:\.\d+)?", v)
        got = set(_digits(x) for x in re.findall(r"\d[\d_,]*(?:\.\d+)?", text))
        return all(_digits(n) in got for n in nums) if nums else v.lower() in low
    if len(v.split()) <= 2:  # constante/identificador/enum: precisa aparecer (sem diferenciar caixa/_)
        norm = lambda x: re.sub(r"[\s_-]+", "", x.lower())  # noqa: E731
        return norm(v) in norm(text)
    return True


class Checker(object):
    def __init__(self, target, require_evidence=True):
        self.target = target
        self.require_evidence = require_evidence
        self.f = Facts(target)
        self.files = set(self.f.all_files())
        self.ops = set(norm_cmd(o["command"]) for o in self.f.operations())
        self._lines = {}
        self._defs = None

    def definitions(self, name):
        """[(path, line)] onde o símbolo `name` (nome exato) é definido — grafo L1 ou regex."""
        if self._defs is None:
            self._defs = {}
            for sy in self.f.symbols():
                self._defs.setdefault(sy["name"], []).append((sy["path"], sy["line"]))
        return self._defs.get(name) or []

    def lines(self, p):
        if p not in self._lines:
            self._lines[p] = read_lines(self.target, p)
        return self._lines[p]

    def evidence_ok(self, ev):
        e = str(ev).strip()
        m = re.match(r"^([^\s:]+):(\d+)(?:-\d+)?(?:[\s,;(—–-].*)?$", e)  # comentário depois é tolerado
        if m:
            p = m.group(1)[2:] if m.group(1).startswith("./") else m.group(1)
            ls = self.lines(p) if p in self.files else None
            return ls is not None and 1 <= int(m.group(2)) <= max(len(ls), 1)
        if " " not in e and (e in self.files or (e[2:] if e.startswith("./") else e) in self.files):
            return True
        n = norm_cmd(e)
        return n in self.ops or n.startswith(INSPECT_CMDS)

    def score_one(self, probe, ans):
        """→ (passed: bool, hallucination: bool, reason: str, panel_pending: bool)."""
        text = _text(ans.get("answer")) if ans else ""
        evid = [str(x) for x in (ans.get("evidence") or [])] if ans else []
        if not ans:
            return False, False, "sem resposta", False
        bad = [e for e in evid if not self.evidence_ok(e)]
        if self.require_evidence:
            if bad:
                return False, True, "evidência inexistente: %s" % bad[0], False
            if not evid:
                return False, False, "sem evidência citada", False
        exp = probe["answer"]
        none = is_none(text)
        if not exp.get("exists", True):
            if none:
                return True, False, "negativa correta", False
            return False, True, "afirmou padrão inexistente (alucinação)", False
        if none:
            return False, False, "respondeu NENHUM para algo que existe", False
        t = probe["type"]
        allc = cites(text) + [c for e in evid for c in cites(e)]
        if t in ("location",) or (t == "term" and exp.get("variant") == "where"):
            targets = [(exp["path"], exp["line"])]
            if t == "term" and exp.get("term"):  # a definição exata do termo também é resposta certa
                targets += self.definitions(exp["term"])
            ok = any(p == tp and (ln is not None and abs(ln - tl) <= LINE_TOL)
                     for p, ln in cites(text) for tp, tl in targets)
            return ok, False, "localização %s" % ("ok" if ok else "errada (esperado arquivo:linha ±3)"), False
        if t == "term":
            low = " %s " % re.sub(r"[^\w]+", " ", text.lower())
            if exp.get("variant") == "canonical":
                ok = (" %s " % exp["canonical"].lower()) in low
            else:
                ok = any((" %s " % v.lower()) in low for v in exp.get("never_use") or [])
            return ok, False, "termo %s" % ("ok" if ok else "errado"), False
        if t == "command":
            cands = [norm_cmd(x) for x in re.findall(r"`([^`]+)`", text)] + [norm_cmd(text)]
            want = [norm_cmd(exp["command"])] + [norm_cmd(x) for x in exp.get("alternatives") or []]
            ok = any(w in cands for w in want)  # duas respostas corretas (mesmo propósito) valem as duas
            return ok, False, "comando %s" % ("ok" if ok else "diferente"), False
        if t == "existence":
            ok = any(p in set(exp.get("files") or []) for p, _ in allc)
            return ok, False, "existência %s" % ("ok" if ok else "sem arquivo do gabarito"), False
        if t == "dependency":
            from cslib import refs
            subject = exp.get("subject") or ""
            want = set(exp.get("files") or [])
            got = set()
            for p, _ in cites(text):
                if refs.is_package(p) or p == subject or (subject and subject.endswith("/" + p)):
                    continue  # `@shop/shared` em prosa e o próprio arquivo perguntado não são "arquivo extra"
                if p in self.files or ("/" in p and not any(f.endswith("/" + p) for f in want)):
                    got.add(p)
                elif any(f.endswith("/" + p) for f in want):
                    got.add([f for f in want if f.endswith("/" + p)][0])
            ok = got == want
            return ok, False, "conjunto %s" % ("igual" if ok else "diferente (falta %s, sobra %s)" % (
                sorted(want - got)[:3], sorted(got - want)[:3])), False
        if t == "history":
            ok = any(exp["sha"].startswith(s) for s in SHA_RE.findall(text.lower()))
            return ok, False, "sha %s" % ("ok" if ok else "errado"), False
        if t == "prohibition":
            tg = exp.get("enforced_at") or []
            # gabarito no cabeçalho (linha 1) de config com várias regras: a imposição é o ARQUIVO; qualquer
            # linha dele vale (iteração 2: eslint.config.mjs:1 reprovava quem citava a linha da regra)
            tg = [dict(x, line=None) if exp.get("file_level") or int(x.get("line") or 1) <= 1 else x for x in tg]
            ok = self._near(allc, tg)
            return ok, False, "imposição %s" % ("ok" if ok else "não localizada"), False
        if t == "business_rule":
            loc = self._near(allc, exp.get("sources") or [], need_line=True)
            vok = value_ok(exp.get("value"), text)
            ok = loc and vok
            return ok, False, "regra %s" % ("ok" if ok else ("local errado" if not loc else "valor errado")), False
        if t == "why":
            terms = [k.lower() for k in exp.get("key_terms") or []]
            ok = False
            for p, ln in allc:
                ls = self.lines(p) if p in self.files else None
                if ls is None or ln is None:
                    continue
                win = " ".join(ls[max(0, ln - 1 - LINE_TOL): ln + LINE_TOL]).lower()
                # sem termos-chave: basta citar o DOCUMENTO-fonte (qualquer linha); o mérito é do painel. Exigir
                # ±LINE_TOL do título/Status reprovava quem citava a seção de Contexto (cobaia .NET 2026-10-05)
                if (terms and any(k in win for k in terms)) or (
                        not terms and any(p == s.get("file") for s in exp["sources"])):
                    ok = True
                    break
            return ok, False, "fonte %s (painel decide o mérito)" % ("ok" if ok else "não citada"), ok
        return False, False, "tipo desconhecido %s" % t, False

    @staticmethod
    def _near(cited, targets, need_line=False):
        for p, ln in cited:
            for tg in targets:
                if p != tg["file"]:
                    continue
                if ln is None:
                    if not need_line:
                        return True
                elif tg.get("line", 1) is None or abs(ln - int(tg.get("line") or 1)) <= LINE_TOL:
                    return True
        return False


def panel_verdict(entry, probe):
    """Veredito do painel de juízes para ESTA sonda: {verdict, probe_sha256} só vale se a sonda é a mesma
    (iteração 2: P-security-17 do banco r2 herdou o FAIL dado à P-security-17 do banco r1)."""
    if entry is None:
        return None
    if isinstance(entry, dict):
        from probes.generate import probe_sha
        if entry.get("probe_sha256") != probe_sha(probe):
            return None
        return entry.get("verdict")
    return entry  # formato antigo {id: "PASS"}: sem identidade da sonda


def _load_answers(path):
    raw = read_json(path, "respostas")
    if isinstance(raw, dict):
        raw = raw.get("answers") or []
    if not isinstance(raw, list):
        raise CsError("respostas devem ser lista [{id, answer, evidence}]: %s" % path)
    return {str(a.get("id")): a for a in raw if isinstance(a, dict) and a.get("id")}


def _score(target, bank, agent, answers, require_evidence):
    ch = Checker(target, require_evidence=require_evidence)
    panel = {}
    pp = sp_path(target, "probes", "panel", "%s.json5" % agent)
    if require_evidence and os.path.isfile(find_doc(pp)):
        panel = read_json(pp, "painel")
    rows = []
    for p in bank["probes"]:
        if p["agent"] != agent:
            continue
        ok, hall, why, pend = ch.score_one(p, answers.get(p["id"]))
        verdict = panel_verdict(panel.get(p["id"]), p)
        if p.get("panel") and verdict:
            # o veredito dos juízes POR-QUÊ prevalece sobre o pré-check mecânico (iteração 3: "Na Black Friday…"
            # julgado 3/3 PASS saía "respondeu NENHUM"); evidência inexistente continua veto (não é heurística)
            ok = verdict == "PASS" and not hall
            pend = False
            why += "; painel=%s" % verdict
        rows.append({"id": p["id"], "type": p["type"], "scope": p["scope"], "negative": p.get("negative", False),
                     "discriminative": p.get("discriminative"), "pass": ok, "hallucination": hall,
                     "reason": why, "panel_pending": pend})
    if not rows:
        raise CsError("nenhuma sonda para o agente %s no banco" % agent)
    return rows


def _ratio(rows):
    return round(sum(1 for r in rows if r["pass"]) / float(len(rows)), 4) if rows else None


def check(target, agent, answers_path=None):
    bank = load_bank(target)
    answers_path = answers_path or sp_path(target, "probes", "exams", "%s.answers.json5" % agent)
    rows = _score(target, bank, agent, _load_answers(answers_path), True)
    disc = [r for r in rows if r["discriminative"] is not False]
    # não medido ≠ reprovado (decisoes.nao_medido): escopo em que o baseline sem cartão acertou TUDO não tem sonda
    # que discrimine — usa o score sem filtro daquele escopo e marca `baseline_saturated` (visível no relatório)
    saturated = []
    scores = {}
    for scope in ("territory", "cross"):
        scores[scope] = _ratio([r for r in disc if r["scope"] == scope])
        if scores[scope] is None and any(r["scope"] == scope for r in rows):
            scores[scope] = _ratio([r for r in rows if r["scope"] == scope])
            saturated.append(scope)
    terr, cross = scores["territory"], scores["cross"]
    hall = sum(1 for r in rows if r["hallucination"])
    raw_all = _ratio(rows)
    base = (bank.get("baseline") or {}).get(agent)
    delta = round(raw_all - base["score"], 4) if base else None
    reasons = []
    if terr is None or terr < G4["territory"]:
        reasons.append("território %s < %.2f" % (terr, G4["territory"]))
    if cross is None or cross < G4["cross"]:
        reasons.append("cross %s < %.2f" % (cross, G4["cross"]))
    if hall:
        reasons.append("%d alucinação(ões) — veto" % hall)
    if delta is None:
        reasons.append("baseline sem cartão ausente (rode baseline-filter): delta não medido")
    elif delta <= 0:
        reasons.append("delta sobre baseline = %s ≤ 0" % delta)
    pend = [r["id"] for r in rows if r["panel_pending"]]
    rep = {"schema_version": 1, "agent": agent, "gate": "G4",
           "thresholds": dict(G4, hallucinations=0, delta=">0"),
           "score_territory": terr, "score_cross": cross, "hallucinations": hall,
           "score_all_raw": raw_all, "baseline_score": base["score"] if base else None, "delta": delta,
           "excluded_non_discriminative": sum(1 for r in rows if r["discriminative"] is False),
           "baseline_saturated": bool(saturated), "baseline_saturated_scopes": saturated,
           "panel_pending": pend, "decision": "PASS" if not reasons else "FAIL",
           "provisional": bool(pend), "reasons": reasons, "probes": rows}
    write_json(target, sp_path(target, "probes", "reports", "%s.json5" % agent), rep)
    agg_p = sp_path(target, "probes", "report.json5")
    agg = read_json(agg_p, "report.json5") if os.path.isfile(find_doc(agg_p)) else {"schema_version": 1, "agents": {}}
    prev_row = agg.setdefault("agents", {}).get(agent) or {}
    row = {k: rep[k] for k in ("score_territory", "score_cross", "hallucinations", "delta", "decision",
                               "provisional", "reasons", "baseline_saturated")}
    for k in ("closed_mode", "status", "cycles", "allowed"):
        if k in prev_row:
            row[k] = prev_row[k]
    agg["agents"][agent] = row
    # linha só com `closed_mode` (modo fechado pontuado antes do guiado) não tem `decision`: não examinado = não PASS
    agg["g4"] = "PASS" if agg["agents"] and all(v.get("decision") == "PASS" for v in agg["agents"].values()) else "FAIL"
    write_json(target, agg_p, agg)
    # pontuado: a cópia do exame não serve mais (sanitize, causa) — EXCETO com painel why pendente: os juízes leem
    # o repo NESSA cópia (cobaia .NET 2026-10-05: apagada antes do painel, teve de ser recriada à mão)
    removed = None if rep.get("panel_pending") else remove_exam_copy(target, agent)
    if removed:
        rep["exam_copy_removed"] = removed
    return rep


def baseline_filter(target, agent, answers_path=None):
    bank = load_bank(target)
    answers_path = answers_path or sp_path(target, "probes", "exams", "%s.baseline.json5" % agent)
    answers = _load_answers(answers_path)
    ids = set(p["id"] for p in bank["probes"] if p["agent"] == agent)
    if answers and sum(1 for k in answers if k in ids) * 2 < len(answers):
        raise CsError("%s: baseline respondeu sondas de outro banco" % agent,
                      "rode o baseline de novo com `probes exam-pack %s`" % agent, code=1)
    rows = _score(target, bank, agent, answers, False)
    passed = set(r["id"] for r in rows if r["pass"])
    n = 0
    for p in bank["probes"]:
        if p["agent"] == agent:
            p["discriminative"] = p["id"] not in passed
            n += 0 if p["discriminative"] else 1
    bank.setdefault("baseline", {})[agent] = {"score": _ratio(rows), "non_discriminative": n,
                                              "hallucinations": sum(1 for r in rows if r["hallucination"]),
                                              "probes_sha256": _agent_probes_sha(bank, agent),
                                              "answered": sum(1 for k in answers if k in ids), "probes": len(ids)}
    write_json(target, sp_path(target, "probes", "bank.json5"), bank)
    return bank["baseline"][agent]


CLOSED_NOTE = ("modo fechado = só o cartão, sem acesso ao repositório: mede o que o cartão CARREGA, não o que o "
               "agente sabe achar. Cartão é MAPA (aponta onde está), não memória; score baixo aqui é esperado e "
               "não entra no G4.")


def closed_check(target, agent, answers_path=None):
    """Pontua o exame em modo fechado (sem evidência exigida, como o baseline) e grava em report.json5
    `agents.<a>.closed_mode = {score, hallucinations, note}` — SINAL explícito, fora do G4 e dos ciclos."""
    bank = load_bank(target)
    answers_path = answers_path or sp_path(target, "probes", "exams", "%s.closed.json5" % agent)
    rows = _score(target, bank, agent, _load_answers(answers_path), False)
    res = {"score": _ratio(rows), "hallucinations": sum(1 for r in rows if r["hallucination"]),
           "baseline_score": ((bank.get("baseline") or {}).get(agent) or {}).get("score"), "note": CLOSED_NOTE}
    agg_p = sp_path(target, "probes", "report.json5")
    agg = read_json(agg_p, "report.json5") if os.path.isfile(find_doc(agg_p)) else {"schema_version": 1, "agents": {}}
    agg.setdefault("agents", {}).setdefault(agent, {})["closed_mode"] = res
    agg["closed_mode_note"] = CLOSED_NOTE
    write_json(target, agg_p, agg)
    return res
