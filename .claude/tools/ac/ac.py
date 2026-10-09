#!/usr/bin/env python3
"""ac.py — estado mecânico da auto-correcao (stdlib, Python 3.9+).

Campanha em <work>/.auto-correcao/: state.json (estado), ledger.jsonl (toda mutação), rounds/<n>/ (DEFEITOS.json5,
PLANO.json5, fronts/, runs.jsonl). O modelo interpreta e decide; este script guarda, confere e recusa.

Uso: python3 ac.py --work <dir> <comando> ...   (veja `ac.py --help`)
Exit: 0 ok · 1 check não satisfeito · 2 entrada inválida.
"""
import argparse
import datetime
import fnmatch
import getpass
import hashlib
import hmac
import json
import os
import re
import secrets
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_frase():
    """Módulo compartilhado scripts/frase.py, carregado pelo caminho (funciona também quando ac.py é importado)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("ac_frase", os.path.join(HERE, "frase.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


frase = _load_frase()
CICLO = os.path.join(os.path.dirname(HERE), "references", "ciclo.json5")
if not os.path.isfile(CICLO):  # motor EMBUTIDO (.claude/tools/ac/): references/ ao lado do ac.py (ver ORIGEM.txt)
    CICLO = os.path.join(HERE, "references", "ciclo.json5")


class Fail(Exception):
    """Check não satisfeito (exit 1)."""


class Bad(Exception):
    """Entrada inválida (exit 2)."""


# ------------------------------------------------------------------ JSON5 (subconjunto usado pela skill)

def _fix_code(seg):
    """Só fora de strings: vírgula final e chave sem aspas."""
    seg = re.sub(r",(\s*[}\]])", r"\1", seg)
    return re.sub(r'([{,]\s*)([A-Za-z_][\w-]*)(\s*:)', r'\1"\2"\3', seg)


def json5_loads(text):
    """Comentários // e /* */, vírgula final, chaves sem aspas, strings '...' e `...` (multilinha)."""
    out, code, i, n = [], [], 0, len(text)

    def flush():
        if code:
            out.append(_fix_code("".join(code)))
            del code[:]
    while i < n:
        c = text[i]
        if c in "\"'`":
            q, j, buf = c, i + 1, []
            while j < n and text[j] != q:
                if text[j] == "\\" and j + 1 < n:
                    nxt = text[j + 1]
                    # \` e \' viram o caractere literal (inválidos em JSON); demais escapes passam intactos
                    buf.append(nxt if (q != '"' and nxt in "`'") else text[j:j + 2])
                    j += 2
                    continue
                buf.append(text[j])
                j += 1
            s = "".join(buf)
            if q != '"':
                s = s.replace('"', '\\"')
            s = s.replace("\n", "\\n").replace("\t", "\\t")
            flush()
            out.append('"' + s + '"')
            i = j + 1
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
        elif text.startswith("/*", i):
            k = text.find("*/", i + 2)
            i = n if k < 0 else k + 2
        else:
            code.append(c)
            i += 1
    flush()
    return json.loads("".join(out))


def json5_load(path):
    with open(path, encoding="utf-8") as fh:
        return json5_loads(fh.read())


# ------------------------------------------------------------------ campanha

def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Campaign:
    def __init__(self, work):
        self.work = os.path.realpath(work)
        self.dir = os.path.join(self.work, ".auto-correcao")
        self.state_path = os.path.join(self.dir, "state.json")

    def exists(self):
        return os.path.isfile(self.state_path)

    def load(self):
        if not self.exists():
            raise Bad("campanha não iniciada em %s — rode `ac.py --work %s init ...`" % (self.work, self.work))
        with open(self.state_path, encoding="utf-8") as fh:
            return json.load(fh)

    def save(self, st, event, **fields):
        os.makedirs(self.dir, exist_ok=True)
        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(st, fh, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, self.state_path)
        self.log(event, **fields)

    def log(self, event, **fields):
        os.makedirs(self.dir, exist_ok=True)
        rec = dict(ts=now(), event=event, **fields)
        with open(os.path.join(self.dir, "ledger.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")

    def round_dir(self, st, r=None):
        d = os.path.join(self.dir, "rounds", str(st["round"] if r is None else r))
        os.makedirs(d, exist_ok=True)
        return d

    def runs(self, st, r=None):
        p = os.path.join(self.round_dir(st, r), "runs.jsonl")
        if not os.path.isfile(p):
            return []
        with open(p, encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]


def ciclo():
    return json5_load(CICLO)


def get(d, dotted):
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def put(d, dotted, value):
    parts = dotted.split(".")
    cur = d
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


def sha_files(paths):
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.encode())
        with open(p, "rb") as fh:
            # CRLF->LF antes do hash: o checkout Windows (autocrlf) não muda o oráculo; só-LF = hash de antes
            h.update(hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).digest())
    return h.hexdigest()


# ------------------------------------------------------------------ checks (provam efeito)

def chk_require(c, st, args):
    missing = []
    for a in args:
        if a.startswith("gate:"):
            if not gate_approved(st, a[5:]):
                missing.append("portão '%s' aprovado (ac.py gate %s --by <humano> --decision approve)" % (a[5:], a[5:]))
        elif get(st, a) in (None, "", [], {}):
            missing.append(a)
    if missing:
        raise Fail("faltando: " + "; ".join(missing))


def gate_approved(st, name):
    """Portão aprovado por humano: decision=approve e NÃO simulado (simulado nunca satisfaz `gate:X`)."""
    g = (st.get("gates") or {}).get(name)
    return isinstance(g, dict) and g.get("decision") == "approve" and not g.get("simulated")


def chk_oracle_verify(c, st, args):
    o = st.get("oracle", {})
    if not o.get("files") or not o.get("hash"):
        raise Fail("oráculo não congelado (ac.py oracle freeze --file ...)")
    missing = [p for p in o["files"] if not os.path.isfile(p)]
    if missing:
        raise Fail("arquivos do oráculo sumiram: %s" % missing)
    cur = sha_files(o["files"])
    if cur != o["hash"]:
        raise Fail("oráculo mudou fora de `oracle change` (hash %s ≠ congelado %s)" % (cur[:12], o["hash"][:12]))


def _flag(args, name, default=None):
    return args[args.index(name) + 1] if name in args else default


def chk_runs(c, st, args):
    r = int(_flag(args, "--round", st["round"]))
    cfg = _flag(args, "--config")
    mn = int(_flag(args, "--min", 1))
    latest = {}
    for x in c.runs(st, r):  # o registro mais recente de cada (alvo, config) substitui os anteriores
        latest[(x.get("alvo"), x.get("config"))] = x
    runs = [x for x in latest.values() if cfg is None or x.get("config") == cfg]
    if "--or-waived" in args and get(st, "waivers.%d.%s" % (r, cfg)):
        return
    if len(runs) < mn:
        raise Fail("rodada %d: %d execução(ões)%s registradas, mínimo %d (ac.py run record ...)"
                   % (r, len(runs), " '%s'" % cfg if cfg else "", mn))
    if "--graded" in args:
        ungraded = [x["alvo"] + "/" + x["config"] for x in runs if not x.get("quality", {}).get("total")]
        if ungraded:
            raise Fail("execuções sem nota de qualidade: %s" % ungraded)


def load_defects(c, st):
    p = os.path.join(c.round_dir(st), "DEFEITOS.json5")
    if not os.path.isfile(p):
        raise Fail("sem %s" % p)
    return json5_load(p).get("defeitos") or []


