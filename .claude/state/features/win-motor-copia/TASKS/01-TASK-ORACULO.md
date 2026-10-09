# 01-TASK-ORACULO — Oráculo da cópia do motor corrigido

id: 01-TASK-ORACULO
feature: win-motor-copia
tipo: ORACULO
grupo: —
agente: autor do oráculo (agente SEPARADO do corretor; nunca vê a correção)
CA: CA-01, CA-02, CA-03, CA-04, CA-05
depends: —
status: DONE
gate: PASS

## Goal
Escrever `ESPEC.md` + testes em `campanhas/win-motor-copia/oraculo/` que provam os 5 CAs e FALHAM hoje pelo motivo
do defeito; o tech-lead congela (`oracle freeze` com TODOS os arquivos). NÃO escrever protótipo de correção, NÃO
tocar `.claude/tools/ac/`, `.claude/settings.json` nem `.gitattributes`, NÃO rodar `gate`/`preauth`/`frase`.

## Contexto
CA-01..CA-05 do FEATURE.md. Âncoras da E2: F1 `.claude/tools/ac/frase.py:187-239`, F2 `ac.py:952`/`:929`, F3
`hook_aprovacao.py:259` + `.claude/settings.json:15`, F4 `.claude/tools/tests/test_harness_dev.py:451`. Fonte de
comparação: `git -C <irmão auto-correcao> show 30e2da6:<arq>` (caminho do irmão por variável/argumento, nunca fixo).
Pode reaproveitar casos dos oráculos `campanhas/win-motor` e `campanhas/win-hook` do `auto-correcao`.

## Subtasks
1. Ler FEATURE.md, a E2 e os oráculos win-motor/win-hook da fonte; fixar no ESPEC como cada CA é verificado.
2. Escrever `test_win_motor_copia.py` com classes CA01..CA05 (motor via `ORACULO_SCRIPTS` ou `ORACULO_SKILL`, com
   fallback para `.claude/tools/ac/` do projeto).
3. Rodar no Windows nativo (sem `PYTHONUTF8`) e no WSL; registrar no ESPEC a tabela teste × resultado hoje.

## Invariants
- Cada teste de CA falha hoje pelo motivo do defeito (não por erro de import); guardas de regressão passam hoje.
- Temporários em `tempfile.mkdtemp()` apagados; HOME/USERPROFILE/AC_FRASE_FILE/AC_AUDIT_LOG isolados.

## Scope IN / OUT
IN: os testes e o ESPEC do oráculo. OUT: qualquer arquivo do motor, do harness ou do produto.

## Arquivos permitidos
- `campanhas/win-motor-copia/oraculo/ESPEC.md`
- `campanhas/win-motor-copia/oraculo/test_win_motor_copia.py`

## AC
- 5 classes de CA presentes; todas falham hoje; o ESPEC traz a tabela de hoje nos 2 ambientes.

## DoD
- Oráculo congelado pelo tech-lead (`oracle freeze --file … --file …`); Handoff preenchido.

## Verificação
```bash
python -m unittest discover -s campanhas/win-motor-copia/oraculo -p "test_*.py" -v
```

## Handoff
- Executor real: subagente general-purpose, model opus (persona oraculista; agente separado, nunca viu cópia de
  trabalho — não existia). Arquivos: `campanhas/win-motor-copia/oraculo/ESPEC.md`, `test_win_motor_copia.py` (LF).
- Resultado: 21 testes (16 de CA em 5 classes CA01..CA05 + 5 guardas). Hoje, HEAD `e8a9b93`: Windows (3.12, sem
  PYTHONUTF8) `Ran 21 · FAILED (failures=26)` — conferido pelo tech-lead; WSL (3.10) idem (relatório do oraculista).
  Motivos = achados da E2 (F1 `_windows` ausente, F2 UnicodeEncodeError, F3 matcher Bash/decide sem PowerShell/
  selftest 83, F4 sha CRLF, ORIGEM `da3ea45`). Guardas 5/5 verdes. Entrega simulada fora do repo: 21/21 nos 2.
- Congelado pelo tech-lead: `oracle freeze` → `afeac8b409ff` (2 arquivos); `oracle verify` intacto.
- Limites: CA05 na raiz viva depende dos `references/*.json5` em LF (normalizado no ambiente em 2026-10-08);
  `test_help_e_init_com_ciclo_embutido` dá UnicodeDecodeError no Windows sem PYTHONUTF8 (B-15).
