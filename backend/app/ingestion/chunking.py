import hashlib
from dataclasses import dataclass

from app.schemas.repository import IndexedFile, RepositoryIndexResponse


@dataclass(frozen=True)
class SourceChunk:
    chunk_id: str
    repository: str
    file_path: str
    language: str | None
    start_line: int
    end_line: int
    content: str


class CodeChunker:
    def __init__(self, chunk_size_lines: int = 100, overlap_lines: int = 15) -> None:
        if chunk_size_lines <= 0:
            raise ValueError("chunk_size_lines must be positive")
        if overlap_lines < 0 or overlap_lines >= chunk_size_lines:
            raise ValueError(
                "overlap_lines must be non-negative and less than chunk size"
            )
        self.chunk_size_lines = chunk_size_lines
        self.overlap_lines = overlap_lines

    def chunk_repository(
        self,
        repository: RepositoryIndexResponse,
    ) -> list[SourceChunk]:
        repository_id = f"{repository.owner}/{repository.name}"
        chunks: list[SourceChunk] = []
        for indexed_file in repository.files:
            chunks.extend(self.chunk_file(repository_id, indexed_file))
        return chunks

    def chunk_file(
        self,
        repository_id: str,
        indexed_file: IndexedFile,
    ) -> list[SourceChunk]:
        lines = indexed_file.source.splitlines(keepends=True)
        if not lines:
            return []

        chunks: list[SourceChunk] = []
        step = self.chunk_size_lines - self.overlap_lines
        for start_offset in range(0, len(lines), step):
            end_offset = min(start_offset + self.chunk_size_lines, len(lines))
            content = "".join(lines[start_offset:end_offset])
            if content:
                start_line = start_offset + 1
                end_line = end_offset
                identity = "\0".join(
                    (
                        repository_id,
                        indexed_file.path,
                        str(start_line),
                        str(end_line),
                        content,
                    )
                )
                chunk_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
                chunks.append(
                    SourceChunk(
                        chunk_id=chunk_id,
                        repository=repository_id,
                        file_path=indexed_file.path,
                        language=indexed_file.language,
                        start_line=start_line,
                        end_line=end_line,
                        content=content,
                    )
                )
            if end_offset == len(lines):
                break
        return chunks