def chk_defects(c, st, args):
    ds = load_defects(c, st)
    if len(ds) < int(_flag(args, "--min", 1)):
        raise Fail("DEFEITOS.json5 com %d defeito(s)" % len(ds))
    if "--evidence" in args:
        sem = [d.get("id") for d in ds if not d.get("evidencia")]
        if sem:
            raise Fail("defeitos sem evidência: %s" % sem)
    if "--classified" in args:
        bad = [d.get("id") for d in ds if d.get("classe") not in ("sistema", "oraculo", "ambiente", "executor")
               or d.get("prioridade") not in ("P0", "P1", "P2", "P3")]
        if bad:
            raise Fail("defeitos sem classe/prioridade válidas: %s" % bad)


def load_plan(c, st):
    p = os.path.join(c.round_dir(st), "PLANO.json5")
    if not os.path.isfile(p):
        raise Fail("sem %s" % p)
    try:
        pl = json5_load(p)
    except ValueError as e:
        raise Fail("PLANO.json5 ilegível (%s): %s" % (p, e))
    validate_plan(pl)
    return pl


def _str_list(v):
    return isinstance(v, list) and all(isinstance(x, str) and x for x in v)


def validate_plan(pl):
    """Esquema mínimo do PLANO (AC-05): recusa com mensagem em vez de quebrar com traceback."""
    if not isinstance(pl, dict):
        raise Fail("PLANO.json5 precisa ser um objeto {parada, frentes: [...], decisoes: [...]}")
    errs = []
    fronts = pl.get("frentes")
    if fronts is not None and not isinstance(fronts, list):
        errs.append("'frentes' precisa ser lista de objetos {nome, escreve: [globs]}")
    for i, f in enumerate(fronts if isinstance(fronts, list) else []):
        if not isinstance(f, dict):
            errs.append("frentes[%d] precisa ser objeto {nome, escreve: [globs]} (recebido %r)" % (i, f))
            continue
        if not isinstance(f.get("nome"), str) or not f.get("nome"):
            errs.append("frentes[%d] sem 'nome' (texto)" % i)
        if f.get("escreve") is not None and not _str_list(f.get("escreve")):
            errs.append("frentes[%d].escreve precisa ser lista de globs (texto)" % i)
    decs = pl.get("decisoes")
    if decs is not None and not isinstance(decs, list):
        errs.append("'decisoes' precisa ser lista de objetos {id, produto: bool, ...}")
    for i, d in enumerate(decs if isinstance(decs, list) else []):
        if not isinstance(d, dict):
            errs.append("decisoes[%d] precisa ser objeto {id, produto: bool, ...} (recebido %r)" % (i, d))
            continue
        if not isinstance(d.get("id"), str) or not d.get("id"):
            errs.append("decisoes[%d] sem 'id' (texto)" % i)
        if "produto" in d and not isinstance(d.get("produto"), bool):
            errs.append("decisoes[%d].produto precisa ser true/false" % i)
    if errs:
        raise Fail("PLANO.json5 fora do esquema: " + "; ".join(errs))


def _prefix(glob):
    return re.split(r"[*?\[{]", glob, maxsplit=1)[0].rstrip("/")


def globs_overlap(a, b):
    """Aproximação conservadora: sobrepõem se um casa o outro ou se um prefixo literal contém o outro."""
    a, b = a.replace("\\", "/"), b.replace("\\", "/")  # caminho Windows: '\' vale como '/'
    if fnmatch.fnmatch(a, b) or fnmatch.fnmatch(b, a):
        return True
    pa, pb = _prefix(a), _prefix(b)
    if not pa or not pb:
        return True  # glob sem prefixo literal ("**", "*.py") pode tocar qualquer coisa
    return pa == pb or pa.startswith(pb + "/") or pb.startswith(pa + "/")


def chk_plan(c, st, args):
    pl = load_plan(c, st)
    fronts = pl.get("frentes") or []
    if not fronts:
        raise Fail("PLANO sem frentes")
    errs = []
    for i, f in enumerate(fronts):
        if not f.get("escreve"):
            errs.append("frente %s sem 'escreve'" % f.get("nome"))
        for g in f.get("escreve") or []:
            base = st.get("target") or c.work  # globs das frentes são relativos ao alvo
            for of in (st.get("oracle") or {}).get("files") or []:
                rel = os.path.relpath(of, base) if of.startswith(base + os.sep) else of
                if fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(of, g) or globs_overlap(g, rel):
                    errs.append("frente %s escreve no oráculo (%s ~ %s)" % (f.get("nome"), g, rel))
        for f2 in fronts[i + 1:]:
            for a in f.get("escreve") or []:
                for b in f2.get("escreve") or []:
                    if globs_overlap(a, b):
                        errs.append("frentes %s e %s se sobrepõem (%s ~ %s)" % (f.get("nome"), f2.get("nome"), a, b))
    if not pl.get("parada"):
        errs.append("PLANO sem 'parada'")
    if errs:
        raise Fail("; ".join(errs))


def chk_plan_gates(c, st, args):
    pl = load_plan(c, st)
    pend = [d.get("id") for d in pl.get("decisoes") or [] if d.get("produto")
            and not gate_approved(st, "plan:%s" % d.get("id"))]
    if pend:
        raise Fail("decisões de produto sem portão aprovado: %s (ac.py gate plan:<id> ...)" % pend)


def chk_fronts(c, st, args):
    pl = load_plan(c, st)
    d = os.path.join(c.round_dir(st), "fronts")
    miss = [f["nome"] for f in pl.get("frentes") or [] if not os.path.isfile(os.path.join(d, f["nome"] + ".md"))]
    if miss:
        raise Fail("frentes sem relatório: %s (ac.py front report <nome> --file ...)" % miss)


def chk_gate_ok(c, st, args):
    name = args[0] if args else "?"
    if gate_approved(st, name):
        return
    pa = (st.get("preauth") or {}).get(name)
    if pa:
        pend = [sid for sid in pa.get("requires") or [] if not st["done"].get(sid)]
        if pend:
            raise Fail("pré-autorização de '%s' exige %s concluídas (faltam: %s)" % (name, pa["requires"], pend))
        return
    raise Fail("portão '%s' não aprovado (nem pré-autorizado)" % name)


def cmd_preauth(c, a):
    """Pré-autorização HUMANA de um portão para a campanha inteira, condicionada a sub-etapas concluídas.
    v0.4: pede a FRASE do founder e grava seq/estado_hash/tag (ledger, audit e state)."""
    st = c.load()
    if a.simulated:
        raise Bad("pré-autorização não pode ser simulada: é uma decisão humana")
    if not a.requires:
        raise Bad("pré-autorização exige --requires <sub-etapa> (ex.: integracao.1 integracao.2) — nunca incondicional")
    cy = ciclo()
    for sid in a.requires:
        substage(cy, sid)
    audit = audit_log_path(c)
    tty, k = human_phrase(c, "pré-autorizar o portão '%s' (por %s), condicionado a %s"
                          % (a.name, a.by, ", ".join(a.requires)))
    seal = approval_seal(c, k, a.name, "preauth:" + ",".join(a.requires))
    audit_append(audit, c, tty, cmd="preauth", name=a.name, by=a.by, requires=a.requires, **seal)
    st.setdefault("preauth", {})[a.name] = {"by": a.by, "requires": a.requires, "note": a.note or "", "at": now(),
                                            "seq": seal["seq"], "tag": seal["tag"]}
    c.save(st, "preauth", name=a.name, by=a.by, requires=a.requires, **seal)
    print("portão %s pré-autorizado por %s, condicionado a %s" % (a.name, a.by, ", ".join(a.requires)))


# ------------------------------------------------------------------ canal humano (AC-04): tty + desafio + auditoria

