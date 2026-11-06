"""Registro de agentes: fuente única de verdad sobre objetivos, herramientas, permisos,
memoria y handoffs. Lo usan el orquestador nativo, el adaptador CrewAI, la API
(/v1/agents) y la documentación. Cambiar un permiso aquí cambia todo el sistema.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AgentSpec:
    id: str
    name: str
    goal: str
    tools: tuple[str, ...]
    permissions: tuple[str, ...]  # mínimo privilegio; todo es lectura salvo lo declarado
    informs: tuple[str, ...]
    recommends: tuple[str, ...]
    executes: tuple[str, ...]
    never: tuple[str, ...]  # decisiones reservadas a personas
    memory: str
    handoff_to: tuple[str, ...]
    uses_llm: bool


@dataclass(frozen=True, slots=True)
class HumanRole:
    id: str
    name: str
    decides: str
    sla_hours: int


AGENTS: tuple[AgentSpec, ...] = (
    AgentSpec(
        id="orquestador",
        name="Orquestador del caso",
        goal="Llevar la solicitud por la máquina de estados, invocar agentes y garantizar los controles.",
        tools=("maquina_estados", "cola_casos", "bitacora_auditoria"),
        permissions=("escritura:estado_solicitud", "escritura:cola_casos", "escritura:auditoria"),
        informs=("estado de la solicitud",),
        recommends=(),
        executes=("transiciones permitidas", "encolar casos para personas"),
        never=("aprobar", "rechazar en definitiva", "desembolsar"),
        memory="Estado del caso (corto plazo, por solicitud). Sin memoria entre clientes.",
        handoff_to=("analista_credito", "comite_credito", "oficial_cumplimiento", "analista_fraude"),
        uses_llm=False,
    ),
    AgentSpec(
        id="onboarding",
        name="Agente de onboarding y consentimiento",
        goal="Explicar el producto, capturar autorizaciones y verificar la existencia de la empresa.",
        tools=("registro_consentimientos", "rues_consulta"),
        permissions=("escritura:consentimientos", "lectura:rues"),
        informs=("requisitos", "para qué se usa cada dato", "estado del trámite"),
        recommends=(),
        executes=("registrar consentimiento otorgado por el cliente",),
        never=("consultar datos sin autorización",),
        memory="Versión de la autorización firmada y sello de tiempo.",
        handoff_to=("asesor_pyme",),
        uses_llm=False,
    ),
    AgentSpec(
        id="cumplimiento",
        name="Agente de cumplimiento (SARLAFT/KYB)",
        goal="Detectar coincidencias en listas restrictivas y beneficiarios finales antes de cualquier oferta.",
        tools=("listas_restrictivas",),
        permissions=("lectura:listas_restrictivas",),
        informs=(),
        recommends=("retener el caso",),
        executes=(),
        never=("revelar al cliente una coincidencia en listas", "vincular o rechazar en definitiva"),
        memory="Ninguna fuera del caso; el detalle de la coincidencia solo lo ve el oficial.",
        handoff_to=("oficial_cumplimiento",),
        uses_llm=False,
    ),
    AgentSpec(
        id="facturas",
        name="Agente de facturas (RADIAN)",
        goal="Traer las facturas electrónicas y filtrar las negociables según política.",
        tools=("radian_consulta",),
        permissions=("lectura:radian",),
        informs=("qué facturas califican y por qué otras no",),
        recommends=("facturas a incluir",),
        executes=(),
        never=("endosar facturas",),
        memory="Snapshot de facturas del caso con su CUFE.",
        handoff_to=("analista_fraude",),
        uses_llm=False,
    ),
    AgentSpec(
        id="fraude",
        name="Agente guardián de fraude",
        goal="Detectar doble negociación de facturas y señales anómalas.",
        tools=("radian_consulta", "reglas_fraude"),
        permissions=("lectura:radian",),
        informs=(),
        recommends=("retener el caso",),
        executes=(),
        never=("acusar al cliente", "bloquear cuentas"),
        memory="Señales del caso; patrones agregados sin PII para mejorar reglas.",
        handoff_to=("analista_fraude",),
        uses_llm=False,
    ),
    AgentSpec(
        id="riesgo",
        name="Agente de riesgo",
        goal="Consultar centrales, aplicar el scorecard explicable y proponer una oferta dentro de política.",
        tools=("central_riesgo", "politica_credito", "scorecard"),
        permissions=("lectura:central_riesgo", "lectura:politica"),
        informs=(),
        recommends=("banda de riesgo", "cupo", "anticipo", "tasa"),
        executes=(),
        never=("aprobar", "ofrecer por encima del techo de tasa", "modificar la política"),
        memory="Resultado del scorecard y versión de política usada.",
        handoff_to=("analista_credito", "comite_credito"),
        uses_llm=False,
    ),
    AgentSpec(
        id="asesor",
        name="Agente asesor (IA generativa)",
        goal="Explicar en lenguaje claro la oferta, costos y siguientes pasos; responder dudas con guardrails.",
        tools=("snapshot_caso", "base_conocimiento_productos"),
        permissions=("lectura:snapshot_caso",),
        informs=("costo total", "comparación anticipo vs. espera", "siguientes pasos"),
        recommends=("si la oferta encaja con la necesidad declarada",),
        executes=(),
        never=("prometer aprobación", "fijar tasas", "incluir enlaces", "repetir PII"),
        memory="Conversación de la sesión con PII enmascarada; sin memoria de largo plazo.",
        handoff_to=("asesor_pyme",),
        uses_llm=True,
    ),
    AgentSpec(
        id="copiloto_analista",
        name="Copiloto del analista (IA generativa)",
        goal="Preparar un resumen verificable del caso para que la persona decida más rápido.",
        tools=("snapshot_caso",),
        permissions=("lectura:snapshot_caso",),
        informs=("resumen del caso", "alertas", "datos faltantes"),
        recommends=("puntos a revisar",),
        executes=(),
        never=("decidir", "ocultar alertas"),
        memory="Ninguna; cada resumen se genera desde el snapshot y se audita.",
        handoff_to=("analista_credito",),
        uses_llm=True,
    ),
)

HUMAN_ROLES: tuple[HumanRole, ...] = (
    HumanRole("analista_credito", "Analista de crédito", "Aprueba o rechaza cupos bajo su atribución", 24),
    HumanRole("comite_credito", "Comité de crédito", "Aprueba montos sobre el umbral de comité", 72),
    HumanRole("oficial_cumplimiento", "Oficial de cumplimiento", "Resuelve coincidencias SARLAFT", 48),
    HumanRole("analista_fraude", "Analista de fraude", "Resuelve señales de doble negociación", 24),
    HumanRole("asesor_pyme", "Asesor pyme", "Atiende dudas y casos que el agente no resuelve", 8),
)

AGENTS_BY_ID = {agent.id: agent for agent in AGENTS}
ROLES_BY_ID = {role.id: role for role in HUMAN_ROLES}


def agent_name(agent_id: str) -> str:
    if agent_id in AGENTS_BY_ID:
        return AGENTS_BY_ID[agent_id].name
    if agent_id in ROLES_BY_ID:
        return ROLES_BY_ID[agent_id].name
    return agent_id
