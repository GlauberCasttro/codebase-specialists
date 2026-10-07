# PORQUE — mudança oficial 01: suíte do harness com comandos em português

Patch: `01-suite-harness-nomes-pt.patch` (sobre `.claude/tools/tests/test_harness_dev.py` do HEAD; `git apply -p1`
confere). Quem aplica: o grupo G3 da frente harness-dev. Pré-condição: o founder aprova a emenda da D-07 (ESPEC §8.1).

## O que muda (4 testes, nenhum `def` removido)

| teste | antes | depois | por quê |
|---|---|---|---|
| `AjudaETools.test_skills_do_harness` | exige exatamente close-front, install, load-session, new-front, package, save-session; new-front/close-front/load-session citam o motor | exige as 11 skills em português; criar-frente e fechar-frente citam `frente.py`; auto-correcao cita o motor `python3 .claude/tools/ac/ac.py` | o founder decidiu comandos em português e uma skill auto-correcao no harness |
| `AjudaETools.test_nomes_antigos_de_skill_ausentes` | nenhum arquivo de `.claude/` cita salvar-sessao, carregar-sessao… | nenhum arquivo de `.claude/` (fora de `state/` e `tests/`) cita os nomes **ingleses substituídos** do harness (new-front, close-front) | os nomes em português passam a SER os comandos do harness; a D-07 continua valendo para o produto |
| `ScriptAprovacao.test_sem_campanha_recusa` | mensagem cita new-front | cita criar-frente | renome |
| `ScriptAprovacao.test_gera_em_local_com_motor_embutido` | gera sem oráculo congelado | sem `oracle freeze` recusa (cita "congel"); congela e então gera | quem testa não constrói: o founder só aprova depois do oráculo congelado |

## Evidência (conferida à mão)

- A D-07 (`.claude/state/DECISIONS.md`) diz "onde vale: produto e este harness"; o teste que a estendia ao harness é
  só o `test_nomes_antigos_de_skill_ausentes` da suíte do harness (`.claude/tools/tests/test_harness_dev.py:586`).
- O guarda da D-07 no PRODUTO é `campanhas/iter15/oraculo/test_iter15.py::TestR1FontesDaSkill`; ele varre
  `SOURCE_GLOBS_ROOT = ("SKILL.md", "MODO-DE-USO.md")` e `SOURCE_DIRS = ("assets/templates", "references", "docs",
  "scripts")` (linhas 68–69) — **não** inclui `.claude/`. Logo não precisa de mudança, e continua guardando o produto:
  o portão da harness-dev passa a rodá-lo (`--oraculo campanhas/iter15/oraculo:test_iter15.TestR1FontesDaSkill`).
- Varredura dos testes do produto (`scripts/*/tests`, `evals/`, `campanhas/*/oraculo`) por `salvar-sessao`/
  `carregar-sessao`/varredura de `.claude/`: nenhuma outra ocorrência além da iter15 (lista de renomes, R1 acima).
- Aplicado num protótipo de calibração: a suíte do harness passa nos 2 Pythons (exceto
  `GuardPrivacidade.test_pre_commit_e_instalador`, que depende de o projeto estar dentro de um repositório git —
  ambiental no protótipo; no portão a cópia limpa fica em `local/`, dentro do repositório, e o teste passa).

## O que NÃO afrouxa

Nada sobre o produto: a varredura da D-07 no produto continua (iter15 R1) e passa a rodar no portão desta frente. O
harness ganha uma varredura nova (nomes ingleses substituídos) no lugar da antiga.
