import pytest

from app.core.config import Settings


def test_settings_read_environment_variable(monkeypatch) -> None:
    monkeypatch.setenv("REPOSAGE_APP_NAME", "RepoSage Test")
    monkeypatch.setenv(
        "REPOSAGE_CORS_ORIGINS",
        '["http://localhost:4173"]',
    )

    settings = Settings(_env_file=None)

    assert settings.app_name == "RepoSage Test"
    assert settings.cors_origins == ["http://localhost:4173"]


def test_settings_reject_overlap_at_least_chunk_size() -> None:
    with pytest.raises(ValueError, match="chunk_overlap_lines"):
        Settings(
            _env_file=None,
            chunk_size_lines=20,
            chunk_overlap_lines=20,
        )
