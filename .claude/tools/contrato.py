#!/usr/bin/env python3
"""contrato.py — a LEI da frente: valida o Bloco A (FRENTE.md), o Bloco B (tasks), a cobertura, os grupos, os
depends, as propostas das etapas E1/E2/E5 e a complexidade declarada. Um script único (sem cópia que derive),
Python 3.9+ stdlib, nos 2 Pythons. É o que o `frente.py criar propor` roda; o agente roda antes para ver as lacunas.

Uso:
  contrato.py frente <FRENTE.md> [--json]            Bloco A (FRENTE-ID, seções, CAs DADO/QUANDO/ENTÃO + Prova,
                                                      escopo de escrita estreito, parada com número, aceites)
  contrato.py completo <pasta-da-frente> [--json]    Bloco A + todas as TASKS/ + cobertura de CA, oráculo, QA,
                                                      REVIEW, depends (com porquê, existentes, sem ciclo), grupos
                                                      (≤3, disjuntos), escopo, mesmo arquivo serializado
  contrato.py task <task.md> [--json]                só o schema de UMA task (cabeçalho, seções, arquivos exatos,
                                                      verificação concreta)
  contrato.py etapa E1|E2|E5 <proposta.md> [--json]  rótulos obrigatórios da proposta; E2 exige achado F<n> com
                                                      arquivo:linha
  contrato.py complexidade <task.md>                 `complexidade: baixa` só vale com ≤2 arquivos, sem área
                                                      sensível, sem texto de protocolo e verificação concreta
  contrato.py --sonda                                sonda negativa: frente válida tem de passar e a mesma frente
                                                      sem o Goal de uma task tem de reprovar (0 = sonda ok,
                                                      3 = NOT_RUN: o contrato não discrimina — não confie nele)
Exit: 0 ok · 2 lacunas (listadas; em --json {"ok","lacunas":[{"codigo","msg"}]}) · 3 uso/NOT_RUN.
NOT_RUN nunca é PASS: se a sonda falhar, a validação manual não substitui o script.
"""
import argparse
import fnmatch
import json
import os
import re
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import estado_lib as L  # noqa: E402

SECOES_FRENTE = ("História", "Problema / Contexto", "Valor de negócio", "Personas / Stakeholders",
                 "Critérios de Aceitação", "RNFs", "Edge cases", "Dependências", "Escopo IN", "Escopo OUT",
                 "Escopo de escrita", "Critério de parada", "Métrica de sucesso", "Aceite da Frente")
ROTULOS = {"E1": ("Demanda", "Problema por trás", "O que NÃO é", "Perguntas abertas", "FRENTE-ID"),
           "E2": ("Inventário", "Classificação", "Exclusões", "Achados", "Enforcement existente"),
           "E5": ("Ordem", "Primeira task", "Escopo da campanha", "Critério de parada", "Git")}
AMPLOS = ("*", "**", "**/*", ".", "./", "/")


class Lacunas:
    def __init__(self):
        self.itens = []

    def add(self, codigo, msg):
        if not any(x["codigo"] == codigo for x in self.itens):
            self.itens.append({"codigo": codigo, "msg": msg})


# ------------------------------------------------------------------ Bloco A

