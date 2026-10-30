# RepoSage

RepoSage is an AI codebase intelligence assistant. The FastAPI backend indexes
public GitHub repositories, combines semantic and keyword retrieval, and
generates Gemini answers with source citations. The React/Vite frontend provides
a responsive dashboard for repository indexing and grounded code questions.

## Prerequisites

- Python 3.12
- Node.js 20 or newer and npm
- Windows PowerShell

## Backend setup

Run these commands from the repository root:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item ..\.env.example .env
```

If PowerShell blocks virtual environment activation, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then activate again.

Run the backend from the `backend` directory with the virtual environment
activated:

```powershell
uvicorn app.main:app --reload
```

The health endpoint is available at <http://127.0.0.1:8000/health>, repository
indexing at `POST /api/repositories/index`, search at
`POST /api/repositories/search`, and interactive API documentation at
<http://127.0.0.1:8000/docs>.

### Index a public GitHub repository

From PowerShell, call the endpoint with a public repository URL:

```powershell
$body = @{ repository_url = "https://github.com/psf/requests" } | ConvertTo-Json
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/repositories/index" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

The successful response includes repository identity and the eligible source
files, preserving each repository-relative path and source text:

```json
{
  "owner": "psf",
  "name": "requests",
  "branch": "main",
  "files": [
    {
      "path": "src/requests/__init__.py",
      "language": "Python",
      "source": "..."
    }
  ]
}
```

Invalid or unsupported repository URLs return HTTP 422. Missing or private
repositories return 404. Configured repository/file/chunk limits return 413. GitHub
rate limits return 429, upstream timeouts return 504, and other GitHub API or
network failures return 502 without returning upstream response bodies.

Ingestion only reads repository metadata, trees, and Git blobs through the
GitHub REST API; it does not clone or execute repository code. It follows API
pagination links when present and walks subtrees if GitHub marks a recursive
tree response as truncated. Binary, generated, dependency, build, common
credential/configuration, and oversized files are excluded. Language labels
are inferred from recognized filename extensions; unsupported extensions have
`null` language.

### Index and search

Index a repository first. This existing endpoint now also chunks eligible files,
generates embeddings, and builds the FAISS and BM25 indexes in process:

```powershell
$indexBody = @{ repository_url = "https://github.com/psf/requests" } | ConvertTo-Json
$indexed = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/repositories/index" `
  -Method Post `
  -ContentType "application/json" `
  -Body $indexBody
```

The indexing response retains the Phase 2 response format. Then search that
repository in the same running backend process:

```powershell
$searchBody = @{
  repository_url = "https://github.com/psf/requests"
  query = "Where are request timeouts handled?"
  top_k = 5
} | ConvertTo-Json
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/repositories/search" `
  -Method Post `
  -ContentType "application/json" `
  -Body $searchBody
```

Search response example:

```json
{
  "repository": "psf/requests",
  "query": "Where are request timeouts handled?",
  "results": [
    {
      "chunk_id": "stable-sha256-id",
      "repository": "psf/requests",
      "file_path": "src/requests/adapters.py",
      "language": "Python",
      "start_line": 120,
      "end_line": 180,
      "content": "...",
      "semantic_score": 0.71,
      "keyword_score": 2.4,
      "hybrid_score": 0.032
    }
  ]
}
```

Chunks are deterministic line windows. Defaults are 100 lines with 15 lines
overlap; source line ranges are 1-based and inclusive. Chunk IDs are stable
SHA-256 digests of repository identity, path, range, and content. Chunking is
line-based, not AST-aware.

Semantic search uses normalized Sentence Transformers embeddings and FAISS
CPU inner-product similarity. The backend requirements add
`sentence-transformers`, `faiss-cpu`, `rank-bm25`, and NumPy; no GPU FAISS
package is used. Keyword search uses `rank-bm25`; tokenization keeps
lowercased complete identifiers and also splits snake_case and camelCase
identifiers into searchable parts. This favors identifier lookup but can
produce token-boundary trade-offs for unusual naming styles. The hybrid
retriever combines each result's rank using Reciprocal Rank Fusion:
`sum(1 / (60 + rank))` across semantic and keyword candidate lists. Raw
semantic and BM25 scores are returned for interpretation but are not directly
added together.

Indexes are in memory and disappear when the backend restarts. Indexing the
same repository again replaces its current process-local index. The default
`sentence-transformers/all-MiniLM-L6-v2` model is a lightweight general-purpose
baseline, not a code-specific quality guarantee. Its model files may download
the first time a nonempty repository is indexed; a model load failure returns
an error instead of fabricated embeddings. Retrieval quality has not been
benchmarked against a real query set.

Run backend tests from the `backend` directory with the virtual environment
activated. Tests mock all GitHub API responses, so no network access or token
is needed:

```powershell
python -m pytest
```

## Frontend setup

Open a separate PowerShell window and run these commands from the repository
root:

```powershell
cd frontend
npm install
npm run dev
```

Vite prints the local development URL when it starts. Open that URL to index a
public repository, ask questions, and inspect source citations. The frontend
uses `http://127.0.0.1:8000` as its default backend URL. To use a different
backend, create `frontend\.env.local` with:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Restart Vite after changing this setting. The backend allows the default Vite
origin, `http://localhost:5173`. Do not put Gemini or GitHub credentials in
frontend environment variables; only the backend should receive those secrets.

## Configuration

