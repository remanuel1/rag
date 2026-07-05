import json
from fastapi import FastAPI, HTTPException
from fastapi import File, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from create_database import (
    load_documents,
    split_text,
    save_to_pgvector,
    set_context_tag,
)
from models import (
    IndexResponse, IngestRequest,
    StreamStartResponse, StreamSdpRequest, StreamIceRequest,
    StreamSendTextRequest, StreamSendTextResponse, StreamCloseRequest, StreamSpeakRequest,
)
from did_service import (
    create_stream, send_sdp_answer, send_ice_candidate, send_stream_text, close_stream,
)
from query_data import SYSTEM_TEMPLATE, PROMPT_TEMPLATE
from vector_store import create_vector_store, get_collection_name, extract_content_from_bytes


app = FastAPI(title="RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/index", response_model=IndexResponse)
def index_documents(
    file: UploadFile = File(...),
    metadata_json: str | None = Query(default=None),
    reset_collection: bool = Query(default=False),
    context_tag: str | None = Query(default=None),
):
    try:
        base_metadata = {}
        if metadata_json:
            loaded_metadata = json.loads(metadata_json)
            if not isinstance(loaded_metadata, dict):
                raise HTTPException(status_code=400, detail="metadata_json must be a JSON object.")
            base_metadata = loaded_metadata
        resolved_source = file.filename or "api_document"
        if "source" not in base_metadata:
            base_metadata["source"] = resolved_source
        content = extract_content_from_bytes(file.file.read(), resolved_source)
        documents = [Document(page_content=content, metadata=base_metadata)]
        chunks = split_text(documents)
        chunks = set_context_tag(chunks, context_tag)
        save_to_pgvector(chunks, pre_delete_collection=reset_collection)
        return IndexResponse(
            documents=len(documents),
            chunks=len(chunks),
            collection=get_collection_name(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def _run_rag_and_llm(query_text: str, k: int, min_relevance: float, context_tag: str | None, language: str) -> tuple[str, list[str]]:
    """לוגיקת ה-RAG+LLM המשותפת - בשימוש ע"י /stream/send-text."""
    db = create_vector_store(OpenAIEmbeddings())
    query_filter = {"context_tag": context_tag} if context_tag else None
    results = db.similarity_search_with_relevance_scores(
        query_text,
        k=k,
        filter=query_filter,
    )
    if len(results) == 0 or results[0][1] < min_relevance:
        raise HTTPException(status_code=404, detail="Unable to find matching results.")
    context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
    chat_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(SYSTEM_TEMPLATE),
        HumanMessagePromptTemplate.from_template(PROMPT_TEMPLATE),
    ])
    messages = chat_prompt.format_messages(
        language=language,
        context=context_text,
        question=query_text,
    )
    response_text = ChatOpenAI(
        model="gpt-4o-mini",
        max_tokens=150,
    ).invoke(messages).content
    sources = [doc.metadata.get("source", "") for doc, _score in results]
    return response_text, sources


# ---------------------------------------------------------------------------
# Streams API (WebRTC) - תגובה מהירה בזמן אמת
# ---------------------------------------------------------------------------

@app.post("/stream/start", response_model=StreamStartResponse)
async def stream_start():
    """
    נקרא פעם אחת כשהמשתמש פותח את הצ'אט.
    פותח stream חדש מול D-ID ומחזיר לפרונט את מה שהוא צריך כדי להשלים
    את משא-ומתן ה-WebRTC (SDP offer + ICE servers).
    """
    try:
        data = await create_stream()
        return StreamStartResponse(
            stream_id=data["id"],
            session_id=data["session_id"],
            offer=data["offer"],
            ice_servers=data["ice_servers"],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/stream/sdp")
async def stream_sdp(request: StreamSdpRequest):
    """הפרונט קורא לזה אחרי שהדפדפן יצר SDP answer, כדי לסגור את משא-ומתן ה-WebRTC."""
    try:
        await send_sdp_answer(request.stream_id, request.session_id, request.answer)
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/stream/ice")
async def stream_ice(request: StreamIceRequest):
    """הפרונט קורא לזה בכל ICE candidate שהדפדפן מגלה (חלק ממו״מ ה-WebRTC)."""
    try:
        await send_ice_candidate(
            request.stream_id, request.session_id,
            request.candidate, request.sdpMid, request.sdpMLineIndex,
        )
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/stream/send-text", response_model=StreamSendTextResponse)
async def stream_send_text(request: StreamSendTextRequest):
    """
    נקרא בכל שאלה של המשתמש.
    עושה RAG+LLM ואז שולח את התשובה ל-stream שכבר פתוח -
    D-ID משדר את הוידאו ישירות דרך ה-WebRTC הקיים, בלי לחכות לקובץ שלם.
    """
    try:
        response_text, sources = _run_rag_and_llm(
            request.query_text, request.k, request.min_relevance, request.context_tag, request.language,
        )
        await send_stream_text(request.stream_id, request.session_id, response_text, language=request.language)
        return StreamSendTextResponse(response=response_text, sources=sources)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/stream/speak")
async def stream_speak(request: StreamSpeakRequest):
    """
    משמש לטקסט קבוע כמו ברכת פתיחה - שולח ישירות ל-D-ID בלי RAG+LLM.
    ה-warm-up הזה חשוב: בלי זה, ה-<video> נשאר שחור עד לשאלה הראשונה
    כי D-ID לא שולח פריימים לפני שביקשו ממנו "לדבר" משהו.
    """
    try:
        await send_stream_text(request.stream_id, request.session_id, request.text, language=request.language)
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/stream/close")
async def stream_close(request: StreamCloseRequest):
    """נקרא כשהמשתמש סוגר את הצ'אט, או אוטומטית אחרי חוסר פעילות - כדי לא לבזבז דקות."""
    try:
        await close_stream(request.stream_id, request.session_id)
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
