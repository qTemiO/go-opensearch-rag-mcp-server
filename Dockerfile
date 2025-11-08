FROM python:3.13 AS build

WORKDIR /mcp-server

# Виртуальное окружение для slim-версий
COPY pyproject.toml poetry.lock ./
RUN pip install poetry
RUN poetry self update

RUN python -m venv /venv
RUN . /venv/bin/activate && poetry install --no-root

FROM python:3.13-slim AS production
COPY --from=build /venv /venv
COPY . .

EXPOSE 13005

ENV PATH="/venv/bin:$PATH"

CMD ["python", "main.py"]