def checar_frente(p, lac, fid=None):
    fr = L.ler_frente(p)
    if fr is None:
        lac.add("campo_ausente:FRENTE.md", "FRENTE.md não existe: %s" % p)
        return None
    if not fr["id"] or not L.ID_RE.match(fr["id"]):
        lac.add("id_invalido:%s" % (fr["id"] or "—"),
                "FRENTE-ID ausente ou fora da gramática ^[a-z][a-z0-9]*(-[a-z0-9]+){0,5}$ (é o nome da campanha)")
    elif fid and fr["id"] != fid:
        lac.add("id_invalido:%s" % fr["id"], "FRENTE-ID %s difere da frente %s" % (fr["id"], fid))
    if not fr["nome"]:
        lac.add("campo_ausente:Nome", "falta a linha `Nome:`")
    for s in SECOES_FRENTE:
        if not fr["secoes"].get(s, "").strip():
            lac.add("campo_ausente:%s" % s, "seção `## %s` ausente ou vazia" % s)
    h = fr["historia"].lower()
    if h and not (re.search(r"\bcomo\b", h) and re.search(r"\bquero\b", h) and re.search(r"\bpara\b", h)):
        lac.add("historia_sem_como_quero_para", "a História tem de ser 'Como …, quero …, para …'")
    if fr["secoes"].get("Critérios de Aceitação", "").strip() and not fr["cas"]:
        lac.add("sem_ca", "nenhum item `- **CA-NN — …**` em Critérios de Aceitação")
    elif "Critérios de Aceitação" in fr["secoes"] and not fr["cas"]:
        lac.add("sem_ca", "nenhum CA")
    for ca in fr["cas"]:
        t = ca["texto"].upper()
        if not ("DADO" in t and "QUANDO" in t and ("ENTÃO" in t or "ENTAO" in t)):
            lac.add("ca_sem_dado_quando_entao:%s" % ca["id"], "%s sem DADO/QUANDO/ENTÃO" % ca["id"])
        if not ca["prova"]:
            lac.add("ca_sem_prova:%s" % ca["id"], "%s sem a linha `Prova: \\`comando\\``" % ca["id"])
    if "Escopo de escrita" in fr["secoes"]:
        if not fr["escopo"]:
            lac.add("escopo_vazio", "Escopo de escrita sem itens `- \\`glob\\`` (vira o --scope da campanha)")
        for g in fr["escopo"]:
            if g in AMPLOS or os.path.isabs(g) or ".." in g.split("/") or g.startswith("~"):
                lac.add("escopo_amplo:%s" % g, "glob amplo demais ou fora do projeto: %s" % g)
    if fr["parada"] and not re.search(r"\d", fr["parada"]):
        lac.add("parada_sem_numero", "o Critério de parada precisa de número (vira o --stop)")
    if "Aceite da Frente" in fr["secoes"]:
        if fr["aceite_qa"] not in ("PENDENTE", "ACCEPT") or fr["aceite_review"] not in ("PENDENTE", "APPROVED"):
            lac.add("aceite_sem_qa_review",
                    "Aceite da Frente precisa de `### Aceite QA — PENDENTE|ACCEPT` e `### Aceite Review — PENDENTE|APPROVED`")
    return fr


# ------------------------------------------------------------------ Bloco B

def checar_task(t, lac, fid=None):
    tid = t["cab"].get("id") or t["stem"]
    if not L.TASK_NOME_RE.match(t["nome"]):
        lac.add("task_nome_invalido:%s" % t["nome"], "nome fora da gramática {NN}-{TASK|BUG|GAP|DEBT}-{DESCRICAO}.md")
    for c in L.CAB_TASK:
        if not t["cab"].get(c):
            lac.add("task_cabecalho:%s:%s" % (tid, c), "%s: cabeçalho sem `%s:`" % (tid, c))
    if t["cab"].get("id") and t["cab"]["id"] != t["stem"]:
        lac.add("id_difere_do_arquivo:%s" % t["nome"], "id %s difere do nome do arquivo" % t["cab"]["id"])
    if t["tipo"] and t["tipo"] not in L.TIPOS_TASK:
        lac.add("tipo_invalido:%s" % tid, "tipo %s fora de %s" % (t["tipo"], "|".join(L.TIPOS_TASK)))
    for s in L.SECOES_TASK:
        if s not in t["secoes"] or (s != "Handoff" and not t["secoes"][s].strip()):
            lac.add("task_campo_ausente:%s:%s" % (tid, s), "%s: seção `## %s` ausente ou vazia" % (tid, s))
    n = len(re.findall(r"(?m)^\s*\d+\.\s+\S", t["secoes"].get("Subtasks", "")))
    if "Subtasks" in t["secoes"] and not 2 <= n <= 5:
        lac.add("subtasks_fora_de_faixa:%s" % tid, "%s: %d subtasks (2–5)" % (tid, n))
    if "Arquivos permitidos" in t["secoes"] and not t["arquivos"]:
        lac.add("arquivos_vazio:%s" % tid, "%s: Arquivos permitidos sem itens `- \\`path\\``" % tid)
    for a in t["arquivos"]:
        if any(c in a for c in "*?[") or a.endswith("/"):
            lac.add("arquivo_glob:%s:%s" % (tid, a), "%s: arquivo permitido tem de ser exato, não glob: %s" % (tid, a))
    if "Verificação" in t["secoes"] and L.verificacao_trivial(t["verificacao"]):
        lac.add("verificacao_trivial:%s" % tid, "%s: Verificação sem comando concreto (ls/echo/TBD/true/cat não "
                                                "provam nada)" % tid)
    if t["status"] == "DONE" and (t["gate"] != "PASS" or not t["handoff"]):
        lac.add("done_sem_gate_ou_handoff:%s" % tid, "%s: DONE exige gate PASS e Handoff preenchido" % tid)


