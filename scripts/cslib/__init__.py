"""cslib — biblioteca comum da skill codebase-specialists (Python 3.9+, só stdlib).

Módulos: errors, paths, jsonio, evidence, gitx, log. API documentada em README.md.
"""

from .errors import CsError

SCHEMA_VERSION = 1
SKILL_NAME = "codebase-specialists"

__all__ = ["CsError", "SCHEMA_VERSION", "SKILL_NAME"]
