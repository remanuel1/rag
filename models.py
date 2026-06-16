from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class IngestRequest(BaseModel):
    context_tag: Optional[str] = None


class QueryRequest(BaseModel):
    query_text: str
    k: int = 6
    min_relevance: float = 0.5
    context_tag: Optional[str] = None
    language: str = "English"


class QueryResponse(BaseModel):
    response: str
    sources: list[str]


class IndexResponse(BaseModel):
    documents: int
    chunks: int
    collection: str


class AvatarQueryRequest(BaseModel):
    query_text: str
    k: int = 6
    min_relevance: float = 0.5
    context_tag: Optional[str] = None
    language: str = "Hebrew"


class AvatarQueryResponse(BaseModel):
    response: str
    video_url: str
    sources: list[str]
