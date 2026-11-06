"use strict";

// Toda la UI se construye con createElement/textContent: nunca se interpreta HTML (evita XSS).
const $ = (id) => document.getElementById(id);

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

const COP = new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 });
const PCT = (v, d = 1) => (v * 100).toFixed(d).replace(".", ",") + " %";

const STATUS = {
  consentimiento_requerido: ["Faltan autorizaciones", "warn"],
  no_elegible: ["Sin oferta por ahora (con explicación)", "bad"],
  revision_cumplimiento: ["En validación adicional", "warn"],
  revision_fraude: ["En validación adicional", "warn"],
  revision_manual: ["Revisión manual por un analista", "warn"],
  oferta_indicativa: ["Oferta indicativa lista", "good"],
  pendiente_aprobacion_humana: ["Pendiente de decisión humana", "warn"],
  aprobada_por_humano: ["Aprobada por una persona · desembolso en curso", "good"],
  rechazada_por_humano: ["No aprobada tras revisión humana", "bad"],
};

// ------------------------------------------------------------------ HTTP
function clientHeaders() {
  const h = { "Content-Type": "application/json" };
  const key = $("apikey").value.trim();
  if (key) h["X-API-Key"] = key;
  return h;
}

function analystHeaders() {
  const h = { "Content-Type": "application/json" };
  const key = $("analystkey").value.trim();
  if (key) h["X-Analyst-Key"] = key;
  return h;
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (response.status === 401) throw new Error("Clave de acceso inválida.");
  if (!response.ok) {
    let detail = "";
    try { detail = (await response.json()).detail; } catch (_) { /* sin cuerpo */ }
    throw new Error(typeof detail === "string" && detail ? detail : "Error " + response.status);
  }
  return response.json();
}

// ------------------------------------------------------------------ Tabs
document.querySelectorAll(".tab").forEach((tab) =>
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => {
      const on = t === tab;
      t.classList.toggle("active", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
      $("tab-" + t.dataset.tab).hidden = !on;
    });
    if (tab.dataset.tab === "analyst") loadQueue();
  })
);

// ------------------------------------------------------------------ Traza
function renderTrace(container, steps) {
  container.replaceChildren();
  if (!steps.length) {
    container.appendChild(el("li", "empty", "Sin pasos."));
    return;
  }
  steps.forEach((s) => {
    const li = el("li", "step " + s.resultado);
    const head = el("div", "step-head");
    head.appendChild(el("span", "badge " + s.accion, s.accion.replace("_", " ")));
    head.appendChild(el("strong", "", s.agente_nombre));
    li.appendChild(head);
    li.appendChild(el("p", "step-text", s.resumen));
    if (s.sistemas.length) {
      const chips = el("div", "systems");
      s.sistemas.forEach((name) => chips.appendChild(el("span", "sys", name)));
      li.appendChild(chips);
    }
    if (s.transfiere_a) li.appendChild(el("p", "to-human", "→ Persona responsable: " + s.transfiere_a));
    container.appendChild(li);
  });
}

function fillList(list, items) {
  list.replaceChildren(...items.map((t) => el("li", "", t)));
}

// ------------------------------------------------------------------ Journey
let scenarios = [];
let currentId = null;

async function loadScenarios() {
  try {
    scenarios = await api("/v1/demo/scenarios");
  } catch (_) {
    scenarios = [];
  }
  const select = $("scenario");
  select.replaceChildren(...scenarios.map((s, i) => {
    const opt = el("option", "", s.empresa + " · " + s.camino.replaceAll("_", " "));
    opt.value = String(i);
    return opt;
  }));
  pickScenario();
}

function pickScenario() {
  const s = scenarios[Number($("scenario").value)];
  if (!s) return;
  $("nit").value = s.nit;
  $("scenario-desc").textContent = s.descripcion;
}

