"""Secret scanning to prevent credentials from being sent to LLM."""

import re
from dataclasses import dataclass, field
from enum import Enum


class SecretType(Enum):
    """Types of secrets that can be detected."""

    AWS_ACCESS_KEY = "AWS Access Key"
    AWS_SECRET_KEY = "AWS Secret Key"
    GITHUB_TOKEN = "GitHub Token"
    GITHUB_APP_KEY = "GitHub App Private Key"
    OPENAI_API_KEY = "OpenAI API Key"
    ANTHROPIC_API_KEY = "Anthropic API Key"
    SLACK_TOKEN = "Slack Token"
    SLACK_WEBHOOK = "Slack Webhook URL"
    STRIPE_API_KEY = "Stripe API Key"
    TWILIO_API_KEY = "Twilio API Key"
    SENDGRID_API_KEY = "SendGrid API Key"
    DATABASE_URL = "Database Connection String"
    GENERIC_API_KEY = "Generic API Key"
    GENERIC_SECRET = "Generic Secret/Password"
    PRIVATE_KEY = "Private Key"
    JWT_TOKEN = "JWT Token"
    BASIC_AUTH = "Basic Auth Credentials"


@dataclass
class SecretMatch:
    """A detected secret in a file."""

    file_path: str
    line_number: int
    secret_type: SecretType
    matched_text: str  # Redacted version of matched text
    context: str  # Surrounding context (also redacted)


@dataclass
class ScanResult:
    """Result of scanning files for secrets."""

    has_secrets: bool
    matches: list[SecretMatch] = field(default_factory=list)
    files_scanned: int = 0
    error: str | None = None

    def get_summary(self) -> str:
        """Get a human-readable summary of findings."""
        if not self.has_secrets:
            return f"No secrets found in {self.files_scanned} files."

        summary_lines = [
            f"Found {len(self.matches)} potential secret(s) in {self.files_scanned} files:",
            "",
        ]

        # Group by file
        by_file: dict[str, list[SecretMatch]] = {}
        for match in self.matches:
            if match.file_path not in by_file:
                by_file[match.file_path] = []
            by_file[match.file_path].append(match)

        for file_path, matches in by_file.items():
            summary_lines.append(f"  {file_path}:")
            for match in matches:
                summary_lines.append(f"    - Line {match.line_number}: {match.secret_type.value}")

        return "\n".join(summary_lines)


# Secret detection patterns
# Each pattern is a tuple of (SecretType, regex pattern, description)
SECRET_PATTERNS: list[tuple[SecretType, re.Pattern[str]]] = [
    # AWS
    (SecretType.AWS_ACCESS_KEY, re.compile(r"AKIA[0-9A-Z]{16}")),
    (
        SecretType.AWS_SECRET_KEY,
        re.compile(
            r"(?i)aws[_\-]?secret[_\-]?access[_\-]?key[\s]*[=:]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?"
        ),
    ),
    # GitHub
    (SecretType.GITHUB_TOKEN, re.compile(r"ghp_[A-Za-z0-9]{36}")),
    (SecretType.GITHUB_TOKEN, re.compile(r"gho_[A-Za-z0-9]{36}")),
    (SecretType.GITHUB_TOKEN, re.compile(r"ghu_[A-Za-z0-9]{36}")),
    (SecretType.GITHUB_TOKEN, re.compile(r"ghs_[A-Za-z0-9]{36}")),
    (SecretType.GITHUB_TOKEN, re.compile(r"ghr_[A-Za-z0-9]{36}")),
    (SecretType.GITHUB_APP_KEY, re.compile(r"-----BEGIN RSA PRIVATE KEY-----")),
    # OpenAI
    (SecretType.OPENAI_API_KEY, re.compile(r"sk-[A-Za-z0-9]{48}")),
    (SecretType.OPENAI_API_KEY, re.compile(r"sk-proj-[A-Za-z0-9\-_]{48,}")),
    # Anthropic
    (SecretType.ANTHROPIC_API_KEY, re.compile(r"sk-ant-[A-Za-z0-9\-_]{80,}")),
    # Slack
    (SecretType.SLACK_TOKEN, re.compile(r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}")),
    (
        SecretType.SLACK_WEBHOOK,
        re.compile(r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+"),
    ),
    # Stripe
    (SecretType.STRIPE_API_KEY, re.compile(r"sk_live_[A-Za-z0-9]{24,}")),
    (SecretType.STRIPE_API_KEY, re.compile(r"sk_test_[A-Za-z0-9]{24,}")),
    (SecretType.STRIPE_API_KEY, re.compile(r"rk_live_[A-Za-z0-9]{24,}")),
    (SecretType.STRIPE_API_KEY, re.compile(r"rk_test_[A-Za-z0-9]{24,}")),
    # Twilio
    (SecretType.TWILIO_API_KEY, re.compile(r"SK[a-f0-9]{32}")),
    # SendGrid
    (SecretType.SENDGRID_API_KEY, re.compile(r"SG\.[A-Za-z0-9\-_]{22}\.[A-Za-z0-9\-_]{43}")),
    # Database URLs
    (
        SecretType.DATABASE_URL,
        re.compile(r"(?i)(postgres|postgresql|mysql|mongodb|redis)://[^:\s]+:[^@\s]+@[^\s]+"),
    ),
    # Private keys
    (SecretType.PRIVATE_KEY, re.compile(r"-----BEGIN (EC |DSA |OPENSSH )?PRIVATE KEY-----")),
    (SecretType.PRIVATE_KEY, re.compile(r"-----BEGIN PGP PRIVATE KEY BLOCK-----")),
    # JWT
    (SecretType.JWT_TOKEN, re.compile(r"eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+")),
    # Basic Auth in URLs
    (SecretType.BASIC_AUTH, re.compile(r"https?://[^:\s]+:[^@\s]+@[^\s]+")),
    # Generic patterns (less specific, check last)
    (
        SecretType.GENERIC_API_KEY,
        re.compile(r"(?i)(api[_\-]?key|apikey)[\s]*[=:]\s*['\"]?([A-Za-z0-9\-_]{20,})['\"]?"),
    ),
    (
        SecretType.GENERIC_SECRET,
        re.compile(r"(?i)(secret|password|passwd|pwd)[\s]*[=:]\s*['\"]?([^\s'\"]{8,})['\"]?"),
    ),
]

# Files to skip when scanning
SKIP_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".zip",
    ".tar",
    ".gz",
    ".rar",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".pyc",
    ".pyo",
    ".class",
    ".lock",
    ".sum",
}

SKIP_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Cargo.lock",
    "poetry.lock",
    "go.sum",
}


