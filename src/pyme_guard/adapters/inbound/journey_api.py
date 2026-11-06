"""Rutas HTTP del journey de liquidez y de la consola del analista."""

from __future__ import annotations

import hmac
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from pyme_guard.application.credit_journey import CreditJourneyService
from pyme_guard.domain.agents import AGENTS, HUMAN_ROLES, agent_name
from pyme_guard.domain.credit import Consent, mask_nit
from pyme_guard.domain.errors import ApplicationNotFoundError, InvalidNitError, InvalidTransitionError
from pyme_guard.domain.journey import Application


class ConsentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    habeas_data: bool
    credit_bureau: bool
    invoice_registry: bool


class ApplicationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nit: str = Field(min_length=6, max_length=20, pattern=r"^[\d.\s-]+$")
    consent: ConsentIn


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approve: bool
    reason: str = Field(min_length=5, max_length=500)
    reviewer: str = Field(default="analista.demo", min_length=3, max_length=60, pattern=r"^[\w.\-]+$")


def serialize(app: Application, for_analyst: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": app.id,
        "nit": mask_nit(app.nit),
        "empresa": app.company_name,
        "estado": app.status.value,
        "mensaje_cliente": app.client_message,
        "explicaciones": app.explanations,
        "facturas_excluidas": app.exclusions,
        "fuente_narrativa": app.narrative_source,
        "oferta": None,
        "handoff": None,
        "decision": None,
        "traza": [
            {
                "agente": step.agent_id,
                "agente_nombre": agent_name(step.agent_id),
                "accion": step.action.value,
                "resumen": step.summary,
                "sistemas": list(step.systems),
                "resultado": step.outcome,
                "transfiere_a": agent_name(step.handoff_to) if step.handoff_to else None,
                "hora": step.at.isoformat(),
            }
            for step in app.trace
        ],
    }
    if app.offer:
        o = app.offer
        data["oferta"] = {
            "banda": o.band,
            "cupo_rotativo": o.credit_line_cop,
            "facturas": o.invoices_count,
            "valor_facturas": o.invoices_total_cop,
            "porcentaje_anticipo": o.advance_rate,
            "anticipo": o.advance_cop,
            "tasa_mensual": o.monthly_rate,
            "tasa_efectiva_anual": o.effective_annual_rate,
            "dias_promedio": o.weighted_days,
            "descuento": o.discount_cop,
            "comision": o.fee_cop,
            "neto": o.net_disbursement_cop,
            "aprobador": agent_name(o.required_approver),
            "politica": o.policy_version,
            "indicativa": o.indicative,
        }
    if app.handoff:
        data["handoff"] = {
            "rol": agent_name(app.handoff.role),
            # El motivo interno (p. ej. SARLAFT) solo se expone a la consola del analista.
            "motivo": app.handoff.reason if for_analyst else None,
            "sla_horas": app.handoff.sla_hours,
        }
    if app.decision:
        data["decision"] = {
            "revisor": app.decision.reviewer,
            "aprueba": app.decision.approved,
            "justificacion": app.decision.reason if for_analyst else None,
        }
    if for_analyst:
        data["resumen_analista"] = app.analyst_brief
    else:
        # El cliente no ve la traza interna de cumplimiento/fraude (evita tipping-off).
        data["traza"] = [t for t in data["traza"] if t["agente"] not in ("cumplimiento", "fraude")]
    return data


def build_journey_router(
    journey: CreditJourneyService,
    require_client: Callable[..., None],
    analyst_key: str | None,
    demo_scenarios: tuple[dict[str, str], ...] = (),
) -> APIRouter:
    router = APIRouter(prefix="/v1")

    def require_analyst(x_analyst_key: str | None = Header(default=None)) -> None:
        if analyst_key is None:
            return
        if x_analyst_key is None or not hmac.compare_digest(x_analyst_key, analyst_key):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Clave de analista inválida")

    def _load(fn: Callable[[], Application]) -> Application:
        try:
            return fn()
        except ApplicationNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Solicitud no encontrada") from exc
        except InvalidTransitionError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    @router.get("/agents")
    def agents() -> dict[str, Any]:
        return {
            "agentes": [
                {
                    "id": a.id, "nombre": a.name, "objetivo": a.goal, "herramientas": list(a.tools),
                    "permisos": list(a.permissions), "informa": list(a.informs), "recomienda": list(a.recommends),
                    "ejecuta": list(a.executes), "nunca": list(a.never), "memoria": a.memory,
                    "transfiere_a": [agent_name(h) for h in a.handoff_to], "usa_llm": a.uses_llm,
                }
                for a in AGENTS
            ],
            "personas": [
                {"id": r.id, "nombre": r.name, "decide": r.decides, "sla_horas": r.sla_hours} for r in HUMAN_ROLES
            ],
        }

    @router.get("/demo/scenarios")
    def scenarios() -> list[dict[str, str]]:
        return list(demo_scenarios)

    @router.post("/applications", dependencies=[Depends(require_client)], status_code=201)
    def create(body: ApplicationIn) -> dict[str, Any]:
        consent = Consent(body.consent.habeas_data, body.consent.credit_bureau, body.consent.invoice_registry)
        try:
            app = journey.start(body.nit, consent)
        except InvalidNitError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        return serialize(app)

    @router.get("/applications/{application_id}", dependencies=[Depends(require_client)])
    def read(application_id: str) -> dict[str, Any]:
        return serialize(_load(lambda: journey.get(application_id)))

    @router.post("/applications/{application_id}/accept", dependencies=[Depends(require_client)])
    def accept(application_id: str) -> dict[str, Any]:
        return serialize(_load(lambda: journey.accept_offer(application_id)))

    @router.get("/analyst/queue", dependencies=[Depends(require_analyst)])
    def queue() -> list[dict[str, Any]]:
        return [serialize(a, for_analyst=True) for a in journey.human_queue()]

    @router.post("/analyst/applications/{application_id}/decision", dependencies=[Depends(require_analyst)])
    def decide(application_id: str, body: DecisionIn) -> dict[str, Any]:
        app = _load(lambda: journey.human_decision(application_id, body.reviewer, body.approve, body.reason))
        return serialize(app, for_analyst=True)

    return router
