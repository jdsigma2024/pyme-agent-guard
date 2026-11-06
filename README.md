# Liquidez Factura · Pyme Agent Guard

**Prueba técnica AI Product Engineer · Banca Pyme agéntica** · Autor: **Jose Sanchez** · v0.3.0 · noviembre de 2026

Propuesta end-to-end para que un banco de segundo piso (ficticio) ofrezca directamente a pymes un producto de primer piso: **anticipo de facturas electrónicas registradas en RADIAN**, con una solución agéntica responsable. Los agentes consultan, explican y recomiendan; **aprobar y desembolsar siempre lo decide una persona**.

## Entregables

| # | Entregable | Dónde |
|---|---|---|
| 01 | Prototipo funcional (journey, agentes visibles, 5 caminos de falla/excepción, handoff humano) | Este repositorio · `docker compose up` |
| 02 | Resumen ejecutivo (PDF, 2 páginas) | [`entregables/02_Resumen_Ejecutivo_Liquidez_Factura_Jose_Sanchez.pdf`](entregables/02_Resumen_Ejecutivo_Liquidez_Factura_Jose_Sanchez.pdf) |
| 03 | Modelo financiero reproducible (xlsx) | [`entregables/03_Modelo_Financiero_Liquidez_Factura_Jose_Sanchez.xlsx`](entregables/03_Modelo_Financiero_Liquidez_Factura_Jose_Sanchez.xlsx) |
| — | Declaración de uso de IA | [`docs/USO_DE_IA.md`](docs/USO_DE_IA.md) |
| — | Arquitectura C4 (Mermaid) | [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) |
| — | Roadmap (piloto, KPIs, contenedores) | [`docs/ROADMAP.md`](docs/ROADMAP.md) |
| — | Propuesta de producto y caso de negocio | [`docs/PROPUESTA_PRODUCTO.md`](docs/PROPUESTA_PRODUCTO.md) |
| — | Matriz de cumplimiento contra el enunciado | [`docs/CHECKLIST_ENTREGABLES.md`](docs/CHECKLIST_ENTREGABLES.md) |

## Arranque rápido

```bash
# Docker (recomendado): app en modo demo, sin modelo
cp .env.example .env
docker compose up -d --build
# abrir http://localhost:8000  (claves por defecto en .env: cliente "cambia-esto", analista "cambia-esto-analista")

# Con modelo local (asistente + CrewAI)
docker compose --profile llm up -d --build
docker compose exec ollama ollama pull llama3.2
# y en .env: PYME_LLM_PROVIDER=ollama, PYME_NARRATOR=crewai; construir con INSTALL_CREWAI=true

# Local
pip install -r requirements-dev.txt          # + requirements-crewai.txt si se usa CrewAI
pytest -q && python evals/run_evals.py
uvicorn --app-dir src pyme_guard.main:create_default_app --factory
```

## Recorrido sugerido de la demo (5 minutos)

1. **Pestaña 1 · Solicitud pyme**: elegir *Confecciones Andinas* → oferta indicativa con costo total; a la derecha, la traza de cada agente (acción, sistemas consultados). Aceptar la oferta.
2. **Pestaña 2 · Consola del analista**: el caso llega con el resumen del copiloto. Aprobar con justificación → el orquestador prepara la orden con doble firma.
3. Repetir con las otras empresas: *Logística Sabana* (SARLAFT, mensaje neutral al cliente), *Agroinsumos del Llano* (factura ya endosada → fraude), *Metalmecánica Caribe* (central caída → revisión manual), *Servicios Digitales Nova* (no elegible, con razones). Desmarcar una autorización para ver que no se consulta nada.
4. **Pestaña 3 · Asistente**: probar prompt injection, PII y "aprueben mi crédito".
5. **Pestaña 4 · Agentes y permisos**: qué informa, recomienda o ejecuta cada agente y qué nunca decide.

## Arquitectura en una mirada

