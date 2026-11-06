"""Agregado Solicitud y su traza: lo que hace cada agente queda visible y auditable."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from pyme_guard.domain.credit import Consent, Offer
from pyme_guard.domain.errors import InvalidTransitionError


class AppStatus(StrEnum):
    CONSENT_REQUIRED = "consentimiento_requerido"
    NOT_ELIGIBLE = "no_elegible"
    COMPLIANCE_REVIEW = "revision_cumplimiento"
    FRAUD_REVIEW = "revision_fraude"
    MANUAL_REVIEW = "revision_manual"
    OFFER_READY = "oferta_indicativa"
    PENDING_APPROVAL = "pendiente_aprobacion_humana"
    APPROVED = "aprobada_por_humano"
    DECLINED = "rechazada_por_humano"


# Transiciones permitidas: la IA no puede saltar a APPROVED; solo una decisión humana.
_TRANSITIONS: dict[AppStatus, frozenset[AppStatus]] = {
    AppStatus.OFFER_READY: frozenset({AppStatus.PENDING_APPROVAL}),
    AppStatus.PENDING_APPROVAL: frozenset({AppStatus.APPROVED, AppStatus.DECLINED}),
    AppStatus.MANUAL_REVIEW: frozenset({AppStatus.APPROVED, AppStatus.DECLINED}),
    AppStatus.COMPLIANCE_REVIEW: frozenset({AppStatus.DECLINED, AppStatus.MANUAL_REVIEW}),
    AppStatus.FRAUD_REVIEW: frozenset({AppStatus.DECLINED, AppStatus.MANUAL_REVIEW}),
}

HUMAN_QUEUE_STATUSES = frozenset(
    {AppStatus.PENDING_APPROVAL, AppStatus.MANUAL_REVIEW, AppStatus.COMPLIANCE_REVIEW, AppStatus.FRAUD_REVIEW}
)


PIPELINE_OUTCOMES = frozenset(
    {
        AppStatus.CONSENT_REQUIRED,
        AppStatus.NOT_ELIGIBLE,
        AppStatus.COMPLIANCE_REVIEW,
        AppStatus.FRAUD_REVIEW,
        AppStatus.MANUAL_REVIEW,
        AppStatus.OFFER_READY,
    }
)


class ActionKind(StrEnum):
    INFORM = "informa"
    RECOMMEND = "recomienda"
    EXECUTE = "ejecuta"
    HANDOFF = "transfiere"
    HUMAN = "decision_humana"


@dataclass(frozen=True, slots=True)
class TraceStep:
    agent_id: str
    action: ActionKind
    summary: str
    systems: tuple[str, ...] = ()
    outcome: str = "ok"  # ok | alerta | bloqueo | error
    handoff_to: str | None = None
    at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class Handoff:
    role: str  # analista_credito | comite_credito | oficial_cumplimiento | analista_fraude
    reason: str
    sla_hours: int


@dataclass(frozen=True, slots=True)
class HumanDecision:
    reviewer: str
    approved: bool
    reason: str
    at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class Application:
    id: str
    nit: str
    consent: Consent
    status: AppStatus = AppStatus.CONSENT_REQUIRED
    company_name: str | None = None
    trace: list[TraceStep] = field(default_factory=list)
    offer: Offer | None = None
    exclusions: list[dict[str, str]] = field(default_factory=list)
    explanations: list[str] = field(default_factory=list)
    client_message: str = ""
    analyst_brief: str = ""
    narrative_source: str = ""
    handoff: Handoff | None = None
    decision: HumanDecision | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def log(self, step: TraceStep) -> None:
        self.trace.append(step)

    def set_pipeline_outcome(self, status: AppStatus) -> None:
        """Resultado del flujo automático. Nunca puede ser una aprobación o un rechazo final."""
        if status not in PIPELINE_OUTCOMES:
            raise InvalidTransitionError(f"El flujo automático no puede fijar {status.value}")
        self.status = status

    def move_to(self, new_status: AppStatus) -> None:
        allowed = _TRANSITIONS.get(self.status, frozenset())
        if new_status not in allowed:
            raise InvalidTransitionError(f"{self.status.value} -> {new_status.value} no permitido")
        self.status = new_status

    @property
    def in_human_queue(self) -> bool:
        return self.status in HUMAN_QUEUE_STATUSES
