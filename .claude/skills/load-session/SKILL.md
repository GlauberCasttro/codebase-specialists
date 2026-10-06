---
name: load-session
description: Retoma o desenvolvimento da skill codebase-specialists — carimbo real, RESUME, WORKFLOW e status da(s) campanha(s) ativa(s). Use ao abrir a sessão neste projeto ou quando o founder pedir "retoma", "onde paramos", "carrega a sessão".
---

# load-session

Só lê; não altera nada. Ordem:

1. Âncora (fonte única de branch/HEAD/VERSION/campanhas/arquivos sujos):
   `bash .claude/tools/carimbo.sh`
2. Leia `.claude/state/RESUME.md` e `.claude/state/WORKFLOW.md` (e BACKLOG/DECISIONS só se a tarefa pedir).
3. Para cada campanha ativa que o carimbo listou, o status mecânico (motor embutido, caminho LITERAL):
   `python3 .claude/tools/ac/ac.py --work campanhas/<frente> status`
4. Se houver portão da frente: `tail -5 local/portao-<frente>/portao.out`.
5. Máquina nova? Se `local/termos-privados.txt` não existe, `bash .claude/tools/guard-privacidade.sh --termos`
   avisa: diga ao founder (README, seção "Primeira vez numa máquina nova"). Se o carimbo (SessionStart) sugeriu
   `/install` (skill não instalada, link antigo ou pacote desatualizado) ou `bash .claude/tools/instalar.sh --check`
   reprova, proponha `/install` ao founder.
6. Frescor: se o RESUME diz algo que o carimbo/ac.py contradiz (ex.: commit que já entrou, etapa que andou),
   VALE o script — diga a divergência ao founder e corrija o state no `save-session`.

Responda curto: onde estamos (com os números do carimbo/ac.py), a próxima ação (comando pronto) e o que espera
decisão do founder. Não invente progresso que nenhum script mostrou.
