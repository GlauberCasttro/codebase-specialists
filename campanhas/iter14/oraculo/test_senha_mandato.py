"""ORÁCULO campanha-iter14 — a aprovação do mandato autônomo (cs-auto approve) passa a exigir a SENHA do humano.

Contrato: ESPEC.md (mesma pasta). Quem implementa NÃO edita este arquivo.
Padrão espelhado: skill auto-correcao (scripts/frase.py + tests/_pty_helper.py), SEM depender dela.

Tudo pelo comportamento OBSERVÁVEL, sem mock e sem bypass no produto:
  * `cs-auto` = <skill>/scripts/harness/engine/auto.py --root <alvo> (subprocesso);
  * o HUMANO é simulado num pseudo-terminal real (pty.fork): a cada prompt `SENHA...:` o teste digita a resposta;
  * "sem terminal" = stdin /dev/null (ou pipe) + `start_new_session=True` (sem tty controlador, /dev/tty não abre);
  * a senha de teste só vale porque o teste grava, num CS_SENHA_FILE temporário, um registro PBKDF2 gerado com ela
    (formato FIXADO na ESPEC §2.1). HOME também é temporário: o ~/.config real nunca é lido nem escrito.
  * o forjador é modelado como um agente com acesso de escrita ao estado: reescreve events.jsonl (re-encadeando
    prev/seq e o hash final da projeção) e a projeção do motor — o máximo que se faz sem saber a senha.

Reaproveita as fixtures do oráculo do M5 (campanha-m5/oraculo/test_mandato.py: alvo git temporário em árvore,
propose, status, tick). Skill: $CS_SKILL_DIR, senão ~/.claude/skills/codebase-specialists. Oráculo do M5:
$CS_M5_ORACULO, senão ../../campanha-m5/oraculo. Python 3.9+, unittest puro, POSIX (pty).
Rodar: python3 -m unittest -v test_senha_mandato   (de dentro desta pasta)
"""
import hashlib
import hmac
import json
import os
import pty
import re
import select
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unicodedata
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
M5_DIR = os.path.realpath(os.environ.get("CS_M5_ORACULO") or os.path.join(HERE, "..", "..", "campanha-m5", "oraculo"))
if M5_DIR not in sys.path:
    sys.path.insert(0, M5_DIR)
import test_mandato as m5  # noqa: E402  (fixtures do M5; as classes de teste dele NÃO são coletadas aqui)

SKILL = m5.SKILL
AUTO_PY = m5.AUTO_PY
GUARD_PY = m5.GUARD_PY
SD = m5.SD
HUMAN = m5.HUMAN
ORC = "despachos=17,tentativas=40,replanos=3,minutos=600,usd=50"   # 17: valor distinto para achar no selo

SENHA = "Mandato-Seguro-2026"          # 4 classes, 19 caracteres
SENHA_ERRADA = "Mandato-Errado-2027"
SENHA_AGENTE = "Agente-Forjador-0099"
ITER = 600000
PROMPT = re.compile(rb"SENHA[^\r\n:]*:")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
FRACAS = ("Curta-1a",               # < 12 caracteres
          "aaaaaaaaaaA1-",          # 13 caracteres, só 4 distintos
          "abcdefghijklmnop",       # 1 classe
          "abcdefgh12345678",       # 2 classes
          "ABCDEFGH-IJKLMN")        # 2 classes
SENHA_ENV_VARS = ("CS_SENHA", "CS_AUTO_SENHA", "CS_MANDATO_SENHA", "SENHA", "CS_PASSWORD", "CS_HUMAN_PROOF")


# ====================================================================== senha: registro e selo (ESPEC §2.1 e §2.3)
def normalizar(s):
    return unicodedata.normalize("NFC", s.strip())


def derivar(senha, salt_hex, it=ITER):
    return hashlib.pbkdf2_hmac("sha256", normalizar(senha).encode("utf-8"), bytes.fromhex(salt_hex), it, dklen=32)


_REG = {}


def registro(senha, it=ITER, kdf="pbkdf2-sha256"):
    """Registro de senha no formato FIXADO (ESPEC §2.1); derivado uma vez por processo e parâmetros."""
    k = (senha, it, kdf)
    if k not in _REG:
        sv, sk = os.urandom(16).hex(), os.urandom(16).hex()
        _REG[k] = {"versao": 1, "kdf": kdf, "iter": it, "salt_verificador": sv, "salt_chave": sk,
                   "verificador": derivar(senha, sv, it).hex(), "criada_em": "2026-10-05T00:00:00Z"}
    return dict(_REG[k])


def gravar_registro(path, senha, **kw):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(registro(senha, **kw), f)
    os.chmod(path, 0o600)
    return path


def canonical_selo(selo):
    body = dict((k, selo.get(k)) for k in ("mandato", "plano_sha256", "orcamento", "seq", "ts"))
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def tag_esperada(reg, senha, selo):
    return hmac.new(derivar(senha, reg["salt_chave"], reg["iter"]), canonical_selo(selo), hashlib.sha256).hexdigest()


def sha(b):
    return hashlib.sha256(b).hexdigest()


def walk_drop(obj, key):
    """Remove `key` de todo dict aninhado."""
    if isinstance(obj, dict):
        obj.pop(key, None)
        for v in obj.values():
            walk_drop(v, key)
    elif isinstance(obj, list):
        for v in obj:
            walk_drop(v, key)


