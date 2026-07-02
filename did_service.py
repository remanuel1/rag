import asyncio
import base64
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

DID_API_URL = "https://api.d-id.com"

VOICE_BY_LANGUAGE = {
    "Hebrew": "he-IL-HilaNeural",
    "English": "en-US-JennyNeural",
}


def _get_headers() -> dict:
    api_key = os.environ["DID_API_KEY"]
    encoded = base64.b64encode(f"{api_key}:".encode()).decode()
    return {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json",
    }


def _get_image_url() -> str:
    return os.environ["DID_IMAGE_URL"]


async def create_talk(text: str, language: str = "Hebrew") -> str:
    voice_id = VOICE_BY_LANGUAGE.get(language.capitalize(), "he-IL-HilaNeural")
    payload = {
        "source_url": _get_image_url(),
        "script": {
            "type": "text",
            "input": text,
            "provider": {"type": "microsoft", "voice_id": voice_id},
        },
        "config": {"fluent": True, "pad_audio": 0.0, "stitch": True},
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{DID_API_URL}/talks",
            json=payload,
            headers=_get_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["id"]


async def wait_for_talk(talk_id: str, timeout: int = 120, poll_interval: float = 2.0) -> str:
    async with httpx.AsyncClient() as client:
        elapsed = 0.0

        while elapsed < timeout:
            response = await client.get(
                f"{DID_API_URL}/talks/{talk_id}",
                headers=_get_headers(),
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            status = data.get("status")

            if status == "done":
                return data["result_url"]
            if status == "error":
                raise RuntimeError(f"D-ID failed: {data.get('error', {})}")

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(f"D-ID talk {talk_id} did not complete within {timeout}s")