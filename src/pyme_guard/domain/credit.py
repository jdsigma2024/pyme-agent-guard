"""Dominio de crédito pyme: descuento de facturas electrónicas (RADIAN).

Todo es lógica pura y explicable (sin I/O, sin LLM). Aquí viven las reglas que
deciden elegibilidad, banda de riesgo y oferta indicativa. Los agentes pueden
*recomendar* usando estas reglas, pero nunca saltárselas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from pyme_guard.domain.errors import InvalidNitError

# --------------------------------------------------------------------------- #
# NIT colombiano (algoritmo de dígito de verificación de la DIAN, módulo 11)
# --------------------------------------------------------------------------- #
_NIT_WEIGHTS = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)


def nit_check_digit(base: str) -> int:
    total = sum(int(d) * w for d, w in zip(reversed(base), _NIT_WEIGHTS, strict=False))
    remainder = total % 11
    return remainder if remainder < 2 else 11 - remainder


def parse_nit(raw: str) -> str:
    """Normaliza '900.123.456-8' -> '900123456'. Si trae dígito de verificación, lo valida."""
    text = re.sub(r"[\s.]", "", raw or "")
    match = re.fullmatch(r"(\d{6,15})(?:-(\d))?", text)
    if not match:
        raise InvalidNitError("NIT con formato inválido")
    base, dv = match.groups()
    if dv is not None and int(dv) != nit_check_digit(base):
        raise InvalidNitError("Dígito de verificación del NIT inválido")
    return base


def mask_nit(nit: str) -> str:
    return "*" * max(len(nit) - 3, 0) + nit[-3:]


# --------------------------------------------------------------------------- #
# Datos de entrada (vienen de RUES, RADIAN, centrales de riesgo)
# --------------------------------------------------------------------------- #
class RadianStatus(StrEnum):
    TITULO_VALOR = "titulo_valor"  # aceptada (expresa o tácita): negociable
    PENDIENTE_ACEPTACION = "pendiente_aceptacion"
    ENDOSADA = "endosada"  # ya fue negociada con otro tenedor
    PAGADA = "pagada"


@dataclass(frozen=True, slots=True)
class Company:
    nit: str
    name: str
    sector: str
    years_operating: float
    annual_sales_cop: int
    active_registry: bool = True


@dataclass(frozen=True, slots=True)
class Invoice:
    cufe: str
    payer_nit: str
    payer_name: str
    payer_rating: str  # calificación interna del pagador (AAA..B)
    amount_cop: int
    issue_date: date
    due_date: date
    status: RadianStatus


@dataclass(frozen=True, slots=True)
class BureauReport:
    score: int  # 150..950
    max_days_past_due_12m: int
    active_defaults: bool
    debt_to_sales: float


@dataclass(frozen=True, slots=True)
class SanctionsResult:
    hit: bool
    detail: str | None = None  # solo para el oficial de cumplimiento; nunca al cliente


@dataclass(frozen=True, slots=True)
class Consent:
    """Autorizaciones explícitas (Ley 1581 de 2012 y Ley 1266 de 2008)."""

    habeas_data: bool
    credit_bureau: bool
    invoice_registry: bool
    version: str = "AUT-2026-11"

    @property
    def complete(self) -> bool:
        return self.habeas_data and self.credit_bureau and self.invoice_registry

    def missing(self) -> tuple[str, ...]:
        labels = {
            "habeas_data": "tratamiento de datos personales",
            "credit_bureau": "consulta en centrales de riesgo",
            "invoice_registry": "consulta de facturas en RADIAN",
        }
        return tuple(label for key, label in labels.items() if not getattr(self, key))


# --------------------------------------------------------------------------- #
# Política (parámetros que el banco aprueba en comité; versionados)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class CreditPolicy:
    version: str = "POL-LF-0.3"
    min_years_operating: float = 2.0
    min_bureau_score: int = 600
    max_days_past_due: int = 30
    max_debt_to_sales: float = 0.6
    eligible_payer_ratings: tuple[str, ...] = ("AAA", "AA", "A", "BBB")
    min_days_to_due: int = 15
    max_days_to_due: int = 120
    advance_rate: dict[str, float] = field(
        default_factory=lambda: {"A": 0.90, "B": 0.85, "C": 0.80}
    )
    monthly_rate: dict[str, float] = field(
        default_factory=lambda: {"A": 0.0155, "B": 0.0175, "C": 0.0199}
    )
    operation_fee_rate: float = 0.0025  # comisión por operación sobre el anticipo
    max_line_pct_sales: float = 0.15
    max_line_cop: int = 1_500_000_000
    # Techo prudencial interno (tasa de usura certificada, nov-2026: 28,34 % E.A.).
    max_effective_annual_rate: float = 0.2834
    # Autonomías: en el piloto ninguna operación se aprueba sin una persona.
    auto_approval_limit_cop: int = 0
    committee_threshold_cop: int = 800_000_000


# --------------------------------------------------------------------------- #
# Reglas
# --------------------------------------------------------------------------- #
class Exclusion(StrEnum):
    PAGADOR_NO_ELEGIBLE = "pagador_no_elegible"
    NO_ACEPTADA = "factura_no_aceptada"
    YA_ENDOSADA = "factura_ya_endosada"
    PAGADA = "factura_pagada"
    VENCE_PRONTO = "vence_pronto"
    PLAZO_EXCEDE = "plazo_excede_politica"


@dataclass(frozen=True, slots=True)
class InvoiceScreening:
    eligible: tuple[Invoice, ...]
    excluded: tuple[tuple[Invoice, Exclusion], ...]

    @property
    def fraud_signals(self) -> tuple[Invoice, ...]:
        return tuple(inv for inv, why in self.excluded if why is Exclusion.YA_ENDOSADA)


def screen_invoices(invoices: list[Invoice], today: date, policy: CreditPolicy) -> InvoiceScreening:
    eligible: list[Invoice] = []
    excluded: list[tuple[Invoice, Exclusion]] = []
    for inv in invoices:
        days = (inv.due_date - today).days
        if inv.status is RadianStatus.ENDOSADA:
            excluded.append((inv, Exclusion.YA_ENDOSADA))
        elif inv.status is RadianStatus.PAGADA:
            excluded.append((inv, Exclusion.PAGADA))
        elif inv.status is not RadianStatus.TITULO_VALOR:
            excluded.append((inv, Exclusion.NO_ACEPTADA))
        elif inv.payer_rating not in policy.eligible_payer_ratings:
            excluded.append((inv, Exclusion.PAGADOR_NO_ELEGIBLE))
        elif days < policy.min_days_to_due:
            excluded.append((inv, Exclusion.VENCE_PRONTO))
        elif days > policy.max_days_to_due:
            excluded.append((inv, Exclusion.PLAZO_EXCEDE))
        else:
            eligible.append(inv)
    return InvoiceScreening(tuple(eligible), tuple(excluded))


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    band: str | None  # A, B, C o None (no elegible)
    points: int
    reasons: tuple[str, ...]  # explicación en lenguaje claro (positiva y negativa)


def assess_risk(company: Company, bureau: BureauReport, policy: CreditPolicy) -> RiskAssessment:
    """Scorecard explicable: cada punto tiene una razón legible por el cliente y el analista."""
    reasons: list[str] = []
    knockout = False

    if company.years_operating < policy.min_years_operating:
        knockout = True
        reasons.append(f"La empresa tiene menos de {policy.min_years_operating:g} años de operación.")
    if bureau.active_defaults:
        knockout = True
        reasons.append("Registra obligaciones en mora vigentes en centrales de riesgo.")
    if bureau.score < policy.min_bureau_score:
        knockout = True
        reasons.append(f"El puntaje en centrales ({bureau.score}) está por debajo del mínimo ({policy.min_bureau_score}).")
    if bureau.max_days_past_due_12m > policy.max_days_past_due:
        knockout = True
        reasons.append(f"Tuvo moras superiores a {policy.max_days_past_due} días en los últimos 12 meses.")
    if bureau.debt_to_sales > policy.max_debt_to_sales:
        knockout = True
        reasons.append("El endeudamiento frente a ventas supera el límite de la política.")

    points = 0
    points += 30 if bureau.score >= 800 else 20 if bureau.score >= 700 else 10
    points += 20 if company.years_operating >= 5 else 10
    points += 20 if bureau.debt_to_sales <= 0.3 else 10
    points += 20 if bureau.max_days_past_due_12m == 0 else 5

    if knockout:
        return RiskAssessment(None, points, tuple(reasons))

    band = "A" if points >= 80 else "B" if points >= 60 else "C"
    reasons.append(f"Puntaje interno {points}/90 → banda {band}.")
    if bureau.max_days_past_due_12m == 0:
        reasons.append("Sin moras en los últimos 12 meses.")
    if company.years_operating >= 5:
        reasons.append("Trayectoria de 5 o más años.")
    return RiskAssessment(band, points, tuple(reasons))


@dataclass(frozen=True, slots=True)
class Offer:
    band: str
    credit_line_cop: int
    invoices_count: int
    invoices_total_cop: int
    advance_rate: float
    advance_cop: int
    monthly_rate: float
    effective_annual_rate: float
    weighted_days: int
    discount_cop: int
    fee_cop: int
    net_disbursement_cop: int
    required_approver: str
    policy_version: str
    indicative: bool = True  # siempre indicativa hasta la decisión humana


def effective_annual(monthly_rate: float) -> float:
    return (1 + monthly_rate) ** 12 - 1


def required_approver(amount_cop: int, policy: CreditPolicy) -> str:
    if amount_cop <= policy.auto_approval_limit_cop:
        return "automatica"
    if amount_cop >= policy.committee_threshold_cop:
        return "comite_credito"
    return "analista_credito"


def build_offer(
    company: Company, eligible: tuple[Invoice, ...], risk: RiskAssessment, today: date, policy: CreditPolicy
) -> Offer:
    if risk.band is None or not eligible:
        raise ValueError("No se puede construir oferta sin banda de riesgo y facturas elegibles")

    line = min(int(company.annual_sales_cop * policy.max_line_pct_sales), policy.max_line_cop)
    total = sum(inv.amount_cop for inv in eligible)
    rate_adv = policy.advance_rate[risk.band]
    advance = min(int(total * rate_adv), line)

    weighted_days = round(
        sum((inv.due_date - today).days * inv.amount_cop for inv in eligible) / total
    )
    monthly = policy.monthly_rate[risk.band]
    ea = effective_annual(monthly)
    if ea > policy.max_effective_annual_rate:  # invariante: nunca se ofrece por encima del techo
        raise ValueError("La tasa supera el techo prudencial de la política")

    discount = round(advance * monthly * weighted_days / 30)
    fee = round(advance * policy.operation_fee_rate)
    return Offer(
        band=risk.band,
        credit_line_cop=line,
        invoices_count=len(eligible),
        invoices_total_cop=total,
        advance_rate=rate_adv,
        advance_cop=advance,
        monthly_rate=monthly,
        effective_annual_rate=round(ea, 4),
        weighted_days=weighted_days,
        discount_cop=discount,
        fee_cop=fee,
        net_disbursement_cop=advance - discount - fee,
        required_approver=required_approver(advance, policy),
        policy_version=policy.version,
    )
