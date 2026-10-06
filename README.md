# go-opensearch-rag-mcp-server

MCP-сервер (Python, FastMCP 4) для [GoOpenDB](../go-opensearch-database), хранилища документов
и конфигурации `agent-constructor` на OpenSearch.

Через сервер LLM-агенты могут:

- искать по RAG-индексам книг (гибридный поиск, реранкинг, фильтр по книгам);
- вести описания книг и управлять корпусом (загрузка текста, переименование, удаление книг, создание индексов);
- работать с generic-индексами JSON-документов (поиск, фильтры, CRUD);
- собирать агентные графы: agents, nodes, edges, graphs, с валидацией по правилам agent-constructor;
- читать и менять реестры MCP-серверов и LLM-провайдеров.

## Префиксы инструментов = права доступа

`agent-constructor` выдаёт агенту инструменты по `mcp_permissions`. Это список **префиксов
имён инструментов**, фильтр `tool.name.startswith(prefix)`. Поэтому имена инструментов
являются публичным контрактом: существующие имена сохранены, новые разложены по префиксам
так, чтобы старые права не получили неожиданного доступа на запись.

| Префикс | Доступ | Инструменты |
| --- | --- | --- |
| `search_` | только чтение | `search_list_indexes`, `search_books`, `search_documents`, `search_documents_with_filter` |
| `descriptions_` | чтение/запись | `descriptions_get_all`, `descriptions_get_by_name`, `descriptions_write`, `descriptions_delete` |
| `books_` | запись | `books_create_index`, `books_load_text`, `books_rename`, `books_delete` |
| `documents_` | чтение/запись | `documents_search`, `documents_filter`, `documents_get`, `documents_create_index`, `documents_upsert`, `documents_patch`, `documents_delete` |
| `agents_` | чтение/запись | CRUD `agents_{list,get,create,update,patch,delete}_{agent,node,edge,graph}`, `agents_get_full_graph`, `agents_get_resolved_agent`, `agents_validate_graph`, `agents_list/get_mcp_server(s)`, `agents_list/get_model_provider(s)` |
| `registry_` | запись | `registry_{create,update,delete}_{mcp_server,model_provider}` |
| — | чтение | `current_time` |

Примеры прав: `["search_"]` даёт весь поиск, `["search_documents"]` только два поисковых
инструмента, `["descriptions_get"]` даёт описания только на чтение.

Ресурс `resource://indexes` отдаёт список RAG-индексов.

## Поведение инструментов

- **Плоские аргументы.** Аргументы передаются напрямую, без обёртки `{"item": {...}}`.
- **Структурированный ответ.** У каждого инструмента есть `outputSchema`, и он возвращает `structuredContent` (плюс тот же JSON текстом).
- **Ошибки.** Ошибки возвращаются как `isError` с понятным текстом и следующим шагом (`"No agent with id 'x'. Use agents_list_agents to find valid ids."`). Тело ошибки GoOpenDB никогда не отдаётся модели под видом данных.
- **Create возвращает id.** GoOpenDB отвечает на create просто `"Written successfully"`, поэтому сервер находит новый объект сам и возвращает его целиком.
- **Проверка ссылок до записи.** Неизвестные книги, `agent_id`, node ids, `mcp_server_ids`, `model_provider_id` и модель вне `available_models` отклоняются до записи, со списком допустимых значений.
- **Защита от поломки графов.** Удаление agent/node/edge, на которые ещё ссылаются, требует `force=true`.
- **Пагинация.** `agents_list_*` поддерживают `limit`/`offset`/`name_contains` и не отдают системные промпты в списках.
- **`descriptions_write` — upsert.** API GoOpenDB добавляет дубль при каждом вызове, сервер заменяет существующее описание.
- **Аннотации.** У всех инструментов есть `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`.

## Конфигурация

Переменные окружения или файл `.env` / `.env.production` в корне (пример: [`.env.dev`](.env.dev)):

| Переменная | По умолчанию | Описание |
| --- | --- | --- |
| `GO_OPENSEARCH_DATABASE_URL` | обязательна | Базовый URL GoOpenDB |
| `HOST` / `PORT` / `MCP_PATH` | `0.0.0.0` / `13005` / `/mcp` | Адрес MCP-эндпоинта |
| `STATELESS_HTTP` | `true` | Stateless streamable HTTP, без sticky-сессий |
| `JSON_RESPONSE` | `true` | JSON-ответы вместо SSE-потока |
| `REQUEST_TIMEOUT_SECONDS` | `60` | Таймаут запросов к GoOpenDB |
| `TIMEZONE` | пусто | IANA-зона для `current_time` |
| `LOG_LEVEL` | `INFO` | Уровень логов |

## Запуск

```bash
poetry install
poetry run python main.py        # http://localhost:13005/mcp
```

Docker:

```bash
docker build -t go-opensearch-rag-mcp-server .
docker run --rm -p 13005:13005 -e GO_OPENSEARCH_DATABASE_URL=http://go-opensearch-database:8000 go-opensearch-rag-mcp-server
```

Отладка через MCP Inspector: `npx @modelcontextprotocol/inspector` → Streamable HTTP → `http://localhost:13005/mcp`.

## Тесты

```bash
poetry run pytest
```

Тесты не требуют ни GoOpenDB, ни LLM: GoOpenDB подменяется in-memory фейком
([`tests/fake_goopendb.py`](tests/fake_goopendb.py)). Отдельный тест фиксирует контракт
имён инструментов и проверяет, что всё под префиксом `search` доступно только на чтение.

Оценочные вопросы для проверки, насколько хорошо LLM справляется с сервером:
[`evaluations/goopendb_eval.xml`](evaluations/goopendb_eval.xml)
(формат скилла `mcp-builder`, только операции чтения).

## Структура

```text
main.py                     точка входа
goopendb_mcp/
  app.py                    экземпляр FastMCP и instructions
  server.py                 запуск транспорта
  settings.py               конфигурация
  client.py                 HTTP-клиент GoOpenDB и обработка ошибок
  common.py                 аннотации, пагинация, общие типы аргументов
  tools/
    search.py               search_*
    descriptions.py         descriptions_*
    books.py                books_*
    documents.py            documents_*
    agents.py               agents_* (agents, чтение реестров)
    graphs.py               agents_* (nodes, edges, graphs, валидация)
    registry.py             registry_*
    system.py               current_time
    _store.py               общий CRUD и получение id после create
tests/
```
