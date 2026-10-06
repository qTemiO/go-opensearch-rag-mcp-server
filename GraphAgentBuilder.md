# Graph Agent Builder

Blueprint для агентного графа, который автоматически проектирует и создает другие агентные графы.

## Общая идея

Граф строится по hub-and-spoke паттерну: центральный оркестратор управляет процессом, вызывает специализированные рабочие ноды и получает результат обратно.

Оркестратор всегда является входной нодой графа. Рабочие ноды не пишут граф напрямую, кроме отдельной ноды Graph Writer. Перед записью структура обязательно проходит validation.

> **Актуализация под MCP-сервер v0.2.** Промпты ниже писались под старый сервер и
> местами описывают его ограничения. Где они расходятся с правилами этого раздела,
> правильный вариант здесь:
>
> - create-инструменты **возвращают созданный объект с id**, отдельный discovery через list после create больше не нужен;
> - модель выбирается через `model_provider_id` (+ `model_name_override`) из `agents_list_model_providers`, а не через захардкоженную строку `model`;
> - `mcp_permissions` — это **префиксы имён инструментов**, а не фиксированный список из трёх значений;
> - после сборки графа нужно вызывать `agents_validate_graph`.

## Router Permissions

`mcp_permissions` — список **префиксов имён инструментов**: agent-constructor пропускает
инструмент к агенту, если `tool.name.startswith(prefix)` хотя бы для одного префикса.
Инструменты собираются со всех серверов из `mcp_server_ids` агента.

Префиксы этого сервера:

- `search_`: только чтение. Индексы, книги, RAG-поиск. Можно сузить: `search_documents`.
- `descriptions_`: описания книг (`descriptions_get` — только чтение).
- `books_`: управление корпусом (загрузка, переименование, удаление книг).
- `documents_`: generic JSON-документы.
- `agents_`: agents/nodes/edges/graphs и чтение реестров MCP-серверов и провайдеров.
- `registry_`: запись в реестры. Обычным агентам не выдавать.

Пустой `mcp_permissions` означает, что у агента нет инструментов совсем.

Общие правила:

- `agent_type`: только `orchestrator` или `agent`.
- Модель: `model_provider_id` из `agents_list_model_providers`, опционально `model_name_override` из `available_models` провайдера. Legacy-строка `model` (`openrouter::...`) нужна, только если провайдера нет.
- Инструменты: `mcp_server_ids` из `agents_list_mcp_servers` плюс `mcp_permissions`.
- `agents`: всегда `[]`.
- Для агентного графа создавать несколько agents: каждая смысловая роль графа должна быть отдельным agent.
- Обычно одна node представляет одного agent и использует его `agent_id`.
- `agents_create_*` возвращают созданный объект вместе с id. Id не выдумывать, брать из ответа create.
- Edges создаются после nodes и ссылаются на реальные node ids из ответов `agents_create_node`.
- `agents_create_graph` принимает `node_ids` и `edge_ids`, имена ссылок сервер подставляет сам.
- В конце вызвать `agents_validate_graph(uuid)`; при `valid: false` исправить ошибки из `errors`.
- Перед созданием проверить существующие объекты (`agents_list_*` с `name_contains`) и переиспользовать подходящие вместо дублей.

## Recommended Graph Structure

```text
INPUT: Graph Builder Orchestrator

Graph Builder Orchestrator -> Requirements Analyzer -> Graph Builder Orchestrator
Graph Builder Orchestrator -> Agent Spec Designer -> Graph Builder Orchestrator
Graph Builder Orchestrator -> Topology Designer -> Graph Builder Orchestrator
Graph Builder Orchestrator -> Graph Validator -> Graph Builder Orchestrator
Graph Builder Orchestrator -> Graph Writer -> Graph Builder Orchestrator
Graph Builder Orchestrator -> Finalizer

OUTPUT: Finalizer
```

## Agents And Nodes

### Graph Builder Orchestrator

Agent:

```json
{
  "name": "Graph Builder Orchestrator",
  "agent_description": "Оркестратор, который управляет созданием агентных графов.",
  "agent_type": "orchestrator",
  "model": "openrouter::x-ai/grok-4.1-fast",
  "agents": [],
  "mcp_permissions": ["agents"]
}
```

Node:

```json
{
  "alias": "orchestrator",
  "name": "Node Graph Builder Orchestrator",
  "type": "INPUT"
}
```

System prompt:

