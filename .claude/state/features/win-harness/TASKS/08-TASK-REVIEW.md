# 08-TASK-REVIEW — Revisão isolada da feature

id: 08-TASK-REVIEW
feature: win-harness
tipo: REVIEW
grupo: —
agente: revisor isolado (/revisor, sem escrita)
CA: CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07, CA-08, CA-09, CA-10, CA-11, CA-12, CA-13, CA-14
depends: 07-TASK-QA (revisa sobre o portão verde e a matriz da QA)
status: IN_PROGRESS
gate: FAIL

## Goal
Revisar o diff da cópia de trabalho contra o HEAD, os 14 CAs, o oráculo congelado e as evidências da QA; atenção a
guard que passou a deixar passar algo (falha aberta), mudança de comportamento fora do Windows, asserção
enfraquecida e termo privado. Veredito APPROVED ou CHANGES_REQUESTED. NÃO alterar nenhum arquivo.

## Contexto
FEATURE.md (14 CAs, RNF-02 falha fechada), Handoffs das tasks 02–06 e da 07, `portao.out` dos dois ambientes.

## Subtasks
1. Matriz CA → evidência (comando executado, não alegado).
2. Findings classificados (BLOQUEANTE/MENOR · REGRESSÃO/PRÉ-EXISTENTE · CONFIRMADO/SUSPEITA).
3. Veredito.

## Invariants
- Só leitura; cada finding com `arquivo:linha` e como reproduzir.

## Scope IN / OUT
IN: diff, oráculo, evidências. OUT: corrigir (volta ao corretor pelo tech-lead).

## Arquivos permitidos
- `.claude/state/features/win-harness/TASKS/08-TASK-REVIEW.md`

## AC
- Veredito registrado com a matriz e os findings; nenhum BLOQUEANTE aberto para APPROVED.

## DoD
- Handoff com o veredito; Aceite Review proposto.

## Verificação
```bash
python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -v
```

## Handoff
- Revisor: general-purpose · opus (70 turnos), instância nova que nunca executou nada na feature → APPROVED.
  Independência: revisão por instância isolada, não humana. Snapshot: não escreveu na cópia nem no projeto.
- Matriz: CA-01..CA-14 PASS (CA-01..12 rodados pelo revisor no Windows sem atalho, 50 OK; WSL CA-03/05/06/08/09/11/12;
  CA-13 pela saída do portão Windows; CA-14 pelo portão WSL + reexecução parcial). RNF-02: diferencial de 43.680
  comandos Bash guard_git HEAD × cópia, nenhum negado passou a passar; os 5 hooks pelo lançador saem 2 sem interpretador
  (no HEAD: 127 = aberto). Ramo POSIX igual ao HEAD salvo as mudanças intencionais do CA-08. Nenhum `def`/função
  removido; oráculo íntegro (sha recalculado = 540e1eccf037…); privacidade 0 nos 28 tocados.
- Findings MENOR (nenhum BLOQUEANTE):
  1. REGRESSÃO `e2e.py:121-123` — `e2e.py regua` usa o `pythons` cru (dict) → "17 suítes × windows e posix"; deveria
     usar `pythons_da_maquina()` (a skill e2e-loop manda rodar esse comando).
  2. REGRESSÃO `script-aprovacao.sh:38` — `qp()` não dobra aspas tipográficas (‘ ’ ‚ ‛), que o PowerShell trata como
     aspas: `--por`/`--criterio`/`--oraculo` com apóstrofo tipográfico gera `.ps1` quebrado.
  3. REGRESSÃO `tests/test_harness_dev.py:537` — no POSIX, a sintaxe do `aprovar-<f>.sh` passou de `sh -n` para
     `bash -n` (bashismo passaria e quebraria no dash).
  4. REGRESSÃO `ac/hook_aprovacao.py:76` (fora do escopo, motor) — `APROVAR_RE` só casa `aprovar-*.sh`; o agente pode
     invocar o `.ps1` de aprovação (a senha continua sendo a trava) → B-18 / auto-correcao.
  5. REGRESSÃO skills `fechar-feature/SKILL.md:112-113,121` e `auto-correcao/SKILL.md:74` chamam `campanha.py fechar`
     sem `--qualidade` (recusa antes do motor, sem estado gravado; o Passo 2 do fechamento precisa do argumento).
  6. PRÉ-EXISTENTE docs: `.claude/CLAUDE.md:56,63`, `e2e-loop/SKILL.md:19`, `fechar-feature/SKILL.md:86,107`,
     `feature.py:604,856`, `tech-lead/SKILL.md` e `auto-correcao/SKILL.md` citam `.sh` de aprovação e "2 Pythons".
  7. SUSPEITA `_py.sh:22` — descarta todo caminho sob WindowsApps, inclusive um Python da Microsoft Store funcional
     (falha fechada; RNF-02 preservado).
  8. PRÉ-EXISTENTE `_comum.sh` — o vivo tem a F15 não commitada sobreposta às edições da cópia: o `portar.sh` vai dar
     CONFLITO nesse arquivo; resolver tomando a cópia (que já absorve a F15) e rodar o portão de novo com `--src .`.
  9. SUSPEITA `PYTHONUTF8=1` exportado pelo `_comum.sh` a todo subprocesso do portão: no Windows as suítes do produto
     rodariam em UTF-8 e poderiam esconder bug de cp1252 em `scripts/` (B-14).
