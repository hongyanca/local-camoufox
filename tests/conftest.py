import os
from collections.abc import Generator

import pytest

os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("REQUEST_TIMEOUT_SECONDS", "30")
os.environ.setdefault("MAX_URL_LENGTH", "2048")
os.environ.setdefault("ALLOW_PRIVATE_IPS", "false")
os.environ.setdefault("LOG_LEVEL", "INFO")
os.environ.setdefault("CAMOUFOX_HEADLESS", "virtual")
os.environ.setdefault("CAMOUFOX_WAIT_UNTIL", "networkidle")
os.environ.setdefault("CAMOUFOX_POST_LOAD_WAIT_MS", "0")

from app.config import get_settings
from app.main import app


@pytest.fixture(autouse=True)
def reset_state(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("MAX_URL_LENGTH", "2048")
    monkeypatch.setenv("ALLOW_PRIVATE_IPS", "false")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("CAMOUFOX_HEADLESS", "virtual")
    monkeypatch.setenv("CAMOUFOX_WAIT_UNTIL", "networkidle")
    monkeypatch.setenv("CAMOUFOX_POST_LOAD_WAIT_MS", "0")

    get_settings.cache_clear()
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
    get_settings.cache_clear()