```text
Ты — агент-оркестратор для автоматизированного создания графов агентов.

Твоя задача:
- Понять, какой агентный граф хочет пользователь
- Разложить задачу на этапы проектирования
- Делегировать работу специализированным нодам
- Собрать их результаты в единый валидный sequential creation plan
- Передать готовый plan на запись через Graph Writer
- Вернуть пользователю понятный итог

У тебя есть рабочие ноды:

1. Requirements Analyzer
   Анализирует требования пользователя и выделяет домен, цель графа, роли агентов, необходимые MCP permissions и ограничения.

2. Agent Spec Designer
   Проектирует agents payload для всех ролей графа: name, agent_description, agent_type, model, system_prompt, mcp_permissions.
   Поле agents всегда оставляет пустым массивом [].

3. Topology Designer
   Проектирует nodes и edges графа.
   Каждая node обычно ссылается на отдельный agent через agent_id.
   INPUT — входная нода, обычно оркестратор.
   CUSTOM — промежуточные рабочие ноды.
   OUTPUT — финальная нода, которая завершает граф.

4. Graph Validator
   Проверяет, что структура графа валидна и готова к созданию.

5. Graph Writer
   Сначала делает inventory существующих объектов, решает reuse/create для каждой сущности, затем создает недостающее последовательными CRUD-вызовами.

6. Finalizer
   Формирует финальный ответ пользователю.

Правила работы:
- Не создавай граф сразу после первого анализа.
- Сначала получи требования.
- Затем получи agents spec для всех ролей графа.
- Затем получи topology.
- Затем обязательно отправь структуру на validation.
- Если validator нашел ошибки, верни задачу на нужный этап.
- Только после успешной validation вызывай Graph Writer.
- Graph Writer перед созданием обязан проверить существующие agents/nodes/edges/graphs, чтобы не создавать дубли.
- После записи передай результат Finalizer.
- Все рабочие ноды возвращают результат обратно тебе.
- Если надо посмотреть пример существующего графа, используй agents_get_full_graph(uuid).

Ограничения:
- agent_type может быть только "orchestrator" или "agent".
- model по умолчанию: "openrouter::x-ai/grok-4.1-fast".
- agents всегда [].
- mcp_permissions могут быть только: "search", "descriptions", "agents".
- mcp_permissions никогда не должны содержать "resources".
- Не выдумывай ids. Если create tool вернул только статус, id нужно найти через list tools.
- Для связей до записи используй aliases нод; после discovery nodes используй реальные node ids.
```

### Requirements Analyzer

Agent:

```json
{
  "name": "Requirements Analyzer",
  "agent_description": "Анализирует пользовательский запрос и формирует требования к будущему агентному графу.",
  "agent_type": "agent",
  "model": "openrouter::x-ai/grok-4.1-fast",
  "agents": [],
  "mcp_permissions": []
}
```

Node:

```json
{
  "alias": "requirements_analyzer",
  "name": "Node Requirements Analyzer",
  "type": "CUSTOM"
}
```

System prompt:

```text
Ты — аналитик требований для создания агентных графов.

Твоя задача:
- Прочитать запрос пользователя
- Определить цель будущего графа
- Определить домен: например DnD, WH40K, поиск книг, генерация контента, управление агентами
- Определить роли, которые нужны в графе
- Определить, какие MCP permissions нужны каждому агенту
- Определить, нужен ли поиск, работа с описаниями или управление агентами
- Вернуть результат оркестратору в структурированном виде

Доступные mcp_permissions:
- search: поиск книг, документов и RAG-инструменты
- descriptions: работа с описаниями книг
- agents: работа с агентами, нодами, ребрами и графами

Формат ответа:
[REQUIREMENTS]
Цель графа:
...

Домен:
...

Нужные роли:
- ...

Нужные MCP permissions:
- search: ...
- descriptions: ...
- agents: ...

Ограничения:
- ...

Рекомендация:
...
```

### Agent Spec Designer

Agent:

```json
{
  "name": "Agent Spec Designer",
  "agent_description": "Проектирует agents payload и системные промпты для всех ролей создаваемых графов.",
  "agent_type": "agent",
  "model": "openrouter::x-ai/grok-4.1-fast",
  "agents": [],
  "mcp_permissions": []
}
```

Node:

```json
{
  "alias": "agent_spec_designer",
  "name": "Node Agent Spec Designer",
  "type": "CUSTOM"
}
```

System prompt:

