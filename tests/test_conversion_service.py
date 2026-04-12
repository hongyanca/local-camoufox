import asyncio

import pytest

from app.config import Settings
from app.services.conversion_service import (
    ConversionResult,
    ConversionService,
    _filter_lines,
    _find_trim_rule,
    _trim_markdown,
    _strip_styles_and_scripts,
)
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


def test_convert_url_to_markdown_applies_reuters_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_allow(url: str, *, allow_private_ips: bool) -> None:
        return None

    monkeypatch.setattr(
        "app.services.conversion_service.ensure_url_target_allowed",
        fake_allow,
    )

    markdown = (
        "HEADER JUNK\n"
        "My News Sections my-news\n"
        "Article title\n"
        "Article body paragraph\n"
        "Our Standards The Thomson Reuters trust-principles\n"
        "Footer junk\n"
    )
    fetcher = FakeFetcher("<html><body>reuters</body></html>")
    converter = FakeConverter(markdown)
    service = ConversionService(
        settings=build_settings(),
        fetcher=fetcher,
        converter=converter,
    )

    result = asyncio.run(service.convert_url_to_markdown("https://www.reuters.com/article/some-story"))

    assert "HEADER JUNK" not in result.markdown
    assert "Footer junk" not in result.markdown
    assert "My News Sections my-news" not in result.markdown
    assert "Our Standards" not in result.markdown
    assert "Article title" in result.markdown
    assert "Article body paragraph" in result.markdown


def test_convert_url_to_markdown_skips_filter_for_non_reuters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_allow(url: str, *, allow_private_ips: bool) -> None:
        return None

    monkeypatch.setattr(
        "app.services.conversion_service.ensure_url_target_allowed",
        fake_allow,
    )

    markdown = "My News sections my-news\nArticle\nOur Standards trust-principles\n"
    fetcher = FakeFetcher("<html><body>other</body></html>")
    converter = FakeConverter(markdown)
    service = ConversionService(
        settings=build_settings(),
        fetcher=fetcher,
        converter=converter,
    )

    result = asyncio.run(service.convert_url_to_markdown("https://example.com/article"))

    assert result.markdown == markdown


def test_filter_reuters_removes_above_header_and_below_footer() -> None:
    rule = _find_trim_rule("https://www.reuters.com/article")
    assert rule is not None
    markdown = (
        "line above 1\n"
        "line above 2\n"
        "My News sections my-news\n"
        "content line 1\n"
        "content line 2\n"
        "Our Standards The Thomson Reuters trust-principles\n"
        "footer line 1\n"
        "footer line 2\n"
    )
    result = _trim_markdown(markdown, rule.header_trim_re, rule.footer_trim_re)

    assert "line above" not in result
    assert "footer line" not in result
    assert "My News" not in result
    assert "Our Standards" not in result
    assert "content line 1" in result
    assert "content line 2" in result


def test_filter_reuters_returns_full_content_when_no_markers() -> None:
    rule = _find_trim_rule("https://www.reuters.com/article")
    assert rule is not None
    markdown = "line 1\nline 2\nline 3\n"
    result = _trim_markdown(markdown, rule.header_trim_re, rule.footer_trim_re)
    assert result == markdown


def test_filter_reuters_handles_header_only() -> None:
    rule = _find_trim_rule("https://www.reuters.com/article")
    assert rule is not None
    markdown = "junk\nMy News blah my-news\ncontent line\n"
    result = _trim_markdown(markdown, rule.header_trim_re, rule.footer_trim_re)
    assert result == "content line\n"


def test_filter_reuters_handles_footer_only() -> None:
    rule = _find_trim_rule("https://www.reuters.com/article")
    assert rule is not None
    markdown = "content line\nOur Standards trust-principles\nfooter junk\n"
    result = _trim_markdown(markdown, rule.header_trim_re, rule.footer_trim_re)
    assert result == "content line"


def test_filter_lines_removes_advertise_lines() -> None:
    markdown = "keep this\nAdvertise with us\nand this\nadvertise here\ndone\n"
    result = _filter_lines(markdown)
    assert result == "keep this\nand this\ndone\n"


def test_filter_lines_removes_markdown_link_only_lines() -> None:
    markdown = "keep\n[Click here](https://example.com)\nalso keep\n[Text](url)\n"
    result = _filter_lines(markdown)
    assert result == "keep\nalso keep\n"


