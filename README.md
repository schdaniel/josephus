# Josephus

AI-powered documentation generator - automatically create and maintain customer-facing docs from code.

## Overview

Josephus transforms code repositories into living, customer-facing documentation. It handles both the initial generation of comprehensive docs and the ongoing maintenance as code evolves through PRs.

### Key Features

- **Customer-facing focus** - Generates user documentation, not internal developer docs
- **Natural language configuration** - Configure tone, scope, and style with plain English
- **PR-aware** - Automatically detects documentation-relevant changes in pull requests
- **CI/CD native** - Integrates seamlessly with GitHub workflows as a GitHub App
- **Platform-agnostic** - Outputs standard markdown; use any docs platform you prefer

## Quick Start

### Prerequisites

- Python 3.11+
- GitHub App credentials (for GitHub integration)
- Anthropic API key (for Claude)

### Installation

```bash
# Clone the repository
git clone https://github.com/schdaniel/josephus.git
cd josephus

# Install dependencies
pip install -e ".[dev]"

# Copy and configure environment
cp .env.example .env
# Edit .env with your credentials
```

### Running the API

```bash
uvicorn josephus.api.app:app --reload
```

## Configuration

Josephus is configured through environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `GITHUB_APP_ID` | GitHub App ID | Yes |
| `GITHUB_APP_PRIVATE_KEY` | GitHub App private key | Yes |
| `GITHUB_WEBHOOK_SECRET` | Webhook signature verification secret | Yes |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude | Yes |
| `DATABASE_URL` | PostgreSQL connection URL | No |
| `REDIS_URL` | Redis connection URL | No |

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Web App    │     │  GitHub App  │     │   CLI Tool   │
│  (Frontend)  │     │  (Webhooks)  │     │  (Optional)  │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       └────────────────────┼────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│                        API Layer                          │
│  - REST API                                               │
│  - GitHub App (auth + webhooks)                           │
└──────────────────────────┬───────────────────────────────┘
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Repo       │    │  Doc Generation  │    │  PR Analysis    │
│  Analyzer   │    │  Engine          │    │  Service        │
└─────────────┘    └──────────────────┘    └─────────────────┘
```

## Development

### Running Tests

```bash
# Unit tests
pytest tests/unit -v

# With coverage
pytest tests/unit --cov=josephus --cov-report=html
```

### Code Quality

```bash
# Linting
ruff check .

# Formatting
ruff format .

# Type checking
mypy .
```

## License

MIT
