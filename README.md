# RepoSage

RepoSage is an AI codebase intelligence assistant. Phase 2 provides a FastAPI
backend that can index eligible text files from a public GitHub repository,
alongside the minimal React/Vite foundation.

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
indexing is available at `POST /api/repositories/index`, and the interactive
API documentation is at <http://127.0.0.1:8000/docs>.

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
repositories return 404. Configured repository/file limits return 413. GitHub
rate limits return 429, upstream timeouts return 504, and other GitHub API or
network failures return 502 without returning upstream response bodies.

Ingestion only reads repository metadata, trees, and Git blobs through the
GitHub REST API; it does not clone or execute repository code. It follows API
pagination links when present and walks subtrees if GitHub marks a recursive
tree response as truncated. Binary, generated, dependency, build, common
credential/configuration, and oversized files are excluded. Language labels
are inferred from recognized filename extensions; unsupported extensions have
`null` language.

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
