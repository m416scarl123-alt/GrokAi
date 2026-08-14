import base64
import io
import os
from urllib.parse import quote

import httpx
import edge_tts
from groq import AsyncGroq


class XAI:

    def __init__(
        self,
        api_key,
        model,
        image_model,
        voice_id
    ):

        # =========================
        # OPENROUTER
        # =========================

        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://telegram.org",
            "X-Title": "GrokChat",
        }

        self.model = "openrouter/free"

        # =========================
        # POLLINATIONS
        # =========================

        self.pollinations_api_key = os.getenv(
            "XAI_API_KEY"
        )

        self.image_model = image_model

        # =========================
        # VOICE
        # =========================

        self.voice_id = voice_id or "alloy"

        # =========================
        # OPENROUTER URL
        # =========================

        self.base = "https://openrouter.ai/api/v1"

        # =========================
        # GROQ
        # =========================

        groq_key = os.getenv("GROQ_API_KEY")

        if not groq_key:
            self.groq = None
        else:
            self.groq = AsyncGroq(
                api_key=groq_key
            )

    # ==================================================
    # 💬 ЧАТ
    # ==================================================

    async def chat(
        self,
        messages,
        use_web=True,
        image_bytes=None,
        image_mime="image/jpeg",
    ):

        openrouter_messages = []

        for message in messages:

            role = message["role"]
            content = message["content"]

            openrouter_messages.append({
                "role": role,
                "content": content,
            })

        # ==================================================
        # 🖼️ ДОБАВЛЯЕМ ИЗОБРАЖЕНИЕ
        # ==================================================

        if (
            image_bytes is not None
            and openrouter_messages
        ):

            image_base64 = base64.b64encode(
                image_bytes
            ).decode("utf-8")

            last_message = openrouter_messages[-1]

            text_content = last_message["content"]

            last_message["content"] = [
                {
                    "type": "text",
                    "text": text_content,
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": (
                            f"data:{image_mime};base64,"
                            f"{image_base64}"
                        )
                    },
                },
            ]

        payload = {
            "model": self.model,
            "messages": openrouter_messages,
        }

        async with httpx.AsyncClient(
            timeout=180
        ) as client:

            response = await client.post(
                f"{self.base}/chat/completions",
                headers=self.headers,
                json=payload,
            )

        if response.status_code >= 400:

            raise RuntimeError(
                f"OpenRouter API "
                f"{response.status_code}: "
                f"{response.text}"
            )

        data = response.json()

        try:

            return (
                data["choices"][0]
                ["message"]["content"]
            )

        except (
            KeyError,
            IndexError,
            TypeError,
        ):

            return (
                "Не удалось получить "
                "ответ от AI."
            )

    # ==================================================
    # 🎨 ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЯ
    # ==================================================

    async def generate_image(
        self,
        prompt
    ):

        if not self.pollinations_api_key:

            raise RuntimeError(
                "XAI_API_KEY не найден."
            )

        encoded_prompt = quote(
            prompt,
            safe=""
        )

        url = (
            "https://gen.pollinations.ai/image/"
            f"{encoded_prompt}"
        )

        params = {
            "model": "flux"
        }

        headers = {
            "Authorization":
                f"Bearer {self.pollinations_api_key}"
        }

        async with httpx.AsyncClient(
            timeout=180
        ) as client:

            response = await client.get(
                url,
                headers=headers,
                params=params,
            )

        if response.status_code >= 400:

            raise RuntimeError(
                f"Pollinations API "
                f"{response.status_code}: "
                f"{response.text}"
            )

        if not response.content:

            raise RuntimeError(
                "Pollinations не вернул "
                "изображение."
            )

        return base64.b64encode(
            response.content
        ).decode("utf-8")

    # ==================================================
    # 🎤 SPEECH → TEXT
    # ==================================================

    async def stt(
        self,
        audio_bytes,
        filename="voice.ogg"
    ):

        if self.groq is None:

            raise RuntimeError(
                "GROQ_API_KEY не найден."
            )

        audio_file = (
            filename,
            audio_bytes
        )

        result = await (
            self.groq
            .audio
            .transcriptions
            .create(
                file=audio_file,
                model="whisper-large-v3-turbo",
                response_format="text",
            )
        )

        return str(result)

    # ==================================================
    # 🔊 TEXT → SPEECH
    # ==================================================

    async def tts(
        self,
        text,
        language="auto"
    ):

        # Русский голос по умолчанию
        voice = "ru-RU-DmitryNeural"

        # Английский
        if language == "en":

            voice = (
                "en-US-GuyNeural"
            )

        communicate = edge_tts.Communicate(
            text,
            voice,
        )

        audio = io.BytesIO()

        async for chunk in (
            communicate.stream()
        ):

            if chunk["type"] == "audio":

                audio.write(
                    chunk["data"]
                )

        return audio.getvalue()
