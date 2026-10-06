---
name: save-session
description: Salva a sessão de desenvolvimento da codebase-specialists — regrava o carimbo no RESUME, atualiza RESUME/WORKFLOW/DECISIONS/BACKLOG, acrescenta uma linha no log e commita SÓ o state. Use quando o founder pedir "salva a sessão", ao fim de um bloco de trabalho ou antes de pausar.
---

# save-session

1. Carimbo no topo do RESUME (gerado, nunca à mão):
   `bash .claude/tools/carimbo.sh --write`
2. Atualize à mão (Edit é permitido em `.claude/state/**`):
   - `RESUME.md`: "Onde paramos" e "Próximos passos" com comando pronto; pendências de decisão do founder.
   - `WORKFLOW.md`: estado de cada frente ativa (copie a etapa do `ac.py status`, não estime), fila, entregas
     (commit e data do `git log`).
   - `DECISIONS.md`: só decisão que o FOUNDER tomou nesta sessão (D-nn, data, decisão, porquê, onde vale).
   - `BACKLOG.md`: achados novos (inclusive os que outras sessões reportaram) com origem e critério de pronto.
   - Nada privado: nomes reais de projetos/pessoas e caminhos absolutos vão para `local/` (gitignored).
3. Log append-only (uma linha JSON; nunca reescreva as anteriores):
   `printf '%s\n' '{"data": "<date -Iseconds>", "evento": "sessao-salva", "resumo": "<1 frase>", "head": "<git rev-parse --short HEAD>"}' >> .claude/state/logs/sessoes.jsonl`
   (data e HEAD vêm dos comandos, não da memória).
4. Privacidade antes do commit: `bash .claude/tools/guard-privacidade.sh .claude/state` (tem de voltar vazio).
5. Commit SÓ do state, arquivo a arquivo, mensagem em arquivo:
   ```
   git add .claude/state/RESUME.md .claude/state/WORKFLOW.md .claude/state/BACKLOG.md \
           .claude/state/DECISIONS.md .claude/state/logs/sessoes.jsonl
   git commit -F <arquivo-com-a-mensagem>
   ```
   Nunca push (é do founder).
