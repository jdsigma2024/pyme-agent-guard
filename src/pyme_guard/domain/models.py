"""Modelos de dominio: objetos de valor inmutables, sin dependencias externas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class Status(StrEnum):
    ANSWERED = "answered"  # el agente respondió dentro de sus límites
    BLOCKED = "blocked"  # la defensa rechazó la entrada o la salida
    HANDOFF = "handoff"  # la decisión pertenece a una persona


@dataclass(frozen=True, slots=True)
class ChatResult:
    status: Status
    answer: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Evidencia de la interacción. Nunca contiene el texto original (privacidad)."""

    message_hash: str
    status: Status
    reasons: tuple[str, ...]
    occurred_at: datetime

    @staticmethod
    def now(message_hash: str, status: Status, reasons: tuple[str, ...]) -> AuditEvent:
        return AuditEvent(message_hash, status, reasons, datetime.now(UTC))
