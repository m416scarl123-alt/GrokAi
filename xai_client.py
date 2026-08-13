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
        inp = []
        for m in messages[:-1]:
            inp.append({"role": m["role"], "content": m["content"]})

        last = messages[-1]
        if image_bytes:
            b64 = base64.b64encode(image_bytes).decode()
            inp.append({
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": f"data:{image_mime};base64,{b64}",
                        "detail": "high",
                    },
                    {"type": "input_text", "text": last["content"]},
                ],
            })
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
            r.raise_for_status()
            data = r.json()
        return data.get("output_text", "")

    async def generate_image(self, prompt):
        payload = {"model": self.image_model, "prompt": prompt}
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(
                f"{self.base}/images/generations",
                headers={**self.headers, "Content-Type": "application/json"},
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
        return data["data"][0].get("url") or data["data"][0].get("b64_json")

    async def stt(self, audio_bytes, filename="voice.ogg"):
        files = {"file": (filename, audio_bytes, "audio/ogg")}
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(
                f"{self.base}/stt",
                headers=self.headers,
                files=files,
            )
            r.raise_for_status()
            return r.json()["text"]

    async def tts(self, text, language="auto"):
        payload = {"text": text, "voice_id": self.voice_id, "language": language}
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(
                f"{self.base}/tts",
                headers={**self.headers, "Content-Type": "application/json"},
                json=payload,
            )
            r.raise_for_status()
            return r.content
