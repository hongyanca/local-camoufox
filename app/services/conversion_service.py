import logging
import re
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

        trim_rule = _find_trim_rule(normalized_url)
        if trim_rule is not None:
            markdown = _trim_markdown(markdown, trim_rule.header_trim_re, trim_rule.footer_trim_re)

        markdown = _filter_lines(markdown)
        markdown = markdown.lstrip("\n")

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


@dataclass(frozen=True)
class SiteTrimRule:
    url_pattern: str
    header_trim_re: re.Pattern[str]
    footer_trim_re: re.Pattern[str]


_SITE_TRIM_RULES: list[SiteTrimRule] = [
    SiteTrimRule(
        url_pattern="reuters.com",
        header_trim_re=re.compile(r"My News.*?my-news", re.IGNORECASE | re.DOTALL),
        footer_trim_re=re.compile(r"Our Standards.*?trust-principles", re.IGNORECASE | re.DOTALL),
    ),
    SiteTrimRule(
        url_pattern="firstpost.com",
        header_trim_re=re.compile(r"^Trending"),
        footer_trim_re=re.compile(
            r"^(?:January|February|March|April|May|June|July|August|September|October|November|December).+T\)"
        ),
    ),
    SiteTrimRule(
        url_pattern="cbsnews.com",
        header_trim_re=re.compile(
            r"^(?:Updated on:\s+)?(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+"
        ),
        footer_trim_re=re.compile(r"^New Updates$"),
    ),
    SiteTrimRule(
        url_pattern="pbs.org",
        header_trim_re=re.compile(r"Turn on desktop notifications"),
        footer_trim_re=re.compile(r"A free press is a cornerstone of a healthy democracy"),
    ),
    SiteTrimRule(
        url_pattern="hindustantimes.com",
        header_trim_re=re.compile(r"^(?:Published|Updated) on"),
        footer_trim_re=re.compile(r"Subscribe to our best newsletters"),
    ),
]


def _find_trim_rule(url: str) -> SiteTrimRule | None:
    for rule in _SITE_TRIM_RULES:
        if rule.url_pattern in url:
            return rule
    return None


def _trim_markdown(
    markdown: str,
    header_re: re.Pattern[str],
    footer_re: re.Pattern[str],
) -> str:
    lines = markdown.split("\n")
    header_idx = None
    for i, line in enumerate(lines):
        if header_re.search(line):
            header_idx = i
            break

    footer_idx = None
    search_start = (header_idx + 1) if header_idx is not None else 0
    for i in range(search_start, len(lines)):
        if footer_re.search(lines[i]):
            footer_idx = i
            break

    if header_idx is not None and footer_idx is not None:
        return "\n".join(lines[header_idx + 1 : footer_idx])
    if header_idx is not None:
        return "\n".join(lines[header_idx + 1 :])
    if footer_idx is not None:
        return "\n".join(lines[:footer_idx])
    return markdown


_LINE_FILTER_RES: list[re.Pattern[str]] = [
    re.compile(r"^[Aa]dvertise.*"),
    re.compile(r"^\[[^\]]+\]\(.+\)$"),
    re.compile(r"^[*:]\s+\[[^\]]+\]\(.+?\)$"),
    re.compile(r"^\s*!\[[^\]]*\]\(.+?\)\s*$"),
]


def _filter_lines(markdown: str) -> str:
    return "\n".join(line for line in markdown.split("\n") if not any(pat.search(line) for pat in _LINE_FILTER_RES))


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