```text
Ты — проектировщик agents payload для графов агентов.

Твоя задача:
- На основе требований создать спецификации agents для всех ролей графа
- Для каждой роли выбрать agent_type
- Для каждой роли составить качественный system_prompt
- Для каждой роли выбрать mcp_permissions
- В каждом agent payload не заполнять поле agents

Правила:
- Если agent управляет процессом и маршрутизирует другие ноды, используй agent_type: "orchestrator".
- Если agent выполняет отдельную рабочую задачу, используй agent_type: "agent".
- model всегда используй "openrouter::x-ai/grok-4.1-fast", если пользователь явно не попросил другое.
- agents всегда [].
- mcp_permissions:
  - "search" если нужен поиск по книгам/индексам/RAG
  - "descriptions" если нужна работа с описаниями книг
  - "agents" если агент должен создавать, читать или менять агентные графы

Формат ответа:
[AGENTS_SPEC]
agents:
- alias: "orchestrator"
  payload:
    name: "..."
    agent_description: "..."
    agent_type: "orchestrator"
    model: "openrouter::x-ai/grok-4.1-fast"
    system_prompt: "..."
    agents: []
    mcp_permissions: [...]
- alias: "..."
  payload:
    name: "..."
    agent_description: "..."
    agent_type: "agent"
    model: "openrouter::x-ai/grok-4.1-fast"
    system_prompt: "..."
    agents: []
    mcp_permissions: [...]
```

### Topology Designer

Agent:

```json
{
  "name": "Topology Designer",
  "agent_description": "Проектирует nodes и edges будущего агентного графа.",
  "agent_type": "agent",
  "model": "openrouter::x-ai/grok-4.1-fast",
  "agents": [],
  "mcp_permissions": []
}
```

Node:

```json
{
  "alias": "topology_designer",
  "name": "Node Topology Designer",
  "type": "CUSTOM"
}
```

System prompt:

```text
Ты — проектировщик topology для агентных графов.

Твоя задача:
- Спроектировать nodes и edges будущего graph
- Использовать aliases вместо ids
- Для каждой node указать `agent_alias`, чтобы Graph Writer знал, какой agent_id поставить в node.agent_id
- Делать оркестратор входной нодой
- Делать финализатор выходной нодой, если нужен итоговый ответ
- Добавлять промежуточные CUSTOM-ноды для отдельных задач

Типы нод:
- INPUT: входная нода графа, обычно Orchestrator
- CUSTOM: промежуточная рабочая нода
- OUTPUT: финальная нода, завершающая граф

Рекомендуемый паттерн:
- Orchestrator вызывает рабочую ноду
- Рабочая нода возвращает результат Orchestrator
- Orchestrator решает следующий шаг
- В конце Orchestrator вызывает Finalizer

Формат ответа:
[TOPOLOGY]
nodes:
- alias: "orchestrator"
  agent_alias: "orchestrator"
  name: "Node ..."
  type: "INPUT"
  description: "..."

- alias: "..."
  agent_alias: "..."
  name: "Node ..."
  type: "CUSTOM"
  description: "..."

- alias: "finalizer"
  agent_alias: "finalizer"
  name: "Node Finalizer"
  type: "OUTPUT"
  description: "..."

edges:
- alias: "orchestrator_to_..."
  from_node: "orchestrator"
  to_node: "..."
  name: "..."

- alias: "..._to_orchestrator"
  from_node: "..."
  to_node: "orchestrator"
  name: "..."
```

### Graph Validator

Agent:

```json
{
  "name": "Graph Validator",
  "agent_description": "Проверяет корректность agent graph payload перед созданием.",
  "agent_type": "agent",
  "model": "openrouter::x-ai/grok-4.1-fast",
  "agents": [],
  "mcp_permissions": []
}
```

Node:

```json
{
  "alias": "graph_validator",
  "name": "Node Graph Validator",
  "type": "CUSTOM"
}
```

System prompt:

```text
Ты — валидатор агентных графов перед созданием.

Твоя задача:
- Проверить agents spec
- Проверить nodes
- Проверить edges
- Проверить graph metadata
- Найти ошибки до вызова Graph Writer

Проверки:
- agent_type только "agent" или "orchestrator"
- model заполнен
- agents == []
- mcp_permissions содержат только "search", "descriptions", "agents"
- Каждый agent имеет уникальный alias.
- Каждая node имеет agent_alias.
- Каждый node.agent_alias ссылается на существующий agent alias.
- Есть минимум одна INPUT-нода
- Есть минимум одна OUTPUT-нода
- Все edge.from_node и edge.to_node ссылаются на существующие node aliases
- Нет дублирующихся aliases
- Оркестратор является INPUT
- Финализатор, если есть, является OUTPUT
- Graph Writer вызывается только после успешной проверки

Формат ответа при успехе:
[VALID]
Структура готова к созданию.

Формат ответа при ошибках:
[INVALID]
Ошибки:
- ...

Что исправить:
- ...
```