# ====================================================================== terminal: pty real e "sem terminal"
def run_pty(argv, env, answers=(), timeout=240, stdin_data=None):
    """Roda argv num pseudo-terminal real. A cada prompt `SENHA...:` digita a próxima resposta (esgotou → linha
    vazia). stdin_data != None: o tty controlador continua sendo o pty, mas a STDIN vira um pipe com esses bytes.
    Retorna (exit, saída do terminal, nº de prompts vistos)."""
    pid, fd = pty.fork()
    if pid == 0:
        try:
            if stdin_data is not None:
                r, w = os.pipe()
                os.write(w, stdin_data)
                os.close(w)
                os.dup2(r, 0)
                os.close(r)
            os.execve(argv[0], argv, env)
        finally:
            os._exit(127)
    answers = list(answers)
    buf, seen, deadline = b"", 0, time.time() + timeout
    try:
        while True:
            if time.time() > deadline:
                os.kill(pid, signal.SIGKILL)
                raise AssertionError("processo no pty não terminou em %ss: %r" % (timeout, buf[-600:]))
            r, _, _ = select.select([fd], [], [], 0.1)
            if not r:
                continue
            try:
                data = os.read(fd, 4096)
            except OSError:
                break
            if not data:
                break
            buf += data
            n = len(PROMPT.findall(buf))
            while seen < n:
                os.write(fd, ((answers[seen] if seen < len(answers) else "") + "\n").encode("utf-8"))
                seen += 1
    finally:
        _, status = os.waitpid(pid, 0)
        os.close(fd)
    code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else 128 + os.WTERMSIG(status)
    return code, buf.decode("utf-8", "replace"), seen


def run_notty(argv, env, data=None):
    """Sem terminal: stdin /dev/null (ou pipe com `data`), nova sessão (sem tty controlador)."""
    p = subprocess.run(argv, env=env, input=data, stdin=None if data is not None else subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300, start_new_session=True)
    return p.returncode, p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")


