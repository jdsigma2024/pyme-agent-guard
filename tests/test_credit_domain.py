from datetime import date, timedelta

import pytest

from pyme_guard.domain.credit import (
    BureauReport,
    Company,
    CreditPolicy,
    Exclusion,
    Invoice,
    RadianStatus,
    assess_risk,
    build_offer,
    effective_annual,
    parse_nit,
    required_approver,
    screen_invoices,
)
from pyme_guard.domain.errors import InvalidNitError

TODAY = date(2026, 11, 5)
POLICY = CreditPolicy()
COMPANY = Company("900123456", "Demo S.A.S.", "C1410", 7, 4_800_000_000)
GOOD = BureauReport(812, 0, False, 0.22)


def inv(days=60, rating="AAA", status=RadianStatus.TITULO_VALOR, amount=10_000_000):
    return Invoice("CUFE", "800", "Pagador", rating, amount, TODAY, TODAY + timedelta(days=days), status)


# ------------------------------ NIT ------------------------------------- #
@pytest.mark.parametrize("raw", ["900123456-8", "900.123.456-8", " 900123456 ", "860002964-4"])
def test_parse_valid_nit(raw):
    assert parse_nit(raw).isdigit()


@pytest.mark.parametrize("raw", ["900123456-9", "abc", "", "12-3", "900123456-88"])
def test_parse_invalid_nit(raw):
    with pytest.raises(InvalidNitError):
        parse_nit(raw)


# --------------------------- Facturas ----------------------------------- #
@pytest.mark.parametrize(
    "invoice, reason",
    [
        (inv(status=RadianStatus.ENDOSADA), Exclusion.YA_ENDOSADA),
        (inv(status=RadianStatus.PENDIENTE_ACEPTACION), Exclusion.NO_ACEPTADA),
        (inv(status=RadianStatus.PAGADA), Exclusion.PAGADA),
        (inv(rating="BB"), Exclusion.PAGADOR_NO_ELEGIBLE),
        (inv(days=5), Exclusion.VENCE_PRONTO),
        (inv(days=200), Exclusion.PLAZO_EXCEDE),
    ],
)
def test_invoice_exclusions(invoice, reason):
    result = screen_invoices([invoice], TODAY, POLICY)
    assert result.eligible == ()
    assert result.excluded[0][1] is reason


def test_endorsed_invoice_is_a_fraud_signal():
    result = screen_invoices([inv(), inv(status=RadianStatus.ENDOSADA)], TODAY, POLICY)
    assert len(result.eligible) == 1 and len(result.fraud_signals) == 1


# ----------------------------- Riesgo ----------------------------------- #
def test_good_company_gets_band_a_with_reasons():
    risk = assess_risk(COMPANY, GOOD, POLICY)
    assert risk.band == "A"
    assert any("banda A" in r for r in risk.reasons)


def test_knockouts_are_explained():
    young = Company("1", "x", "y", 1, 1_000_000_000)
    risk = assess_risk(young, BureauReport(500, 60, True, 0.9), POLICY)
    assert risk.band is None
    assert len(risk.reasons) == 5  # cada criterio incumplido tiene su explicación


# ----------------------------- Oferta ----------------------------------- #
def test_offer_math_and_indicative_flag():
    eligible = (inv(days=60, amount=100_000_000),)
    offer = build_offer(COMPANY, eligible, assess_risk(COMPANY, GOOD, POLICY), TODAY, POLICY)
    assert offer.advance_cop == 90_000_000
    assert offer.discount_cop == round(90_000_000 * 0.0155 * 60 / 30)
    assert offer.net_disbursement_cop == offer.advance_cop - offer.discount_cop - offer.fee_cop
    assert offer.indicative is True
    assert offer.effective_annual_rate <= POLICY.max_effective_annual_rate


def test_advance_is_capped_by_credit_line():
    small = Company("1", "x", "y", 7, 100_000_000)  # cupo = 15 % de ventas = 15 M
    offer = build_offer(small, (inv(amount=100_000_000),), assess_risk(small, GOOD, POLICY), TODAY, POLICY)
    assert offer.advance_cop == 15_000_000


def test_price_above_ceiling_is_impossible():
    greedy = CreditPolicy(monthly_rate={"A": 0.03, "B": 0.03, "C": 0.03})
    with pytest.raises(ValueError):
        build_offer(COMPANY, (inv(),), assess_risk(COMPANY, GOOD, greedy), TODAY, greedy)


def test_no_offer_without_band():
    with pytest.raises(ValueError):
        build_offer(COMPANY, (inv(),), assess_risk(COMPANY, BureauReport(400, 90, True, 1), POLICY), TODAY, POLICY)


@pytest.mark.parametrize(
    "amount, role", [(0, "automatica"), (1, "analista_credito"), (800_000_000, "comite_credito")]
)
def test_required_approver(amount, role):
    assert required_approver(amount, POLICY) == role


def test_pilot_policy_never_auto_approves_real_amounts():
    assert POLICY.auto_approval_limit_cop == 0


def test_effective_annual():
    assert round(effective_annual(0.0155), 4) == 0.2027