def checar_completo(fd, lac):
    fr = checar_frente(os.path.join(fd, "FRENTE.md"), lac)
    fid = (fr or {}).get("id") or os.path.basename(os.path.normpath(fd))
    escopo = (fr or {}).get("escopo") or []
    tasks = L.ler_tasks(fd)
    ids = {t["stem"] for t in tasks}
    for t in tasks:
        checar_task(t, lac, fid)
    oraculo_pfx = "campanhas/%s/oraculo/" % fid
    por_tipo = {k: [t for t in tasks if t["tipo"] == k] for k in L.TIPOS_TASK}
    if not por_tipo["ORACULO"]:
        lac.add("oraculo_ausente", "falta a task ORACULO (por agente separado, em %s)" % oraculo_pfx)
    for t in por_tipo["ORACULO"]:
        for a in L.arquivos_reais(t):
            if not a.startswith(oraculo_pfx):
                lac.add("oraculo_fora_da_pasta:%s:%s" % (t["stem"], a), "o oráculo só escreve em %s" % oraculo_pfx)
    if not por_tipo["QA"]:
        lac.add("qa_ausente", "falta a task QA (portão + oráculo)")
    if not por_tipo["REVIEW"]:
        lac.add("review_ausente", "falta a task REVIEW (revisor isolado)")
    for t in tasks:
        for d, porque in t["depends"]:
            if d not in ids:
                lac.add("depends_inexistente:%s:%s" % (t["stem"], d), "%s depende de %s, que não existe" % (t["stem"], d))
            elif not porque:
                lac.add("depends_sem_porque:%s:%s" % (t["stem"], d), "%s → %s sem o porquê entre parênteses" % (t["stem"], d))
    if L.tem_ciclo(tasks):
        lac.add("depends_ciclo", "o grafo de depends tem ciclo")
    fecho = L.fecho_depends(tasks)
    oraculos = {t["stem"] for t in por_tipo["ORACULO"]}
    grupos = set()
    for t in por_tipo["CORRECAO"]:
        if not re.match(r"^G[1-3]$", t["grupo"] or ""):
            lac.add("grupo_ausente:%s" % t["stem"], "%s: CORRECAO precisa de grupo G1..G3" % t["stem"])
        else:
            grupos.add(t["grupo"])
        for a in L.arquivos_reais(t):
            if a.startswith("campanhas/") and "/oraculo/" in a + "/":
                lac.add("correcao_escreve_oraculo:%s:%s" % (t["stem"], a), "quem corrige não toca o oráculo")
            elif escopo and not any(fnmatch.fnmatch(a, g) for g in escopo):
                lac.add("arquivo_fora_do_escopo:%s:%s" % (t["stem"], a), "%s fora do Escopo de escrita" % a)
        if oraculos and not (fecho.get(t["stem"], set()) & oraculos):
            lac.add("correcao_sem_depender_do_oraculo:%s" % t["stem"], "%s não depende (nem transitivamente) do "
                                                                      "oráculo" % t["stem"])
    if len(grupos) > 3:
        lac.add("grupos_demais", "mais de 3 grupos de correção")
    donos = {}
    for t in tasks:
        for a in L.arquivos_reais(t):
            donos.setdefault(a, []).append(t)
    for a, ts in sorted(donos.items()):
        for i, x in enumerate(ts):
            for y in ts[i + 1:]:
                if not (y["stem"] in fecho.get(x["stem"], set()) or x["stem"] in fecho.get(y["stem"], set())):
                    lac.add("mesmo_arquivo_sem_ordem:%s" % a, "%s em %s e %s sem depends entre elas"
                            % (a, x["stem"], y["stem"]))
                if x["tipo"] == y["tipo"] == "CORRECAO" and x["grupo"] != y["grupo"]:
                    lac.add("grupos_colidem:%s" % a, "%s em grupos %s e %s (grupos têm arquivos disjuntos)"
                            % (a, x["grupo"], y["grupo"]))
    cobertos = set()
    for t in por_tipo["CORRECAO"]:
        cobertos |= set(t["cas"])
    for ca in (fr or {}).get("cas") or []:
        if ca["id"] not in cobertos:
            lac.add("ca_orfao:%s" % ca["id"], "%s sem task CORRECAO que o cubra" % ca["id"])
    return fr, tasks


