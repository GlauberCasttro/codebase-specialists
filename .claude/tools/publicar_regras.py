#!/usr/bin/env python3
"""publicar_regras.py — MECANISMO de limpeza de privacidade (as regras com texto privado NÃO ficam aqui).

Uso:
  publicar_regras.py aplicar <dir> [--regras ARQ] [--pacote] [--json]
  publicar_regras.py --grep <dir> [--pacote]   (só o grep: guard-privacidade + referências internas se --pacote)
  publicar_regras.py --check-regras            (valida o arquivo de regras; imprime só contagens)
  publicar_regras.py --help

Regras privadas: `local/regras-privadas.json5` (gitignored; nunca publicado; outro caminho em $CS_REGRAS_PRIVADAS ou
--regras). Formato (JSON5):
  { renomear: [["caminho/antigo", "caminho/novo"], ...],          // relativo ao <dir>; aplicado primeiro
    blocos:   [["arquivo", "texto original", "texto novo"], ...],  // troca exata num arquivo; ausente = AVISO
    gerais:   [{de: "...", para: "...", re: false, i: false, caso: false}, ...] }   // todo arquivo de texto
  `re` = expressão regular; `i` = ignora caixa; `caso` = preserva a caixa do achado (MAIÚSCULA/Título/minúscula).
Sem o arquivo: AVISO e só as regras de código abaixo (o grep final é quem decide).

`--pacote` (usado por tools/package.sh): além das regras privadas, troca referências a documentos INTERNOS que
não vão no pacote (PONTOS-DO-FOUNDER, ROADMAP-*, campanhas/…) por texto neutro, apaga linhas de tabela Markdown que
linkam um .md ausente no pacote e, no grep, reprova referência interna que sobrou.
Ordem: renomear → blocos → gerais (privadas) → regras de pacote → grep (guard_privacidade). Achado = exit 1.
Stdlib apenas, Python 3.9+.
"""
import importlib.util
import json
import os
import re
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
PROJETO = os.path.realpath(os.environ.get("CS_DEV_SKILL_DIR") or os.path.join(TOOLS, "..", ".."))

# Regras de PACOTE (não contêm nada privado): documentos internos do projeto que não entram no pacote.
PACOTE_GERAIS = [
    (True, r"`?campanhas/(iter\d+|m5)/oraculo/ESPEC\.md`?", r"ESPEC interna da rodada \1"),
    (True, r"`?campanhas/(iter\d+|m5)/[^\s`)]*`?", r"registro interno da rodada \1"),
    (True, r"`?campanhas/[^\s`)]*`?", "registro interno das rodadas"),
    (False, "PONTOS-DO-FOUNDER.md", "registro de decisões de produto"),
    (False, "PONTOS-DO-FOUNDER", "decisão de produto"),
    (False, "AUTONOMIA-DESENHO.md", "desenho do modo autônomo"),
    (False, "AUTONOMIA-DESENHO", "desenho do modo autônomo"),
    (True, r"`?(docs/)?ROADMAP-proxima-rodada\.md`?", "plano da rodada"),
    (True, r"`?(docs/)?ROADMAP-rodada-seguinte\.md`?", "plano da rodada seguinte"),
    (True, r"`?PROXIMA-RODADA\.md`?", "plano da rodada seguinte"),
    (True, r"`?RODADA-SEGUINTE\.md`?", "plano da rodada seguinte"),
    (True, r"`?(docs/)?PENDENTE\.md`?", "registro interno de pendências"),
    (True, r"`?(docs/)?defeitos-abertos\.json5`?", "registro interno de defeitos"),
]
# O que não pode sobrar no pacote (referência a documento/pasta interna). Não é privado; é higiene do pacote.
PACOTE_INTERNOS = (r"PONTOS-DO-FOUNDER|PROXIMA-RODADA|RODADA-SEGUINTE|ROADMAP-|AUTONOMIA-DESENHO|PENDENTE\.md|"
                   r"defeitos-abertos|campanhas/|12-rodada-")
