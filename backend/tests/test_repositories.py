import asyncio
import base64

import httpx
import pytest

from app.api.routes.repositories import get_github_client
from app.core.config import Settings
from app.ingestion.github import (
    GitHubRepositoryIndexer,
    RepositoryIngestionError,
    parse_repository_url,
    should_include_file,
)
from app.main import app
from app.services.repository_index import get_repository_index_registry

API_URL = "https://api.github.com"
REPOSITORY_URL = "https://github.com/example/project"


def response(
    request: httpx.Request,
    payload: object,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=payload,
        headers=headers,
        request=request,
    )


def repository_handler(
    request: httpx.Request,
    tree_entries: list[dict[str, object]],
    blobs: dict[str, bytes],
) -> httpx.Response:
    path = request.url.path
    if path == "/repos/example/project":
        return response(
            request,
            {
                "private": False,
                "owner": {"login": "example"},
                "name": "project",
                "default_branch": "main",
            },
        )
    if path == "/repos/example/project/commits/main":
        return response(
            request,
            {"commit": {"tree": {"sha": "tree-sha"}}},
        )
    if path == "/repos/example/project/git/trees/tree-sha":
        return response(request, {"tree": tree_entries, "truncated": False})
    if path.startswith("/repos/example/project/git/blobs/"):
        sha = path.rsplit("/", 1)[-1]
        content = base64.b64encode(blobs[sha]).decode("ascii")
        return response(
            request,
            {"encoding": "base64", "content": content},
        )
    return response(request, {"message": "not found"}, status_code=404)


def run_index(
    indexer: GitHubRepositoryIndexer,
    client: httpx.AsyncClient,
    repository_url: str = REPOSITORY_URL,
):
    return asyncio.run(indexer.index(repository_url, client))


@pytest.mark.parametrize(
    "repository_url, owner, name",
    [
        ("https://github.com/octo-cat/hello", "octo-cat", "hello"),
        ("https://github.com/octo-cat/hello.git", "octo-cat", "hello"),
    ],
)
def test_parse_valid_public_github_repository_url(
    repository_url: str,
    owner: str,
    name: str,
) -> None:
    reference = parse_repository_url(repository_url)

    assert reference.owner == owner
    assert reference.name == name


@pytest.mark.parametrize(
    "repository_url",
    [
        "http://github.com/example/project",
        "https://github.com.evil.invalid/example/project",
        "https://user@github.com/example/project",
        "https://github.com:8443/example/project",
        "https://github.com/example/project/tree/main",
        "https://github.com/example/project?tab=readme",
        "https://github.com/example/../project",
        "https://github.com/example%2Fother/project",
        "https://github.com/example/project\\..\\private",
        "https://github.com/example/",
    ],
)
def test_parse_rejects_unsafe_or_malformed_repository_url(
    repository_url: str,
) -> None:
    with pytest.raises(RepositoryIngestionError) as error:
        parse_repository_url(repository_url)

    assert error.value.status_code == 422


def test_file_filter_excludes_secrets_binaries_generated_and_dependencies() -> None:
    assert should_include_file("src/app.py")
    assert not should_include_file(".env.production")
    assert not should_include_file("config/id_rsa")
    assert not should_include_file("assets/logo.png")
    assert not should_include_file("dist/app.js")
    assert not should_include_file("src/node_modules/package/index.js")
    assert not should_include_file("src/bundle.min.js")
    assert not should_include_file("src/generated/client.py")


def test_language_detection_covers_json_and_toml_text_files() -> None:
    tree = [
        {"path": "config/settings.json", "type": "blob", "sha": "json", "size": 2},
        {"path": "pyproject.toml", "type": "blob", "sha": "toml", "size": 2},
    ]
    blobs = {"json": b"{}", "toml": b"[]"}
    transport = httpx.MockTransport(
        lambda request: repository_handler(request, tree, blobs)
    )

    async def execute():
        async with httpx.AsyncClient(transport=transport) as client:
            return await GitHubRepositoryIndexer(
                Settings(_env_file=None)
            ).index(REPOSITORY_URL, client)

    result = asyncio.run(execute())

    assert [(file.path, file.language) for file in result.files] == [
        ("config/settings.json", "JSON"),
        ("pyproject.toml", "TOML"),
    ]


