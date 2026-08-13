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
    admin_password: str = os.environ["ADMIN_PASSWORD"]

    memory_messages: int = int(os.getenv("MEMORY_MESSAGES", "25"))
    activation_code_uses: int = int(os.getenv("ACTIVATION_CODE_USES", "3"))
    xai_model: str = os.getenv("XAI_MODEL", "grok-4.5")
    xai_image_model: str = os.getenv("XAI_IMAGE_MODEL", "grok-imagine-image-quality")
    xai_voice_id: str = os.getenv("XAI_VOICE_ID", "eve")

    port: int = int(os.getenv("PORT", "10000"))
    webhook_secret: str = os.getenv("WEBHOOK_SECRET", "")
    external_url: str = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")

settings = Settings()