# ====================================================================== base
class Base(m5.Base):
    def setUp(self):
        super(Base, self).setUp()
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="cs-senha-"))
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)
        self.senha_file = os.path.join(self.tmp, "cfg", "senha.json")

    def tearDown(self):
        super(Base, self).tearDown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- ambiente isolado: HOME e CS_SENHA_FILE temporários; nenhuma variável que "forneça" senha
    def _env(self, extra=None):
        e = super(Base, self)._env()
        for k in ("XDG_CONFIG_HOME", "CS_HUMAN_PROOF_ARGS", "AC_FRASE_FILE") + SENHA_ENV_VARS:
            e.pop(k, None)
        e["HOME"] = self.home
        e["CS_SENHA_FILE"] = self.senha_file
        e.update(extra or {})
        return e

    def _run(self, root, argv, inp=None, env=None, is_auto=False):
        """Como o do M5, mas SEMPRE sem terminal (stdin /dev/null, nova sessão): nada aqui pode ler o tty do runner."""
        before = [len(m5._read_lines(p)) for p in m5.events_files(root)]
        p = subprocess.run(argv, cwd=root, env=env or self._env(), input=inp,
                           stdin=None if inp is not None else subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=300, start_new_session=True)
        out, err = p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
        for path, n in zip(m5.events_files(root), before):
            for ev in m5._read_lines(path)[n:]:
                m5._account(ev)
        return p.returncode, out, err

    def auto_argv(self, root, *args, auto_py=AUTO_PY):
        return [sys.executable, auto_py, "--root", root] + list(args)

    # -- atos humanos no terminal
    def senha_ok(self):
        return gravar_registro(self.senha_file, SENHA)

    def approve_pty(self, root, senha=SENHA, by=HUMAN, orc=ORC, extra=(), env=None, auto_py=AUTO_PY):
        args = ["approve", "--by", by] + (["--orcamento", orc] if orc else []) + list(extra)
        return run_pty(self.auto_argv(root, *args, auto_py=auto_py), env or self._env(), answers=(senha,))

    def conferir_pty(self, root, senha=SENHA, env=None):
        return run_pty(self.auto_argv(root, "conferir"), env or self._env(), answers=(senha,))

    def definir_pty(self, root, answers, env=None, auto_py=AUTO_PY):
        return run_pty(self.auto_argv(root, "senha", "definir", auto_py=auto_py), env or self._env(), answers=answers)

    # -- leitura
    def estado(self, root):
        return self.status(root).get("estado")

    def approve_events(self, root):
        return m5.mevents(root, "approve")

    def selo(self, root):
        ev = self.approve_events(root)
        self.assertTrue(ev, "nenhum evento mandato.approve")
        d = ev[-1].get("data") or {}
        self.assertIsInstance(d.get("selo"), dict, "o evento mandato.approve grava `data.selo` (objeto): %r" % d)
        return ev[-1], d["selo"]

    def no_echo(self, out, *segredos):
        for s in segredos:
            self.assertNotIn(s, out, "a senha apareceu no terminal (eco ligado ou impressa)")
        self.assertNotIn("Traceback", out)

    def tree_bytes(self, base):
        out = []
        for dp, _, fs in os.walk(base):
            for f in fs:
                try:
                    with open(os.path.join(dp, f), "rb") as fh:
                        out.append((os.path.join(dp, f), fh.read()))
                except OSError:
                    pass
        return out

    def assert_sem_senha_no_disco(self, *bases):
        for b in bases:
            for p, data in self.tree_bytes(b):
                for s in (SENHA, SENHA_ERRADA, SENHA_AGENTE):
                    self.assertNotIn(s.encode("utf-8"), data, "senha gravada em %s" % p)

    # -- montagem
    def proposto(self, acs=m5.ACS_2, nos=2):
        fx = self.make_repo(acs=acs)
        mid = self.propose(fx, nos=nos)
        return fx, mid

    def aprovado(self, acs=m5.ACS_2, nos=2):
        self.senha_ok()
        fx, mid = self.proposto(acs, nos)
        code, out, n = self.approve_pty(fx.root)
        self.assertEqual(code, 0, "approve com a senha certa no terminal deveria passar (exit %d): %s" % (code, out[-1500:]))
        self.assertEqual(self.estado(fx.root), "CHARTERED")
        return fx, mid

    def controle_definir(self, root):
        """Controle positivo: com terminal, senha forte e confirmação igual, `senha definir` grava o registro."""
        if os.path.lexists(self.senha_file):
            os.remove(self.senha_file)
        code, out, n = self.definir_pty(root, (SENHA, SENHA))
        self.assertEqual(code, 0, "controle: senha definir legítimo passa (exit %d): %s" % (code, out[-800:]))
        self.assertTrue(os.path.isfile(self.senha_file), "controle: registro gravado")

    def assert_nao_aprovou(self, root, msg):
        self.assertEqual(self.estado(root), "PROPOSED", "%s: o mandato não pode sair de PROPOSED" % msg)
        self.assertFalse(self.approve_events(root), "%s: nenhum evento mandato.approve pode ser gravado" % msg)

    # -- forjador (agente com escrita no estado, sem a senha)
    def projection_path(self, root):
        for dp, _, fs in os.walk(m5.sd(root)):
            for f in fs:
                if not f.endswith(".json5"):
                    continue
                p = os.path.join(dp, f)
                try:
                    d = m5.json5io.read(p)
                except Exception:
                    continue
                if isinstance(d, dict) and "last_event_hash" in d and isinstance(d.get("mandatos"), list):
                    return p
        self.fail("projeção do motor (com last_event_hash e mandatos) não encontrada")

    def tamper_mandate(self, root, mid, fn):
        p = self.projection_path(root)
        b = m5.json5io.read(p)
        ms = [m for m in b["mandatos"] if m.get("id") == mid]
        self.assertTrue(ms, "mandato %s ausente da projeção" % mid)
        fn(ms[0])
        with open(p, "w", encoding="utf-8") as f:
            json.dump(b, f, ensure_ascii=False, indent=1)

    def rewrite_chain(self, root, mutate):
        """Reescreve events.jsonl aplicando mutate(records), re-encadeia seq/prev e atualiza o hash final onde ele
        estiver gravado (projeção etc.). É o que um agente sem a senha consegue fazer."""
        p = m5.sd(root, "events.jsonl")
        with open(p, "rb") as f:
            lines = [ln for ln in f.read().split(b"\n") if ln.strip()]
        old_last = sha(lines[-1])
        recs = [json.loads(ln.decode("utf-8")) for ln in lines]
        prev = recs[0].get("prev")
        mutate(recs)
        out = []
        for i, r in enumerate(recs):
            r["seq"], r["prev"] = i, prev
            line = json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            out.append(line)
            prev = sha(line)
        with open(p, "wb") as f:
            f.write(b"\n".join(out) + b"\n")
        for fp, data in self.tree_bytes(m5.sd(root)):
            if fp != p and old_last.encode() in data:
                with open(fp, "wb") as f:
                    f.write(data.replace(old_last.encode(), prev.encode()))

    def mutate_approve(self, root, fn):
        """fn(evento_approve) sobre o ÚLTIMO mandato.approve da cadeia."""
        def mut(recs):
            idx = [i for i, r in enumerate(recs) if r.get("type") == "mandato.approve"]
            self.assertTrue(idx, "sem mandato.approve na cadeia")
            fn(recs[idx[-1]])
        self.rewrite_chain(root, mut)

    def snapshot(self, root):
        snap = os.path.join(self.tmp, "snap-%d" % len(os.listdir(self.tmp)))
        shutil.copytree(m5.sd(root), snap, symlinks=True)
        return snap

    def restore(self, root, snap):
        shutil.rmtree(m5.sd(root))
        shutil.copytree(snap, m5.sd(root), symlinks=True)

    def assert_tick_recusa_selo(self, root, msg):
        """Recusa do avanço: exit != 0 citando o selo, OU exit 0 com acao ASK_HUMAN citando o selo. Em ambos os
        casos o mandato NÃO avança: mesmo estado e nenhum evento mandato.* novo."""
        est = self.estado(root)
        n = len(m5.mevents(root))
        code, out, err = self.auto(root, "tick", "--json")
        txt = (out + err).lower()
        if code == 0:
            try:
                t = json.loads(out)
            except ValueError:
                t = {}
            self.assertEqual(t.get("acao"), "ASK_HUMAN", "%s: tick deveria RECUSAR avançar (exit≠0 ou ASK_HUMAN), "
                             "veio %r" % (msg, out[-800:]))
        self.assertIn("selo", txt, "%s: a recusa do tick deve citar o selo: %s" % (msg, (out + err)[-800:]))
        self.assertEqual(self.estado(root), est, "%s: o mandato não pode sair de %s" % (msg, est))
        self.assertEqual(len(m5.mevents(root)), n, "%s: nenhum evento mandato.* novo na recusa" % msg)


