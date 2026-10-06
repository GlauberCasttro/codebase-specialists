# codebase-specialists — harness de desenvolvimento (projeto)

Você está DESENVOLVENDO a skill `codebase-specialists` (não usando-a num alvo). Este repositório é o PROJETO: a raiz
é a skill (SKILL.md na raiz), mais `.claude/` (este harness), `campanhas/` (oráculos) e `local/` (só nesta máquina,
gitignored). Markdown explica; script decide. Nunca fabrique aprovação, execução, contagem ou data.

## Âncora e estado
- Âncora: `bash .claude/tools/carimbo.sh` (o SessionStart injeta `--brief`). Só ela diz branch, HEAD, VERSION,
  campanhas ativas e arquivos sujos.
- Estado: `.claude/state/` — RESUME, WORKFLOW (frentes, fila, entregas), BACKLOG (P0..P2), DECISIONS (do founder),
  `logs/sessoes.jsonl` (append-only).
- Editável direto (guard-entrega): `.claude/state/**`, `campanhas/**`, `local/**`, `dist/**`. O resto é produto.
- Rituais (`.claude/skills/`): `load-session`, `save-session`, `new-front`, `close-front`, `package`.

## Método (campanhas) e fluxo de entrega
Motor de campanhas EMBUTIDO: `.claude/tools/ac/ac.py` (cópia da auto-correcao, origem em `ac/ORIGEM.txt`). Sempre
o caminho LITERAL `python3 .claude/tools/ac/ac.py --work campanhas/<frente> ...` — o hook de aprovação nega
variável + palavra de aprovação. Toda mudança no produto é uma FRENTE = campanha em `campanhas/<frente>/`:
1. `new-front`: `ac.py init` (um `--scope` por glob) + linha no WORKFLOW. Uma frente ativa por vez, ou paralelas
   declaradas sem colisão (`ac.py overlap --other campanhas/<outra>`).
2. Oráculo por um agente SEPARADO (quem testa não constrói) em `campanhas/<frente>/oraculo/`, congelado
   (`oracle freeze`). Mudança só oficial: `oracle change --why --evidence`, patch + PORQUE em `mudanca-oficial/`.
3. Aprovação humana: `bash .claude/tools/script-aprovacao.sh <frente>` GERA `local/aprovar-<frente>.sh`; o FOUNDER
   roda no terminal dele, com a senha. Nunca peça a senha no chat; nunca rode o script; nunca aprove pela IA.
4. Corretor (agente) só na cópia de trabalho: `bash .claude/tools/copia.sh <frente>` → `local/work/<frente>/...`.
5. `bash .claude/tools/portao.sh <frente> [--oraculo campanhas/<frente>/oraculo:<mod>]... -- <arquivos>`: cópia
   limpa (HEAD + só os arquivos da frente), suítes nos 2 Pythons (python3 e /usr/bin/python3), oráculos, nenhum
   `def` removido. Saída em `local/portao-<frente>/portao.out` (termina em `RESULTADO:` e `FIM`). Rode em background.
6. `tools/portar.sh` (cópia → projeto; merge de 3 vias se o vivo mudou; para em conflito) →
   `tools/conferir-commit.sh` (vivo × cópia testada) → commit SÓ dos arquivos da frente.
7. Fechar a campanha (`close-front`): front report, done, run record --decision, decisão; o founder confere a
   aprovação (`frase conferir`) no terminal dele.
8. `package` quando a versão fechar: gera e VALIDA `dist/` (publicar o pacote é decisão do founder).
Achados de uso real vindos de outras sessões chegam por mensagem e viram item do BACKLOG ou frente.

## Git e privacidade
- Repo próprio (este projeto, branch `master`, remoto público). `git add` arquivo a arquivo; nunca `-A`/`.`/`-a`.
- Mensagem de commit SEMPRE em arquivo (`git commit -F <arq>`). Autor:
  `GlauberCasttro <GlauberCasttro@users.noreply.github.com>`.
- Proibido (hook `guard-git.sh`): reset --hard, checkout --/restore do worktree, clean -f, stash, push (push só pelo
  humano), add -A/--all/., commit -a.
- Privacidade: o repositório é PÚBLICO. Termos privados ficam em `local/termos-privados.txt` e pares de limpeza em
  `local/regras-privadas.json5` (gitignored; nunca versionados). `bash .claude/tools/guard-privacidade.sh` (projeto),
  `--staged`, `--msg ARQ`, `--git-log`. O pre-commit do harness (instale com `tools/instalar-hooks-git.sh`) roda o
  guard no índice e na mensagem. Em teste/fixture, pessoa = "Ana"; cobaia = "repositório-piloto (projeto-legado)"
  ou "cobaia .NET"; caminhos com `~` ou variável de ambiente.

## Lições (curtas)
- zsh não faz word-split de `$VAR`: passe arquivos explícitos ou `--lista ARQ` nos tools.
- AC-09: `run record` no mesmo segundo do `done` não registra; re-registre.
- `oracle change --file X` SUBSTITUI a lista inteira de arquivos do oráculo: passe sempre TODOS.
- Só entra no commit o que o portão testou (`conferir-commit.sh`). Depois de merge no `portar.sh`, rode de novo
  o portão com `--src .` (o projeto).
- Máx. 5 agentes simultâneos (3 se der 429). Confirme o custo com o founder antes de medição pesada.
- Cópias de trabalho e portões em `local/`, nunca em /tmp (somem no reboot).
- Nomes de skill/comando em inglês verbo-objeto; os nomes antigos em português não aparecem em nada (há teste).

## O que NÃO existe (não alegue)
- `guard-entrega.py` só vê Edit/Write/MultiEdit/NotebookEdit. Escrita por Bash no produto NÃO é bloqueada — a regra
  vale por escrito (e é por Bash que `portar.sh` trabalha, de propósito).
- `guard-git.sh` e `hook_aprovacao.py` são filtros sintáticos, não sandbox. O pre-commit só existe depois de
  `tools/instalar-hooks-git.sh` (o `.git/hooks/` não é versionado).
- Os hooks só valem com o Claude aberto NESTA pasta. Os ledgers das campanhas (`campanhas/*/.auto-correcao/`) são
  locais: numa máquina nova o histórico das campanhas é só o que está em `campanhas/` (oráculos + README).
- O portão não mede qualidade de uso real; mede suítes, oráculos e remoção de `def`.
