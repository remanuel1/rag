import json
import httpx
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
from models import IndexResponse, IngestRequest, AvatarQueryRequest, AvatarQueryResponse, AvatarStatusResponse
from did_service import create_talk, wait_for_talk, DID_API_URL, _get_headers
from query_data import SYSTEM_TEMPLATE, PROMPT_TEMPLATE
from vector_store import create_vector_store, get_collection_name, extract_content_from_bytes


app = FastAPI(title="RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://renana-friedman.up.railway.app/"],
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

'''
@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    try:
        db = create_vector_store(OpenAIEmbeddings())
        query_filter = {"context_tag": request.context_tag} if request.context_tag else None
        results = db.similarity_search_with_relevance_scores(
            request.query_text,
            k=request.k,
            filter=query_filter,
        )
        if len(results) == 0 or results[0][1] < request.min_relevance:
            raise HTTPException(status_code=404, detail="Unable to find matching results.")
        context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
        chat_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(SYSTEM_TEMPLATE),
            HumanMessagePromptTemplate.from_template(PROMPT_TEMPLATE),
        ])
        messages = chat_prompt.format_messages(
            language=request.language,
            context=context_text,
            question=request.query_text,
        )
        response_text = ChatOpenAI(model="gpt-4o-mini").invoke(messages).content
        sources = [doc.metadata.get("source", "") for doc, _score in results]
        return QueryResponse(response=response_text, sources=sources)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
'''

@app.post("/avatar-query", response_model=AvatarQueryResponse)
async def avatar_query(request: AvatarQueryRequest):
    try:
        db = create_vector_store(OpenAIEmbeddings())
        query_filter = {"context_tag": request.context_tag} if request.context_tag else None
        results = db.similarity_search_with_relevance_scores(
            request.query_text,
            k=request.k,
            filter=query_filter,
        )
        if len(results) == 0 or results[0][1] < request.min_relevance:
            raise HTTPException(status_code=404, detail="Unable to find matching results.")
        context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
        chat_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(SYSTEM_TEMPLATE),
            HumanMessagePromptTemplate.from_template(PROMPT_TEMPLATE),
        ])
        messages = chat_prompt.format_messages(
            language=request.language,
            context=context_text,
            question=request.query_text,
        )
        response_text = ChatOpenAI(
            model="gpt-4o-mini",
            max_tokens=150,
        ).invoke(messages).content
        print(f"DEBUG - response_text: '{response_text}'")
        print(f"DEBUG - length: {len(response_text)}")
        talk_id = await create_talk(response_text, language=request.language)
        sources = [doc.metadata.get("source", "") for doc, _score in results]
        return AvatarQueryResponse(response=response_text, talk_id=talk_id, sources=sources)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/avatar-status/{talk_id}", response_model=AvatarStatusResponse)
async def avatar_status(talk_id: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{DID_API_URL}/talks/{talk_id}",
                headers=_get_headers(),
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            status = data.get("status")
            if status == "done":
                return AvatarStatusResponse(status="done", video_url=data["result_url"])
            elif status == "error":
                raise HTTPException(status_code=500, detail="D-ID failed to generate video")
            else:
                return AvatarStatusResponse(status=status, video_url=None)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
