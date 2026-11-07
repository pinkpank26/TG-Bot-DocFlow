import os
from dataclasses import dataclass
from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    api_id: int
    api_hash: str
    db_path: str
    encryption_key: str
    web_auth_host: str
    web_auth_port: int
    web_auth_base_url: str


def load_settings() -> Settings:
    return Settings(
        bot_token=os.getenv("BOT_TOKEN", ""),
        api_id=int(os.getenv("TELEGRAM_API_ID", "0")),
        api_hash=os.getenv("TELEGRAM_API_HASH", ""),
        db_path=os.getenv("DB_PATH", "bot.db"),
        encryption_key=os.getenv("SESSION_ENCRYPTION_KEY", ""),
        web_auth_host=os.getenv("WEB_AUTH_HOST", "127.0.0.1"),
        web_auth_port=int(os.getenv("WEB_AUTH_PORT", "8081")),
        web_auth_base_url=os.getenv("WEB_AUTH_BASE_URL", "http://127.0.0.1:8081"),
    )


settings = load_settings()
