# local-camoufox

`local-camoufox` is a FastAPI service that accepts a URL, fetches the rendered page with Camoufox, converts the HTML to Markdown with MarkItDown, and returns the Markdown behind an API key.

By default the service runs Camoufox with `headless="virtual"`, which uses a virtual display instead of standard headless mode.

## Requirements

- Python 3.13+
- Camoufox runtime dependencies available on the host
- `xvfb` installed when running on Linux outside Docker

## Configuration

Copy `.env.example` to `.env` and set a real API key.

```env
API_KEY=replace-with-strong-secret
REQUEST_TIMEOUT_SECONDS=30
MAX_URL_LENGTH=2048
ALLOW_PRIVATE_IPS=false
LOG_LEVEL=INFO
CAMOUFOX_HEADLESS=virtual
CAMOUFOX_WAIT_UNTIL=networkidle
CAMOUFOX_POST_LOAD_WAIT_MS=0
```

## Run locally

```bash
uv run uvicorn app.main:app --reload
```

You can also run:

```bash
uv run python main.py
```

## API

### `GET /health`

Returns:

```json
{
  "status": "ok"
}
```

### `POST /v1/convert`

Headers:

- `Authorization: Bearer <api_key>`

Request:

```json
{
  "url": "https://example.com/article"
}
```

Response:

```json
{
  "url": "https://example.com/article",
  "markdown": "# Example Article\n\nConverted content..."
}
```

Example:

```bash
curl -X POST "http://localhost:8000/v1/convert" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer replace-with-strong-secret" \
  -d '{
    "url": "https://example.com"
  }'
```

## Security notes

- The API rejects missing or invalid bearer tokens.
- Only `http` and `https` URLs are accepted.
- Localhost, loopback, link-local, and private/internal IP targets are blocked by default.
- DNS resolution is checked before fetches unless `ALLOW_PRIVATE_IPS=true`.

## Tests

```bash
uv run pytest
```

## Docker

Build:

```bash
docker build -t local-camoufox:latest .
```

Run:

```bash
docker run --rm -p 8000:8000 --env-file .env local-camoufox:latest
```

Test the running container:

```bash
curl -X POST "http://localhost:8000/v1/convert" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer replace-with-strong-secret" \
  -d '{
    "url": "https://www.example.com"
  }'
```

The Docker image prefetches Camoufox browser assets during build. If your deployment environment needs additional browser libraries, install them in the image or base image you use.

The container image installs `xvfb`, and the default env configuration uses `CAMOUFOX_HEADLESS=virtual`.