LINK_MD = re.compile(r"\]\(([^)#\s]+\.md)(#[^)]*)?\)")


def _json5():
    spec = importlib.util.spec_from_file_location("ac_motor", os.path.join(TOOLS, "ac", "ac.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.json5_loads


def arquivo_regras(explicito=None):
    return explicito or os.environ.get("CS_REGRAS_PRIVADAS") or os.path.join(PROJETO, "local", "regras-privadas.json5")


def carregar_regras(explicito=None):
    p = arquivo_regras(explicito)
    if not os.path.isfile(p):
        print("AVISO publicar_regras: %s ausente — só regras de código; o grep decide." % p, file=sys.stderr)
        return {"renomear": [], "blocos": [], "gerais": []}, False
    with open(p, encoding="utf-8") as fh:
        r = _json5()(fh.read())
    if not isinstance(r, dict):
        raise SystemExit("regras inválidas: %s não é objeto" % p)
    for k in ("renomear", "blocos", "gerais"):
        r.setdefault(k, [])
        if not isinstance(r[k], list):
            raise SystemExit("regras inválidas: %s.%s não é lista" % (p, k))
    for b in r["blocos"]:
        if not (isinstance(b, list) and len(b) == 3 and all(isinstance(x, str) for x in b)):
            raise SystemExit("regras inválidas: bloco deve ser [arquivo, original, novo]")
    for g in r["gerais"]:
        if not (isinstance(g, dict) and isinstance(g.get("de"), str) and isinstance(g.get("para"), str)):
            raise SystemExit("regras inválidas: regra geral precisa de 'de' e 'para'")
    return r, True


def eh_texto(path):
    try:
        with open(path, "rb") as fh:
            return b"\0" not in fh.read(4096)
    except OSError:
        return False


def arquivos(root):
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in (".git", "__pycache__", "local", "dist", ".auto-correcao"))
        for f in sorted(files):
            p = os.path.join(d, f)
            if not os.path.islink(p) and eh_texto(p):
                yield p


def _caso(modelo, novo):
    if modelo.isupper():
        return novo.upper()
    if modelo[:1].isupper():
        return novo[:1].upper() + novo[1:]
    return novo


def _sub_geral(g, s):
    flags = re.I if g.get("i") else 0
    pat = g["de"] if g.get("re") else re.escape(g["de"])
    if g.get("caso"):
        return re.sub(pat, lambda m: _caso(m.group(0), m.expand(g["para"]) if g.get("re") else g["para"]), s,
                      flags=flags)
    return re.sub(pat, g["para"] if g.get("re") else g["para"].replace("\\", "\\\\"), s, flags=flags)


def _linhas_de_link_quebrado(p, s):
    out = []
    for ln in s.split("\n"):
        if ln.lstrip().startswith("|"):
            quebrado = False
            for m in LINK_MD.finditer(ln):
                alvo = m.group(1)
                if "://" in alvo:
                    continue
                if not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(p), alvo))):
                    quebrado = True
            if quebrado:
                continue
        out.append(ln)
    return "\n".join(out)


