"""Target audience inference from project context."""

import re
from dataclasses import dataclass
from enum import Enum

import logfire

from josephus.analyzer.repo import AnalyzedFile, RepoAnalysis


class AudienceType(Enum):
    """Target audience types for documentation."""

    DEVELOPERS = "developers"  # Technical: libraries, APIs, SDKs, CLI tools
    END_USERS = "end_users"  # Non-technical: applications, GUIs
    MIXED = "mixed"  # Both technical and non-technical users


@dataclass
class AudienceInference:
    """Result of audience inference."""

    audience: AudienceType
    confidence: float  # 0.0 to 1.0
    signals: list[str]  # Reasons for the inference
    tone_guidance: str  # Specific guidance for documentation tone

    def to_prompt_context(self) -> str:
        """Convert inference to prompt context string."""
        if self.audience == AudienceType.DEVELOPERS:
            return f"""Target Audience: Technical (Developers)
Confidence: {self.confidence:.0%}
Signals: {", ".join(self.signals)}

Write documentation for developers who will integrate, extend, or build upon this project.
- Use precise technical terminology
- Include code examples and API references
- Document configuration options and parameters
- Explain architectural decisions where relevant
- Assume familiarity with programming concepts"""

        elif self.audience == AudienceType.END_USERS:
            return f"""Target Audience: Non-Technical (End Users)
Confidence: {self.confidence:.0%}
Signals: {", ".join(self.signals)}

Write documentation for end users who want to use the software.
- Use clear, jargon-free language
- Focus on tasks and outcomes, not implementation
- Include step-by-step instructions with screenshots if relevant
- Explain concepts before using them
- Provide troubleshooting guidance"""

        else:  # MIXED
            return f"""Target Audience: Mixed (Developers and End Users)
Confidence: {self.confidence:.0%}
Signals: {", ".join(self.signals)}

Write documentation that serves both developers and end users.
- Start with user-friendly getting started guides
- Include separate technical reference sections
- Layer complexity: simple first, then advanced
- Clearly label sections for different audiences
- Provide both quick-start and detailed configuration docs"""


# Patterns that indicate developer-focused projects
DEVELOPER_SIGNALS = {
    # Package/library indicators
    "pyproject.toml": ("Python package", 0.3),
    "setup.py": ("Python package", 0.3),
    "package.json": ("NPM package", 0.2),
    "Cargo.toml": ("Rust crate", 0.3),
    "go.mod": ("Go module", 0.3),
    "*.gemspec": ("Ruby gem", 0.3),
    "pom.xml": ("Java/Maven library", 0.3),
    "build.gradle": ("Java/Gradle library", 0.2),
    # CLI indicators
    "cli.py": ("CLI application", 0.4),
    "cli.ts": ("CLI application", 0.4),
    "cli.js": ("CLI application", 0.4),
    "__main__.py": ("CLI entry point", 0.3),
    # API indicators
    "openapi.yaml": ("OpenAPI spec", 0.5),
    "openapi.json": ("OpenAPI spec", 0.5),
    "swagger.yaml": ("Swagger spec", 0.5),
    "swagger.json": ("Swagger spec", 0.5),
    # SDK/library structure
    "src/lib/": ("Library structure", 0.3),
    "lib/": ("Library structure", 0.2),
    "sdk/": ("SDK structure", 0.4),
    "api/": ("API structure", 0.3),
}

# Content patterns in files
DEVELOPER_CONTENT_PATTERNS = [
    (r"(?i)^#.*\bapi\b.*reference", "API reference in docs", 0.4),
    (r"(?i)^#.*\bsdk\b", "SDK documentation", 0.4),
    (r"(?i)^#.*\blibrary\b", "Library documentation", 0.3),
    (r"(?i)^#.*\bcli\b", "CLI documentation", 0.4),
    (r"(?i)^#.*\binstallation\b.*\bpip\b", "pip installation", 0.3),
    (r"(?i)^#.*\binstallation\b.*\bnpm\b", "npm installation", 0.3),
    (r"(?i)^#.*\binstallation\b.*\bcargo\b", "cargo installation", 0.3),
    (r"(?i)\bimport\b.*\bfrom\b", "Import statements in docs", 0.2),
    (r"(?i)```(?:python|javascript|typescript|rust|go)", "Code blocks", 0.2),
    (r"(?i)\bexport\s+(?:default\s+)?(?:function|class|const)", "JS exports", 0.2),
]

