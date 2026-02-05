"""File filtering for repository analysis."""

import fnmatch
from dataclasses import dataclass, field
from pathlib import PurePosixPath

# Default patterns to always exclude
DEFAULT_EXCLUDES = [
    # Version control
    ".git/**",
    ".svn/**",
    ".hg/**",
    # Dependencies
    "node_modules/**",
    "vendor/**",
    "venv/**",
    ".venv/**",
    "env/**",
    "__pycache__/**",
    "*.pyc",
    ".tox/**",
    ".nox/**",
    # Build outputs
    "dist/**",
    "build/**",
    "out/**",
    "target/**",
    "*.egg-info/**",
    # IDE/Editor
    ".idea/**",
    ".vscode/**",
    "*.swp",
    "*.swo",
    # OS files
    ".DS_Store",
    "Thumbs.db",
    # Lock files (usually not useful for docs)
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Pipfile.lock",
    "poetry.lock",
    "Cargo.lock",
    # Binaries and media
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
    "*.svg",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.eot",
    "*.mp3",
    "*.mp4",
    "*.wav",
    "*.pdf",
    "*.zip",
    "*.tar",
    "*.gz",
    "*.exe",
    "*.dll",
    "*.so",
    "*.dylib",
    # Test fixtures/snapshots (often large, not useful for docs)
    "**/__snapshots__/**",
    "**/fixtures/**/*.json",
]

# File extensions we can meaningfully process
TEXT_EXTENSIONS = {
    # Programming languages
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".java",
    ".kt",
    ".scala",
    ".go",
    ".rs",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".rb",
    ".php",
    ".swift",
    ".m",
    ".mm",
    ".r",
    ".R",
    ".jl",
    ".lua",
    ".pl",
    ".pm",
    ".ex",
    ".exs",
    ".erl",
    ".hrl",
    ".clj",
    ".cljs",
    ".hs",
    ".elm",
    ".f90",
    ".f95",
    ".f03",
    ".v",
    ".sv",
    ".vhd",
    ".zig",
    ".nim",
    ".d",
    ".dart",
    ".groovy",
    ".gradle",
    # Web
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".vue",
    ".svelte",
    ".astro",
    # Config
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".xml",
    ".plist",
    ".env.example",
    # Documentation
    ".md",
    ".mdx",
    ".rst",
    ".txt",
    ".adoc",
    # Shell/Scripts
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".ps1",
    ".bat",
    ".cmd",
    # Data
    ".sql",
    ".graphql",
    ".gql",
    ".prisma",
    # Other
    ".dockerfile",
    ".containerfile",
    ".tf",
    ".hcl",
    "Makefile",
    "Dockerfile",
    "Containerfile",
    "Justfile",
    "CMakeLists.txt",
    "Rakefile",
    "Gemfile",
    "Brewfile",
}


@dataclass
class FileFilter:
    """Configurable file filter for repository analysis.

    Combines default excludes with user-provided patterns.
    """

    exclude_patterns: list[str] = field(default_factory=list)
    include_patterns: list[str] = field(default_factory=list)
    max_file_size_bytes: int = 1024 * 1024  # 1MB default
    use_default_excludes: bool = True

    def __post_init__(self) -> None:
        if self.use_default_excludes:
            self.exclude_patterns = DEFAULT_EXCLUDES + self.exclude_patterns

    def should_include(self, path: str, size: int = 0) -> bool:
        """Check if a file should be included in analysis.

        Args:
            path: File path relative to repo root
            size: File size in bytes

        Returns:
            True if file should be included
        """
        # Check size limit
        if size > self.max_file_size_bytes:
            return False

        # Check if it's a text file we can process
        path_obj = PurePosixPath(path)
        if path_obj.suffix.lower() not in TEXT_EXTENSIONS and path_obj.name not in {
            "Makefile",
            "Dockerfile",
            "Containerfile",
            "Justfile",
            "Rakefile",
            "Gemfile",
            "Brewfile",
        }:
            return False

        # Check include patterns first (if specified, only include matching)
        if self.include_patterns and not any(
            self._match(path, pattern) for pattern in self.include_patterns
        ):
            return False

        # Check exclude patterns
        return not any(self._match(path, pattern) for pattern in self.exclude_patterns)

    def _match(self, path: str, pattern: str) -> bool:
        """Check if path matches a glob pattern."""
        # Handle ** for recursive matching
        if "**" in pattern:
            # Convert ** to work with fnmatch
            # e.g., "node_modules/**" matches "node_modules/foo/bar.js"
            parts = pattern.split("**")
            if len(parts) == 2:
                prefix, suffix = parts
                if path.startswith(prefix.rstrip("/")):
                    remaining = path[len(prefix.rstrip("/")) :]
                    if not suffix or fnmatch.fnmatch(remaining, "*" + suffix):
                        return True
            return False
        else:
            return fnmatch.fnmatch(path, pattern)


@dataclass
class FilteredFile:
    """A file that passed filtering."""

    path: str
    size: int
    extension: str


def filter_tree(
    tree: list[dict],
    filter_config: FileFilter | None = None,
) -> list[FilteredFile]:
    """Filter a GitHub tree to files we want to analyze.

    Args:
        tree: GitHub tree entries (from get_tree API)
        filter_config: Filter configuration

    Returns:
        List of FilteredFile objects
    """
    file_filter = filter_config or FileFilter()
    result = []

    for entry in tree:
        # Only process files (blobs), not directories (trees)
        if entry.get("type") != "blob":
            continue

        path = entry.get("path", "")
        size = entry.get("size", 0)

        if file_filter.should_include(path, size):
            ext = PurePosixPath(path).suffix.lower()
            result.append(FilteredFile(path=path, size=size, extension=ext))

    return result