# ====================================================================== S1 — cs-auto senha definir
class TestS1SenhaDefinir(Base):
    def test_definir_grava_so_sal_e_verificador_pbkdf2_modo_0600(self):
        root = self.minimal_repo()
        code, out, n = self.definir_pty(root, (SENHA, SENHA))
        self.assertEqual(code, 0, "senha definir no terminal deveria passar (exit %d): %s" % (code, out[-1500:]))
        self.assertGreaterEqual(n, 2, "definir pede a senha e a confirmação (2 prompts `SENHA...:`), viu %d" % n)
        self.no_echo(out, SENHA)
        self.assertTrue(os.path.isfile(self.senha_file), "registro gravado em $CS_SENHA_FILE")
        self.assertEqual(stat.S_IMODE(os.stat(self.senha_file).st_mode), 0o600, "registro com modo 0600")
        with open(self.senha_file, "rb") as f:
            raw = f.read()
        self.assertNotIn(SENHA.encode("utf-8"), raw, "o registro não pode conter a senha")
        reg = json.loads(raw.decode("utf-8"))
        self.assertEqual(reg.get("versao"), 1)
        self.assertEqual(reg.get("kdf"), "pbkdf2-sha256")
        self.assertIs(type(reg.get("iter")), int)
        self.assertGreaterEqual(reg["iter"], ITER, "PBKDF2 com ≥ 600000 iterações")
        for k in ("salt_verificador", "salt_chave"):
            self.assertRegex(str(reg.get(k)), r"^([0-9a-f]{2}){16,}$", "%s: hex de ≥ 16 bytes" % k)
        self.assertNotEqual(reg["salt_verificador"], reg["salt_chave"], "sais distintos (verificador × chave)")
        self.assertRegex(str(reg.get("verificador")), HEX64)
        self.assertEqual(reg["verificador"], derivar(SENHA, reg["salt_verificador"], reg["iter"]).hex(),
                         "verificador = PBKDF2-HMAC-SHA256(senha NFC sem espaços das pontas, salt_verificador, iter)")
        self.assert_sem_senha_no_disco(root, self.tmp)

    def test_definir_sem_terminal_recusa_e_nao_grava(self):
        root = self.minimal_repo()
        argv = self.auto_argv(root, "senha", "definir")
        for data in (None, ("%s\n%s\n" % (SENHA, SENHA)).encode("utf-8")):
            code, out = run_notty(argv, self._env(), data)
            self.assertNotEqual(code, 0, "senha definir sem terminal (stdin %s) deveria falhar: %s" % (
                "pipe" if data else "/dev/null", out[-800:]))
            self.assertFalse(os.path.lexists(self.senha_file), "sem terminal nada é gravado")
        self.controle_definir(root)

    def test_definir_recusa_senha_fraca(self):
        root = self.minimal_repo()
        for fraca in FRACAS:
            code, out, n = self.definir_pty(root, (fraca, fraca))
            self.assertNotEqual(code, 0, "senha fraca %r deveria ser recusada: %s" % (fraca, out[-600:]))
            self.assertFalse(os.path.lexists(self.senha_file), "senha fraca %r: nada gravado" % fraca)
        self.controle_definir(root)

    def test_definir_confirmacao_diferente_recusa(self):
        root = self.minimal_repo()
        code, out, n = self.definir_pty(root, (SENHA, SENHA_ERRADA))
        self.assertNotEqual(code, 0, "confirmação diferente deveria ser recusada: %s" % out[-600:])
        self.assertFalse(os.path.lexists(self.senha_file))
        self.controle_definir(root)

    def test_redefinir_exige_a_senha_atual(self):
        root = self.minimal_repo()
        self.senha_ok()
        with open(self.senha_file, "rb") as f:
            antes = f.read()
        code, out, n = self.definir_pty(root, (SENHA_ERRADA, SENHA_AGENTE, SENHA_AGENTE))
        self.assertNotEqual(code, 0, "trocar a senha sem a senha atual deveria falhar: %s" % out[-600:])
        with open(self.senha_file, "rb") as f:
            self.assertEqual(f.read(), antes, "senha atual errada: registro intocado")
        code, out, n = self.definir_pty(root, (SENHA, SENHA_AGENTE, SENHA_AGENTE))
        self.assertEqual(code, 0, "com a senha atual a troca passa (exit %d): %s" % (code, out[-800:]))
        self.no_echo(out, SENHA, SENHA_AGENTE)
        with open(self.senha_file, "r", encoding="utf-8") as f:
            reg = json.load(f)
        self.assertEqual(reg["verificador"], derivar(SENHA_AGENTE, reg["salt_verificador"], reg["iter"]).hex())

    def test_caminho_padrao_no_home_do_usuario_fora_do_alvo(self):
        root = self.minimal_repo()
        env = self._env()
        env.pop("CS_SENHA_FILE")
        code, out, n = self.definir_pty(root, (SENHA, SENHA), env=env)
        self.assertEqual(code, 0, "definir com o caminho padrão (exit %d): %s" % (code, out[-1000:]))
        p = os.path.join(self.home, ".config", "codebase-specialists", "senha.json")
        self.assertTrue(os.path.isfile(p), "padrão: ~/.config/codebase-specialists/senha.json")
        self.assertEqual(stat.S_IMODE(os.stat(p).st_mode), 0o600)
        for fp, data in self.tree_bytes(root):
            self.assertNotIn(b"salt_verificador", data, "registro de senha dentro do alvo: %s" % fp)

    def test_caminho_dentro_do_alvo_recusado(self):
        root = self.minimal_repo()
        for dentro in (os.path.join(root, "senha.json"), os.path.join(root, SD, "senha.json")):
            code, out, n = self.definir_pty(root, (SENHA, SENHA), env=self._env({"CS_SENHA_FILE": dentro}))
            self.assertNotEqual(code, 0, "CS_SENHA_FILE dentro do repositório-alvo deveria ser recusado: %s" % out[-600:])
            self.assertFalse(os.path.lexists(dentro), "nada gravado dentro do alvo")
        self.controle_definir(root)

    def test_nao_depende_da_auto_correcao(self):
        bad = re.compile(r"^\s*(import\s+frase\b|from\s+frase\s+import)|auto-correcao/scripts|AC_FRASE_FILE", re.M)
        for dp, dns, fs in os.walk(os.path.join(SKILL, "scripts")):
            dns[:] = [d for d in dns if d not in ("__pycache__", "tests")]
            for f in fs:
                if f.endswith(".py") or "bin" in dp.split(os.sep):
                    p = os.path.join(dp, f)
                    with open(p, "r", encoding="utf-8", errors="replace") as fh:
                        m = bad.search(fh.read())
                    self.assertIsNone(m, "a skill pública não pode depender da auto-correcao: %s (%r)" % (
                        p, m.group(0) if m else ""))
        # cópia da skill SEM a auto-correcao ao lado e com HOME vazio: definir + approve funcionam sozinhos
        dst = os.path.join(self.tmp, "skills", "codebase-specialists")
        shutil.copytree(SKILL, dst, ignore=shutil.ignore_patterns("__pycache__", ".git", "evals"))
        auto_cp = os.path.join(dst, "scripts", "harness", "engine", "auto.py")
        fx, mid = self.proposto()
        # o registro da auto-correcao (com a MESMA senha) não serve de senha do mandato
        acf = os.path.join(self.tmp, "ac", "frase.json")
        gravar_registro(acf, SENHA)
        code, out, n = self.approve_pty(fx.root, env=self._env({"AC_FRASE_FILE": acf}), auto_py=auto_cp)
        self.assertNotEqual(code, 0, "sem senha do mandato definida o approve falha, mesmo com frase da auto-correcao")
        self.assert_nao_aprovou(fx.root, "registro só da auto-correcao")
        code, out, n = self.definir_pty(fx.root, (SENHA, SENHA), auto_py=auto_cp)
        self.assertEqual(code, 0, "definir pela cópia isolada da skill (exit %d): %s" % (code, out[-800:]))
        code, out, n = self.approve_pty(fx.root, auto_py=auto_cp)
        self.assertEqual(code, 0, "approve pela cópia isolada da skill (exit %d): %s" % (code, out[-800:]))
        self.assertEqual(self.estado(fx.root), "CHARTERED")


