# 01-TASK-ORACULO — Oráculo da escolha do bash no fechamento

id: 01-TASK-ORACULO
feature: win-bash
tipo: ORACULO
grupo: —
agente: autor do oráculo (agente SEPARADO do corretor; nunca vê a correção)
CA: CA-01, CA-02, CA-03, CA-04, CA-05
depends: —
status: PENDENTE
gate: PENDENTE

## Goal
Escrever `ESPEC.md` + testes em `campanhas/win-bash/oraculo/` que provam os 5 CAs e FALHAM hoje pelo motivo do
defeito (`feature.bash_exe` não existe; `conferir_commit` cai no WSL); o tech-lead congela. NÃO escrever protótipo de
correção, NÃO tocar `.claude/tools/`, NÃO rodar `gate`/`preauth`/`frase`.

## Contexto
CA-01..CA-05 do FEATURE.md. Âncora: `.claude/tools/feature.py:544-550` (`conferir_commit`), `:53` (`Recusa`); E2 F1/F2.
Contrato de nomes: `feature.bash_exe()` → str; recusa = `feature.Recusa`. Os CAs 01–04 com mocks (`os.name`,
`shutil.which`, `os.path.isfile`, `SystemRoot`); o CA-05 real (sem mock), na máquina onde roda.

## Subtasks
1. Ler FEATURE.md, a E2 e o `feature.py` (só as faixas citadas); fixar no ESPEC como cada CA é verificado.
2. Escrever `test_win_bash.py` com classes CA01..CA05, importando `feature.py` de `<raiz>/.claude/tools/`
   (`ORACULO_SKILL`, senão `CS_SKILL_DIR`, senão a raiz do projeto).
3. Rodar no Windows nativo (sem `PYTHONUTF8`) e no WSL; registrar no ESPEC a tabela teste × resultado hoje.

## Invariants
- Cada teste de CA falha hoje pelo motivo do defeito (não por erro de import do próprio teste).
- Nenhum teste escreve fora de `tempfile.mkdtemp()`.

## Scope IN / OUT
IN: testes e ESPEC do oráculo. OUT: qualquer arquivo do harness ou do produto.

## Arquivos permitidos
- `campanhas/win-bash/oraculo/ESPEC.md`
- `campanhas/win-bash/oraculo/test_win_bash.py`

## AC
- 5 classes de CA; todas falham hoje; o ESPEC traz a tabela de hoje nos 2 ambientes.

## DoD
- Oráculo congelado pelo tech-lead (`oracle freeze --file … --file …`); Handoff preenchido.

## Verificação
```bash
python -m unittest discover -s campanhas/win-bash/oraculo -p "test_*.py" -v
```

## Handoff
