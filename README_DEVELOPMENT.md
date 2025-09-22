# Auto WordPress Post Generator

AI-powered WordPress article generator and publisher using Perplexity API.

## Features

- **AI Article Generation**: Generate ~10,000 character articles using Perplexity API
- **WordPress Integration**: Automatic publishing with draft/publish/schedule modes
- **Preview System**: Safe HTML preview before publishing
- **Character Control**: Automatic adjustment to target 9,000-11,000 characters
- **Idempotency**: Prevent duplicate generation with same input
- **Async Processing**: Non-blocking article generation with Celery workers

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Perplexity API key
- WordPress site with Application Password

### Setup

1. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your API keys and credentials
```

2. **Start services:**
```bash
make setup
```

3. **API available at:** http://localhost:8080/docs

## Development Commands

```bash
make up            # Start services
make down          # Stop services
make logs          # View logs
make shell         # API container shell
make migrate       # Run migrations
make test          # Run tests
```