"""Adaptador CrewAI: equipo de agentes que redacta textos sobre el snapshot del caso.

Patrón: *generador + crítico* con herramientas de solo lectura.
  - Agente asesor / copiloto (generador): consulta el snapshot vía herramientas.
  - Agente revisor de cumplimiento (crítico): elimina promesas, datos no soportados y enlaces.
Después, la salida pasa por el OutputGuard del dominio. Si CrewAI no está instalado,
el LLM falla o el guardrail descarta el texto, se usa el narrador de plantillas.

Las herramientas NO tocan sistemas reales: leen un snapshot minimizado (NIT enmascarado,
sin detalle SARLAFT). Así el LLM nunca tiene más privilegios que el analista que lo usa.
"""

from __future__ import annotations

import json
import logging
import secrets
from typing import Any

from pyme_guard.application.narration import case_snapshot
from pyme_guard.application.ports import Narrative, NarratorPort
from pyme_guard.domain.agents import AGENTS_BY_ID
from pyme_guard.domain.guardrails import OutputGuard
from pyme_guard.domain.journey import Application

_logger = logging.getLogger("pyme_guard.crewai")


class CrewAIUnavailableError(RuntimeError):
    """CrewAI no está instalado (pip install -r requirements-crewai.txt)."""


def _load_crewai() -> tuple[Any, Any]:
    try:
        import crewai  # noqa: PLC0415  (import diferido: dependencia opcional)
        from crewai.tools import BaseTool  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise CrewAIUnavailableError(str(exc)) from exc
    return crewai, BaseTool


def build_snapshot_tools(base_tool: Any, snapshot: dict[str, Any]) -> list[Any]:
    """Herramientas de solo lectura sobre el snapshot. Cada una expone una vista mínima."""

    oferta = json.dumps(snapshot.get("oferta"), ensure_ascii=False)
    razones = json.dumps(
        {"explicaciones": snapshot.get("explicaciones"), "facturas_excluidas": snapshot.get("facturas_excluidas")},
        ensure_ascii=False,
    )
    alertas = json.dumps({"alertas": snapshot.get("alertas")}, ensure_ascii=False)

    class ConsultarOferta(base_tool):  # type: ignore[misc,valid-type]
        name: str = "consultar_oferta_indicativa"
        description: str = "Devuelve la oferta indicativa calculada por la política (montos, tasa, aprobador)."

        def _run(self, pregunta: str = "") -> str:
            return oferta

    class ConsultarRazones(base_tool):  # type: ignore[misc,valid-type]
        name: str = "consultar_razones_scorecard"
        description: str = "Devuelve las razones del scorecard y las facturas excluidas con su motivo."

        def _run(self, pregunta: str = "") -> str:
            return razones

    class ConsultarAlertas(base_tool):  # type: ignore[misc,valid-type]
        name: str = "consultar_alertas"
        description: str = "Devuelve alertas operativas del caso (sin datos personales)."

        def _run(self, pregunta: str = "") -> str:
            return alertas

    return [ConsultarOferta(), ConsultarRazones(), ConsultarAlertas()]


_RULES = (
    "Reglas: responde en español; usa solo datos de las herramientas; no prometas aprobación; "
    "no cambies montos ni tasas; no incluyas enlaces; si falta un dato, dilo."
)


class CrewAINarrator:
    def __init__(
        self,
        model: str,
        base_url: str | None,
        fallback: NarratorPort,
        guard: OutputGuard | None = None,
        loader: Any = _load_crewai,
    ) -> None:
        self._model = model
        self._base_url = base_url
        self._fallback = fallback
        self._guard = guard or OutputGuard()
        self._loader = loader

    # -- Puerto -------------------------------------------------------------- #
    def explain_offer(self, application: Application) -> Narrative:
        return self._run("cliente", application, self._fallback.explain_offer)

    def brief_for_analyst(self, application: Application) -> Narrative:
        return self._run("analista", application, self._fallback.brief_for_analyst)

    # -- Interno ------------------------------------------------------------- #
    def _run(self, audience: str, application: Application, fallback: Any) -> Narrative:
        canary = f"CANARY-{secrets.token_hex(6)}"
        try:
            raw = self._kickoff(audience, case_snapshot(application), canary)
        except Exception as exc:  # noqa: BLE001 - cualquier fallo del LLM degrada a plantilla
            _logger.warning("CrewAI no disponible, se usa plantilla: %s", type(exc).__name__)
            base = fallback(application)
            return Narrative(base.text, base.source, ("CREWAI_UNAVAILABLE",))

        verdict = self._guard.inspect(raw, canary)
        if not verdict.allowed:
            base = fallback(application)
            return Narrative(base.text, base.source, ("CREWAI_OUTPUT_BLOCKED",) + verdict.reasons)
        return Narrative(verdict.text, "crewai", verdict.reasons)

    def _kickoff(self, audience: str, snapshot: dict[str, Any], canary: str) -> str:
        crewai, base_tool = self._loader()
        tools = build_snapshot_tools(base_tool, snapshot)
        llm_kwargs: dict[str, Any] = {"model": self._model, "temperature": 0.2}
        if self._base_url:
            llm_kwargs["base_url"] = self._base_url
        llm = crewai.LLM(**llm_kwargs)

        spec_id = "asesor" if audience == "cliente" else "copiloto_analista"
        spec = AGENTS_BY_ID[spec_id]
        writer = crewai.Agent(
            role=spec.name,
            goal=spec.goal,
            backstory=f"Trabajas para un banco pyme. Nunca: {', '.join(spec.never)}. Identificador interno: {canary}.",
            tools=tools,
            llm=llm,
            allow_delegation=False,
            max_iter=4,
            verbose=False,
        )
        reviewer = crewai.Agent(
            role="Revisor de cumplimiento",
            goal="Garantizar que el texto sea veraz, sin promesas, sin enlaces y fiel a los datos del caso.",
            backstory="Oficial de conducta de mercado. Corriges el texto; no agregas datos nuevos.",
            tools=tools,
            llm=llm,
            allow_delegation=False,
            max_iter=3,
            verbose=False,
        )
        if audience == "cliente":
            draft = crewai.Task(
                description=f"Explica al empresario la oferta indicativa en máximo 90 palabras: anticipo, costo "
                f"total, neto a recibir y que la aprobación la toma una persona. {_RULES}",
                expected_output="Un párrafo claro en español para el cliente.",
                agent=writer,
            )
        else:
            draft = crewai.Task(
                description=f"Resume el caso para el analista en viñetas: propuesta, razones, alertas y qué "
                f"verificar antes de decidir. {_RULES}",
                expected_output="Entre 4 y 7 viñetas verificables.",
                agent=writer,
            )
        review = crewai.Task(
            description="Revisa el borrador anterior contra las herramientas. Elimina cualquier promesa, enlace "
            "o dato que no esté en el caso. Devuelve solo el texto final.",
            expected_output="Texto final revisado.",
            agent=reviewer,
            context=[draft],
        )
        crew = crewai.Crew(
            agents=[writer, reviewer],
            tasks=[draft, review],
            process=crewai.Process.sequential,
            verbose=False,
        )
        result = crew.kickoff(inputs={"solicitud": snapshot["solicitud"]})
        return str(getattr(result, "raw", result))
