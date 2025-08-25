# PDFKatana 🗡️

A high-performance, production-ready PDF splitting microservice with intelligent validation and repair capabilities. Built with FastAPI and optimized for paperless-ngx compatibility.

## Features

- **Smart PDF Splitting**: Split PDFs at specified page boundaries with automatic validation
- **Intelligent Error Handling**: Gracefully handles invalid split requests by returning the original PDF
- **PDF Validation & Repair**: Comprehensive validation with automatic repair for compatibility
- **Multiple Output Formats**: 
  - Multipart/mixed response for direct streaming
  - ZIP archive for bundled downloads
- **Production Ready**:
  - Health checks and Prometheus metrics
  - Automatic temp file cleanup
  - Request logging and tracing
  - Docker support with multi-stage builds

## API Endpoints

### Core Endpoints

#### `POST /v1/split`
Splits a PDF into multiple parts based on specified page boundaries.

**Request:**
- `file`: PDF file (multipart/form-data)
- `pages`: JSON string specifying split points

**Response:** 
- Success: `multipart/mixed` stream with PDF parts
- Invalid pages: Original PDF returned unchanged

**Example:**
```bash
curl -X POST http://localhost:8000/v1/split \
  -F "file=@document.pdf" \
  -F 'pages={"pages":[{"page":5},{"page":10}]}'
```

#### `POST /v1/split-into-zip`
Same as `/v1/split` but returns results in a ZIP archive.

**Response:**
- Success: ZIP file containing split PDF parts
- Invalid pages: ZIP file containing original PDF

#### `POST /v1/validate-pdf`
Validates a PDF for structural integrity and paperless-ngx compatibility.

**Response:**
```json
{
  "filename": "document.pdf",
  "is_valid": true,
  "needs_repair": false,
  "repair_successful": null,
  "issues": [],
  "warnings": ["PDF version 1.4 (older version)"],
  "page_count": 10,
  "original_size_mb": 2.5
}
```

### Monitoring Endpoints

- `GET /health` - Health check endpoint
- `GET /metrics` - Prometheus metrics
- `GET /docs` - Interactive API documentation (Swagger UI)

## Intelligent Page Handling

PDFKatana intelligently handles invalid split requests:

| Input | Behavior |
|-------|----------|
| Empty pages array `{"pages": []}` | Returns original PDF |
| Invalid page numbers (0, negative) | Returns original PDF |
| Out-of-range pages | Returns original PDF |
| Malformed JSON | Returns original PDF |
| Valid split points | Performs normal split |

This ensures the service never fails with 500 errors for invalid input, always returning something useful.

## Architecture

```
PDFKatana/
├── src/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── health.py      # Health checks
│   │   │       ├── metrics.py     # Prometheus metrics
│   │   │       └── split.py       # PDF operations
│   │   ├── core/
│   │   │   ├── config.py          # Configuration
│   │   │   ├── splitter.py        # PDF splitting logic
│   │   │   ├── sweeper.py         # Temp file cleanup
│   │   │   └── validator.py       # PDF validation
│   │   ├── schemas/
│   │   │   └── split.py           # Pydantic models
│   │   └── main.py                # FastAPI application
│   └── gunicorn_conf.py           # Production server config
└── tmp/                            # Temporary file storage
```

### Technology Stack

- **Framework**: FastAPI (async Python web framework)
- **PDF Processing**: pikepdf (Python bindings for QPDF)
- **Validation**: Custom validator with paperless-ngx compatibility
- **Server**: Gunicorn with Uvicorn workers
- **Monitoring**: Prometheus metrics
- **Containerization**: Docker with multi-stage builds

## Installation

### Local Development

1. **Clone the repository:**
```bash
git clone https://github.com/yourusername/pdfkatana.git
cd pdfkatana
```

2. **Create virtual environment:**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Run the development server:**
```bash
uvicorn app.main:app --reload --app-dir src --host 0.0.0.0 --port 8000
```

### Docker Deployment

1. **Build the image:**
```bash
docker build -t pdfkatana:latest .
```

2. **Run the container:**
```bash
docker run -d \
  --name pdfkatana \
  -p 8000:8000 \
  -e MAX_UPLOAD_SIZE_MB=50 \
  -e MAX_WORKERS=4 \
  pdfkatana:latest
```

### Docker Compose

```yaml
version: '3.8'

services:
  pdfkatana:
    image: pdfkatana:latest
    container_name: pdfkatana
    ports:
      - "8000:8000"
    environment:
      - MAX_UPLOAD_SIZE_MB=50
      - MAX_WORKERS=4
      - LOG_LEVEL=INFO
    volumes:
      - ./tmp:/app/tmp
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Portainer Stack Configuration

### Simple Deployment (portainer-stack-simple.yml)

```yaml
version: '3.8'

services:
  pdfkatana:
    image: ghcr.io/yourusername/pdfkatana:latest
    container_name: pdfkatana
    ports:
      - "8000:8000"
    environment:
      - MAX_UPLOAD_SIZE_MB=50
      - MAX_WORKERS=2
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Production Deployment with Nginx (portainer-stack-prod.yml)

