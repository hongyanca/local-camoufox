from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.auth import authenticate_request
from app.models import ConvertRequest, ConvertResponse, ErrorResponse
from app.services.conversion_service import ConversionService, get_conversion_service

router = APIRouter(prefix="/v1", tags=["conversion"])


@router.post(
    "/convert",
    response_model=ConvertResponse,
    status_code=status.HTTP_200_OK,
    summary="Convert a webpage URL into Markdown",
    description=(
        "Authenticates the request, fetches the rendered HTML with Camoufox, "
        "and converts the result to Markdown with MarkItDown."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid URL or blocked target"},
        401: {"model": ErrorResponse, "description": "Missing or invalid API key"},
        422: {"model": ErrorResponse, "description": "Request body validation failed"},
        502: {"model": ErrorResponse, "description": "Failed to fetch or convert the webpage"},
        504: {"model": ErrorResponse, "description": "Fetching webpage timed out"},
    },
)
async def convert_url(
    payload: ConvertRequest,
    _auth: Annotated[None, Depends(authenticate_request)],
    service: Annotated[ConversionService, Depends(get_conversion_service)],
) -> ConvertResponse:
    result = await service.convert_url_to_markdown(str(payload.url))
    return ConvertResponse(url=result.url, markdown=result.markdown)