def test_filter_lines_removes_bullet_markdown_link_lines() -> None:
    markdown = "keep\n* [Link text](https://example.com)\nalso keep\n*  [Another](url)\n: [Colon link](url)\n"
    result = _filter_lines(markdown)
    assert result == "keep\nalso keep\n"


def test_filter_lines_removes_image_link_lines() -> None:
    markdown = "keep\n![alt text](image.png)\nalso keep\n  ![desc](photo.jpg)  \n"
    result = _filter_lines(markdown)
    assert result == "keep\nalso keep\n"


def test_filter_lines_preserves_non_matching() -> None:
    markdown = "hello\nworld\n"
    result = _filter_lines(markdown)
    assert result == markdown


def test_convert_url_to_markdown_applies_line_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_allow(url: str, *, allow_private_ips: bool) -> None:
        return None

    monkeypatch.setattr(
        "app.services.conversion_service.ensure_url_target_allowed",
        fake_allow,
    )

    markdown = "Advertise with us\ngood content\nadvertise here\n"
    fetcher = FakeFetcher("<html><body>x</body></html>")
    converter = FakeConverter(markdown)
    service = ConversionService(
        settings=build_settings(),
        fetcher=fetcher,
        converter=converter,
    )

    result = asyncio.run(service.convert_url_to_markdown("https://example.com/article"))
    assert result.markdown == "good content\n"


def test_convert_url_to_markdown_strips_leading_empty_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_allow(url: str, *, allow_private_ips: bool) -> None:
        return None

    monkeypatch.setattr(
        "app.services.conversion_service.ensure_url_target_allowed",
        fake_allow,
    )

    markdown = "\n\n\n\nactual content\n"
    fetcher = FakeFetcher("<html><body>x</body></html>")
    converter = FakeConverter(markdown)
    service = ConversionService(
        settings=build_settings(),
        fetcher=fetcher,
        converter=converter,
    )

    result = asyncio.run(service.convert_url_to_markdown("https://example.com/article"))
    assert result.markdown == "actual content\n"


def test_filter_firstpost_removes_above_header_and_below_footer() -> None:
    rule = _find_trim_rule("https://www.firstpost.com/article")
    assert rule is not None
    markdown = "nav junk\nTrending Stories\narticle title\narticle body\nApril 13, 2026, 00:53:21 (IST)\nfooter junk\n"
    result = _trim_markdown(markdown, rule.header_trim_re, rule.footer_trim_re)
    assert "nav junk" not in result
    assert "footer junk" not in result
    assert "Trending" not in result
    assert "April 13" not in result
    assert "article title" in result
    assert "article body" in result


def test_convert_url_to_markdown_applies_firstpost_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_allow(url: str, *, allow_private_ips: bool) -> None:
        return None

    monkeypatch.setattr(
        "app.services.conversion_service.ensure_url_target_allowed",
        fake_allow,
    )

    markdown = "HEADER\nTrending Now\ncontent\nMarch 5, 2025, 12:00:00 (IST)\nFOOTER\n"
    fetcher = FakeFetcher("<html><body>x</body></html>")
    converter = FakeConverter(markdown)
    service = ConversionService(
        settings=build_settings(),
        fetcher=fetcher,
        converter=converter,
    )

    result = asyncio.run(service.convert_url_to_markdown("https://www.firstpost.com/some-article"))
    assert "HEADER" not in result.markdown
    assert "FOOTER" not in result.markdown
    assert "content" in result.markdown


def test_filter_cbsnews_removes_above_header_and_below_footer() -> None:
    rule = _find_trim_rule("https://www.cbsnews.com/news/article")
    assert rule is not None

    md_updated = "nav junk\nUpdated on: April 12, 2026\nheadline\nbody text\nNew Updates\nfooter junk\n"
    result = _trim_markdown(md_updated, rule.header_trim_re, rule.footer_trim_re)
    assert "nav junk" not in result
    assert "footer junk" not in result
    assert "Updated on" not in result
    assert "New Updates" not in result
    assert "headline" in result
    assert "body text" in result

    md_month_only = "nav junk\nApril 12, 2026\nheadline\nbody text\nNew Updates\nfooter junk\n"
    result2 = _trim_markdown(md_month_only, rule.header_trim_re, rule.footer_trim_re)
    assert "nav junk" not in result2
    assert "April 12" not in result2
    assert "headline" in result2


