FROM python:3.11-slim AS builder

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./

RUN uv sync --no-dev --frozen

FROM python:3.11-slim

RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY rag/ ./rag/
COPY dashboard/ ./dashboard/
COPY scripts/ ./scripts/
COPY migrations/ ./migrations/
COPY init.sql alembic.ini ./

RUN chown -R appuser:appuser /app

ENV PATH="/app/.venv/bin:$PATH" \
    HOME="/app"

USER appuser

EXPOSE 8502

CMD ["streamlit", "run", "dashboard/app.py", \
     "--server.port", "8502", \
     "--server.address", "0.0.0.0"]
