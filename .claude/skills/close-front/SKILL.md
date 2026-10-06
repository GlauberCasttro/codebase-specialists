---
name: close-front
description: Fecha uma frente da codebase-specialists — portão verde, portar, conferir-commit, commit só dos arquivos da frente, fechamento da campanha no motor embutido e arquivamento no WORKFLOW e em campanhas/README.md. Use quando o corretor terminar, quando o founder pedir "fecha a frente", "commita a iterN", ou para retomar um fechamento pela metade.
---

# close-front `<frente>`

W = `campanhas/<frente>`; AC literal = `python3 .claude/tools/ac/ac.py --work campanhas/<frente>`. Lista de arquivos
SEMPRE explícita (ou `--lista`).

1. Portão (cópia limpa; rode em background e acompanhe `local/portao-<frente>/portao.out` até `FIM`):
   `bash .claude/tools/portao.sh <frente> --oraculo campanhas/<frente>/oraculo:<modulo> [--oraculo <outro>]... -- <arquivos>`
   VERMELHO ⇒ volta ao corretor. Não "conserte" o portão.
2. Para o projeto: `bash .claude/tools/portar.sh <frente> --dry-run -- <arquivos>`, depois sem `--dry-run`.
   Houve MERGE ⇒ rode o passo 1 de novo com `--src .`. CONFLITO ⇒ pare e devolva ao founder/corretor.
3. `bash .claude/tools/conferir-commit.sh <frente> -- <arquivos>` tem de dar OK.
4. Privacidade: `bash .claude/tools/guard-privacidade.sh` (projeto inteiro) vazio.
5. Commit só da frente: `git add <arq>` um a um (mais `campanhas/<frente>/oraculo/**` e o README de campanhas);
   mensagem em arquivo (`git commit -F <arq>`). Nunca `-A`, `.`, `-a`, push.
6. Campanha (cada etapa só depois da anterior; números vêm do portão, não da memória):
   - `... front report <nome> --file <relatório da frente>`;
   - `... done correcao`; `... set integration.tests_green true`; `... done integracao`;
   - `... run record --config <config> --decision GO` (AC-09: se cair no mesmo segundo do `done`, registre de novo);
   - `... done remedicao`;
   - o FOUNDER roda no terminal dele a conferência da aprovação (`frase conferir`); você só avisa;
   - `... done decisao`. Confira com `... status` (etapa `concluida`).
7. WORKFLOW: tire das ativas, ponha em "Últimas entregas" (commit + data do `git log`); em `campanhas/README.md`
   preencha commit de entrega e decisão (GO/PARCIAL). Depois, `save-session`.