# ====================================================================== S2 — approve exige terminal + senha
class TestS2Approve(Base):
    def test_approve_com_a_senha_certa_no_terminal(self):
        self.senha_ok()
        fx, mid = self.proposto()
        code, out, n = self.approve_pty(fx.root)
        self.assertEqual(code, 0, "approve com a senha certa (exit %d): %s" % (code, out[-1500:]))
        self.assertGreaterEqual(n, 1, "approve pede a senha (prompt `SENHA...:`)")
        self.no_echo(out, SENHA)
        self.assertEqual(self.estado(fx.root), "CHARTERED")
        self.assert_sem_senha_no_disco(fx.root, self.tmp)

    def test_approve_senha_errada_nao_sai_de_proposed(self):
        self.senha_ok()
        fx, mid = self.proposto()
        code, out, n = self.approve_pty(fx.root, senha=SENHA_ERRADA)
        self.assertNotEqual(code, 0, "senha errada deveria ser recusada: %s" % out[-800:])
        self.assertGreaterEqual(n, 1, "a senha foi pedida")
        self.no_echo(out, SENHA_ERRADA)
        self.assert_nao_aprovou(fx.root, "senha errada")
        self.assert_sem_senha_no_disco(fx.root, self.tmp)
        code, out, n = self.approve_pty(fx.root)
        self.assertEqual(code, 0, "depois, a senha certa aprova (exit %d): %s" % (code, out[-800:]))

    def test_approve_sem_terminal_recusa(self):
        self.senha_ok()
        fx, mid = self.proposto()
        argv = self.auto_argv(fx.root, "approve", "--by", HUMAN, "--orcamento", ORC)
        for data in (None, (SENHA + "\n").encode("utf-8")):
            code, out = run_notty(argv, self._env(), data)
            self.assertNotEqual(code, 0, "approve sem terminal (stdin %s) deveria falhar: %s" % (
                "pipe com a senha" if data else "/dev/null", out[-800:]))
            self.assert_nao_aprovou(fx.root, "sem terminal")

    def test_approve_stdin_em_pipe_recusa_mesmo_com_tty_controlador(self):
        self.senha_ok()
        fx, mid = self.proposto()
        argv = self.auto_argv(fx.root, "approve", "--by", HUMAN, "--orcamento", ORC)
        code, out, n = run_pty(argv, self._env(), answers=(SENHA,), stdin_data=(SENHA + "\n").encode("utf-8"))
        self.assertNotEqual(code, 0, "stdin em pipe (mesmo com /dev/tty) deveria ser recusado: %s" % out[-800:])
        self.assert_nao_aprovou(fx.root, "stdin em pipe")

    def test_approve_nao_aceita_senha_por_argumento_nem_ambiente(self):
        self.senha_ok()
        fx, mid = self.proposto()
        base = ["approve", "--by", HUMAN, "--orcamento", ORC]
        for extra in (["--senha", SENHA], ["--senha=" + SENHA], ["--password", SENHA], [SENHA]):
            code, out = run_notty(self.auto_argv(fx.root, *(base + extra)), self._env())
            self.assertNotEqual(code, 0, "senha por argumento %r sem terminal deveria falhar" % extra[0])
            self.assert_nao_aprovou(fx.root, "argumento %r" % extra[0])
            code, out, n = self.approve_pty(fx.root, senha=SENHA_ERRADA, extra=extra)
            self.assertNotEqual(code, 0, "argumento %r com a senha certa + digitada errada deveria falhar" % extra[0])
            self.assert_nao_aprovou(fx.root, "argumento %r (tty)" % extra[0])
        env = self._env(dict((k, SENHA) for k in SENHA_ENV_VARS))
        env["CS_HUMAN_PROOF_ARGS"] = "--senha %s" % SENHA
        code, out = run_notty(self.auto_argv(fx.root, *base), env)
        self.assertNotEqual(code, 0, "senha por variável de ambiente sem terminal deveria falhar")
        self.assert_nao_aprovou(fx.root, "variáveis de ambiente")
        code, out, n = self.approve_pty(fx.root, senha=SENHA_ERRADA, env=env)
        self.assertNotEqual(code, 0, "variáveis com a senha certa + digitada errada deveria falhar")
        self.assert_nao_aprovou(fx.root, "variáveis de ambiente (tty)")

    def test_approve_sem_senha_definida_manda_rodar_senha_definir(self):
        fx, mid = self.proposto()
        self.assertFalse(os.path.lexists(self.senha_file))
        code, out, n = self.approve_pty(fx.root)
        self.assertNotEqual(code, 0, "sem senha definida o approve falha: %s" % out[-800:])
        self.assertIn("senha definir", out, "a mensagem manda rodar `cs-auto senha definir`: %s" % out[-800:])
        self.assert_nao_aprovou(fx.root, "sem senha definida")

    def test_registro_de_senha_invalido_recusa(self):
        fx, mid = self.proposto()
        for kw in ({"it": 1000}, {"kdf": "md5"}):
            gravar_registro(self.senha_file, SENHA, **kw)
            code, out, n = self.approve_pty(fx.root)
            self.assertNotEqual(code, 0, "registro inválido %r deveria ser recusado: %s" % (kw, out[-600:]))
            self.assert_nao_aprovou(fx.root, "registro %r" % kw)

    def test_by_humano_continua_exigido_com_a_senha_certa(self):
        """Regressão (passa na base): a senha não substitui o --by humano."""
        self.senha_ok()
        fx, mid = self.proposto()
        for who in ("orchestrator", "lead", "dev-billing"):
            code, out, n = self.approve_pty(fx.root, by=who)
            self.assertEqual(code, 1, "approve --by %s deveria ser recusado (exit 1): %s" % (who, out[-600:]))
            self.assertIn("by_human", m5.GUARD_RE.findall(out), "recusa pela guarda by_human: %s" % out[-600:])
            self.assert_nao_aprovou(fx.root, "--by %s" % who)