WORDS = ("acude", "barco", "cedro", "dunas", "estrela", "farol", "garoa", "horta", "ilha", "jangada", "lagoa",
         "mangue", "neblina", "orvalho", "pedra", "quartzo", "rio", "serra", "trilha", "uva", "vento", "xisto",
         "zinco", "areia", "brisa", "canoa", "duna", "enseada", "folha", "gruta", "jasmim", "lenha", "musgo",
         "ninho", "onda", "palha", "raiz", "sal", "telha", "vale", "cobre", "ferro", "prata", "ouro", "lua", "sol",
         "nuvem", "chuva", "trigo", "milho", "cacau", "coco", "caju", "pinha", "figo", "lima", "manga", "pera")
DEFAULT_AUDIT = os.path.join("~", ".claude", "auto-correcao", "audit.jsonl")


def make_challenge(n=4):
    """Desafio aleatório (não pré-digitável): n dígitos. A proteção vem do tty exigido, não do texto; palavras
    confundiam o humano (AC-07: 4 recusas seguidas por redigitação errada no uso real)."""
    return "%0*d" % (n, secrets.randbelow(10 ** n))


def human_channel(what):
    """Exige um humano no terminal: stdin tty E /dev/tty; mostra `DESAFIO: ...` e só aceita a redigitação exata.
    Nenhuma variável de ambiente dispensa isto. Sem tty → Bad (exit 2). Retorna o ttyname (auditoria)."""
    try:
        stdin_tty = sys.stdin is not None and sys.stdin.isatty()
    except (ValueError, OSError):
        stdin_tty = False
    if not stdin_tty:
        raise Bad("aprovação humana exige terminal interativo (stdin tty); nada gravado. "
                  "Um agente não aprova portões — peça ao humano que rode este comando no terminal dele.")
    try:
        fd = os.open("/dev/tty", os.O_RDWR | getattr(os, "O_NOCTTY", 0))
    except OSError:
        raise Bad("aprovação humana exige /dev/tty (terminal controlador); nada gravado.")
    try:
        name = os.ttyname(sys.stdin.fileno())
    except OSError:
        name = "/dev/tty"
    ch = make_challenge()
    try:
        os.write(fd, ("Você vai %s.\nDESAFIO: %s\nDigite o número %s e aperte Enter: " % (what, ch, ch)).encode())
        buf = b""
        while not buf.endswith(b"\n") and len(buf) < 4096:
            chunk = os.read(fd, 1)
            if not chunk:
                break
            buf += chunk
    finally:
        os.close(fd)
    if buf.decode("utf-8", "replace").strip() != ch:
        raise Fail("desafio não confere — nada gravado")
    return name


def audit_log_path(c):
    """`$AC_AUDIT_LOG` é só CAMINHO (padrão ~/.claude/auto-correcao/audit.jsonl); dentro da campanha → recusa."""
    raw = os.environ.get("AC_AUDIT_LOG") or DEFAULT_AUDIT
    p = os.path.realpath(os.path.expanduser(raw))
    if p == c.work or p.startswith(c.work + os.sep):
        raise Bad("AC_AUDIT_LOG (%s) está dentro da campanha %s — o log de auditoria precisa ficar fora do --work"
                  % (p, c.work))
    return p


def audit_append(path, c, tty, **fields):
    rec = dict(fields, work=c.work, user=_os_user(), tty=tty, ts=now())
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError as e:
        raise Bad("não consegui gravar a auditoria em %s (%s); nada gravado" % (path, e))


def _os_user():
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 — getuser pode falhar sem LOGNAME/pwd
        return str(os.getuid()) if hasattr(os, "getuid") else "?"


# ------------------------------------------------------------------ canal humano v0.4: FRASE-SENHA + tag por aprovação

PER_CAMPAIGN_GATES = ("stop",)  # o resto dos portões vale por rodada (round new zera)


