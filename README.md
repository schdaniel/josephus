# Josephus

AI-powered documentation generator for GitHub repositories.

## Overview

Josephus automatically generates and maintains customer-facing documentation from your codebase:

- **Initial Generation**: Analyze your repository and generate comprehensive docs
- **PR Updates**: Automatically update documentation when code changes
- **Natural Language Guidelines**: Configure tone, scope, and style in plain English

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run linting
ruff check src tests

# Start development server
uv run uvicorn josephus.api.app:app --reload
```

## License

MIT
