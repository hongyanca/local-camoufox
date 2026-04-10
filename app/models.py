from pydantic import AnyHttpUrl, BaseModel, ConfigDict


class ConvertRequest(BaseModel):
    url: AnyHttpUrl

    model_config = ConfigDict(
        json_schema_extra={"example": {"url": "https://example.com/article"}}
    )


class ConvertResponse(BaseModel):
    url: str
    markdown: str


class ErrorResponse(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: str
