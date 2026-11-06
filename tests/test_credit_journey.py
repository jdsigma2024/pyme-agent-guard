import pytest

from pyme_guard.application.credit_journey import NEUTRAL_REVIEW_MESSAGE
from pyme_guard.domain.credit import Consent
from pyme_guard.domain.errors import ApplicationNotFoundError, InvalidNitError, InvalidTransitionError
from pyme_guard.domain.journey import ActionKind, Application, AppStatus

OK = Consent(True, True, True)


def test_happy_path_reaches_indicative_offer_then_human(journey):
    app = journey.start("900123456-8", OK)
    assert app.status is AppStatus.OFFER_READY
    assert app.offer is not None and app.offer.indicative
    assert "analista" in app.client_message

    journey.accept_offer(app.id)
    assert app.status is AppStatus.PENDING_APPROVAL
    assert app.handoff.role == "analista_credito"
    assert app.analyst_brief  # el copiloto preparó el resumen
    assert app in journey.human_queue()

    journey.human_decision(app.id, "ana.analista", True, "Cumple política y flujo de caja")
    assert app.status is AppStatus.APPROVED
    assert app.trace[-2].action is ActionKind.HUMAN
    assert "doble firma" in app.trace[-1].summary
    assert app not in journey.human_queue()


def test_without_consent_no_system_is_queried(journey_parts):
    journey, data, _ = journey_parts
    app = journey.start("900123456-8", Consent(True, False, True))
    assert app.status is AppStatus.CONSENT_REQUIRED
    assert data.calls == []
    assert "centrales de riesgo" in app.client_message


def test_sanctions_hit_holds_case_without_tipping_off(journey_parts):
    journey, data, _ = journey_parts
    app = journey.start("900555001", OK)
    assert app.status is AppStatus.COMPLIANCE_REVIEW
    assert app.handoff.role == "oficial_cumplimiento"
    assert app.client_message == NEUTRAL_REVIEW_MESSAGE
    assert "lista" not in app.client_message.lower()
    assert "radian" not in data.calls and "central" not in data.calls  # se detiene antes


def test_double_negotiated_invoice_goes_to_fraud(journey):
    app = journey.start("900777002", OK)
    assert app.status is AppStatus.FRAUD_REVIEW
    assert app.handoff.role == "analista_fraude"
    assert app.offer is None


def test_bureau_down_degrades_to_human_and_never_invents_offer(journey):
    app = journey.start("900888003", OK)
    assert app.status is AppStatus.MANUAL_REVIEW
    assert app.offer is None
    assert any(step.outcome == "error" for step in app.trace)


def test_not_eligible_is_explained(journey):
    app = journey.start("900999004", OK)
    assert app.status is AppStatus.NOT_ELIGIBLE
    assert len(app.explanations) >= 2
    assert "aliada" in app.client_message


def test_unknown_company_is_not_eligible(journey):
    assert journey.start("901234567-7", OK).status is AppStatus.NOT_ELIGIBLE


def test_invalid_nit_is_rejected(journey):
    with pytest.raises(InvalidNitError):
        journey.start("900123456-1", OK)


# --------------------- Invariantes de gobierno ------------------------- #
def test_ai_pipeline_can_never_set_final_decision():
    app = Application(id="x", nit="1", consent=OK)
    for forbidden in (AppStatus.APPROVED, AppStatus.DECLINED, AppStatus.PENDING_APPROVAL):
        with pytest.raises(InvalidTransitionError):
            app.set_pipeline_outcome(forbidden)


def test_cannot_approve_without_passing_through_human_queue(journey):
    app = journey.start("900999004", OK)  # no elegible
    with pytest.raises(InvalidTransitionError):
        journey.human_decision(app.id, "ana", True, "Quiero aprobar igual")


def test_human_decision_requires_justification(journey):
    app = journey.start("900123456", OK)
    journey.accept_offer(app.id)
    with pytest.raises(InvalidTransitionError):
        journey.human_decision(app.id, "ana", True, "   ")


def test_accept_only_valid_offer(journey):
    app = journey.start("900888003", OK)
    with pytest.raises(InvalidTransitionError):
        journey.accept_offer(app.id)


def test_released_compliance_alert_goes_to_manual_review_not_approval(journey):
    app = journey.start("900555001", OK)
    journey.human_decision(app.id, "oficial", True, "Homónimo descartado con documento")
    assert app.status is AppStatus.MANUAL_REVIEW
    assert app.handoff.role == "analista_credito"


def test_unknown_application(journey):
    with pytest.raises(ApplicationNotFoundError):
        journey.get("nope")


def test_every_step_is_audited_without_raw_nit(journey_parts):
    journey, _, log = journey_parts
    app = journey.start("900123456", OK)
    assert len(log.events) == len(app.trace)
    assert all("900123456" not in repr(e) for e in log.events)