def test_index_preserves_metadata_and_filters_files() -> None:
    tree = [
        {"path": "src/app.py", "type": "blob", "sha": "python", "size": 15},
        {"path": "README.md", "type": "blob", "sha": "readme", "size": 14},
        {"path": ".env", "type": "blob", "sha": "secret", "size": 8},
        {
            "path": "node_modules/pkg/index.js",
            "type": "blob",
            "sha": "dependency",
            "size": 13,
        },
        {
            "path": "assets/logo.png",
            "type": "blob",
            "sha": "binary",
            "size": 6,
        },
        {
            "path": "large.py",
            "type": "blob",
            "sha": "large",
            "size": 100,
        },
    ]
    blobs = {
        "python": b"print('hello')\n",
        "readme": b"# Project doc\n",
    }
    transport = httpx.MockTransport(
        lambda request: repository_handler(request, tree, blobs)
    )
    settings = Settings(
        _env_file=None,
        max_file_size_bytes=50,
        max_total_source_bytes=100,
    )

    async def execute():
        async with httpx.AsyncClient(transport=transport) as client:
            return await GitHubRepositoryIndexer(settings).index(
                REPOSITORY_URL, client
            )

    result = asyncio.run(execute())

    assert result.owner == "example"
    assert result.name == "project"
    assert result.branch == "main"
    assert [(file.path, file.language, file.source) for file in result.files] == [
        ("src/app.py", "Python", "print('hello')\n"),
        ("README.md", "Markdown", "# Project doc\n"),
    ]


def test_index_follows_github_tree_pagination_links() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/example/project":
            return response(
                request,
                {
                    "private": False,
                    "owner": {"login": "example"},
                    "name": "project",
                    "default_branch": "main",
                },
            )
        if request.url.path == "/repos/example/project/commits/main":
            return response(request, {"commit": {"tree": {"sha": "tree-sha"}}})
        if request.url.path == "/repos/example/project/git/trees/tree-sha":
            if request.url.params.get("page") == "2":
                return response(
                    request,
                    {
                        "tree": [
                            {
                                "path": "two.py",
                                "type": "blob",
                                "sha": "two",
                                "size": 6,
                            }
                        ],
                        "truncated": False,
                    },
                )
            next_url = (
                f"{API_URL}/repos/example/project/git/trees/tree-sha"
                "?recursive=1&page=2"
            )
            return response(
                request,
                {
                    "tree": [
                        {
                            "path": "one.py",
                            "type": "blob",
                            "sha": "one",
                            "size": 6,
                        }
                    ],
                    "truncated": False,
                },
                headers={"Link": f'<{next_url}>; rel="next"'},
            )
        if request.url.path.endswith("/git/blobs/one"):
            return response(
                request,
                {"encoding": "base64", "content": base64.b64encode(b"one()\n").decode()},
            )
        if request.url.path.endswith("/git/blobs/two"):
            return response(
                request,
                {"encoding": "base64", "content": base64.b64encode(b"two()\n").decode()},
            )
        return response(request, {}, status_code=404)

    async def execute():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            return await GitHubRepositoryIndexer(Settings(_env_file=None)).index(
                REPOSITORY_URL, client
            )

    result = asyncio.run(execute())

    assert [file.path for file in result.files] == ["one.py", "two.py"]


def test_index_recovers_truncated_tree_by_walking_subtrees() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        calls.append(path)
        if path == "/repos/example/project":
            return response(
                request,
                {
                    "private": False,
                    "owner": {"login": "example"},
                    "name": "project",
                    "default_branch": "main",
                },
            )
        if path == "/repos/example/project/commits/main":
            return response(request, {"commit": {"tree": {"sha": "root-tree"}}})
        if path.endswith("/git/trees/root-tree"):
            if request.url.params.get("recursive") == "1":
                return response(
                    request,
                    {"tree": [], "truncated": True},
                )
            return response(
                request,
                {
                    "tree": [
                        {
                            "path": "src",
                            "type": "tree",
                            "sha": "src-tree",
                        }
                    ],
                    "truncated": False,
                },
            )
        if path.endswith("/git/trees/src-tree"):
            return response(
                request,
                {
                    "tree": [
                        {
                            "path": "main.py",
                            "type": "blob",
                            "sha": "file-sha",
                            "size": 7,
                        }
                    ],
                    "truncated": False,
                },
            )
        if path.endswith("/git/blobs/file-sha"):
            return response(
                request,
                {
                    "encoding": "base64",
                    "content": base64.b64encode(b"main()\n").decode(),
                },
            )
        return response(request, {}, status_code=404)

    async def execute():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            return await GitHubRepositoryIndexer(Settings(_env_file=None)).index(
                REPOSITORY_URL, client
            )

    result = asyncio.run(execute())

    assert result.files[0].path == "src/main.py"
    assert "/repos/example/project/git/trees/src-tree" in calls


def test_index_rejects_repository_over_file_count_limit() -> None:
    tree = [
        {"path": "one.py", "type": "blob", "sha": "one", "size": 1},
        {"path": "two.py", "type": "blob", "sha": "two", "size": 1},
    ]
    transport = httpx.MockTransport(
        lambda request: repository_handler(request, tree, {})
    )

    async def execute():
        async with httpx.AsyncClient(transport=transport) as client:
            return await GitHubRepositoryIndexer(
                Settings(_env_file=None, max_repository_files=1)
            ).index(REPOSITORY_URL, client)

    with pytest.raises(RepositoryIngestionError) as error:
        asyncio.run(execute())

    assert error.value.status_code == 413