```mermaid
flowchart LR
  P[Pyme] --> W[Web] --> API[FastAPI]
  API --> O[Orquestador nativo<br/>máquina de estados]
  O --> ON[Onboarding] & CU[Cumplimiento] & FA[Facturas] & FR[Fraude] & RI[Riesgo]
  O --> N{NarratorPort}
  N --> TP[Plantillas]
  N --> CR[CrewAI: redactor + crítico<br/>+ OutputGuard]
  RI --> POL[(Política versionada<br/>scorecard explicable)]
  O --> Q[[Cola humana]] --> AN[Analista / comité / oficial]
```

```
src/pyme_guard/
  domain/        credit.py (política, scorecard, oferta) · journey.py (máquina de estados)
                 agents.py (registro de agentes) · guardrails.py · models.py · errors.py
  application/   credit_journey.py (orquestador) · narration.py (snapshot + plantillas)
                 assistant_service.py (chat) · ports.py
  adapters/
    inbound/     api.py · journey_api.py · web/ (UI sin innerHTML, CSP estricta)
    outbound/    crewai_narrator.py · demo_sources.py · memory_repository.py
                 ollama_llm.py · fake_llm.py · logging_audit.py
evals/           datasets + run_evals.py (compuerta de CI)
deploy/k8s/      base Kustomize endurecida
docs/            ARQUITECTURA (C4) · ROADMAP · PROPUESTA_PRODUCTO · USO_DE_IA · CHECKLIST
entregables/     PDF y xlsx
```

Detalle completo, decisiones y controles: [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

## API

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| POST | `/v1/applications` | X-API-Key | Inicia solicitud (NIT + consentimientos) |
| GET | `/v1/applications/{id}` | X-API-Key | Vista cliente (sin detalle de cumplimiento/fraude) |
| POST | `/v1/applications/{id}/accept` | X-API-Key | Acepta oferta indicativa → cola humana |
| GET | `/v1/analyst/queue` | X-Analyst-Key | Cola con resumen del copiloto y traza completa |
| POST | `/v1/analyst/applications/{id}/decision` | X-Analyst-Key | Decisión humana con justificación |
| GET | `/v1/agents` · `/v1/demo/scenarios` | pública | Registro de agentes · escenarios demo |
| POST | `/v1/chat` | X-API-Key | Asistente con defensa en profundidad |

## Calidad

- `pytest`: dominio, orquestador, invariantes de gobierno, registro de agentes, adaptador CrewAI (módulo falso), guardrails, API.
- `python evals/run_evals.py`: bloqueo de ataques 93,3% (2 ataques semánticos declarados), 0% falsos positivos, 100% captura en salida, 100% exactitud del journey e invariantes.
- CI: ruff, mypy, pytest, evals, pip-audit, build y Trivy (`.github/workflows/ci.yml`).

## Funcionalidades

A continuación, estas son las principales funcionalidades que cuenta la aplicación actual:

### Solicitud Pyme - Escenario Ok
![Mi imagen local](docs/imgs/escenarioSolicitudPymeOk.png)

### Solicitud Pyme - Escenario no Ok 
![Mi imagen local](docs/imgs/escenarioSolicitudPymeNoOk.png)

### Consola de Analista
![Mi imagen local](docs/imgs/escenarioConsolaAnalisis.png)

### Asistente con guardrails - Escenario Ok
![Mi imagen local](docs/imgs/escenarioaAsistentesGuardrailsOk.png)

### Asistente con guardrails - Escenario no Ok
![Mi imagen local](docs/imgs/escenarioaAsistentesGuardrailsNoOk.png)


## Cambiar logo y colores
`brand/logo.svg` y `brand/brand.css`; nombre y subtítulo con `PYME_BRAND_NAME` / `PYME_BRAND_TAGLINE`. Con Docker, `brand/` es un volumen: el cambio se ve al recargar.

## Limitaciones declaradas
Datos y empresas ficticios; integraciones simuladas; repositorio en memoria (1 réplica); claves de demo en lugar de SSO; guardrails por patrones no cubren ataques semánticos (contenidos porque la IA no decide). 
Ver detalle arquitectura [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).
