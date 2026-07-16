from __future__ import annotations

from typing import Optional
from pydantic import BaseModel



class IndexResponse(BaseModel):
    documents: int
    chunks: int
    collection: str


# ---------------------------------------------------------------------------
# Models for Streams API (WebRTC)
# ---------------------------------------------------------------------------

class StreamStartResponse(BaseModel):
    stream_id: str
    session_id: str
    offer: dict
    ice_servers: list[dict]


class StreamSdpRequest(BaseModel):
    stream_id: str
    session_id: str
    answer: dict


class StreamIceRequest(BaseModel):
    stream_id: str
    session_id: str
    candidate: Optional[str] = None
    sdpMid: Optional[str] = None
    sdpMLineIndex: Optional[int] = None


class StreamSendTextRequest(BaseModel):
    stream_id: str
    session_id: str
    query_text: str
    k: int = 6
    min_relevance: float = 0.5
    context_tag: Optional[str] = None
    language: str = "English"


class StreamSendTextResponse(BaseModel):
    response: str
    sources: list[str]


class StreamCloseRequest(BaseModel):
    stream_id: str
    session_id: str


class StreamSpeakRequest(BaseModel):
    """Sends static text (e.g. welcome greeting) directly to the avatar, bypassing the RAG+LLM pipeline."""
    stream_id: str
    session_id: str
    text: str
    language: str = "English"
