# Decisões do founder — codebase-specialists (desenvolvimento da skill)

Formato: `D-nn` · data · decisão · porquê · onde vale. Só entra decisão DO FOUNDER (a IA não decide aqui).
Quando a data exata não foi registrada, está escrito "data não registrada" — não invente.
Commits citados antes de D-14 são do repositório privado de origem.

| id | data | decisão | porquê | onde vale |
|---|---|---|---|---|
| D-01 | data não registrada (≤ 2026-10-05) | Skills finas + scripts: tudo que é mecânico vira script (`--dry-run`, `check`, `--json`); a skill só chama. | Markdown explica, script decide; skill gorda erra e não é testável. | produto e este harness |
| D-02 | 2026-10-04 (0.6.0, `ffe388f`) | Harness único na pasta `.swarm/` no alvo; nunca coexiste com outro harness (substitui com backup, só com `--replace-harness`). | Dois harness no mesmo repo brigam pelos mesmos hooks e estado. | produto |
| D-03 | 2026-10-05 (0.7.0, `3127bf9`) | Estado do harness do alvo como árvore de pastas (backlog/ state/ archive/), um arquivo por item. | Navegável por humano; `state/` só com o que executa agora. | produto |
| D-04 | 2026-10-04/05 (auto-correcao v0.3–v0.4.1) | Aprovação humana só no terminal do founder, com a senha dele; a IA nunca aprova, nunca pede a senha no chat. | Aprovação forjável não vale nada. | campanhas (gate, preauth, `frase conferir`) |
| D-05 | 2026-10-05 (iter14, `18e3496`) | Senha do humano também na aprovação do mandato (modo autônomo). | Mesmo motivo de D-04, dentro do produto. | produto (`cs-auto approve`) |
| D-06 | data não registrada | `--fast` é o modo padrão. | Custo. | produto |
| D-07 | 2026-10-06 (iter15, `be1d03c`) | Nomes de skill/comando em inglês, verbo-objeto (save-session, load-session, correct, plan-sprint, new-epic, close-epic); prosa em português. Os nomes antigos em português não podem aparecer em nada (há teste que varre). | Padrão de comando legível e consistente entre plataformas. | produto e este harness |
| D-08 | data não registrada (pacotes 0.7.0/0.8.0) | Nada privado no que é público: cobaia vira "repositório-piloto (projeto-legado)" ou "cobaia .NET", pessoa nos testes vira Ana, caminhos internos viram `~`/variável, testes de recurso privado só por variável de ambiente (pulam sem ela); autor do commit `GlauberCasttro@users.noreply.github.com`. | Privacidade. | todo o projeto (público) e o pacote |
| D-09 | 2026-10-05 (`9d1ab30`) | iter11 fecha PARCIAL: medição real com as 3 fixtures adiada por custo. | ~6–9 h e 15–38 M tokens estimados; confirmar custo antes. | BACKLOG B-01 |
| D-10 | data não registrada | Máximo de 5 agentes ao mesmo tempo (3 se der 429). | Limite de taxa e custo. | orquestração |
| D-11 | data não registrada | Outras sessões (ex.: a do uso real na cobaia .NET) REPORTAM achados; não editam a skill viva. | Uma porta de entrada para mudança; nada sem portão. | este harness (guard-entrega) |
| D-12 | 2026-10-06 | Cada skill tem o seu harness de desenvolvimento em `.claude/`; toda mudança no produto passa por ele. | Entrega rastreável: frente → cópia → portão → commit. | este harness |
| D-13 | pendente de confirmação do founder | U5 (commit pós-accept) no layout PLANO continua barrado; só a árvore ganha a correção. | Layout plano é legado. | iter16 / BACKLOG B-05 |
| D-14 | 2026-10-06 | Cada skill vira um PROJETO completo e público (raiz = skill + `.claude/` + `campanhas/` + `local/` gitignored), para continuar o desenvolvimento em outra máquina; o motor de campanhas vai embutido no harness. Projeto ≠ pacote: o pacote (só o que roda) é gerado por `package` em `dist/`. | Portabilidade e histórico do método junto do código. | este repositório |
| D-16 | 2026-10-06 | Projeto publicado em repositório PÚBLICO (`github.com/GlauberCasttro/codebase-specialists`, push autorizado pelo founder); na máquina do founder `~/.claude/skills/codebase-specialists` é LINK para o projeto (uma cópia só). Push sempre só com autorização do founder. | Continuar em outra máquina; não divergir duas cópias. | instalação local, README |
| D-15 | 2026-10-06 | Termos privados e pares de limpeza com texto privado ficam só em `local/` (gitignored); o código mantém só o mecanismo. Publicar o pacote é decisão do founder, fora do `package`. | O repositório é público. | `tools/publicar_regras.py`, `tools/guard-privacidade.sh`, `tools/package.sh` |
