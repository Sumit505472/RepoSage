from app.ingestion.chunking import CodeChunker
from app.schemas.repository import IndexedFile, RepositoryIndexResponse


def make_repository(source: str, path: str = "src/main.py") -> RepositoryIndexResponse:
    return RepositoryIndexResponse(
        owner="Example",
        name="Project",
        branch="main",
        files=[IndexedFile(path=path, language="Python", source=source)],
    )


def test_small_file_produces_one_chunk_with_exact_source_lines() -> None:
    repository = make_repository("first line\nsecond line")

    chunks = CodeChunker(chunk_size_lines=10, overlap_lines=2).chunk_repository(
        repository
    )

    assert len(chunks) == 1
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 2
    assert chunks[0].content == "first line\nsecond line"
    assert chunks[0].repository == "Example/Project"


def test_large_file_chunks_overlap_and_use_one_based_line_numbers() -> None:
    source = "".join(f"line {line}\n" for line in range(1, 8))

    chunks = CodeChunker(chunk_size_lines=4, overlap_lines=1).chunk_repository(
        make_repository(source)
    )

    assert [(chunk.start_line, chunk.end_line) for chunk in chunks] == [
        (1, 4),
        (4, 7),
    ]
    assert chunks[0].content.endswith("line 4\n")
    assert chunks[1].content.startswith("line 4\n")


def test_empty_file_produces_no_chunks() -> None:
    chunks = CodeChunker().chunk_repository(make_repository(""))

    assert chunks == []


def test_identical_content_in_different_files_has_distinct_stable_ids() -> None:
    chunker = CodeChunker()
    first = chunker.chunk_repository(make_repository("same\n", "src/one.py"))
    second = chunker.chunk_repository(make_repository("same\n", "src/two.py"))
    repeated = chunker.chunk_repository(make_repository("same\n", "src/one.py"))

    assert first[0].chunk_id != second[0].chunk_id
    assert first[0].chunk_id == repeated[0].chunk_id


def test_chunker_rejects_invalid_overlap() -> None:
    try:
        CodeChunker(chunk_size_lines=4, overlap_lines=4)
    except ValueError as error:
        assert "overlap_lines" in str(error)
    else:
        raise AssertionError("Invalid overlap was accepted")