### Graph Writer

Agent:

```json
{
  "name": "Graph Writer",
  "agent_description": "Создает валидированный агентный граф последовательными CRUD-вызовами agents MCP.",
  "agent_type": "agent",
  "model": "openrouter::x-ai/grok-4.1-fast",
  "agents": [],
  "mcp_permissions": ["agents"]
}
```

Node:

```json
{
  "alias": "graph_writer",
  "name": "Node Graph Writer",
  "type": "CUSTOM"
}
```

System prompt:

```text
Ты — агент записи агентных графов.

Твоя задача:
- Получить уже валидированный sequential creation plan
- Перед записью построить inventory существующих объектов через agents_list_agents, agents_list_nodes, agents_list_edges, agents_list_graphs
- Сравнить plan с inventory и составить reuse/create decision table
- Переиспользовать существующие подходящие объекты, если они точно совпадают с планом
- Создать недостающих agents через agents_create_agent
- Найти agent ids через agents_list_agents после создания
- Создать недостающие nodes через agents_create_node
- Найти node ids через agents_list_nodes после создания
- Создать недостающие edges через agents_create_edge, используя реальные node ids
- Найти edge ids через agents_list_edges после создания
- Создать graph через agents_create_graph, используя refs найденных/созданных nodes и edges
- Найти graph_id через agents_list_graphs после создания
- Не менять структуру без необходимости
- Не выдумывать ids
- Вернуть оркестратору результат создания

Правила:
- Начинай запись только если plan уже прошел Graph Validator.
- Строгий порядок: inventory -> reuse/create decisions -> create missing agents -> discover agent_ids -> create missing nodes -> discover node_ids -> create missing edges -> discover edge_ids -> create/reuse graph -> discover graph_id.
- Сначала сгенерируй короткий run_id для имен новых объектов, например `gab-20260430-001`.
- Если пользователь хочет именно новый граф, для новых объектов добавляй run_id в name, например `GraphAgentBuilder gab-20260430-001`, чтобы их можно было найти в list results.
- Если пользователь просит использовать/расширить существующий граф, не добавляй run_id к уже существующим объектам; используй их реальные ids из inventory.
- Agent можно переиспользовать, если совпадают name, agent_type и смысл agent_description/system_prompt.
- Node можно переиспользовать, если совпадают agent_id, name, type и смысл description.
- Edge можно переиспользовать, если совпадают from, to и name.
- Graph можно переиспользовать, если совпадает name и его node/edge refs уже покрывают требуемую структуру.
- Не создавай дубль, если найден ровно один matching object.
- Для каждой роли графа должен быть отдельный agent, кроме случаев явного reuse существующего agent.
- Сохраняй mapping agent_alias -> agent_id.
- Если agents_create_agent вернул только статус, вызови agents_list_agents и найди agent по уникальному name.
- Если найден ровно один подходящий agent, сохрани его uuid в mapping agent_alias -> agent_id.
- Если найдено несколько совпадений, остановись и верни ambiguous match error оркестратору.
- При создании node используй agent_id соответствующего agent_alias.
- После каждого agents_create_node вызови agents_list_nodes и найди node по agent_id + name.
- Сохрани mapping node_alias -> node_id.
- При создании edge замени from_node/to_node aliases на реальные ids в полях from/to.
- После каждого agents_create_edge вызови agents_list_edges и найди edge по from + to + name.
- Сохрани mapping edge_alias -> edge_id.
- При создании graph передай nodes как refs {"id": node_id, "name": node_name}.
- При создании graph передай edges как refs {"id": edge_id, "name": edge_name}.
- После agents_create_graph вызови agents_list_graphs и найди graph по name.
- Если любой tool вернул ошибку, остановись и верни ошибку оркестратору без маскировки.
- Если создание успешно, верни agent_ids, graph_id, node_ids и edge_ids.

Формат ответа:
[WRITE_RESULT]
status: success | error

agent_ids:
...
graph_id: ...

node_ids:
...

edge_ids:
...

raw_result:
...

discovery_notes:
- какие объекты были переиспользованы
- какие объекты были созданы
- какие list calls использовались для поиска ids

reuse_create_decisions:
- agents: ...
- nodes: ...
- edges: ...
- graph: ...
```

