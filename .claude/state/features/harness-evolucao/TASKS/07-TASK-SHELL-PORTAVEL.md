# 07-TASK-SHELL-PORTAVEL — Motor executa verify, aceite e selftest sem /bin/sh fixo

id: 07-TASK-SHELL-PORTAVEL
feature: harness-evolucao
tipo: CORRECAO
grupo: G2
agente: corretor (papel; o executor real e o model passado vão para o Handoff)
CA: CA-15
depends: 01-TASK-ORACULO (o oráculo congelado é a régua da correção)
status: IN_PROGRESS
gate: FAIL
complexidade: normal

## Goal
`engine.run_cmd` e `selftest` resolvem o shell por plataforma (POSIX: `/bin/sh`; Windows: `sh` do Git encontrado no
PATH ou no local padrão do Git for Windows; sem shell: erro de ambiente explícito) mantendo o contrato atual (`&&`,
aspas e pipes funcionam, exit real propagado, 127 só quando o programa não existe, sha da saída). O DoR da feature
trata 127 como erro de ambiente, não como "aceite vermelho". NÃO mudar a semântica de verify/aceite no Linux, NÃO
tocar o `mem.check` (é a 04, outro grupo).

## Contexto
CA-15. Âncoras: `scripts/harness/engine/engine.py:103-122` (`argv = ["/bin/sh", "-c", cmd]`),
`scripts/harness/engine/selftest.py:97`, `scripts/harness/engine/tree.py:620-628` (DoR aceita 127); achado F30 (B-14,
parte do motor).

## Subtasks
1. Rodar o oráculo (`-k CA15`) no Windows nativo e ver falhar (RED).
2. Resolver de shell por plataforma em `engine.py` e uso no `selftest.py`; DoR distinguindo 127.
3. Testes em `scripts/harness/tests/test_evolucao_arvore.py` (comando com pipe e `&&` no Windows e no Linux; 127 de
   programa inexistente).
4. Rodar o oráculo e a suíte `harness` no Windows nativo e no WSL nos 2 Pythons.

## Invariants
- No Linux o argv continua `/bin/sh -c` (sem regressão); o exit real e o sha da saída continuam registrados.

## Scope IN / OUT
IN: execução de comandos do motor. OUT: `mem.check` (04), o resto do B-14 (pty/termios, symlink, fcntl).

## Arquivos permitidos
- `scripts/harness/engine/engine.py`
- `scripts/harness/engine/selftest.py`
- `scripts/harness/engine/tree.py`
- `scripts/harness/tests/test_evolucao_arvore.py`

## AC
- No Windows nativo, `cs-state verify` de uma task com comando real roda e devolve o exit real; o DoR recusa aceite
  que sai 127 como erro de ambiente.

## DoD
- Régua seletiva verde (harness) no WSL nos 2 Pythons e no Windows nativo sem falha por `/bin/sh`; Handoff preenchido.

## Verificação
```bash
python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA15
```

## Handoff
