"""Oráculo de VIVACIDADE das máquinas (bug real reportado pelo founder em 2026-10-03: delegação em ESCALATED
ficava trancada — nenhuma transição saía dela). Nenhum estado pode ser beco sem saída por acidente.

Regras:
1. Todo estado sem transição de saída tem de estar declarado em `terminal` da máquina (ou a máquina é conduzida
   por outra via `drives_task` / é a sessão ociosa).
2. Estados que significam "esperando decisão humana" NUNCA são terminais e têm saída para retomar, trocar de agente
   e descartar: delegação ESCALATED e ABSTAINED.
3. Todo estado é alcançável a partir do inicial.
4. (M5, campanha-M5) O modo autônomo `mandato` mora em `machines` e cumpre 1–3; `to: "^"` (volta ao estado de onde
   veio) é expandido para os estados que levam à origem. AWAITING_HUMAN e PAUSED do mandato nunca são terminais;
   AWAITING_HUMAN sai para retomar (RUNNING), emendar (PROPOSED), encerrar (WRAPPING_UP) e abortar (ABORTED).
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, SCRIPTS)
from cslib import json5io  # noqa: E402

MACHINES = os.path.join(SCRIPTS, "harness", "machines.json5")
AGUARDANDO_HUMANO = {"delegation": {"ESCALATED", "ABSTAINED"}}
# M5: estados de espera do mandato e as saídas mínimas da espera humana
MANDATO_ESPERA = {"AWAITING_HUMAN", "PAUSED"}
MANDATO_SAIDAS_HUMANAS = {"RUNNING", "PROPOSED", "WRAPPING_UP", "ABORTED"}
# máquinas cujos estados são escritos por outra máquina (sem transições próprias) ou estado ocioso legítimo
CONDUZIDAS = {"task"}
OCIOSOS = {("session", "IDLE")}


def load():
    return json5io.read(MACHINES)["machines"]


def edges(mv):
    tr = mv.get("transitions", {})
    items = tr.items() if isinstance(tr, dict) else [(t.get("name"), t) for t in tr]
    raw = []
    for name, t in items:
        if not isinstance(t, dict):
            continue
        fr = t.get("from")
        for f in (fr if isinstance(fr, list) else [fr]):
            raw.append((name, f, t.get("to")))
    into = {}  # estado → origens das transições que levam a ele (para expandir "^")
    for name, f, to in raw:
        if to not in ("=", "^"):
            into.setdefault(to, set()).add(f)
    out = []
    for name, f, to in raw:
        if to == "^":
            for prev in sorted(x for x in into.get(f, ()) if x is not None):
                out.append((name, f, prev))
        else:
            out.append((name, f, f if to == "=" else to))
    return out


class VivacidadeTest(unittest.TestCase):
    def test_sem_beco_sem_saida_acidental(self):
        for name, mv in load().items():
            if name in CONDUZIDAS:
                continue
            terminal = set(mv.get("terminal") or [])
            com_saida = {f for _, f, _ in edges(mv)}
            for s in mv.get("states", []):
                if s in com_saida or s in terminal or (name, s) in OCIOSOS:
                    continue
                self.fail("%s.%s não tem transição de saída e não está declarado terminal" % (name, s))

    def test_aguardando_humano_nao_e_terminal_e_tem_saidas(self):
        machines = load()
        for name, estados in AGUARDANDO_HUMANO.items():
            mv = machines[name]
            terminal = set(mv.get("terminal") or [])
            for s in estados:
                self.assertNotIn(s, terminal, "%s.%s espera decisão humana: não pode ser terminal" % (name, s))
                destinos = {to for _, f, to in edges(mv) if f == s}
                self.assertTrue(destinos, "%s.%s sem saída (trancado)" % (name, s))
                # retomar (volta a BRIEFED), trocar de agente (REROUTED) e descartar (um terminal)
                self.assertIn("BRIEFED", destinos, "%s.%s precisa permitir retomar" % (name, s))
                self.assertIn("REROUTED", destinos, "%s.%s precisa permitir trocar de agente" % (name, s))
                self.assertTrue(destinos & terminal, "%s.%s precisa permitir descartar (ir a um terminal)" % (name, s))

    def test_todo_estado_alcancavel(self):
        for name, mv in load().items():
            if name in CONDUZIDAS or not mv.get("initial"):
                continue
            seen, stack = {mv["initial"]}, [mv["initial"]]
            es = edges(mv)
            while stack:
                cur = stack.pop()
                for _, f, to in es:
                    if f == cur and to not in seen:
                        seen.add(to)
                        stack.append(to)
            inalcancaveis = set(mv.get("states", [])) - seen
            self.assertFalse(inalcancaveis, "%s: estados inalcançáveis %s" % (name, sorted(inalcancaveis)))


    def test_mandato_m5_presente_e_espera_nunca_tranca(self):
        machines = load()
        self.assertIn("mandato", machines, "M5 `mandato` mora em machines.machines (coberta por este oráculo)")
        mv = machines["mandato"]
        terminal = set(mv.get("terminal") or [])
        es = edges(mv)
        for s in MANDATO_ESPERA:
            self.assertIn(s, mv.get("states") or [], "mandato.%s declarado" % s)
            self.assertNotIn(s, terminal, "mandato.%s nunca é terminal" % s)
            self.assertTrue({to for _, f, to in es if f == s}, "mandato.%s sem saída (trancado)" % s)
        destinos = {to for _, f, to in es if f == "AWAITING_HUMAN"}
        faltam = MANDATO_SAIDAS_HUMANAS - destinos
        self.assertFalse(faltam, "mandato.AWAITING_HUMAN sem saída para %s" % sorted(faltam))


if __name__ == "__main__":
    unittest.main()
