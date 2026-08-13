import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str = os.environ["TELEGRAM_BOT_TOKEN"]
    xai_api_key: str = os.environ["XAI_API_KEY"]
    database_url: str = os.environ["DATABASE_URL"]

    admin_telegram_id: int = int(os.environ["ADMIN_TELEGRAM_ID"])
    admin_email: str = os.environ["ADMIN_EMAIL"]
    gmail_smtp_user: str = os.environ["GMAIL_SMTP_USER"]
    gmail_app_password: str = os.environ["GMAIL_APP_PASSWORD"]

    admin_code_ttl_minutes: int = int(os.getenv("ADMIN_CODE_TTL_MINUTES", "5"))
    activation_code_uses: int = int(os.getenv("ACTIVATION_CODE_USES", "3"))
    memory_messages: int = int(os.getenv("MEMORY_MESSAGES", "25"))

    xai_model: str = os.getenv("XAI_MODEL", "grok-4.5")
    xai_image_model: str = os.getenv("XAI_IMAGE_MODEL", "grok-imagine-image-quality")
    xai_voice_id: str = os.getenv("XAI_VOICE_ID", "eve")

settings = Settings()
