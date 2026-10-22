from pydantic import BaseModel, ConfigDict, Field


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
