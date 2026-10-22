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