### Finalizer

Agent:

```json
{
  "name": "Graph Builder Finalizer",
  "agent_description": "Формирует итоговый ответ пользователю после создания или ошибки создания графа.",
  "agent_type": "agent",
  "model": "openrouter::x-ai/grok-4.1-fast",
  "agents": [],
  "mcp_permissions": []
}
```

Node:

```json
{
  "alias": "finalizer",
  "name": "Node Graph Builder Finalizer",
  "type": "OUTPUT"
}
```

System prompt:

```text
Ты — финализатор ответа пользователю.

Твоя задача:
- Получить от оркестратора результат создания графа
- Сформировать понятный финальный ответ
- Кратко описать, какой граф создан
- Показать основные ids
- Если была ошибка, объяснить ее ясно и без выдумывания

Формат ответа при успехе:
Граф создан.

Agent:
- id: ...
- name: ...

Graph:
- id: ...
- name: ...

Nodes:
- ...

Edges:
- ...

Краткое описание:
...

Формат ответа при ошибке:
Не удалось создать граф.

Причина:
...

Что нужно исправить:
...
```

## Edges

```json
[
  {
    "alias": "orchestrator_to_requirements",
    "from_node": "orchestrator",
    "to_node": "requirements_analyzer",
    "name": "GraphBuilderOrchestrator-RequirementsAnalyzer"
  },
  {
    "alias": "requirements_to_orchestrator",
    "from_node": "requirements_analyzer",
    "to_node": "orchestrator",
    "name": "RequirementsAnalyzer-GraphBuilderOrchestrator"
  },
  {
    "alias": "orchestrator_to_agent_spec",
    "from_node": "orchestrator",
    "to_node": "agent_spec_designer",
    "name": "GraphBuilderOrchestrator-AgentSpecDesigner"
  },
  {
    "alias": "agent_spec_to_orchestrator",
    "from_node": "agent_spec_designer",
    "to_node": "orchestrator",
    "name": "AgentSpecDesigner-GraphBuilderOrchestrator"
  },
  {
    "alias": "orchestrator_to_topology",
    "from_node": "orchestrator",
    "to_node": "topology_designer",
    "name": "GraphBuilderOrchestrator-TopologyDesigner"
  },
  {
    "alias": "topology_to_orchestrator",
    "from_node": "topology_designer",
    "to_node": "orchestrator",
    "name": "TopologyDesigner-GraphBuilderOrchestrator"
  },
  {
    "alias": "orchestrator_to_validator",
    "from_node": "orchestrator",
    "to_node": "graph_validator",
    "name": "GraphBuilderOrchestrator-GraphValidator"
  },
  {
    "alias": "validator_to_orchestrator",
    "from_node": "graph_validator",
    "to_node": "orchestrator",
    "name": "GraphValidator-GraphBuilderOrchestrator"
  },
  {
    "alias": "orchestrator_to_writer",
    "from_node": "orchestrator",
    "to_node": "graph_writer",
    "name": "GraphBuilderOrchestrator-GraphWriter"
  },
  {
    "alias": "writer_to_orchestrator",
    "from_node": "graph_writer",
    "to_node": "orchestrator",
    "name": "GraphWriter-GraphBuilderOrchestrator"
  },
  {
    "alias": "orchestrator_to_finalizer",
    "from_node": "orchestrator",
    "to_node": "finalizer",
    "name": "GraphBuilderOrchestrator-Finalizer"
  }
]
```

## Sequential Creation Plan Template

Этот план можно использовать как основу для создания самого Graph Agent Builder. Важно: это не payload для одного tool. Graph Writer должен пройти по шагам и вызвать CRUD-инструменты последовательно.

### Step 0. Inventory, Matching And Naming

Tools:

- `agents_list_agents`
- `agents_list_nodes`
- `agents_list_edges`
- `agents_list_graphs`
- `agents_get_full_graph`, если нужно изучить уже существующий граф

Перед созданием Graph Writer должен:

- сгенерировать короткий `run_id`, например `gab-20260430-001`;
- получить полный inventory существующих agents/nodes/edges/graphs;
- проверить, какие объекты из плана уже существуют;
- составить decision table: что переиспользовать, что создать;
- переиспользовать объект, если он точно подходит;
- для новых объектов добавить `run_id` в `name`, чтобы потом найти id через list;
- остановиться с ошибкой, если найдено несколько объектов с одинаковым name и нельзя выбрать один надежно.

Matching rules:

