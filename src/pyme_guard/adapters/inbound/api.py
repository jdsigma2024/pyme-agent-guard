"""Adaptador de entrada HTTP (FastAPI). Traduce HTTP <-> casos de uso y sirve la pantalla web."""

from __future__ import annotations

import hmac
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from pyme_guard.adapters.inbound.journey_api import build_journey_router
from pyme_guard.application.assistant_service import AssistantService
from pyme_guard.application.credit_journey import CreditJourneyService
from pyme_guard.domain.guardrails import DEFAULT_MAX_CHARS

WEB_DIR = Path(__file__).parent / "web"

_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=DEFAULT_MAX_CHARS)


class ChatResponse(BaseModel):
    status: str
    answer: str
    reasons: list[str]


class Brand(BaseModel):
    name: str = "Periferia IT Group"
    tagline: str = "Liquidez Factura · Banca Pyme"
    provider: str = ""
    auth_required: bool = False
    analyst_auth_required: bool = False


def create_app(
    service: AssistantService,
    api_key: str | None = None,
    brand: Brand | None = None,
    brand_dir: Path | None = None,
    journey: CreditJourneyService | None = None,
    analyst_key: str | None = None,
    demo_scenarios: tuple[dict[str, str], ...] = (),
) -> FastAPI:
    app = FastAPI(title="Pyme Agent Guard · Liquidez Factura", version="0.3.0")
    brand = brand or Brand(auth_required=api_key is not None, analyst_auth_required=analyst_key is not None)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        # /docs de Swagger carga scripts externos: se excluye de la CSP estricta.
        if not request.url.path.startswith(("/docs", "/redoc")):
            response.headers["Content-Security-Policy"] = _CSP
        return response

    def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
        if api_key is None:
            return
        if x_api_key is None or not hmac.compare_digest(x_api_key, api_key):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key inválida")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/brand", response_model=Brand)
    def get_brand() -> Brand:
        return brand

    @app.post("/v1/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
    def chat(body: ChatRequest) -> ChatResponse:
        result = service.handle(body.message)
        return ChatResponse(
            status=result.status.value, answer=result.answer, reasons=list(result.reasons)
        )

    if journey is not None:
        app.include_router(build_journey_router(journey, require_api_key, analyst_key, demo_scenarios))

    # --- Pantalla web ---------------------------------------------------- #
    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
    # La marca (logo + colores) vive fuera del código: se edita sin tocar Python.
    if brand_dir is not None and brand_dir.is_dir():
        app.mount("/brand", StaticFiles(directory=brand_dir), name="brand")

    return app