```yaml
version: '3.8'

services:
  pdfkatana:
    image: ghcr.io/yourusername/pdfkatana:latest
    container_name: pdfkatana-app
    environment:
      - MAX_UPLOAD_SIZE_MB=100
      - MAX_WORKERS=4
      - LOG_LEVEL=INFO
      - TEMP_FILE_MAX_AGE_HOURS=1
    volumes:
      - pdfkatana-tmp:/app/tmp
    networks:
      - pdfkatana-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    container_name: pdfkatana-nginx
    ports:
      - "80:80"
    volumes:
      - ./nginx-prod.conf:/etc/nginx/nginx.conf:ro
    networks:
      - pdfkatana-net
    depends_on:
      - pdfkatana
    restart: unless-stopped

networks:
  pdfkatana-net:
    driver: bridge

volumes:
  pdfkatana-tmp:
    driver: local
```

### Integration with Paperless-ngx (portainer-stack-npm.yml)

```yaml
version: '3.8'

services:
  pdfkatana:
    image: ghcr.io/yourusername/pdfkatana:latest
    container_name: pdfkatana
    environment:
      - MAX_UPLOAD_SIZE_MB=200
      - MAX_WORKERS=4
      - LOG_LEVEL=INFO
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.pdfkatana.rule=Host(`pdf.yourdomain.com`)"
      - "traefik.http.routers.pdfkatana.entrypoints=websecure"
      - "traefik.http.routers.pdfkatana.tls.certresolver=letsencrypt"
      - "traefik.http.services.pdfkatana.loadbalancer.server.port=8000"
    networks:
      - proxy
      - paperless
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  proxy:
    external: true
  paperless:
    external: true
```

## Configuration

Environment variables for configuration:

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_UPLOAD_SIZE_MB` | 50 | Maximum PDF file size in MB |
| `MAX_WORKERS` | 4 | Number of Gunicorn workers |
| `LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `TEMP_FILE_MAX_AGE_HOURS` | 1 | Age before temp files are cleaned |
| `PORT` | 8000 | Port to bind the service |

## API Usage Examples

### Python
```python
import requests

# Split PDF
with open('document.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/v1/split',
        files={'file': f},
        data={'pages': '{"pages":[{"page":5},{"page":10}]}'}
    )
    
    # Handle multipart response
    if response.status_code == 200:
        if 'multipart/mixed' in response.headers['Content-Type']:
            # PDF was split successfully
            # Parse multipart response
            pass
        else:
            # Original PDF returned (invalid pages)
            with open('original.pdf', 'wb') as out:
                out.write(response.content)
```

### JavaScript/Node.js
```javascript
const FormData = require('form-data');
const fs = require('fs');

const form = new FormData();
form.append('file', fs.createReadStream('document.pdf'));
form.append('pages', JSON.stringify({ pages: [{ page: 5 }, { page: 10 }] }));

fetch('http://localhost:8000/v1/split', {
    method: 'POST',
    body: form
})
.then(response => {
    if (response.ok) {
        // Handle response based on Content-Type
        const contentType = response.headers.get('Content-Type');
        if (contentType.includes('multipart/mixed')) {
            // PDF was split
        } else {
            // Original PDF returned
        }
    }
});
```

### cURL
```bash
# Split PDF at pages 5 and 10
curl -X POST http://localhost:8000/v1/split \
  -F "file=@document.pdf" \
  -F 'pages={"pages":[{"page":5},{"page":10}]}' \
  -o output.pdf

# Get split PDFs as ZIP
curl -X POST http://localhost:8000/v1/split-into-zip \
  -F "file=@document.pdf" \
  -F 'pages={"pages":[{"page":5},{"page":10}]}' \
  -o output.zip

# Validate PDF
curl -X POST http://localhost:8000/v1/validate-pdf \
  -F "file=@document.pdf" \
  | jq .
```

## Monitoring & Observability

### Prometheus Metrics

Available at `/metrics`:

- `pdf_split_duration_seconds` - PDF split operation duration
- `pdf_split_pages_total` - Total pages processed
- `pdf_validation_duration_seconds` - Validation duration
- `pdf_validation_errors_total` - Validation errors count

### Health Checks

The `/health` endpoint returns:
```json
{
  "status": "healthy",
  "timestamp": "2025-01-20T10:30:00Z",
  "version": "v1",
  "temp_files": 0
}
```

### Logging

Structured JSON logging with request IDs for tracing:
```json
{
  "timestamp": "2025-01-20T10:30:00",
  "level": "INFO",
  "request_id": "1234567890.123",
  "message": "Split completed, generated 3 parts"
}
```

## Development

### Running Tests
```bash
# Unit tests
pytest tests/

# Integration tests
pytest tests/ -m integration

# Coverage report
pytest --cov=app tests/
```

### Code Quality
```bash
# Format code
black src/

# Lint
ruff check src/

# Type checking
mypy src/
```

## Troubleshooting

### Common Issues

1. **Large PDFs timing out**
   - Increase `MAX_UPLOAD_SIZE_MB`
   - Adjust Nginx/proxy timeouts

2. **Memory issues with many workers**
   - Reduce `MAX_WORKERS`
   - Enable swap on host

3. **Temp files accumulating**
   - Check `TEMP_FILE_MAX_AGE_HOURS`
   - Ensure cleanup cron is running

## Security Considerations

- Input validation on all endpoints
- File size limits enforced
- Automatic temp file cleanup
- No arbitrary code execution
- Sanitized error messages
- Request rate limiting (configure in reverse proxy)

## License

MIT License - See LICENSE file for details

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing documentation
- Review API docs at `/docs`

---

Built with ❤️ for the paperless-ngx community