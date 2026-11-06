"""Caso de uso: orquesta defensa -> LLM -> defensa. Depende solo de puertos y dominio."""

from __future__ import annotations

import hashlib
import secrets

from pyme_guard.application.ports import AuditPort, LLMPort
from pyme_guard.application.prompts import (
    BLOCKED_MESSAGE,
    HANDOFF_MESSAGE,
    SYSTEM_PROMPT_TEMPLATE,
    UNAVAILABLE_MESSAGE,
    USER_TEMPLATE,
)
from pyme_guard.domain.errors import LLMUnavailableError
from pyme_guard.domain.guardrails import HandoffPolicy, InputGuard, OutputGuard
from pyme_guard.domain.models import AuditEvent, ChatResult, Status


class AssistantService:
    def __init__(
        self,
        llm: LLMPort,
        audit: AuditPort,
        input_guard: InputGuard | None = None,
        output_guard: OutputGuard | None = None,
        handoff: HandoffPolicy | None = None,
    ) -> None:
        self._llm = llm
        self._audit = audit
        self._input_guard = input_guard or InputGuard()
        self._output_guard = output_guard or OutputGuard()
        self._handoff = handoff or HandoffPolicy()
        self._canary = f"CANARY-{secrets.token_hex(8)}"
        self._system_prompt = SYSTEM_PROMPT_TEMPLATE.format(canary=self._canary)

    def handle(self, message: str) -> ChatResult:
        result = self._process(message)
        self._audit.record(
            AuditEvent.now(_hash(message), result.status, result.reasons)
        )
        return result

    def _process(self, message: str) -> ChatResult:
        checked = self._input_guard.inspect(message)
        if not checked.allowed:
            return ChatResult(Status.BLOCKED, BLOCKED_MESSAGE, checked.reasons)

        if self._handoff.requires_human(checked.sanitized):
            return ChatResult(Status.HANDOFF, HANDOFF_MESSAGE, ("HUMAN_DECISION_REQUIRED",))

        try:
            raw = self._llm.generate(
                self._system_prompt, USER_TEMPLATE.format(message=checked.sanitized)
            )
        except LLMUnavailableError:
            return ChatResult(Status.HANDOFF, UNAVAILABLE_MESSAGE, ("LLM_UNAVAILABLE",))

        verdict = self._output_guard.inspect(raw, self._canary)
        if not verdict.allowed:
            return ChatResult(Status.HANDOFF, HANDOFF_MESSAGE, verdict.reasons)

        return ChatResult(Status.ANSWERED, verdict.text, checked.reasons + verdict.reasons)


def _hash(message: str) -> str:
    return hashlib.sha256(message.encode("utf-8")).hexdigest()[:16]
