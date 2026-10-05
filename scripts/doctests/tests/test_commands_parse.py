"""Todo comando `cs.py …` / `{CS} …` / `.swarm/bin/cs-…` citado na documentação existe na CLI real.

Fontes lidas: SKILL.md, MODO-DE-USO.md, references/*.json5, references/{ARCHITECTURE,harness,platforms,probes}.md, assets/templates/*.
Contra quem confere: o argparse REAL — `cs.build_parser()` (o mesmo de `python3 scripts/cs.py <sub> --help`)
e os parsers dos bins do harness (cs-state, cs-mem, cs-session, cs-route), capturados chamando o `main()` de
cada um com `parse_args` interceptado (nada é executado).

Por ocorrência confere: (1) cada subcomando do caminho existe; (2) posicional com `choices` recebe um valor
válido; (3) cada `--flag` existe no parser do nível em que aparece. Placeholders (`<x>`, `{x}`, `...`) e
valores entre aspas são ignorados. Prosa ("o cs.py grava …") não é comando: uma palavra desconhecida logo
depois de `cs.py` só reprova se estiver em código (entre crases ou num campo de comando) ou vier seguida de flag.

PENDENTES: comandos que a frente da CLI ainda está criando. Enquanto o parser real não os tiver, as
ocorrências são puladas com motivo (test_pendentes); quando passarem a existir, são conferidas como qualquer
outra. Remova a entrada da lista depois da integração.

Rodar: python3 -m unittest discover -s scripts/doctests/tests
"""
import argparse
import glob
import importlib.util
import os
import re
import sys
import unittest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILL = os.path.dirname(SCRIPTS)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

# (programa, caminho de subcomandos) → motivo. Pulado só enquanto o argparse real não tiver o caminho.
PENDENTES = {}
# (programa, caminho, flag) → motivo. Flag nova num subcomando que já existe; pulada só enquanto não existir.
PENDENTES_FLAGS = {}  # iteração 4: harness install --dry-run/--allow-outside já integrados (conferidos normalmente)

# Comandos do contrato da iteração 3 (PLANO-ITER3.json5 → contrato). Cada um tem de (1) ser citado na
# documentação e (2) parsear contra a CLI real — ou estar em PENDENTES/PENDENTES_FLAGS enquanto a frente_cli cria.
CONTRATO = {
    "init": ("cs.py", "init --platforms claude-code,cursor"),
    "fast": ("cs.py", "stage skip rt.1 --reason VAL"),
    "refino": ("cs.py", "probes generate --rotate --agent A"),
    "refino_check": ("cs.py", "probes check --all"),
    "exame_isolado": ("cs.py", "probes exam-pack A --out D"),
    "emit_dry": ("cs.py", "emit --dry-run"),
    "emit_fora": ("cs.py", "emit --allow-outside"),
    "aprovacao": ("cs.py", "approve --by X --decision GO --simulated"),
    "gap": ("cs.py", "interview record --id I --answer-unknown"),
    "harness": ("cs.py", "harness install --platforms claude-code,cursor --git-hook"),
    "verify": ("cs.py", "verify"),
    # iteração 4 (PLANO-ITER4.json5 → decisoes + frente_docs_scan_eval)
    "roster_simulado": ("cs.py", "team approve --by X --simulated"),
    "harness_dry": ("cs.py", "harness install --platforms claude-code --git-hook --dry-run"),
    "harness_fora": ("cs.py", "harness install --platforms claude-code --git-hook --allow-outside"),
    "exame_no_tmp": ("cs.py", "probes exam-pack A --out D"),
    "nao_especialista": ("cs.py", "probes check A --allow-non-specialist --reason VAL"),
}
# como cada comando do contrato aparece nos docs (regex sobre o texto inteiro dos docs)
CONTRATO_CITADO = {
    "init": r"init --platforms",
    "fast": r"stage skip",
    "refino": r"probes generate --rotate --agent",
    "refino_check": r"probes check --all",
    "exame_isolado": r"probes exam-pack \S+ --out",
    "emit_dry": r"emit --dry-run",
    "emit_fora": r"--allow-outside",
    "aprovacao": r"--simulated",
    "gap": r"--answer-unknown",
    "harness": r"harness install --platforms",
    "verify": r"cs\.py verify",
    "roster_simulado": r"team approve --by \S+ --simulated",
    "harness_dry": r"harness install [^\n`]*--dry-run",
    "harness_fora": r"harness install [^\n`]*--allow-outside",
    "exame_no_tmp": r"probes exam-pack \S+ --out <alvo>/\.swarm/tmp/exam/",
    "nao_especialista": r"probes check (<agente>|\{agente\}) --allow-non-specialist --reason",
}

