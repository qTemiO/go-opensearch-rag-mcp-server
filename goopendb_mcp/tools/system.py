from datetime import datetime
from zoneinfo import ZoneInfo

from goopendb_mcp.app import mcp
from goopendb_mcp.common import annotations
from goopendb_mcp.settings import settings


@mcp.tool(name="current_time", annotations=annotations("Current time", "read"))
def current_time() -> str:
    """Current date and time of the server as ISO 8601 with UTC offset, e.g. '2026-10-06T14:03:00+03:00'."""
    zone = ZoneInfo(settings.TIMEZONE) if settings.TIMEZONE else None
    return datetime.now(zone).astimezone(zone).isoformat(timespec="seconds")
