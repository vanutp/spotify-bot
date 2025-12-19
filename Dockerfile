FROM python:3.13-slim as base
RUN apt-get update  \
    && apt-get install -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app

FROM base as builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=2.2.1 \
    POETRY_PLUGIN_EXPORT_VERSION=1.9.0

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install poetry==$POETRY_VERSION \
    && pip install poetry-plugin-export==$POETRY_PLUGIN_EXPORT_VERSION
RUN python -m venv /venv

COPY pyproject.toml poetry.lock ./
RUN --mount=type=cache,target=/root/.cache/pip \
    poetry export -f requirements.txt | /venv/bin/pip install -r /dev/stdin


FROM base as runner
COPY --from=builder /venv /venv
ENV PATH="/venv/bin:$PATH"

COPY . .

ENV DATA_DIR=/data
VOLUME /data

ENTRYPOINT ["/venv/bin/python", "-m", "app"]
