# Backend del sistema centralizado de robots y drones.
# Etapa "dev" (la que usa docker-compose.yml): incluye pytest, moto y ruff para correr las pruebas en el contenedor.
# Etapa "prod": solo dependencias de ejecución.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    TZ=America/Bogota

RUN pip install --no-cache-dir uv==0.12.21

WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 8000
# Migra la base y arranca Uvicorn con UN worker (el simulador, el monitor y el SSE viven en memoria).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:crear_app --factory --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers"]

FROM base AS dev
RUN uv sync --frozen --group dev

FROM base AS prod
