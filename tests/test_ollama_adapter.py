import pytest

httpx = pytest.importorskip("httpx")

from pyme_guard.adapters.outbound.ollama_llm import OllamaLLM
from pyme_guard.domain.errors import LLMUnavailableError


def adapter(handler):
    client = httpx.Client(base_url="http://ollama.test", transport=httpx.MockTransport(handler))
    return OllamaLLM("http://ollama.test", "llama3.2", client=client)


def test_returns_model_content():
    def handler(request):
        assert request.url.path == "/api/chat"
        return httpx.Response(200, json={"message": {"content": "hola"}})

    assert adapter(handler).generate("sys", "user") == "hola"


@pytest.mark.parametrize(
    "response",
    [httpx.Response(500), httpx.Response(200, text="no es json"), httpx.Response(200, json={"x": 1})],
)
def test_failures_become_domain_error(response):
    with pytest.raises(LLMUnavailableError):
        adapter(lambda request: response).generate("sys", "user")
