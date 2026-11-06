"""Raíz de composición: el único lugar que conoce las implementaciones concretas."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI

from pyme_guard.adapters.inbound.api import Brand, create_app
from pyme_guard.adapters.outbound.demo_sources import SCENARIOS, DemoDataset
from pyme_guard.adapters.outbound.fake_llm import FakeLLM
from pyme_guard.adapters.outbound.logging_audit import LoggingAudit
from pyme_guard.adapters.outbound.memory_repository import InMemoryApplicationRepository
from pyme_guard.adapters.outbound.ollama_llm import OllamaLLM
from pyme_guard.application.assistant_service import AssistantService
from pyme_guard.application.credit_journey import CreditJourneyService
from pyme_guard.application.narration import TemplateNarrator
from pyme_guard.application.ports import LLMPort, NarratorPort
from pyme_guard.config import Settings


def build_llm(settings: Settings) -> LLMPort:
    if settings.llm_provider == "ollama":
        return OllamaLLM(settings.ollama_base_url, settings.ollama_model, settings.ollama_timeout)
    return FakeLLM()


def build_narrator(settings: Settings) -> NarratorPort:
    template = TemplateNarrator()
    if settings.narrator == "crewai":
        from pyme_guard.adapters.outbound.crewai_narrator import CrewAINarrator  # noqa: PLC0415

        return CrewAINarrator(settings.crewai_model, settings.crewai_base_url, fallback=template)
    return template


def build_journey(settings: Settings, audit: LoggingAudit) -> CreditJourneyService:
    data = DemoDataset()  # sustituir por adaptadores reales: RUES, KYB, RADIAN, centrales
    return CreditJourneyService(
        registry=data,
        sanctions=data,
        invoices=data,
        bureau=data,
        repository=InMemoryApplicationRepository(),
        decision_log=audit,
        narrator=build_narrator(settings),
    )


def create_default_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = Settings()
    audit = LoggingAudit()
    service = AssistantService(llm=build_llm(settings), audit=audit)
    provider = (
        f"Ollama · {settings.ollama_model}" if settings.llm_provider == "ollama" else "Demo (sin modelo)"
    )
    narrator_label = "CrewAI" if settings.narrator == "crewai" else "Plantillas"
    brand = Brand(
        name=settings.brand_name,
        tagline=settings.brand_tagline,
        provider=f"{provider} · Narrador: {narrator_label}",
        auth_required=settings.api_key is not None,
        analyst_auth_required=settings.analyst_key is not None,
    )
    api_key = settings.api_key.get_secret_value() if settings.api_key else None
    analyst_key = settings.analyst_key.get_secret_value() if settings.analyst_key else None
    return create_app(
        service,
        api_key,
        brand,
        Path(settings.brand_dir),
        journey=build_journey(settings, audit),
        analyst_key=analyst_key,
        demo_scenarios=demo_scenarios(),
    )


def demo_scenarios() -> tuple[dict[str, str], ...]:
    return tuple(
        {"nit": s.nit_with_dv, "empresa": s.company.name, "camino": s.path, "descripcion": s.description}
        for s in SCENARIOS
    )
