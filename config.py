import random
import string

import structlog
from pydantic import BaseSettings
from pydantic import SecretStr

log = structlog.get_logger()


def generate_string(n: int = 16):
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for _ in range(n))


class Settings(BaseSettings):
    SECRET_KEY: SecretStr = SecretStr(generate_string())

    TELEGRAM_ENABLED: bool = False
    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_CHAT_ID: str | None = None

    BASE: str = "EUR"

    ECB_ENDPOINT: str = "https://sdw-wsrest.ecb.europa.eu/service/data/EXR/"
    ECB_SYMBOLS: str = "USD+CZK+HUF+RON+TRY+BGN"  # we can get monthly too

    APILAYER_API_KEY: SecretStr
    APILAYER_ENDPOINT: str = "https://api.apilayer.com/exchangerates_data/"
    APILAYER_SYMBOLS: str = "RSD,KZT,UAH,UZS"  # daily only

    class Config:
        # environment variables always take priority over dotenv file
        env_file = ".env"


settings = Settings()  # load env vars into a single importable central pydantic model
