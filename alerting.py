import requests
import structlog

from config import settings

log = structlog.get_logger()


async def telegram(text: str) -> None:
    if not settings.TELEGRAM_ENABLED:
        return None

    api_url = "https://api.telegram.org"
    endpoint = "sendMessage"
    try:
        requests.post(
            url=f"{api_url}/bot{settings.TELEGRAM_BOT_TOKEN}/{endpoint}",
            headers={"Content-type": "application/json"},
            params={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
            },
        )
    except BaseException:
        log.warning("telegram message not dispatched", message=text)
    return None
