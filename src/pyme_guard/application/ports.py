"""Puertos de salida: contratos que el núcleo necesita; los adaptadores los implementan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pyme_guard.domain.credit import BureauReport, Company, Invoice, SanctionsResult
from pyme_guard.domain.journey import Application
from pyme_guard.domain.models import AuditEvent


class LLMPort(Protocol):
    def generate(self, system_prompt: str, user_message: str) -> str:
        """Devuelve el texto del modelo. Lanza LLMUnavailableError si falla."""
        ...


class AuditPort(Protocol):
    def record(self, event: AuditEvent) -> None: ...


# --- Sistemas externos (todos de solo lectura para los agentes) -------------- #
class CompanyRegistryPort(Protocol):
    """RUES / cámaras de comercio."""

    def lookup(self, nit: str) -> Company | None: ...


class SanctionsPort(Protocol):
    """Listas restrictivas (ONU, OFAC) y PEP. Proveedor KYB."""

    def screen(self, nit: str, name: str) -> SanctionsResult: ...


class InvoiceRegistryPort(Protocol):
    """RADIAN (DIAN) vía proveedor tecnológico o sistema de negociación electrónica."""

    def invoices_for(self, nit: str) -> list[Invoice]: ...


class CreditBureauPort(Protocol):
    """Centrales de riesgo. Lanza SourceUnavailableError si no responde."""

    def report(self, nit: str) -> BureauReport: ...


# --- Persistencia y operación --------------------------------------------- #
class ApplicationRepositoryPort(Protocol):
    def save(self, application: Application) -> None: ...

    def get(self, application_id: str) -> Application | None: ...

    def human_queue(self) -> list[Application]: ...


@dataclass(frozen=True, slots=True)
class DecisionEvent:
    """Evidencia de cada paso del flujo. Sin PII: NIT enmascarado y razones codificadas."""

    application_id: str
    nit_masked: str
    actor: str
    action: str
    status: str
    detail: str


class DecisionLogPort(Protocol):
    def record_decision(self, event: DecisionEvent) -> None: ...


@dataclass(frozen=True, slots=True)
class Narrative:
    text: str
    source: str  # "plantilla" | "crewai"
    notes: tuple[str, ...] = ()


class NarratorPort(Protocol):
    """Genera textos explicativos (cliente y analista). Nunca decide."""

    def explain_offer(self, application: Application) -> Narrative: ...

    def brief_for_analyst(self, application: Application) -> Narrative: ...
