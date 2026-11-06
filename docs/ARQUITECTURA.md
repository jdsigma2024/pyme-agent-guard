# Arquitectura · Liquidez Factura (banca pyme agéntica)

**Autor:** Jose Sanchez · **Versión:** 0.3.0 · **Fecha:** noviembre de 2026
**Alcance:** prueba técnica *AI Product Engineer · Banca Pyme agéntica* (caso ficticio).

Este documento describe la arquitectura con el modelo **C4** (contexto → contenedores → componentes → código), los agentes, los controles y cómo se despliega en contenedores. Todos los diagramas son Mermaid y se renderizan directamente en GitHub/GitLab.

> **Leyenda de alcance.** ✅ implementado en el prototipo · 🟡 simulado con datos ficticios · 🔜 roadmap (ver [ROADMAP.md](ROADMAP.md)).

---

## 1. Principios de diseño

| Principio | Cómo se materializa |
|---|---|
| **El LLM propone, la política dispone** | Elegibilidad, banda de riesgo, cupo y tasa salen de reglas deterministas y versionadas (`domain/credit.py`). La IA generativa solo redacta textos y pasa por el `OutputGuard`. |
| **Humano responsable en toda decisión crítica** | La máquina de estados (`domain/journey.py`) impide que el flujo automático fije `aprobada` o `rechazada`. Solo `human_decision()` con justificación obligatoria. |
| **Mínimo privilegio para agentes** | Registro único de agentes (`domain/agents.py`): los agentes con LLM solo leen un *snapshot* minimizado del caso; ninguno escribe en sistemas core. |
| **Fallar hacia una persona** | Si una central de riesgo o RADIAN no responde, el caso va a un analista (`revision_manual`). Nunca se inventa una oferta. |
| **Privacidad por diseño** | Sin consentimiento no se consulta ningún sistema; NIT enmascarado en snapshot y auditoría; PII enmascarada antes del LLM. |
| **Arquitectura hexagonal** | `adapters → application → domain`. Cambiar Ollama por otro modelo, o el orquestador por CrewAI, no toca el núcleo. |
| **Evals como compuerta** | `evals/run_evals.py` mide guardrails, journey e invariantes de gobierno y falla el CI si no se cumplen umbrales. |

---

## 2. C4 · Nivel 1: Contexto del sistema

```mermaid
C4Context
  title Contexto · Liquidez Factura (banco de segundo piso con oferta directa a pymes)

  Person(pyme, "Empresario pyme", "Gerente o contador de una pequeña/mediana empresa facturadora electrónica")
  Person(analista, "Analista de crédito / comité", "Aprueba cupos y desembolsos")
  Person(oficial, "Oficial de cumplimiento y analista de fraude", "Resuelven alertas SARLAFT y doble negociación")

  System(lf, "Liquidez Factura", "Journey digital + plataforma agéntica: onboarding, evaluación, oferta indicativa, handoff humano")

  System_Ext(rues, "RUES", "Registro mercantil (cámaras de comercio)")
  System_Ext(radian, "RADIAN · DIAN", "Registro de facturas electrónicas como título valor")
  System_Ext(buro, "Centrales de riesgo", "Historial crediticio (con autorización)")
  System_Ext(kyb, "Proveedor KYB / listas", "Listas restrictivas, PEP, beneficiario final")
  System_Ext(core, "Core bancario y pagos", "Desembolso, recaudo, contabilidad")
  System_Ext(llm, "Proveedor de modelos", "Ollama local o API gestionada")
  System_Ext(aliados, "Entidades aliadas (red de segundo piso)", "Reciben referidos que no califican")

  Rel(pyme, lf, "Solicita anticipo, autoriza datos, acepta oferta", "HTTPS")
  Rel(analista, lf, "Revisa cola y decide", "HTTPS + SSO")
  Rel(oficial, lf, "Resuelve alertas", "HTTPS + SSO")
  Rel(lf, rues, "Verifica matrícula", "API")
  Rel(lf, radian, "Consulta y endosa facturas", "API vía proveedor tecnológico / SNE")
  Rel(lf, buro, "Consulta historial", "API")
  Rel(lf, kyb, "Screening", "API")
  Rel(lf, core, "Orden de desembolso (doble firma)", "API / mensajería")
  Rel(lf, llm, "Redacción de textos con snapshot minimizado", "HTTPS")
  Rel(lf, aliados, "Referidos con consentimiento", "API")

  UpdateLayoutConfig($c4ShapeInRow="4", $c4BoundaryInRow="1")
```

