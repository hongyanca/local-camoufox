# Implementation Plan: Python REST API Server for URL-to-Markdown Conversion

## 1. Goal

Build a Python REST API server that:

1. Accepts a URL from a client request
2. Fetches the webpage using **Camoufox**
3. Converts the fetched HTML into Markdown using **MarkItDown**
4. Returns the generated Markdown in the API response
5. Secures the endpoint with an **API key**

The server will use **FastAPI** as the web framework.

---

## 2. High-Level Requirements

### Functional Requirements
- Expose a RESTful endpoint that accepts a URL
- Fetch the target webpage content with Camoufox
- Convert fetched HTML to Markdown
- Return Markdown in the response
- Require API key bearer authentication for access

### Non-Functional Requirements
- Simple, maintainable project structure
- Clear validation and error handling
- Basic security protections against abuse
- Testable design
- Easy local development and deployment

---

## 3. Proposed API Design

## 3.1 Endpoint

### `POST /v1/convert`

Converts a webpage URL into Markdown.

### Request Headers
- `Authorization: Bearer <api_key>`

### Request Body
```json
{
  "url": "https://example.com/article"
}
~~~

### Success Response

**HTTP 200**

```json
{
  "url": "https://example.com/article",
  "markdown": "# Example Article\n\nConverted content..."
}
```

### Error Responses

**HTTP 400** – Invalid input

```json
{
  "detail": "Invalid URL"
}
```

**HTTP 401** – Missing or invalid API key

```json
{
  "detail": "Invalid or missing API key"
}
```

**HTTP 422** – Validation error

```json
{
  "detail": "Request body validation failed"
}
```

**HTTP 502** – Upstream fetch/conversion failure

```json
{
  "detail": "Failed to fetch or convert the webpage"
}
```

**HTTP 504** – Timeout

```json
{
  "detail": "Fetching webpage timed out"
}
```

------

## 4. Architecture Overview

The service will be split into clear layers:

1. **API layer**
   - FastAPI routes
   - Request/response models
   - Authentication dependency
2. **Service layer**
   - Orchestrates fetch + convert pipeline
   - Applies validation and business rules
3. **Fetcher layer**
   - Uses Camoufox to load and retrieve webpage HTML
4. **Converter layer**
   - Uses MarkItDown to convert HTML into Markdown
5. **Configuration layer**
   - Reads environment variables
   - Stores API key and operational settings
6. **Testing layer**
   - Unit and integration tests

------

## 5. Proposed Project Structure

```text
app/
  main.py
  config.py
  auth.py
  models.py
  routers/
    convert.py
  services/
    conversion_service.py
  clients/
    camoufox_client.py
    markitdown_client.py
  utils/
    validators.py
    exceptions.py
tests/
  test_auth.py
  test_convert_endpoint.py
  test_conversion_service.py
requirements.txt
.env.example
README.md
```

------

## 6. Detailed Implementation Plan

## Phase 1: Project Bootstrap

### Tasks

- Create Python project
- Create virtual environment
- Install dependencies
- Set up FastAPI app skeleton
- Add `.env` configuration support

### Dependencies

Suggested packages:

- `fastapi`
- `uvicorn`
- `pydantic`
- `python-dotenv`
- `camoufox`
- `markitdown`
- `httpx` or test tooling as needed
- `pytest`
- `pytest-asyncio` if async tests are needed

### Deliverables

- Working FastAPI starter app
- Configuration loading from environment

------

## Phase 2: Configuration and Authentication

## 6.2.1 Config Settings

Use environment variables for configuration:

- `API_KEY`
- `REQUEST_TIMEOUT_SECONDS`
- `MAX_URL_LENGTH`
- `ALLOW_PRIVATE_IPS` (default false)
- `LOG_LEVEL`

### Example `.env`

```env
API_KEY=replace-with-strong-secret
REQUEST_TIMEOUT_SECONDS=30
MAX_URL_LENGTH=2048
ALLOW_PRIVATE_IPS=false
LOG_LEVEL=INFO
```

## 6.2.2 Authentication Design

Use bearer authentication:

- `Authorization: Bearer <API_KEY>`

### FastAPI auth flow

- Create a dependency that reads the header
- Compare against configured `API_KEY`
- Reject with `401 Unauthorized` if invalid or missing

### Deliverables

- Reusable authentication dependency
- Protected route(s)

------

## Phase 3: Request Validation

### Input model

Create a Pydantic request model:

```python
class ConvertRequest(BaseModel):
    url: AnyHttpUrl