# ====================================================================== S3 — selo HMAC no evento de aprovação
class TestS3Selo(Base):
    def test_selo_hmac_da_senha_sobre_mandato_plano_orcamento_seq_ts(self):
        fx, mid = self.aprovado()
        ev, selo = self.selo(fx.root)
        self.assertEqual(selo.get("versao"), 1)
        self.assertEqual(selo.get("alg"), "hmac-sha256")
        self.assertEqual(selo.get("mandato"), mid, "selo.mandato = id do mandato")
        self.assertRegex(str(selo.get("plano_sha256")), HEX64, "selo.plano_sha256 = sha256 do plano aprovado")
        orc = selo.get("orcamento")
        self.assertIsInstance(orc, dict, "selo.orcamento (objeto)")
        d = orc.get("despachos")
        self.assertEqual(d.get("limite") if isinstance(d, dict) else d, 17, "selo.orcamento traz o orçamento APROVADO")
        self.assertEqual(selo.get("seq"), 1, "1ª aprovação do mandato: selo.seq = 1")
        self.assertTrue(isinstance(selo.get("ts"), str) and selo["ts"], "selo.ts (texto)")
        self.assertRegex(str(selo.get("tag")), HEX64)
        with open(self.senha_file, "r", encoding="utf-8") as f:
            reg = json.load(f)
        self.assertEqual(selo["tag"], tag_esperada(reg, SENHA, selo),
                         "tag = HMAC-SHA256(PBKDF2(senha, salt_chave, iter), canonical(mandato, plano_sha256, "
                         "orcamento, seq, ts))")
        self.assertNotEqual(selo["tag"], tag_esperada(reg, SENHA_ERRADA, selo))
        self.assert_sem_senha_no_disco(fx.root, self.tmp)

    def test_selo_muda_com_o_orcamento_aprovado(self):
        self.senha_ok()
        fx, mid = self.proposto()
        code, out, n = self.approve_pty(fx.root, orc="despachos=5,tentativas=40,replanos=3,minutos=600")
        self.assertEqual(code, 0, out[-800:])
        ev, selo = self.selo(fx.root)
        d = selo["orcamento"].get("despachos")
        self.assertEqual(d.get("limite") if isinstance(d, dict) else d, 5)