def test_github_not_found_is_reported_as_repository_not_found() -> None:
    transport = httpx.MockTransport(
        lambda request: response(request, {}, status_code=404)
    )

    async def execute():
        async with httpx.AsyncClient(transport=transport) as client:
            return await GitHubRepositoryIndexer(Settings(_env_file=None)).index(
                REPOSITORY_URL, client
            )

    with pytest.raises(RepositoryIngestionError) as error:
        asyncio.run(execute())

    assert error.value.status_code == 404
    assert error.value.detail == "Public repository not found"


def test_index_rejects_total_source_size_limit() -> None:
    tree = [
        {"path": "one.py", "type": "blob", "sha": "one", "size": 6},
        {"path": "two.py", "type": "blob", "sha": "two", "size": 6},
    ]
    blobs = {"one": b"one()\n", "two": b"two()\n"}
    transport = httpx.MockTransport(
        lambda request: repository_handler(request, tree, blobs)
    )

    async def execute():
        async with httpx.AsyncClient(transport=transport) as client:
            return await GitHubRepositoryIndexer(
                Settings(_env_file=None, max_total_source_bytes=10)
            ).index(REPOSITORY_URL, client)

    with pytest.raises(RepositoryIngestionError) as error:
        asyncio.run(execute())

    assert error.value.status_code == 413


def test_github_rate_limit_is_reported_as_too_many_requests() -> None:
    transport = httpx.MockTransport(
        lambda request: response(
            request,
            {"message": "API rate limit exceeded"},
            status_code=403,
            headers={"X-RateLimit-Remaining": "0"},
        )
    )

    async def execute():
        async with httpx.AsyncClient(transport=transport) as client:
            return await GitHubRepositoryIndexer(Settings(_env_file=None)).index(
                REPOSITORY_URL, client
            )

    with pytest.raises(RepositoryIngestionError) as error:
        asyncio.run(execute())

    assert error.value.status_code == 429


def test_timeout_is_reported_as_gateway_timeout() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream timed out", request=request)

    async def execute():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(timeout)
        ) as client:
            return await GitHubRepositoryIndexer(Settings(_env_file=None)).index(
                REPOSITORY_URL, client
            )

    with pytest.raises(RepositoryIngestionError) as error:
        asyncio.run(execute())

    assert error.value.status_code == 504


def test_index_route_rejects_invalid_url_without_calling_github() -> None:
    def unexpected_request(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Unexpected GitHub request: {request.url}")

    async def override_client() -> object:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(unexpected_request)
        ) as client:
            yield client

    async def execute():
        app.dependency_overrides[get_github_client] = override_client
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                return await client.post(
                    "/api/repositories/index",
                    json={"repository_url": "https://evil.invalid/repo"},
                )
        finally:
            app.dependency_overrides.pop(get_github_client, None)

    result = asyncio.run(execute())

    assert result.status_code == 422
    assert result.json()["detail"] == "Invalid GitHub repository URL"


def test_index_route_returns_repository_response() -> None:
    tree = [{"path": "main.py", "type": "blob", "sha": "main", "size": 7}]
    blobs = {"main": b"main()\n"}

    async def override_client() -> object:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: repository_handler(request, tree, blobs)
            )
        ) as client:
            yield client

    class StubRegistry:
        repository = None
        settings = None

        def build_and_store(self, repository, settings) -> int:
            self.repository = repository
            self.settings = settings
            return len(repository.files)

    registry = StubRegistry()

    def override_registry() -> StubRegistry:
        return registry

    async def execute():
        app.dependency_overrides[get_github_client] = override_client
        app.dependency_overrides[
            get_repository_index_registry
        ] = override_registry
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                return await client.post(
                    "/api/repositories/index",
                    json={"repository_url": REPOSITORY_URL},
                )
        finally:
            app.dependency_overrides.pop(get_github_client, None)
            app.dependency_overrides.pop(
                get_repository_index_registry, None
            )

    result = asyncio.run(execute())

    assert result.status_code == 200
    assert registry.repository.owner == "example"
    assert registry.settings.app_name == "RepoSage"
    assert result.json() == {
        "owner": "example",
        "name": "project",
        "branch": "main",
        "files": [
            {
                "path": "main.py",
                "language": "Python",
                "source": "main()\n",
            }
        ],
    }


def test_index_route_maps_github_api_failure_to_http_error() -> None:
    async def override_client() -> object:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: response(request, {}, status_code=404)
            )
        ) as client:
            yield client

    async def execute():
        app.dependency_overrides[get_github_client] = override_client
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                return await client.post(
                    "/api/repositories/index",
                    json={"repository_url": REPOSITORY_URL},
                )
        finally:
            app.dependency_overrides.pop(get_github_client, None)

    result = asyncio.run(execute())

    assert result.status_code == 404
    assert result.json()["detail"] == "Public repository not found"
