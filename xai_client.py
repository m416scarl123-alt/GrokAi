import base64
import httpx

class XAI:
    def __init__(self, api_key, model, image_model, voice_id):
        self.headers = {"Authorization": f"Bearer {api_key}"}
        self.model = model
        self.image_model = image_model
        self.voice_id = voice_id
        self.base = "https://api.x.ai/v1"

    async def chat(self, messages, use_web=True, image_bytes=None, image_mime="image/jpeg"):
        inp = [{"role": m["role"], "content": m["content"]} for m in messages[:-1]]
        last = messages[-1]
        if image_bytes:
            b64 = base64.b64encode(image_bytes).decode()
            inp.append({"role": "user", "content": [
                {"type": "input_image", "image_url": f"data:{image_mime};base64,{b64}", "detail": "high"},
                {"type": "input_text", "text": last["content"]},
            ]})
        else:
            inp.append({"role": last["role"], "content": last["content"]})

        payload = {"model": self.model, "input": inp}
        if use_web:
            payload["tools"] = [{"type": "web_search"}]

        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(
    f"{self.base}/responses",
    headers={**self.headers, "Content-Type": "application/json"},
    json=payload,
)

if r.status_code >= 400:
    raise RuntimeError(
        f"xAI API {r.status_code}: {r.text}"
    )

data = r.json()
  
chunks = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                if isinstance(content, dict) and content.get("text"):
                    chunks.append(content["text"])
        return "\n".join(chunks) if chunks else "Не удалось получить ответ от Grok."

    async def generate_image(self, prompt):
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(
                f"{self.base}/images/generations",
                headers={**self.headers, "Content-Type": "application/json"},
                json={"model": self.image_model, "prompt": prompt},
            )
            r.raise_for_status()
            item = r.json()["data"][0]
        return item.get("url") or item.get("b64_json")

    async def stt(self, audio_bytes, filename="voice.ogg"):
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(
                f"{self.base}/stt",
                headers=self.headers,
                files={"file": (filename, audio_bytes, "audio/ogg")},
            )
            r.raise_for_status()
            return r.json()["text"]

    async def tts(self, text, language="auto"):
        payload = {
            "text": text,
            "voice_id": self.voice_id,
            "language": language,
            "output_format": {"codec": "mp3", "sample_rate": 24000, "bit_rate": 128000},
        }
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(
                f"{self.base}/tts",
                headers={**self.headers, "Content-Type": "application/json"},
                json=payload,
            )
            r.raise_for_status()
            if "application/json" not in r.headers.get("content-type", ""):
                return r.content
            data = r.json()
            if data.get("audio"):
                return base64.b64decode(data["audio"])
            raise RuntimeError("TTS returned JSON without audio.")
