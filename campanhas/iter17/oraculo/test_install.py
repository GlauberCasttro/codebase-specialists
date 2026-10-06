"""ORÁCULO campanha-iter17 — `/install`: a versão INSTALADA da skill é o PACOTE `dist/codebase-specialists`.

Decisão do founder: numa máquina nova ninguém digita comando de terminal; o Claude roda `/install`, que instala as
travas do git, gera e valida o pacote e liga `$HOME/.claude/skills/codebase-specialists` → `<projeto>/dist/
codebase-specialists`. O SessionStart (`carimbo.sh --brief`) avisa quando as travas faltam (e as instala) e quando o
pacote instalado está desatualizado. Mapa requisito→teste e contrato exato em ESPEC.md (mesma pasta).

  I1a travas do git (pre-commit/commit-msg) instaladas se faltarem; trava alheia nunca é sobrescrita
  I1b package falho ⇒ instalar falha e NÃO toca a instalação (nem a nova, nem a anterior que já funcionava)
  I1c link simbólico para o dist; algo diferente lá ⇒ backup em $HOME/.claude/skills-backup-<data>/ (nunca apaga)
  I1d conferência: cs.py --help do instalado, VERSION instalada == VERSION do projeto, nada interno no instalado
  I1e --dry-run e --check não escrevem nada; --check diz se está em dia (exit 0) ou não (exit != 0 + motivo)
  I1f 2 execuções seguidas sem erro e sem backup novo na 2ª (link intocado)
  I2  `.origem` no pacote (HEAD, sem caminho); carimbo --brief: instala travas que faltam e avisa; pacote
      desatualizado (commit de PRODUTO depois do pacote) ⇒ avisa e sugere /install; commit só de state não avisa
  I3  skill fina `.claude/skills/install`; close-front manda /install depois do commit; README "Primeira vez numa
      máquina nova" sem comando de terminal para o humano

Isolamento: cada teste monta uma CÓPIA TEMPORÁRIA do projeto (sem .git/local/dist/ledgers; vira um repositório git
novo com um commit) e um HOME TEMPORÁRIO. Nunca toca o HOME real nem o projeto sob teste.
Projeto sob teste: $CS_PROJETO; senão $CS_SKILL_DIR se for um projeto (tem .claude/tools — é o que o portão passa);
senão a raiz deste repositório. Python 3.9+, unittest puro.
Rodar (de dentro desta pasta):  python3 -m unittest -v test_install
"""
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import warnings

sys.dont_write_bytecode = True
warnings.simplefilter("ignore", ResourceWarning)

AQUI = os.path.dirname(os.path.abspath(__file__))


def _projeto():
    for v in ("CS_PROJETO", "CS_SKILL_DIR"):
        p = os.environ.get(v)
        if p and os.path.isdir(os.path.join(p, ".claude", "tools")):
            return os.path.realpath(p)
    return os.path.realpath(os.path.join(AQUI, "..", "..", ".."))


PROJETO = _projeto()
NOME = "codebase-specialists"
PROIBIDOS = {".claude", "campanhas", "local", "tests", "evals"}
IGNORAR_COPIA = {".git", "local", "dist", "__pycache__", ".auto-correcao", ".DS_Store"}
LINHA_TRAVA = ".claude/tools/pre-commit.sh"
GIT_ID = {"GIT_AUTHOR_NAME": "Ana", "GIT_AUTHOR_EMAIL": "ana@exemplo.invalid", "GIT_COMMITTER_NAME": "Ana",
          "GIT_COMMITTER_EMAIL": "ana@exemplo.invalid"}
TIMEOUT = 600