function renderApplication(app) {
  currentId = app.id;
  $("result").hidden = false;
  const [label, tone] = STATUS[app.estado] || [app.estado, "warn"];
  const status = $("status");
  status.className = "status " + tone;
  status.textContent = (app.empresa ? app.empresa + " · " : "") + label;
  $("client-msg").textContent = app.mensaje_cliente;

  const offer = $("offer");
  offer.replaceChildren();
  offer.hidden = !app.oferta;
  if (app.oferta) {
    const o = app.oferta;
    const rows = [
      ["Facturas incluidas", o.facturas + " por " + COP.format(o.valor_facturas)],
      ["Anticipo", COP.format(o.anticipo) + " (" + PCT(o.porcentaje_anticipo, 0) + ")"],
      ["Tasa", PCT(o.tasa_mensual, 2) + " mensual · " + PCT(o.tasa_efectiva_anual) + " E.A."],
      ["Descuento + comisión", COP.format(o.descuento) + " + " + COP.format(o.comision)],
      ["Neto a recibir", COP.format(o.neto)],
      ["Cupo rotativo indicativo", COP.format(o.cupo_rotativo)],
      ["Decide", o.aprobador + " · política " + o.politica],
    ];
    rows.forEach(([k, v]) => {
      offer.appendChild(el("dt", "", k));
      offer.appendChild(el("dd", "", v));
    });
  }

  $("explain-box").hidden = !app.explicaciones.length;
  fillList($("explanations"), app.explicaciones);
  $("excluded-box").hidden = !app.facturas_excluidas.length;
  fillList($("excluded"), app.facturas_excluidas.map((e) => e.pagador + " — " + e.motivo.replaceAll("_", " ")));

  const handoff = $("handoff");
  handoff.hidden = !app.handoff;
  if (app.handoff) {
    handoff.textContent = "Caso transferido a: " + app.handoff.rol + " · respuesta objetivo " + app.handoff.sla_horas + " h";
  }
  $("accept-btn").hidden = app.estado !== "oferta_indicativa";
  renderTrace($("trace"), app.traza);
}

async function submitApplication(event) {
  event.preventDefault();
  $("apply-btn").disabled = true;
  try {
    const app = await api("/v1/applications", {
      method: "POST",
      headers: clientHeaders(),
      body: JSON.stringify({
        nit: $("nit").value.trim(),
        consent: {
          habeas_data: $("c-habeas").checked,
          credit_bureau: $("c-bureau").checked,
          invoice_registry: $("c-radian").checked,
        },
      }),
    });
    renderApplication(app);
  } catch (error) {
    $("result").hidden = false;
    $("status").className = "status bad";
    $("status").textContent = error.message;
    $("client-msg").textContent = "";
  } finally {
    $("apply-btn").disabled = false;
  }
}

async function acceptOffer() {
  if (!currentId) return;
  $("accept-btn").disabled = true;
  try {
    renderApplication(await api("/v1/applications/" + currentId + "/accept", { method: "POST", headers: clientHeaders() }));
  } catch (error) {
    $("client-msg").textContent = error.message;
  } finally {
    $("accept-btn").disabled = false;
  }
}

// ------------------------------------------------------------------ Analista
async function loadQueue() {
  const box = $("queue");
  try {
    const items = await api("/v1/analyst/queue", { headers: analystHeaders() });
    box.replaceChildren();
    if (!items.length) {
      box.appendChild(el("p", "empty", "Sin casos pendientes. Crea solicitudes en la pestaña 1."));
      return;
    }
    items.forEach((app) => box.appendChild(caseCard(app)));
  } catch (error) {
    box.replaceChildren(el("p", "status bad", error.message));
  }
}

function caseCard(app) {
  const card = el("article", "case");
  const [label] = STATUS[app.estado] || [app.estado];
  card.appendChild(el("h3", "", (app.empresa || "Empresa") + " · NIT " + app.nit));
  card.appendChild(el("p", "status warn", label + (app.handoff ? " → " + app.handoff.rol : "")));
  if (app.handoff && app.handoff.motivo) card.appendChild(el("p", "motive", "Motivo interno: " + app.handoff.motivo));
  if (app.resumen_analista) {
    card.appendChild(el("h4", "", "Resumen del copiloto (verificar antes de decidir)"));
    card.appendChild(el("pre", "brief", app.resumen_analista));
  }
  const details = el("details", "");
  details.appendChild(el("summary", "", "Traza completa del caso (incluye cumplimiento y fraude)"));
  const ol = el("ol", "trace");
  renderTrace(ol, app.traza);
  details.appendChild(ol);
  card.appendChild(details);

  const form = el("form", "decision");
  const reason = el("textarea", "");
  reason.rows = 2;
  reason.required = true;
  reason.minLength = 5;
  reason.placeholder = "Justificación obligatoria (queda en auditoría)";
  form.appendChild(reason);
  const row = el("div", "row");
  const approve = el("button", "primary", "Aprobar");
  approve.type = "button";
  const reject = el("button", "danger", "Rechazar");
  reject.type = "button";
  row.append(approve, reject);
  form.appendChild(row);
  const out = el("p", "hint");
  form.appendChild(out);
  const decide = async (ok) => {
    if (reason.value.trim().length < 5) {
      out.textContent = "Escribe una justificación (mínimo 5 caracteres).";
      return;
    }
    try {
      await api("/v1/analyst/applications/" + app.id + "/decision", {
        method: "POST",
        headers: analystHeaders(),
        body: JSON.stringify({ approve: ok, reason: reason.value.trim(), reviewer: "analista.demo" }),
      });
      loadQueue();
      if (app.id === currentId) {
        renderApplication(await api("/v1/applications/" + app.id, { headers: clientHeaders() }));
      }
    } catch (error) {
      out.textContent = error.message;
    }
  };
  approve.addEventListener("click", () => decide(true));
  reject.addEventListener("click", () => decide(false));
  card.appendChild(form);
  return card;
}