**Por qué así:** el banco de segundo piso conserva su red de aliados (los casos no elegibles se refieren con consentimiento) y abre una relación directa en un producto *autoliquidable* y rico en datos (facturas aceptadas en RADIAN), donde el riesgo se apoya en la calidad del pagador.

---

## 3. C4 · Nivel 2: Contenedores (arquitectura objetivo)

```mermaid
C4Container
  title Contenedores · arquitectura objetivo (producción)

  Person(pyme, "Empresario pyme")
  Person(analista, "Analista / oficial")

  System_Boundary(lf, "Liquidez Factura") {
    Container(web, "Web pyme + consola analista", "HTML/JS (prototipo) · React (objetivo)", "Journey, traza visible de agentes, cola humana")
    Container(gw, "API Gateway / WAF", "Kong · Azure APIM · AWS API GW", "OIDC, rate limiting, mTLS hacia adentro")
    Container(api, "API de solicitudes y orquestador", "Python · FastAPI", "Máquina de estados, políticas, handoffs")
    Container(agents, "Servicio de agentes", "Python · CrewAI (opcional) · plantillas", "Asesor, copiloto del analista; guardrails de entrada/salida")
    Container(guard, "Guardrails y evals", "Python", "InputGuard, OutputGuard, canary, set de ataques en CI")
    Container(integ, "Adaptadores de integración", "Python · colas", "RUES, RADIAN, centrales, KYB, core")
    ContainerDb(db, "Solicitudes, consentimientos, auditoría", "PostgreSQL cifrado", "Estado del caso, versión de política, decisiones humanas")
    ContainerQueue(bus, "Bus de eventos", "Kafka / Service Bus", "Eventos de caso para operación y analítica")
    Container(obs, "Observabilidad LLM", "OpenTelemetry + Langfuse", "Trazas, costo por caso, calidad")
    Container(llmgw, "Gateway de modelos", "LiteLLM / Ollama", "Ruteo de modelos, presupuesto, PII masking")
  }

  System_Ext(ext, "RUES · RADIAN · Centrales · KYB")
  System_Ext(core, "Core bancario")

  Rel(pyme, web, "Usa", "HTTPS")
  Rel(analista, web, "Decide", "HTTPS + SSO")
  Rel(web, gw, "Llama", "HTTPS/JSON")
  Rel(gw, api, "Enruta", "mTLS")
  Rel(api, agents, "Pide narrativas", "HTTP interno")
  Rel(agents, guard, "Valida salida")
  Rel(agents, llmgw, "Inferencia", "HTTPS")
  Rel(api, integ, "Consulta datos")
  Rel(integ, ext, "API")
  Rel(api, db, "Lee/escribe", "SQL")
  Rel(api, bus, "Publica eventos")
  Rel(integ, core, "Orden de desembolso")
  Rel(agents, obs, "Trazas y costos")

  UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

**Hoy (v0.3):** web, API, orquestador, agentes y guardrails corren en **un solo contenedor** FastAPI (monolito modular hexagonal), con repositorio en memoria y fuentes simuladas. La separación en contenedores es una decisión de escalado, no un rediseño: los límites ya existen como puertos.

---

## 4. C4 · Nivel 3: Componentes del servicio (mapeados al código)

```mermaid
C4Component
  title Componentes · API + orquestador + agentes (src/pyme_guard)

  Container_Boundary(app, "pyme_guard") {
    Component(http, "Adaptador HTTP", "adapters/inbound/api.py · journey_api.py", "Rutas, esquemas estrictos, claves, CSP, vista cliente vs. analista")
    Component(journey, "CreditJourneyService", "application/credit_journey.py", "Orquestador nativo: consentimiento → RUES → SARLAFT → RADIAN → fraude → riesgo → oferta → handoff")
    Component(assistant, "AssistantService", "application/assistant_service.py", "Chat con defensa en profundidad")
    Component(narr, "NarratorPort", "application/narration.py", "Snapshot minimizado + narrador de plantillas")
    Component(crew, "CrewAINarrator", "adapters/outbound/crewai_narrator.py", "Generador + crítico con herramientas de solo lectura")
    Component(policy, "Política y scorecard", "domain/credit.py", "Elegibilidad, bandas, oferta, techo de tasa, autonomías")
    Component(sm, "Máquina de estados", "domain/journey.py", "Transiciones permitidas; la IA no puede aprobar")
    Component(reg, "Registro de agentes", "domain/agents.py", "Objetivos, herramientas, permisos, memoria, handoffs")
    Component(guards, "Guardrails", "domain/guardrails.py", "InputGuard, HandoffPolicy, OutputGuard")
    Component(src, "Fuentes de datos", "adapters/outbound/demo_sources.py", "RUES, listas, RADIAN, centrales (simuladas)")
    Component(repo, "Repositorio", "adapters/outbound/memory_repository.py", "Solicitudes y cola humana")
    Component(audit, "Auditoría", "adapters/outbound/logging_audit.py", "JSON por línea sin PII")
  }

  Rel(http, journey, "start / accept / decide")
  Rel(http, assistant, "chat")
  Rel(journey, policy, "aplica")
  Rel(journey, sm, "transiciona")
  Rel(journey, narr, "explica / resume")
  Rel(crew, narr, "implementa el puerto")
  Rel(crew, guards, "OutputGuard")
  Rel(crew, reg, "lee roles y límites")
  Rel(journey, src, "consulta (puertos)")
  Rel(journey, repo, "persiste")
  Rel(journey, audit, "registra cada paso")
  Rel(assistant, guards, "filtra")

  UpdateLayoutConfig($c4ShapeInRow="4", $c4BoundaryInRow="1")
