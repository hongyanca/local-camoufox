import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

from bs4 import BeautifulSoup, Doctype
from fastapi import Depends

from app.clients.camoufox_client import CamoufoxClient
from app.clients.markitdown_client import MarkItDownClient
from app.config import Settings, get_settings
from app.utils.validators import ensure_url_target_allowed, normalize_url

logger = logging.getLogger(__name__)


class HTMLFetcher(Protocol):
    async def fetch_html(self, url: str) -> str: ...


class MarkdownConverter(Protocol):
    def html_to_markdown(self, html: str, *, source_url: str | None = None) -> str: ...


@dataclass(frozen=True)
class ConversionResult:
    url: str
    markdown: str


@dataclass(frozen=True)
class RawResult:
    url: str
    html: str


class ConversionService:
    def __init__(
        self,
        *,
        settings: Settings,
        fetcher: HTMLFetcher,
        converter: MarkdownConverter,
    ) -> None:
        self.settings = settings
        self.fetcher = fetcher
        self.converter = converter

    async def convert_url_to_markdown(self, url: str) -> ConversionResult:
        started = perf_counter()
        normalized_url = normalize_url(url, self.settings.max_url_length)

        logger.info("Starting conversion for url=%s", normalized_url)
        await ensure_url_target_allowed(normalized_url, allow_private_ips=self.settings.allow_private_ips)

        html = await self.fetcher.fetch_html(normalized_url)
        markdown = self.converter.html_to_markdown(
            html,
            source_url=normalized_url,
        )

        logger.info(
            "Completed conversion for url=%s duration_seconds=%.3f",
            normalized_url,
            perf_counter() - started,
        )
        return ConversionResult(url=normalized_url, markdown=markdown)

    async def fetch_raw_html(self, url: str) -> RawResult:
        started = perf_counter()
        normalized_url = normalize_url(url, self.settings.max_url_length)

        logger.info("Starting raw fetch for url=%s", normalized_url)
        await ensure_url_target_allowed(normalized_url, allow_private_ips=self.settings.allow_private_ips)

        html = await self.fetcher.fetch_html(normalized_url)
        cleaned = _strip_styles_and_scripts(html)
        if normalized_url.startswith("https://news.google.com"):
            cleaned = cleaned.replace('href="./read', 'href="https://news.google.com/read')

        logger.info(
            "Completed raw fetch for url=%s duration_seconds=%.3f",
            normalized_url,
            perf_counter() - started,
        )
        return RawResult(url=normalized_url, html=cleaned)


def _strip_styles_and_scripts(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["style", "script", "link", "noscript", "meta"]):
        tag.decompose()
    for tag in soup.find_all(True, attrs={"style": True}):
        del tag["style"]
    for item in list(soup.contents):
        if isinstance(item, Doctype):
            item.extract()
    return str(soup)


def get_conversion_service(
    settings: Settings = Depends(get_settings),
) -> ConversionService:
    fetcher = CamoufoxClient(
        timeout_seconds=settings.request_timeout_seconds,
        headless=settings.camoufox_headless,
        wait_until=settings.camoufox_wait_until,
        post_load_wait_ms=settings.camoufox_post_load_wait_ms,
    )
    converter = MarkItDownClient()
    return ConversionService(settings=settings, fetcher=fetcher, converter=converter)
