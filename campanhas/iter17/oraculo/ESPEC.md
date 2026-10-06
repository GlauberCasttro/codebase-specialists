# ESPEC — frente iter17: `/install` (a skill instalada é o PACOTE)

Decisão do founder (fixa): numa máquina nova ele não digita comando de terminal. A versão INSTALADA da skill é o
PACOTE `dist/codebase-specialists` (gerado e validado pelo `package`), não o projeto inteiro.

Oráculo: `test_install.py` (esta pasta), unittest puro, Python 3.9+, nos 2 Pythons (`python3`, `/usr/bin/python3`).
Rodar de dentro desta pasta: `python3 -m unittest -v test_install`.

## Isolamento (como o oráculo testa)

- Projeto sob teste: `$CS_PROJETO`; senão `$CS_SKILL_DIR` se ele tiver `.claude/tools` (é o que o `portao.sh` passa
  para a cópia limpa); senão a raiz deste repositório.
- Cada teste de I1/I2 monta uma CÓPIA TEMPORÁRIA do projeto (sem `.git`, `local/`, `dist/`, `__pycache__`,
  `.auto-correcao/`), faz dela um repositório git novo com um commit (identidade "Ana"), e usa um `HOME` temporário
  (`GIT_CONFIG_NOSYSTEM=1`, `XDG_CONFIG_HOME` temporário, variáveis `CS_*`/`GIT_*` do ambiente removidas, stdin
  fechado: nada pode pedir senha). Nunca toca o HOME real nem o projeto sob teste.
- Commits que o oráculo faz na cópia usam `--no-verify` (não dependem dos termos privados desta máquina).
- "Não escreve nada" = hash igual, antes/depois, de `$HOME` inteiro e da árvore da cópia (caminho, modo, mtime,
  conteúdo; links sem seguir). De `.git/` só entra `hooks/` (o `git status` regrava o índice).
- I3 lê os textos direto do projeto sob teste.

## Contrato

### `.claude/tools/instalar.sh` (I1)

Uso: `bash .claude/tools/instalar.sh [--dry-run | --check | --help]`, de qualquer diretório (o projeto é o da
própria ferramenta). `--help` exit 0 e cita `--dry-run` e `--check`.

Sem opção, nesta ordem:
- **a) travas do git**: liga `pre-commit` e `commit-msg` (no diretório de hooks do `git rev-parse --git-path hooks`)
  com a linha que chama `.claude/tools/pre-commit.sh` (o que `instalar-hooks-git.sh` já faz), se faltarem.
  Idempotente. Trava ALHEIA (arquivo de hook que não chama o pre-commit.sh) nunca é sobrescrita; a que falta entra.
- **b) pacote**: gera e valida com `package.sh` (fonte: `git archive HEAD`). Falha do package ⇒ `instalar.sh` sai
  com exit != 0 e NÃO toca a instalação: `$HOME` idêntico, nenhum backup, e — se já havia uma instalação boa
  apontando para `dist/codebase-specialists` — ela continua funcionando com o MESMO pacote (mesmo `.origem`,
  `cs.py --help` exit 0). Ou seja: o pacote novo é montado/validado fora do lugar e só substitui o anterior se
  passar (o `package.sh` hoje apaga `dist/codebase-specialists` antes de validar).
- **c) link**: `$HOME/.claude/skills/codebase-specialists` vira link simbólico cujo `realpath` é
  `<projeto>/dist/codebase-specialists` (cria `$HOME/.claude/skills` se faltar). Se já existir ali algo que não é
  esse link (pasta, arquivo, link para outro lugar — inclusive o link antigo para o projeto inteiro): MOVE para
  `$HOME/.claude/skills-backup-<data>/codebase-specialists` (o link antigo vai como link, com o mesmo alvo; o alvo
  não é tocado), nunca apaga, e a saída cita o caminho (`skills-backup-`). Dois backups nunca se sobrescrevem
  (mesmo no mesmo dia/segundo). Se já é o link certo: não mexe (mesmo inode e mtime do link).
- **d) conferência depois**: `python3 <instalado>/scripts/cs.py --help` exit 0; `VERSION` instalada == `VERSION` do
  projeto (árvore de trabalho) — divergente ⇒ exit != 0 com a palavra `VERSION` na saída; o instalado não contém
  componente `.claude`, `campanhas`, `local`, `tests`, `evals`.
- **e) `--dry-run`**: exit 0, mostra o plano (cita `dist/codebase-specialists`; cita backup quando haveria um) e não
  escreve nada (nem package, nem travas, nem link). **`--check`**: não escreve nada (nem instala trava); exit 0 só
  se TUDO está em dia: travas presentes, link certo, `cs.py --help` ok, VERSION igual, nada interno, pacote não
  desatualizado (abaixo). Senão exit != 0 com o motivo (saída não vazia).
- **f)** duas execuções seguidas: exit 0 nas duas, nenhum backup novo na 2ª, link intocado.

### Origem do pacote e "desatualizado" (I2)

- O pacote grava `dist/codebase-specialists/.origem` com o HEAD COMPLETO (40 hex) do projeto do qual saiu. Sem
  caminho nenhum (nenhuma `/`, nada do HOME/projeto) — o pacote é publicável.
- **Desatualizado** = `.origem` ausente/desconhecida, OU algum arquivo de PRODUTO mudou entre `.origem` e HEAD.
  Produto = o que entra no pacote: `SKILL.md`, `MODO-DE-USO.md`, `VERSION`, `LICENSE`, `scripts/`, `assets/`,
  `references/`, `docs/`, `.claude/package/`. Commit só de `.claude/state/` (ex.: `save-session`) NÃO desatualiza
  (decisão de desenho deste oráculo: senão todo `save-session` geraria aviso falso).

