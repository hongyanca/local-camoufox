import logging
from io import BytesIO
from time import perf_counter

from markitdown import MarkItDown

from app.utils.exceptions import ConversionError

logger = logging.getLogger(__name__)


class MarkItDownClient:
    def __init__(self) -> None:
        self._converter = MarkItDown(enable_plugins=False)

    def html_to_markdown(self, html: str, *, source_url: str | None = None) -> str:
        if not html.strip():
            logger.warning("Refusing to convert empty HTML source url=%s", source_url)
            raise ConversionError()

        started = perf_counter()
        try:
            result = self._converter.convert_stream(
                BytesIO(html.encode("utf-8")),
                file_extension=".html",
                url=source_url,
            )
        except Exception as exc:
            logger.warning("MarkItDown failed for url=%s error=%s", source_url, exc)
            raise ConversionError() from exc

        markdown = result.markdown.strip()
        if not markdown:
            logger.warning("MarkItDown returned empty Markdown for url=%s", source_url)
            raise ConversionError()

        logger.info(
            "Converted HTML to Markdown for url=%s duration_seconds=%.3f",
            source_url,
            perf_counter() - started,
        )
        return markdown
