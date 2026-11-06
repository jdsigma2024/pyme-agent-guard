import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from pyme_guard.adapters.inbound.api import create_app  # noqa: E402
from pyme_guard.adapters.outbound.fake_llm import FakeLLM  # noqa: E402
from pyme_guard.application.assistant_service import AssistantService  # noqa: E402
from pyme_guard.main import demo_scenarios  # noqa: E402


class NullAudit:
    def record(self, event):
        pass


CLIENT = {"X-API-Key": "cli"}
ANALYST = {"X-Analyst-Key": "ana"}
CONSENT = {"habeas_data": True, "credit_bureau": True, "invoice_registry": True}


@pytest.fixture
def client(journey):
    app = create_app(
        AssistantService(FakeLLM(), NullAudit()), "cli", journey=journey, analyst_key="ana",
        demo_scenarios=demo_scenarios(),
    )
    return TestClient(app)


def apply(client, nit):
    return client.post("/v1/applications", json={"nit": nit, "consent": CONSENT}, headers=CLIENT)


def test_full_journey_over_http(client):
    created = apply(client, "900123456-8")
    assert created.status_code == 201
    body = created.json()
    assert body["estado"] == "oferta_indicativa" and body["oferta"]["indicativa"] is True
    assert body["nit"].endswith("456") and "900123456" not in body["nit"]

    accepted = client.post(f"/v1/applications/{body['id']}/accept", headers=CLIENT).json()
    assert accepted["estado"] == "pendiente_aprobacion_humana"

    queue = client.get("/v1/analyst/queue", headers=ANALYST).json()
    assert queue[0]["resumen_analista"]

    decided = client.post(
        f"/v1/analyst/applications/{body['id']}/decision",
        json={"approve": True, "reason": "Cumple política"}, headers=ANALYST,
    ).json()
    assert decided["estado"] == "aprobada_por_humano"


def test_client_view_hides_compliance_details(client):
    body = apply(client, "900555001").json()
    assert body["estado"] == "revision_cumplimiento"
    assert body["handoff"]["motivo"] is None
    assert all(step["agente"] != "cumplimiento" for step in body["traza"])
    analyst_view = client.get("/v1/analyst/queue", headers=ANALYST).json()[0]
    assert "listas" in analyst_view["handoff"]["motivo"]


def test_analyst_endpoints_require_analyst_key(client):
    assert client.get("/v1/analyst/queue").status_code == 401
    assert client.get("/v1/analyst/queue", headers=CLIENT).status_code == 401


def test_client_endpoints_require_client_key(client):
    assert client.post("/v1/applications", json={"nit": "900123456", "consent": CONSENT}).status_code == 401


def test_invalid_nit_and_extra_fields(client):
    assert apply(client, "900123456-1").status_code == 422
    bad = client.post("/v1/applications", json={"nit": "900123456", "consent": CONSENT, "role": "admin"}, headers=CLIENT)
    assert bad.status_code == 422


def test_conflicts_and_not_found(client):
    body = apply(client, "900999004").json()
    assert client.post(f"/v1/applications/{body['id']}/accept", headers=CLIENT).status_code == 409
    assert client.get("/v1/applications/nope", headers=CLIENT).status_code == 404


def test_agents_and_scenarios_are_public(client):
    agents = client.get("/v1/agents").json()
    assert {a["id"] for a in agents["agentes"]} >= {"orquestador", "riesgo", "asesor"}
    assert len(client.get("/v1/demo/scenarios").json()) == 5