```

### Nivel 4 (código): hexagonal

```mermaid
flowchart LR
  subgraph IN[Adaptadores de entrada]
    API[FastAPI · api.py / journey_api.py]
    WEB[Pantalla web · textContent, CSP]
  end
  subgraph APP[Aplicación]
    J[CreditJourneyService]
    A[AssistantService]
    P{{Puertos: Registry, Sanctions, Invoices,<br/>Bureau, Repository, DecisionLog, Narrator, LLM}}
  end
  subgraph DOM[Dominio · puro, sin I/O]
    C[credit.py · política y scorecard]
    S[journey.py · máquina de estados]
    G[guardrails.py]
    R[agents.py · registro]
  end
  subgraph OUT[Adaptadores de salida]
    D[demo_sources · RUES/RADIAN/centrales/listas]
    M[memory_repository]
    L[logging_audit]
    T[TemplateNarrator]
    CR[CrewAINarrator]
    O[OllamaLLM / FakeLLM]
  end
  WEB --> API --> J & A
  J --> P
  A --> P
  J --> C & S & R
  A --> G
  CR --> G
  P -.implementan.- D & M & L & T & CR & O
```

---

## 5. Arquitectura agéntica

### 5.1 Agentes, objetivos, herramientas, permisos, memoria y handoffs

Fuente única: `src/pyme_guard/domain/agents.py` (también visible en la pestaña **4 · Agentes y permisos** y en `GET /v1/agents`).

| Agente | Objetivo | Herramientas / permisos | Informa | Recomienda | Ejecuta | Nunca | Memoria | Handoff |
|---|---|---|---|---|---|---|---|---|
| Orquestador | Llevar el caso por la máquina de estados | estado, cola, auditoría (escritura) | Estado | — | Transiciones permitidas, encolar | Aprobar, rechazar en definitiva, desembolsar | Estado del caso | Todas las personas |
| Onboarding y consentimiento | Explicar, capturar autorizaciones, verificar empresa | consentimientos (escritura), RUES (lectura) | Requisitos, uso de datos | — | Registrar consentimiento otorgado | Consultar sin autorización | Versión de autorización | Asesor pyme |
| Cumplimiento (SARLAFT/KYB) | Screening antes de cualquier oferta | listas (lectura) | — | Retener | — | Revelar coincidencia al cliente | Ninguna fuera del caso | Oficial de cumplimiento |
| Facturas (RADIAN) | Traer y filtrar facturas negociables | RADIAN (lectura) | Qué califica y por qué | Facturas a incluir | — | Endosar | Snapshot con CUFE | Analista de fraude |
| Guardián de fraude | Detectar doble negociación | RADIAN (lectura), reglas | — | Retener | — | Acusar, bloquear | Señales del caso | Analista de fraude |
| Riesgo | Scorecard explicable y oferta en política | centrales, política (lectura) | — | Banda, cupo, anticipo, tasa | — | Aprobar, superar techo | Resultado y versión de política | Analista / comité |
| Asesor (IA gen.) | Explicar costo y pasos en lenguaje claro | snapshot (lectura) | Costo total, pasos | Encaje con la necesidad | — | Prometer, fijar tasas, enlaces, PII | Sesión con PII enmascarada | Asesor pyme |
| Copiloto del analista (IA gen.) | Resumen verificable del caso | snapshot (lectura) | Resumen, alertas | Puntos a revisar | — | Decidir, ocultar alertas | Ninguna | Analista |

### 5.2 Qué decide la IA y qué decide una persona

| Decisión | IA | Persona |
|---|---|---|
| Explicar producto, requisitos y costos | ✅ informa | — |
| Filtrar facturas por política | ✅ recomienda (regla determinista) | Revisa en la cola |
| Banda de riesgo, cupo, tasa indicativa | ✅ recomienda (scorecard + política) | **Aprueba o ajusta** |
| Aprobar cupo / desembolso | ❌ | **Analista** (< umbral) o **comité** (≥ COP 800 M) |
| Coincidencia en listas | ❌ solo retiene | **Oficial de cumplimiento** |
| Doble negociación de factura | ❌ solo retiene | **Analista de fraude** |
| Liberar desembolso en el core | ❌ prepara la orden | **Operaciones con doble firma** |
| Cambiar la política o el scorecard | ❌ | **Comité de riesgo / gobierno de modelos** |

Autonomía futura (🔜, gate del mes 5 del roadmap): aprobación automática de operaciones pequeñas (p. ej. < COP 30 M, banda A, pagador AAA) **solo** si los evals y el piloto muestran pérdida y error dentro de umbral. El parámetro ya existe: `CreditPolicy.auto_approval_limit_cop` (hoy en 0).

### 5.3 Secuencia del journey (camino feliz + handoff)

```mermaid
sequenceDiagram
  autonumber
  actor P as Empresario pyme
  participant W as Web
  participant O as Orquestador
  participant ON as Onboarding
  participant CU as Cumplimiento
  participant FA as Facturas
  participant FR as Fraude
  participant RI as Riesgo
  participant AS as Asesor (IA)
  participant CP as Copiloto (IA)
  actor AN as Analista

  P->>W: NIT + 3 autorizaciones
  W->>O: POST /v1/applications
  O->>ON: ¿consentimiento completo?
  alt falta autorización
    ON-->>P: Explica qué falta · no se consulta ningún sistema
  end
  ON->>ON: RUES: matrícula vigente
  O->>CU: Screening listas
  alt coincidencia
    CU-->>AN: Oficial de cumplimiento (mensaje neutral al cliente)
  end
  O->>FA: RADIAN: facturas
  FA->>FR: ¿alguna ya endosada?
  alt doble negociación
    FR-->>AN: Analista de fraude
  end
  O->>RI: Central de riesgo + scorecard
  alt central caída
    RI-->>AN: Revisión manual (no se inventa oferta)
  end
  RI-->>O: Oferta indicativa (política versionada)
  O->>AS: Explicar oferta (snapshot)
  AS-->>P: Costo total y siguientes pasos
  P->>W: Acepta oferta
  O->>CP: Resumen para el analista
  O-->>AN: Cola humana (SLA 24 h)
  AN->>O: Aprueba con justificación
  O->>O: Orden de desembolso + endoso RADIAN (doble firma en core)
