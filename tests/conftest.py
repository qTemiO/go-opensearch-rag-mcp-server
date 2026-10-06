import os

os.environ.setdefault("GO_OPENSEARCH_DATABASE_URL", "http://goopendb.test")

import pytest
from fastmcp import Client

from goopendb_mcp import tools  # noqa: F401  (registers tools)
from goopendb_mcp.app import mcp
from goopendb_mcp.client import GoOpenDBClient, set_client
from goopendb_mcp.tools import _store
from tests.fake_goopendb import FakeGoOpenDB


@pytest.fixture
def fake(monkeypatch) -> FakeGoOpenDB:
    db = FakeGoOpenDB()
    set_client(GoOpenDBClient("http://goopendb.test", timeout=5, transport=db.transport()))
    monkeypatch.setattr(_store, "DISCOVERY_DELAYS", (0, 0))
    yield db
    set_client(None)


@pytest.fixture
async def client(fake):
    async with Client(mcp) as c:
        yield c


async def call(client: Client, tool: str, /, **arguments):
    """Call a tool and return its structured result, or the error text."""
    result = await client.call_tool(tool, arguments, raise_on_error=False)
    if result.is_error:
        return {"error": result.content[0].text}
    data = result.structured_content
    return data.get("result", data) if isinstance(data, dict) and list(data) == ["result"] else data
