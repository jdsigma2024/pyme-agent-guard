# syntax=docker/dockerfile:1.7
# Imagen multi-etapa: dependencias compiladas en "builder", runtime mínimo y sin root.
#   docker build -t pyme-agent-guard .
#   docker build --build-arg INSTALL_CREWAI=true -t pyme-agent-guard:crewai .

ARG PYTHON_VERSION=3.13

FROM python:${PYTHON_VERSION}-slim AS builder
ARG INSTALL_CREWAI=false
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements.txt requirements-crewai.txt ./
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install -r requirements.txt \
 && if [ "$INSTALL_CREWAI" = "true" ]; then /opt/venv/bin/pip install -r requirements-crewai.txt; fi

FROM python:${PYTHON_VERSION}-slim AS runtime
LABEL org.opencontainers.image.title="pyme-agent-guard" \
      org.opencontainers.image.description="Liquidez Factura · banca pyme agéntica" \
      org.opencontainers.image.authors="Jose Sanchez"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH"
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser
COPY --from=builder /opt/venv /opt/venv
COPY src ./src
COPY brand ./brand
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"
CMD ["uvicorn", "--app-dir", "src", "pyme_guard.main:create_default_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-server-header"]
