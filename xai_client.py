import base64
import httpx


class XAI:
    def __init__(self, api_key, model, image_model, voice_id):
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://telegram.org",
            "X-Title": "GrokChat",
        }

        # =========================
        # МОДЕЛЬ ЧАТА
        # =========================

        self.model = "openrouter/free"

        # =========================
        # МОДЕЛЬ ИЗОБРАЖЕНИЙ
        # =========================

        self.image_model = image_model

        # =========================
        # ГОЛОС
        # =========================

        self.voice_id = voice_id

        # Модели OpenRouter для аудио
        self.stt_model = "openai/whisper-1"
        self.tts_model = "openai/gpt-4o-mini-tts-2025-12-15"

        # Если voice_id не задан,
        # используем alloy
        self.tts_voice = voice_id or "alloy"

        self.base = "https://openrouter.ai/api/v1"

    # ==================================================
    # ЧАТ
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

            # ------------------------------------------
            # Если пользователь отправил изображение
            # ------------------------------------------

            if (
                role == "user"
                and image_bytes is not None
                and message is messages[-1]
            ):

                image_base64 = base64.b64encode(
                    image_bytes
                ).decode("utf-8")

                content = [
                    {
                        "type": "text",
                        "text": content,
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

            openrouter_messages.append({
                "role": role,
                "content": content,
            })

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

    # ==================================================
    # ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ
    # ==================================================

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
                f"OpenRouter Image API "
                f"{response.status_code}: "
                f"{response.text}"
            )

        data = response.json()

        try:
            image = data["data"][0]

            if "b64_json" in image:
                return image["b64_json"]

            raise RuntimeError(
                f"Изображение не содержит b64_json: {data}"
            )

        except (
            KeyError,
            IndexError,
            TypeError,
        ):
            raise RuntimeError(
                "OpenRouter не вернул изображение:\n"
                f"{data}"
            )

    # ==================================================
    # 🎤 SPEECH TO TEXT
    # ==================================================

    async def stt(
        self,
        audio_bytes,
        filename="voice.ogg",
    ):

        audio_base64 = base64.b64encode(
            audio_bytes
        ).decode("utf-8")

        payload = {
            "model": self.stt_model,

            "input_audio": {
                "data": audio_base64,
                "format": "ogg",
            },
        }

        async with httpx.AsyncClient(
            timeout=180
        ) as client:

            response = await client.post(
                f"{self.base}/audio/transcriptions",
                headers=self.headers,
                json=payload,
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"OpenRouter STT API "
                f"{response.status_code}: "
                f"{response.text}"
            )

        data = response.json()

        try:
            text = data["text"]

            if not text:
                return "Не удалось распознать речь."

            return text

        except (
            KeyError,
            TypeError,
        ):
            raise RuntimeError(
                "OpenRouter не вернул текст:\n"
                f"{data}"
            )

    # ==================================================
    # 🔊 TEXT TO SPEECH
    # ==================================================

    async def tts(
        self,
        text,
        language="auto",
    ):

        payload = {
            "model": self.tts_model,
            "input": text,
            "voice": self.tts_voice,
            "response_format": "mp3",
        }

        async with httpx.AsyncClient(
            timeout=180
        ) as client:

            response = await client.post(
                f"{self.base}/audio/speech",
                headers=self.headers,
                json=payload,
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"OpenRouter TTS API "
                f"{response.status_code}: "
                f"{response.text}"
            )

        if not response.content:
            raise RuntimeError(
                "OpenRouter не вернул аудио."
            )

        return response.content
