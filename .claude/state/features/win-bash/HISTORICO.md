# HISTORICO — feature win-bash

<!-- APPEND-ONLY: [NOTA] | [PASS] | [REJECT]; escrito pelo feature.py e pelo tech-lead, em série -->

## [NOTA] 2026-10-08T22:22:40-0300 — Abertura da feature win-bash
- campanha: campanhas/win-bash (ac.py init; escopo: .claude/tools/feature.py, .claude/tools/tests/test_feature.py)
- tasks: 4 · primeira: 01-TASK-ORACULO
- investigação aprovada (E2):

    # E2 — Investigação medida
    
    ## Inventário
    - Chamadas de shell pelo nome nas ferramentas do harness (`grep -n -E '\[\s*"(bash|sh)"' .claude/tools/*.py`): 1 —
      `.claude/tools/feature.py:548` (`conferir_commit`). Nas suítes de teste do harness: 13 (`.claude/tools/tests/*.py`).
    - Quem chama `conferir_commit` (`grep -n 'conferir_commit(' .claude/tools/feature.py`): 2 — `:580` (gate
      `fechar check`, também usado por `fechar archive`) e `:840` (`fechar commit`).
    - `feature.py` já importa `shutil`, `os`, `subprocess`, `sys` (linhas 35–42): a correção não precisa de import novo.
    - Testes de `feature.py` (`.claude/tools/tests/test_feature.py`): 13 testes; nenhum exercita `conferir_commit` nem a
      escolha do bash (a linha 123 só confere que `fechar commit` aparece no `--help`).
    
    ## Classificação
    - muda: 1 — `feature.py:548` passa a usar o caminho do bash resolvido por uma função nova (decisão 2 da E1).
    - não muda: 2 — as chamadas `:580` e `:840` (continuam chamando `conferir_commit`); e as 13 dos testes (B-15).
    - congelado: nenhum oráculo de campanha cobre este caminho.
    - Soma: 1 + 2 = 3 chamadas no `feature.py`; as 13 dos testes ficam fora da soma (B-15).
    
    ## Exclusões
    - Fora: `estado_lib.py` e os demais tools (`portao.sh`, `portar.sh` etc. são scripts bash, rodados pelo próprio bash
      do usuário — não passam por esta busca); as 13 chamadas nas suítes do harness (B-15); macOS/Linux (lá a busca é o
      PATH e não existe o `System32`).
    
    ## Achados
    - F1 — `.claude/tools/feature.py:548` — `subprocess.run(["bash", …])` no Windows executa `C:\Windows\System32\bash.exe`
      (WSL): `fechar check win-motor-copia` → `conferir_commit: /bin/bash: C:Users<usuário>…conferir-commit.sh: No such file
      or directory` (medido 2026-10-08), mesmo com o `conferir-commit.sh` passando pelo Git Bash (`OK: 6 arquivo(s)
      idênticos ao portão VERDE`).
    - F2 — medição `local/criar-win-bash/medir.py` (Python 3.12.7, Git Bash e PowerShell): `shutil.which("bash")` =
      `C:\Program Files\Git\usr\bin\bash.EXE`; `subprocess.run(["bash","-c",…])` → rc 2, sem saída (WSL). O resolver por
      `shutil.which` resolve nesta máquina.
    - F3 — o Python 3.12 não procura o executável na pasta atual (medido: rodar o `feature.py` com cwd na pasta do Git
      Bash continua caindo no WSL) — não há contorno de ambiente limpo; é código.
    - F4 (DESCARTADO por medição) — suspeita de outras chamadas pelo nome nos tools: só a `:548` (o grep acima).
    
    ## Enforcement existente
    - Nenhum teste cobre `conferir_commit` nem a escolha do bash (`test_feature.py`, 13 testes; `test_harness_dev.py`
      só confere o `conferir-commit.sh` direto pelo bash da suíte).
    - O gate do fechamento (`fechar check`) é a prova de ponta a ponta: hoje reprova `win-motor-copia` só por F1.

## [NOTA] 2026-10-09 — redação de privacidade na E2 aprovada
A proposta E2 aprovada pelo founder ("ok", sha de aprovação 27c9ee47eeb7…) citava o erro literal com o nome do usuário
da máquina num caminho; o guard de privacidade recusou o commit do estado. Por decisão do founder (2026-10-09,
"sigo sua recomendacao"), o termo foi trocado por `<usuário>` em `propostas/E2.md:25` e na cópia acima; nada mais
mudou. sha do arquivo antes: b7885b3dd396…; depois: 4900f012fca9…