def _redact_secret(text: str, secret_start: int, secret_end: int) -> str:
    """Redact a secret in text, showing only first and last 2 chars."""
    secret = text[secret_start:secret_end]
    if len(secret) <= 8:
        redacted = "*" * len(secret)
    else:
        redacted = secret[:2] + "*" * (len(secret) - 4) + secret[-2:]
    return text[:secret_start] + redacted + text[secret_end:]


def _should_skip_file(file_path: str) -> bool:
    """Check if a file should be skipped during scanning."""
    # Check file extension
    for ext in SKIP_EXTENSIONS:
        if file_path.lower().endswith(ext):
            return True

    # Check specific files
    file_name = file_path.split("/")[-1]
    return file_name in SKIP_FILES


def scan_content(content: str, file_path: str) -> list[SecretMatch]:
    """Scan file content for secrets.

    Args:
        content: File content to scan.
        file_path: Path to the file (for reporting).

    Returns:
        List of SecretMatch objects for any secrets found.
    """
    if _should_skip_file(file_path):
        return []

    matches: list[SecretMatch] = []
    lines = content.split("\n")

    for line_num, line in enumerate(lines, start=1):
        # Skip lines that look like they're in tests or examples
        if any(marker in line.lower() for marker in ["# example", "// example", "test_", "_test"]):
            continue

        for secret_type, pattern in SECRET_PATTERNS:
            for match in pattern.finditer(line):
                # Redact the matched text
                redacted_line = _redact_secret(line, match.start(), match.end())

                matches.append(
                    SecretMatch(
                        file_path=file_path,
                        line_number=line_num,
                        secret_type=secret_type,
                        matched_text=redacted_line.strip(),
                        context=redacted_line.strip()[:100],
                    )
                )

    return matches


def scan_files(files: dict[str, str]) -> ScanResult:
    """Scan multiple files for secrets.

    Args:
        files: Dictionary mapping file paths to file contents.

    Returns:
        ScanResult with all findings.
    """
    all_matches: list[SecretMatch] = []
    files_scanned = 0

    for file_path, content in files.items():
        if _should_skip_file(file_path):
            continue

        files_scanned += 1
        matches = scan_content(content, file_path)
        all_matches.extend(matches)

    return ScanResult(
        has_secrets=len(all_matches) > 0,
        matches=all_matches,
        files_scanned=files_scanned,
    )


class SecretFoundError(Exception):
    """Raised when secrets are found in repository files."""

    def __init__(self, scan_result: ScanResult) -> None:
        self.scan_result = scan_result
        super().__init__(scan_result.get_summary())
