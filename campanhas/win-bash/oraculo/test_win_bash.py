"""Oráculo da feature win-bash — escolha do bash no fechamento (feature.bash_exe / feature.conferir_commit).

Contrato (fixado pelo tech-lead):
- feature.bash_exe() -> str (caminho do bash ou "bash"); falha = levanta feature.Recusa com mensagem que cita "Git Bash".
- feature.conferir_commit(fid, arqs, r) mantém o retorno (ok: bool, saida: str).

CA01..CA04 simulam a plataforma por mock (os.name, shutil.which, SystemRoot) com árvores falsas REAIS num
tempfile.mkdtemp() (arquivos .exe vazios), para não depender de como a correção testa existência.
CA05 é real (sem mock da plataforma): roda o conferir-commit.sh pelo bash que a correção escolher.

Raiz: ORACULO_SKILL, senão CS_SKILL_DIR, senão 3 níveis acima deste arquivo. Filtro: -k CA0N.
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True

RAIZ = os.path.abspath(
    os.environ.get("ORACULO_SKILL")
    or os.environ.get("CS_SKILL_DIR")
    or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
)
TOOLS = os.path.join(RAIZ, ".claude", "tools")
WINDOWS_REAL = os.sep == "\\"  # os.path é ntpath: dá para usar caminhos literais do Windows

_FEATURE = None
_ERRO_IMPORT = None


def _carregar():
    global _FEATURE, _ERRO_IMPORT
    if _FEATURE is not None or _ERRO_IMPORT is not None:
        return _FEATURE
    try:
        if TOOLS not in sys.path:
            sys.path.insert(0, TOOLS)
        spec = importlib.util.spec_from_file_location("feature", os.path.join(TOOLS, "feature.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _FEATURE = mod
    except Exception as e:  # pragma: no cover - só se o feature.py não importar
        _ERRO_IMPORT = "%s: %s" % (type(e).__name__, e)
    return _FEATURE


def _norm(p):
    return os.path.normcase(os.path.normpath(p))


def _tocar(*partes):
    p = os.path.join(*partes)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb"):
        pass
    return p


class _Base(unittest.TestCase):
    """Árvore falsa: <tmp>/Windows (SystemRoot), <tmp>/WINDOWS/system32/bash.exe (o WSL, caixa diferente),
    <tmp>/Git (raiz do Git: cmd/git.exe, mingw64/bin/git.exe, bin/bash.exe, usr/bin/bash.exe conforme o teste)."""

    def setUp(self):
        self.f = _carregar()
        if self.f is None:
            self.fail("não importou %s: %s" % (os.path.join(TOOLS, "feature.py"), _ERRO_IMPORT))
        self.tmp = tempfile.mkdtemp(prefix="oraculo-win-bash-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.sysroot = os.path.join(self.tmp, "Windows")
        os.makedirs(self.sysroot, exist_ok=True)
        # Mesmo diretório que SystemRoot\System32, escrito com outra caixa (no Linux são pastas distintas no disco,
        # mas a regra é comparar sem diferenciar caixa; no Windows é a mesma pasta).
        self.wsl = _tocar(self.tmp, "WINDOWS", "system32", "bash.exe")
        self.git_raiz = os.path.join(self.tmp, "Git")

    def exige_bash_exe(self):
        fn = getattr(self.f, "bash_exe", None)
        if not callable(fn):
            self.fail("feature.bash_exe() não existe em %s (contrato: bash_exe() -> str; falha = feature.Recusa)"
                      % os.path.join(TOOLS, "feature.py"))
        return fn

    def rodar(self, nome_os, bash=None, git=None, env=None, sem_sysroot=False):
        """Roda feature.bash_exe() com os.name, shutil.which e SystemRoot simulados.
        Devolve (resultado | None, Recusa | None, chamadas de which)."""
        fn = self.exige_bash_exe()
        mapa = {"bash": bash, "git": git}
        chamadas = []

        def which(cmd, *a, **k):
            chamadas.append(cmd)
            chave = os.path.basename(str(cmd)).lower()
            if chave.endswith(".exe"):
                chave = chave[:-4]
            return mapa.get(chave)

        # No Windows as chaves do ambiente não diferenciam caixa; no Linux sim: as duas grafias, mesmo valor.
        novo_env = {"SystemRoot": self.sysroot, "SYSTEMROOT": self.sysroot} if env is None else env
        with mock.patch.dict(self.f.os.environ, novo_env):
            if sem_sysroot:
                for k in ("SystemRoot", "SYSTEMROOT", "systemroot"):
                    self.f.os.environ.pop(k, None)
            with mock.patch.object(self.f.shutil, "which", side_effect=which), \
                    mock.patch.object(self.f.os, "name", nome_os):
                try:
                    return fn(), None, chamadas
                except self.f.Recusa as e:
                    return None, e, chamadas

    def assertMesmoCaminho(self, obtido, esperado, msg=None):
        self.assertIsInstance(obtido, str, msg)
        self.assertEqual(_norm(obtido), _norm(esperado), msg)

    def assertNaoWsl(self, res, *wsls):
        if res is None:
            return
        for w in wsls:
            self.assertNotEqual(_norm(res), _norm(w), "devolveu o bash do WSL (System32): %s" % res)
        self.assertNotIn("system32", res.lower(), "devolveu um bash dentro do System32: %s" % res)


class CA01BashForaDoSystem32(_Base):
    """CA-01: no Windows, o bash do PATH fora do System32 é devolvido; dentro do System32, descartado."""

    def test_bash_do_path_fora_do_system32_e_devolvido(self):
        fora = _tocar(self.git_raiz, "usr", "bin", "bash.exe")
        res, rec, _ = self.rodar("nt", bash=fora, git=None)
        self.assertIsNone(rec, "recusou com bash utilizável no PATH: %s" % rec)
        self.assertMesmoCaminho(res, fora, "deveria devolver o bash do PATH fora do System32")

    def test_bash_do_system32_com_outra_caixa_e_descartado(self):
        # SystemRoot = <tmp>\Windows; which devolve <tmp>\WINDOWS\system32\bash.exe (o WSL, caixa diferente).
        # Com o Git disponível, a escolha tem de cair no bash do Git, não no do System32.
        git = _tocar(self.git_raiz, "cmd", "git.exe")
        esperado = _tocar(self.git_raiz, "bin", "bash.exe")
        res, rec, _ = self.rodar("nt", bash=self.wsl, git=git)
        self.assertIsNone(rec, "recusou havendo bash do Git: %s" % rec)
        self.assertNaoWsl(res, self.wsl)
        self.assertMesmoCaminho(res, esperado, "o bash do System32 deveria ser descartado em favor do bash do Git")

    def test_bash_do_system32_sem_git_nao_e_devolvido(self):
        res, rec, _ = self.rodar("nt", bash=self.wsl, git=None)
        self.assertNaoWsl(res, self.wsl)
        self.assertIsNotNone(rec, "sem bash fora do System32 e sem Git deveria recusar; devolveu %r" % (res,))

    @unittest.skipUnless(WINDOWS_REAL, "caminho literal do Windows: só com os.path = ntpath")
    def test_literal_windows_system32_maiusculo_descartado(self):
        wsl = r"C:\WINDOWS\system32\bash.exe"
        git = _tocar(self.git_raiz, "cmd", "git.exe")
        esperado = _tocar(self.git_raiz, "bin", "bash.exe")
        res, rec, _ = self.rodar("nt", bash=wsl, git=git, env={"SystemRoot": r"C:\Windows", "SYSTEMROOT": r"C:\Windows"})
        self.assertIsNone(rec, "recusou havendo bash do Git: %s" % rec)
        self.assertNaoWsl(res, wsl)
        self.assertMesmoCaminho(res, esperado)

    @unittest.skipUnless(WINDOWS_REAL, "SystemRoot ausente => C:\\Windows: só com os.path = ntpath")
    def test_sem_systemroot_usa_c_windows(self):
        wsl = r"C:\Windows\System32\bash.exe"
        res, rec, _ = self.rodar("nt", bash=wsl, git=None, env={}, sem_sysroot=True)
        self.assertNaoWsl(res, wsl)
        self.assertIsNotNone(rec, "SystemRoot ausente: C:\\Windows\\System32\\bash.exe deveria ser descartado")


class CA02BashDoGitQuandoPathSoTemWsl(_Base):
    """CA-02: PATH só com o WSL (ou sem bash) + git em <raiz>\\cmd ou <raiz>\\mingw64\\bin => bash do Git."""

    def _caso(self, git_rel, bash_rels, esperado_rel, bash_path):
        git = _tocar(self.git_raiz, *git_rel)
        for b in bash_rels:
            _tocar(self.git_raiz, *b)
        res, rec, _ = self.rodar("nt", bash=bash_path, git=git)
        self.assertIsNone(rec, "recusou com %s existente: %s" % (os.path.join(*esperado_rel), rec))
        self.assertNaoWsl(res, self.wsl)
        self.assertMesmoCaminho(res, os.path.join(self.git_raiz, *esperado_rel))

    def test_git_em_cmd_bash_em_bin(self):
        self._caso(("cmd", "git.exe"), [("bin", "bash.exe")], ("bin", "bash.exe"), self.wsl)

    def test_git_em_mingw64_bin_bash_em_bin(self):
        self._caso(("mingw64", "bin", "git.exe"), [("bin", "bash.exe")], ("bin", "bash.exe"), self.wsl)

    def test_git_em_cmd_so_usr_bin(self):
        self._caso(("cmd", "git.exe"), [("usr", "bin", "bash.exe")], ("usr", "bin", "bash.exe"), self.wsl)

    def test_git_em_mingw64_bin_so_usr_bin(self):
        self._caso(("mingw64", "bin", "git.exe"), [("usr", "bin", "bash.exe")], ("usr", "bin", "bash.exe"),
                   self.wsl)

    def test_bin_tem_precedencia_sobre_usr_bin(self):
        self._caso(("cmd", "git.exe"), [("bin", "bash.exe"), ("usr", "bin", "bash.exe")], ("bin", "bash.exe"),
                   self.wsl)

    def test_sem_bash_nenhum_no_path(self):
        self._caso(("cmd", "git.exe"), [("bin", "bash.exe")], ("bin", "bash.exe"), None)

    def test_raiz_com_espaco(self):
        self.git_raiz = os.path.join(self.tmp, "Program Files", "Git")
        self._caso(("cmd", "git.exe"), [("usr", "bin", "bash.exe")], ("usr", "bin", "bash.exe"), self.wsl)


class CA03RecusaSemBashDoGit(_Base):
    """CA-03: sem bash fora do System32 e sem Git (utilizável) => feature.Recusa citando o Git Bash; nunca o WSL."""

    def _recusa(self, bash, git):
        res, rec, _ = self.rodar("nt", bash=bash, git=git)
        self.assertNaoWsl(res, self.wsl)
        self.assertIsNone(res, "deveria recusar; devolveu %r" % (res,))
        self.assertIsInstance(rec, self.f.Recusa)
        self.assertIn("git bash", str(rec).lower(), "a recusa deve citar o Git Bash: %r" % str(rec))

    def test_so_wsl_no_path_sem_git(self):
        self._recusa(self.wsl, None)

    def test_nada_no_path(self):
        self._recusa(None, None)

    def test_git_sem_bash_na_arvore(self):
        git = _tocar(self.git_raiz, "cmd", "git.exe")
        self._recusa(self.wsl, git)


class CA04ForaDoWindowsInalterado(_Base):
    """CA-04: os.name != "nt" => "bash", sem consultar git nem SystemRoot."""

    def test_posix_devolve_bash_sem_consultar_git(self):
        git = _tocar(self.git_raiz, "cmd", "git.exe")
        _tocar(self.git_raiz, "bin", "bash.exe")
        res, rec, chamadas = self.rodar("posix", bash="/usr/bin/bash", git=git)
        self.assertIsNone(rec, "fora do Windows não recusa: %s" % rec)
        self.assertEqual(res, "bash")
        self.assertNotIn("git", [os.path.basename(str(c)).lower().replace(".exe", "") for c in chamadas],
                         "fora do Windows não consulta which('git'): %r" % chamadas)

    def test_posix_nao_le_systemroot(self):
        fn = self.exige_bash_exe()
        lidas = []

        class Espiao(dict):
            def _anota(self, k):
                if str(k).lower() == "systemroot":
                    lidas.append(k)

            def __getitem__(self, k):
                self._anota(k)
                return dict.__getitem__(self, k)

            def get(self, k, d=None):
                self._anota(k)
                return dict.get(self, k, d)

            def __contains__(self, k):
                self._anota(k)
                return dict.__contains__(self, k)

        espiao = Espiao(dict(os.environ, SystemRoot=self.sysroot, SYSTEMROOT=self.sysroot))
        with mock.patch.object(self.f.os, "environ", espiao), \
                mock.patch.object(self.f.shutil, "which", return_value=None), \
                mock.patch.object(self.f.os, "name", "posix"):
            res = fn()
        self.assertEqual(res, "bash")
        self.assertEqual(lidas, [], "fora do Windows não consulta SystemRoot")


class CA05ConferirCommitRodaDeVerdade(unittest.TestCase):
    """CA-05: real, sem mock da plataforma. A saída é a do próprio conferir-commit.sh (portão ausente),
    nunca o erro de um bash que não acha o script (o WSL no Windows)."""

    FID = "feature-inexistente-win-bash"

    def test_portao_ausente_mensagem_do_proprio_script(self):
        f = _carregar()
        if f is None:
            self.fail("não importou %s: %s" % (os.path.join(TOOLS, "feature.py"), _ERRO_IMPORT))
        portao = os.path.join(RAIZ, "local", "portao-" + self.FID)
        self.assertFalse(os.path.exists(portao), "pré-condição: %s não pode existir" % portao)
        # isolamento: CS_DEV_WS do ambiente desviaria a área de trabalho do conferir-commit.sh
        with mock.patch.dict(os.environ, {}):
            os.environ.pop("CS_DEV_WS", None)
            r = f.conferir_commit(self.FID, ["x"], RAIZ)
        self.assertIsInstance(r, tuple)
        self.assertEqual(len(r), 2, "conferir_commit mantém o retorno (ok, saida)")
        ok, saida = r
        self.assertIs(ok, False, "portão ausente: ok deve ser False; saída: %r" % saida)
        self.assertNotIn("No such file or directory", saida,
                         "o bash não achou o conferir-commit.sh (bash do WSL?): %r" % saida)
        self.assertIn("portão da feature %s não existe" % self.FID, saida,
                      "a saída não é a do conferir-commit.sh: %r" % saida)


if __name__ == "__main__":
    unittest.main()