```

### 5.4 Máquina de estados

```mermaid
stateDiagram-v2
  [*] --> consentimiento_requerido: falta autorización
  [*] --> no_elegible: sin matrícula / sin facturas / scorecard
  [*] --> revision_cumplimiento: coincidencia en listas
  [*] --> revision_fraude: factura ya endosada
  [*] --> revision_manual: sistema caído
  [*] --> oferta_indicativa: política OK
  oferta_indicativa --> pendiente_aprobacion_humana: cliente acepta
  pendiente_aprobacion_humana --> aprobada_por_humano: analista/comité
  pendiente_aprobacion_humana --> rechazada_por_humano: analista/comité
  revision_manual --> aprobada_por_humano
  revision_manual --> rechazada_por_humano
  revision_cumplimiento --> revision_manual: oficial libera
  revision_cumplimiento --> rechazada_por_humano
  revision_fraude --> revision_manual: analista libera
  revision_fraude --> rechazada_por_humano
  aprobada_por_humano --> [*]
  rechazada_por_humano --> [*]
```

Las flechas que llegan a `aprobada_por_humano` o `rechazada_por_humano` **solo** las puede disparar `human_decision()`; `set_pipeline_outcome()` las rechaza (probado en `tests/test_credit_journey.py`).

### 5.5 CrewAI: generador + crítico con degradación segura

```mermaid
flowchart TB
  S[Snapshot minimizado del caso<br/>NIT enmascarado · sin detalle SARLAFT] --> T1[Tool: consultar_oferta_indicativa]
  S --> T2[Tool: consultar_razones_scorecard]
  S --> T3[Tool: consultar_alertas]
  T1 & T2 & T3 --> W[Agente redactor<br/>Asesor o Copiloto]
  W --> R[Agente revisor de cumplimiento<br/>elimina promesas, enlaces, datos no soportados]
  R --> G{OutputGuard<br/>canary · promesas · URLs · PII}
  G -- pasa --> OK[Texto CrewAI]
  G -- bloquea --> F[Plantilla determinista + nota en la traza]
  X[CrewAI no instalado / LLM caído] --> F
