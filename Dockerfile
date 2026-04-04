FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY aria /app/aria
COPY docs /app/docs
COPY prompts /app/prompts
COPY samples /app/samples
COPY config /app/config
COPY docker /app/docker

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir .

RUN mkdir -p /app/data/auth /app/data/logs /app/data/skills /app/bootstrap \
    && cp -a /app/config /app/bootstrap/config \
    && cp -a /app/prompts /app/bootstrap/prompts \
    && chmod +x /app/docker/entrypoint.sh

EXPOSE 8800

VOLUME ["/app/config", "/app/prompts", "/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8800/health', timeout=5)"

ENTRYPOINT ["/app/docker/entrypoint.sh"]
