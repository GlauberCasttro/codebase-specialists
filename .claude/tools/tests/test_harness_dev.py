"""Testes do harness de desenvolvimento (.claude/tools). Rodar nos 2 Pythons:
    cd <projeto>/.claude/tools && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
    (idem com /usr/bin/python3). Stdlib apenas; tudo em diretórios temporários — não toca o projeto vivo
    (exceto leituras: settings.json, ORIGEM.txt, `package.sh --dry-run`, `carimbo.sh --json`).
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings

warnings.simplefilter("ignore", ResourceWarning)
TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.dirname(os.path.dirname(TOOLS))
AC = os.path.join(TOOLS, "ac", "ac.py")
PY = sys.executable
# termos montados por partes: este arquivo é público e passa pelo guard-privacidade
CAM_USUARIO = "/" + "Users" + "/fulano" + "/proj"
TERMO = "segredo" + "-de-teste"


def run(args, stdin="", env=None, cwd=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith("CS_")}
    e.update(env or {})
    p = subprocess.run(args, input=stdin.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       env=e, cwd=cwd)
    return p.returncode, p.stdout.decode("utf-8"), p.stderr.decode("utf-8")


def decisao(out):
    if not out.strip():
        return "allow"
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"]


def git(cwd, *a):
    subprocess.run(["git", "-C", cwd, "-c", "user.email=t@t", "-c", "user.name=t"] + list(a), check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def escrever(base, rel, txt):
    p = os.path.join(base, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(txt)
    return p


class GuardEntrega(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.sk = os.path.join(self.tmp, "projeto")
        os.makedirs(os.path.join(self.sk, ".claude", "state"))
        os.makedirs(os.path.join(self.sk, "scripts"))
        self.env = {"CS_DEV_SKILL_DIR": self.sk}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def g(self, payload):
        raw = payload if isinstance(payload, str) else json.dumps(payload)
        code, out, err = run([PY, os.path.join(TOOLS, "guard-entrega.py")], raw, self.env)
        self.assertEqual(code, 0, err)
        return decisao(out), out

    def w(self, rel, tool="Write"):
        return self.g({"tool_name": tool, "tool_input": {"file_path": os.path.join(self.sk, rel)}})[0]

    def test_edit_em_produto_nega(self):
        d, out = self.g({"tool_name": "Edit", "tool_input": {"file_path": os.path.join(self.sk, "scripts", "x.py")}})
        self.assertEqual(d, "deny")
        self.assertIn("portao.sh", out)

    def test_harness_e_motor_embutido_negam(self):
        for rel in (".claude/CLAUDE.md", ".claude/tools/ac/ac.py", ".claude/tools/package.sh", "SKILL.md",
                    "README.md", ".gitignore"):
            self.assertEqual(self.w(rel), "deny", rel)

    def test_zonas_livres_permitem(self):
        for rel in (".claude/state/RESUME.md", ".claude/state/logs/sessoes.jsonl", "campanhas/iter17/oraculo/t.py",
                    "campanhas/README.md", "local/work/iter17/codebase-specialists/a.py", "local/notas.md",
                    "dist/codebase-specialists/README.md"):
            self.assertEqual(self.w(rel, "Edit"), "allow", rel)

    def test_prefixo_parecido_nao_libera(self):
        for rel in ("campanhas-x/a.py", "localx/a.py", ".claude/statex/a.md", "distrib/a.py"):
            self.assertEqual(self.w(rel), "deny", rel)

    def test_fora_do_projeto_permite(self):
        d, _ = self.g({"tool_name": "Write", "tool_input": {"file_path": os.path.join(self.tmp, "fora", "a.py")}})
        self.assertEqual(d, "allow")

    def test_caminho_relativo_resolve_pelo_cwd(self):
        d, _ = self.g({"tool_name": "Edit", "cwd": self.sk, "tool_input": {"file_path": "scripts/x.py"}})
        self.assertEqual(d, "deny")

    def test_escapar_por_dotdot_nega(self):
        p = os.path.join(self.sk, "local", "..", "scripts", "x.py")
        d, _ = self.g({"tool_name": "Edit", "tool_input": {"file_path": p}})
        self.assertEqual(d, "deny")

    def test_symlink_para_produto_nega(self):
        link = os.path.join(self.tmp, "atalho.py")
        alvo = os.path.join(self.sk, "scripts", "x.py")
        open(alvo, "w").close()
        os.symlink(alvo, link)
        d, _ = self.g({"tool_name": "Write", "tool_input": {"file_path": link}})
        self.assertEqual(d, "deny")

    def test_notebook_e_multiedit(self):
        d, _ = self.g({"tool_name": "NotebookEdit", "tool_input": {"notebook_path": os.path.join(self.sk, "n.ipynb")}})
        self.assertEqual(d, "deny")
        self.assertEqual(self.w("SKILL.md", "MultiEdit"), "deny")

    def test_payload_invalido_nega_com_motivo(self):
        d, out = self.g("{isto não é json")
        self.assertEqual(d, "deny")
        self.assertIn("payload inválido", out)

    def test_escrita_sem_caminho_nega(self):
        d, out = self.g({"tool_name": "Write", "tool_input": {}})
        self.assertEqual(d, "deny")
        self.assertIn("sem file_path", out)

    def test_outras_ferramentas_passam(self):
        d, _ = self.g({"tool_name": "Read", "tool_input": {"file_path": os.path.join(self.sk, "SKILL.md")}})
        self.assertEqual(d, "allow")


class GuardGit(unittest.TestCase):
    def g(self, cmd, raw=None):
        payload = raw if raw is not None else json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
        code, out, err = run(["sh", os.path.join(TOOLS, "guard-git.sh")], payload)
        self.assertEqual(code, 0, err)
        return decisao(out)

    def test_nega(self):
        for cmd in ("git reset --hard", "git -C ~/proj reset --hard HEAD~1", "/usr/bin/git reset --hard",
                    "git checkout -- scripts/x.py", "git checkout HEAD -- a b", "git restore scripts/x.py",
                    "git clean -fd", "git clean -xdf", "git clean --force", "git stash", "git stash push -m x",
                    "git push", "git push origin master", "git add -A", "git add --all", "git add .",
                    "git commit -am 'x'", "git commit -a -F m.txt", "cd x && git reset --hard",
                    "echo ok; git push", "sh -c 'git reset --hard'", "bash -lc \"cd a && git stash\"",
                    "FOO=1 git push", "env GIT_DIR=x git clean -f"):
            self.assertEqual(self.g(cmd), "deny", cmd)

    def test_permite(self):
        for cmd in ("git status", "git log --oneline -5", "git diff HEAD -- x", "git add scripts/a.py",
                    "git commit -F local/msg.txt", "git restore --staged a.py", "git stash list", "git clean -n",
                    "git archive HEAD:", "git merge-file -p a b c", "ls -la", "echo git push",
                    "grep -rn 'reset --hard' docs", "git checkout -b nova"):
            self.assertEqual(self.g(cmd), "allow", cmd)

    def test_payload_invalido(self):
        self.assertEqual(self.g(None, raw="nao-json git reset --hard"), "deny")
        self.assertEqual(self.g(None, raw="nao-json qualquer"), "allow")


class GuardPrivacidade(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.termos = escrever(self.tmp, "termos.txt", "# comentário\n%s\nre:proj[-_]?secreto\n" % TERMO)
        self.env = {"CS_TERMOS_PRIVADOS": self.termos, "CS_DEV_SKILL_DIR": os.path.join(self.tmp, "p")}
        os.makedirs(os.path.join(self.tmp, "p"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def gp(self, *args, env=None):
        e = dict(self.env)
        e.update(env or {})
        return run(["sh", os.path.join(TOOLS, "guard-privacidade.sh")] + list(args), env=e)

    def test_acha_termo_regex_nome_de_arquivo_e_caminho_generico(self):
        d = os.path.join(self.tmp, "p")
        escrever(d, "docs/a.md", "ok\nfala do %s aqui\n" % TERMO.upper())
        escrever(d, "docs/b.md", "o PROJ_SECRETO\n")
        escrever(d, "proj-secreto.txt", "nada\n")
        escrever(d, "docs/c.md", "veja %s/coisa\n" % CAM_USUARIO)
        code, out, _ = self.gp(d)
        self.assertEqual(code, 1)
        self.assertIn("PRIVADO docs/a.md:2", out)
        self.assertIn("PRIVADO docs/b.md:1", out)
        self.assertIn("proj-secreto.txt: (nome do arquivo)", out)
        self.assertIn("PRIVADO docs/c.md:1", out)

    def test_limpo_e_placeholders_passam(self):
        d = os.path.join(self.tmp, "p")
        escrever(d, "a.md", "exemplo /" "Users/x/.claude/skills e ~/proj e /home/user/x\nautor@users.noreply.github.com\n")
        code, out, err = self.gp(d)
        self.assertEqual(code, 0, out + err)

    def test_ignora_local_dist_e_git(self):
        d = os.path.join(self.tmp, "p")
        for rel in ("local/t.md", "dist/t.md", ".git/t.md"):
            escrever(d, rel, TERMO + "\n")
        code, out, _ = self.gp(d)
        self.assertEqual(code, 0, out)
        code, out, _ = self.gp(os.path.join(d, "dist"))
        self.assertEqual(code, 1, "dist/ passado explicitamente é varrido")

    def test_sem_arquivo_de_termos_avisa_e_usa_genericos(self):
        d = os.path.join(self.tmp, "p")
        escrever(d, "a.md", TERMO + "\n")
        code, out, err = self.gp(d, env={"CS_TERMOS_PRIVADOS": os.path.join(self.tmp, "nao-existe.txt")})
        self.assertEqual(code, 0)
        self.assertIn("AVISO", err)
        escrever(d, "b.md", "mail: fulano.tal@" + "gmail.com\n")
        code, out, _ = self.gp(d, env={"CS_TERMOS_PRIVADOS": os.path.join(self.tmp, "nao-existe.txt")})
        self.assertEqual(code, 1)
        self.assertIn("b.md:1", out)

    def test_msg_e_staged(self):
        msg = escrever(self.tmp, "msg.txt", "commit sobre %s\n" % TERMO)
        code, out, _ = self.gp("--msg", msg)
        self.assertEqual(code, 1)
        d = os.path.join(self.tmp, "p")
        git(d, "init", "-q")
        escrever(d, "ok.txt", "limpo\n")
        git(d, "add", "ok.txt")
        self.assertEqual(self.gp("--staged")[0], 0)
        escrever(d, "ruim.txt", TERMO + "\n")
        git(d, "add", "ruim.txt")
        code, out, _ = self.gp("--staged")
        self.assertEqual(code, 1)
        self.assertIn("ruim.txt:1", out)

    def test_termos_nunca_impressos(self):
        code, out, err = self.gp("--termos")
        self.assertEqual(code, 0)
        self.assertNotIn(TERMO, out + err)
        self.assertIn("padrões ativos", out)

    def test_pre_commit_e_instalador(self):
        d = os.path.join(self.tmp, "p")
        git(d, "init", "-q")
        code, out, _ = run(["sh", os.path.join(TOOLS, "instalar-hooks-git.sh"), "--dry-run"], cwd=d)
        self.assertEqual(code, 0)
        code, out, _ = run(["sh", os.path.join(TOOLS, "pre-commit.sh"), "--help"])
        self.assertEqual(code, 0)
        self.assertIn("commit-msg", out)


class PublicarRegras(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.d = os.path.join(self.tmp, "stage")
        self.regras = escrever(self.tmp, "regras.json5", """// regras de teste
{ renomear: [["docs/velho-%(t)s.md", "docs/novo.md"]],
  blocos: [["scripts/a.py", "CAMINHO = '%(c)s'", "CAMINHO = os.environ.get('X') or ''"],
           ["scripts/a.py", "linha que não existe", "x"]],
  gerais: [{de: "%(t)s", para: "termo-generico", i: true},
           {de: "proj(eto)?-real", para: "piloto", re: true, i: true, caso: true}], }
