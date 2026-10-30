from pydantic import BaseModel, ConfigDict, Field, field_validator


class RepositoryIndexRequest(BaseModel):
    repository_url: str = Field(min_length=1, max_length=2048)

    model_config = ConfigDict(extra="forbid")


class IndexedFile(BaseModel):
    path: str
    language: str | None
    source: str


class RepositoryIndexResponse(BaseModel):
    owner: str
    name: str
    branch: str
    files: list[IndexedFile]


class RepositorySearchRequest(BaseModel):
    repository_url: str = Field(min_length=1, max_length=2048)
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=50)

    model_config = ConfigDict(extra="forbid")

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Query must not be blank")
        return value.strip()


class RepositorySearchResult(BaseModel):
    chunk_id: str
    repository: str
    file_path: str
    language: str | None
    start_line: int
    end_line: int
    content: str
    semantic_score: float | None
    keyword_score: float | None
    hybrid_score: float


class RepositorySearchResponse(BaseModel):
    repository: str
    query: str
    results: list[RepositorySearchResult]


class RepositoryAskRequest(BaseModel):
    repository_url: str = Field(min_length=1, max_length=2048)
    question: str = Field(min_length=1, max_length=2000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question must not be blank")
        return value.strip()


class RepositoryCitation(BaseModel):
    source_id: str
    chunk_id: str
    file_path: str
    start_line: int
    end_line: int
    relevant_content: str


class RepositoryAskResponse(BaseModel):
    repository: str
    question: str
    answer: str
    insufficient_context: bool
    citations: list[RepositoryCitation]
