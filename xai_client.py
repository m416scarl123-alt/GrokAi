import base64
import io
import os

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

        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://telegram.org",
            "X-Title": "GrokChat",
        }

        self.model = "openrouter/free"
        self.image_model = image_model
        self.voice_id = voice_id or "alloy"

        self.base = "https://openrouter.ai/api/v1"

        # Groq для распознавания голоса
        self.groq = AsyncGroq(
            api_key=os.getenv("GROQ_API_KEY")
        )

    # =========================
    # ЧАТ
    # =========================

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

        # Если есть изображение,
        # добавляем его к последнему сообщению
        if image_bytes is not None and openrouter_messages:

            image_base64 = base64.b64encode(
                image_bytes
            ).decode("utf-8")

            last_message = openrouter_messages[-1]

            last_message["content"] = [
                {
                    "type": "text",
                    "text": last_message["content"],
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url":
                            f"data:{image_mime};base64,"
                            f"{image_base64}"
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

            return data["choices"][0]["message"]["content"]

        except (
            KeyError,
            IndexError,
            TypeError,
        ):

            return "Не удалось получить ответ от AI."

    # =========================
    # ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ
    # =========================

    async def generate_image(self, prompt):

        payload = {
            "model": self.image_model,
            "prompt": prompt,
            "n": 1,
        }

        async with httpx.AsyncClient(
            timeout=180
        ) as client:

            response = await client.post(
                f"{self.base}/images",
                headers=self.headers,
                json=payload,
            )

        if response.status_code >= 400:

            raise RuntimeError(
                f"Image API "
                f"{response.status_code}: "
                f"{response.text}"
            )

        data = response.json()

        try:

            return data["data"][0]["b64_json"]

        except (
            KeyError,
            IndexError,
            TypeError,
        ):

            raise RuntimeError(
                f"Изображение не получено: {data}"
            )

    # =========================
    # 🎤 ГОЛОС → ТЕКСТ
    # =========================

    async def stt(
        self,
        audio_bytes,
        filename="voice.ogg"
    ):

        if not os.getenv("GROQ_API_KEY"):

            raise RuntimeError(
                "GROQ_API_KEY не найден."
            )

        audio_file = (
            filename,
            audio_bytes,
        )

        result = await self.groq.audio.transcriptions.create(
            file=audio_file,
            model="whisper-large-v3-turbo",
            response_format="text",
        )

        return str(result)

    # =========================
    # 🔊 ТЕКСТ → ГОЛОС
    # =========================

    async def tts(
        self,
        text,
        language="auto"
    ):

        # Русский голос
        voice = "ru-RU-DmitryNeural"

        # Если текст на английском
        if language == "en":
            voice = "en-US-GuyNeural"

        communicate = edge_tts.Communicate(
            text,
            voice,
        )

        audio = io.BytesIO()

        async for chunk in communicate.stream():

            if chunk["type"] == "audio":

                audio.write(chunk["data"])

        return audio.getvalue()