BINS = {
    "cs-state": "harness/engine/state.py",
    "cs-mem": "memory/mem.py",
    "cs-session": "harness/engine/session.py",
    "cs-route": "harness/engine/router.py",
}
NO_ARGPARSE_BINS = {"cs-precommit"}  # script sh sem argumentos


class _Captured(Exception):
    def __init__(self, parser):
        Exception.__init__(self)
        self.parser = parser


def _capture(main):
    orig = argparse.ArgumentParser.parse_args

    def fake(self, *a, **k):
        raise _Captured(self)
    argparse.ArgumentParser.parse_args = fake
    try:
        main(["--help"])
    except _Captured as c:
        return c.parser
    finally:
        argparse.ArgumentParser.parse_args = orig
    raise AssertionError("main() não chamou parse_args")


def load_parsers():
    import cs
    parsers = {"cs.py": cs.build_parser()}
    for name, rel in BINS.items():
        full = os.path.join(SCRIPTS, rel)
        d = os.path.dirname(full)
        if d not in sys.path:
            sys.path.insert(0, d)
        spec = importlib.util.spec_from_file_location("doctest_" + name.replace("-", "_"), full)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        parsers[name] = _capture(mod.main)
    return parsers


# ------------------------------------------------------------------ fontes
def doc_files():
    out = [os.path.join(SKILL, "SKILL.md"), os.path.join(SKILL, "MODO-DE-USO.md")]  # iter9: o guia de uso também
    # .md de references desta frente (team-schema.md é da frente da CLI e fica de fora até integrar)
    out += [os.path.join(SKILL, "references", n) for n in ("ARCHITECTURE.md", "harness.md", "platforms.md", "probes.md")]
    out += sorted(glob.glob(os.path.join(SKILL, "references", "*.json5")))
    out += sorted(p for p in glob.glob(os.path.join(SKILL, "assets", "templates", "**", "*"), recursive=True)
                  if os.path.isfile(p))
    return out


def doc_texts(path):
    """[(rótulo, texto, é_código)] — json5: cada string do documento (campos de comando contam como código)."""
    rel = os.path.relpath(path, SKILL)
    if path.endswith(".json5"):
        from cslib import json5io
        data = json5io.load(path)
        out = []

        def walk(o, key, trail):
            if isinstance(o, str):
                # campo de comando = código ESTRITO: além de subcomando/flags, as opções obrigatórias têm de estar lá
                code = "strict" if key in ("comando", "check", "check_da_etapa", "antes", "depois", "cmd",
                                           "command") else False
                out.append(("%s:%s" % (rel, trail), o, code))
            elif isinstance(o, dict):
                for k, v in o.items():
                    walk(v, k, trail + "." + str(k))
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, key, "%s[%d]" % (trail, i))
        walk(data, None, "")
        # comentários // também citam comandos
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        for n, line in enumerate(raw.splitlines(), 1):
            if "//" in line:
                out.append(("%s:%d(comentário)" % (rel, n), line.split("//", 1)[1], False))
        return out
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    return [("%s:%d" % (rel, n), line, None) for n, line in enumerate(raw.splitlines(), 1)]


CMD_RE = re.compile(r"(?:(?<![\w/.-])(?:\S*/)?cs\.py|\{CS\}|(?<![\w-])(?:\.swarm/bin/)?(cs-(?:state|mem|session|route|precommit)))(?![\w-])")
CUT_RE = re.compile(r"`|\n| \| |\|| · | — | -> | → | && | ; |;$|\(|\)| # | ou | or |, | e depois|\. |\.$|: ")
PLACEHOLDER_RE = re.compile(r"^(<[^>]*>|\{[^}]*\}|\.\.\.|…|\$\w+|\$\$\w+|[A-Z_]+)$")


def occurrences(label, text, is_code):
    for m in CMD_RE.finditer(text):
        prog = m.group(1) or "cs.py"
        rest = text[m.end():]
        if prog == "cs.py" and m.group(0) == "{CS}":
            rest = rest  # {CS} já inclui --target
        # código? entre crases (nº ímpar de crases antes, na mesma linha) ou campo de comando do json5
        before = text[:m.start()].split("\n")[-1]
        in_code = is_code if is_code is not None else False
        if before.count("`") % 2 == 1 and not in_code:
            in_code = True
        # tira strings entre aspas (valores) e colchetes de opcional
        rest = re.sub(r'\\?"[^"\n]*\\?"', " VAL ", rest)
        rest = re.sub(r"'[^'\n]*'", " VAL ", rest)
        cut = CUT_RE.search(rest)
        seg = rest[:cut.start()] if cut else rest
        seg = seg.replace("[", " ").replace("]", " ")
        toks = [t for t in seg.split() if t]
        yield label, prog, toks, in_code, m.group(0) + " " + " ".join(toks)


