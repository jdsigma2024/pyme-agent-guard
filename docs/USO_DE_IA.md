# Declaración de uso de IA

**Autor:** Jose Sanchez · noviembre de 2026

| Herramienta | Uso | Qué decidí yo |
|---|---|---|
| Claude (Anthropic), asistente de IA | Búsqueda y síntesis de fuentes de mercado; borradores de código (dominio, orquestador, adaptador CrewAI, UI), tests, evals, diagramas Mermaid C4, documentación, modelo financiero y resumen ejecutivo | Segmento, producto, principio "el LLM propone, la política dispone", límites de autonomía, supuestos y escenarios, estructura de la arquitectura y del roadmap |
| CrewAI (en el producto) | Equipo generador + crítico para narrativas al cliente y resúmenes al analista | Qué puede y qué no puede hacer cada agente |
| Ollama / modelos LLM (en el producto) | Asistente conversacional y backend opcional de CrewAI | Datos que ve el modelo (snapshot minimizado) |

**Cómo se verificó:** 86 tests automáticos en verde en el entorno de desarrollo (las pruebas de API se ejecutan en CI/Docker, donde FastAPI está instalado); evals offline con umbrales; recálculo del modelo financiero sin errores de fórmula; cada cifra de mercado tiene fuente con URL en la hoja `Fuentes`. Los supuestos propios están marcados como tales y tienen un experimento de validación.

**Límites:** los datos del prototipo son ficticios; los precios de modelos de IA provienen de una fuente secundaria y deben confirmarse con el proveedor.
