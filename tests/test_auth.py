import asyncio

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from app.auth import authenticate_request
from app.config import get_settings
from app.utils.exceptions import AuthenticationError


def test_authenticate_request_accepts_bearer_token() -> None:
    settings = get_settings()
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="test-api-key",
    )
    asyncio.run(
        authenticate_request(
            settings=settings,
            bearer_credentials=credentials,
        )
    )


def test_authenticate_request_rejects_invalid_key() -> None:
    settings = get_settings()
    with pytest.raises(AuthenticationError):
        asyncio.run(
            authenticate_request(
                settings=settings,
                bearer_credentials=None,
            )
        )


def test_authenticate_request_rejects_wrong_bearer_token() -> None:
    settings = get_settings()
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="wrong-key",
    )
    with pytest.raises(AuthenticationError):
        asyncio.run(
            authenticate_request(
                settings=settings,
                bearer_credentials=credentials,
            )
        )
