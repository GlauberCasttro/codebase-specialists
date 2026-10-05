"""Erro único da skill: mensagem + como resolver. cs.py converte em exit != 0."""


class CsError(Exception):
    """Falha alta e acionável.

    message: o que deu errado (uma frase).
    hint: o que o usuário deve fazer para resolver (opcional, mas recomendado).
    code: exit code do processo (default 2).
    """

    def __init__(self, message, hint=None, code=2):
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.code = code

    def render(self):
        out = "erro: " + self.message
        if self.hint:
            out += "\n  como resolver: " + self.hint
        return out
