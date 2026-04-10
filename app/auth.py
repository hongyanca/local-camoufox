from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings
from app.utils.exceptions import AuthenticationError

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Bearer token containing the shared API key.",
)


async def authenticate_request(
    settings: Annotated[Settings, Depends(get_settings)],
    bearer_credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(bearer_scheme)
    ],
) -> None:
    provided_key = bearer_credentials.credentials if bearer_credentials is not None else None
    expected_key = settings.api_key.get_secret_value()

    if not provided_key or not compare_digest(provided_key, expected_key):
        raise AuthenticationError()