```

### Additional validation rules

- Only allow `http` and `https`
- Reject overly long URLs
- Optionally reject localhost/private/internal network targets
- Normalize URL before processing

### Deliverables

- Request schema
- Validation helper utilities

------

## Phase 4: Webpage Fetching with Camoufox

## 6.4.1 Responsibility

Build a dedicated fetch client that:

- Accepts a URL
- Uses Camoufox to load the page
- Waits for page rendering if needed
- Extracts final HTML content

## 6.4.2 Design Notes

The fetcher should:

- Run with a configurable timeout
- Support dynamic pages
- Cleanly handle browser startup/shutdown
- Return raw HTML string

## 6.4.3 Fetcher Interface

Example service contract:

```python
class CamoufoxClient:
    async def fetch_html(self, url: str) -> str:
        ...
```

### Error cases to handle

- Browser launch failure
- Navigation timeout
- Redirect loops
- Blocked pages / bot challenges
- Empty HTML response

### Deliverables

- `camoufox_client.py`
- Standardized exceptions for fetch failures

------

## Phase 5: HTML-to-Markdown Conversion with MarkItDown

## 6.5.1 Responsibility

Build a conversion client that:

- Accepts HTML content
- Converts it to Markdown using MarkItDown
- Returns Markdown text

## 6.5.2 Design Notes

Keep MarkItDown use isolated so it can be replaced later if needed.

### Converter Interface

Example contract:

```python
class MarkItDownClient:
    def html_to_markdown(self, html: str) -> str:
        ...
```

### Conversion concerns

- Empty or malformed HTML
- Very large pages
- Preserve useful headings/links/content
- Strip obvious boilerplate if needed in a future enhancement

### Deliverables

- `markitdown_client.py`
- Conversion-specific exception handling

------

## Phase 6: Conversion Service Orchestration

Create a service that coordinates the whole flow:

1. Validate URL
2. Fetch HTML with Camoufox
3. Convert HTML to Markdown with MarkItDown
4. Return structured response

### Service interface

```python
class ConversionService:
    async def convert_url_to_markdown(self, url: str) -> str:
        ...
```

### Deliverables

- `conversion_service.py`
- Central place for business logic and error mapping

------

## Phase 7: FastAPI Route Implementation

## 6.7.1 Route Behavior

Implement:

### `POST /v1/convert`

Flow:

- Authenticate request
- Validate body
- Call conversion service
- Return JSON result

### Example response model

```python
class ConvertResponse(BaseModel):
    url: str
    markdown: str
