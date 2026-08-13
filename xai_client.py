import base64
import httpx


class XAI:
    def __init__(self, api_key, model, image_model, voice_id):
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self.model = model
        self.image_model = image_model
        self.voice_id = voice_id
        self.base = "https://api.x.ai/v1"

    async def chat(
        self,
        messages,
        use_web=True,
        image_bytes=None,
        image_mime="image/jpeg",
    ):
        inp = []

        for m in messages[:-1]:
            inp.append({
                "role": m["role"],
                "content": m["content"],
            })

        last = messages[-1]

        if image_bytes:
            b64 = base64.b64encode(image_bytes).decode("utf-8")

            inp.append({
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": f"data:{image_mime};base64,{b64}",
                    },
                    {
                        "type": "input_text",
                        "text": last["content"],
                    },
                ],
            })
        else:
            inp.append({
                "role": last["role"],
                "content": last["content"],
            })

        payload = {
            "model": self.model,
            "input": inp,
        }

        if use_web:
            payload["tools"] = [
                {
                    "type": "web_search",
                }
            ]

        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{self.base}/responses",
                headers=self.headers,
                json=payload,
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"xAI API {response.status_code}: {response.text}"
            )

        data = response.json()

        if data.get("output_text"):
            return data["output_text"]

        chunks = []

        for item in data.get("output", []):
            for content in item.get("content", []):
                if isinstance(content, dict):
                    text = content.get("text")

                    if text:
                        chunks.append(text)

        if chunks:
            return "\n".join(chunks)

        return "Не удалось получить ответ от Grok."

    async def generate_image(self, prompt):
        payload = {
            "model": self.image_model,
            "prompt": prompt,
        }

        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{self.base}/images/generations",
                headers=self.headers,
                json=payload,
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"xAI API {response.status_code}: {response.text}"
            )

        data = response.json()
        item = data["data"][0]

        return item.get("url") or item.get("b64_json")

    async def stt(self, audio_bytes, filename="voice.ogg"):
        headers = {
            "Authorization": f"Bearer {self.headers['Authorization'].replace('Bearer ', '')}"
        }

        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{self.base}/stt",
                headers=headers,
                files={
                    "file": (
                        filename,
                        audio_bytes,
                        "audio/ogg",
                    )
                },
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"xAI API {response.status_code}: {response.text}"
            )

        data = response.json()

        return data["text"]

    async def tts(self, text, language="auto"):
        payload = {
            "text": text,
            "voice_id": self.voice_id,
            "language": language,
            "output_format": {
                "codec": "mp3",
                "sample_rate": 24000,
                "bit_rate": 128000,
            },
        }

        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{self.base}/tts",
                headers=self.headers,
                json=payload,
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"xAI API {response.status_code}: {response.text}"
            )

        if "application/json" not in response.headers.get(
            "content-type", ""
        ):
            return response.content

        data = response.json()

        if data.get("audio"):
            return base64.b64decode(data["audio"])

        raise RuntimeError(
            "TTS returned JSON without audio."
        )