// ------------------------------------------------------------------ Agentes
async function loadAgents() {
  try {
    const data = await api("/v1/agents");
    $("agents").replaceChildren(...data.agentes.map((a) => {
      const card = el("article", "agent");
      card.appendChild(el("h4", "", a.nombre + (a.usa_llm ? " · IA generativa" : " · reglas")));
      card.appendChild(el("p", "", a.objetivo));
      const dl = el("dl", "mini");
      [
        ["Herramientas", a.herramientas.join(", ")],
        ["Permisos", a.permisos.join(", ")],
        ["Informa", a.informa.join(", ") || "—"],
        ["Recomienda", a.recomienda.join(", ") || "—"],
        ["Ejecuta", a.ejecuta.join(", ") || "—"],
        ["Nunca", a.nunca.join(", ")],
        ["Memoria", a.memoria],
        ["Transfiere a", a.transfiere_a.join(", ") || "—"],
      ].forEach(([k, v]) => { dl.appendChild(el("dt", "", k)); dl.appendChild(el("dd", "", v)); });
      card.appendChild(dl);
      return card;
    }));
    $("roles").replaceChildren(...data.personas.map((r) => {
      const card = el("article", "agent human");
      card.appendChild(el("h4", "", r.nombre));
      card.appendChild(el("p", "", r.decide + " · SLA " + r.sla_horas + " h"));
      return card;
    }));
  } catch (_) { /* la vista es informativa */ }
}

// ------------------------------------------------------------------ Chat (asistente con guardrails)
const LABELS = { answered: "Respondido", blocked: "Bloqueado por la defensa", handoff: "Escalado a una persona" };

function addMessage(text, cls) {
  const div = el("div", "msg " + cls, text);
  $("log").appendChild(div);
  $("log").scrollTop = $("log").scrollHeight;
  return div;
}

function showVerdict(status, reasons) {
  const verdict = $("verdict");
  verdict.className = "verdict " + status;
  verdict.textContent = LABELS[status] || status;
  fillList($("reasons"), reasons);
}

async function send(message) {
  addMessage(message, "user");
  const pending = addMessage("Analizando…", "bot pending");
  $("send").disabled = true;
  try {
    const data = await api("/v1/chat", { method: "POST", headers: clientHeaders(), body: JSON.stringify({ message }) });
    pending.className = "msg bot " + data.status;
    pending.textContent = data.answer;
    showVerdict(data.status, data.reasons);
  } catch (error) {
    pending.className = "msg bot blocked";
    pending.textContent = error.message;
  } finally {
    $("send").disabled = false;
  }
}

$("form").addEventListener("submit", (event) => {
  event.preventDefault();
  const message = $("text").value.trim();
  if (!message) return;
  $("text").value = "";
  send(message);
});

document.querySelectorAll(".chip").forEach((chip) =>
  chip.addEventListener("click", () => {
    $("text").value = chip.dataset.text;
    $("text").focus();
  })
);

// ------------------------------------------------------------------ Marca e inicio
async function loadBrand() {
  try {
    const brand = await api("/v1/brand");
    document.title = brand.name + " · " + brand.tagline;
    $("logo").alt = brand.name;
    $("tagline").textContent = brand.tagline;
    $("provider").textContent = brand.provider;
    $("foot").textContent = brand.name + " · Prototipo de banca pyme agéntica · Datos ficticios - Por Jose Danilo Sanchez";
    $("auth").hidden = !brand.auth_required;
    $("analystkey").hidden = !brand.analyst_auth_required;
  } catch (_) {
    /* la pantalla funciona con los valores por defecto */
  }
}

$("scenario").addEventListener("change", pickScenario);
$("apply-form").addEventListener("submit", submitApplication);
$("accept-btn").addEventListener("click", acceptOffer);
$("refresh-btn").addEventListener("click", loadQueue);

loadBrand();
loadScenarios();
loadAgents();
