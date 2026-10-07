#!/usr/bin/env python3
"""exige-modelo.py — hook PreToolUse (Agent|Task) do harness de desenvolvimento: despacho de TASK exige `model`.

Se a `description` do despacho cita um ID de task (`NN-TASK-…`, `TASK|BUG|GAP|DEBT-…`) e o `model` está ausente,
vazio ou `inherit`, bloqueia (exit 2; a mensagem vai ao modelo pelo stderr, cita o ID e NUNCA o prompt). O modelo
certo sai de `python3 .claude/tools/tech_lead.py modelo --papel P [--ciclo N] [--task ARQ]` (tabela roteamento.json).
Todo o resto passa (exit 0), inclusive payload inválido: este hook roteia custo, não é guard de segurança.
Uso: echo '<payload>' | python3 exige-modelo.py · --help
"""
import json
import re
import sys

ID = re.compile(r"\b(?:\d{2}-)?(?:TASK|BUG|GAP|DEBT)-[A-Z0-9][A-Z0-9-]*")


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    try:
        d = json.loads(sys.stdin.read())
    except Exception:  # noqa: BLE001 — payload inválido não é assunto deste hook
        return 0
    if not isinstance(d, dict) or d.get("tool_name") not in ("Agent", "Task"):
        return 0
    ti = d.get("tool_input") or {}
    if not isinstance(ti, dict):
        return 0
    m = ID.search(str(ti.get("description") or ""))
    if not m:
        return 0
    modelo = ti.get("model")
    if isinstance(modelo, str) and modelo.strip() and modelo.strip() != "inherit":
        return 0
    sys.stderr.write("exige-modelo: o despacho da task %s precisa de `model` explícito (haiku|sonnet|opus) — rode "
                     "`python3 .claude/tools/tech_lead.py modelo --papel <papel> --task <arquivo da task>` e passe o "
                     "modelo devolvido; depois registre o custo com custo.py registrar.\n" % m.group(0))
    return 2


if __name__ == "__main__":
    sys.exit(main())