```

- Activación: `PYME_NARRATOR=crewai`, `pip install -r requirements-crewai.txt` (o imagen con `INSTALL_CREWAI=true`) y un modelo (`PYME_CREWAI_MODEL=ollama/llama3.2` u otro proveedor LiteLLM).
- Probado con un módulo CrewAI falso (`tests/test_crewai_narrator.py`): cableado, herramientas de solo lectura, bloqueo de promesas y enlaces, y degradación.
- **Por qué CrewAI aquí y no en las decisiones:** las decisiones de crédito deben ser reproducibles y auditables; la generación de lenguaje es donde la IA aporta (claridad para el cliente, ahorro de tiempo del analista) con un riesgo acotado por el crítico y el guardrail.

### 5.6 Evolución agéntica (🔜)

| Patrón | Uso propuesto | Fase |
|---|---|---|
| **CrewAI Flows** con estado persistente y *human feedback* | Reemplazar el orquestador nativo cuando haya más productos (crédito de capital de trabajo, confirming) | Fase 3 |
| **MCP (Model Context Protocol)** | Exponer RADIAN, política y snapshot como servidores MCP con permisos por herramienta | Fase 2 |
| **A2A** | Interoperar con agentes de entidades aliadas (referidos) y de pagadores ancla (confirming) | Fase 3 |
| **LLM gateway** (LiteLLM) | Presupuesto por caso, ruteo modelo pequeño/grande, enmascarado central de PII | Fase 2 |
| **Clasificador de prompt injection** | Segunda capa tras los patrones (los evals declaran 2 ataques semánticos no bloqueados) | Fase 2 |
| **Observabilidad LLM** (OpenTelemetry + Langfuse) | Costo y calidad por caso, alertas de deriva | Fase 2 |

---

## 6. Controles

| Riesgo | Control | Dónde | Estado |
|---|---|---|---|
| **Privacidad / consentimiento** | Tres autorizaciones explícitas versionadas; sin ellas no hay consultas | `credit_journey.py`, `Consent` | ✅ |
| | NIT enmascarado en snapshot, API y auditoría; PII enmascarada antes del LLM | `narration.py`, `guardrails.py` | ✅ |
| | Retención, cifrado en reposo, derecho de revocación por API | PostgreSQL + KMS | 🔜 |
| **Explicabilidad** | Scorecard por reglas: cada punto y cada exclusión tiene una razón legible | `assess_risk`, `screen_invoices` | ✅ |
| | Oferta con costo total (descuento, comisión, E.A., neto) | `build_offer` | ✅ |
| **Fraude** | Detección de facturas ya endosadas en RADIAN → analista de fraude | `screen_invoices`, `fraude` | ✅ 🟡 |
| | Velocidad, concentración por pagador, verificación de cuenta destino | reglas + modelo | 🔜 |
| **Mensajes adversariales** | NFKC, invisibles, patrones ES/EN, payloads codificados, delimitadores, canary | `guardrails.py` | ✅ |
| | Crítico CrewAI + OutputGuard sobre todo texto generado | `crewai_narrator.py` | ✅ |
| **SARLAFT** | Screening antes de cualquier oferta; sin *tipping-off* | `cumplimiento` | ✅ 🟡 |
| **Calidad** | Evals offline como compuerta de CI (guardrails, journey, invariantes) | `evals/` | ✅ |
| | Muestreo humano de narrativas, *LLM-as-judge* con rúbrica, deriva | Langfuse | 🔜 |
| **Trazabilidad** | Traza por paso: agente, acción, sistemas, resultado, handoff; auditoría JSON sin PII | `journey.py`, `logging_audit.py` | ✅ |
| | Versión de política en cada oferta; justificación obligatoria en decisiones humanas | `Offer.policy_version`, `HumanDecision` | ✅ |
| **Disponibilidad** | Degradación a persona si una fuente cae; narrador degrada a plantilla | `_degrade`, `CrewAINarrator` | ✅ |
| **Seguridad de aplicación** | Claves en tiempo constante, esquemas estrictos, CSP, `textContent`, contenedor sin root y solo lectura | `api.py`, `Dockerfile`, compose | ✅ |
| | OIDC/SSO + RBAC por rol (analista ≠ oficial), WAF, rate limiting | Gateway | 🔜 |

---

## 7. Integración con sistemas y datos

| Sistema | Dato | Puerto | Adaptador hoy | Integración objetivo |
|---|---|---|---|---|
| RUES | Matrícula, antigüedad, actividad (CIIU) | `CompanyRegistryPort` | 🟡 `DemoDataset` | API RUES / proveedor de datos empresariales |
| RADIAN (DIAN) | Facturas, aceptación, endosos | `InvoiceRegistryPort` | 🟡 | Proveedor tecnológico o sistema de negociación electrónica habilitado |
| Centrales de riesgo | Puntaje, moras, endeudamiento | `CreditBureauPort` | 🟡 | API de la central, con autorización Ley 1266 |
| KYB / listas | ONU, OFAC, PEP, beneficiario final | `SanctionsPort` | 🟡 | Proveedor KYB del banco |
| Finanzas abiertas | Extractos y flujo de caja (con consentimiento) | 🔜 nuevo puerto | — | Estándares del Decreto 368 de 2026 cuando estén publicados |
| Core bancario | Desembolso, recaudo, contabilidad | 🔜 `DisbursementPort` | — | Orden con doble firma; eventos al bus |
| Modelos de IA | Narrativas | `NarratorPort`, `LLMPort` | ✅ Ollama / CrewAI / plantillas | Gateway de modelos con presupuesto |

---

## 8. Despliegue en contenedores

```mermaid
flowchart LR
  subgraph F1[Hoy · Docker Compose]
    A1[app · FastAPI<br/>no root · read-only · cap_drop ALL] --- O1[(ollama · perfil llm)]
  end
  subgraph F2[Piloto · Kubernetes gestionado]
    I2[Ingress + WAF] --> A2[Deployment app x1<br/>NetworkPolicy · PSS restricted]
    A2 --> O2[Ollama / gateway de modelos]
    A2 --> S2[(Secrets: External Secrets)]
  end
  subgraph F3[Escala · K8s multi-servicio]
    G3[API Gateway OIDC] --> API3[API + orquestador · HPA 2-8]
    API3 --> AG3[Servicio de agentes · HPA]
    API3 --> PG3[(PostgreSQL HA)]
    API3 --> BUS3[[Bus de eventos]]
    AG3 --> LLM3[LLM gateway]
    AG3 --> OBS3[OTel + Langfuse]
  end
  F1 ==> F2 ==> F3
