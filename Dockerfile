FROM docker:26-cli@sha256:f13cbf1ea352bdbdc825a9233fc56716bdf818e4f608f63280a1aa0b3dc1f2f7 AS docker_cli

FROM python:3.12-slim@sha256:ec948fa5f90f4f8907e89f4800cfd2d2e91e391a4bce4a6afa77ba265bc3a2fe

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY constraints /app/constraints
COPY aria /app/aria
COPY docs /app/docs
COPY prompts /app/prompts
COPY samples /app/samples
COPY config /app/config
COPY docker /app/docker

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=docker_cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker_cli /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/libexec/docker/cli-plugins/docker-compose

RUN python -m pip install --no-cache-dir -c /app/constraints/runtime.txt \
      pip==25.0.1 setuptools==80.9.0 wheel==0.45.1 \
    && python -m pip install --no-cache-dir --no-build-isolation -c /app/constraints/runtime.txt ".[model-gateway]"

RUN mkdir -p /app/data/auth /app/data/logs /app/data/skills /app/bootstrap \
    && cp -a /app/config /app/bootstrap/config \
    && cp -a /app/prompts /app/bootstrap/prompts \
    && chmod +x /app/docker/entrypoint.sh

EXPOSE 8800

VOLUME ["/app/config", "/app/prompts", "/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8800/health', timeout=5)"

ENTRYPOINT ["/app/docker/entrypoint.sh"]
