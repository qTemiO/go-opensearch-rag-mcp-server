import aiohttp

from fastmcp import FastMCP
from loguru import logger

from settings import settings
from servers.translator.schemas.requests import TranslateTextRequest

translator_mcp = FastMCP(name="TransaltorServer")


@translator_mcp.tool(name="Translator.Get.Languages")
async def get_available_languages() -> list[dict]:
    """
    This tool is getting list of available languages in translator service with a list of language codes with available combinations.
    
    Use this tool when you need to know:
    - which source languages are available
    - which target languages are supported
    - whether a translation direction is valid
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
        
@translator_mcp.tool(name="Translator.Translate")
async def translate_text(args: TranslateTextRequest) -> str:
    """
    This tool helps to translate text from translator service.
    Always ensure the language pair is supported before calling this tool.
    """
    try:
        logger.success("Transalte tool called!")
        logger.debug(args)
        async with aiohttp.ClientSession() as session:
            url = settings.TRANSLATOR_SERVICE_BASE_URL + settings.TRANSLATOR_SERVICE_TRANSLATE_TEXT
            payload = args.model_dump()
            response = await session.post(url, json=payload)
            languages = await response.json()
            logger.debug(languages)
            return languages.get("text", "")
    except Exception as error:
        logger.error(f"Error occured with available languages tool, {error}")
