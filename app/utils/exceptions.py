from fastapi import status


class ApplicationError(Exception):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "Internal server error"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class InvalidUrlError(ApplicationError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid URL"


class AuthenticationError(ApplicationError):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Invalid or missing API key"


class FetchTimeoutError(ApplicationError):
    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    default_detail = "Fetching webpage timed out"


class FetchFailedError(ApplicationError):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "Failed to fetch or convert the webpage"


class ConversionError(ApplicationError):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "Failed to fetch or convert the webpage"
