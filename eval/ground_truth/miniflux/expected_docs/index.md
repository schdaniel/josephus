# Miniflux

Miniflux is a minimalist and opinionated feed reader written in Go. It's designed to be simple, fast, and self-hosted.

## Key Features

- **Minimalist Design**: Clean, distraction-free reading experience
- **Fast**: Single binary, optimized for performance
- **Self-Hosted**: Run on your own server
- **Multiple APIs**: REST v1, Fever, and Google Reader compatible
- **Keyboard Navigation**: Full keyboard support
- **Content Scraping**: Fetch original article content
- **OPML Import/Export**: Migrate feeds easily

## Quick Start

### Installation

```bash
# Using Docker
docker run -d \
  -p 8080:8080 \
  -e DATABASE_URL="postgres://user:pass@host/miniflux?sslmode=disable" \
  -e RUN_MIGRATIONS=1 \
  -e CREATE_ADMIN=1 \
  -e ADMIN_USERNAME=admin \
  -e ADMIN_PASSWORD=secret \
  miniflux/miniflux:latest

# Or download binary from releases
./miniflux -migrate
./miniflux -create-admin
./miniflux
```

### Configuration

Key environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `LISTEN_ADDR` | Server address | `127.0.0.1:8080` |
| `BASE_URL` | Public URL | `http://localhost` |
| `POLLING_FREQUENCY` | Feed refresh interval | `60` minutes |
| `BATCH_SIZE` | Feeds per refresh cycle | `100` |

## CLI Commands

```bash
# Database operations
miniflux -migrate              # Run migrations
miniflux -create-admin         # Create admin user
miniflux -reset-password       # Reset user password

# Maintenance
miniflux -refresh-feeds        # Refresh all feeds
miniflux -flush-sessions       # Clear sessions
miniflux -run-cleanup-tasks    # Clean old entries

# Utilities
miniflux -config-dump          # Show configuration
miniflux -healthcheck <url>    # Health check
miniflux -export-user-feeds    # Export OPML
```

## API

Miniflux provides three compatible APIs:

### REST API v1

```bash
# Get feeds
curl -H "X-Auth-Token: your-api-key" \
  https://miniflux.example.com/v1/feeds

# Create feed
curl -X POST -H "X-Auth-Token: your-api-key" \
  -d '{"feed_url": "https://example.com/feed.xml", "category_id": 1}' \
  https://miniflux.example.com/v1/feeds
```

### Fever API

Compatible with Fever API clients. Enable in user settings.

### Google Reader API

Compatible with Google Reader API clients. Enable in user settings.

## Documentation

- [API Reference](api.md) - REST API v1 documentation
- [Configuration](configuration.md) - All environment variables
- [CLI Reference](cli.md) - Command line options
- [Deployment](deployment.md) - Production setup guide
