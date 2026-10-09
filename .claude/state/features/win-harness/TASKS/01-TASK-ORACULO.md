# 01-TASK-ORACULO — Oráculo dos 14 CAs, por agente separado

id: 01-TASK-ORACULO
feature: win-harness
tipo: ORACULO
grupo: —
agente: oraculista (persona via /rh; nunca o corretor)
CA: CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07, CA-08, CA-09, CA-10, CA-11, CA-12, CA-13, CA-14
depends: —
status: DONE
gate: PASS

## Goal
Escrever o ESPEC e os testes que provam os 14 CAs do FEATURE.md, um `class TestCA<NN>` por CA (selecionável por
`-k CA<NN>`), rodando contra a skill apontada por `CS_DEV_SKILL_DIR` (padrão: a raiz do projeto). Os testes têm de
FALHAR no HEAD de hoje nos CAs que pedem mudança (CA-01..CA-13) e passar no CA-14 no WSL. NÃO corrigir nada do
harness, NÃO escrever fora de `campanhas/win-harness/oraculo/`, NÃO depender do atalho `~/bin/python3`.

## Contexto
CA-01..CA-14 do FEATURE.md. Âncoras da E2: `.claude/settings.json:5,19,29,39,49`, `regua.json:3`, `portao.sh:24`,
`estado_lib.py:115,122`, `guard_privacidade.py:32-33`, `feature.py:556-558`, `carimbo.sh:40-41`,
`campanha.py:123-125`, `package_validar.py:82`, `instalar.sh:88`, `script-aprovacao.sh:38-40`. Ambiente "sem atalho"
= PATH montado pelo teste só com a pasta do Python real (`sys.executable`), Git Bash e `System32`, sem `PYTHONUTF8`.

## Subtasks
1. ESPEC.md: para cada CA, o ambiente simulado (PATH, `os.name`, perfil temporário), a entrada e o resultado esperado.
2. `test_win_harness.py`: helpers de ambiente (PATH sem `python3`, perfil temporário com `HOME` e `USERPROFILE`,
   campanha temporária) e um `TestCA<NN>` por CA; o que só existe no Windows pula com motivo fora dele, e vice-versa.
3. Rodar no HEAD no Windows (Git Bash e PowerShell) e no WSL; anotar no Handoff quais CAs falham (RED esperado).

## Invariants
- Só stdlib, Python 3.9+; tudo em diretórios temporários; nada escrito no projeto nem no perfil real.
- Nada privado: pessoa = "Ana"; caminhos com `~` ou variável; placeholders `C:\Users\x\`.

## Scope IN / OUT
IN: ESPEC e testes do oráculo. OUT: qualquer arquivo do harness ou do produto; suítes existentes.

## Arquivos permitidos
- `campanhas/win-harness/oraculo/ESPEC.md`
- `campanhas/win-harness/oraculo/test_win_harness.py`

## AC
- 14 classes `TestCA01`..`TestCA14`; no HEAD: CA-01..CA-13 falham no Windows nativo, CA-14 passa no WSL.
- Nenhum teste passa trivialmente (cada um tem ao menos uma asserção sobre saída, exit ou arquivo gravado).

## DoD
- O tech-lead congela com `oracle freeze` (os 2 arquivos); Handoff com o RED medido por CA nos dois ambientes.

## Verificação
```bash
python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -v
```

## Handoff
- Executor: rh-oraculista-01-TASK-ORACULO-1 (general-purpose, opus; ficha `local/tech-lead/win-harness/ficha-oraculista.txt`,
  conferida por `rh.py conferir`). Custo: 51 turnos, contexto somado ~9,0 M (`logs/custo.jsonl`).
- Escrita conferida por snapshot (`tech_lead.py snap --comparar`): só `campanhas/win-harness/oraculo/ESPEC.md` e
  `test_win_harness.py`; guard de privacidade 0 achados.
- Oráculo: 14 classes `TestCA01..TestCA14`, 55 testes, cada classe com `test_calibracao_*` (saída vazia reprova,
  saída boa conhecida passa).
- RED reproduzido pelo tech-lead no Windows sem atalho (`local/tech-lead/win-harness/oraculo-red-windows.out`):
  Ran 55 · failures=73 (com subtestes) · skipped=5; falhas por CA: 01:12 02:16 03:3 04:17 05:5 06:5 07:4 08:1 09:1
  10:1 11:5 12:2 13:1; nenhuma calibração falha. CA-14 no WSL: Ran 3 · OK (`oraculo-ca14-wsl.out`).
- Congelado: `oracle freeze` com os 2 arquivos → `540e1eccf037`; `oracle verify` intacto.
- Achados do oraculista: CA-04 mede "decodifica como UTF-8" (15 de 16 tools falham hoje, mais estrito que a E2);
  `conferir_commit` já usa o `argv[0]` de `bash_exe()` (PRÉ-EXISTENTE; o teste fica vermelho pelo cenário do alias).
- Lacunas declaradas: PATH real dos hooks no Claude Code não medido (simulado pelo pior caso); CA-10 usa stub de
  `package.sh`; CA-13 hoje falha antes da suíte (em `e2e.py pythons`); macOS não rodado.
