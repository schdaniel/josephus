# Taiga

Taiga is an open-source project management platform for agile developers and designers. It provides comprehensive tools for managing projects using Scrum or Kanban methodologies.

## Key Features

- **Agile Project Management**: Scrum and Kanban boards
- **User Stories & Epics**: Track features and requirements
- **Sprint Planning**: Plan and track iterations
- **Issue Tracking**: Bug and improvement management
- **Wiki**: Built-in documentation
- **Webhooks**: Integration with external services
- **Import Tools**: Migrate from Trello, Jira, GitHub, Asana

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/taigaio/taiga-back.git
cd taiga-back

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start server
python manage.py runserver
```

### Configuration

Key settings in `settings/local.py`:

```python
# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'taiga',
        'USER': 'taiga',
        'PASSWORD': 'secret',
        'HOST': 'localhost',
    }
}

# Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.example.com'

# Features
PUBLIC_REGISTER_ENABLED = True
WEBHOOKS_ENABLED = True
```

## REST API

Taiga provides a comprehensive REST API at `/api/v1/`.

### Authentication

```bash
# Get auth token
curl -X POST \
  -d '{"type": "normal", "username": "admin", "password": "secret"}' \
  -H "Content-Type: application/json" \
  https://taiga.example.com/api/v1/auth

# Use token in requests
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://taiga.example.com/api/v1/projects
```

### Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/v1/projects/` | Project management |
| `/api/v1/userstories/` | User stories |
| `/api/v1/tasks/` | Tasks |
| `/api/v1/issues/` | Issues |
| `/api/v1/epics/` | Epics |
| `/api/v1/milestones/` | Sprints/Milestones |
| `/api/v1/wiki/` | Wiki pages |
| `/api/v1/webhooks/` | Webhook management |

## Integrations

### Git Webhooks

Taiga integrates with popular Git platforms:

- GitHub (`/api/v1/github-hook`)
- GitLab (`/api/v1/gitlab-hook`)
- Bitbucket (`/api/v1/bitbucket-hook`)

### Importers

Import projects from:

- Trello
- Jira
- GitHub Issues
- Asana

## Documentation

- [API Reference](api.md) - Complete API documentation
- [Authentication](authentication.md) - Auth flows and tokens
- [Webhooks](webhooks.md) - Event subscriptions
- [Integrations](integrations.md) - Git and external tools
