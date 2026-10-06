# PORQUÊ — mudança oficial em `.claude/tools/tests/test_harness_dev.py` (frente iter17)

- Arquivo: `.claude/tools/tests/test_harness_dev.py`, teste `test_skills_do_harness` (linha ~577), único trecho
  tocado.
- sha256 ANTES (HEAD 4c54bb3, árvore limpa):
  `49ac39b45a222086b3c3da8c4d2f238ef20d528a51a2c9440197b73602ac64e5`
- sha256 DEPOIS (patch aplicado):
  `a4b5abeafb1746d03da8158b373b774c39a0d6a0d6ba98501c3a9ae43ef53ec6`
- Aplicar (da raiz do projeto): `patch -p0 < campanhas/iter17/oraculo/mudanca-oficial/test_harness_dev.patch`
  (conferido com `--dry-run`).

## O que muda

Uma linha: a lista EXATA de skills do harness esperada por `test_skills_do_harness` passa de
`["close-front", "load-session", "new-front", "package", "save-session"]` para
`["close-front", "install", "load-session", "new-front", "package", "save-session"]` (ordem alfabética, como o
`sorted(os.listdir(...))` produz).

## Por que é necessária

A frente iter17 cria a skill `.claude/skills/install/SKILL.md` (requisito I1/I3 do oráculo, `test_i3_skill_install_fina`).
Sem esta mudança, o teste congelado do harness reprova qualquer implementação correta da frente.

## Por que não enfraquece

- Continua igualdade EXATA (`assertEqual` da lista inteira): skill a mais ou a menos que as seis continua reprovando.
- A nova skill passa pelas mesmas checagens do laço seguinte (frontmatter começando com `---\nname: install\n`).
- Nenhuma asserção removida ou afrouxada; nenhum `def` removido; nada mais no arquivo muda (diff de 1 linha).
- A lista de skills que exigem o caminho literal do `ac.py` (`new-front`, `close-front`, `load-session`) fica igual:
  `install` não opera campanhas.
