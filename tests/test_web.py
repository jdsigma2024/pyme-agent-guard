import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from pyme_guard.adapters.inbound.api import Brand, create_app
from pyme_guard.adapters.outbound.fake_llm import FakeLLM
from pyme_guard.application.assistant_service import AssistantService
from pyme_guard.config import Settings


class NullAudit:
    def record(self, event):
        pass


@pytest.fixture
def client(tmp_path):
    (tmp_path / "logo.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    (tmp_path / "brand.css").write_text(":root{--brand-primary:#15601d}")
    service = AssistantService(FakeLLM(), NullAudit())
    brand = Brand(name="Acme", tagline="Demo", provider="Ollama · x", auth_required=True)
    return TestClient(create_app(service, "k", brand, tmp_path))


def test_home_page_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_static_assets_are_served(client):
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200


def test_brand_folder_is_served_and_editable_without_code(client):
    assert client.get("/brand/logo.svg").status_code == 200
    assert "--brand-primary" in client.get("/brand/brand.css").text


def test_brand_endpoint_is_public_and_exposes_no_secret(client):
    data = client.get("/v1/brand").json()
    assert data["name"] == "Acme" and data["auth_required"] is True
    assert "k" not in data.values()


def test_security_headers(client):
    headers = client.get("/").headers
    assert "default-src 'self'" in headers["content-security-policy"]
    assert headers["x-content-type-options"] == "nosniff"


def test_frontend_never_uses_innerhtml(client):
    assert "innerHTML" not in client.get("/static/app.js").text


def test_default_settings_use_ollama(monkeypatch):
    monkeypatch.delenv("PYME_LLM_PROVIDER", raising=False)
    assert Settings(_env_file=None).llm_provider == "ollama"
