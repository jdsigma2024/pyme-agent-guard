import json
import logging

from pyme_guard.application.ports import DecisionEvent
from pyme_guard.domain.models import AuditEvent

_logger = logging.getLogger("pyme_guard.audit")


class LoggingAudit:
    """Auditoría estructurada (JSON por línea). Sustituible por BD o SIEM sin tocar el núcleo."""

    def record(self, event: AuditEvent) -> None:
        _logger.info(
            json.dumps(
                {
                    "type": "chat",
                    "message_hash": event.message_hash,
                    "status": event.status.value,
                    "reasons": list(event.reasons),
                    "at": event.occurred_at.isoformat(),
                }
            )
        )

    def record_decision(self, event: DecisionEvent) -> None:
        _logger.info(
            json.dumps(
                {
                    "type": "journey",
                    "application_id": event.application_id,
                    "nit": event.nit_masked,
                    "actor": event.actor,
                    "action": event.action,
                    "status": event.status,
                    "outcome": event.detail,
                }
            )
        )
