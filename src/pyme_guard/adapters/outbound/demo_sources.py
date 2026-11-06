"""Datos 100 % ficticios (empresas, pagadores y NIT) para el prototipo: simulan RUES, listas, RADIAN y centrales.

Cada NIT representa un camino del journey (feliz y de excepción). En producción
estos adaptadores se reemplazan por integraciones reales sin tocar el núcleo.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

from pyme_guard.domain.credit import (
    BureauReport,
    Company,
    Invoice,
    RadianStatus,
    SanctionsResult,
    nit_check_digit,
)
from pyme_guard.domain.errors import SourceUnavailableError


@dataclass(frozen=True, slots=True)
class DemoScenario:
    nit: str
    company: Company
    path: str
    description: str
    bureau: BureauReport | None  # None = central de riesgo caída
    sanctions_hit: bool = False
    invoice_plan: tuple[tuple[str, str, int, int, RadianStatus], ...] = ()  # pagador, rating, monto, días, estado

    @property
    def nit_with_dv(self) -> str:
        return f"{self.nit}-{nit_check_digit(self.nit)}"


_GOOD_BUREAU = BureauReport(score=812, max_days_past_due_12m=0, active_defaults=False, debt_to_sales=0.22)
_T = RadianStatus.TITULO_VALOR

SCENARIOS: tuple[DemoScenario, ...] = (
    DemoScenario(
        nit="900123456",
        company=Company("900123456", "Confecciones Andinas S.A.S.", "C1410 Confección", 7, 4_800_000_000),
        path="feliz",
        description="Facturas aceptadas a grandes superficies; buen historial. Llega a oferta y decisión humana.",
        bureau=_GOOD_BUREAU,
        invoice_plan=(
            ("Gran Superficie Andina S.A.", "AAA", 86_000_000, 58, _T),
            ("Retail Pacífico S.A.", "AA", 54_500_000, 74, _T),
            ("Distribuidora Local Ltda.", "BB", 12_000_000, 40, _T),  # pagador no elegible
            ("Moda Express S.A.", "AA", 31_200_000, 9, _T),  # vence pronto
        ),
    ),
    DemoScenario(
        nit="900555001",
        company=Company("900555001", "Logística Sabana S.A.S.", "H4923 Transporte de carga", 4, 2_100_000_000),
        path="excepcion_sarlaft",
        description="Coincidencia en listas restrictivas: retención y oficial de cumplimiento, sin revelar el motivo.",
        bureau=_GOOD_BUREAU,
        sanctions_hit=True,
        invoice_plan=(("Lácteos del Valle S.A.", "AAA", 40_000_000, 45, _T),),
    ),
    DemoScenario(
        nit="900777002",
        company=Company("900777002", "Agroinsumos del Llano S.A.S.", "G4664 Comercio de insumos", 6, 3_300_000_000),
        path="excepcion_fraude",
        description="Una factura ya figura endosada a otro tenedor en RADIAN: posible doble negociación.",
        bureau=_GOOD_BUREAU,
        invoice_plan=(
            ("Alimentos Cordillera S.A.", "AAA", 62_000_000, 50, _T),
            ("Alimentos Cordillera S.A.", "AAA", 48_000_000, 65, RadianStatus.ENDOSADA),
        ),
    ),
    DemoScenario(
        nit="900888003",
        company=Company("900888003", "Metalmecánica Caribe S.A.S.", "C2592 Metalmecánica", 9, 6_200_000_000),
        path="excepcion_sistema_caido",
        description="La central de riesgo no responde: el caso se degrada a un analista; no se inventa oferta.",
        bureau=None,
        invoice_plan=(("Cementera del Norte S.A.", "AAA", 95_000_000, 60, _T),),
    ),
    DemoScenario(
        nit="900999004",
        company=Company("900999004", "Servicios Digitales Nova S.A.S.", "J6201 Desarrollo de software", 1.5, 900_000_000),
        path="no_elegible_explicado",
        description="Menos de 2 años y mora reciente: no hay oferta y se explican las razones y alternativas.",
        bureau=BureauReport(score=588, max_days_past_due_12m=45, active_defaults=False, debt_to_sales=0.41),
        invoice_plan=(("Fintech Ejemplo S.A.", "AA", 20_000_000, 30, _T),),
    ),
)

_BY_NIT = {s.nit: s for s in SCENARIOS}


class DemoDataset:
    """Implementa CompanyRegistryPort, SanctionsPort, InvoiceRegistryPort y CreditBureauPort."""

    def __init__(self, today: Callable[[], date] = date.today) -> None:
        self._today = today

    def lookup(self, nit: str) -> Company | None:
        scenario = _BY_NIT.get(nit)
        return scenario.company if scenario else None

    def screen(self, nit: str, name: str) -> SanctionsResult:
        scenario = _BY_NIT.get(nit)
        if scenario and scenario.sanctions_hit:
            return SanctionsResult(True, "Coincidencia parcial de nombre en lista OFAC SDN (demo)")
        return SanctionsResult(False)

    def invoices_for(self, nit: str) -> list[Invoice]:
        scenario = _BY_NIT.get(nit)
        if scenario is None:
            return []
        today = self._today()
        return [
            Invoice(
                cufe=f"CUFE{nit}{i:04d}{'a1b2c3d4'}",
                payer_nit=f"8{i:08d}",
                payer_name=payer,
                payer_rating=rating,
                amount_cop=amount,
                issue_date=today - timedelta(days=10),
                due_date=today + timedelta(days=days),
                status=status,
            )
            for i, (payer, rating, amount, days, status) in enumerate(scenario.invoice_plan, start=1)
        ]

    def report(self, nit: str) -> BureauReport:
        scenario = _BY_NIT.get(nit)
        if scenario is None:
            raise SourceUnavailableError("NIT sin datos en la central (demo)")
        if scenario.bureau is None:
            raise SourceUnavailableError("Central de riesgo no disponible (timeout simulado)")
        return scenario.bureau
