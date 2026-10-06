# BACKLOG — codebase-specialists

Prioridade: P0 (bloqueia entrega) · P1 (próxima frente) · P2 (quando houver folga). Cada item vira frente
(campanha no motor embutido) pela skill `new-front`. Origem = de onde veio; pronto = critério verificável.

| id | P | item | origem | pronto quando |
|---|---|---|---|---|
| B-08 | P0 | Publicar o pacote 0.9.0 (hoje o último publicado é 0.8.0) e avisar a sessão da cobaia .NET para rodar o upgrade. | pedido do founder | `bash .claude/tools/package.sh` verde (guard vazio, 0 vazamentos, 5 passos exit 0); founder decide onde publicar e faz o push; aviso enviado |
| B-03 | P1 | Refino no `--fast` gasta o slot do refino (`scripts/team/cards.py`, trecho do refino liberado). | uso real (cobaia .NET) | teste que prova o gasto indevido falha antes e passa depois; suítes verdes |
| B-02 | P1 | Upgrade real no repositório-piloto (cobaia legada) e destravar os agentes de lá (KEY/AGT, OPS/AGT/QA). | `campanhas/historico/RETOMADA-2026-10-05.md` §4; backup local na máquina original | upgrade conclui com selftest, validate e emit validate verdes no repo real; backup conferido antes |
| B-06 | P2 | Lembrete "comite antes do close" no `próximo:` do `cs-state`. | uso real | `cs-state` imprime o lembrete quando há diff não commitado na task; teste |
| B-07 | P2 | Estender a senha a `amend`/`resolve`/`stop`/`abort` do mandato. | iter14 cobriu `approve` | teste por subcomando: sem senha nega, com senha passa |
| B-04 | P2 | Limites do scan C#: `global using`; segundo bloco `namespace` no mesmo arquivo. | iter16 (achados restantes) | casos cobertos por teste no scan; suítes verdes |
| B-05 | P2 | U5 (commit pós-accept) no layout plano — hoje barrado; confirmar. | iter16; D-13 pendente | founder decide; se liberar, teste de U5 no layout plano verde |
| B-01 | P2 | Medição real da iter11: 3 fixtures (py-billing, ts-shop, go-polyglot), com e sem skill; antes, 1 execução `--fast` por fixture para calibrar custo. Custo a confirmar. | iter11 fechou parcial (D-09); `campanhas/iter11/oraculo/ESPEC.md` | founder confirmou o custo; resultados registrados com `run record`; os 2 checks do sanitize que dependem de execução real verdes |
| B-09 | P2 | `docs/PENDENTE.md` está desatualizado (M5, iter11–16 já entraram). | leitura em 2026-10-06 | atualizado numa frente de doc (ou removido em favor deste state/) |
| B-11 | P2 | Primeira sessão numa máquina nova: exercitar `frase definir` do motor embutido e `instalar-hooks-git.sh` num clone limpo (não testados de ponta a ponta). | montagem do projeto (2026-10-06) | numa máquina/HOME limpos: senha definida, hook de privacidade ativo, `/load-session` mostra o carimbo |
| B-12 | P2 | Repositório privado de origem: as pastas antigas das 3 skills viraram links (backup local na máquina de origem); decidir se o repositório privado deixa de versionar essas skills. | links de 2026-10-06 | founder decide; repositório privado sem cópia divergente |
| B-10 | feito | Portão de frente em `tools/portao.sh`; motor de campanhas embutido; `package` no lugar do export público. | ESPEC do projeto (2026-10-06) | tools e testes em `.claude/tools/` |
