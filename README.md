# RAG API with PGVector & D-ID WebRTC Stream

[![Website](https://img.shields.io/badge/Website-Live-brightgreen)](https://renana-friedman.up.railway.app/)
[🔗 Visit Renana Friedman's Live Website](https://renana-friedman.up.railway.app/)

Minimal retrieval-augmented generation (RAG) service built with FastAPI, LangChain, OpenAI, and PostgreSQL + pgvector, integrated with D-ID's WebRTC Streams API to stream real-time speaking avatar responses.

## Demo / Preview

![Avatar Interaction Screenshot](assets/screenshot.png)

*Note: Save your interface screenshot under `assets/screenshot.png` in the repository to display your live preview here.*

---

## Key Features

- **D-ID WebRTC Integration:** Establishes live peer-to-peer video streams of a speaking avatar.
- **RAG-Powered Answers:** Combines PGVector semantic similarity search with OpenAI's `gpt-4o-mini` to answer queries about Renana's background.
- **On-the-fly Ingestion:** Upload PDF or text documents via the `/index` endpoint to expand the knowledge base.
- **In-Memory/Script Ingestion:** Scripted bulk document loading from `data/books`.
- **Stateless Streaming Control:** Standard WebRTC handshake handling (SDP and ICE candidates) through FastAPI endpoints.

---

## Project Structure

- `api.py`: FastAPI application containing document ingestion and D-ID WebRTC streaming endpoints.
- `did_service.py`: Service wrapper using `httpx` to negotiate connections and speak commands with the D-ID API.
- `models.py`: Pydantic data models representing requests and responses.
- `vector_store.py`: Postgres connection helpers, PGVector collection configuration, and file parser (text/PDF).
- `create_database.py`: Script to parse and index Markdown files inside `data/books/` to the database.
- `query_data.py`: CLI testing script to execute similarity search + LLM generation directly.
- `docker-compose.yml`: Local setup for running the FastAPI application alongside a PostgreSQL container with `pgvector`.
- `init.sql`: Automatically initializes the PostgreSQL database with the `vector` extension.

---

## Environment Variables

Create a `.env` file in the repository root:

```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key

# D-ID Configuration
DID_API_KEY=your_d_id_api_key
DID_IMAGE_URL=https://url-to-your-avatar-image.png

# PGVector Database Config
PGVECTOR_COLLECTION=default
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ragdb
POSTGRES_USER=raguser
POSTGRES_PASSWORD=ragpass
```

*Note: In Docker Compose, the database connection is resolved internally using the container services.*

---

## API Endpoints

### 1. Ingestion Endpoint
#### `POST /index`
Uploads a document and indexes its content in the vector database.
- **Content-Type:** `multipart/form-data`
- **Fields:**
  - `file`: The text or PDF file to ingest.
  - `metadata_json` *(optional)*: Stringified JSON containing custom metadata.
  - `reset_collection` *(optional)*: Boolean (`true`/`false`) to clear the database before loading.
  - `context_tag` *(optional)*: String tag to group chunks (e.g. `book`, `cv`).

### 2. D-ID WebRTC Streaming Endpoints
The following endpoints are called sequentially by the frontend to establish and maintain a WebRTC connection:

#### `POST /stream/start`
Initiates a new stream session with D-ID.
- **Response:** Returns `stream_id`, `session_id`, D-ID's WebRTC `offer` (SDP), and `ice_servers`.

#### `POST /stream/sdp`
Sends the local SDP answer from the browser to D-ID to establish the connection.
- **Request Body:**
  ```json
  {
    "stream_id": "str",
    "session_id": "str",
    "answer": {}
  }
  ```

#### `POST /stream/ice`
Submits WebRTC ICE candidates discovered by the browser to D-ID.
- **Request Body:**
  ```json
  {
    "stream_id": "str",
    "session_id": "str",
    "candidate": "str",
    "sdpMid": "str",
    "sdpMLineIndex": 0
  }
  ```

#### `POST /stream/send-text`
Accepts a user question, retrieves relevant context from the database (RAG), runs the LLM, and instructs D-ID to speak the answer dynamically over the active WebRTC stream.
- **Request Body:**
  ```json
  {
    "stream_id": "str",
    "session_id": "str",
    "query_text": "Who is Renana?",
    "k": 6,
    "min_relevance": 0.5,
    "context_tag": "optional_tag",
    "language": "Hebrew"
  }
  ```
- **Response:** Returns the full generated response text and the document sources used.

#### `POST /stream/speak`
Sends static text directly to D-ID to speak on the stream, bypassing the RAG+LLM pipeline (typically used for a welcome/greeting message).
- **Request Body:**
  ```json
  {
    "stream_id": "str",
    "session_id": "str",
    "text": "Hello, welcome to my website!",
    "language": "English"
  }
  ```

#### `POST /stream/close`
Closes the active D-ID stream session to save API usage minutes.
- **Request Body:**
  ```json
  {
    "stream_id": "str",
    "session_id": "str"
  }
  ```

---

## Running the Project

### Option A: Running with Docker (Recommended)

1. Start all containerized services:
   ```bash
   docker compose up --build
   ```
2. The FastAPI server will be available at: `http://localhost:8000`
3. Swagger interactive documentation will be hosted at: `http://localhost:8000/docs`

### Option B: Running Locally

1. Create and activate a python virtual environment:
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Ensure you have a running PostgreSQL database with the `pgvector` extension.
4. Launch the FastAPI server:
   ```bash
   uvicorn api:app --reload --host 0.0.0.0 --port 8000
   ```

---

## Testing / Command Line Interface
You can query the RAG system directly from the terminal without running the web server:
```bash
python query_data.py "Tell me about Renana's experience with Python."
```
Ensure your database is populated and your `.env` contains the required OpenAI credentials.