### `carimbo.sh --brief` (SessionStart) (I2)

- Exit 0 sempre nesses cenários; não escreve em `$HOME` nem no projeto (exceto instalar travas que faltam).
- Travas faltando ⇒ instala sozinho (sem rede, sem senha; mesma lógica do instalar-hooks-git) e imprime uma linha
  com `travas` e `faltav…` (ex.: `travas do git faltavam — instaladas agora`). Na execução seguinte nenhuma linha
  com `faltav` e os hooks não são regravados. Trava alheia: não mexe.
- Pacote instalado desatualizado (commit de produto depois do `.origem`) ⇒ uma linha com `desatualizad…` e a
  sugestão `/install`. Sem instalação, ou instalado que não é o link para o dist (ex.: link para o projeto
  inteiro) ⇒ sugere `/install`.
- Tudo em dia ⇒ nenhuma ocorrência de `/install`, `desatualizad`, `faltav`.

### Textos (I3)

- `.claude/skills/install/SKILL.md`: começa com `---\nname: install\n`, tem `description:`, chama
  `.claude/tools/instalar.sh`, no máximo 40 linhas (fina: o script decide).
- `.claude/skills/close-front/SKILL.md`: cita `/install` DEPOIS de `git commit` (o instalado é atualizado depois do
  commit da frente).
- `README.md`, seção `## Primeira vez numa máquina nova`: sem bloco de código, sem trecho `` `...` `` que seja comando
  de terminal (git/bash/sh/python3/cd/ln/cp/mv/mkdir/rm/curl/pip/brew/chmod/export/source), sem linha `$ ...`;
  única exceção: o que cita `frase definir` (a senha, que o HUMANO define e digita no terminal dele quando uma
  aprovação pedir). Ordem: clonar (pedindo ao Claude) → abrir o Claude no projeto → `/install` → `/load-session`;
  cita a senha.

## Mapa requisito → teste

| Req | Testes |
|---|---|
| I1 (existe, help) | `test_i1_existe_e_help_nao_escreve` |
| I1a | `test_i1a_instala_as_travas_do_git`, `test_i1a_trava_alheia_nao_e_sobrescrita` |
| I1b | `test_i1b_package_falho_nao_toca_instalacao`, `test_i1b_package_falho_preserva_instalacao_anterior_funcionando` |
| I1c | `test_i1c_instalacao_nova_link_para_o_dist_independe_do_cwd`, `test_i1c_pasta_existente_vai_para_backup`, `test_i1c_link_errado_vai_para_backup`, `test_i1c_backup_nunca_apaga_backup_anterior` |
| I1d | `test_i1d_instalado_roda_e_tem_a_versao_do_projeto`, `test_i1d_instalado_sem_nada_interno`, `test_i1d_versao_do_projeto_divergente_do_pacote_reprova` |
| I1e | `test_i1e_dry_run_nao_escreve_e_mostra_o_plano`, `test_i1e_dry_run_depois_de_instalado_nao_escreve`, `test_i1e_check_em_dia`, `test_i1e_check_sem_instalacao`, `test_i1e_check_commit_de_produto_desatualiza`, `test_i1e_check_commit_so_de_state_continua_em_dia`, `test_i1e_check_versao_divergente`, `test_i1e_check_link_errado`, `test_i1e_check_travas_faltando_nao_reinstala` |
| I1f | `test_i1f_duas_execucoes_sem_backup_novo_e_link_intocado` |
| I2 origem | `test_i2_origem_no_pacote_instalado_sem_caminho` |
| I2 brief | `test_i2_brief_instala_travas_que_faltam_e_avisa_uma_vez`, `test_i2_brief_trava_alheia_preservada`, `test_i2_brief_sem_instalacao_sugere_install`, `test_i2_brief_em_dia_nao_sugere_nada`, `test_i2_brief_commit_de_produto_avisa_desatualizado`, `test_i2_brief_commit_so_de_state_nao_avisa`, `test_i2_brief_link_para_o_projeto_sugere_install` |
| I3 | `test_i3_skill_install_fina`, `test_i3_close_front_manda_install_depois_do_commit`, `test_i3_readme_primeira_vez_sem_terminal`, `test_i3_readme_primeira_vez_ordem` |

34 testes; TODOS falham com o projeto atual (base.txt).

## Fora do oráculo (o corretor cuida, o portão/suíte cobre)

- `.claude/tools/tests/test_harness_dev.py::test_skills_do_harness` fixa a lista de skills do harness: com
  `install` nova ela tem de ser atualizada (está no escopo da frente).
- `.claude/CLAUDE.md` (lista de rituais) e `load-session` (passo "máquina nova") devem citar `/install`;
  recomendado, não testado aqui.
- Custo: cada `instalar.sh` sem opção roda o `package.sh` completo (~6 s nesta máquina); o oráculo inteiro leva
  ~3–4 min por Python.

## Escopo sugerido da frente

`.claude/tools/instalar.sh` (novo), `.claude/tools/package.sh` (`.origem`; montar fora do lugar ou permitir saída
alternativa), `.claude/tools/carimbo.sh`, `.claude/skills/install/SKILL.md` (novo),
`.claude/skills/close-front/SKILL.md`, `README.md`, `.claude/tools/tests/test_harness_dev.py`, e opcionalmente
`.claude/CLAUDE.md`, `.claude/skills/load-session/SKILL.md`, `.claude/package/README.md`.
