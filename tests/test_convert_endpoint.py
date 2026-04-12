import asyncio
import json

from fastapi.exceptions import RequestValidationError
from starlette.requests import Request

from app.main import app
from app.models import ConvertRequest, ConvertResponse, RawResponse
from app.routers.convert import convert_url, raw_url
from app.services.conversion_service import ConversionResult, RawResult
from app.utils.exceptions import (
    ApplicationError,
    ConversionError,
    FetchTimeoutError,
    InvalidUrlError,
)


class FakeService:
    def __init__(
        self,
        *,
        result: ConversionResult | None = None,
        raw_result: RawResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or ConversionResult(
            url="https://example.com/article",
            markdown="# Example",
        )
        self.raw_result = raw_result or RawResult(
            url="https://example.com/article",
            html="<html><body>Hello</body></html>",
        )
        self.error = error
        self.urls: list[str] = []

    async def convert_url_to_markdown(self, url: str) -> ConversionResult:
        self.urls.append(url)
        if self.error is not None:
            raise self.error
        return self.result

    async def fetch_raw_html(self, url: str) -> RawResult:
        self.urls.append(url)
        if self.error is not None:
            raise self.error
        return self.raw_result


def build_request(path: str = "/v1/convert") -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "path": path,
            "headers": [],
        }
    )


def decode_body(response) -> dict[str, str]:
    return json.loads(response.body.decode("utf-8"))


def test_convert_route_success() -> None:
    service = FakeService()
    payload = ConvertRequest(url="https://example.com/article")

    response = asyncio.run(convert_url(payload=payload, _auth=None, service=service))

    assert response == ConvertResponse(
        url="https://example.com/article",
        markdown="# Example",
    )
    assert service.urls == ["https://example.com/article"]


def test_application_error_handler_maps_invalid_url() -> None:
    handler = app.exception_handlers[ApplicationError]
    response = asyncio.run(handler(build_request(), InvalidUrlError()))

    assert response.status_code == 400
    assert decode_body(response) == {"detail": "Invalid URL"}


def test_application_error_handler_maps_fetch_timeout() -> None:
    handler = app.exception_handlers[ApplicationError]
    response = asyncio.run(handler(build_request(), FetchTimeoutError()))

    assert response.status_code == 504
    assert decode_body(response) == {"detail": "Fetching webpage timed out"}


def test_application_error_handler_maps_conversion_failure() -> None:
    handler = app.exception_handlers[ApplicationError]
    response = asyncio.run(handler(build_request(), ConversionError()))

    assert response.status_code == 502
    assert decode_body(response) == {"detail": "Failed to fetch or convert the webpage"}


def test_validation_error_handler_returns_422() -> None:
    handler = app.exception_handlers[RequestValidationError]
    error = RequestValidationError(
        [
            {
                "type": "url_parsing",
                "loc": ("body", "url"),
                "msg": "Input should be a valid URL",
                "input": "not-a-url",
            }
        ]
    )
    response = asyncio.run(handler(build_request(), error))

    assert response.status_code == 422
    assert decode_body(response) == {"detail": "Request body validation failed"}


def test_raw_route_success() -> None:
    service = FakeService()
    payload = ConvertRequest(url="https://example.com/article")

    response = asyncio.run(raw_url(payload=payload, _auth=None, service=service))

    assert response == RawResponse(
        url="https://example.com/article",
        html="<html><body>Hello</body></html>",
    )
    assert service.urls == ["https://example.com/article"]
