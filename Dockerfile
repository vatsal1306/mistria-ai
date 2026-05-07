# syntax=docker/dockerfile:1.7

FROM python:3.10-slim-bookworm AS python-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    HF_HOME=/app/.cache/huggingface \
    XDG_CACHE_HOME=/app/.cache

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /uvx /bin/

RUN groupadd --system --gid 10001 mistria \
    && useradd --system --uid 10001 --gid mistria --home-dir /app --shell /usr/sbin/nologin mistria \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl libgomp1 libnuma1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

FROM python-base AS backend-vllm-deps

RUN --mount=type=cache,target=/root/.cache/uv \
    uv export --frozen --no-dev --no-hashes --extra inference --output-file /tmp/requirements.txt \
    && uv pip install --system --requirement /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

FROM python-base AS frontend-deps

RUN --mount=type=cache,target=/root/.cache/uv \
    uv export --frozen --no-dev --no-hashes --output-file /tmp/requirements.txt \
    && uv pip install --system --requirement /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

FROM python-base AS runtime-base

COPY . .

RUN mkdir -p /app/data/db /app/Logs /app/.cache/huggingface \
    && chown -R mistria:mistria /app/data /app/Logs /app/.cache

FROM runtime-base AS backend-vllm

COPY --from=backend-vllm-deps /usr/local /usr/local

USER mistria

EXPOSE 8080

CMD ["python", "main.py"]

FROM runtime-base AS frontend

COPY --from=frontend-deps /usr/local /usr/local

USER mistria

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
