from datetime import date

import pytest

from pyme_guard.adapters.outbound.demo_sources import DemoDataset
from pyme_guard.adapters.outbound.memory_repository import InMemoryApplicationRepository
from pyme_guard.application.credit_journey import CreditJourneyService
from pyme_guard.application.narration import TemplateNarrator

TODAY = date(2026, 11, 5)


class MemoryDecisionLog:
    def __init__(self):
        self.events = []

    def record_decision(self, event):
        self.events.append(event)


class SpyDataset(DemoDataset):
    """Cuenta las consultas a sistemas externos (para probar minimización y consentimiento)."""

    def __init__(self):
        super().__init__(today=lambda: TODAY)
        self.calls = []

    def lookup(self, nit):
        self.calls.append("rues")
        return super().lookup(nit)

    def screen(self, nit, name):
        self.calls.append("listas")
        return super().screen(nit, name)

    def invoices_for(self, nit):
        self.calls.append("radian")
        return super().invoices_for(nit)

    def report(self, nit):
        self.calls.append("central")
        return super().report(nit)


@pytest.fixture
def journey_parts():
    data = SpyDataset()
    log = MemoryDecisionLog()
    service = CreditJourneyService(
        data, data, data, data, InMemoryApplicationRepository(), log, TemplateNarrator(), today=lambda: TODAY
    )
    return service, data, log


@pytest.fixture
def journey(journey_parts):
    return journey_parts[0]