# ====================================================================== S4 — tick recusa aprovação sem selo válido
class TestS4Tick(Base):
    def test_tick_legitimo_avanca_ate_running_e_segue(self):
        """Regressão (passa na base): selo válido não trava o piloto, nem depois do uso do orçamento mudar."""
        fx, mid = self.aprovado(acs=m5.ACS_STD, nos=3)
        t = self.tick(fx.root)
        self.assertEqual(t.get("acao"), "PLAN", "CHARTERED com selo válido: o piloto segue para o PLAN: %r" % t)
        self.submit_plan(fx.root, m5.NODES_STD)
        self.assertEqual(self.estado(fx.root), "RUNNING")
        t = self.tick(fx.root)
        self.assertEqual(t.get("acao"), "DISPATCH", "RUNNING: o piloto despacha: %r" % t)
        t2 = self.tick(fx.root)
        self.assertNotIn("selo", json.dumps(t2, ensure_ascii=False).lower(), "tick legítimo sem queixa de selo: %r" % t2)

    def test_tick_recusa_aprovacao_sem_selo(self):
        fx, mid = self.aprovado()
        self.selo(fx.root)  # pré-condição: aprovação legítima tem selo

        def strip(ev):
            walk_drop(ev, "selo")
        self.mutate_approve(fx.root, strip)
        self.tamper_mandate(fx.root, mid, lambda m: walk_drop(m, "selo"))
        self.assert_tick_recusa_selo(fx.root, "aprovação sem selo (evento escrito à mão)")
        self.assert_tick_recusa_selo(fx.root, "2º tick: a recusa é estável")

    def test_tick_recusa_selo_fora_do_formato(self):
        fx, mid = self.aprovado()
        self.selo(fx.root)  # pré-condição: aprovação legítima tem selo
        snap = self.snapshot(fx.root)
        variantes = (
            ("tag não-hex", lambda s: s.__setitem__("tag", "z" * 64)),
            ("tag curta", lambda s: s.__setitem__("tag", "ab" * 8)),
            ("sem tag", lambda s: s.pop("tag", None)),
            ("de outro mandato", lambda s: s.__setitem__("mandato", "MAN-999")),
            ("sem plano_sha256", lambda s: s.pop("plano_sha256", None)),
            ("alg desconhecido", lambda s: s.__setitem__("alg", "none")),
        )
        for nome, fn in variantes:
            self.restore(fx.root, snap)

            def mut(ev, fn=fn):
                fn(ev["data"]["selo"])
            self.mutate_approve(fx.root, mut)
            self.assert_tick_recusa_selo(fx.root, "selo %s" % nome)
        self.restore(fx.root, snap)
        self.mutate_approve(fx.root, lambda ev: ev["data"].__setitem__("selo", "ok"))
        self.assert_tick_recusa_selo(fx.root, "selo que não é objeto")

    def test_tick_recusa_contrato_alterado_depois_da_aprovacao(self):
        fx, mid = self.aprovado()
        self.selo(fx.root)  # pré-condição: aprovação legítima tem selo
        snap = self.snapshot(fx.root)

        def crit_cmd(m):
            c = m["criterios"][0]
            for k in ("comando", "teste", "test", "cmd"):
                if k in c:
                    c[k] = "true"
                    return
            c["texto"] = "Dado nada Quando nada Então passa"

        variantes = (
            ("orçamento inflado", lambda m: m["orcamento"].__setitem__("despachos", 999)),
            ("objetivo trocado", lambda m: m.__setitem__("objetivo", "Outro objetivo qualquer")),
            ("critério trocado", crit_cmd),
            ("regressão trocada", lambda m: m.__setitem__("regressao", "true")),
        )
        for nome, fn in variantes:
            self.restore(fx.root, snap)
            self.tamper_mandate(fx.root, mid, fn)
            self.assert_tick_recusa_selo(fx.root, "plano alterado depois da aprovação (%s)" % nome)

    def test_forja_consistente_na_cadeia_sem_a_senha_recusada(self):
        """O forjador reescreve o ORÇAMENTO na projeção E no evento de aprovação (cadeia re-encadeada), mas não sabe
        a senha: o selo antigo não cobre o plano novo."""
        fx, mid = self.aprovado()
        self.selo(fx.root)  # pré-condição: aprovação legítima tem selo

        def mut(ev):
            for op in ev.get("ops") or []:
                if len(op) >= 4 and op[0] == "set" and op[2] == "orcamento" and isinstance(op[3], dict):
                    op[3]["despachos"] = 999
        self.mutate_approve(fx.root, mut)
        self.tamper_mandate(fx.root, mid, lambda m: m["orcamento"].__setitem__("despachos", 999))
        self.assert_tick_recusa_selo(fx.root, "orçamento reescrito na cadeia e na projeção")

    def test_tick_recusa_orcamento_inflado_em_running(self):
        fx, mid = self.aprovado(acs=m5.ACS_STD, nos=3)
        self.assertEqual(self.tick(fx.root).get("acao"), "PLAN")
        self.submit_plan(fx.root, m5.NODES_STD)
        self.assertEqual(self.estado(fx.root), "RUNNING")
        self.tamper_mandate(fx.root, mid, lambda m: m["orcamento"].__setitem__("despachos", 999))
        self.assert_tick_recusa_selo(fx.root, "orçamento inflado no meio da execução")


