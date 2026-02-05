import asyncio

import pytest
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from langchain.messages import ToolMessage
from langchain_openai import ChatOpenAI
from langchain.messages import AIMessage
from loguru import logger

from settings import settings


@pytest.mark.asyncio(loop_scope='session')
async def test_mcp_books_list():
    client = MultiServerMCPClient(
        {
            "mcp": {
                "transport": "http",
                "url": settings.TEST_MCP_URL,
            }
        }
    )

    tools = await client.get_tools()
    llm = ChatOpenAI(
        model=settings.TEST_MODEL_NAME,
        api_key=settings.TEST_API_KEY,
        base_url=settings.TEST_PROVIDER_BASE_URL
    )

    agent = create_agent(
        llm,
        tools,
        system_prompt="""
Твой индекс в opensearch это **dnd-index**

Для ответа на вопрос используй инструменты которые тебе даны, если это необходимо.
"""
    )
    result = await agent.ainvoke(
        {"messages": [
            {"role": "user", "content": "Какие документы находятся в индексе?"}]}
    )

    for message in reversed(result["messages"]):
        if isinstance(message, AIMessage):
            logger.debug(message.content)
            break


@pytest.mark.asyncio(loop_scope='session')
async def test_mcp_search_documents():
    client = MultiServerMCPClient(
        {
            "mcp": {
                "transport": "http",
                "url": settings.TEST_MCP_URL,
            }
        }
    )

    tools = await client.get_tools()
    llm = ChatOpenAI(
        model=settings.TEST_MODEL_NAME,
        api_key=settings.TEST_API_KEY,
        base_url=settings.TEST_PROVIDER_BASE_URL
    )

    agent = create_agent(
        llm,
        tools,
        system_prompt="""
Твой индекс в opensearch это **dnd-index**

Для ответа на вопрос используй инструменты которые тебе даны, если это необходимо.
"""
    )
    result = await agent.ainvoke(
        {"messages": [
            {"role": "user", "content": "Найти описание заговора Ядовитые брызги и описание заговора Волшебная рука"}]}
    )

    for message in reversed(result["messages"]):
        if isinstance(message, AIMessage):
            logger.debug(message.content)
            break
