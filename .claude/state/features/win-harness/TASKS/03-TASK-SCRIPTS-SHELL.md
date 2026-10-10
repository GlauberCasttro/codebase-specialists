# 03-TASK-SCRIPTS-SHELL — carimbo, aprovação .ps1, /install por junção e package

id: 03-TASK-SCRIPTS-SHELL
feature: win-harness
tipo: CORRECAO
grupo: G1
agente: corretor (papel; o executor real e o model passado vão para o Handoff)
CA: CA-08, CA-09, CA-10
depends: 01-TASK-ORACULO (o oráculo congelado é a régua da correção), 02-TASK-LANCADOR-HOOKS (usa o `_py.sh` e o `PY` do `_comum.sh`, e edita o mesmo `_comum.sh`)
status: IN_PROGRESS
gate: FAIL
complexidade: normal

## Goal
`carimbo.sh` chama o Python pelo lançador, imprime `python: <interpretador>` no `--brief` e conta as etapas da
campanha sem depender do encoding; `script-aprovacao.sh` gera `local/aprovar-<f>.ps1` no Windows (interpretador
resolvido, `throw` em `$LASTEXITCODE` ≠ 0 a cada passo) e o `.sh` de hoje fora dele; `instalar.sh` cria junção
(`mklink /J`) no Windows e a checagem do `_comum.sh` reconhece a junção; `package.sh` mantém o `$PY` (sujo, F15). NÃO
rodar o script de aprovação, NÃO mudar os 3 passos da aprovação, NÃO apagar instalação existente que não seja o link.

## Contexto
CA-08, CA-09, CA-10. Âncoras: `carimbo.sh:15,37,40-41,51,78`; `script-aprovacao.sh:30,38-40`; `instalar.sh:88`;
`_comum.sh:65,81`; `package.sh:24` (sujo). Referência do `.ps1` esperado: `local/aprovar-win-bash.ps1` (escrito à
mão). E2: F9, F11, F12, F15; B-18 (4).

## Subtasks
1. Rodar o oráculo `-k CA08`, `-k CA09`, `-k CA10` e ver falharem (RED).
2. `carimbo.sh`: lançador, linha `python:`, contagem robusta; `script-aprovacao.sh`: ramo Windows gerando `.ps1`.
3. `instalar.sh` + `_comum.sh`: junção no Windows e reconhecimento dela; `package.sh` com `$PY`.
4. Rodar o oráculo `-k CA08 -k CA09 -k CA10` e a suíte harness-dev (GREEN, sem falha nova).

## Invariants
- Fora do Windows, `script-aprovacao.sh` e `instalar.sh` fazem exatamente o de hoje.
- O `.ps1` gerado nunca contém senha nem a pede fora dos comandos do motor.
- Nenhum `def`/função de shell existente some.

## Scope IN / OUT
IN: os 4 scripts e a checagem do link em `_comum.sh`. OUT: lançador e hooks (task 02), régua/portão (task 05).

## Arquivos permitidos
- `.claude/tools/carimbo.sh`
- `.claude/tools/script-aprovacao.sh`
- `.claude/tools/instalar.sh`
- `.claude/tools/package.sh`
- `.claude/tools/_comum.sh`

## AC
- `-k CA08`, `-k CA09` e `-k CA10` verdes no Windows; no WSL, os mesmos testes passam ou pulam com motivo.

## DoD
- Régua seletiva verde; diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -k CA08 -k CA09 -k CA10
```

## Handoff
- Executor: general-purpose · sonnet (25 turnos), ciclo 1. Revisor isolado: general-purpose · sonnet, instância
  distinta → APPROVED. Independência: executor e revisor instâncias distintas.
- Arquivos: `carimbo.sh` (Python pelo lançador; linha `python: <interpretador>` no `--brief`; etapa e contagem
  feitas/total por bytes, sem depender do encoding); `script-aprovacao.sh` (Windows → `local/aprovar-<f>.ps1` com BOM,
  interpretador resolvido, 3 passos e `throw` em `$LASTEXITCODE` ≠ 0; POSIX → o `.sh` de hoje); `instalar.sh` (Windows:
  junção `cmd /c mklink /J`; junção antiga só sai por `rmdir`, destino intacto; pasta comum → backup como hoje);
  `_comum.sh` (`cs_windows`, `eh_juncao`, `eh_link`; `instalado_estado` reconhece junção); `package.sh` sem mudança
  além da base F15.
- Régua do tech-lead (cópia): oráculo Windows sem atalho `-k CA08 -k CA09 -k CA10` 7 OK (1 skip só-POSIX); WSL
  harness-dev 83/83 em python3 e /usr/bin/python3; WSL `-k CA08 -k CA09 -k CA14` 8 OK (1 skip); `.ps1` do dry-run
  aceito pelo parser do PowerShell 5.1 (0 erros, 3 conferências de LASTEXITCODE; nunca executado); `bash -n` ok;
  nenhuma função de shell removida; privacidade 0; perfil real não tocado.
- Ressalvas (MENOR, revisor): carimbo.sh ainda cita `python3 .claude/tools/sessao.py briefing` como texto na linha do
  frescor; `date '+%Z'` vazio no Git Bash (cosmético no cabeçalho do .ps1); a contagem passou a incluir etapas parciais
  no total (mais fiel ao `ac.py status`). O executor não mediu o RED antes de editar (declarado; RED do oráculo medido
  pelo tech-lead na task 01).
