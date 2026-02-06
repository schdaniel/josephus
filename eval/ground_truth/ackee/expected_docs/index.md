# Ackee

Ackee is a self-hosted, Node.js based analytics tool for privacy-conscious users. It provides visitor tracking without cookies and runs on your own server.

## Key Features

- **Privacy-First**: No cookies, GDPR compliant by design
- **Self-Hosted**: Complete control over your data
- **GraphQL API**: Modern API for all operations
- **Real-Time Stats**: Live visitor tracking
- **Event Tracking**: Track custom actions and events
- **Multiple Domains**: Track multiple websites from one instance

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/electerious/Ackee.git
cd Ackee

# Install dependencies
npm install

# Start with environment variables
ACKEE_MONGODB=mongodb://localhost/ackee \
ACKEE_USERNAME=admin \
ACKEE_PASSWORD=secret \
npm start
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ACKEE_MONGODB` | Yes | MongoDB connection string |
| `ACKEE_USERNAME` | No | Dashboard username |
| `ACKEE_PASSWORD` | No | Dashboard password |
| `ACKEE_PORT` | No | Server port (default: 3000) |
| `ACKEE_ALLOW_ORIGIN` | No | CORS allowed origins |

## Tracking Script

Add the tracking script to your website:

```html
<script async src="https://your-ackee.com/tracker.js"
        data-ackee-server="https://your-ackee.com"
        data-ackee-domain-id="your-domain-id">
</script>
```

## GraphQL API

Ackee uses GraphQL for all data operations. Access the API at `/api`.

### Authentication

```graphql
mutation {
  createToken(input: { username: "admin", password: "secret" }) {
    payload { id }
  }
}
```

### Key Operations

- **Domains**: Create and manage tracked websites
- **Records**: Page view tracking
- **Events**: Custom event tracking
- **Statistics**: View analytics data

## Documentation

- [API Reference](api.md) - Complete GraphQL API documentation
- [Configuration](configuration.md) - Environment variables and setup
- [Tracking](tracking.md) - How to integrate the tracker
- [Events](events.md) - Custom event tracking