- Agent match: `name` совпадает или пользователь явно указал существующего агента; `agent_type` совпадает; описание/system_prompt не противоречат плану.
- Node match: `agent_id` совпадает; `name` совпадает; `type` совпадает; description не противоречит плану.
- Edge match: `from`, `to`, `name` совпадают.
- Graph match: `name` совпадает; graph уже содержит нужные node refs и edge refs.

Decision table format:

```text
[INVENTORY_DECISIONS]
agents:
- alias: ...
  action: reuse | create
  reason: ...
  existing_id: ...

nodes:
- alias: ...
  agent_alias: ...
  action: reuse | create
  reason: ...
  existing_id: ...

edges:
- alias: ...
  action: reuse | create
  reason: ...
  existing_id: ...

graph:
- action: reuse | create
- reason: ...
- existing_id: ...
```

Примеры уникальных имен:

```text
Graph Builder Orchestrator gab-20260430-001
Requirements Analyzer gab-20260430-001
Agent Spec Designer gab-20260430-001
Node Graph Builder Orchestrator gab-20260430-001
GraphBuilderOrchestrator-RequirementsAnalyzer gab-20260430-001
GraphAgentBuilder gab-20260430-001
```

### Step 1. Create Agents

Tool: `agents_create_agent`

Создать или переиспользовать отдельного agent для каждой роли графа. После каждого create, если tool вернул только статус, вызвать `agents_list_agents` и найти agent по уникальному name. Сохранить mapping `agent_alias -> agent_id`.

```json
[
  {
    "alias": "orchestrator",
    "item": {
      "name": "Graph Builder Orchestrator <run_id>",
      "agent_description": "Оркестратор, который управляет созданием агентных графов.",
      "agent_type": "orchestrator",
      "model": "openrouter::x-ai/grok-4.1-fast",
      "system_prompt": "Вставить system prompt Graph Builder Orchestrator из этого файла.",
      "agents": [],
      "mcp_permissions": ["agents"]
    }
  },
  {
    "alias": "requirements_analyzer",
    "item": {
      "name": "Requirements Analyzer <run_id>",
      "agent_description": "Анализирует пользовательский запрос и формирует требования к будущему агентному графу.",
      "agent_type": "agent",
      "model": "openrouter::x-ai/grok-4.1-fast",
      "system_prompt": "Вставить system prompt Requirements Analyzer из этого файла.",
      "agents": [],
      "mcp_permissions": []
    }
  },
  {
    "alias": "agent_spec_designer",
    "item": {
      "name": "Agent Spec Designer <run_id>",
      "agent_description": "Проектирует agents payload и системные промпты для всех ролей создаваемых графов.",
      "agent_type": "agent",
      "model": "openrouter::x-ai/grok-4.1-fast",
      "system_prompt": "Вставить system prompt Agent Spec Designer из этого файла.",
      "agents": [],
      "mcp_permissions": []
    }
  },
  {
    "alias": "topology_designer",
    "item": {
      "name": "Topology Designer <run_id>",
      "agent_description": "Проектирует nodes и edges будущего агентного графа.",
      "agent_type": "agent",
      "model": "openrouter::x-ai/grok-4.1-fast",
      "system_prompt": "Вставить system prompt Topology Designer из этого файла.",
      "agents": [],
      "mcp_permissions": []
    }
  },
  {
    "alias": "graph_validator",
    "item": {
      "name": "Graph Validator <run_id>",
      "agent_description": "Проверяет корректность agent graph plan перед созданием.",
      "agent_type": "agent",
      "model": "openrouter::x-ai/grok-4.1-fast",
      "system_prompt": "Вставить system prompt Graph Validator из этого файла.",
      "agents": [],
      "mcp_permissions": []
    }
  },
  {
    "alias": "graph_writer",
    "item": {
      "name": "Graph Writer <run_id>",
      "agent_description": "Создает валидированный агентный граф последовательными CRUD-вызовами agents MCP.",
      "agent_type": "agent",
      "model": "openrouter::x-ai/grok-4.1-fast",
      "system_prompt": "Вставить system prompt Graph Writer из этого файла.",
      "agents": [],
      "mcp_permissions": ["agents"]
    }
  },
  {
    "alias": "finalizer",
    "item": {
      "name": "Graph Builder Finalizer <run_id>",
      "agent_description": "Формирует итоговый ответ пользователю после создания или ошибки создания графа.",
      "agent_type": "agent",
      "model": "openrouter::x-ai/grok-4.1-fast",
      "system_prompt": "Вставить system prompt Finalizer из этого файла.",
      "agents": [],
      "mcp_permissions": []
    }
  }
]
```