""" % {"t": TERMO, "c": CAM_USUARIO})
        self.termos = escrever(self.tmp, "termos.txt", TERMO + "\nprojeto-real\n")
        self.env = {"CS_TERMOS_PRIVADOS": self.termos}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def pr(self, *a, env=None):
        e = dict(self.env)
        e.update(env or {})
        return run([PY, os.path.join(TOOLS, "publicar_regras.py")] + list(a), env=e)

    def test_aplica_renomear_blocos_gerais_e_grep_vazio(self):
        escrever(self.d, "docs/velho-%s.md" % TERMO, "doc\n")
        escrever(self.d, "scripts/a.py", "CAMINHO = '%s'\n# %s e PROJETO-REAL e Projeto-real\n" % (CAM_USUARIO, TERMO))
        code, out, err = self.pr("aplicar", self.d, "--regras", self.regras)
        self.assertEqual(code, 0, out + err)
        self.assertTrue(os.path.isfile(os.path.join(self.d, "docs", "novo.md")))
        s = open(os.path.join(self.d, "scripts", "a.py"), encoding="utf-8").read()
        self.assertIn("os.environ.get('X')", s)
        self.assertIn("termo-generico e PILOTO e Piloto", s)
        self.assertIn("AVISO bloco não aplicado", out)
        code, out, _ = self.pr("aplicar", self.d, "--regras", self.regras)
        self.assertEqual(code, 0, "idempotente: segunda passada não acha nada privado")

    def test_grep_acusa_o_que_sobrou(self):
        escrever(self.d, "docs/x.md", "veja %s/coisa\n" % CAM_USUARIO)
        code, out, _ = self.pr("--grep", self.d)
        self.assertEqual(code, 1)
        self.assertIn("PRIVADO docs/x.md:1", out)

    def test_pacote_troca_internos_e_tira_link_quebrado(self):
        escrever(self.d, "docs/README.md", "| doc | o quê |\n|---|---|\n| [a.md](a.md) | ok |\n"
                 "| [PENDENTE.md](PENDENTE.md) | interno |\n\nver `campanhas/iter12/oraculo/ESPEC.md` e "
                 "PONTOS-DO-FOUNDER.md\n")
        escrever(self.d, "docs/a.md", "a\n")
        code, out, err = self.pr("aplicar", self.d, "--pacote", "--regras", self.regras)
        self.assertEqual(code, 0, out + err)
        s = open(os.path.join(self.d, "docs", "README.md"), encoding="utf-8").read()
        self.assertIn("[a.md](a.md)", s)
        self.assertNotIn("PENDENTE", s)
        self.assertIn("ESPEC interna da rodada iter12", s)
        self.assertNotIn("PONTOS-DO-FOUNDER", s)

    def test_pacote_reprova_referencia_interna_que_sobra(self):
        escrever(self.d, "docs/b.md", "ver docs/12-rodada-x.md\n")
        code, out, _ = self.pr("--grep", self.d, "--pacote")
        self.assertEqual(code, 1)
        self.assertIn("INTERNO docs/b.md:1", out)

    def test_sem_arquivo_de_regras_avisa(self):
        escrever(self.d, "a.md", "limpo\n")
        code, out, err = self.pr("aplicar", self.d, env={"CS_REGRAS_PRIVADAS": os.path.join(self.tmp, "nada.json5")})
        self.assertEqual(code, 0)
        self.assertIn("AVISO", err)
        code, out, _ = self.pr("--check-regras", env={"CS_REGRAS_PRIVADAS": os.path.join(self.tmp, "nada.json5")})
        self.assertEqual(code, 1)
        self.assertIn("AUSENTES", out)

    def test_codigo_nao_contem_texto_privado(self):
        """O mecanismo não carrega pares privados: só listas de pacote (documentos internos, não privados)."""
        s = open(os.path.join(TOOLS, "publicar_regras.py"), encoding="utf-8").read()
        self.assertNotIn("BLOCOS = [", s)
        self.assertIn("regras-privadas.json5", s)


class FluxoEntrega(unittest.TestCase):
    """copia.sh → (edição na cópia) → portao.sh → portar.sh → conferir-commit.sh num repo git temporário, nos 2
    layouts: projeto = raiz do repo (o caso real) e skill como subpasta (prefixo)."""

    layout_raiz = True

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.repo = os.path.join(self.tmp, "repo")
        self.sk = self.repo if self.layout_raiz else os.path.join(self.repo, "sk")
        self.ws = os.path.join(self.sk, "local")
        os.makedirs(self.sk)
        git(self.repo, "init", "-q")
        escrever(self.sk, "a.py", "def um():\n    return 1\n\n\ndef dois():\n    return 2\n")
        escrever(self.sk, "VERSION", "0.0.1\n")
        escrever(self.sk, ".gitignore", "local/\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "base")
        self.env = {"CS_DEV_SKILL_DIR": self.sk}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def t(self, nome, *args):
        return run(["bash", os.path.join(TOOLS, nome)] + list(args), env=self.env)

    def copia_editada(self, novo):
        code, out, err = self.t("copia.sh", "f1")
        self.assertEqual(code, 0, out + err)
        w = os.path.join(self.ws, "work", "f1", "codebase-specialists", "a.py")
        self.assertTrue(os.path.isfile(w), out)
        with open(w, "w") as fh:
            fh.write(novo)
        return w

    def test_copia_recusa_sobrescrever(self):
        self.copia_editada("def um():\n    return 1\n\n\ndef dois():\n    return 22\n")
        code, out, _ = self.t("copia.sh", "f1")
        self.assertEqual(code, 1)
        self.assertIn("já existe", out)

    def test_fluxo_verde_e_conferencia(self):
        self.copia_editada("def um():\n    return 1\n\n\ndef dois():\n    return 22\n")
        code, out, err = self.t("portao.sh", "f1", "--pythons", PY, "--", "a.py")
        self.assertEqual(code, 0, out + err)
        po = open(os.path.join(self.ws, "portao-f1", "portao.out")).read()
        self.assertTrue(po.rstrip().endswith("RESULTADO: VERDE\nFIM"), po)
        code, out, _ = self.t("conferir-commit.sh", "f1", "--", "a.py")
        self.assertEqual(code, 1, "antes de portar o vivo difere do portão")
        self.assertIn("DIFERE: a.py", out)
        code, out, err = self.t("portar.sh", "f1", "--", "a.py")
        self.assertEqual(code, 0, out + err)
        self.assertIn("COPIA: a.py", out)
        code, out, _ = self.t("conferir-commit.sh", "f1", "--", "a.py")
        self.assertEqual(code, 0, out)

    def test_portao_acusa_def_removido(self):
        self.copia_editada("def um():\n    return 1\n")
        code, out, _ = self.t("portao.sh", "f1", "--pythons", PY, "--", "a.py")
        self.assertNotEqual(code, 0)
        po = open(os.path.join(self.ws, "portao-f1", "portao.out")).read()
        self.assertIn("REMOVIDA a.py: def dois", po)
        self.assertIn("RESULTADO: VERMELHO", po)

    def test_portao_roda_oraculo_relativo_ao_projeto(self):
        self.copia_editada("def um():\n    return 1\n\n\ndef dois():\n    return 22\n")
        escrever(self.sk, "campanhas/f1/oraculo/test_o.py",
                 "import os, sys, unittest\nsys.path.insert(0, os.environ['CS_SKILL_DIR'])\nimport a\n\n\n"
                 "class T(unittest.TestCase):\n    def test_dois(self):\n        self.assertEqual(a.dois(), 22)\n")
        code, out, err = self.t("portao.sh", "f1", "--pythons", PY, "--oraculo", "campanhas/f1/oraculo:test_o",
                                "--", "a.py")
        self.assertEqual(code, 0, out + err)
        po = open(os.path.join(self.ws, "portao-f1", "portao.out")).read()
        self.assertIn("ORACULO test_o: Ran 1 test", po)

    def test_portar_merge_3_vias_e_conflito(self):
        self.copia_editada("def um():\n    return 1\n\n\ndef dois():\n    return 22\n")
        vivo = os.path.join(self.sk, "a.py")
        with open(vivo, "w") as fh:   # outra sessão mexeu em outra região
            fh.write("def um():\n    return 11\n\n\ndef dois():\n    return 2\n")
        code, out, err = self.t("portar.sh", "f1", "--", "a.py")
        self.assertEqual(code, 0, out + err)
        self.assertIn("MERGE 3 vias limpo", out)
        self.assertEqual(open(vivo).read(), "def um():\n    return 11\n\n\ndef dois():\n    return 22\n")
        with open(vivo, "w") as fh:   # agora conflita na mesma linha
            fh.write("def um():\n    return 11\n\n\ndef dois():\n    return 99\n")
        antes = open(vivo).read()
        code, out, _ = self.t("portar.sh", "f1", "--", "a.py")
        self.assertEqual(code, 1)
        self.assertIn("CONFLITO", out)
        self.assertEqual(open(vivo).read(), antes, "em conflito não escreve")

    def test_dry_run_nao_escreve(self):
        self.copia_editada("def um():\n    return 1\n\n\ndef dois():\n    return 22\n")
        vivo = os.path.join(self.sk, "a.py")
        antes = open(vivo).read()
        code, out, _ = self.t("portar.sh", "f1", "--dry-run", "--", "a.py")
        self.assertEqual(code, 0)
        self.assertEqual(open(vivo).read(), antes)


class FluxoEntregaSkillEmSubpasta(FluxoEntrega):
    layout_raiz = False


class MotorEmbutido(unittest.TestCase):
    def test_help_e_init_com_ciclo_embutido(self):
        code, out, _ = run([PY, AC, "--help"])
        self.assertEqual(code, 0)
        self.assertIn("overlap", out)
        tmp = os.path.realpath(tempfile.mkdtemp())
        try:
            git(tmp, "init", "-q")
            code, out, err = run([PY, AC, "--work", "campanhas/x", "init", "--target", ".", "--scope", "a/*",
                                  "--problem", "p", "--stop", "s"], cwd=tmp)
            self.assertEqual(code, 0, out + err)
            code, out, err = run([PY, AC, "--work", "campanhas/x", "status"], cwd=tmp)
            self.assertEqual(code, 0, err)
            self.assertIn("etapa: intake", out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_hook_aprovacao_selftest(self):
        code, out, err = run([PY, os.path.join(TOOLS, "ac", "hook_aprovacao.py"), "--selftest"])
        self.assertEqual(code, 0, out + err)

    def test_origem_confere_sha256(self):
        txt = open(os.path.join(TOOLS, "ac", "ORIGEM.txt"), encoding="utf-8").read()
        emb = txt.split("sha256 EMBUTIDO")[1]
        linhas = re.findall(r"^\s+([0-9a-f]{64})\s+(\S+)$", emb, re.M)
        self.assertEqual(len(linhas), 7)
        for sha, rel in linhas:
            with open(os.path.join(TOOLS, "ac", rel), "rb") as fh:
                self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), sha, rel)


class ScriptAprovacao(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        git(self.tmp, "init", "-q")
        self.env = {"CS_DEV_SKILL_DIR": self.tmp}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def sa(self, *a):
        return run(["bash", os.path.join(TOOLS, "script-aprovacao.sh")] + list(a), env=self.env)

    def test_sem_campanha_recusa(self):
        code, out, err = self.sa("f1")
        self.assertNotEqual(code, 0)
        self.assertIn("new-front", err)

    def test_gera_em_local_com_motor_embutido(self):
        code, out, err = run([PY, AC, "--work", "campanhas/f1", "init", "--target", ".", "--scope", "a/*",
                              "--problem", "p", "--stop", "s"], cwd=self.tmp)
        self.assertEqual(code, 0, out + err)
        code, out, err = self.sa("f1", "--por", "Ana", "--dry-run")
        self.assertEqual(code, 0, err)
        for trecho in ("gate stop", "gate oracle:requisito", "preauth commit", "--requires integracao.1 integracao.2",
                       "'Ana'", AC, os.path.join(self.tmp, "campanhas", "f1")):
            self.assertIn(trecho, out)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "local")), "dry-run não grava")
        code, out, err = self.sa("f1", "--por", "Ana")
        self.assertEqual(code, 0, err)
        gerado = os.path.join(self.tmp, "local", "aprovar-f1.sh")
        self.assertTrue(os.access(gerado, os.X_OK))
        self.assertEqual(run(["sh", "-n", gerado])[0], 0, "script gerado tem sintaxe válida")


class Package(unittest.TestCase):
    def test_dry_run_lista_inclusao(self):
        code, out, err = run(["bash", os.path.join(TOOLS, "package.sh"), "--dry-run", "--worktree"])
        self.assertEqual(code, 0, out + err)
        entra = out.split("ENTRA")[1].split("FICA DE FORA")[0]
        fora = out.split("FICA DE FORA")[1]
        for d in ("SKILL.md", "scripts/harness/", "assets/templates/", "references/", "docs/fases/"):
            self.assertIn(d, entra)
        for d in (".claude/", "campanhas/", "evals/", "local/", "PONTOS", "ROADMAP"):
            self.assertNotIn(d, entra, d)
        self.assertIsNone(re.search(r"(^|[\s/])tests/", entra), "nenhum tests/ entra no pacote")
        for d in (".claude/", "campanhas/", "evals/", "scripts/*/tests/"):
            self.assertIn(d, fora, d)
        self.assertIn("nada escrito", out)

    def test_validador_acusa_vazamento(self):
        sys.path.insert(0, TOOLS)
        try:
            import package_validar as pv
        finally:
            sys.path.remove(TOOLS)
        tmp = tempfile.mkdtemp()
        try:
            for rel in ("SKILL.md", "scripts/a.py", "scripts/x/tests/t.py", ".claude/s.json", "evals/e.json",
                        "campanhas/i/o.py", "local/n.md", "scripts/b.pyc"):
                escrever(tmp, rel, "x")
            v = pv.vazamentos(tmp)
            self.assertEqual(sorted(v), sorted(["scripts/x/tests", "scripts/x/tests/t.py", ".claude",
                                                ".claude/s.json", "evals", "evals/e.json", "campanhas",
                                                "campanhas/i", "campanhas/i/o.py", "local", "local/n.md",
                                                "scripts/b.pyc"]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class AjudaETools(unittest.TestCase):
    def test_todos_os_tools_tem_help(self):
        for nome in ("carimbo.sh", "copia.sh", "portao.sh", "conferir-commit.sh", "portar.sh", "package.sh",
                     "guard-git.sh", "guard-privacidade.sh", "script-aprovacao.sh", "pre-commit.sh",
                     "instalar-hooks-git.sh"):
            code, out, err = run(["bash", os.path.join(TOOLS, nome), "--help"])
            self.assertEqual(code, 0, nome + err)
            self.assertTrue(out.strip(), nome)
        for nome in ("publicar_regras.py", "guard_privacidade.py", "guard-entrega.py", "package_validar.py",
                     "guard_git.py"):
            code, out, _ = run([PY, os.path.join(TOOLS, nome), "--help"])
            self.assertEqual(code, 0, nome)

    def test_carimbo_json_do_projeto(self):
        code, out, err = run(["bash", os.path.join(TOOLS, "carimbo.sh"), "--json"])
        self.assertEqual(code, 0, err)
        d = json.loads(out)
        with open(os.path.join(SKILL, "VERSION")) as fh:
            self.assertEqual(d["version"], fh.read().strip())
        self.assertIsInstance(d["campanhas_ativas"], list)

    def test_carimbo_lista_campanha_ativa(self):
        tmp = os.path.realpath(tempfile.mkdtemp())
        try:
            git(tmp, "init", "-q")
            escrever(tmp, "VERSION", "1.2.3\n")
            git(tmp, "add", "VERSION")
            git(tmp, "commit", "-qm", "v")
            run([PY, AC, "--work", "campanhas/iter99", "init", "--target", ".", "--scope", "a/*", "--problem", "p",
                 "--stop", "s"], cwd=tmp)
            code, out, err = run(["bash", os.path.join(TOOLS, "carimbo.sh")], env={"CS_DEV_SKILL_DIR": tmp})
            self.assertEqual(code, 0, err)
            self.assertIn("VERSION viva 1.2.3 (HEAD: 1.2.3)", out)
            self.assertIn("iter99: etapa intake", out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_settings_aponta_para_tools_existentes(self):
        with open(os.path.join(SKILL, ".claude", "settings.json")) as fh:
            s = json.load(fh)
        cmds = [h["command"] for ev in s["hooks"].values() for m in ev for h in m["hooks"]]
        for rel in ("guard-git.sh", "guard-entrega.py", "carimbo.sh", "ac/hook_aprovacao.py"):
            self.assertTrue(any(".claude/tools/" + rel in c for c in cmds), rel)
            self.assertTrue(os.path.isfile(os.path.join(TOOLS, rel)), rel)

    def test_skills_do_harness(self):
        nomes = sorted(os.listdir(os.path.join(SKILL, ".claude", "skills")))
        self.assertEqual(nomes, ["close-front", "install", "load-session", "new-front", "package", "save-session"])
        for n in nomes:
            s = open(os.path.join(SKILL, ".claude", "skills", n, "SKILL.md"), encoding="utf-8").read()
            self.assertTrue(s.startswith("---\nname: %s\n" % n), n)
        for n in ("new-front", "close-front", "load-session"):
            s = open(os.path.join(SKILL, ".claude", "skills", n, "SKILL.md"), encoding="utf-8").read()
            self.assertIn("python3 .claude/tools/ac/ac.py", s, n)
            self.assertNotIn("skills/auto-correcao", s, n)

    def test_nomes_antigos_de_skill_ausentes(self):
        # nomes antigos em português, montados por partes para este próprio teste não os conter
        proibidos = ["salvar" + "-sessao", "carregar" + "-sessao", "planejar" + "-sprint", "new" + "-epico",
                     "close" + "-epico", "/corri" + "gir"]
        base = os.path.join(SKILL, ".claude")
        for d, dirs, files in os.walk(base):
            dirs[:] = [x for x in dirs if x != "__pycache__"]
            for f in files:
                p = os.path.join(d, f)
                try:
                    s = open(p, encoding="utf-8").read()
                except (UnicodeDecodeError, OSError):
                    continue
                for n in proibidos:
                    self.assertNotIn(n, s, "%s cita nome antigo de skill" % p)


if __name__ == "__main__":
    unittest.main()