# Patterns that indicate end-user focused projects
END_USER_SIGNALS = {
    # GUI/Desktop app indicators
    "electron.js": ("Electron app", 0.4),
    "electron-builder.json": ("Electron app", 0.4),
    "tauri.conf.json": ("Tauri app", 0.4),
    "*.desktop": ("Desktop application", 0.3),
    "Info.plist": ("macOS application", 0.3),
    # Web app indicators (user-facing)
    "pages/": ("Web pages", 0.2),
    "app/": ("Application structure", 0.1),
    "public/": ("Public assets", 0.1),
    "static/": ("Static assets", 0.1),
}

END_USER_CONTENT_PATTERNS = [
    (r"(?i)^#.*\buser\s+guide\b", "User guide", 0.4),
    (r"(?i)^#.*\btutorial\b", "Tutorial", 0.3),
    (r"(?i)^#.*\bgetting\s+started\b", "Getting started guide", 0.2),
    (r"(?i)\bclick\b.*\bbutton\b", "UI instructions", 0.3),
    (r"(?i)\bdownload\b.*\binstaller\b", "Installer download", 0.4),
    (r"(?i)\bscreenshot\b", "Screenshots mentioned", 0.2),
]


def infer_audience(
    analysis: RepoAnalysis,
    guidelines: str = "",
) -> AudienceInference:
    """Infer target audience from repository analysis.

    Args:
        analysis: Repository analysis result
        guidelines: User's documentation guidelines (checked first)

    Returns:
        AudienceInference with audience type and reasoning
    """
    signals: list[str] = []
    dev_score = 0.0
    user_score = 0.0

    # First, check if guidelines explicitly specify audience
    explicit = _check_explicit_audience(guidelines)
    if explicit:
        logfire.info(
            "Audience explicitly specified in guidelines",
            audience=explicit.audience.value,
        )
        return explicit

    # Analyze file structure
    file_paths = [f.path for f in analysis.files]
    dev_score, user_score, signals = _analyze_file_structure(
        file_paths, dev_score, user_score, signals
    )

    # Analyze file contents (especially README)
    dev_score, user_score, signals = _analyze_file_contents(
        analysis.files, dev_score, user_score, signals
    )

    # Analyze repository metadata
    dev_score, user_score, signals = _analyze_repo_metadata(
        analysis, dev_score, user_score, signals
    )

    # Determine audience based on scores
    total_score = dev_score + user_score
    if total_score == 0:
        # Default to developers for code repositories
        audience = AudienceType.DEVELOPERS
        confidence = 0.5
        signals.append("Default: code repository assumed developer-focused")
    elif dev_score > user_score * 1.5:
        audience = AudienceType.DEVELOPERS
        confidence = min(dev_score / (total_score + 0.5), 0.95)
    elif user_score > dev_score * 1.5:
        audience = AudienceType.END_USERS
        confidence = min(user_score / (total_score + 0.5), 0.95)
    else:
        audience = AudienceType.MIXED
        confidence = 0.6

    # Generate tone guidance
    tone_guidance = _generate_tone_guidance(audience, signals)

    result = AudienceInference(
        audience=audience,
        confidence=confidence,
        signals=signals[:5],  # Keep top 5 signals
        tone_guidance=tone_guidance,
    )

    logfire.info(
        "Audience inferred",
        audience=audience.value,
        confidence=confidence,
        signals=signals[:5],
    )

    return result


def _check_explicit_audience(guidelines: str) -> AudienceInference | None:
    """Check if guidelines explicitly specify audience."""
    if not guidelines:
        return None

    guidelines_lower = guidelines.lower()

    # Check for explicit end-user audience FIRST (more specific patterns)
    # This must come before developer patterns to avoid "non-technical" matching "technical"
    user_patterns = [
        r"\bfor\s+(?:end\s+)?users\b",
        r"\bnon-technical\s+audience\b",
        r"\buser\s+documentation\b",
        r"\bfor\s+beginners\b",
    ]
    for pattern in user_patterns:
        if re.search(pattern, guidelines_lower):
            return AudienceInference(
                audience=AudienceType.END_USERS,
                confidence=1.0,
                signals=["Explicitly specified in guidelines"],
                tone_guidance="Write for end users as specified in guidelines.",
            )

    # Check for explicit developer/technical audience
    dev_patterns = [
        r"\bfor\s+developers\b",
        r"(?<!non-)\btechnical\s+audience\b",  # Negative lookbehind to exclude "non-technical"
        r"\bdeveloper\s+documentation\b",
        r"\bapi\s+documentation\b",
        r"\blibrary\s+documentation\b",
    ]
    for pattern in dev_patterns:
        if re.search(pattern, guidelines_lower):
            return AudienceInference(
                audience=AudienceType.DEVELOPERS,
                confidence=1.0,
                signals=["Explicitly specified in guidelines"],
                tone_guidance="Write for developers as specified in guidelines.",
            )

    return None