def checar_etapa(etapa, p, lac):
    txt = L.ler(p)
    if txt is None:
        lac.add("etapa_campo_ausente:%s:arquivo" % etapa, "proposta não existe: %s" % p)
        return
    for r in ROTULOS[etapa]:
        if not re.search(r"(?im)^[#>*\-\s]*\**\s*" + re.escape(r) + r"(?![\wÀ-ú])", txt):
            lac.add("etapa_campo_ausente:%s:%s" % (etapa, r), "%s sem o rótulo `%s`" % (etapa, r))
    if etapa == "E2" and not re.search(r"(?m)\bF\d+\b.*?[\w./-]+\.\w+:\d+", txt):
        lac.add("e2_sem_evidencia", "nenhum achado F<n> com arquivo:linha — medir antes de afirmar")


def complexidade_ok(t):
    """(ok, motivos): `baixa` só se ≤2 arquivos, sem área sensível, sem protocolo e verificação concreta."""
    if (t["cab"].get("complexidade") or "").strip() != "baixa":
        return True, []
    m = []
    arqs = L.arquivos_reais(t)
    if len(arqs) > 2:
        m.append("%d arquivos (máx. 2)" % len(arqs))
    for a in arqs:
        if L.sensivel(a):
            m.append("área sensível: %s" % a)
        if L.protocolo(a):
            m.append("texto de protocolo: %s" % a)
    if L.verificacao_trivial(t["verificacao"]):
        m.append("verificação trivial")
    return not m, m


# ------------------------------------------------------------------ sonda

SONDA_FRENTE = """# sonda — frente de sonda

FRENTE-ID: sonda
Nome: frente de sonda do contrato

## História
Como mantenedor, quero que `x()` devolva 2, para provar que o contrato discrimina.

## Problema / Contexto
`s/x.py:2` devolve 1 (medido).

## Valor de negócio
O contrato é conferido antes de valer.

## Personas / Stakeholders
- founder

## Critérios de Aceitação
- **CA-01 — x devolve 2.** DADO `x`, QUANDO chamada, ENTÃO devolve 2.
  Prova: `python3 -m unittest test_sonda`

## RNFs
- stdlib

## Edge cases
- nenhum

## Dependências
- nenhuma

## Escopo IN
- `s/x.py`

## Escopo OUT
- o resto

## Escopo de escrita
- `s/x.py`

## Critério de parada
oráculo 1/1 verde

## Métrica de sucesso
1 de 1 CA

## Aceite da Frente
### Aceite QA — PENDENTE
### Aceite Review — PENDENTE
"""


def _sonda_task(nn, desc, tipo, grupo, dep, arq, goal=True, verif="python3 -m unittest test_sonda"):
    tid = "%s-TASK-%s" % (nn, desc)
    c = ["# %s — %s" % (tid, desc.lower()), "", "id: " + tid, "frente: sonda", "tipo: " + tipo, "grupo: " + grupo,
         "agente: x", "CA: CA-01", "depends: " + dep, "status: PENDENTE", "gate: PENDENTE", ""]
    if goal:
        c += ["## Goal", "fazer e NÃO tocar o resto", ""]
    c += ["## Contexto", "CA-01; `s/x.py:2`", "", "## Subtasks", "1. a", "2. b", "", "## Invariants", "- x", "",
          "## Scope IN / OUT", "IN x OUT y", "", "## Arquivos permitidos", "- `%s`" % arq, "", "## AC", "- x", "",
          "## DoD", "- x", "", "## Verificação", "```bash", verif, "```", "", "## Handoff", ""]
    return tid, "\n".join(c) + "\n"