def subparsers_of(p):
    for a in p._actions:
        if isinstance(a, argparse._SubParsersAction):
            return a
    return None


def option_strings(p):
    return {o for a in p._actions for o in a.option_strings}


def positionals_with_choices(p):
    return [a for a in p._actions if not a.option_strings and not isinstance(a, argparse._SubParsersAction)]


def check_occurrence(parsers, prog, toks, in_code):
    """→ (status, msg, path) com status ok|erro|prosa|pendente|sem-parser."""
    if prog in NO_ARGPARSE_BINS:
        ok = os.path.isfile(os.path.join(SCRIPTS, "harness", "templates", "bin", prog))
        return ("ok" if ok else "erro"), ("bin %s ausente em harness/templates/bin" % prog), ()
    parser = parsers[prog]
    path = []
    p = parser
    i = 0
    pos_idx = 0
    extra_ok = {"--target", "-h", "--help"} if prog == "cs.py" else {"-h", "--help"}
    first_word = True
    seen = set()
    while i < len(toks):
        t = toks[i]
        if t in ("VAL",) or PLACEHOLDER_RE.match(t):
            if first_word and not path:
                return "prosa", "placeholder de subcomando", ()
            i += 1
            pos_idx += 1
            continue
        if t.startswith("-"):
            flag = t.split("=", 1)[0].rstrip(".,:")
            if not re.match(r"^--?[A-Za-z][\w-]*$", flag):
                i += 1
                continue
            if flag not in option_strings(p) and flag not in extra_ok:
                if (prog, tuple(path), flag) in PENDENTES_FLAGS:
                    return "pendente", PENDENTES_FLAGS[(prog, tuple(path), flag)], tuple(path) + (flag,)
                return "erro", "flag %s não existe em `%s %s` (flags: %s)" % (
                    flag, prog, " ".join(path), " ".join(sorted(option_strings(p) - {"-h", "--help"}))), tuple(path)
            seen.add(flag)
            i += 1
            # pula o valor da flag (se a ação recebe valor)
            act = next((a for a in p._actions if flag in a.option_strings), None)
            if act is not None and act.nargs != 0 and i < len(toks) and not toks[i].startswith("-"):
                i += 1
            elif act is None and flag == "--target" and i < len(toks):
                i += 1
            continue
        word = t.rstrip(".,:")
        sp = subparsers_of(p)
        if sp is not None:
            if word in sp.choices:
                path.append(word)
                p = sp.choices[word]
                first_word = False
                pos_idx = 0
                i += 1
                continue
            key = (prog, tuple(path + [word]))
            if key in PENDENTES:
                return "pendente", PENDENTES[key], tuple(path + [word])
            if not re.match(r"^[a-z][a-z0-9-]*$", word):
                return ("prosa" if not path else "ok"), "", tuple(path)
            nxt_flag = i + 1 < len(toks) and toks[i + 1].startswith("--")
            if not path and not in_code and not nxt_flag:
                return "prosa", "", ()
            if path and not sp.required and not positionals_with_choices(p):
                return "ok", "", tuple(path)
            if path and not in_code and not nxt_flag and not sp.required:
                return "ok", "", tuple(path)
            return "erro", "subcomando `%s` não existe em `%s %s` (há: %s)" % (
                word, prog, " ".join(path), ", ".join(sorted(sp.choices))), tuple(path)
        pos = positionals_with_choices(p)
        if pos_idx < len(pos):
            a = pos[pos_idx]
            if a.nargs == argparse.REMAINDER:
                return "ok", "", tuple(path)
            if a.choices and word not in a.choices:
                if not in_code and not (i + 1 < len(toks) and toks[i + 1].startswith("--")):
                    return "ok", "", tuple(path)  # prosa depois de um comando completo
                return "erro", "`%s %s`: valor %r fora de %s" % (prog, " ".join(path), word, sorted(a.choices)), tuple(path)
            pos_idx += 1
            i += 1
            continue
        # palavra solta depois de um comando completo = fim do comando (prosa)
        break
    if in_code == "strict" and path:
        missing = []
        for a in p._actions:
            if a.option_strings and a.required and not (set(a.option_strings) & seen):
                missing.append(a.option_strings[-1])
        if missing:
            return "erro", "`%s %s` sem opção obrigatória %s" % (prog, " ".join(path), ", ".join(missing)), tuple(path)
    return "ok", "", tuple(path)


class CommandsParseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parsers = load_parsers()
        cls.results = []
        for f in doc_files():
            for label, text, is_code in doc_texts(f):
                for lab, prog, toks, in_code, shown in occurrences(label, text, is_code):
                    st, msg, path = check_occurrence(cls.parsers, prog, toks, in_code)
                    cls.results.append((st, lab, shown.strip(), msg))

    def test_found_commands(self):
        n = sum(1 for r in self.results if r[0] == "ok")
        self.assertGreater(n, 40, "o extrator deveria achar dezenas de comandos citados; achou %d" % n)

    def test_every_cited_command_parses(self):
        errs = ["%s: %s\n      → %s" % (lab, shown[:140], msg) for st, lab, shown, msg in self.results if st == "erro"]
        self.assertEqual(errs, [], "comandos citados que a CLI real não aceita:\n  " + "\n  ".join(errs))

    def test_pendentes(self):
        pend = sorted(set("%s: %s (%s)" % (lab, shown[:90], msg) for st, lab, shown, msg in self.results
                          if st == "pendente"))
        if pend:
            self.skipTest("PENDENTES (frente_cli ainda criando; %d citações):\n  %s" % (len(pend), "\n  ".join(pend)))

    def test_pendentes_list_is_current(self):
        """Entrada de PENDENTES que já existe no argparse real deve sair da lista (é conferida normalmente)."""
        landed = []
        for (prog, path), why in PENDENTES.items():
            p = self.parsers[prog]
            ok = True
            for w in path:
                sp = subparsers_of(p)
                if sp is None or w not in sp.choices:
                    ok = False
                    break
                p = sp.choices[w]
            if ok:
                landed.append("%s %s" % (prog, " ".join(path)))
        for (prog, path, flag), why in PENDENTES_FLAGS.items():
            p = self.parsers[prog]
            for w in path:
                sp = subparsers_of(p)
                p = sp.choices.get(w) if sp is not None else None
                if p is None:
                    break
            if p is not None and flag in option_strings(p):
                landed.append("%s %s %s" % (prog, " ".join(path), flag))
        if landed:
            self.skipTest("já existem no argparse (remova de PENDENTES/PENDENTES_FLAGS): %s" % ", ".join(landed))

    def test_contrato_commands_cited_and_parse(self):
        """Comandos do contrato (iterações 3 e 4): citados nos docs e aceitos pela CLI (ou pendentes com motivo)."""
        allraw = ""
        for f in doc_files():
            with open(f, encoding="utf-8") as fh:
                allraw += fh.read() + "\n"
        missing, bad = [], []
        for key, (prog, cmd) in CONTRATO.items():
            if not re.search(CONTRATO_CITADO[key], allraw):
                missing.append("%s (%s)" % (key, CONTRATO_CITADO[key]))
            st, msg, _ = check_occurrence(self.parsers, prog, cmd.split(), "strict")
            if st not in ("ok", "pendente"):
                bad.append("%s: %s %s → %s" % (key, prog, cmd, msg))
        self.assertEqual(missing, [], "contrato não citado na documentação: %s" % missing)
        self.assertEqual(bad, [], "contrato não parseia nem está pendente:\n  " + "\n  ".join(bad))

    def test_extractor_catches_known_bad(self):
        """Sanidade do extrator: os desalinhamentos da iteração 1 são pegos."""
        bad = [  # flags/subcomandos inventados (estáveis mesmo que a CLI ganhe aliases)
            ("cs.py", "facts spotcheck record --fact F --verdict ok --note VAL --veredito-inexistente x".split(), True),
            ("cs.py", "panel inexistente-xyz --file f".split(), True),
            ("cs.py", "team card set a --flag-que-nao-existe f".split(), True),
            ("cs-state", "sprint plann".split(), True),
            ("cs-mem", "search VAL --kind-x y".split(), True),
            ("cs.py", "panel pack A".split(), "strict"),  # --role/--out obrigatórias
        ]
        for prog, toks, code in bad:
            st, msg, _ = check_occurrence(self.parsers, prog, toks, code)
            self.assertEqual(st, "erro", "%s %s deveria reprovar (%s)" % (prog, toks, msg))
        good = [
            ("cs.py", "facts spotcheck record --fact F --verdict wrong --note VAL".split(), True),
            ("cs.py", "--target T stage load scan".split(), True),
            ("cs-mem", "search VAL --paths VAL".split(), True),
            ("cs-state", "sprint plan --goal VAL".split(), True),
        ]
        for prog, toks, code in good:
            st, msg, _ = check_occurrence(self.parsers, prog, toks, code)
            self.assertEqual(st, "ok", "%s %s deveria passar (%s)" % (prog, toks, msg))


if __name__ == "__main__":
    unittest.main()
