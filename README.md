# RepoSage

RepoSage is an AI codebase intelligence assistant. Phase 3 adds code chunking,
semantic and keyword indexes, and hybrid repository search to the existing
FastAPI backend and minimal React/Vite foundation.

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

Vite prints the local development URL when it starts. The backend allows the
default Vite origin, `http://localhost:5173`.

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
