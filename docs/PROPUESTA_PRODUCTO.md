# Propuesta de producto y caso de negocio · Liquidez Factura

**Autor:** Jose Sanchez · noviembre de 2026 · caso ficticio con referencias de mercado reales (consultadas el 5-nov-2026).

Complementa el [resumen ejecutivo (PDF)](../entregables/02_Resumen_Ejecutivo_Liquidez_Factura_Jose_Sanchez.pdf) y el [modelo financiero (xlsx)](../entregables/03_Modelo_Financiero_Liquidez_Factura_Jose_Sanchez.xlsx).

---

## A. Producto y experiencia

### A.1 Mercado: hechos y supuestos

| Tipo | Dato | Fuente |
|---|---|---|
| Hecho | La demanda potencial de crédito mipyme es de COP 122,49 billones (13,8% del PIB) y el exceso de demanda sobre la oferta promedia 7,6% del PIB (2018-2022) | BID / Banca de las Oportunidades, 2026 |
| Hecho | La proporción de pymes que solicita crédito cayó de 54,3% (2005) a 33,2% (2021); la principal barrera declarada es la autoexclusión | Mismo estudio |
| Hecho | Pymes registradas: ≈ 89.000 pequeñas y ≈ 23.000 medianas por año (promedio 2013-2022) | Mismo estudio, tabla 1 |
| Hecho | Facturas endosadas en RADIAN: de COP 11,23 billones (2022) a COP 46,7 billones (2025); COP 37,1 billones solo entre enero y julio de 2026 | DIAN vía Portafolio |
| Hecho | Bancóldex ya opera productos de primer piso (crédito, leasing, factoring) por COP 1,3 billones en 2025, además de COP 4,8 billones totales | Informe de Junta 2025 |
| Hecho | Finanzas abiertas obligatorias para vigilados (Decreto 368 de 2026), implementación gradual | SFC |
| Hecho | Usura noviembre 2026: 28,34% E.A.; factoring en el mercado entre 1,19% y 3,5% mensual | SFC; Alegra |
| Supuesto | 35% de las pymes registradas factura B2B a pagadores calificados (mercado objetivo ≈ 39.000) | Validar con E1 |
| Supuesto | Saldo medio de COP 150 M por cliente activo; pérdida esperada 2,5% anual | Validar con E3 y E5 |

Lectura crítica: la brecha es grande pero gran parte es **autoexclusión** y **asimetría de información**. Un producto que usa un dato verificable (la factura aceptada) y responde en minutos ataca ambas causas; un crédito genérico no.

### A.2 Segmento, problema y producto

- **Segmento de entrada:** pequeñas y medianas empresas formales (personas jurídicas), con ≥ 2 años, facturadoras electrónicas que venden a crédito (30-120 días) a pagadores medianos o grandes. Sectores con cadena clara: manufactura liviana, agroinsumos, logística, servicios B2B.
- **Problema prioritario:** caja atrapada en cuentas por cobrar. El empresario necesita liquidez para nómina, prima e insumos y hoy compara opciones opacas con respuestas lentas.
- **Producto inicial:** *Liquidez Factura*: anticipo (descuento) de facturas aceptadas en RADIAN, con recurso, cupo rotativo indicativo, anticipo 80-90% según banda, costo total transparente y decisión humana en < 24 h.
- **Por qué este producto para un banco de segundo piso:** autoliquidable, de plazo corto, riesgo apoyado en el pagador, dato verificable y mercado en crecimiento. Genera la relación directa (datos de comportamiento) que hoy el banco no tiene, sin competir con los aliados en crédito tradicional; los no elegibles se refieren a aliados.

### A.3 Propuesta de valor

| Para la pyme | Para el banco |
|---|---|
| Oferta indicativa en minutos con costo total claro | Relación directa y datos propios de comportamiento |
| Sin papeles: RUES, RADIAN y centrales con su autorización | Riesgo de corto plazo, diversificado por pagador |
| Explicación de por qué sí o por qué no, y alternativas | Operación eficiente: la IA prepara, la persona decide |
| No aumenta su deuda bancaria (venta de un activo) | Plataforma reutilizable para crédito de capital de trabajo y confirming |

### A.4 Experiencia end-to-end

| Etapa | Qué vive la pyme | Qué hace la IA | Persona |
|---|---|---|---|
| Descubrimiento | Llega por su software de facturación, cámara de comercio o referido de un aliado | Asesor responde dudas con guardrails | Asesor pyme si lo pide |
| Onboarding | NIT + 3 autorizaciones explícitas | Valida NIT, registra consentimiento, verifica RUES | — |
| Evaluación | Espera < 5 min | Screening SARLAFT, facturas RADIAN, fraude, scorecard | Oficial / fraude si hay alerta |
| Oferta | Ve anticipo, costo, neto y por qué | Riesgo recomienda; asesor explica | — |
| Contratación | Acepta y firma electrónicamente | Copiloto prepara resumen | **Analista o comité decide** |
| Desembolso | Recibe el dinero tras el endoso | Orquestador prepara orden y endoso | **Operaciones con doble firma** |
| Acompañamiento | Alertas de vencimiento, nuevas facturas elegibles | Asesor proactivo (fase 2) | Asesor pyme |

El prototipo implementa el journey de descubrimiento a decisión humana, con **cinco caminos**: feliz, coincidencia SARLAFT, doble negociación de factura, central de riesgo caída y no elegible explicado (más el de autorizaciones incompletas).

### A.5 Qué construir primero y qué después
Ver [ROADMAP.md §4](ROADMAP.md#4-qué-se-construye-primero-y-qué-se-deja-para-después).

---

## C. Caso de negocio (resumen del modelo)

Modelo trimestral a 3 años, con supuestos separados de cálculos, tres escenarios, sensibilidad y plan de validación. Cifras en COP millones.

| Indicador | Pesimista | Base | Optimista |
|---|---|---|---|
| Inversión inicial | 4.500 | 3.500 | 3.000 |
| Ingresos año 3 | 5.719 | 34.659 | 106.220 |
| Contribución año 3 | (5.255) | 8.426 | 49.553 |
| Beneficio acumulado 3 años (tras inversión) | (20.055) | 3.934 | 70.000 |
| VPN 3 años @ 15% | (16.920) | 1.124 | 49.801 |
| Payback | > 36 meses | 33 meses | 15 meses |
| Clientes activos al cierre del año 3 | 313 | 1.236 | 3.069 |
| Volumen año 3 / endosos RADIAN 2025 | 0,4% | 2,2% | 6,3% |

**Drivers que más mueven el VPN (base ±20%):** tasa de descuento (rango ≈ COP 16.355 M), costo de fondeo (≈ 6.854 M), saldo por cliente (≈ 6.361 M) y conversión (≈ 6.197 M). La pérdida esperada y el costo por lead pesan menos.

**Valor de la IA, dicho con honestidad:** a esta escala el ahorro en analistas (≈ COP 303 M en 3 años) **no** paga por sí solo el costo de la plataforma de IA (≈ COP 1.090 M, dominado por costos fijos de observabilidad y gateway; los tokens son marginales). El valor está en **conversión y experiencia** (respuesta en minutos, explicación clara, +5 pp de conversión atribuidos al agente, a validar con A/B) y en **control** (trazabilidad y menos error humano). Si el A/B no muestra la mejora, la recomendación es reducir la plataforma a narrativas de plantilla.

**Riesgos principales:** spread insuficiente si sube el fondeo; menor ticket del esperado; fricción en RADIAN (aceptación de facturas por el pagador); conflicto de canal con aliados; riesgo de modelo y reputacional de la IA (mitigado: la IA no decide).