```

## 6.7.2 OpenAPI Documentation

- Add endpoint summary and description
- Describe auth header
- Document possible response codes

### Deliverables

- `routers/convert.py`
- Route registration in `main.py`

------

## Phase 8: Error Handling Strategy

Create a consistent error model.

### Internal exception categories

- `InvalidUrlError`
- `AuthenticationError`
- `FetchTimeoutError`
- `FetchFailedError`
- `ConversionError`

### Mapping to HTTP

- Invalid request -> `400`
- Unauthorized -> `401`
- Fetch timeout -> `504`
- Fetch/conversion failure -> `502`
- Unexpected internal issue -> `500`

### Deliverables

- Exception classes
- FastAPI exception handlers

------

## Phase 9: Security Considerations

This service accepts arbitrary URLs, so security is important.

## 6.9.1 SSRF Protection

Prevent server-side request forgery risks:

- Reject localhost URLs
- Reject private IP ranges by default
- Reject link-local and loopback addresses
- Resolve DNS carefully if implementing stronger checks
- Consider allowlist mode for stricter deployments

## 6.9.2 API Key Security

- Do not hardcode API key
- Read from environment
- Avoid logging the API key
- Use constant-time compare if practical

## 6.9.3 Abuse Prevention

Future or optional:

- Rate limiting
- Request size limits
- Timeout enforcement
- Concurrency limits
- Logging and monitoring

## 6.9.4 Content Safety

The service should treat all webpage content as untrusted input.

### Deliverables

- URL/network validation policy
- Secure defaults in config

------

## Phase 10: Observability and Logging

Add structured logging around:

- Incoming request metadata
- URL processing lifecycle
- Fetch duration
- Conversion duration
- Error category

### Do not log

- API keys
- Full sensitive headers

### Deliverables

- Basic app logging configuration
- Useful operational logs

------

## Phase 11: Testing Plan

## 6.11.1 Unit Tests

Test:

- API key validation
- URL validation
- Error mapping
- Conversion service orchestration

## 6.11.2 Integration Tests

Test:

- `POST /v1/convert` with valid key and mocked services
- Unauthorized requests
- Invalid URLs
- Fetch timeout and conversion failure cases

## 6.11.3 Optional End-to-End Tests

Run against a known public test page and verify:

- HTML fetch succeeds
- Markdown output is returned

### Deliverables

- Pytest suite
- Mocked dependencies for stable tests

------

## Phase 12: Deployment Plan

## 6.12.1 Local Development

Run with Uvicorn:

```bash
uvicorn app.main:app --reload
```

## 6.12.2 Production

Possible options:

- Docker container
- Reverse proxy in front (Nginx/Caddy)
- Process manager or orchestrator

## 6.12.3 Deployment Requirements

- Environment variables injected securely
- Camoufox runtime dependencies available
- Health check endpoint

### Optional endpoint

```
GET /health
{
  "status": "ok"
}
```

### Deliverables

- `Dockerfile`
- `.env.example`
- Deployment notes in README

------

## 7. Suggested Implementation Order

### Milestone 1

- Bootstrap project
- Add config
- Add API key auth
- Add health endpoint

### Milestone 2

- Implement request/response models
- Implement URL validation
- Implement `POST /v1/convert` stub

### Milestone 3

- Implement Camoufox HTML fetcher
- Implement MarkItDown converter
- Wire service together

### Milestone 4

- Add structured errors
- Add tests
- Add logging

### Milestone 5

- Harden security
- Add Docker support
- Finalize README and examples

------

## 8. Example Request Flow

1. Client sends `POST /v1/convert`
2. Server validates the key in `Authorization: Bearer API_KEY`
3. Server validates URL
4. Camoufox loads webpage and returns HTML
5. MarkItDown converts HTML to Markdown
6. API returns Markdown in JSON response

------

## 9. Example cURL Usage

```bash
curl -X POST "http://localhost:8000/v1/convert" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer API_KEY" \
  -d '{
    "url": "https://example.com"
  }'
```

------

## 10. Example Minimal Response Contract

```json
{
  "url": "https://example.com",
  "markdown": "# Example Domain\n\nThis domain is for use in illustrative examples..."
}
```

------

## 11. Future Enhancements

Possible additions after the initial version:

- Return raw HTML optionally
- Support async job processing for long pages
- Rate limiting per API key
- API key rotation / multiple keys
- Allow custom fetch options
- Metadata extraction (title, final URL, status code)
- Content cleanup rules before conversion
- Response streaming for large outputs

------

## 12. Risks and Mitigations

### Risk: Dynamic pages may load slowly

**Mitigation:** configurable timeout and clear timeout errors

### Risk: Some pages block browser automation

**Mitigation:** graceful failure and logging

### Risk: SSRF exposure

**Mitigation:** block private/internal targets by default

### Risk: Large HTML documents

**Mitigation:** response size limits and timeout controls

### Risk: Dependency interface changes

**Mitigation:** isolate Camoufox and MarkItDown behind thin wrapper classes

------

## 13. Definition of Done

The implementation is complete when:

- FastAPI server runs locally
- `POST /v1/convert` accepts a URL and returns Markdown
- Endpoint requires valid `API_KEY`
- HTML is fetched via Camoufox
- HTML is converted via MarkItDown
- Errors are handled consistently
- Basic tests pass
- README documents setup and usage

------

## 14. Summary

This implementation will produce a clean, secure first version of a URL-to-Markdown API with:

- **FastAPI** for REST serving
- **Camoufox** for webpage fetching
- **MarkItDown** for HTML-to-Markdown conversion
- **API key authentication** for access control

The recommended design emphasizes separation of concerns, security defaults, and straightforward extensibility.

```

```
