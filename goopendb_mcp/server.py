import sys

from loguru import logger

from goopendb_mcp import tools  # noqa: F401  (registers tools)
from goopendb_mcp.app import mcp
from goopendb_mcp.settings import settings


def main() -> None:
    logger.remove()
    logger.add(sys.stderr, level=settings.LOG_LEVEL)
    logger.info(f"GoOpenDB: {settings.GO_OPENSEARCH_DATABASE_URL}")
    mcp.run(
        "streamable-http",
        host=settings.HOST,
        port=settings.PORT,
        path=settings.MCP_PATH,
        stateless_http=settings.STATELESS_HTTP,
        json_response=settings.JSON_RESPONSE,
        show_banner=False,
    )


if __name__ == "__main__":
    main()
