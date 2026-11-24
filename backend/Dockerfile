FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.20 /uv /usr/local/bin/uv
WORKDIR /app/backend
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev
COPY backend/ ./
RUN uv sync --frozen --no-dev
# The dataset and config are mounted read-only / read-write by docker-compose (dataset files stay unchanged).
EXPOSE 8000
CMD ["uv", "run", "--no-dev", "uvicorn", "mira.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
