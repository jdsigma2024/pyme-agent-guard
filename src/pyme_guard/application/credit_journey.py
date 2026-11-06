"""Caso de uso: solicitud de liquidez con facturas electrónicas (orquestador nativo).

Principio: *el LLM propone, la política dispone*. Las decisiones salen de reglas
deterministas del dominio; los agentes con IA generativa solo redactan textos
(explicación al cliente, resumen al analista) y pasan por el OutputGuard.
Aprobar, rechazar en definitiva y desembolsar son siempre acciones humanas.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date

from pyme_guard.application.narration import cop
from pyme_guard.application.ports import (
    ApplicationRepositoryPort,
    CompanyRegistryPort,
    CreditBureauPort,
    DecisionEvent,
    DecisionLogPort,
    InvoiceRegistryPort,
    NarratorPort,
    SanctionsPort,
)
from pyme_guard.domain.agents import ROLES_BY_ID
from pyme_guard.domain.credit import (
    Consent,
    CreditPolicy,
    assess_risk,
    build_offer,
    mask_nit,
    parse_nit,
    screen_invoices,
)
from pyme_guard.domain.errors import (
    ApplicationNotFoundError,
    InvalidTransitionError,
    SourceUnavailableError,
)
from pyme_guard.domain.journey import (
    ActionKind,
    Application,
    AppStatus,
    Handoff,
    HumanDecision,
    TraceStep,
)

NEUTRAL_REVIEW_MESSAGE = (
    "Tu solicitud requiere una validación adicional por parte del banco. "
    "Un asesor te contactará en un máximo de 2 días hábiles."
)
MANUAL_REVIEW_MESSAGE = (
    "Uno de los sistemas de consulta no está disponible. No generamos una oferta sin información "
    "completa: un analista revisará tu caso y te contactará en menos de 24 horas."
)


class CreditJourneyService:
    def __init__(
        self,
        registry: CompanyRegistryPort,
        sanctions: SanctionsPort,
        invoices: InvoiceRegistryPort,
        bureau: CreditBureauPort,
        repository: ApplicationRepositoryPort,
        decision_log: DecisionLogPort,
        narrator: NarratorPort,
        policy: CreditPolicy | None = None,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._registry = registry
        self._sanctions = sanctions
        self._invoices = invoices
        self._bureau = bureau
        self._repo = repository
        self._log = decision_log
        self._narrator = narrator
        self._policy = policy or CreditPolicy()
        self._today = today

    @property
    def policy(self) -> CreditPolicy:
        return self._policy

    # ------------------------------------------------------------------ #
    # 1. Solicitud: flujo automático hasta oferta indicativa o handoff
    # ------------------------------------------------------------------ #
    def start(self, raw_nit: str, consent: Consent) -> Application:
        nit = parse_nit(raw_nit)  # InvalidNitError -> 422 en la API
        app = Application(id=uuid.uuid4().hex[:12], nit=nit, consent=consent)
        self._step(app, "orquestador", ActionKind.EXECUTE, "Recibe la solicitud y valida el NIT (dígito de verificación DIAN).")
        try:
            self._run_pipeline(app)
        finally:
            self._repo.save(app)
        return app

    def _run_pipeline(self, app: Application) -> None:
        policy, today = self._policy, self._today()

        # -- Consentimiento: sin autorización no se consulta ningún sistema.
        if not app.consent.complete:
            missing = ", ".join(app.consent.missing())
            self._step(app, "onboarding", ActionKind.INFORM,
                       f"Faltan autorizaciones: {missing}. No se consulta ningún sistema.", outcome="bloqueo")
            app.client_message = (
                f"Para continuar necesitamos tu autorización para: {missing}. "
                "Solo usamos estos datos para evaluar esta solicitud y puedes revocarla cuando quieras."
            )
            app.set_pipeline_outcome(AppStatus.CONSENT_REQUIRED)
            return
        self._step(app, "onboarding", ActionKind.EXECUTE,
                   f"Registra autorizaciones versión {app.consent.version} (Ley 1581/2012, Ley 1266/2008).",
                   systems=("Registro de consentimientos",))

        # -- Existencia y vigencia de la empresa.
        company = self._registry.lookup(app.nit)
        if company is None or not company.active_registry:
            self._step(app, "onboarding", ActionKind.INFORM,
                       "La empresa no aparece con matrícula mercantil vigente.", systems=("RUES",), outcome="bloqueo")
            app.explanations.append("No encontramos una matrícula mercantil vigente para este NIT.")
            app.client_message = "No pudimos verificar la matrícula mercantil vigente. Revisa el NIT o renueva la matrícula."
            app.set_pipeline_outcome(AppStatus.NOT_ELIGIBLE)
            return
        app.company_name = company.name
        self._step(app, "onboarding", ActionKind.EXECUTE,
                   f"Verifica matrícula vigente: {company.name}, {company.years_operating:g} años, sector {company.sector}.",
                   systems=("RUES",))

        # -- SARLAFT antes de cualquier oferta. Nunca se revela la coincidencia (no tipping-off).
        screening = self._sanctions.screen(app.nit, company.name)
        if screening.hit:
            self._step(app, "cumplimiento", ActionKind.RECOMMEND,
                       "Coincidencia en listas restrictivas: se retiene el caso.",
                       systems=("Listas restrictivas (ONU/OFAC/PEP)",), outcome="alerta")
            self._handoff(app, "oficial_cumplimiento", "Coincidencia potencial en listas restrictivas")
            app.client_message = NEUTRAL_REVIEW_MESSAGE
            app.set_pipeline_outcome(AppStatus.COMPLIANCE_REVIEW)
            return
        self._step(app, "cumplimiento", ActionKind.RECOMMEND, "Sin coincidencias en listas restrictivas.",
                   systems=("Listas restrictivas (ONU/OFAC/PEP)",))

        # -- Facturas RADIAN y señales de fraude.
        try:
            invoices = self._invoices.invoices_for(app.nit)
        except SourceUnavailableError:
            return self._degrade(app, "facturas", "RADIAN")
        result = screen_invoices(invoices, today, policy)
        app.exclusions = [
            {"cufe": inv.cufe[-8:], "pagador": inv.payer_name, "motivo": why.value} for inv, why in result.excluded
        ]
        self._step(app, "facturas", ActionKind.RECOMMEND,
                   f"{len(invoices)} facturas consultadas: {len(result.eligible)} elegibles, {len(result.excluded)} excluidas.",
                   systems=("RADIAN (DIAN)",))

        if result.fraud_signals:
            self._step(app, "fraude", ActionKind.RECOMMEND,
                       f"{len(result.fraud_signals)} factura(s) ya endosada(s) a otro tenedor: posible doble negociación.",
                       systems=("RADIAN (DIAN)", "Reglas de fraude"), outcome="alerta")
            self._handoff(app, "analista_fraude", "Factura presentada que ya figura endosada en RADIAN")
            app.client_message = NEUTRAL_REVIEW_MESSAGE
            app.set_pipeline_outcome(AppStatus.FRAUD_REVIEW)
            return

        if not result.eligible:
            app.explanations.append(
                "Ninguna factura cumple la política (pagador elegible, aceptada en RADIAN y vencimiento entre "
                f"{policy.min_days_to_due} y {policy.max_days_to_due} días)."
            )
            app.client_message = (
                "Hoy no tienes facturas negociables. Cuando tus clientes acepten facturas en RADIAN podrás "
                "volver a intentarlo; un asesor puede orientarte."
            )
            app.set_pipeline_outcome(AppStatus.NOT_ELIGIBLE)
            return

        # -- Riesgo: si la central no responde, se degrada a una persona (nunca se inventa la oferta).
        try:
            report = self._bureau.report(app.nit)
        except SourceUnavailableError:
            return self._degrade(app, "riesgo", "Central de riesgo")
        risk = assess_risk(company, report, policy)
        app.explanations.extend(risk.reasons)
        if risk.band is None:
            self._step(app, "riesgo", ActionKind.RECOMMEND,
                       "No cumple criterios de la política; se explican las razones al cliente.",
                       systems=("Central de riesgo", f"Política {policy.version}"), outcome="bloqueo")
            app.client_message = (
                "Por ahora no podemos ofrecerte este producto. Te explicamos las razones abajo; "
                "puedes pedir revisión a un asesor o te referimos a una entidad aliada del banco."
            )
            app.set_pipeline_outcome(AppStatus.NOT_ELIGIBLE)
            return

        app.offer = build_offer(company, result.eligible, risk, today, policy)
        self._step(app, "riesgo", ActionKind.RECOMMEND,
                   f"Banda {risk.band}: propone anticipo de {cop(app.offer.advance_cop)} "
                   f"({app.offer.advance_rate:.0%}) a {app.offer.monthly_rate:.2%} mensual. Oferta indicativa.",
                   systems=("Central de riesgo", f"Política {policy.version}"))

        narrative = self._narrator.explain_offer(app)
        app.client_message = narrative.text
        app.narrative_source = narrative.source
        self._step(app, "asesor", ActionKind.INFORM,
                   f"Explica costo total y siguientes pasos (fuente: {narrative.source}).",
                   systems=("Snapshot del caso",), outcome="alerta" if narrative.notes else "ok")
        app.set_pipeline_outcome(AppStatus.OFFER_READY)

    # ------------------------------------------------------------------ #
    # 2. Aceptación del cliente -> cola humana con resumen del copiloto
    # ------------------------------------------------------------------ #
    def accept_offer(self, application_id: str) -> Application:
        app = self._get(application_id)
        if app.status is not AppStatus.OFFER_READY or app.offer is None:
            raise InvalidTransitionError("Solo se acepta una oferta indicativa vigente")
        app.move_to(AppStatus.PENDING_APPROVAL)
        role = app.offer.required_approver
        brief = self._narrator.brief_for_analyst(app)
        app.analyst_brief = brief.text
        self._step(app, "copiloto_analista", ActionKind.INFORM,
                   f"Prepara resumen verificable del caso (fuente: {brief.source}).", systems=("Snapshot del caso",))
        self._handoff(app, role, "Aprobación de cupo y desembolso: decisión humana obligatoria")
        app.client_message = (
            "Recibimos tu aceptación. Un analista del banco revisará la operación; "
            f"tiempo objetivo de respuesta: {ROLES_BY_ID[role].sla_hours} horas."
        )
        self._repo.save(app)
        return app

    # ------------------------------------------------------------------ #
    # 3. Decisión humana (maker) -> orden de desembolso con doble control (checker)
    # ------------------------------------------------------------------ #
    def human_decision(self, application_id: str, reviewer: str, approve: bool, reason: str) -> Application:
        app = self._get(application_id)
        if not reason or not reason.strip():
            raise InvalidTransitionError("Toda decisión humana debe registrar una justificación")
        if approve and app.status in (AppStatus.COMPLIANCE_REVIEW, AppStatus.FRAUD_REVIEW):
            # Un caso retenido se libera a revisión manual; no salta directo a aprobado.
            app.move_to(AppStatus.MANUAL_REVIEW)
            app.decision = HumanDecision(reviewer, True, reason.strip())
            self._step(app, reviewer, ActionKind.HUMAN, "Libera la alerta; el caso pasa a revisión de crédito.")
            self._handoff(app, "analista_credito", "Alerta resuelta por la persona responsable")
            self._repo.save(app)
            return app

        app.move_to(AppStatus.APPROVED if approve else AppStatus.DECLINED)
        app.decision = HumanDecision(reviewer, approve, reason.strip())
        self._step(app, reviewer, ActionKind.HUMAN,
                   ("Aprueba" if approve else "Rechaza") + f" la operación. Justificación: {reason.strip()}")
        if approve:
            self._step(app, "orquestador", ActionKind.EXECUTE,
                       "Prepara la orden de desembolso y el endoso en RADIAN; la liberación en el core "
                       "exige doble firma de operaciones.", systems=("Core bancario", "RADIAN (DIAN)"))
            app.client_message = (
                "Tu operación fue aprobada por un analista del banco. Operaciones liberará el desembolso "
                "una vez se registre el endoso en RADIAN."
            )
        else:
            app.client_message = (
                "Después de la revisión, el banco no aprobó esta operación. Un asesor te explicará "
                "las razones y alternativas."
            )
        app.handoff = None
        self._repo.save(app)
        return app

    def get(self, application_id: str) -> Application:
        return self._get(application_id)

    def human_queue(self) -> list[Application]:
        return self._repo.human_queue()

    # ------------------------------------------------------------------ #
    def _get(self, application_id: str) -> Application:
        app = self._repo.get(application_id)
        if app is None:
            raise ApplicationNotFoundError(application_id)
        return app

    def _degrade(self, app: Application, agent_id: str, system: str) -> None:
        self._step(app, agent_id, ActionKind.EXECUTE, f"{system} no respondió. No se inventa información.",
                   systems=(system,), outcome="error")
        self._handoff(app, "analista_credito", f"{system} no disponible: evaluación manual")
        app.client_message = MANUAL_REVIEW_MESSAGE
        app.set_pipeline_outcome(AppStatus.MANUAL_REVIEW)

    def _handoff(self, app: Application, role: str, reason: str) -> None:
        human = ROLES_BY_ID[role]
        app.handoff = Handoff(role=role, reason=reason, sla_hours=human.sla_hours)
        self._step(app, "orquestador", ActionKind.HANDOFF, f"Transfiere a {human.name}: {reason}.",
                   systems=("Cola de casos",), handoff_to=role)

    def _step(self, app: Application, agent_id: str, action: ActionKind, summary: str,
              systems: tuple[str, ...] = (), outcome: str = "ok", handoff_to: str | None = None) -> None:
        app.log(TraceStep(agent_id, action, summary, systems, outcome, handoff_to))
        self._log.record_decision(
            DecisionEvent(app.id, mask_nit(app.nit), agent_id, action.value, app.status.value, outcome)
        )
