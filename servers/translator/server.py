import aiohttp

from fastmcp import FastMCP
from loguru import logger

from settings import settings
from servers.translator.schemas.requests import TranslateTextRequest

translator_mcp = FastMCP(name="TranslatorServer")


@translator_mcp.tool(name="Translator.Translator.Get.AvailableLanguages")
async def get_available_languages() -> list[dict]:
    """
    Этот инструмент позволит посмотреть доступные для перевода языки и их комбинации.
    
    Используй этот инструмент если:
    - Какие исходные языки доступны
    - Какие целевые языки перевода доступны
    - Является ли комбинация языков доступной
    """
    try:
        logger.success("Get available languages called!")
        async with aiohttp.ClientSession() as session:
            url = settings.TRANSLATOR_SERVICE_BASE_URL + settings.TRANSLATOR_SERVICE_MODEL_GARDEN
            response = await session.get(url)
            languages = await response.json()
            return languages.get("languages", [])
    except Exception as error:
        logger.error(f"Error occured with available languages tool, {error}")
        return []
        
@translator_mcp.tool(name="Translator.Translate")
async def translate_text(args: TranslateTextRequest) -> str:
    """
    Этот инструмент переводит текст с исходно языка на целевой язык.
    Перед применением убедись, что языки и их комбинация доступны для перевода
    """
    try:
        logger.success("Transalte tool called!")
        logger.debug(args)
        async with aiohttp.ClientSession() as session:
            url = settings.TRANSLATOR_SERVICE_BASE_URL + settings.TRANSLATOR_SERVICE_TRANSLATE_TEXT
            payload = args.model_dump()
            response = await session.post(url, json=payload)
            result = await response.json()
            logger.debug(result["text"])
            return result["text"]
    except Exception as error:
        logger.error(f"Error occured with available languages tool, {error}")
        return ""