# ====================================================================== S5 — cs-auto conferir (humano, terminal + senha)
class TestS5Conferir(Base):
    def conferir_falha(self, root, ev_seq, mid, msg, senha=SENHA):
        code, out, n = self.conferir_pty(root, senha=senha)
        self.assertNotEqual(code, 0, "%s: conferir deveria falhar: %s" % (msg, out[-800:]))
        self.assertTrue(re.search(r"seq\D{0,3}%d\b" % ev_seq, out),
                        "%s: conferir nomeia o evento (`seq %d`): %s" % (msg, ev_seq, out[-800:]))
        self.assertIn(mid, out, "%s: conferir cita o mandato" % msg)
        self.no_echo(out, senha)
        return out

    def test_conferir_legitimo_passa_e_nao_muda_o_mandato(self):
        fx, mid = self.aprovado()
        est = self.estado(fx.root)
        code, out, n = self.conferir_pty(fx.root)
        self.assertEqual(code, 0, "conferir com a senha certa e selo legítimo (exit %d): %s" % (code, out[-1000:]))
        self.assertGreaterEqual(n, 1, "conferir pede a senha")
        self.assertIn(mid, out)
        self.no_echo(out, SENHA)
        self.assertEqual(self.estado(fx.root), est)

    def test_conferir_senha_errada_ou_sem_terminal_recusa(self):
        fx, mid = self.aprovado()
        code, out, n = self.conferir_pty(fx.root)
        self.assertEqual(code, 0, "controle: conferir legítimo passa (exit %d): %s" % (code, out[-600:]))
        code, out, n = self.conferir_pty(fx.root, senha=SENHA_ERRADA)
        self.assertNotEqual(code, 0, "conferir com senha errada deveria falhar: %s" % out[-600:])
        self.no_echo(out, SENHA_ERRADA)
        for data in (None, (SENHA + "\n").encode("utf-8")):
            code, out = run_notty(self.auto_argv(fx.root, "conferir"), self._env(), data)
            self.assertNotEqual(code, 0, "conferir sem terminal deveria falhar: %s" % out[-600:])

    def test_conferir_denuncia_tag_aleatoria(self):
        fx, mid = self.aprovado()
        self.selo(fx.root)  # pré-condição: aprovação legítima tem selo
        self.mutate_approve(fx.root, lambda ev: ev["data"]["selo"].__setitem__("tag", os.urandom(32).hex()))
        ev, _ = self.selo(fx.root)
        self.conferir_falha(fx.root, ev["seq"], mid, "tag aleatória no formato válido")

    def test_conferir_denuncia_tag_de_outra_senha(self):
        fx, mid = self.aprovado()
        self.selo(fx.root)  # pré-condição: aprovação legítima tem selo
        with open(self.senha_file, "r", encoding="utf-8") as f:
            reg = json.load(f)

        def mut(ev):
            s = ev["data"]["selo"]
            s["orcamento"] = dict(s["orcamento"], despachos=999)
            s["tag"] = tag_esperada(reg, SENHA_AGENTE, s)
        self.mutate_approve(fx.root, mut)
        ev, _ = self.selo(fx.root)
        self.conferir_falha(fx.root, ev["seq"], mid, "tag calculada com outra senha")

    def test_conferir_denuncia_aprovacao_sem_selo(self):
        fx, mid = self.aprovado()
        self.selo(fx.root)  # pré-condição: aprovação legítima tem selo
        self.mutate_approve(fx.root, lambda ev: walk_drop(ev, "selo"))
        ev = self.approve_events(fx.root)[-1]
        self.conferir_falha(fx.root, ev["seq"], mid, "aprovação sem selo")

    def test_troca_do_registro_de_senha_pelo_agente_e_denunciada(self):
        """Limite honesto: o agente troca o registro por um da senha DELE e re-sela. O humano, ao conferir com a
        senha REAL, é recusado — é o sinal da troca."""
        fx, mid = self.aprovado()
        self.selo(fx.root)  # pré-condição: aprovação legítima tem selo
        gravar_registro(self.senha_file, SENHA_AGENTE)
        with open(self.senha_file, "r", encoding="utf-8") as f:
            reg_ag = json.load(f)
        self.mutate_approve(fx.root, lambda ev: ev["data"]["selo"].__setitem__(
            "tag", tag_esperada(reg_ag, SENHA_AGENTE, ev["data"]["selo"])))
        code, out, n = self.conferir_pty(fx.root, senha=SENHA)
        self.assertNotEqual(code, 0, "o humano confere com a senha real e é recusado (registro trocado): %s" % out[-600:])


# ====================================================================== S6 — guard, skill humana e doc
class TestS6GuardEDoc(Base):
    def test_guard_trata_senha_conferir_e_approve_como_so_do_humano(self):
        root = self.minimal_repo()
        bloqueados = ["cs-auto senha definir", "%s/bin/cs-auto senha definir" % SD, "cs-auto conferir",
                      "%s/bin/cs-auto conferir" % SD, "python3 %s --root . senha definir" % AUTO_PY,
                      "python3 %s conferir" % AUTO_PY, "cs-auto approve --by founder",
                      "cd x && cs-auto senha definir"]
        livres = ["cs-auto tick", "cs-auto status --json", "grep -n 'senha definir' docs/11-modo-autonomo.md",
                  "cat %s/bin/cs-auto" % SD]
        for actor in ({}, {"agent_id": "ag-1", "agent_type": "dev-billing"}):
            for c in bloqueados:
                p = {"tool_name": "Bash", "tool_use_id": "tu-b", "tool_input": {"command": c}, "cwd": root}
                p.update(actor)
                code, out, err = self.hook(root, "pre-bash", p)
                self.assertEqual(code, 2, "ato HUMANO bloqueado para o %s: %s" % ("subagente" if actor else "principal", c))
            if not actor:
                for c in livres:
                    p = {"tool_name": "Bash", "tool_use_id": "tu-b", "tool_input": {"command": c}, "cwd": root}
                    self.assertEqual(self.hook(root, "pre-bash", p)[0], 0, "o principal pode rodar: %s" % c)

    def _ler(self, *parts):
        p = os.path.join(SKILL, *parts)
        self.assertTrue(os.path.isfile(p), "ausente: %s" % p)
        with open(p, "r", encoding="utf-8") as f:
            return f.read()

    def test_skill_auto_approve_descreve_o_fluxo_real_com_a_senha(self):
        t = self._ler("assets", "templates", "state", "auto-approve.md")
        self.assertIn("senha definir", t, "/auto-approve diz que a 1ª vez é `cs-auto senha definir`")
        self.assertIn("cs-auto approve", t)
        self.assertRegex(t.lower(), r"terminal", "/auto-approve diz que a senha é digitada no terminal do humano")
        for proibido in ("--senha", "CS_HUMAN_PROOF_ARGS", "CS_SENHA="):
            self.assertNotIn(proibido, t, "/auto-approve não pode sugerir senha por argumento/variável (%s)" % proibido)

    def test_doc_modo_autonomo_descreve_senha_selo_conferir_e_o_limite(self):
        t = self._ler("docs", "11-modo-autonomo.md")
        for termo in ("senha definir", "conferir", "selo", "HMAC", "terminal"):
            self.assertIn(termo, t, "docs/11-modo-autonomo.md deve tratar de %r" % termo)
        self.assertNotIn("--senha", t)
        self.assertRegex(t, r"(?is)tick.{0,300}(n[ãa]o (pode |consegue )?(verifica|conferir|confere|checa)|sem a senha)",
                         "a doc declara o limite: sem a senha o tick não verifica a HMAC (só o conferir humano)")


if __name__ == "__main__":
    unittest.main()
