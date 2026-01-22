import asyncio

from langchain_mcp_adapters.client import MultiServerMCPClient  
from langchain.agents import create_agent
from langchain.messages import ToolMessage
from langchain_openai import ChatOpenAI
from langchain.messages import AIMessage
from loguru import logger

from settings import settings


async def main():
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
Ты агент по переводу текста

Правила:
1. Перед переводом убедись, что целевой и исходные языки доступны для перевода с помощью инстурмента Translator.Translator.Get.AvailableLanguages
2. Вызывай Translator.Translate после того как убедишься, что языковая пара доступна для перевода после инстурмента Translator.Translator.Get.AvailableLanguages
3. Если языковая пара недоступна - скажи о том, что язык не поддерживается
4. После ответа верни результат с форматом типа. Вот перевод с *Исходный язык* на *Целевой*: *Перевод*
Answer on Russian.
"""
    )
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "Переведи мне  на русский 'Hallo Herr. Mannelig!'"}]}
    )
    # Extract structured content from tool messages
    

    for message in reversed(result["messages"]):
        if isinstance(message, AIMessage):
            logger.debug(message.content)
            break

    
if __name__ == "__main__":
    asyncio.run(main())