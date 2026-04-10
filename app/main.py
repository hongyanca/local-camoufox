import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.models import HealthResponse
from app.routers.convert import router as convert_router
from app.utils.exceptions import ApplicationError

logger = logging.getLogger(__name__)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Camoufox Markdown API",
        version="0.1.0",
        description=(
            "Protected URL-to-Markdown API that fetches rendered webpages with "
            "Camoufox and converts them with MarkItDown."
        ),
        openapi_tags=[
            {
                "name": "conversion",
                "description": "Protected URL conversion endpoints.",
            },
            {"name": "health", "description": "Simple health check endpoints."},
        ],
    )
    app.include_router(convert_router)

    @app.get("/health", response_model=HealthResponse, tags=["health"], summary="Health check")
    async def health_check() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.exception_handler(ApplicationError)
    async def handle_application_error(
        request: Request, exc: ApplicationError
    ) -> JSONResponse:
        log = logger.warning if exc.status_code < 500 else logger.error
        log(
            "Request failed with status=%s method=%s path=%s detail=%s",
            exc.status_code,
            request.method,
            request.url.path,
            exc.detail,
        )
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning(
            "Request validation failed for method=%s path=%s errors=%s",
            request.method,
            request.url.path,
            exc.errors(),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": "Request body validation failed"},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled error for method=%s path=%s",
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    return app


app = create_app()