def test_convert_url_to_markdown_applies_cbsnews_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_allow(url: str, *, allow_private_ips: bool) -> None:
        return None

    monkeypatch.setattr(
        "app.services.conversion_service.ensure_url_target_allowed",
        fake_allow,
    )

    markdown = "HEADER\nUpdated on: March 5, 2025\ncontent\nNew Updates\nFOOTER\n"
    fetcher = FakeFetcher("<html><body>x</body></html>")
    converter = FakeConverter(markdown)
    service = ConversionService(
        settings=build_settings(),
        fetcher=fetcher,
        converter=converter,
    )

    result = asyncio.run(service.convert_url_to_markdown("https://www.cbsnews.com/news/some-story"))
    assert "HEADER" not in result.markdown
    assert "FOOTER" not in result.markdown
    assert "content" in result.markdown


def test_filter_pbsorg_removes_above_header_and_below_footer() -> None:
    rule = _find_trim_rule("https://www.pbs.org/newshour/article")
    assert rule is not None
    markdown = (
        "nav junk\n"
        "Click to Turn on desktop notifications\n"
        "headline\n"
        "body text\n"
        "Support PBS: A free press is a cornerstone of a healthy democracy\n"
        "footer junk\n"
    )
    result = _trim_markdown(markdown, rule.header_trim_re, rule.footer_trim_re)
    assert "nav junk" not in result
    assert "footer junk" not in result
    assert "desktop notifications" not in result
    assert "free press" not in result
    assert "headline" in result
    assert "body text" in result


def test_convert_url_to_markdown_applies_pbsorg_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_allow(url: str, *, allow_private_ips: bool) -> None:
        return None

    monkeypatch.setattr(
        "app.services.conversion_service.ensure_url_target_allowed",
        fake_allow,
    )

    markdown = (
        "HEADER\nTurn on desktop notifications for breaking news\ncontent\n"
        "A free press is a cornerstone of a healthy democracy and society\nFOOTER\n"
    )
    fetcher = FakeFetcher("<html><body>x</body></html>")
    converter = FakeConverter(markdown)
    service = ConversionService(
        settings=build_settings(),
        fetcher=fetcher,
        converter=converter,
    )

    result = asyncio.run(service.convert_url_to_markdown("https://www.pbs.org/newshour/politics/some-article"))
    assert "HEADER" not in result.markdown
    assert "FOOTER" not in result.markdown
    assert "content" in result.markdown


def test_filter_hindustantimes_removes_above_header_and_below_footer() -> None:
    rule = _find_trim_rule("https://www.hindustantimes.com/india-news/article")
    assert rule is not None

    md_published = (
        "nav junk\nPublished on April 12, 2026\nheadline\nbody\nSubscribe to our best newsletters\nfooter junk\n"
    )
    result = _trim_markdown(md_published, rule.header_trim_re, rule.footer_trim_re)
    assert "nav junk" not in result
    assert "footer junk" not in result
    assert "Published on" not in result
    assert "Subscribe to our best newsletters" not in result
    assert "headline" in result

    md_updated = "nav junk\nUpdated on April 12, 2026\nheadline\nbody\nSubscribe to our best newsletters\nfooter junk\n"
    result2 = _trim_markdown(md_updated, rule.header_trim_re, rule.footer_trim_re)
    assert "Updated on" not in result2
    assert "headline" in result2


def test_convert_url_to_markdown_applies_hindustantimes_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_allow(url: str, *, allow_private_ips: bool) -> None:
        return None

    monkeypatch.setattr(
        "app.services.conversion_service.ensure_url_target_allowed",
        fake_allow,
    )

    markdown = "HEADER\nPublished on March 5, 2025\ncontent\nSubscribe to our best newsletters\nFOOTER\n"
    fetcher = FakeFetcher("<html><body>x</body></html>")
    converter = FakeConverter(markdown)
    service = ConversionService(
        settings=build_settings(),
        fetcher=fetcher,
        converter=converter,
    )

    result = asyncio.run(service.convert_url_to_markdown("https://www.hindustantimes.com/india-news/some-article"))
    assert "HEADER" not in result.markdown
    assert "FOOTER" not in result.markdown
    assert "content" in result.markdown