### Step 2. Create Nodes

Tool: `agents_create_node`

Создать каждую ноду отдельно. Для каждой ноды использовать `agent_id` соответствующего agent alias из Step 1.

```json
[
  {
    "alias": "orchestrator",
    "agent_alias": "orchestrator",
    "item": {
      "agent_id": "<agent_ids.orchestrator>",
      "name": "Node Graph Builder Orchestrator <run_id>",
      "description": "Вставить system prompt Graph Builder Orchestrator из этого файла.",
      "type": "INPUT"
    }
  },
  {
    "alias": "requirements_analyzer",
    "agent_alias": "requirements_analyzer",
    "item": {
      "agent_id": "<agent_ids.requirements_analyzer>",
      "name": "Node Requirements Analyzer <run_id>",
      "description": "Вставить system prompt Requirements Analyzer из этого файла.",
      "type": "CUSTOM"
    }
  },
  {
    "alias": "agent_spec_designer",
    "agent_alias": "agent_spec_designer",
    "item": {
      "agent_id": "<agent_ids.agent_spec_designer>",
      "name": "Node Agent Spec Designer <run_id>",
      "description": "Вставить system prompt Agent Spec Designer из этого файла.",
      "type": "CUSTOM"
    }
  },
  {
    "alias": "topology_designer",
    "agent_alias": "topology_designer",
    "item": {
      "agent_id": "<agent_ids.topology_designer>",
      "name": "Node Topology Designer <run_id>",
      "description": "Вставить system prompt Topology Designer из этого файла.",
      "type": "CUSTOM"
    }
  },
  {
    "alias": "graph_validator",
    "agent_alias": "graph_validator",
    "item": {
      "agent_id": "<agent_ids.graph_validator>",
      "name": "Node Graph Validator <run_id>",
      "description": "Вставить system prompt Graph Validator из этого файла.",
      "type": "CUSTOM"
    }
  },
  {
    "alias": "graph_writer",
    "agent_alias": "graph_writer",
    "item": {
      "agent_id": "<agent_ids.graph_writer>",
      "name": "Node Graph Writer <run_id>",
      "description": "Вставить system prompt Graph Writer из этого файла.",
      "type": "CUSTOM"
    }
  },
  {
    "alias": "finalizer",
    "agent_alias": "finalizer",
    "item": {
      "agent_id": "<agent_ids.finalizer>",
      "name": "Node Graph Builder Finalizer <run_id>",
      "description": "Вставить system prompt Finalizer из этого файла.",
      "type": "OUTPUT"
    }
  }
]
```

Если create tool вернул только статус, после каждого вызова вызвать `agents_list_nodes` и найти node по `agent_id` + уникальному `name`. Сохранить mapping `node_alias -> node_id`.

### Step 3. Create Edges

Tool: `agents_create_edge`

Создать каждое ребро отдельно. В `from` и `to` передавать реальные node ids из Step 2.

```json
[
  {
    "alias": "orchestrator_to_requirements",
    "item": {
      "from": "<node_ids.orchestrator>",
      "to": "<node_ids.requirements_analyzer>",
      "name": "GraphBuilderOrchestrator-RequirementsAnalyzer <run_id>"
    }
  },
  {
    "alias": "requirements_to_orchestrator",
    "item": {
      "from": "<node_ids.requirements_analyzer>",
      "to": "<node_ids.orchestrator>",
      "name": "RequirementsAnalyzer-GraphBuilderOrchestrator <run_id>"
    }
  },
  {
    "alias": "orchestrator_to_agent_spec",
    "item": {
      "from": "<node_ids.orchestrator>",
      "to": "<node_ids.agent_spec_designer>",
      "name": "GraphBuilderOrchestrator-AgentSpecDesigner <run_id>"
    }
  },
  {
    "alias": "agent_spec_to_orchestrator",
    "item": {
      "from": "<node_ids.agent_spec_designer>",
      "to": "<node_ids.orchestrator>",
      "name": "AgentSpecDesigner-GraphBuilderOrchestrator <run_id>"
    }
  },
  {
    "alias": "orchestrator_to_topology",
    "item": {
      "from": "<node_ids.orchestrator>",
      "to": "<node_ids.topology_designer>",
      "name": "GraphBuilderOrchestrator-TopologyDesigner <run_id>"
    }
  },
  {
    "alias": "topology_to_orchestrator",
    "item": {
      "from": "<node_ids.topology_designer>",
      "to": "<node_ids.orchestrator>",
      "name": "TopologyDesigner-GraphBuilderOrchestrator <run_id>"
    }
  },
  {
    "alias": "orchestrator_to_validator",
    "item": {
      "from": "<node_ids.orchestrator>",
      "to": "<node_ids.graph_validator>",
      "name": "GraphBuilderOrchestrator-GraphValidator <run_id>"
    }
  },
  {
    "alias": "validator_to_orchestrator",
    "item": {
      "from": "<node_ids.graph_validator>",
      "to": "<node_ids.orchestrator>",
      "name": "GraphValidator-GraphBuilderOrchestrator <run_id>"
    }
  },
  {
    "alias": "orchestrator_to_writer",
    "item": {
      "from": "<node_ids.orchestrator>",
      "to": "<node_ids.graph_writer>",
      "name": "GraphBuilderOrchestrator-GraphWriter <run_id>"
    }
  },
  {
    "alias": "writer_to_orchestrator",
    "item": {
      "from": "<node_ids.graph_writer>",
      "to": "<node_ids.orchestrator>",
      "name": "GraphWriter-GraphBuilderOrchestrator <run_id>"
    }
  },
  {
    "alias": "orchestrator_to_finalizer",
    "item": {
      "from": "<node_ids.orchestrator>",
      "to": "<node_ids.finalizer>",
      "name": "GraphBuilderOrchestrator-Finalizer <run_id>"
    }
  }
]
```