Copy `.env.example` to `backend\.env` as shown above. Backend settings use the
`REPOSAGE_` environment-variable prefix. Environment variables override values
from the `.env` file. `REPOSAGE_CORS_ORIGINS` must be a JSON array, for example:

```text
REPOSAGE_CORS_ORIGINS=["http://localhost:5173"]
```

Do not commit `.env` files or put credentials in source control. A GitHub token
is optional and only sent to `api.github.com`; configure it as
`REPOSAGE_GITHUB_TOKEN` in `backend\.env` to raise API rate limits. It is never
included in API responses.

The `REPOSAGE_` settings also support:

| Variable | Default | Purpose |
| --- | --- | --- |
| `REPOSAGE_GITHUB_API_TIMEOUT_SECONDS` | `20` | Per-request timeout (maximum 120 seconds) |
| `REPOSAGE_MAX_REPOSITORY_FILES` | `1000` | Maximum eligible files per repository |
| `REPOSAGE_MAX_FILE_SIZE_BYTES` | `1000000` | Maximum size of one source file |
| `REPOSAGE_MAX_TOTAL_SOURCE_BYTES` | `10000000` | Maximum total indexed source size |
| `REPOSAGE_CHUNK_SIZE_LINES` | `100` | Lines in each source chunk |
| `REPOSAGE_CHUNK_OVERLAP_LINES` | `15` | Shared lines between adjacent chunks |
| `REPOSAGE_MAX_REPOSITORY_CHUNKS` | `10000` | Chunk count limit per repository index |
| `REPOSAGE_EMBEDDING_MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | Sentence Transformers model |
| `REPOSAGE_RETRIEVAL_CANDIDATE_COUNT` | `50` | Maximum candidate count per retriever |
| `REPOSAGE_RETRIEVAL_RRF_K` | `60` | Reciprocal Rank Fusion constant |
| `GEMINI_API_KEY` | unset | Google AI Studio API key; required only for `/ask` when context exists |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Gemini model ID |
| `REPOSAGE_GEMINI_TIMEOUT_SECONDS` | `45` | Gemini request timeout (maximum 180 seconds) |
| `REPOSAGE_RAG_CONTEXT_CHUNKS` | `6` | Maximum retrieved chunks sent for one answer |
| `REPOSAGE_RAG_CONTEXT_MAX_CHARACTERS` | `24000` | Maximum serialized source context size |
| `REPOSAGE_RAG_MAX_OUTPUT_TOKENS` | `1200` | Maximum generated answer tokens |

### Ask a question with retrieved code

The `/api/repositories/ask` endpoint requires a repository already indexed in
the current backend process. It reuses hybrid search, sends only a bounded set
of retrieved chunks to Gemini, and returns both the answer and structured
citations:

```powershell
$askBody = @{
  repository_url = "https://github.com/psf/requests"
  question = "How are request timeouts handled?"
} | ConvertTo-Json
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/repositories/ask" `
  -Method Post `
  -ContentType "application/json" `
  -Body $askBody
```

Example response:

```json
{
  "repository": "psf/requests",
  "question": "How are request timeouts handled?",
  "answer": "The adapter configures the timeout when sending a request [src/requests/adapters.py:120-180].",
  "insufficient_context": false,
  "citations": [
    {
      "source_id": "S1",
      "chunk_id": "stable-sha256-id",
      "file_path": "src/requests/adapters.py",
      "start_line": 120,
      "end_line": 180,
      "relevant_content": "..."
    }
  ]
}
```

To configure Gemini, obtain an API key in
[Google AI Studio](https://aistudio.google.com/app/apikey), open `backend\.env`
and set `GEMINI_API_KEY` (or `REPOSAGE_GEMINI_API_KEY`). Do not put the key in
frontend configuration, source code, shell history, or API requests. The key
is used only by the backend and is never returned in API responses. Restart
Uvicorn after changing the environment.

The default `gemini-3.5-flash-lite` is currently listed in Google's model docs
and its pricing page currently lists free-of-charge input/output for the
standard free tier. Availability, quotas, and eligibility can change and vary
by model and project; check your current limits in
[AI Studio](https://aistudio.google.com/) and the official
[model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite),
[pricing](https://ai.google.dev/gemini-api/docs/pricing), and
[rate-limit documentation](https://ai.google.dev/gemini-api/docs/rate-limits).
An HTTP 429 means a quota or rate limit was reached. RepoSage does not fall
back to a paid provider or silently change models.

**Privacy warning:** Google's current pricing documentation indicates that
content submitted through the unpaid service tier may be used to improve
products; review the current
[Gemini API terms](https://ai.google.dev/gemini-api/terms) before use. Do not
send confidential, sensitive, or personal code through an API tier whose
data-use terms are unsuitable for it. Only retrieved chunks are sent, but those
chunks can still contain sensitive source code.

If the repository is not indexed, the endpoint returns HTTP 404. Missing or
invalid Gemini configuration returns 503, quota/rate limits return 429,
timeouts return 504, and other provider failures return 502. Blank questions
are rejected with HTTP 422. Empty retrieval or an answer without validated
source references is returned as `insufficient_context: true` rather than
presenting an unsupported answer. Citation IDs in model output are checked
against the retrieved chunks; displayed paths and line ranges are generated
from those chunks by RepoSage. Answers can still omit relevant facts or
misinterpret code, so review cited source before relying on an answer.

From `backend` with the virtual environment activated, run the mocked tests
without a key or network access:

```powershell
python -m pytest
```
