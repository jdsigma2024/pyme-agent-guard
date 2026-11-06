# Matriz de cumplimiento contra el enunciado de la prueba

**Candidato:** Jose Sanchez · revisión punto por punto del documento *Prueba técnica · AI Product Engineer · Banca Pyme*.

## Desafío del caso

| Pide | Dónde se responde |
|---|---|
| Segmento | PROPUESTA_PRODUCTO §A.2 · PDF |
| Problema | PROPUESTA_PRODUCTO §A.2 · PDF |
| Producto | PROPUESTA_PRODUCTO §A.2 · `domain/credit.py` |
| Propuesta de valor | PROPUESTA_PRODUCTO §A.3 · PDF |
| Datos | ARQUITECTURA §7 · PROPUESTA_PRODUCTO §A.1 |
| Canales | PROPUESTA_PRODUCTO §A.4 (descubrimiento) · ROADMAP §4 |
| Modelo operativo | ARQUITECTURA §5.2 · ROADMAP §2 y §5 (D6) |
| Solución agéntica | ARQUITECTURA §5 · prototipo |
| Modelo económico | xlsx · PROPUESTA_PRODUCTO §C |
| Datos de mercado reales y supuestos declarados | xlsx hojas `Fuentes` y `Supuestos` · PROPUESTA_PRODUCTO §A.1 |

## Reto

| Bloque | Ítem | Evidencia |
|---|---|---|
| **A · Producto** | 1. Mercado y supuestos (tamaño, comportamiento, necesidades, economía, regulación, usuarios) | PROPUESTA_PRODUCTO §A.1 · xlsx `Supuestos` |
| | 2. Segmento, problema, producto inicial | §A.2 |
| | 3. Experiencia end-to-end (descubrimiento → acompañamiento) | §A.4 · prototipo pestañas 1-2 |
| | 4. Qué primero y qué después | ROADMAP §4 |
| **B · Agéntica** | 1. Agentes, objetivos, herramientas, permisos, memoria, handoffs | ARQUITECTURA §5.1 · `domain/agents.py` · pestaña 4 · `GET /v1/agents` |
| | 2. Informar / recomendar / ejecutar y decisiones humanas | ARQUITECTURA §5.2 · máquina de estados · tests de invariantes |
| | 3. Privacidad, consentimiento, explicabilidad, fraude, adversariales, calidad, trazabilidad | ARQUITECTURA §6 · tests · evals |
| | 4. Integración con sistemas y datos | ARQUITECTURA §7 · puertos en `application/ports.py` |
| **C · Negocio** | 1. Modelo a 3 años (mercado, funnel, ingresos, margen, inversión, opex, costos IA, riesgo) | xlsx `M_Base` (y escenarios) |
| | 2. Valor de eficiencia, conversión, experiencia, cross-sell | xlsx bloque *Memo: valor atribuible a la IA* + cross-sell · PROPUESTA §C |
| | 3. Escenarios pesimista/base/optimista, payback, sensibilidades | xlsx `Resumen`, `Sensibilidad` |
| | 4. Fuentes, supuestos y experimentos | xlsx `Fuentes`, `Supuestos`, `Validacion` |
| **D · Delivery** | 1. Roadmap 6 meses con pilotos, fases, dependencias, compuertas | ROADMAP §1 (Gantt + gates G1-G4) |
| | 2. Indicadores de producto, experiencia, adopción, calidad de agentes, costo, riesgo, cumplimiento | ROADMAP §2 |
| | 3. Rol de las personas en operación y gobierno | ARQUITECTURA §5.2 · `HUMAN_ROLES` · ROADMAP §5 (D5) |
| | 4. Restricciones y decisiones antes de escalar | ROADMAP §5 (D1-D6) · ARQUITECTURA §10 |

## Entregables

| Entregable | Requisito | Estado |
|---|---|---|
| **01 Prototipo** | Navegable (stack libre) | ✅ FastAPI + web, Docker |
| | Journey clave con intervención visible de la solución agéntica | ✅ Pestaña 1 con traza en vivo |
| | Al menos dos caminos de falla/excepción | ✅ Cinco: SARLAFT, fraude, sistema caído, no elegible, sin consentimiento (+ ataques en el chat) |
| | Visible qué hace el agente, qué datos/sistemas consulta y cuándo transfiere | ✅ Cada paso muestra agente, tipo de acción, sistemas y persona destino |
| **02 Resumen ejecutivo** | PDF máx. 2 páginas con problema, segmento, producto, propuesta de valor, priorización, solución agéntica, autonomía, límites, controles, valor, inversión, riesgos y decisión solicitada | ✅ `entregables/02_...pdf` |
| **03 Modelo financiero** | Supuestos separados, fórmulas visibles, fuentes, funnel, drivers, margen, costos, riesgo, inversión, costos IA, beneficio 3 años, payback, escenarios, supuestos críticos, sensibilidad, plan de validación | ✅ `entregables/03_...xlsx` (7.914 fórmulas, 0 errores) |
| **Uso de IA** | Declaración corta | ✅ `docs/USO_DE_IA.md` |

## Qué diferencia una propuesta excepcional

| Criterio | Cómo se atiende |
|---|---|
| No es un chatbot genérico | El chat es un componente; el núcleo es un journey con datos (RADIAN, centrales, KYB), política y operación humana |
| Segmento y problema específicos | Pymes facturadoras B2B con caja atrapada en cartera; un solo producto inicial |
| Uso crítico de datos de mercado | Se separan hechos y supuestos; cada supuesto crítico tiene experimento (E1-E7) |
| Diseño para fallos y humanos responsables | Máquina de estados, degradación a persona, mensajes neutrales, justificación obligatoria |
| Cuantifica sin presentar supuestos como certezas | Tres escenarios, sensibilidad, y reconocimiento explícito de que el ahorro de IA no se paga solo |