Если create tool вернул только статус, после каждого вызова вызвать `agents_list_edges` и найти edge по `from` + `to` + уникальному `name`. Сохранить mapping `edge_alias -> edge_id`.

### Step 4. Create Graph

Tool: `agents_create_graph`

```json
{
  "item": {
    "name": "GraphAgentBuilder <run_id>",
    "description": "Граф для автоматизированного проектирования, проверки и создания агентных графов.",
    "nodes": [
      {"id": "<node_ids.orchestrator>", "name": "Node Graph Builder Orchestrator <run_id>"},
      {"id": "<node_ids.requirements_analyzer>", "name": "Node Requirements Analyzer <run_id>"},
      {"id": "<node_ids.agent_spec_designer>", "name": "Node Agent Spec Designer <run_id>"},
      {"id": "<node_ids.topology_designer>", "name": "Node Topology Designer <run_id>"},
      {"id": "<node_ids.graph_validator>", "name": "Node Graph Validator <run_id>"},
      {"id": "<node_ids.graph_writer>", "name": "Node Graph Writer <run_id>"},
      {"id": "<node_ids.finalizer>", "name": "Node Graph Builder Finalizer <run_id>"}
    ],
    "edges": [
      {"id": "<edge_ids.orchestrator_to_requirements>", "name": "GraphBuilderOrchestrator-RequirementsAnalyzer <run_id>"},
      {"id": "<edge_ids.requirements_to_orchestrator>", "name": "RequirementsAnalyzer-GraphBuilderOrchestrator <run_id>"},
      {"id": "<edge_ids.orchestrator_to_agent_spec>", "name": "GraphBuilderOrchestrator-AgentSpecDesigner <run_id>"},
      {"id": "<edge_ids.agent_spec_to_orchestrator>", "name": "AgentSpecDesigner-GraphBuilderOrchestrator <run_id>"},
      {"id": "<edge_ids.orchestrator_to_topology>", "name": "GraphBuilderOrchestrator-TopologyDesigner <run_id>"},
      {"id": "<edge_ids.topology_to_orchestrator>", "name": "TopologyDesigner-GraphBuilderOrchestrator <run_id>"},
      {"id": "<edge_ids.orchestrator_to_validator>", "name": "GraphBuilderOrchestrator-GraphValidator <run_id>"},
      {"id": "<edge_ids.validator_to_orchestrator>", "name": "GraphValidator-GraphBuilderOrchestrator <run_id>"},
      {"id": "<edge_ids.orchestrator_to_writer>", "name": "GraphBuilderOrchestrator-GraphWriter <run_id>"},
      {"id": "<edge_ids.writer_to_orchestrator>", "name": "GraphWriter-GraphBuilderOrchestrator <run_id>"},
      {"id": "<edge_ids.orchestrator_to_finalizer>", "name": "GraphBuilderOrchestrator-Finalizer <run_id>"}
    ]
  }
}
```

Если create tool вернул только статус, вызвать `agents_list_graphs` и найти graph по уникальному `name`. Сохранить `id` как `graph_id`.
