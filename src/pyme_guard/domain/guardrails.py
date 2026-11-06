"""Defensa del agente: lógica pura, sin I/O, fácil de probar.

Capas:
  1. InputGuard   -> normaliza, limita, detecta prompt injection, minimiza PII.
  2. HandoffPolicy -> decisiones que siempre son de una persona.
  3. OutputGuard  -> detecta fuga del prompt (canary), promesas indebidas,
                     elimina enlaces (exfiltración) y PII en la respuesta.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

DEFAULT_MAX_CHARS = 2000


# --------------------------------------------------------------------------- #
# Utilidades de texto
# --------------------------------------------------------------------------- #
def normalize(text: str) -> str:
    """NFKC (colapsa caracteres de ancho completo) y elimina invisibles/control."""
    text = unicodedata.normalize("NFKC", text)
    text = "".join(
        ch for ch in text if ch in "\n\t" or unicodedata.category(ch) not in {"Cf", "Cc"}
    )
    return re.sub(r"[ \t]+", " ", text).strip()


def fold(text: str) -> str:
    """Minúsculas y sin tildes: para comparar patrones de forma robusta."""
    decomposed = unicodedata.normalize("NFD", text.casefold())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


# --------------------------------------------------------------------------- #
# PII
# --------------------------------------------------------------------------- #
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_DOC = re.compile(
    r"(?i)\b(?:c[eé]dula|c\.?c\.?|nit|identificaci[oó]n|documento)\b[^\d\n]{0,15}\d[\d.\-]{5,14}\d"
)
_PHONE = re.compile(r"(?<!\d)(?:\+?57[\s-]?)?3\d{2}[\s-]?\d{3}[\s-]?\d{4}(?!\d)")


def redact_pii(text: str) -> tuple[str, bool]:
    """Reemplaza PII por marcadores. Devuelve (texto, ¿hubo cambios?)."""
    original = text

    def _card(match: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", match.group())
        return "[TARJETA]" if 13 <= len(digits) <= 19 and _luhn_ok(digits) else match.group()

    text = _EMAIL.sub("[EMAIL]", text)
    text = _DOC.sub("[DOCUMENTO]", text)
    text = _CARD.sub(_card, text)
    text = _PHONE.sub("[TELEFONO]", text)
    return text, text != original


# --------------------------------------------------------------------------- #
# Entrada
# --------------------------------------------------------------------------- #
_INJECTION_PATTERNS = tuple(
    re.compile(p, re.MULTILINE)
    for p in (
        r"\b(?:ignor\w*|olvid\w*|omit\w*|desobedec\w*)\s+(?:\w+\s+){0,3}"
        r"(?:instrucciones|reglas|indicaciones|restricciones)",
        r"\b(?:ignore|disregard|forget|override)\s+(?:\w+\s+){0,3}"
        r"(?:instructions|rules|prompts?|guidelines|restrictions)",
        r"\b(?:revela\w*|muestra\w*|imprime|repite|dime|show|reveal|print|repeat|leak)\s+"
        r"(?:\w+\s+){0,4}(?:system\s*prompt|prompt\s+del\s+sistema|"
        r"instrucciones\s+(?:del\s+sistema|internas|iniciales)|tus\s+instrucciones|your\s+instructions)",
        r"\b(?:ahora\s+eres|you\s+are\s+now|actua\s+como|act\s+as|finge\s+(?:ser|que)|pretend\s+(?:to\s+be|you))",
        r"\b(?:modo\s+(?:desarrollador|dios|sin\s+restricciones)|developer\s+mode|jailbreak|do\s+anything\s+now)",
        r"</?\s*(?:system|assistant|mensaje_usuario|instructions?)\s*>|\[/?inst\]|<\|im_(?:start|end)\|>|^#{1,3}\s*system",
        r"\bdesactiv\w*\s+(?:\w+\s+){0,2}(?:filtros|controles|guardrails|seguridad|restricciones)",
    )
)
_ENCODED_BLOB = re.compile(r"[A-Za-z0-9+/]{80,}={0,2}")


@dataclass(frozen=True, slots=True)
class InputInspection:
    allowed: bool
    sanitized: str
    reasons: tuple[str, ...] = ()


class InputGuard:
    def __init__(self, max_chars: int = DEFAULT_MAX_CHARS) -> None:
        self._max_chars = max_chars

    def inspect(self, message: str) -> InputInspection:
        if len(message) > self._max_chars * 2:  # corte barato antes de procesar
            return InputInspection(False, "", ("TOO_LONG",))
        clean = normalize(message)
        if not clean:
            return InputInspection(False, "", ("EMPTY",))
        if len(clean) > self._max_chars:
            return InputInspection(False, "", ("TOO_LONG",))

        folded = fold(clean)
        if any(p.search(folded) for p in _INJECTION_PATTERNS):
            return InputInspection(False, "", ("PROMPT_INJECTION",))
        if _ENCODED_BLOB.search(clean):
            return InputInspection(False, "", ("ENCODED_PAYLOAD",))

        sanitized, changed = redact_pii(clean)
        return InputInspection(True, sanitized, ("PII_REDACTED",) if changed else ())


# --------------------------------------------------------------------------- #
# Decisiones humanas
# --------------------------------------------------------------------------- #
_HUMAN_TOPICS = re.compile(
    r"\b(?:desembols\w*|aprob\w*|apru[eé]b\w*|firm\w*|reestructur\w*|queja\w*|reclamo\w*|demanda\w*|fraude\w*|embargo\w*)"
)


class HandoffPolicy:
    """El agente informa; aprobar, desembolsar o resolver disputas lo hace una persona."""

    def requires_human(self, message: str) -> bool:
        return bool(_HUMAN_TOPICS.search(fold(message)))


# --------------------------------------------------------------------------- #
# Salida
# --------------------------------------------------------------------------- #
_COMMITMENTS = tuple(
    re.compile(p)
    for p in (
        r"\b(?:ha sido|fue|esta|queda|quedo)\s+aprobad[oa]",
        r"\b(?:te|le|se lo)\s+(?:garantizo|garantizamos|aseguro|aseguramos)",
        r"\baprobacion\s+(?:inmediata|garantizada|segura)",
    )
)
_URL = re.compile(r"(?i)\b(?:https?://|www\.)\S+")


@dataclass(frozen=True, slots=True)
class OutputInspection:
    allowed: bool
    text: str
    reasons: tuple[str, ...] = ()


class OutputGuard:
    def inspect(self, text: str, canary: str) -> OutputInspection:
        if not text or not text.strip():
            return OutputInspection(False, "", ("EMPTY_OUTPUT",))
        if canary in text:
            return OutputInspection(False, "", ("SYSTEM_PROMPT_LEAK",))
        folded = fold(text)
        if any(p.search(folded) for p in _COMMITMENTS):
            return OutputInspection(False, "", ("UNAUTHORIZED_COMMITMENT",))

        reasons: list[str] = []
        cleaned = _URL.sub("[ENLACE REMOVIDO]", text)
        if cleaned != text:
            reasons.append("URL_REMOVED")
        cleaned, changed = redact_pii(cleaned)
        if changed:
            reasons.append("PII_REDACTED")
        return OutputInspection(True, cleaned.strip(), tuple(reasons))
