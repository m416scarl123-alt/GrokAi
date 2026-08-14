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

        self.model = "openrouter/free"
        self.image_model = image_model
        self.voice_id = voice_id

        self.base = "https://openrouter.ai/api/v1"

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

            # Если передано изображение
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
                f"OpenRouter Image API "
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
                "OpenRouter не вернул изображение:\n"
                f"{data}"
            )

    # =========================
    # SPEECH TO TEXT
    # =========================

    async def stt(
        self,
        audio_bytes,
        filename="voice.ogg"
    ):

        raise RuntimeError(
            "Распознавание голоса пока не подключено."
        )

    # =========================
    # TEXT TO SPEECH
    # =========================

    async def tts(
        self,
        text,
        language="auto"
    ):

        raise RuntimeError(
            "Озвучивание пока не подключено."
        )