```

- `Dockerfile` multi-etapa, usuario 10001, `HEALTHCHECK`, `INSTALL_CREWAI` como *build arg*.
- `docker-compose.yml`: app en modo demo por defecto; `--profile llm` agrega Ollama sin exponer puertos.
- `deploy/k8s/`: base Kustomize (Namespace con Pod Security *restricted*, ConfigMap, Deployment endurecido, Service, NetworkPolicy). `hpa.yaml` queda fuera hasta tener PostgreSQL (el repositorio actual es en memoria: escalar réplicas hoy rompería el estado).
- CI (`.github/workflows/ci.yml`): ruff, mypy, pytest, **evals como compuerta**, pip-audit, build y escaneo Trivy.

El plan detallado por fases está en [ROADMAP.md](ROADMAP.md#3-roadmap-técnico-de-despliegue-en-contenedores).

---

## 9. Decisiones de arquitectura (ADR resumidos)

| # | Decisión | Alternativa descartada | Razón |
|---|---|---|---|
| 1 | Producto inicial: anticipo de facturas RADIAN | Crédito de libre inversión | Autoliquidable, datos verificables, riesgo en el pagador, ciclo corto para aprender |
| 2 | Decisiones por reglas versionadas; IA generativa solo para lenguaje | LLM que decide | Auditabilidad, explicabilidad y control del regulador |
| 3 | Orquestador nativo + CrewAI como adaptador opcional | Todo en CrewAI desde el día 1 | Reproducibilidad del flujo crítico; CrewAI aporta donde hay lenguaje |
| 4 | Monolito modular hexagonal | Microservicios desde el inicio | Equipo pequeño y piloto; los puertos permiten separar después |
| 5 | Ollama local por defecto | Solo API externa | Datos no salen del perímetro en el piloto; el gateway permite cambiar |
| 6 | Mensaje neutral en SARLAFT/fraude | Explicar el motivo | Evitar *tipping-off*; el detalle solo lo ve el oficial |

---

## 10. Limitaciones conocidas (declaradas)

- Datos y empresas **ficticios**; integraciones simuladas.
- Repositorio en memoria (se pierde al reiniciar; impide escalar réplicas).
- Claves estáticas de demo en lugar de SSO/RBAC.
- Los guardrails por patrones no cubren ataques semánticos (los evals reportan 2 de 30 no bloqueados; la arquitectura los contiene porque el LLM no puede decidir).
- El adaptador CrewAI se valida con un módulo falso; falta una prueba de integración con un modelo real en CI (requiere GPU/API).
