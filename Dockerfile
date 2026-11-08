FROM debian:trixie-slim AS python-env
RUN apt-get update && apt-get install -y --no-install-recommends python3
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
COPY source/pyproject.toml source/uv.lock /src/
RUN UV_PROJECT_ENVIRONMENT=/app/.venv uv sync --locked --no-dev --project /src --python /usr/bin/python3

FROM debian:trixie-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends cups libcupsimage2t64 python3 sane-utils \
    && rm -rf /var/lib/apt/lists/*
RUN --mount=type=bind,source=driver,target=/driver dpkg -i /driver/*.deb
COPY --from=python-env /app/.venv /app/.venv
COPY --chmod=755 entrypoint.sh /usr/local/bin/entrypoint.sh
COPY source/epson_api /app/epson_api
WORKDIR /app
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD lpstat -r | grep -q 'is running' && python3 -c "import socket; socket.create_connection(('127.0.0.1', 8000), 2).close()"
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
