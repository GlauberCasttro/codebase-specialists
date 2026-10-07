#!/usr/bin/env python3
"""guard-estado.py — hook PreToolUse (Edit|Write|MultiEdit|NotebookEdit) do ESTADO das features (.claude/state/).

O guard-entrega deixa `.claude/state/**` editável; este guard estreita o que é do SCRIPT (feature.py) e a ordem das
etapas da criação. Nega:
  - `features.json`, `features/<id>/CHECKLIST.md`, `features/<id>/eventos.jsonl`, `features/<id>/propostas/**`
    (só o feature.py escreve: o checklist é a projeção dos eventos; as propostas guardam o sha aprovado);
  - `features/<id>/FEATURE.md` antes da E2 aprovada (feature aberta: livre);
  - `features/<id>/TASKS/*` antes da E3 aprovada, ou com nome fora de {NN}-{TASK|BUG|GAP|DEBT}-{DESC}.md;
  - task com `status: DONE` sem `gate: PASS` e `## Handoff` preenchido (Write, Edit e MultiEdit: avalia o
    conteúdo RESULTANTE);
  - `archive/<id>/<qualquer coisa>` que não seja `archive/<id>/<id>.md` (documento único).
Fora disso (RESUME, BACKLOG, DECISIONS, INDEX, HISTORICO, produto…) não opina: sem saída.

Contrato (Claude Code): payload JSON pela stdin (tool_name, tool_input.file_path|notebook_path, content,
old_string/new_string, edits, cwd). Negar = stdout {"hookSpecificOutput":{"hookEventName":"PreToolUse",
"permissionDecision":"deny","permissionDecisionReason":...}} e exit 0 (igual ao guard-entrega). Payload inválido = nega.
LIMITE HONESTO: só vê Edit/Write/MultiEdit/NotebookEdit; escrita por Bash no estado não passa aqui (é por Bash que
os scripts escrevem). `feature.py checklist` e o sha das propostas detectam a adulteração depois.
Uso: echo '<payload>' | python3 guard-estado.py · --help. Variável de teste: CS_DEV_SKILL_DIR.
"""
import json
import os
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import estado_lib as L  # noqa: E402

FERRAMENTAS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def negar(motivo):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": "guard-estado: " + motivo}},
                     ensure_ascii=False))
    return 0


def conteudo_resultante(tool, ti, path):
    if tool == "Write":
        return ti.get("content")
    atual = L.ler(path, "")
    if tool == "Edit":
        old, new = ti.get("old_string") or "", ti.get("new_string") or ""
        if ti.get("replace_all"):
            return atual.replace(old, new)
        return atual.replace(old, new, 1) if old in atual else atual + new
    if tool == "MultiEdit":
        for e in ti.get("edits") or []:
            old, new = e.get("old_string") or "", e.get("new_string") or ""
            atual = atual.replace(old, new) if e.get("replace_all") else atual.replace(old, new, 1)
        return atual
    return None


def decidir(raw):
    try:
        d = json.loads(raw)
        if not isinstance(d, dict):
            raise ValueError("payload não é objeto")
    except Exception as e:  # noqa: BLE001
        return negar("payload inválido (%s) — falha fechada." % e)
    tool = d.get("tool_name") or ""
    if tool not in FERRAMENTAS:
        return 0
    ti = d.get("tool_input") or {}
    if not isinstance(ti, dict):
        return negar("tool_input inválido — falha fechada.")
    path = ti.get("file_path") or ti.get("notebook_path") or ""
    if not isinstance(path, str) or not path.strip():
        return negar("%s sem file_path — falha fechada." % tool)
    path = os.path.expanduser(path)
    if not os.path.isabs(path):
        path = os.path.join(d.get("cwd") or os.getcwd(), path)
    real = os.path.realpath(path)
    st = os.path.realpath(L.state())
    if not real.startswith(st + os.sep):
        return 0
    rel = os.path.relpath(real, st).replace(os.sep, "/")
    partes = rel.split("/")
    if rel in ("features.json", L.LEGADO_JSON):  # COMPAT: frentes.json antigo
        return negar("features.json só pelo feature.py (status/abrir/adotar/fechar idle).")
    if partes[0] == "archive" and len(partes) >= 2:
        fid = partes[1]
        if len(partes) != 3 or partes[2] != fid + ".md":
            return negar("archive/%s/ guarda só o documento único %s.md (feature.py fechar archive)." % (fid, fid))
        return 0
    if partes[0] not in ("features", L.LEGADO_DIR) or len(partes) < 3:  # COMPAT: frentes/ antigo
        return 0
    fid = partes[1]
    resto = "/".join(partes[2:])
    if resto in ("CHECKLIST.md", "eventos.jsonl") or partes[2] == "propostas":
        return negar("%s é escrito só pelo feature.py criar (checklist = projeção dos eventos; propostas guardam o "
                     "sha que o founder aprovou)." % rel)
    ev = L.eventos(fid)
    aberta = fid in L.ids_ativas() or any(e.get("tipo") == "abertura" for e in ev)
    ap = L.aprovadas(ev)
    if resto in ("FEATURE.md", L.LEGADO_MD):  # COMPAT: FRENTE.md antigo
        if not aberta and "E2" not in ap:
            return negar("FEATURE.md só depois da E2 aprovada (investigação medida antes de escrever a feature).")
        return 0
    if partes[2] == "TASKS":
        nome = partes[-1]
        if len(partes) != 4 or not L.TASK_NOME_RE.match(nome):
            return negar("nome de task fora da gramática {NN}-{TASK|BUG|GAP|DEBT}-{DESCRICAO}.md: %s" % nome)
        if not aberta and "E3" not in ap:
            return negar("TASKS só depois da E3 aprovada (o FEATURE.md vem antes da decomposição).")
        txt = conteudo_resultante(tool, ti, real)
        if txt is not None and re.search(r"(?m)^status:\s*DONE\s*$", txt):
            gate = re.search(r"(?m)^gate:\s*PASS\s*$", txt)
            ho = L.secoes(txt).get("Handoff", "").strip()
            if not gate or not ho:
                return negar("task DONE exige `gate: PASS` e `## Handoff` preenchido — use `feature.py task marcar` "
                             "depois da verificação.")
        return 0
    return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    return decidir(sys.stdin.read())


if __name__ == "__main__":
    sys.exit(main())
