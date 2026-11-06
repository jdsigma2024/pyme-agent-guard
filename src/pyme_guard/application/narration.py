"""Snapshot minimizado del caso + narrador determinista (plantillas).

El snapshot es lo único que ven los agentes con IA generativa: NIT enmascarado,
sin datos de personas naturales, sin detalle de listas restrictivas.
"""

from __future__ import annotations

from typing import Any

from pyme_guard.application.ports import Narrative
from pyme_guard.domain.credit import mask_nit
from pyme_guard.domain.journey import Application


def cop(value: int | float) -> str:
    return "$" + f"{value:,.0f}".replace(",", ".")


def case_snapshot(app: Application) -> dict[str, Any]:
    offer = app.offer
    return {
        "solicitud": app.id,
        "empresa": app.company_name,
        "nit": mask_nit(app.nit),
        "estado": app.status.value,
        "explicaciones": list(app.explanations),
        "facturas_excluidas": [{"pagador": e["pagador"], "motivo": e["motivo"]} for e in app.exclusions],
        "oferta": None
        if offer is None
        else {
            "banda": offer.band,
            "cupo_rotativo": offer.credit_line_cop,
            "facturas_incluidas": offer.invoices_count,
            "valor_facturas": offer.invoices_total_cop,
            "porcentaje_anticipo": offer.advance_rate,
            "anticipo": offer.advance_cop,
            "tasa_mensual": offer.monthly_rate,
            "tasa_efectiva_anual": offer.effective_annual_rate,
            "dias_promedio": offer.weighted_days,
            "descuento": offer.discount_cop,
            "comision": offer.fee_cop,
            "neto_a_recibir": offer.net_disbursement_cop,
            "aprobador_requerido": offer.required_approver,
            "politica": offer.policy_version,
        },
        "alertas": [s.summary for s in app.trace if s.outcome in ("alerta", "error")],
    }


class TemplateNarrator:
    """Narrador por defecto: determinista, auditable y sin costo de IA."""

    def explain_offer(self, application: Application) -> Narrative:
        o = application.offer
        if o is None:
            return Narrative("", "plantilla")
        text = (
            f"Oferta indicativa: anticipamos {cop(o.advance_cop)} ({o.advance_rate:.0%}) sobre "
            f"{o.invoices_count} factura(s) por {cop(o.invoices_total_cop)}, con vencimiento promedio de "
            f"{o.weighted_days} días. Costo: {o.monthly_rate:.2%} mensual ({o.effective_annual_rate:.1%} E.A.) "
            f"= {cop(o.discount_cop)} de descuento y {cop(o.fee_cop)} de comisión. Recibirías "
            f"{cop(o.net_disbursement_cop)} netos. Es indicativa: la aprobación la toma un analista del banco."
        )
        return Narrative(text, "plantilla")

    def brief_for_analyst(self, application: Application) -> Narrative:
        snap = case_snapshot(application)
        o = snap["oferta"] or {}
        lines = [
            f"Caso {snap['solicitud']} · {snap['empresa']} · NIT {snap['nit']}",
            f"Propuesta: anticipo {cop(o.get('anticipo', 0))} (banda {o.get('banda', '-')}, "
            f"{o.get('tasa_mensual', 0):.2%} m.v.), cupo rotativo {cop(o.get('cupo_rotativo', 0))}.",
            "Razones del scorecard: " + " ".join(snap["explicaciones"]),
            f"Facturas excluidas: {len(snap['facturas_excluidas'])}.",
            "Alertas: " + ("; ".join(snap["alertas"]) if snap["alertas"] else "ninguna."),
            "Verificar: estados financieros del último corte y concentración por pagador.",
        ]
        return Narrative("\n".join(lines), "plantilla")