def transformar(root, regras, pacote=False):
    rel = {"renomeados": [], "blocos_aplicados": 0, "blocos_ausentes": [], "alterados": []}
    for a, b in regras["renomear"]:
        pa, pb = os.path.join(root, a), os.path.join(root, b)
        if os.path.exists(pa):
            os.makedirs(os.path.dirname(pb), exist_ok=True)
            os.rename(pa, pb)
            rel["renomeados"].append("%s -> %s" % (a, b))
    for i, (arq, a, b) in enumerate(regras["blocos"], 1):
        p = os.path.join(root, arq)
        if not os.path.isfile(p):
            rel["blocos_ausentes"].append("%s: arquivo ausente (bloco #%d)" % (arq, i))
            continue
        with open(p, encoding="utf-8") as fh:
            s = fh.read()
        if a not in s:
            if b and b in s:
                rel.setdefault("blocos_ja_aplicados", 0)
                rel["blocos_ja_aplicados"] += 1   # a fonte já está limpa (ex.: o projeto): nada a fazer
            else:
                rel["blocos_ausentes"].append("%s: bloco #%d" % (arq, i))
            continue
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(s.replace(a, b))
        rel["blocos_aplicados"] += 1
    for p in arquivos(root):
        try:
            with open(p, encoding="utf-8") as fh:
                s = fh.read()
        except UnicodeDecodeError:
            continue
        novo = s
        for g in regras["gerais"]:
            novo = _sub_geral(g, novo)
        if pacote:
            for eh_re, a, b in PACOTE_GERAIS:
                novo = re.sub(a, b, novo) if eh_re else novo.replace(a, b)
            if p.endswith(".md"):
                novo = _linhas_de_link_quebrado(p, novo)
        if novo != s:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(novo)
            rel["alterados"].append(os.path.relpath(p, root))
    return rel


def grep(root, pacote=False):
    spec = importlib.util.spec_from_file_location("guard_priv", os.path.join(TOOLS, "guard_privacidade.py"))
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    rx, _, _ = g.carregar()
    achados = g.varrer_arquivos(rx, [os.path.realpath(root)])
    if pacote:
        ri = re.compile(PACOTE_INTERNOS)
        for p in arquivos(root):
            with open(p, encoding="utf-8", errors="replace") as fh:
                for n, ln in enumerate(fh, 1):
                    if ri.search(ln):
                        achados.append("INTERNO %s:%d: %s" % (os.path.relpath(p, root), n, ln.strip()[:160]))
    return achados


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    pacote = "--pacote" in argv
    js = "--json" in argv
    explicito = argv[argv.index("--regras") + 1] if "--regras" in argv else None
    if argv[0] == "--check-regras":
        r, tem = carregar_regras(explicito)
        print("regras: %s · renomear %d · blocos %d · gerais %d" % ("presentes" if tem else "AUSENTES",
              len(r["renomear"]), len(r["blocos"]), len(r["gerais"])))
        return 0 if tem else 1
    if argv[0] == "--grep":
        if len(argv) < 2:
            print("uso: publicar_regras.py --grep <dir> [--pacote]", file=sys.stderr)
            return 2
        ach = grep(argv[1], pacote)
        for a in ach:
            print(a if a.startswith("INTERNO ") else "PRIVADO " + a)
        return 1 if ach else 0
    if argv[0] != "aplicar" or len(argv) < 2 or not os.path.isdir(argv[1]):
        print("uso: publicar_regras.py aplicar <dir> [--regras ARQ] [--pacote] [--json]", file=sys.stderr)
        return 2
    root = argv[1]
    regras, _ = carregar_regras(explicito)
    rel = transformar(root, regras, pacote)
    rel["privados"] = grep(root, pacote)
    if js:
        print(json.dumps(rel, ensure_ascii=False, indent=1))
    else:
        print("renomeados: %d · blocos aplicados: %d/%d · arquivos alterados pelas regras gerais: %d"
              % (len(rel["renomeados"]), rel["blocos_aplicados"], len(regras["blocos"]), len(rel["alterados"])))
        ausentes = [b for b in rel["blocos_ausentes"] if "arquivo ausente" in b]
        for b in rel["blocos_ausentes"]:
            if pacote and b in ausentes:
                continue  # no pacote, arquivos de teste/campanha/docs internos não existem: esperado
            print("AVISO bloco não aplicado (código mudou?): " + b)
        if pacote and ausentes:
            print("(%d bloco(s) de arquivos fora do pacote ignorados)" % len(ausentes))
        for a in rel["privados"]:
            print(a if a.startswith("INTERNO ") else "PRIVADO " + a)
    return 1 if rel["privados"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