def sonda():
    tmp = tempfile.mkdtemp(prefix="contrato-sonda-")
    try:
        fd = os.path.join(tmp, "frentes", "sonda")
        L.gravar(os.path.join(fd, "FRENTE.md"), SONDA_FRENTE)
        dep = "01-TASK-ORACULO (o oráculo vem antes)"
        tasks = [_sonda_task("01", "ORACULO", "ORACULO", "—", "—", "campanhas/sonda/oraculo/test_sonda.py"),
                 _sonda_task("02", "X", "CORRECAO", "G1", dep, "s/x.py"),
                 _sonda_task("03", "QA", "QA", "—", "02-TASK-X (precisa da correção)",
                             ".claude/state/frentes/sonda/TASKS/03-TASK-QA.md", verif="bash portao.sh sonda --dry-run"),
                 _sonda_task("04", "REVIEW", "REVIEW", "—", "03-TASK-QA (examina o QA)",
                             ".claude/state/frentes/sonda/TASKS/04-TASK-REVIEW.md", verif="git diff --stat")]
        for tid, txt in tasks:
            L.gravar(os.path.join(fd, "TASKS", tid + ".md"), txt)
        bom = Lacunas()
        checar_completo(fd, bom)
        tid, sem_goal = _sonda_task("02", "X", "CORRECAO", "G1", dep, "s/x.py", goal=False)
        L.gravar(os.path.join(fd, "TASKS", tid + ".md"), sem_goal)
        ruim = Lacunas()
        checar_completo(fd, ruim)
        ok = not bom.itens and any("Goal" in x["codigo"] for x in ruim.itens)
        return ok, bom.itens, ruim.itens
    except Exception as e:  # noqa: BLE001 — qualquer erro da sonda é NOT_RUN, nunca PASS
        return False, [{"codigo": "sonda_erro", "msg": str(e)}], []
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ CLI

def emitir(lac, a, titulo):
    ok = not lac.itens
    if getattr(a, "json", False):
        print(json.dumps({"ok": ok, "lacunas": lac.itens}, ensure_ascii=False, indent=1))
    else:
        if ok:
            print("%s: PASS (0 lacunas)" % titulo)
        else:
            print("%s: %d lacuna(s)" % (titulo, len(lac.itens)))
            for x in lac.itens:
                print("  - %s — %s" % (x["codigo"], x["msg"]))
    return 0 if ok else 2


def main(argv=None):
    ap = argparse.ArgumentParser(prog="contrato.py", description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="subcomandos: frente, completo, task, etapa, complexidade, --sonda (ver o "
                                        "cabeçalho do arquivo)")
    ap.add_argument("--sonda", action="store_true", help="sonda negativa (0 ok · 3 NOT_RUN)")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("frente", help="Bloco A")
    s.add_argument("arquivo")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("completo", help="Bloco A + tasks + cobertura")
    s.add_argument("pasta")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("task", help="schema de uma task")
    s.add_argument("arquivo")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("etapa", help="proposta E1|E2|E5")
    s.add_argument("etapa", choices=("E1", "E2", "E5"))
    s.add_argument("arquivo")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("complexidade", help="complexidade: baixa confere?")
    s.add_argument("arquivo")
    s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.sonda:
        ok, bom, ruim = sonda()
        if a.json:
            print(json.dumps({"ok": ok, "valida_passou": not bom, "sem_goal_reprovou": [x["codigo"] for x in ruim]},
                             ensure_ascii=False))
        else:
            print("sonda: %s" % ("OK (válida passa; sem Goal reprova)" if ok else "NOT_RUN — o contrato não discrimina"))
            for x in bom:
                print("  válida reprovou: %s — %s" % (x["codigo"], x["msg"]))
        return 0 if ok else 3
    if not a.cmd:
        ap.print_help()
        return 3
    lac = Lacunas()
    if a.cmd == "frente":
        checar_frente(a.arquivo, lac)
        return emitir(lac, a, "contrato frente")
    if a.cmd == "completo":
        if not os.path.isdir(a.pasta):
            print("pasta da frente não existe: %s" % a.pasta, file=sys.stderr)
            return 3
        checar_completo(a.pasta, lac)
        return emitir(lac, a, "contrato completo")
    if a.cmd == "task":
        t = L.ler_task(a.arquivo)
        if t is None:
            print("task não existe: %s" % a.arquivo, file=sys.stderr)
            return 3
        checar_task(t, lac)
        return emitir(lac, a, "contrato task")
    if a.cmd == "etapa":
        checar_etapa(a.etapa, a.arquivo, lac)
        return emitir(lac, a, "contrato etapa %s" % a.etapa)
    if a.cmd == "complexidade":
        t = L.ler_task(a.arquivo)
        if t is None:
            print("task não existe: %s" % a.arquivo, file=sys.stderr)
            return 3
        ok, motivos = complexidade_ok(t)
        if a.json:
            print(json.dumps({"ok": ok, "complexidade": t["cab"].get("complexidade") or "normal",
                              "motivos": motivos}, ensure_ascii=False))
        else:
            print("complexidade: %s" % ("OK" if ok else "RECUSADA — " + "; ".join(motivos)))
        return 0 if ok else 2
    return 3


if __name__ == "__main__":
    sys.exit(main())
