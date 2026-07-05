import base64
import os

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


# ---------------------------------------------------------------------------
# Streams API (WebRTC) - שלב 1: פתיחת session ומשא ומתן (SDP + ICE)
# ---------------------------------------------------------------------------

async def create_stream() -> dict:
    """
    פותח stream חדש מול D-ID.
    מחזיר dict עם: id, offer (SDP), ice_servers, session_id
    """
    payload = {"source_url": _get_image_url()}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{DID_API_URL}/talks/streams",
            json=payload,
            headers=_get_headers(),
        )
        response.raise_for_status()
        return response.json()


async def send_sdp_answer(stream_id: str, session_id: str, answer: dict) -> None:
    """שולח ל-D-ID את ה-SDP answer שהדפדפן יצר, כדי לסגור את משא-ומתן ה-WebRTC."""
    payload = {"session_id": session_id, "answer": answer}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{DID_API_URL}/talks/streams/{stream_id}/sdp",
            json=payload,
            headers=_get_headers(),
        )
        response.raise_for_status()


async def send_ice_candidate(
    stream_id: str,
    session_id: str,
    candidate: str | None,
    sdp_mid: str | None,
    sdp_m_line_index: int | None,
) -> None:
    """
    שולח ל-D-ID כל ICE candidate שהדפדפן מגלה (חלק ממו"מ ה-WebRTC).
    candidate=None מסמן "סיימתי לשלוח candidates".
    """
    payload = {
        "session_id": session_id,
        "candidate": candidate,
        "sdpMid": sdp_mid,
        "sdpMLineIndex": sdp_m_line_index,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{DID_API_URL}/talks/streams/{stream_id}/ice",
            json=payload,
            headers=_get_headers(),
        )
        response.raise_for_status()


# ---------------------------------------------------------------------------
# Streams API - שלב 2: לגרום לאווטאר "לדבר" דרך stream פתוח
# ---------------------------------------------------------------------------

async def send_stream_text(stream_id: str, session_id: str, text: str, language: str = "Hebrew") -> None:
    """
    שולח טקסט לאווטאר בזמן שה-stream כבר פתוח.
    D-ID ישדר את הפריימים ישירות דרך ה-WebRTC הקיים - אין המתנה לקובץ שלם.
    """
    voice_id = VOICE_BY_LANGUAGE.get(language.capitalize(), "he-IL-HilaNeural")
    payload = {
        "session_id": session_id,
        "script": {
            "type": "text",
            "input": text,
            "provider": {"type": "microsoft", "voice_id": voice_id},
        },
        "config": {"fluent": True, "pad_audio": 0.0},
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{DID_API_URL}/talks/streams/{stream_id}",
            json=payload,
            headers=_get_headers(),
        )
        response.raise_for_status()


async def close_stream(stream_id: str, session_id: str) -> None:
    """
    סוגר את ה-stream - חשוב לקרוא לזה כדי לא לבזבז דקות מיותרות.
    אם D-ID כבר סגר את ה-stream לבד (חוסר פעילות) הוא יחזיר 400 - זה תקין,
    לא מטפלים בזה כשגיאה אמיתית.
    """
    payload = {"session_id": session_id}

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.request(
            "DELETE",
            f"{DID_API_URL}/talks/streams/{stream_id}",
            json=payload,
            headers=_get_headers(),
        )
        if response.status_code == 400:
            # כנראה ה-stream כבר לא קיים/כבר נסגר - זה תקין, לא שגיאה
            return
        response.raise_for_status()
