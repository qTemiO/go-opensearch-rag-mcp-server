"""In-memory stand-in for the parts of the GoOpenDB API the tools use."""

import json
import uuid
from typing import Any

import httpx

COLLECTIONS = {
    # list path segment, item path segment, list key, item key, id key
    "agents": ("agents", "agent", "agents", "agent", "uuid"),
    "nodes": ("nodes", "node", "nodes", "node", "id"),
    "edges": ("edges", "edge", "edges", "edge", "id"),
    "graphs": ("graphs", "graph", "graphs", "graph", "id"),
}


class FakeGoOpenDB:
    def __init__(self) -> None:
        self.store: dict[str, dict[str, dict[str, Any]]] = {name: {} for name in COLLECTIONS}
        self.mcp_servers: dict[str, dict[str, Any]] = {}
        self.providers: dict[str, dict[str, Any]] = {}
        self.books: dict[str, list[str]] = {}
        self.descriptions: list[dict[str, str]] = []
        self.requests: list[tuple[str, str, Any]] = []

    # ------------------------------------------------------------ helpers

    def add(self, collection: str, record: dict[str, Any]) -> dict[str, Any]:
        id_key = COLLECTIONS[collection][4]
        record.setdefault(id_key, str(uuid.uuid4()))
        self.store[collection][record[id_key]] = record
        return record

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    @staticmethod
    def _json(status: int, body: Any) -> httpx.Response:
        return httpx.Response(status, json=body)

    @staticmethod
    def _error(status: int, detail: str) -> httpx.Response:
        return httpx.Response(status, json={"Err": {}, "Detail": detail})

    # ------------------------------------------------------------ routing

    def handle(self, request: httpx.Request) -> httpx.Response:
        method, path = request.method, request.url.path
        body = json.loads(request.content) if request.content else None
        self.requests.append((method, path, body))
        parts = path.removeprefix("/api/v1/").split("/")

        if parts[0] == "agents" and len(parts) >= 2:
            return self._agents(method, parts[1:], body)
        if parts[0] == "mcp-servers":
            return self._registry(self.mcp_servers, "mcp_servers", "mcp_server", method, parts, request)
        if parts[0] == "model-providers":
            return self._registry(self.providers, "model_providers", "model_provider", method, parts, request)
        if path == "/api/v1/index-manager/indexes":
            return self._json(200, {"indexes": list(self.books)})
        if path == "/api/v1/books/list":
            return self._json(200, {"books": self.books.get(body["index"], [])})
        if path in ("/api/v1/search/documents", "/api/v1/search/filter_documents"):
            return self._json(200, {"documents": ["passage"], "scores": [0.5], "sources": ["Book A"]})
        if parts[:2] == ["books", "description"]:
            return self._description(method, parts, body, request)
        if parts[:2] == ["books", "descriptions"]:
            matching = [d for d in self.descriptions if d["parent_index"] == parts[2]]
            return self._json(200, {"descriptions": matching or None})
        return self._error(404, f"no fake route for {method} {path}")

    def _agents(self, method: str, parts: list[str], body: Any) -> httpx.Response:
        for name, (list_seg, item_seg, list_key, item_key, id_key) in COLLECTIONS.items():
            records = self.store[name]
            if parts == [list_seg] and method == "GET":
                return self._json(200, {list_key: list(records.values())})
            if parts == [item_seg] and method == "POST":
                self.add(name, dict(body))
                return self._json(200, "Written successfully")
            if len(parts) == 2 and parts[0] == item_seg:
                record = records.get(parts[1])
                if record is None:
                    # GoOpenDB answers 500 for a missing agent, mimic that.
                    return self._error(500 if name == "agents" else 404, f"{item_seg} not found")
                if method == "GET":
                    return self._json(200, {item_key: record})
                if method == "PUT":
                    records[parts[1]] = {**body, id_key: parts[1]}
                    return self._json(200, {"is_updated": True})
                if method == "PATCH":
                    record.update(body)
                    return self._json(200, {"is_updated": True})
                if method == "DELETE":
                    del records[parts[1]]
                    return self._json(200, {"is_deleted": True})
        return self._error(404, "unknown agents route")

    def _registry(self, records, list_key, item_key, method, parts, request) -> httpx.Response:
        if parts[1] == list_key.replace("_", "-") and method == "GET":
            return self._json(200, {list_key: list(records.values())})
        if len(parts) == 3:
            record = records.get(parts[2])
            if record is None:
                return self._error(404, f"{item_key} not found")
            if method == "GET":
                return self._json(200, {item_key: record})
            if method == "DELETE":
                if request.url.params.get("force") != "true" and any(
                    parts[2] in (a.get("mcp_server_ids") or []) or parts[2] == a.get("model_provider_id")
                    for a in self.store["agents"].values()
                ):
                    return self._json(409, {"detail": "still referenced", "agent_uuids": []})
                del records[parts[2]]
                return httpx.Response(204)
        return self._error(404, "unknown registry route")

    def _description(self, method, parts, body, request) -> httpx.Response:
        if method == "POST":
            self.descriptions.append(
                {"book_name": body["book_name"], "parent_index": body["index"], "description": body["description"]}
            )
            return self._json(200, "Written successfully")
        index, book = parts[2], request.url.params.get("book_name")
        matching = [d for d in self.descriptions if d["parent_index"] == index and d["book_name"] == book]
        if method == "GET":
            if not matching:
                return self._error(404, f"Not found this book: {book} in index: {index}")
            return self._json(200, {"description": matching[0]})
        if method == "DELETE":
            self.descriptions = [d for d in self.descriptions if d not in matching]
            return self._json(200, f"Is deleted: {bool(matching)}")
        return self._error(404, "unknown description route")
