FROM python:3.13-slim AS build

WORKDIR /build
RUN pip install --no-cache-dir "poetry>=2.1,<3"

COPY pyproject.toml poetry.lock ./
# Runtime dependencies only; dev tools stay out of the image.
RUN python -m venv /venv \
    && . /venv/bin/activate \
    && poetry install --only main --no-root --no-interaction --no-ansi


FROM python:3.13-slim AS production

RUN useradd --create-home --uid 10001 mcp
WORKDIR /app

COPY --from=build /venv /venv
COPY goopendb_mcp ./goopendb_mcp
COPY main.py ./

ENV PATH="/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER mcp
EXPOSE 13005

CMD ["python", "main.py"]
