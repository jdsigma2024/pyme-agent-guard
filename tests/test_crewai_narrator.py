"""El adaptador CrewAI se prueba con un módulo falso: valida el cableado (agentes, tareas,
herramientas de solo lectura), el guardrail de salida y la degradación a plantilla,
sin depender de un LLM ni de tener CrewAI instalado."""

import json
import types

from pyme_guard.adapters.outbound.crewai_narrator import CrewAINarrator, build_snapshot_tools
from pyme_guard.application.narration import TemplateNarrator, case_snapshot
from pyme_guard.domain.credit import Consent


class _Base:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def fake_crewai(reply="Te anticipamos el 90 % de tus facturas; una persona del banco decide.", error=None):
    created = {"agents": [], "tasks": [], "crews": []}

    class Agent(_Base):
        def __init__(self, **kw):
            super().__init__(**kw)
            created["agents"].append(self)

    class Task(_Base):
        def __init__(self, **kw):
            super().__init__(**kw)
            created["tasks"].append(self)

    class Crew(_Base):
        def __init__(self, **kw):
            super().__init__(**kw)
            created["crews"].append(self)

        def kickoff(self, inputs):
            if error:
                raise error
            return types.SimpleNamespace(raw=reply)

    module = types.SimpleNamespace(
        Agent=Agent, Task=Task, Crew=Crew, LLM=_Base, Process=types.SimpleNamespace(sequential="sequential")
    )
    return (lambda: (module, _Base)), created


def offer_app(journey):
    return journey.start("900123456", Consent(True, True, True))


def test_crew_is_generator_plus_critic_with_read_only_tools(journey):
    loader, created = fake_crewai()
    narrator = CrewAINarrator("ollama/llama3.2", "http://ollama:11434", TemplateNarrator(), loader=loader)
    result = narrator.explain_offer(offer_app(journey))

    assert result.source == "crewai"
    assert len(created["agents"]) == 2  # generador + revisor
    review = created["tasks"][1]
    assert review.context == [created["tasks"][0]]  # el crítico revisa el borrador
    assert created["crews"][0].process == "sequential"
    tool_names = {t.name for t in created["agents"][0].tools}
    assert tool_names == {"consultar_oferta_indicativa", "consultar_razones_scorecard", "consultar_alertas"}


def test_tools_expose_masked_snapshot_only(journey):
    app = offer_app(journey)
    tools = build_snapshot_tools(_Base, case_snapshot(app))
    payload = " ".join(t._run() for t in tools)
    assert "900123456" not in payload
    assert json.loads(tools[0]._run())["anticipo"] == app.offer.advance_cop


def test_guardrail_blocks_llm_promise_and_falls_back(journey):
    loader, _ = fake_crewai(reply="¡Felicitaciones! Tu crédito ha sido aprobado.")
    narrator = CrewAINarrator("m", None, TemplateNarrator(), loader=loader)
    result = narrator.explain_offer(offer_app(journey))
    assert result.source == "plantilla"
    assert "CREWAI_OUTPUT_BLOCKED" in result.notes
    assert "aprobado" not in result.text


def test_guardrail_strips_links(journey):
    loader, _ = fake_crewai(reply="Revisa https://evil.example para más detalles del anticipo.")
    result = CrewAINarrator("m", None, TemplateNarrator(), loader=loader).explain_offer(offer_app(journey))
    assert result.source == "crewai" and "evil.example" not in result.text


def test_llm_failure_degrades_to_template(journey):
    loader, _ = fake_crewai(error=TimeoutError("llm down"))
    result = CrewAINarrator("m", None, TemplateNarrator(), loader=loader).brief_for_analyst(offer_app(journey))
    assert result.source == "plantilla" and "CREWAI_UNAVAILABLE" in result.notes


def test_missing_crewai_package_degrades_to_template(journey):
    def loader():
        raise ImportError("No module named crewai")

    result = CrewAINarrator("m", None, TemplateNarrator(), loader=loader).explain_offer(offer_app(journey))
    assert result.source == "plantilla"
