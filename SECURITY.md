# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**Please report vulnerabilities through GitHub's private vulnerability reporting:**

1. Go to the [Security tab](https://github.com/schdaniel/josephus/security)
2. Click **"Report a vulnerability"**
3. Fill out the form with details

Alternatively, you can [open a private security advisory](https://github.com/schdaniel/josephus/security/advisories/new).

### Guidelines

- **Do NOT** open public issues for security vulnerabilities
- Include steps to reproduce the vulnerability
- Include the potential impact
- If possible, suggest a fix

### Response Timeline

| Action | Timeframe |
|--------|-----------|
| Acknowledgment | Within 48 hours |
| Initial assessment | Within 1 week |
| Critical patches | Within 7 days |
| Other patches | Within 30 days |

## Security Measures

This project implements the following security measures:

### Static Analysis (SAST)
- **Bandit**: Python-specific security linter
- **CodeQL**: Deep dataflow analysis (planned)
- **Semgrep**: OWASP pattern detection (planned)

### Dependency Scanning (SCA)
- **pip-audit**: Checks for known CVEs in Python dependencies
- **Dependabot**: Automated dependency updates

### Secret Detection
- **Gitleaks**: Scans for secrets in git history (planned)
- **GitHub Secret Scanning**: Native GitHub feature

### Runtime Security
- HMAC signature verification for webhooks
- JWT-based GitHub App authentication
- Secret scanning before LLM submission

## Disclosure Policy

We follow coordinated disclosure:

1. Reporter submits vulnerability privately
2. We acknowledge and assess the report
3. We develop and test a fix
4. We release the fix with security advisory
5. Public disclosure after 90 days or when fix is released (whichever is first)

## Security Contacts

For security concerns, use GitHub's private vulnerability reporting (preferred) or contact the maintainers directly through GitHub.