def ledger_records(c):
    """[(posição 1-based, registro)] das linhas não vazias do ledger.jsonl (linha ilegível vira {})."""
    p = os.path.join(c.dir, "ledger.jsonl")
    out = []
    if not os.path.isfile(p):
        return out
    with open(p, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                rec = {}
            out.append((len(out) + 1, rec if isinstance(rec, dict) else {}))
    return out


def state_hash(c):
    """sha256 dos bytes do state.json como estão agora (antes do comando que aprova)."""
    with open(c.state_path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def human_phrase(c, what):
    """(b) stdin tty e /dev/tty → senão exit 2; (c) frase definida e válida → senão exit 2 sem prompt;
    (d) um prompt `FRASE...:` sem eco, uma tentativa → errada = exit 1. Devolve (ttyname, chave das tags).
    Nenhum argumento, variável de ambiente ou stdin fornece a frase."""
    try:
        tty = frase.exigir_tty()
        fj = frase.carregar()
        f = frase.ler("FRASE do founder (sem eco): ", contexto="Você vai %s." % what)
    except (frase.SemTTY, frase.ArquivoInvalido) as e:
        raise Bad(str(e))
    if not frase.confere(fj, f):
        raise Fail("senha ou frase não confere — nada gravado")
    return tty, frase.chave(fj, f)


def approval_seal(c, k, nome, decisao):
    """seq (linha do evento no ledger), estado_hash (state.json antes) e tag HMAC sobre canonical(...)."""
    eh = state_hash(c)
    seq = len(ledger_records(c)) + 1
    return {"seq": seq, "estado_hash": eh, "tag": frase.tag(k, c.work, nome, decisao, seq, eh)}


def _approval_identity(rec):
    """(nome, decisao) assinados por um evento de aprovação do ledger, ou None se não é aprovação."""
    ev = rec.get("event")
    if ev == "gate" and not rec.get("simulated"):
        return rec.get("name"), rec.get("decision")
    if ev == "preauth":
        req = rec.get("requires")
        return rec.get("name"), "preauth:" + ",".join(str(x) for x in req) if isinstance(req, list) else None
    if ev == "frase-conferida":
        return "frase-conferida", "ok"
    return None


def _audit_records(path, work):
    out = []
    if not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict) or rec.get("simulated"):
                continue
            w = rec.get("work")
            if isinstance(w, str) and os.path.realpath(w) == work and \
                    rec.get("cmd") in ("gate", "preauth", "frase-conferida", "legado-assinado"):
                out.append(rec)
    return out


LEGADO_CMDS = ("gate", "preauth")


def conferir_problemas(c, st, k, audit, criada_em=None):
    """Recalcula a tag de toda aprovação da campanha. Devolve (problemas, legadas_pendentes).

    Legada (rollout v0.3 → v0.4): gate não simulado ou preauth SEM tag, com `ts` < `criada_em` do frase.json E numa
    linha anterior ao 1º evento com tag do ledger. Assinada por um `legado-assinado` válido, vale como aprovação;
    pendente, só pode ser assinada (`frase conferir --assinar-legado`). Qualquer outra aprovação sem tag é forja."""
    probs = []
    recs = ledger_records(c)
    first_tagged = min([pos for pos, rec in recs if rec.get("tag")] or [len(recs) + 1])
    by_pos = dict(recs)

    def is_legacy(pos, rec):
        ts = rec.get("ts")
        return (not rec.get("tag") and isinstance(criada_em, str) and isinstance(ts, str) and ts < criada_em
                and pos < first_tagged and rec.get("event") in LEGADO_CMDS)

    # legado-assinado: tag do evento + tag de cada item, conferidos contra a linha do ledger
    signed = set()
    events = []  # (pos, rec, label) — eventos tagueáveis que precisam de linha na auditoria
    for pos, rec in recs:
        if rec.get("event") != "legado-assinado":
            continue
        events.append((pos, rec, "legado-assinado"))
        itens = rec.get("itens") if isinstance(rec.get("itens"), list) else []
        linhas = [it.get("linha") if isinstance(it, dict) else None for it in itens]
        t, seq, eh = rec.get("tag"), rec.get("seq"), rec.get("estado_hash")
        decisao = "legado:" + ",".join(str(x) for x in linhas)
        if not (isinstance(t, str) and isinstance(eh, str) and seq == pos and hmac.compare_digest(
                frase.tag(k, c.work, "legado-assinado", decisao, seq, eh), t)):
            probs.append("legado-assinado: evento na linha %d sem tag válida (seq, tag ou itens não conferem)" % pos)
            continue
        ok = []
        for it in itens:
            linha = it.get("linha") if isinstance(it, dict) else None
            alvo = by_pos.get(linha) if isinstance(linha, int) else None
            ident = _approval_identity(alvo) if alvo is not None else None
            if (alvo is None or ident is None or not is_legacy(linha, alvo) or linha >= pos
                    or (it.get("nome"), it.get("decisao"), it.get("ts")) != (ident[0], ident[1], alvo.get("ts"))
                    or not isinstance(it.get("tag"), str) or not hmac.compare_digest(
                        frase.tag(k, c.work, ident[0], ident[1], linha, "legado:" + alvo.get("ts")), it["tag"])):
                probs.append("legado-assinado: item da linha %r não confere com o ledger ou com a frase" % (linha,))
                ok = None
                break
            ok.append(linha)
        if ok:
            signed.update(ok)

    valid = []  # (pos, event, nome, rec, legado?)
    pending = []
    legacy_audit = set()
    for pos, rec in recs:
        ident = _approval_identity(rec)
        if ident is None:
            continue
        nome, decisao = ident
        label = nome if isinstance(nome, str) else "?"
        if not isinstance(nome, str) or not isinstance(decisao, str):
            events.append((pos, rec, label))
            probs.append("%s: evento %s na linha %d sem nome/decisão" % (label, rec.get("event"), pos))
            continue
        if is_legacy(pos, rec):
            legacy_audit.add((rec.get("event"), nome, rec.get("ts")))
            if pos in signed:
                valid.append((pos, rec.get("event"), nome, rec, True))
            else:
                pending.append((pos, nome, decisao, rec.get("ts"),
                                "%s: aprovação legada v0.3 (%s, linha %d, %s) sem assinatura"
                                % (nome, rec.get("event"), pos, rec.get("ts"))))
            continue
        events.append((pos, rec, label))
        t, seq, eh = rec.get("tag"), rec.get("seq"), rec.get("estado_hash")
        if not t:
            probs.append("%s: evento %s na linha %d sem tag (não é legado: ts ≥ criada_em ou depois do 1º "
                         "evento tagueado)" % (label, rec.get("event"), pos))
            continue
        if seq != pos:
            probs.append("%s: evento %s com seq %r ≠ posição %d no ledger" % (label, rec.get("event"), seq, pos))
            continue
        if not isinstance(eh, str) or not isinstance(t, str) or \
                not hmac.compare_digest(frase.tag(k, c.work, nome, decisao, seq, eh), t):
            probs.append("%s: evento %s na linha %d com tag que não confere com a frase" % (label, rec.get("event"), pos))
            continue
        valid.append((pos, rec.get("event"), nome, rec, False))
    aud = _audit_records(audit, c.work)
    aud = [x for x in aud if x.get("tag") or (x.get("cmd"), x.get("name"), x.get("ts")) not in legacy_audit]
    aud_keys = {(x.get("seq"), x.get("tag")) for x in aud}
    led_keys = {(rec.get("seq"), rec.get("tag")) for _, rec, _ in events}
    for pos, rec, label in events:
        if (rec.get("seq"), rec.get("tag")) not in aud_keys:
            probs.append("%s: evento %s na linha %d sem linha correspondente na auditoria %s"
                         % (label, rec.get("event"), pos, audit))
    for x in aud:
        if (x.get("seq"), x.get("tag")) not in led_keys:
            probs.append("%s: linha da auditoria (%s, seq %r) ausente do ledger" % (x.get("name"), x.get("cmd"), x.get("seq")))
    last_round = max([pos for pos, rec in recs if rec.get("event") == "round-new"] or [0])
    pending_names = {p[1] for p in pending}
    for kind, event in (("gates", "gate"), ("preauth", "preauth")):
        for name, entry in sorted((st.get(kind) or {}).items()):
            if not isinstance(entry, dict):
                probs.append("%s: entrada de state.%s inválida" % (name, kind))
                continue
            if kind == "gates" and entry.get("simulated"):
                continue
            mine = [v for v in valid if v[1] == event and v[2] == name]
            if not mine:
                if name not in pending_names:
                    probs.append("%s: state.%s sem aprovação válida no ledger" % (name, kind))
                continue
            pos, _, _, rec, leg = mine[-1]
            if leg:
                same = entry.get("seq") is None and entry.get("tag") is None and entry.get("at") == rec.get("ts")
            else:
                same = (entry.get("seq"), entry.get("tag")) == (rec.get("seq"), rec.get("tag"))
            if not same:
                probs.append("%s: state.%s não é a aprovação válida mais recente do ledger (linha %d)" % (name, kind, pos))
            elif kind == "gates" and entry.get("decision") != rec.get("decision"):
                probs.append("%s: decisão no state ≠ decisão assinada" % name)
            elif kind == "gates" and name not in PER_CAMPAIGN_GATES and pos < last_round:
                probs.append("%s: aprovação da rodada anterior (linha %d, antes do round-new na linha %d)"
                             % (name, pos, last_round))
    return probs, pending


def cmd_frase(c, a):
    if a.action == "definir":
        if a.assinar_legado:
            raise Bad("--assinar-legado só vale para `frase conferir`")
        return frase_definir(c, a)
    return frase_conferir(c, a)


def frase_definir(c, a):
    """Define (ou troca) a frase do founder. Sem campanha. Sem arquivo: nova + confirmação. Com arquivo: antiga,
    nova, confirmação. Grava só salts + verificador PBKDF2 em $AC_FRASE_FILE (0600)."""
    path = frase.caminho()
    try:
        frase.exigir_tty()
        fj_old = None
        if os.path.exists(path):
            fj_old = frase.carregar(path)
            old = frase.ler("FRASE antiga (sem eco): ", contexto="Trocar a frase exige a frase atual.")
            if not frase.confere(fj_old, old):
                raise Fail("senha ou frase antiga não confere — %s intacto" % path)
        nova = frase.ler("FRASE nova (sem eco): ",
                         contexto="Defina a senha ou frase do founder (só você a conhece): ≥12 caracteres, "
                                  "≥6 distintos e ≥3 palavras ou ≥3 tipos entre minúscula, maiúscula, dígito e símbolo.")
        probs = frase.problemas_forca(nova)
        if probs:
            raise Fail("senha ou frase fraca (%s) — nada gravado" % ", ".join(probs))
        conf = frase.ler("FRASE nova de novo (sem eco): ")
        if frase.normalizar(conf) != frase.normalizar(nova):
            raise Fail("confirmação diferente — nada gravado")
    except frase.SemTTY as e:
        raise Bad(str(e))
    except frase.ArquivoInvalido as e:
        raise Bad("%s — um frase.json inválido só se troca apagando-o à mão, no terminal do founder" % e)
    frase.gravar(frase.novo_registro(nova), path)
    print("senha ou frase %s em %s (0600: só salts e verificador PBKDF2; o segredo não é gravado)"
          % ("trocada" if fj_old else "definida", path))


def frase_conferir(c, a):
    """Founder confere TODAS as aprovações da campanha com a frase; tudo ok → evento tagueado frase-conferida.
    `--assinar-legado`: assina de uma vez as aprovações v0.3 legadas (evento humano legado-assinado), desde que não
    haja nenhum outro problema; não grava frase-conferida (rode `frase conferir` depois)."""
    st = c.load()
    audit = audit_log_path(c)
    tty, k = human_phrase(c, "%s da campanha %s" % ("assinar as aprovações legadas v0.3" if a.assinar_legado
                                                     else "conferir as aprovações", c.work))
    try:
        criada_em = frase.carregar().get("criada_em")
    except frase.ArquivoInvalido as e:
        raise Bad(str(e))
    probs, pending = conferir_problemas(c, st, k, audit, criada_em)
    if probs:
        raise Fail("%d problema(s) nas aprovações — nada gravado%s:\n  " % (
            len(probs), ", nada assinado" if a.assinar_legado else "") + "\n  ".join(probs + [p[4] for p in pending]))
    if not a.assinar_legado:
        if pending:
            raise Fail("%d aprovação(ões) legada(s) v0.3 sem tag — nada gravado. Confira a lista e, se todas são "
                       "suas, rode no seu terminal `ac.py --work %s frase conferir --assinar-legado`:\n  "
                       % (len(pending), c.work) + "\n  ".join(p[4] for p in pending))
        seal = approval_seal(c, k, "frase-conferida", "ok")
        audit_append(audit, c, tty, cmd="frase-conferida", name="frase-conferida", decision="ok", by=_os_user(), **seal)
        c.log("frase-conferida", name="frase-conferida", decision="ok", **seal)
        print("aprovações conferidas: todas as tags batem com a frase (frase-conferida na linha %d)" % seal["seq"])
        return
    if not pending:
        raise Fail("nenhuma aprovação legada pendente — nada a assinar; rode `frase conferir` sem a flag")
    itens = [{"linha": pos, "nome": nome, "decisao": dec, "ts": ts,
              "tag": frase.tag(k, c.work, nome, dec, pos, "legado:" + ts)} for pos, nome, dec, ts, _ in pending]
    decisao = "legado:" + ",".join(str(it["linha"]) for it in itens)
    seal = approval_seal(c, k, "legado-assinado", decisao)
    audit_append(audit, c, tty, cmd="legado-assinado", name="legado-assinado", decision=decisao, by=_os_user(),
                 itens=itens, **seal)
    c.log("legado-assinado", name="legado-assinado", decision=decisao, itens=itens, **seal)
    print("%d aprovação(ões) legada(s) assinada(s): %s (legado-assinado na linha %d). Agora rode "
          "`frase conferir`." % (len(itens), ", ".join("%s@%d" % (it["nome"], it["linha"]) for it in itens), seal["seq"]))


def chk_frase_conferida(c, st, args):
    """`done decisao`: exige um frase-conferida posterior a toda aprovação não simulada. Só a ORDEM; a
    autenticidade vem do `frase conferir` do founder (que reconfere os frase-conferida anteriores)."""
    recs = ledger_records(c)
    apr = [pos for pos, rec in recs if (rec.get("event") == "gate" and not rec.get("simulated"))
           or rec.get("event") == "preauth"]
    conf = [pos for pos, rec in recs if rec.get("event") == "frase-conferida"]
    if not conf or (apr and max(conf) < max(apr)):
        raise Fail("falta o founder rodar `ac.py --work %s frase conferir` no terminal dele depois da última "
                   "aprovação (linha %s do ledger)" % (c.work, max(apr) if apr else "—"))


def chk_calibration(c, st, args):
    """Calibração prova que o oráculo não mente: vazio≈0, bom passa, conferências à mão suficientes e corretas."""
    cal = get(st, "oracle.calibration")
    if isinstance(cal, dict) and cal.get("modo") == "requisito":
        return chk_calibration_requisito(st, cal)
    if not isinstance(cal, dict):
        raise Fail("oracle.calibration ausente: ac.py set oracle.calibration '{\"vazio\":0.0,\"bom\":1.0,"
                   "\"conferencias\":[{\"assercao\":\"...\",\"correto\":true,\"evidencia\":\"arq:linha\"}],\"configs\":2}'")
    errs = []
    if not isinstance(cal.get("vazio"), (int, float)) or cal["vazio"] > 0.1:
        errs.append("saída vazia precisa pontuar ≤0.10 (recebido %r)" % cal.get("vazio"))
    if not isinstance(cal.get("bom"), (int, float)) or cal["bom"] < 0.9:
        errs.append("saída boa conhecida precisa pontuar ≥0.90 (recebido %r)" % cal.get("bom"))
    conf = cal.get("conferencias") or []
    need = 2 * int(cal.get("configs") or 1)
    if len(conf) < need:
        errs.append("conferências à mão: %d, mínimo %d (2 por configuração)" % (len(conf), need))
    wrong = [x.get("assercao") for x in conf if not x.get("correto")]
    if wrong:
        errs.append("oráculo errou em %s — corrija via `oracle change` e recalibre" % wrong)
    sem = [x.get("assercao") for x in conf if not x.get("evidencia")]
    if sem:
        errs.append("conferências sem evidência: %s" % sem)
    if errs:
        raise Fail("; ".join(errs))


def chk_calibration_requisito(st, cal):
    """Requisito NOVO (lição L15): não há saída boa conhecida. Exige: vazio medido ≈0 (oráculo falhando antes da
    correção), cada arquivo de oráculo ligado à seção da especificação de onde veio, e portão HUMANO
    `oracle:requisito` aprovando que os oráculos representam o pedido."""
    errs = []
    if not isinstance(cal.get("vazio"), (int, float)) or cal["vazio"] > 0.1:
        errs.append("modo requisito: vazio medido precisa ser ≤0.10 (oráculo falhando antes) — recebido %r" % cal.get("vazio"))
    files = set((st.get("oracle") or {}).get("files") or [])
    spec = cal.get("spec") or {}
    faltam = sorted(os.path.basename(f) for f in files if os.path.basename(f) not in spec)
    if not files:
        errs.append("oráculo não congelado")
    if faltam:
        errs.append("arquivos do oráculo sem seção de especificação em calibration.spec: %s" % faltam)
    g = (st.get("gates") or {}).get("oracle:requisito")
    if not g or g.get("decision") != "approve" or g.get("simulated"):
        errs.append("portão humano `oracle:requisito` não aprovado (ac.py gate oracle:requisito --by <humano> --decision approve)")
    if errs:
        raise Fail("; ".join(errs))


CHECKS = {"calibration": chk_calibration, "require": chk_require, "oracle": chk_oracle_verify, "runs": chk_runs, "defects": chk_defects,
          "plan": None, "fronts": chk_fronts, "gate-ok": chk_gate_ok}


def run_check(c, st, expr):
    toks = expr.split()
    head, rest = toks[0], toks[1:]
    if head == "plan":
        return (chk_plan_gates if rest[:1] == ["gates"] else chk_plan)(c, st, rest[1:])
    if head == "oracle":
        return chk_oracle_verify(c, st, rest[1:])
    fn = CHECKS.get(head)
    if not fn:
        raise Bad("check desconhecido: %s" % expr)
    return fn(c, st, rest)


def chk_post_correction(c, st, args):
    """AC-01: a remedição só vale com execução registrada DEPOIS de correcao.1 concluída e com `decision`."""
    t = st["done"].get("correcao.1")
    if not t:
        raise Fail("correcao.1 não concluída — a remedição mede a correção, não a base")
    runs = c.runs(st)
    after = [x for x in runs if (x.get("at") or "") > t]
    if not after:
        raise Fail("nenhuma execução registrada depois de correcao.1 (%s) — a da base não mede a correção; "
                   "ac.py run record ... --decision <...>" % t)
    if not [x for x in after if (x.get("decision") or "").strip()]:
        raise Fail("execução posterior a correcao.1 sem `decision` (ac.py run record ... --decision <...>)")


SUB_EXTRA = {"remedicao.1": chk_post_correction}  # travas do ac.py que valem mesmo se ciclo.json5 não as citar


def run_sub_checks(c, st, sub):
    if sub.get("check"):
        run_check(c, st, sub["check"])
    extra = SUB_EXTRA.get(sub["id"])
    if extra:
        extra(c, st, [])


def next_stage(st, cy, after):
    """AC-02: primeira etapa de ciclo.order depois de `after` ainda não totalmente concluída; senão 'concluida'."""
    order = cy["order"]
    for name in order[order.index(after) + 1:]:
        if not all(st["done"].get(s["id"]) for s in cy["stages"][name]["substages"]):
            return name
    return "concluida"


def substage(cy, sid):
    for name, s in cy["stages"].items():
        for sub in s["substages"]:
            if sub["id"] == sid:
                return name, sub
    raise Bad("sub-etapa desconhecida: %s" % sid)


# ------------------------------------------------------------------ comandos

def cmd_init(c, a):
    st = c.load() if c.exists() else {"round": 0, "stage": "intake", "done": {}, "gates": {}, "created": now()}
    if a.target:
        st["target"] = os.path.realpath(a.target)
    if a.scope:
        comma = [g for g in a.scope if "," in g]
        if comma:  # AC-06: '--scope "a/**, b/**"' viraria UM glob que não casa nada
            raise Bad("--scope com vírgula (%s): passe um glob por --scope, repetindo a flag "
                      "(--scope 'a/**' --scope 'b/**'); nada gravado" % ", ".join(repr(g) for g in comma))
        st["scope"] = a.scope
    if a.problem:
        st["problem"] = a.problem
    if a.stop:
        st["stop"] = a.stop
    b = st.setdefault("budget", {})
    for k in ("max_rounds", "max_hours", "max_parallel"):
        v = getattr(a, k)
        if v is not None:
            b[k] = v
    if not b:
        st.pop("budget")
    c.save(st, "init", target=st.get("target"))
    print("campanha em %s (rodada %d, etapa %s)" % (c.dir, st["round"], st["stage"]))


PROTECTED = {"gates", "done", "round", "stage", "waivers", "created", "target", "preauth"}


def cmd_set(c, a):
    st = c.load()
    try:
        val = json.loads(a.value)
    except ValueError:
        val = a.value
    root = a.key.split(".")[0]
    if root in PROTECTED or a.key in ("oracle", "oracle.files", "oracle.hash", "oracle.changes", "oracle.frozen_at"):
        raise Bad("'%s' é estado protegido: use o comando próprio (gate, oracle, check/done, round, run)" % a.key)
    put(st, a.key, val)
    c.save(st, "set", key=a.key)
    print("ok: %s" % a.key)


def cmd_status(c, a):
    st = c.load()
    cy = ciclo()
    print("alvo: %s\nrodada: %d · etapa: %s\nparada: %s" % (st.get("target"), st["round"], st["stage"], st.get("stop", "—")))
    for g, v in sorted((st.get("gates") or {}).items()):
        print(" portão %-14s %s por %s%s" % (g, v.get("decision"), v.get("by"), " (SIMULADO)" if v.get("simulated") else ""))
    for name in cy["order"]:
        subs = cy["stages"][name]["substages"]
        ok = [s["id"] for s in subs if st["done"].get(s["id"])]
        mark = "✓" if len(ok) == len(subs) else ("…" if ok else " ")
        print(" %s %-12s %d/%d" % (mark, name, len(ok), len(subs)))


def cmd_load(c, a):
    st = c.load()
    cy = ciclo()
    if a.stage not in cy["stages"]:
        raise Bad("etapa desconhecida: %s" % a.stage)
    idx = cy["order"].index(a.stage)
    for prev in cy["order"][:idx]:
        if not all(st["done"].get(s["id"]) for s in cy["stages"][prev]["substages"]):
            raise Fail("etapa '%s' não fechou — conclua-a antes (ac.py load %s)" % (prev, prev))
    s = cy["stages"][a.stage]
    lines = ["# etapa %s · rodada %d" % (a.stage, st["round"]), "objetivo: " + s["goal"],
             "parada: %s" % st.get("stop", "—"), "orçamento: %s" % st.get("budget", "—")]
    for sub in s["substages"]:
        lines.append("[%s] %s (%s) %s" % ("x" if st["done"].get(sub["id"]) else " ", sub["id"], sub["ctx"], sub["do"]))
    prev = os.path.join(c.dir, "handoff-r%d-%s.txt" % (st["round"], cy["order"][idx - 1])) if idx else None
    if prev and not os.path.isfile(prev) and st["round"] > 0:
        prev = os.path.join(c.dir, "handoff-r%d-%s.txt" % (st["round"] - 1, cy["order"][idx - 1]))
    if prev and os.path.isfile(prev):
        lines.append("handoff anterior:\n" + open(prev, encoding="utf-8").read())
    text = "\n".join(lines)
    print(text[:cy["limits"]["handoff_max_chars"]])
    st["stage"] = a.stage
    c.save(st, "load", stage=a.stage)


def require_previous_closed(st, cy, stage):
    idx = cy["order"].index(stage)
    for prev in cy["order"][:idx]:
        if not all(st["done"].get(s["id"]) for s in cy["stages"][prev]["substages"]):
            raise Fail("etapa '%s' não fechou — conclua-a antes de '%s'" % (prev, stage))


def cmd_check(c, a):
    st = c.load()
    cy = ciclo()
    stage, sub = substage(cy, a.substage)
    require_previous_closed(st, cy, stage)
    run_sub_checks(c, st, sub)
    st["done"][a.substage] = now()
    c.save(st, "check", substage=a.substage)
    print("ok: %s" % a.substage)


def cmd_done(c, a):
    st = c.load()
    cy = ciclo()
    s = cy["stages"].get(a.stage)
    if not s:
        raise Bad("etapa desconhecida: %s" % a.stage)
    require_previous_closed(st, cy, a.stage)
    errs = []
    for sub in s["substages"]:
        try:
            run_sub_checks(c, st, sub)
            st["done"][sub["id"]] = st["done"].get(sub["id"]) or now()
        except Fail as e:
            errs.append("%s: %s" % (sub["id"], e))
    if a.stage == "decisao":
        try:
            chk_frase_conferida(c, st, [])
        except Fail as e:
            errs.append("decisao: %s" % e)
    if errs:
        c.save(st, "done-fail", stage=a.stage)
        raise Fail("etapa '%s' não fecha:\n  " % a.stage + "\n  ".join(errs))
    if a.handoff:
        with open(os.path.join(c.dir, "handoff-r%d-%s.txt" % (st["round"], a.stage)), "w", encoding="utf-8") as fh:
            fh.write(a.handoff)
    st["stage"] = next_stage(st, cy, a.stage)
    c.save(st, "done", stage=a.stage, next=st["stage"])
    print("etapa '%s' fechada" % a.stage)


def cmd_gate(c, a):
    st = c.load()
    if a.decision not in ("approve", "reject"):
        raise Bad("--decision approve|reject")
    if a.simulated:
        old = (st.get("gates") or {}).get(a.name)
        if isinstance(old, dict) and not old.get("simulated"):
            raise Bad("portão '%s' já tem decisão humana — simulado não a substitui" % a.name)
    else:
        audit = audit_log_path(c)
        tty, k = human_phrase(c, "decidir '%s' no portão '%s' (por %s)" % (a.decision, a.name, a.by))
        seal = approval_seal(c, k, a.name, a.decision)
        audit_append(audit, c, tty, cmd="gate", name=a.name, decision=a.decision, by=a.by, **seal)
    seal = {} if a.simulated else seal
    st.setdefault("gates", {})[a.name] = {"by": a.by, "decision": a.decision, "note": a.note or "", "at": now(),
                                         "simulated": bool(a.simulated)}
    if seal:
        st["gates"][a.name].update(seq=seal["seq"], tag=seal["tag"])
    c.save(st, "gate", name=a.name, decision=a.decision, by=a.by, simulated=bool(a.simulated), **seal)
    print("portão %s: %s por %s%s" % (a.name, a.decision, a.by, " (simulado)" if a.simulated else ""))


def cmd_oracle(c, a):
    st = c.load()
    o = st.setdefault("oracle", {})
    if a.action == "freeze":
        if o.get("hash"):
            raise Bad("oráculo já congelado — mudança só por `oracle change --why --evidence`")
        files = [os.path.realpath(f) for f in a.file or []]
        if not files or not all(os.path.isfile(f) for f in files):
            raise Bad("--file <arquivo do oráculo> (repita) — todos precisam existir")
        o["files"], o["hash"], o["frozen_at"] = files, sha_files(files), now()
        c.save(st, "oracle-freeze", hash=o["hash"])
        print("oráculo congelado: %s" % o["hash"][:12])
    elif a.action == "verify":
        chk_oracle_verify(c, st, [])
        print("oráculo intacto")
    elif a.action == "change":
        if not o.get("hash"):
            raise Bad("oráculo nunca foi congelado — use `oracle freeze` primeiro")
        if not a.why or not a.evidence:
            raise Bad("mudar o oráculo exige --why e --evidence (conferência manual que prova o erro do oráculo)")
        files = [os.path.realpath(f) for f in (a.file or o.get("files") or [])]
        old = o.get("hash")
        o["files"], o["hash"] = files, sha_files(files)
        o.setdefault("changes", []).append({"at": now(), "why": a.why, "evidence": a.evidence, "from": old, "to": o["hash"],
                                            "round": st["round"]})
        c.save(st, "oracle-change", why=a.why, evidence=a.evidence, frm=old, to=o["hash"])
        print("oráculo recongelado: %s (mudança registrada; toda medição anterior deve ser recorrigida)" % o["hash"][:12])


def cmd_run(c, a):
    st = c.load()
    if a.action == "waive":
        if not (a.why or "").strip():
            raise Bad("dispensa exige --why (por que não há baseline/execução)")
        put(st, "waivers.%d.%s" % (a.round if a.round is not None else st["round"], a.config), a.why or "")
        c.save(st, "run-waive", config=a.config, why=a.why)
        print("dispensa registrada")
        return
    rec = {"round": a.round if a.round is not None else st["round"], "config": a.config, "alvo": a.alvo,
           "dir": a.dir, "tokens": a.tokens, "minutes": a.minutes, "decision": a.decision,
           "simulated": bool(a.simulated), "at": now()}
    if a.grading:
        g = json.load(open(a.grading, encoding="utf-8"))
        s = g.get("summary") or {}
        rec["quality"] = s.get("quality") or {}
        rec["structure"] = s.get("structure") or {}
        rec["grading"] = os.path.realpath(a.grading)
        check_quality_total(c, st, rec)
    p = os.path.join(c.round_dir(st, rec["round"]), "runs.jsonl")
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    c.log("run-record", **{k: rec[k] for k in ("round", "config", "alvo")})
    print("execução registrada: rodada %d %s/%s" % (rec["round"], rec["alvo"], rec["config"]))


def check_quality_total(c, st, rec):
    """AC-03 (L02): o total de qualidade é o da base da rodada (1ª execução com nota). Só um `oracle change`
    POSTERIOR à base muda o denominador — e aí a 1ª execução com nota depois da última mudança vira a nova base."""
    total = (rec.get("quality") or {}).get("total")
    if total is None:
        return
    graded = [x for x in c.runs(st, rec["round"]) if (x.get("quality") or {}).get("total") is not None]
    if not graded:
        return
    changes = [ch.get("at") or "" for ch in (st.get("oracle") or {}).get("changes") or []]
    base = graded[0]
    last = max([t for t in changes if t > (base.get("at") or "")] or [""])
    if last:
        after = [x for x in graded if (x.get("at") or "") > last]
        if not after:
            return  # oráculo mudou depois da base e ainda não há medição nova: esta fixa o novo total
        base = after[0]
    if total != base["quality"]["total"]:
        raise Fail("L02: total de qualidade %s ≠ total da base da rodada %d (%s, em %s) — qualidade misturada com "
                   "estrutura ou oráculo mudado fora de `oracle change`; nada gravado"
                   % (total, rec["round"], base["quality"]["total"], base.get("at")))


def cmd_overlap(c, a):
    """L17: campanhas simultâneas precisam de escopos disjuntos — e uma não pode escrever no oráculo da outra."""
    st = c.load()
    mine = scope_abs(c, st)
    errs = []
    for other in a.other or []:
        oc = Campaign(other)
        ost = oc.load()
        theirs = scope_abs(oc, ost)
        for ga, pa in mine:
            for gb, pb in theirs:
                if globs_overlap(pa, pb):
                    errs.append("escopo %s (%s) colide com escopo %s (%s) da campanha %s" % (ga, pa, gb, pb, oc.work))
        for cx, sx, cy_, sy in ((c, mine, oc, ost), (oc, theirs, c, st)):
            for of in (sy.get("oracle") or {}).get("files") or []:
                for g, pg in sx:
                    if fnmatch.fnmatch(of, pg) or globs_overlap(pg, of):
                        errs.append("escopo %s (%s) da campanha %s cobre o oráculo %s da campanha %s"
                                    % (g, pg, cx.work, of, cy_.work))
    if errs:
        raise Fail("campanhas sobrepostas (L17):\n  " + "\n  ".join(errs))
    print("campanhas disjuntas: %s × %s" % (c.work, ", ".join(os.path.realpath(o) for o in a.other or [])))


def scope_abs(c, st):
    base = st.get("target") or c.work
    sc = st.get("scope") or []
    if isinstance(sc, str):
        sc = [sc]
    return [(g, g if os.path.isabs(g) else os.path.join(base, g)) for g in sc if isinstance(g, str) and g]


def cmd_front(c, a):
    st = c.load()
    d = os.path.join(c.round_dir(st), "fronts")
    os.makedirs(d, exist_ok=True)
    text = open(a.file, encoding="utf-8").read()
    with open(os.path.join(d, a.name + ".md"), "w", encoding="utf-8") as fh:
        fh.write(text)
    c.log("front-report", name=a.name)
    print("relatório da frente %s registrado" % a.name)


def cmd_round(c, a):
    st = c.load()
    cy = ciclo()
    must = cy["per_round"] if st["round"] > 0 else [n for n in cy["order"] if n not in cy["per_round"]]
    for name in must:  # rodada 0: intake/oraculo/base fechadas; rodada N: o ciclo inteiro da rodada
        for sub in cy["stages"][name]["substages"]:
            if not st["done"].get(sub["id"]):
                raise Fail("rodada %d não terminou (%s pendente)" % (st["round"], sub["id"]))
    b = st.get("budget") or {}
    if b.get("max_rounds") and st["round"] + 1 > b["max_rounds"]:
        raise Fail("orçamento: máximo de %d rodadas atingido — escale ao usuário" % b["max_rounds"])
    st["round"] += 1
    for name in cy["per_round"]:
        for sub in cy["stages"][name]["substages"]:
            st["done"].pop(sub["id"], None)
    for k in ("decision", "report"):
        st.pop(k, None)
    st["gates"] = {k: v for k, v in (st.get("gates") or {}).items() if k == "stop"}  # commit/plan valem por rodada
    st.get("integration", {}).pop("tests_green", None)
    st["stage"] = "diagnostico"
    c.save(st, "round-new", round=st["round"])
    print("rodada %d aberta — comece por `ac.py load diagnostico`" % st["round"])


def _rate(x):
    return (x["passed"] / x["total"]) if x and x.get("total") else None


def cmd_results(c, a):
    st = c.load()
    rows = []
    for r in range(0, st["round"] + 1):
        for x in c.runs(st, r):
            rows.append((r, x))
    if not rows:
        raise Fail("nenhuma execução registrada")
    print("| rodada | alvo | config | qualidade | estrutura | decisão | tokens | min |")
    print("|---|---|---|---|---|---|---|---|")
    for r, x in rows:
        q, s = x.get("quality") or {}, x.get("structure") or {}
        dec = (x.get("decision") or "—") + (" (simulado)" if x.get("simulated") else "")
        print("| %d | %s | %s | %s | %s | %s | %s | %s |" % (
            r, x.get("alvo"), x.get("config"), "%s/%s" % (q.get("passed"), q.get("total")) if q else "—",
            "%s/%s" % (s.get("passed"), s.get("total")) if s else "—", dec, x.get("tokens") or "—", x.get("minutes") or "—"))
    cur = [x for r, x in rows if r == st["round"] and x.get("config") != "baseline"]
    prev = [x for r, x in rows if r == st["round"] - 1 and x.get("config") != "baseline"]

    def mean(xs, k):
        v = [_rate(x.get(k)) for x in xs if _rate(x.get(k)) is not None]
        return sum(v) / len(v) if v else None
    for k in ("quality", "structure"):
        m1, m0 = mean(cur, k), mean(prev, k)
        if m1 is not None:
            print("%s: rodada %d = %.2f%s" % (k, st["round"], m1, (" (anterior %.2f, Δ %+.2f)" % (m0, m1 - m0)) if m0 is not None else ""))
    print("parada: %s" % st.get("stop", "—"))


def build_parser():
    p = argparse.ArgumentParser(prog="ac.py", description="estado mecânico da auto-correcao")
    p.add_argument("--work", help="diretório da campanha (fora do alvo medido); obrigatório, exceto em "
                                   "`frase definir`")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("init")
    s.add_argument("--target")
    s.add_argument("--scope", action="append")
    s.add_argument("--problem")
    s.add_argument("--stop")
    s.add_argument("--max-rounds", dest="max_rounds", type=int)
    s.add_argument("--max-hours", dest="max_hours", type=float)
    s.add_argument("--max-parallel", dest="max_parallel", type=int)
    s = sub.add_parser("set")
    s.add_argument("key")
    s.add_argument("value")
    sub.add_parser("status")
    s = sub.add_parser("load")
    s.add_argument("stage")
    s = sub.add_parser("check")
    s.add_argument("substage")
    s = sub.add_parser("done")
    s.add_argument("stage")
    s.add_argument("--handoff")
    s = sub.add_parser("gate")
    s.add_argument("name")
    s.add_argument("--by", required=True)
    s.add_argument("--decision", required=True)
    s.add_argument("--note")
    s.add_argument("--simulated", action="store_true")
    s = sub.add_parser("preauth", help="pré-autoriza um portão (humano), condicionado a sub-etapas concluídas")
    s.add_argument("name")
    s.add_argument("--by", required=True)
    s.add_argument("--requires", nargs="+", required=True, help="sub-etapas que precisam estar concluídas")
    s.add_argument("--note")
    s.add_argument("--simulated", action="store_true")
    s = sub.add_parser("oracle")
    s.add_argument("action", choices=["freeze", "verify", "change"])
    s.add_argument("--file", action="append")
    s.add_argument("--why")
    s.add_argument("--evidence")
    s = sub.add_parser("run")
    s.add_argument("action", choices=["record", "waive"])
    s.add_argument("--round", type=int)
    s.add_argument("--config", required=True)
    s.add_argument("--alvo", default="default")
    s.add_argument("--dir")
    s.add_argument("--grading", help="grading.json com summary.quality/structure {passed,total}")
    s.add_argument("--tokens", type=int)
    s.add_argument("--minutes", type=float)
    s.add_argument("--decision")
    s.add_argument("--simulated", action="store_true")
    s.add_argument("--why")
    s = sub.add_parser("front")
    s.add_argument("action", choices=["report"])
    s.add_argument("name")
    s.add_argument("--file", required=True)
    s = sub.add_parser("round")
    s.add_argument("action", choices=["new"])
    s = sub.add_parser("results")
    s.add_argument("action", choices=["compare"])
    s = sub.add_parser("plan")
    s.add_argument("action", choices=["check", "gates"])
    s = sub.add_parser("defects")
    s.add_argument("action", choices=["check"])
    s = sub.add_parser("frase", help="frase-senha do founder: definir (1x) e conferir as aprovações (só no terminal)")
    s.add_argument("action", choices=["definir", "conferir"])
    s.add_argument("--assinar-legado", dest="assinar_legado", action="store_true",
                   help="conferir: assina as aprovações v0.3 sem tag anteriores à frase (rollout)")
    s = sub.add_parser("overlap", help="L17: confere que esta campanha é disjunta de outras (escopo e oráculo)")
    s.add_argument("--other", action="append", required=True, help="--work de outra campanha (repita)")
    return p


def main(argv=None):
    # console/pipe fora de UTF-8 (ex.: cp1252 no Windows): o que não codifica sai escapado, sem traceback
    for s in (sys.stdout, sys.stderr):
        enc = (getattr(s, "encoding", None) or "").lower().replace("-", "").replace("_", "")
        if enc and enc != "utf8" and hasattr(s, "reconfigure"):
            try:
                s.reconfigure(errors="backslashreplace")
            except (ValueError, OSError):
                pass
    a = build_parser().parse_args(argv)
    if not a.cmd:
        build_parser().print_help(sys.stderr)
        return 2
    if not a.work and not (a.cmd == "frase" and a.action == "definir"):
        sys.stderr.write("erro: --work <campanha> é obrigatório (só `frase definir` o dispensa)\n")
        return 2
    c = Campaign(a.work or os.getcwd())
    for attr in ("file", "grading"):
        v = getattr(a, attr, None)
        for f in (v if isinstance(v, list) else [v] if v else []):
            if not os.path.isfile(f):
                sys.stderr.write("erro: arquivo não encontrado: %s\n" % f)
                return 2
    try:
        if a.cmd == "preauth":
            cmd_preauth(c, a)
        elif a.cmd == "plan":
            st = c.load()
            (chk_plan if a.action == "check" else chk_plan_gates)(c, st, [])
            print("plano ok")
        elif a.cmd == "defects":
            st = c.load()
            chk_defects(c, st, ["--evidence", "--classified"])
            print("defeitos ok")
        elif a.cmd != "preauth":
            globals()["cmd_" + a.cmd](c, a)
        return 0
    except Fail as e:
        sys.stderr.write("NÃO: %s\n" % e)
        return 1
    except Bad as e:
        sys.stderr.write("erro: %s\n" % e)
        return 2
    except KeyboardInterrupt:
        sys.stderr.write("interrompido — nada gravado\n")
        return 130


if __name__ == "__main__":
    sys.exit(main())