def ler(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def escrever(p, txt):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(txt)


def arvore(raiz, git_so_hooks=True):
    """Hash de uma árvore SEM seguir links: caminho, tipo, modo, mtime e conteúdo (alvo, se link). Em `.git/` só
    entra `hooks/` (git status pode regravar o índice; isso não é escrita do instalar)."""
    h = hashlib.sha256()
    if not os.path.lexists(raiz):
        return "ausente"
    for d, dirs, files in os.walk(raiz):
        rel_d = os.path.relpath(d, raiz)
        if git_so_hooks and rel_d == ".git":
            dirs[:] = [x for x in dirs if x == "hooks"]
            files = []
        dirs[:] = sorted(x for x in dirs if x != "__pycache__")
        for nome in sorted(dirs + files):
            p = os.path.join(d, nome)
            st = os.lstat(p)
            linha = "%s|%o|%d" % (os.path.relpath(p, raiz), st.st_mode, st.st_mtime_ns)
            if git_so_hooks and rel_d == "." and nome == ".git":
                linha = ".git|dir"   # o mtime da própria .git muda com o índice; hooks/ entra abaixo
            elif stat.S_ISLNK(st.st_mode):
                linha += "|->" + os.readlink(p)
            elif stat.S_ISREG(st.st_mode):
                with open(p, "rb") as fh:
                    linha += "|" + hashlib.sha256(fh.read()).hexdigest()
            h.update(linha.encode("utf-8", "surrogateescape") + b"\n")
        # links para diretório aparecem em dirs; os.walk não desce neles (followlinks=False)
    return h.hexdigest()


class Ambiente(object):
    """Cópia temporária do projeto (repositório git novo, 1 commit) + HOME temporário."""

    def __init__(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="cs-iter17-"))
        self.proj = os.path.join(self.tmp, "projeto")
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)
        shutil.copytree(PROJETO, self.proj, symlinks=True,
                        ignore=lambda d, ns: [n for n in ns if n in IGNORAR_COPIA or n.endswith(".pyc")])
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("CS_") and not k.startswith("GIT_")}
        self.env.update(GIT_ID)
        self.env.update({"HOME": self.home, "GIT_CONFIG_NOSYSTEM": "1", "XDG_CONFIG_HOME": os.path.join(self.tmp, "xdg"),
                         "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": os.environ.get("LC_ALL", "en_US.UTF-8")})
        self.git("init", "-q")
        self.commitar("base do oráculo iter17")
        self.skills = os.path.join(self.home, ".claude", "skills")
        self.link = os.path.join(self.skills, NOME)
        self.dist = os.path.join(self.proj, "dist", NOME)

    def limpar(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def git(self, *a):
        p = subprocess.run(["git", "-C", self.proj] + list(a), env=self.env, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=120)
        if p.returncode != 0:
            raise AssertionError("git %s falhou: %s" % (" ".join(a), p.stdout.decode("utf-8", "replace")))
        return p.stdout.decode("utf-8", "replace").strip()

    def commitar(self, msg):
        self.git("add", "-A")
        self.git("-c", "core.hooksPath=/dev/null", "commit", "-q", "--no-verify", "--allow-empty", "-m", msg)

    def head(self):
        return self.git("rev-parse", "HEAD")

    def run(self, args, cwd=None):
        p = subprocess.run(args, env=self.env, cwd=cwd or self.proj, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=TIMEOUT)
        return p.returncode, p.stdout.decode("utf-8", "replace")

    def instalar(self, *args, cwd=None):
        return self.run(["bash", os.path.join(self.proj, ".claude", "tools", "instalar.sh")] + list(args), cwd=cwd)

    def brief(self):
        return self.run(["bash", os.path.join(self.proj, ".claude", "tools", "carimbo.sh"), "--brief"])

    def hooks_dir(self):
        h = self.git("rev-parse", "--git-path", "hooks")
        return h if os.path.isabs(h) else os.path.join(self.proj, h)

    def trava(self, nome):
        return os.path.join(self.hooks_dir(), nome)

    def travas_ok(self):
        for n in ("pre-commit", "commit-msg"):
            p = self.trava(n)
            if not (os.path.isfile(p) and os.access(p, os.X_OK) and LINHA_TRAVA in ler(p)):
                return False
        return True

    def remover_travas(self):
        for n in ("pre-commit", "commit-msg"):
            if os.path.lexists(self.trava(n)):
                os.remove(self.trava(n))

    def backups(self):
        base = os.path.join(self.home, ".claude")
        if not os.path.isdir(base):
            return []
        return sorted(os.path.join(base, d, NOME) for d in os.listdir(base)
                      if d.startswith("skills-backup-") and os.path.lexists(os.path.join(base, d, NOME)))

    def pasta_alheia(self, marca):
        os.makedirs(self.link)
        escrever(os.path.join(self.link, "MARCA.txt"), marca)

    def hashes(self):
        return arvore(self.home), arvore(self.proj)

    def mudar_produto(self):
        p = os.path.join(self.proj, "SKILL.md")
        escrever(p, ler(p) + "\n<!-- mudança de produto do oráculo iter17 -->\n")
        self.commitar("produto: muda SKILL.md")

    def mudar_so_state(self):
        escrever(os.path.join(self.proj, ".claude", "state", "nota-oraculo-iter17.md"), "nota de state\n")
        self.commitar("state: só estado")


class Base(unittest.TestCase):
    def setUp(self):
        self.a = Ambiente()
        self.addCleanup(self.a.limpar)

    def exige_instalar(self):
        self.assertTrue(os.path.isfile(os.path.join(self.a.proj, ".claude", "tools", "instalar.sh")),
                        "falta .claude/tools/instalar.sh")

    def instalar_ok(self, *args, cwd=None):
        rc, out = self.a.instalar(*args, cwd=cwd)
        self.assertEqual(rc, 0, "instalar.sh %s falhou:\n%s" % (" ".join(args), out[-3000:]))
        return out

    def assertLinkCerto(self):
        self.assertTrue(os.path.islink(self.a.link), "instalado não é link simbólico: %s" % self.a.link)
        self.assertEqual(os.path.realpath(self.a.link), os.path.realpath(self.a.dist),
                         "link não aponta para <projeto>/dist/%s" % NOME)
        self.assertTrue(os.path.isfile(os.path.join(self.a.link, "SKILL.md")))

    def assertNaoEscreveu(self, antes, oque):
        depois = self.a.hashes()
        self.assertEqual(antes[0], depois[0], "%s escreveu em $HOME" % oque)
        self.assertEqual(antes[1], depois[1], "%s escreveu no projeto" % oque)


# ---------------------------------------------------------------- I1: instalar.sh


class TestI1Instalar(Base):
    def test_i1_existe_e_help_nao_escreve(self):
        p = os.path.join(self.a.proj, ".claude", "tools", "instalar.sh")
        self.assertTrue(os.path.isfile(p), "falta .claude/tools/instalar.sh")
        antes = self.a.hashes()
        rc, out = self.a.instalar("--help")
        self.assertEqual(rc, 0, out)
        self.assertIn("--dry-run", out)
        self.assertIn("--check", out)
        self.assertNaoEscreveu(antes, "--help")

    def test_i1c_instalacao_nova_link_para_o_dist_independe_do_cwd(self):
        self.assertFalse(os.path.exists(os.path.join(self.a.home, ".claude")))
        self.instalar_ok(cwd=self.a.home)
        self.assertLinkCerto()
        self.assertNotEqual(os.path.realpath(self.a.link), os.path.realpath(self.a.proj),
                            "instalado aponta para o PROJETO, não para o pacote")
        self.assertEqual(self.a.backups(), [], "instalação nova não deveria criar backup")

    def test_i1d_instalado_roda_e_tem_a_versao_do_projeto(self):
        self.instalar_ok()
        rc, out = self.a.run([sys.executable, os.path.join(self.a.link, "scripts", "cs.py"), "--help"])
        self.assertEqual(rc, 0, out[-2000:])
        rc, out = self.a.run(["python3", os.path.join(self.a.link, "scripts", "cs.py"), "--help"])
        self.assertEqual(rc, 0, out[-2000:])
        self.assertEqual(ler(os.path.join(self.a.link, "VERSION")).strip(),
                         ler(os.path.join(self.a.proj, "VERSION")).strip())

    def test_i1d_instalado_sem_nada_interno(self):
        self.instalar_ok()
        raiz = os.path.realpath(self.a.link)
        achados = []
        for d, dirs, files in os.walk(raiz):
            for n in dirs + files:
                rel = os.path.relpath(os.path.join(d, n), raiz)
                if PROIBIDOS.intersection(rel.split(os.sep)):
                    achados.append(rel)
        self.assertEqual(achados, [], "o instalado contém pasta interna")
        for n in ("SKILL.md", "VERSION", os.path.join("scripts", "cs.py")):
            self.assertTrue(os.path.isfile(os.path.join(raiz, n)), n)

    def test_i1d_versao_do_projeto_divergente_do_pacote_reprova(self):
        # VERSION viva (árvore) != VERSION do HEAD (o pacote sai do HEAD) ⇒ a conferência final reprova
        escrever(os.path.join(self.a.proj, "VERSION"), "9.9.9\n")
        rc, out = self.a.instalar()
        self.assertNotEqual(rc, 0, "instalou com VERSION instalada != VERSION do projeto:\n" + out[-2000:])
        self.assertIn("VERSION", out)

    def test_i1a_instala_as_travas_do_git(self):
        self.assertFalse(self.a.travas_ok())
        self.instalar_ok()
        self.assertTrue(self.a.travas_ok(), "pre-commit/commit-msg do harness não instalados")

    def test_i1a_trava_alheia_nao_e_sobrescrita(self):
        alheia = "#!/bin/sh\n# trava de outra ferramenta\nexit 0\n"
        os.makedirs(self.a.hooks_dir(), exist_ok=True)
        escrever(self.a.trava("pre-commit"), alheia)
        os.chmod(self.a.trava("pre-commit"), 0o755)
        self.exige_instalar()
        self.a.instalar()
        self.assertEqual(ler(self.a.trava("pre-commit")), alheia, "instalar sobrescreveu trava alheia")
        p = self.a.trava("commit-msg")
        self.assertTrue(os.path.isfile(p) and LINHA_TRAVA in ler(p), "a trava que faltava (commit-msg) não entrou")

    def test_i1c_pasta_existente_vai_para_backup(self):
        self.a.pasta_alheia("versao-antiga")
        out = self.instalar_ok()
        self.assertLinkCerto()
        b = self.a.backups()
        self.assertEqual(len(b), 1, "esperado 1 backup em $HOME/.claude/skills-backup-*/%s: %r" % (NOME, b))
        self.assertEqual(ler(os.path.join(b[0], "MARCA.txt")), "versao-antiga")
        self.assertIn("skills-backup-", out, "instalar não informou o backup")

    def test_i1c_link_errado_vai_para_backup(self):
        os.makedirs(self.a.skills)
        os.symlink(self.a.proj, self.a.link)   # o jeito antigo: link para o projeto inteiro
        self.instalar_ok()
        self.assertLinkCerto()
        b = self.a.backups()
        self.assertEqual(len(b), 1, b)
        self.assertTrue(os.path.islink(b[0]), "o backup do link antigo deveria ser o próprio link")
        self.assertEqual(os.readlink(b[0]), self.a.proj)
        self.assertTrue(os.path.isfile(os.path.join(self.a.proj, "SKILL.md")), "o alvo do link antigo sumiu")

    def test_i1c_backup_nunca_apaga_backup_anterior(self):
        self.a.pasta_alheia("A")
        self.instalar_ok()
        os.remove(self.a.link)
        self.a.pasta_alheia("B")
        self.instalar_ok()
        self.assertLinkCerto()
        marcas = sorted(ler(os.path.join(b, "MARCA.txt")) for b in self.a.backups())
        self.assertEqual(marcas, ["A", "B"], "um backup sobrescreveu/apagou o outro")

    def test_i1f_duas_execucoes_sem_backup_novo_e_link_intocado(self):
        self.a.pasta_alheia("x")
        self.instalar_ok()
        b1 = self.a.backups()
        st1 = os.lstat(self.a.link)
        out2 = self.instalar_ok()
        self.assertEqual(self.a.backups(), b1, "a 2ª execução criou backup")
        st2 = os.lstat(self.a.link)
        self.assertEqual((st1.st_ino, st1.st_mtime_ns), (st2.st_ino, st2.st_mtime_ns),
                         "a 2ª execução recriou o link que já estava certo")
        self.assertLinkCerto()
        self.assertNotIn("skills-backup-", out2)

    def test_i1b_package_falho_nao_toca_instalacao(self):
        self.a.pasta_alheia("intocada")
        os.remove(os.path.join(self.a.proj, ".claude", "package", "README.md"))
        self.a.commitar("quebra o package (README do pacote ausente)")
        h_home = arvore(self.a.home)
        self.exige_instalar()
        rc, out = self.a.instalar()
        self.assertNotEqual(rc, 0, "package falhou e instalar deu exit 0:\n" + out[-2000:])
        self.assertEqual(arvore(self.a.home), h_home, "package falho mas o instalar mexeu em $HOME")
        self.assertEqual(self.a.backups(), [])
        self.assertEqual(ler(os.path.join(self.a.link, "MARCA.txt")), "intocada")

    def test_i1b_package_falho_preserva_instalacao_anterior_funcionando(self):
        self.instalar_ok()
        origem = ler(os.path.join(self.a.link, ".origem"))
        cs = os.path.join(self.a.proj, "scripts", "cs.py")
        txt = ler(cs)
        i = txt.index("\n") + 1 if txt.startswith("#!") else 0   # logo depois do shebang
        escrever(cs, txt[:i] + "raise SystemExit('quebrado pelo oraculo iter17')\n" + txt[i:])
        self.a.commitar("quebra cs.py (a validação do package reprova)")
        rc, out = self.a.instalar()
        self.assertNotEqual(rc, 0, "package com cs.py quebrado e instalar deu exit 0:\n" + out[-2000:])
        self.assertLinkCerto()
        rc, out = self.a.run(["python3", os.path.join(self.a.link, "scripts", "cs.py"), "--help"])
        self.assertEqual(rc, 0, "package falho quebrou a instalação que funcionava:\n" + out[-1500:])
        self.assertEqual(ler(os.path.join(self.a.link, ".origem")), origem, "o pacote instalado mudou")

    def test_i1e_dry_run_nao_escreve_e_mostra_o_plano(self):
        self.a.pasta_alheia("plano")
        antes = self.a.hashes()
        rc, out = self.a.instalar("--dry-run")
        self.assertEqual(rc, 0, out[-2000:])
        self.assertNaoEscreveu(antes, "--dry-run")
        self.assertIn("dist/" + NOME, out, "o plano não diz para onde o link vai")
        self.assertIn("backup", out.lower(), "o plano não diz que haveria backup")

    def test_i1e_dry_run_depois_de_instalado_nao_escreve(self):
        self.instalar_ok()
        self.a.remover_travas()
        antes = self.a.hashes()
        rc, out = self.a.instalar("--dry-run")
        self.assertEqual(rc, 0, out[-2000:])
        self.assertNaoEscreveu(antes, "--dry-run")

    def test_i1e_check_em_dia(self):
        self.instalar_ok()
        antes = self.a.hashes()
        rc, out = self.a.instalar("--check")
        self.assertEqual(rc, 0, "--check logo depois do instalar deveria dizer em dia:\n" + out[-2000:])
        self.assertNaoEscreveu(antes, "--check")

    def test_i1e_check_sem_instalacao(self):
        self.exige_instalar()
        antes = self.a.hashes()
        rc, out = self.a.instalar("--check")
        self.assertNotEqual(rc, 0)
        self.assertTrue(out.strip(), "--check reprovou sem motivo")
        self.assertNaoEscreveu(antes, "--check")

    def test_i1e_check_commit_de_produto_desatualiza(self):
        self.instalar_ok()
        self.a.mudar_produto()
        antes = self.a.hashes()
        rc, out = self.a.instalar("--check")
        self.assertNotEqual(rc, 0, "commit de produto depois do pacote e --check disse em dia")
        self.assertTrue(out.strip())
        self.assertNaoEscreveu(antes, "--check")

    def test_i1e_check_commit_so_de_state_continua_em_dia(self):
        self.instalar_ok()
        self.a.mudar_so_state()
        rc, out = self.a.instalar("--check")
        self.assertEqual(rc, 0, "commit só de .claude/state não muda o pacote:\n" + out[-2000:])

    def test_i1e_check_versao_divergente(self):
        self.instalar_ok()
        escrever(os.path.join(self.a.proj, "VERSION"), "9.9.9\n")
        rc, out = self.a.instalar("--check")
        self.assertNotEqual(rc, 0)
        self.assertTrue(out.strip())

    def test_i1e_check_link_errado(self):
        self.instalar_ok()
        os.remove(self.a.link)
        os.symlink(self.a.proj, self.a.link)
        rc, out = self.a.instalar("--check")
        self.assertNotEqual(rc, 0, "link para o projeto e --check disse em dia")
        self.assertTrue(out.strip())

    def test_i1e_check_travas_faltando_nao_reinstala(self):
        self.instalar_ok()
        self.a.remover_travas()
        antes = self.a.hashes()
        rc, out = self.a.instalar("--check")
        self.assertNotEqual(rc, 0, "travas do git ausentes e --check disse em dia")
        self.assertTrue(out.strip())
        self.assertNaoEscreveu(antes, "--check")
        self.assertFalse(self.a.travas_ok())


# ---------------------------------------------------------------- I2: origem + carimbo --brief


def linhas_com(out, *termos):
    return [l for l in out.splitlines() if all(t in l.lower() for t in termos)]


class TestI2Origem(Base):
    def test_i2_origem_no_pacote_instalado_sem_caminho(self):
        self.instalar_ok()
        p = os.path.join(self.a.link, ".origem")
        self.assertTrue(os.path.isfile(p), "o pacote não grava .origem")
        s = ler(p)
        self.assertIn(self.a.head(), re.findall(r"[0-9a-f]{40}", s), ".origem não traz o HEAD completo do projeto")
        self.assertNotIn("/", s, ".origem leva caminho")
        for priv in (self.a.home, self.a.proj, self.a.tmp):
            self.assertNotIn(priv, s)


class TestI2Brief(Base):
    def brief_ok(self):
        rc, out = self.a.brief()
        self.assertEqual(rc, 0, out[-2000:])
        return out

    def test_i2_brief_instala_travas_que_faltam_e_avisa_uma_vez(self):
        self.assertFalse(self.a.travas_ok())
        out = self.brief_ok()
        self.assertTrue(linhas_com(out, "travas", "faltav"), "o brief não avisou das travas que faltavam:\n" + out)
        self.assertTrue(self.a.travas_ok(), "o brief não instalou as travas do git")
        h = arvore(self.a.hooks_dir(), git_so_hooks=False)
        out2 = self.brief_ok()
        self.assertEqual(linhas_com(out2, "faltav"), [], "2º brief ainda diz que as travas faltam")
        self.assertEqual(arvore(self.a.hooks_dir(), git_so_hooks=False), h, "2º brief mexeu nas travas")

    def test_i2_brief_trava_alheia_preservada(self):
        alheia = "#!/bin/sh\n# trava de outra ferramenta\nexit 0\n"
        os.makedirs(self.a.hooks_dir(), exist_ok=True)
        escrever(self.a.trava("commit-msg"), alheia)
        self.brief_ok()
        self.assertEqual(ler(self.a.trava("commit-msg")), alheia)
        p = self.a.trava("pre-commit")
        self.assertTrue(os.path.isfile(p) and LINHA_TRAVA in ler(p), "a trava que faltava (pre-commit) não entrou")

    def test_i2_brief_sem_instalacao_sugere_install(self):
        out = self.brief_ok()
        self.assertIn("/install", out)

    def test_i2_brief_em_dia_nao_sugere_nada(self):
        self.instalar_ok()
        out = self.brief_ok()
        self.assertNotIn("/install", out, "instalação em dia e o brief sugere /install:\n" + out)
        self.assertEqual(linhas_com(out, "desatualizad"), [])
        self.assertEqual(linhas_com(out, "faltav"), [])

    def test_i2_brief_commit_de_produto_avisa_desatualizado(self):
        self.instalar_ok()
        self.a.mudar_produto()
        antes = self.a.hashes()
        out = self.brief_ok()
        self.assertTrue(linhas_com(out, "desatualizad"), "o brief não disse que o pacote está desatualizado:\n" + out)
        self.assertIn("/install", out)
        self.assertNaoEscreveu(antes, "carimbo --brief")

    def test_i2_brief_commit_so_de_state_nao_avisa(self):
        self.instalar_ok()
        self.a.mudar_so_state()
        out = self.brief_ok()
        self.assertEqual(linhas_com(out, "desatualizad"), [], out)
        self.assertNotIn("/install", out)

    def test_i2_brief_link_para_o_projeto_sugere_install(self):
        os.makedirs(self.a.skills)
        os.symlink(self.a.proj, self.a.link)
        out = self.brief_ok()
        self.assertIn("/install", out, "instalado = projeto inteiro (jeito antigo) e o brief não sugere /install")


# ---------------------------------------------------------------- I3: skill, close-front, README


def secao(md, titulo):
    m = re.search(r"^(#+)\s+%s\s*$" % re.escape(titulo), md, re.M)
    if not m:
        return None
    nivel = len(m.group(1))
    fim = re.compile(r"^#{1,%d}\s" % nivel, re.M).search(md, m.end())
    return md[m.end():fim.start() if fim else len(md)]


SHELL = re.compile(r"^\s*(\$\s*)?(git|bash|sh|zsh|python3?|/usr/bin/python3|cd|ln|cp|mv|mkdir|rm|curl|pip3?|brew|"
                   r"chmod|export|source|\.)\s")


class TestI3Textos(unittest.TestCase):
    def test_i3_skill_install_fina(self):
        p = os.path.join(PROJETO, ".claude", "skills", "install", "SKILL.md")
        self.assertTrue(os.path.isfile(p), "falta .claude/skills/install/SKILL.md")
        s = ler(p)
        self.assertTrue(s.startswith("---\nname: install\n"), "frontmatter deve começar com name: install")
        self.assertRegex(s.split("---")[1], r"\ndescription: \S")
        self.assertIn(".claude/tools/instalar.sh", s)
        self.assertLessEqual(len(s.splitlines()), 40, "skill não é fina (o script decide; a skill só chama)")

    def test_i3_close_front_manda_install_depois_do_commit(self):
        s = ler(os.path.join(PROJETO, ".claude", "skills", "close-front", "SKILL.md"))
        self.assertIn("/install", s)
        self.assertGreater(s.index("/install"), s.index("git commit"), "/install deve vir depois do commit")

    def test_i3_readme_primeira_vez_sem_terminal(self):
        sec = secao(ler(os.path.join(PROJETO, "README.md")), "Primeira vez numa máquina nova")
        self.assertIsNotNone(sec, "README sem a seção '## Primeira vez numa máquina nova'")
        self.assertNotIn("```", sec, "bloco de código = comando de terminal para o humano")
        for trecho in re.findall(r"`([^`]+)`", sec):
            if "frase definir" in trecho:
                continue   # a senha: o humano define no terminal dele quando uma aprovação pedir
            self.assertIsNone(SHELL.match(trecho), "comando de terminal na seção: `%s`" % trecho)
        for linha in sec.splitlines():
            if "frase definir" in linha:
                continue
            self.assertIsNone(re.match(r"^\s*\$\s", linha), linha)

    def test_i3_readme_primeira_vez_ordem(self):
        sec = secao(ler(os.path.join(PROJETO, "README.md")), "Primeira vez numa máquina nova")
        self.assertIsNotNone(sec)
        low = sec.lower()
        pos = 0
        for termo in ("clon", "abr", "/install", "/load-session"):   # cada passo depois do anterior
            self.assertIn(termo, low[pos:], "ordem esperada: clonar → abrir o Claude → /install → /load-session;"
                                            " falta '%s' depois do passo anterior" % termo)
            pos = low.index(termo, pos) + len(termo)
        self.assertIn("senha", low)


if __name__ == "__main__":
    unittest.main()