def _analyze_file_structure(
    file_paths: list[str],
    dev_score: float,
    user_score: float,
    signals: list[str],
) -> tuple[float, float, list[str]]:
    """Analyze file structure for audience signals."""
    for path in file_paths:
        path_lower = path.lower()
        filename = path_lower.split("/")[-1]

        # Check developer signals
        for pattern, (signal, weight) in DEVELOPER_SIGNALS.items():
            if pattern.startswith("*"):
                # Glob pattern
                if filename.endswith(pattern[1:]):
                    dev_score += weight
                    if signal not in signals:
                        signals.append(signal)
            elif pattern.endswith("/"):
                # Directory pattern
                if pattern[:-1] in path_lower:
                    dev_score += weight
                    if signal not in signals:
                        signals.append(signal)
            else:
                # Exact filename
                if filename == pattern:
                    dev_score += weight
                    if signal not in signals:
                        signals.append(signal)

        # Check end-user signals
        for pattern, (signal, weight) in END_USER_SIGNALS.items():
            if pattern.startswith("*"):
                if filename.endswith(pattern[1:]):
                    user_score += weight
                    if signal not in signals:
                        signals.append(signal)
            elif pattern.endswith("/"):
                if pattern[:-1] in path_lower:
                    user_score += weight
                    if signal not in signals:
                        signals.append(signal)
            else:
                if filename == pattern:
                    user_score += weight
                    if signal not in signals:
                        signals.append(signal)

    return dev_score, user_score, signals


def _analyze_file_contents(
    files: list[AnalyzedFile],
    dev_score: float,
    user_score: float,
    signals: list[str],
) -> tuple[float, float, list[str]]:
    """Analyze file contents for audience signals."""
    # Focus on README and documentation files
    doc_files = [
        f for f in files if f.path.lower().startswith("readme") or f.extension in {".md", ".rst"}
    ]

    for file in doc_files[:3]:  # Check first 3 doc files
        content = file.content

        # Check developer patterns
        for pattern, signal, weight in DEVELOPER_CONTENT_PATTERNS:
            if re.search(pattern, content, re.MULTILINE):
                dev_score += weight
                if signal not in signals:
                    signals.append(signal)

        # Check end-user patterns
        for pattern, signal, weight in END_USER_CONTENT_PATTERNS:
            if re.search(pattern, content, re.MULTILINE):
                user_score += weight
                if signal not in signals:
                    signals.append(signal)

    return dev_score, user_score, signals


def _analyze_repo_metadata(
    analysis: RepoAnalysis,
    dev_score: float,
    user_score: float,
    signals: list[str],
) -> tuple[float, float, list[str]]:
    """Analyze repository metadata for audience signals."""
    repo = analysis.repository

    # Check description for signals
    if repo.description:
        desc_lower = repo.description.lower()

        # Developer-focused keywords
        dev_keywords = ["library", "sdk", "api", "framework", "cli", "tool for developers"]
        for keyword in dev_keywords:
            if keyword in desc_lower:
                dev_score += 0.3
                signals.append(f"Description mentions '{keyword}'")
                break

        # User-focused keywords
        user_keywords = ["app", "application", "desktop", "gui", "user-friendly"]
        for keyword in user_keywords:
            if keyword in desc_lower:
                user_score += 0.3
                signals.append(f"Description mentions '{keyword}'")
                break

    return dev_score, user_score, signals


def _generate_tone_guidance(audience: AudienceType, signals: list[str]) -> str:
    """Generate specific tone guidance based on audience and signals."""
    if audience == AudienceType.DEVELOPERS:
        # Check for specific developer types
        if any("CLI" in s for s in signals):
            return "Focus on command-line usage, flags, and configuration options."
        if any("API" in s for s in signals):
            return "Emphasize API endpoints, request/response formats, and authentication."
        if any("library" in s.lower() for s in signals):
            return "Document public API, installation, and integration examples."
        return "Write technical documentation with code examples and configuration details."

    elif audience == AudienceType.END_USERS:
        if any("Desktop" in s or "Electron" in s for s in signals):
            return "Focus on installation, basic usage, and common tasks."
        return "Write user-friendly guides with clear instructions and visual aids."

    else:
        return "Provide both quick-start guides and detailed technical reference."
