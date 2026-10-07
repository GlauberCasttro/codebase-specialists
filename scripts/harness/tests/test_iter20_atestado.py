"""iter20 (B-13, 0.10.1) — atestado do que a ferramenta escreveu, lido pelo pre-commit (`check-diff --staged`).

Cobre o que o oráculo deixa para a revisão: o atestado não se forja com edição simples (âncora no ledger), não
libera caminho que a ferramenta não gera nem estado, não abençoa edição humana em arquivo mesclado, a remoção à mão
é vista com o próprio nome (sem "rename" para o backup) e o que o HEAD já tem sai do atestado (consumido)."""
import json
import os
import shutil
import subprocess
import unittest

import fixture
import attest
import hcore
import install

GUARD = os.path.join(fixture.ENGINE, "guard.py")
ENGINE_FILE = ".swarm/harness/guard.py"


def check_diff(root, staged=True):
    argv = ["python3", GUARD, "check-diff", "--root", root] + (["--staged"] if staged else [])
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    e.pop("CLAUDE_PROJECT_DIR", None)
    p = subprocess.run(argv, cwd=root, env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    return p.returncode, p.stdout.decode() + p.stderr.decode()


def append(root, rel, txt):
    with open(os.path.join(root, rel), "a", encoding="utf-8") as f:
        f.write(txt)


class Base(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo(with_state=False)
        self.addCleanup(fixture.rm, self.root)
        res = install.install(self.root, allow_outside=True)
        self.assertIsNone(res.get("attest_problem"))

    def commit(self):
        fixture.git(self.root, "add", "-A")
        fixture.git(self.root, "commit", "-q", "--no-verify", "-m", "x")


class TestInstalacaoLiberada(Base):
    def test_resultado_do_install_passa(self):
        fixture.git(self.root, "add", "-A")
        code, out = check_diff(self.root)
        self.assertEqual(code, 0, out)

    def test_motor_editado_a_mao_barra(self):
        append(self.root, ENGINE_FILE, "# à mão\n")
        fixture.git(self.root, "add", "-A")
        code, out = check_diff(self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("FORA: %s (área protegida)" % ENGINE_FILE, out)

    def test_gitignore_do_motor_ignora_pycache(self):
        rel = ".swarm/harness/__pycache__/x.cpython-39.pyc"
        p = subprocess.run(["git", "check-ignore", "-v", rel], cwd=self.root, stdout=subprocess.PIPE)
        self.assertEqual(p.returncode, 0)
        self.assertTrue(p.stdout.decode().startswith(".swarm/harness/.gitignore:"), p.stdout.decode())


class TestForja(Base):
    def test_atestado_editado_sem_ledger_e_ignorado(self):
        self.commit()
        append(self.root, ENGINE_FILE, "# à mão\n")
        with open(os.path.join(self.root, ENGINE_FILE), "rb") as f:
            sha = hcore.sha256_bytes(f.read())
        p = attest.attest_path(self.root)
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        data["files"][ENGINE_FILE] = {"sha256": sha, "by": "harness install", "version": "x"}
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f)
        fixture.git(self.root, "add", "--", ENGINE_FILE)
        code, out = check_diff(self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("FORA: %s " % ENGINE_FILE, out)
        self.assertIn("atestado ignorado", out)

    def test_atestado_fora_da_arvore_versionada(self):
        p = attest.attest_path(self.root)
        self.assertTrue(p.startswith(os.path.join(os.path.realpath(self.root), ".git") + os.sep), p)

    def test_caminho_que_a_ferramenta_nao_gera_nunca_e_liberado(self):
        rel = "src/users/model.py"
        attest.record(self.root, {rel: b"AGE = 1\n"}, "forja")
        fixture.write(self.root, rel, "AGE = 1\n")
        fixture.git(self.root, "add", "--", rel)
        code, out = check_diff(self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("FORA: %s " % rel, out)

    def test_estado_nunca_e_atestavel(self):
        for rel in (".swarm/state/x.json5", ".swarm/backlog/a.md", ".swarm/archive/b.md", ".swarm/events.jsonl",
                    ".swarm/INDEX.md", ".swarm/.engine/projection.json5", ".swarm/memory/m.md"):
            self.assertFalse(attest.attestable(rel), rel)
        for rel in (ENGINE_FILE, ".claude/agents/a.md", "CLAUDE.md", "src/AGENTS.md", "Makefile"):
            self.assertTrue(attest.attestable(rel), rel)
        self.assertFalse(attest.attestable("src/users/model.py"))


class TestMescladoNaoAbencoaEdicaoHumana(Base):
    def test_makefile_editado_antes_do_install_continua_barrado(self):
        self.commit()
        append(self.root, "Makefile", "\nminha-regra:\n\t@echo oi\n")
        install.install(self.root, allow_outside=True)  # bloco intacto: o install não muda o Makefile
        fixture.git(self.root, "add", "--", "Makefile")
        code, out = check_diff(self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("FORA: Makefile ", out)


class TestRemocao(Base):
    def test_remocao_a_mao_com_copia_identica_no_backup_barra_citando_o_arquivo(self):
        self.commit()
        bk = os.path.join(self.root, ".swarm/backups/upgrade-x/harness")
        os.makedirs(bk)
        shutil.copy2(os.path.join(self.root, ".swarm/harness/views.py"), os.path.join(bk, "views.py"))
        os.remove(os.path.join(self.root, ".swarm/harness/views.py"))
        fixture.git(self.root, "add", "-A")
        code, out = check_diff(self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("FORA: .swarm/harness/views.py ", out)

    def test_remocao_atestada_libera(self):
        rel = ".claude/agents/velho.md"
        fixture.write(self.root, rel, "gerado\n")
        self.commit()
        os.remove(os.path.join(self.root, rel))
        attest.record(self.root, {rel: None}, "emit")
        fixture.git(self.root, "add", "-A")
        code, out = check_diff(self.root)
        self.assertEqual(code, 0, out)


class TestConsumido(Base):
    def test_o_que_o_head_ja_tem_sai_do_atestado(self):
        self.commit()
        n, prob = attest.record(self.root, {}, "teste")
        self.assertIsNone(prob)
        self.assertEqual(n, 0)
        files, prob = attest.load(self.root)
        self.assertIsNone(prob)
        self.assertEqual(files, {})

    def test_pasta_dentro_de_outro_repositorio_nao_e_alvo(self):
        sub = os.path.join(self.root, "src")
        self.assertIsNone(attest.git_dir(sub))
        self.assertEqual(attest.record(sub, {".claude/x.md": b"x"}, "teste"), (0, None))


if __name__ == "__main__":
    unittest.main()
