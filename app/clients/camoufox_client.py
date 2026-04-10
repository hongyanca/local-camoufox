import logging
from time import perf_counter
from typing import Literal

from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.utils.exceptions import FetchFailedError, FetchTimeoutError

logger = logging.getLogger(__name__)


class CamoufoxClient:
    def __init__(
        self,
        *,
        timeout_seconds: float,
        headless: bool | Literal["virtual"] = "virtual",
        wait_until: str = "networkidle",
        post_load_wait_ms: int = 0,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.headless = headless
        self.wait_until = wait_until
        self.post_load_wait_ms = post_load_wait_ms

    async def fetch_html(self, url: str) -> str:
        timeout_ms = int(self.timeout_seconds * 1000)
        started = perf_counter()

        try:
            async with AsyncCamoufox(headless=self.headless) as browser:
                page = await browser.new_page()
                page.set_default_navigation_timeout(timeout_ms)
                page.set_default_timeout(timeout_ms)

                await page.goto(url, wait_until=self.wait_until, timeout=timeout_ms)
                if self.post_load_wait_ms:
                    await page.wait_for_timeout(self.post_load_wait_ms)

                html = await page.content()
                await page.close()
        except PlaywrightTimeoutError as exc:
            logger.warning(
                "Camoufox timed out fetching url=%s duration_seconds=%.3f",
                url,
                perf_counter() - started,
            )
            raise FetchTimeoutError() from exc
        except PlaywrightError as exc:
            logger.warning("Camoufox failed for url=%s error=%s", url, exc)
            raise FetchFailedError() from exc
        except Exception as exc:
            logger.exception("Unexpected Camoufox failure for url=%s", url)
            raise FetchFailedError() from exc

        if not html.strip():
            logger.warning("Camoufox returned empty HTML for url=%s", url)
            raise FetchFailedError()

        logger.info(
            "Fetched HTML with Camoufox for url=%s duration_seconds=%.3f",
            url,
            perf_counter() - started,
        )
        return html
