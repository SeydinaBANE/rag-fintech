FROM python:3.11-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./

RUN uv sync --no-dev --frozen

COPY rag/ ./rag/
COPY dashboard/ ./dashboard/
COPY scripts/ ./scripts/
COPY init.sql ./

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8502

CMD ["streamlit", "run", "dashboard/app.py", \
     "--server.port", "8502", \
     "--server.address", "0.0.0.0"]
