# 05-TASK-REGUA-PORTAO — Régua e portão com os Pythons da máquina; fechamento com nota

id: 05-TASK-REGUA-PORTAO
feature: win-harness
tipo: CORRECAO
grupo: G2
agente: corretor (papel; o executor real e o model passado vão para o Handoff)
CA: CA-06, CA-12
depends: 01-TASK-ORACULO (o oráculo congelado é a régua da correção), 02-TASK-LANCADOR-HOOKS (o portao.sh usa o PY do _comum.sh), 04-TASK-ESTADO-ENCODING (e2e.py e campanha.py dependem do stdio UTF-8 e da gravação em LF do estado_lib)
status: DONE
gate: PASS
complexidade: normal

## Goal
`regua.json` passa a ter a lista de Pythons por plataforma (Windows: candidatos `python3`, `python`, `py`; POSIX:
`python3`, `/usr/bin/python3`); `e2e.py` ganha o subcomando `pythons` (os encontrados, sem repetir o executável
resolvido, mínimo 1, senão exit 2) e o usa em `rodar`; `portao.sh` usa essa lista como padrão de `--pythons`;
`campanha.py fechar` exige `--qualidade P/T`, grava o grading e passa `--grading` ao `run record`. Atualizar a regra
dos "2 Pythons" em `.claude/CLAUDE.md` e na skill `e2e-loop` (só esse trecho). NÃO mudar a lista POSIX, NÃO
mudar o mapa de seleção da régua, NÃO tocar o motor.

## Contexto
CA-06, CA-12. Âncoras: `regua.json:3`; `e2e.py:111-140`; `portao.sh:16,24`; `campanha.py:116-150,172-177`;
`.claude/CLAUDE.md` (passo 5 do fluxo); `.claude/skills/e2e-loop/SKILL.md:19`. E2: F3, F14; B-18 (8).

## Subtasks
1. Rodar o oráculo `-k CA06 -k CA12` e ver falharem (RED).
2. `regua.json` + `e2e.py pythons` + `rodar`; `portao.sh` com o padrão vindo do `e2e.py pythons`.
3. `campanha.py fechar --qualidade`; texto do `CLAUDE.md` e da skill `e2e-loop`.
4. Rodar o oráculo desta task e a suíte harness-dev (GREEN).

## Invariants
- No WSL/macOS/Linux a régua roda `python3` e `/usr/bin/python3`, como hoje.
- `--pythons` explícito no `portao.sh`/`e2e.py` continua vencendo. Nenhum `def` existente some.

## Scope IN / OUT
IN: régua, portão, fechamento da campanha, 2 trechos de texto. OUT: seleção de suítes, motor `ac/`, skills além da
`e2e-loop`.

## Arquivos permitidos
- `.claude/tools/regua.json`
- `.claude/tools/e2e.py`
- `.claude/tools/portao.sh`
- `.claude/tools/campanha.py`
- `.claude/CLAUDE.md`
- `.claude/skills/e2e-loop/SKILL.md`

## AC
- `-k CA06` e `-k CA12` verdes no Windows e no WSL.

## DoD
- Régua seletiva verde; diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -k CA06 -k CA12
```

## Handoff
- Executor: general-purpose · sonnet (17 turnos), ciclo 1. Revisor isolado: general-purpose · sonnet, instância
  distinta → APPROVED. Independência: executor e revisor instâncias distintas.
- Arquivos: `regua.json` (`pythons` por plataforma: windows `python3`/`python`/`py`, posix `python3`/`/usr/bin/python3`);
  `e2e.py` (`pythons_da_maquina()`, subcomando `pythons [--json|--brief]`, exit 2 sem Python; `rodar`/`regua` usam a
  lista; `--pythons` vence); `portao.sh` (padrão de `--pythons` vem de `e2e.py pythons --brief`, `die` se vazio);
  `campanha.py` (`qualidade()`; `fechar --qualidade P/T` obrigatório, recusa antes do motor; grading em
  `campanhas/<f>/.auto-correcao/grading-fechamento.json` passado a `run record --grading`); `.claude/CLAUDE.md` e
  skill `e2e-loop` só no trecho dos "2 Pythons".
- Régua do tech-lead (cópia): oráculo Windows sem atalho `-k CA06 -k CA12` 11 OK (1 skip só-POSIX); `e2e.py pythons`
  no Windows sem atalho → `python`; WSL harness-dev 83/83 em python3 e /usr/bin/python3; WSL `e2e.py pythons` →
  `python3 /usr/bin/python3`; WSL `-k CA06 -k CA12 -k CA14` 14 OK (5 skips só-Windows); `def` sem remoção; privacidade 0.
- Ressalvas (MENOR, revisor): `e2e.py regua --json` passa a devolver a lista resolvida em `pythons` (não o valor bruto;
  sem consumidor afetado); `e2e.py pythons` roda cada candidato com timeout de 60 s.
