import asyncio

import pytest

from app.config import Settings
from app.services.conversion_service import ConversionResult, ConversionService, _strip_styles_and_scripts
from app.utils.exceptions import FetchTimeoutError, InvalidUrlError
from app.utils.validators import ensure_url_target_allowed, normalize_url


class FakeFetcher:
    def __init__(self, html: str) -> None:
        self.html = html
        self.urls: list[str] = []

    async def fetch_html(self, url: str) -> str:
        self.urls.append(url)
        return self.html


class TimeoutFetcher:
    async def fetch_html(self, url: str) -> str:
        raise FetchTimeoutError()


class FakeConverter:
    def __init__(self, markdown: str) -> None:
        self.markdown = markdown
        self.calls: list[tuple[str, str | None]] = []

    def html_to_markdown(self, html: str, *, source_url: str | None = None) -> str:
        self.calls.append((html, source_url))
        return self.markdown


def build_settings() -> Settings:
    return Settings(
        api_key="test-api-key",
        request_timeout_seconds=30,
        max_url_length=2048,
        allow_private_ips=False,
        log_level="INFO",
        camoufox_headless="virtual",
        camoufox_wait_until="networkidle",
        camoufox_post_load_wait_ms=0,
    )


def test_normalize_url_strips_fragments() -> None:
    assert (
        normalize_url(" https://example.com/article?x=1#details ", max_url_length=2048)
        == "https://example.com/article?x=1"
    )


def test_normalize_url_rejects_credentials() -> None:
    with pytest.raises(InvalidUrlError):
        normalize_url("https://user:pass@example.com/private", max_url_length=2048)


def test_ensure_url_target_allowed_rejects_private_ip() -> None:
    with pytest.raises(InvalidUrlError):
        asyncio.run(
            ensure_url_target_allowed(
                "http://127.0.0.1/internal",
                allow_private_ips=False,
            )
        )


def test_conversion_service_orchestrates_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validated: list[tuple[str, bool]] = []

    async def fake_allow(url: str, *, allow_private_ips: bool) -> None:
        validated.append((url, allow_private_ips))

    monkeypatch.setattr(
        "app.services.conversion_service.ensure_url_target_allowed",
        fake_allow,
    )

    fetcher = FakeFetcher("<html><body>Hello</body></html>")
    converter = FakeConverter("# Hello")
    service = ConversionService(
        settings=build_settings(),
        fetcher=fetcher,
        converter=converter,
    )

    result = asyncio.run(service.convert_url_to_markdown("https://example.com/article#fragment"))

    assert result == ConversionResult(
        url="https://example.com/article",
        markdown="# Hello",
    )
    assert validated == [("https://example.com/article", False)]
    assert fetcher.urls == ["https://example.com/article"]
    assert converter.calls == [("<html><body>Hello</body></html>", "https://example.com/article")]


def test_conversion_service_propagates_fetch_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_allow(url: str, *, allow_private_ips: bool) -> None:
        return None

    monkeypatch.setattr(
        "app.services.conversion_service.ensure_url_target_allowed",
        fake_allow,
    )

    service = ConversionService(
        settings=build_settings(),
        fetcher=TimeoutFetcher(),
        converter=FakeConverter("# unused"),
    )

    with pytest.raises(FetchTimeoutError):
        asyncio.run(service.convert_url_to_markdown("https://example.com/article"))


def test_fetch_raw_html_returns_cleaned_html(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_allow(url: str, *, allow_private_ips: bool) -> None:
        return None

    monkeypatch.setattr(
        "app.services.conversion_service.ensure_url_target_allowed",
        fake_allow,
    )

    html = (
        "<!DOCTYPE html>"
        "<html><head>"
        '<meta charset="utf-8">'
        '<link rel="stylesheet" href="style.css">'
        "<style>body{color:red}</style>"
        "<script>alert('hi')</script>"
        "<noscript>Enable JS</noscript>"
        "</head>"
        '<body><div style="display:none">Hello</div></body></html>'
    )
    fetcher = FakeFetcher(html)
    service = ConversionService(
        settings=build_settings(),
        fetcher=fetcher,
        converter=FakeConverter("unused"),
    )

    result = asyncio.run(service.fetch_raw_html("https://example.com/article#fragment"))

    assert result.url == "https://example.com/article"
    assert "<style" not in result.html
    assert "<script" not in result.html
    assert "<link" not in result.html
    assert "<noscript" not in result.html
    assert "<meta" not in result.html
    assert "<!DOCTYPE" not in result.html
    assert "style=" not in result.html
    assert "Hello" in result.html


def test_strip_styles_and_scripts_removes_all_targets() -> None:
    html = (
        "<!DOCTYPE html>"
        "<html><head>"
        '<meta charset="utf-8">'
        '<link rel="stylesheet" href="a.css">'
        "<style>.x{}</style>"
        '<script type="text/javascript">var x=1;</script>'
        "<noscript>no</noscript>"
        "</head>"
        '<body><p style="color:red">text</p></body></html>'
    )
    result = _strip_styles_and_scripts(html)

    assert "<!DOCTYPE" not in result
    assert "<style" not in result
    assert "<script" not in result
    assert "<link" not in result
    assert "<noscript" not in result
    assert "<meta" not in result
    assert "style=" not in result
    assert "<p>text</p>" in result


def test_fetch_raw_html_rewrites_google_news_links(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_allow(url: str, *, allow_private_ips: bool) -> None:
        return None

    monkeypatch.setattr(
        "app.services.conversion_service.ensure_url_target_allowed",
        fake_allow,
    )

    html = (
        "<html><body>"
        '<a href="./read/full/abc123">Article</a>'
        '<a href="./read/full/def456">Other</a>'
        '<a href="/other/path">Keep</a>'
        "</body></html>"
    )
    fetcher = FakeFetcher(html)
    service = ConversionService(
        settings=build_settings(),
        fetcher=fetcher,
        converter=FakeConverter("unused"),
    )

    result = asyncio.run(service.fetch_raw_html("https://news.google.com/articles/example"))

    assert 'href="https://news.google.com/read/full/abc123"' in result.html
    assert 'href="https://news.google.com/read/full/def456"' in result.html
    assert 'href="/other/path"' in result.html


def test_fetch_raw_html_does_not_rewrite_non_google_news(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_allow(url: str, *, allow_private_ips: bool) -> None:
        return None

    monkeypatch.setattr(
        "app.services.conversion_service.ensure_url_target_allowed",
        fake_allow,
    )

    html = '<html><body><a href="./read/full/abc123">Article</a></body></html>'
    fetcher = FakeFetcher(html)
    service = ConversionService(
        settings=build_settings(),
        fetcher=fetcher,
        converter=FakeConverter("unused"),
    )

    result = asyncio.run(service.fetch_raw_html("https://example.com/article"))

    assert 'href="./read/full/abc123"' in result.html
