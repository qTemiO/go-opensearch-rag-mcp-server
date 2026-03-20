# go-opensearch-rag-mcp-server

MCP-сервер на Python для работы с данными из `go-opensearch-database`.

Сервис объединяет несколько MCP-инструментов в одну точку входа и позволяет:

- получать текущее время;
- искать документы и фрагменты текста в OpenSearch;
- получать, записывать и удалять описания книг;
- получать список доступных индексов.

## Что внутри

Основной сервер запускается из [`main.py`](/c:/Users/Undefined/Documents/GitHub/go-opensearch-rag-mcp-server/main.py) и подключает три под-сервера:

- `search`:
  поиск документов и список книг в индексе;
- `descriptions`:
  чтение и изменение описаний книг;
- `resources`:
  доступ к списку индексов.

Транспорт запуска: `streamable-http`.

По умолчанию сервис слушает `0.0.0.0:13005`.

## MCP-инструменты

### Основной сервер

- `current_time() -> str`

### `search`

- `search_books(index: str)`  
  Возвращает список книг, загруженных в указанный индекс.
- `search_documents(item)`  
  Ищет документы по текстовому запросу.
- `search_documents_with_filter(item)`  
  Ищет документы с дополнительной фильтрацией по разрешенным и запрещенным книгам.

Фактические имена инструментов будут сформированы FastMCP с учетом префиксов, подключенных в [`main.py`](/c:/Users/Undefined/Documents/GitHub/go-opensearch-rag-mcp-server/main.py).

### `descriptions`

- `descriptions_get_all(index: str)`  
  Возвращает все описания книг в индексе.
- `descriptions_get_by_name(index: str, book_name: str)`  
  Возвращает описание конкретной книги.
- `descriptions_write(item)`  
  Создает или обновляет описание книги.
- `descriptions_delete(item)`  
  Удаляет описание книги.

### `resources`

- `resources_indexes()`  
  Возвращает список доступных индексов.

Дополнительно сервер публикует ресурс `resource://indexes`.

## Зависимости

- Python `3.13`
- Poetry
- доступный HTTP API сервиса `go-opensearch-database`

Основные библиотеки:

- `fastmcp`
- `aiohttp`
- `loguru`
- `fastapi`

## Конфигурация

Настройки описаны в [`settings.py`](/c:/Users/Undefined/Documents/GitHub/go-opensearch-rag-mcp-server/settings.py).

Важно: сейчас `BaseSettings` по умолчанию читает файл `.env.production`.

Для локального запуска нужно либо:

1. заполнить `.env.production`,
2. либо изменить `env_file` в `settings.py`,
3. либо передать переменные окружения напрямую через среду выполнения.

Минимально необходимые переменные:

```env
HOST=0.0.0.0
PORT=13005
GO_OPENSEARCH_DATABASE_URL=http://localhost:8000
```

Также в настройках есть переменные для интеграционных тестов:

```env
TEST_PROVIDER_BASE_URL=
TEST_API_KEY=
TEST_MODEL_NAME=
TEST_MCP_URL=http://localhost:13005/mcp
```

## Установка и запуск

### Через Poetry

```bash
poetry install
poetry run python main.py
```

После запуска MCP-сервер будет доступен по адресу:

```text
http://localhost:13005/mcp
```

### Через Docker

```bash
docker build -t go-opensearch-rag-mcp-server .
docker run --rm -p 13005:13005 --env-file .env.production go-opensearch-rag-mcp-server
```

## Примеры сценариев использования

- получить список книг из индекса OpenSearch;
- найти релевантные фрагменты по пользовательскому запросу;
- ограничить поиск конкретными книгами;
- сохранить краткое описание книги для дальнейшего использования агентом;
- получить список индексов, доступных в базе.

## Тесты

В репозитории есть интеграционные тесты в [`servers/search/tool_test.py`](/c:/Users/Undefined/Documents/GitHub/go-opensearch-rag-mcp-server/servers/search/tool_test.py).

Для запуска тестов нужны:

- запущенный MCP-сервер;
- доступ к LLM-провайдеру;
- заполненные `TEST_*` переменные окружения.

Команда запуска:

```bash
poetry run pytest
```

## Структура проекта

```text
.
|-- main.py
|-- settings.py
|-- servers/
|   |-- search/
|   |-- descriptions/
|   `-- resourses/
|-- Dockerfile
`-- pyproject.toml
```
