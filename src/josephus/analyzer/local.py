"""Local repository analyzer - analyzes repos from local disk."""

from dataclasses import dataclass
from pathlib import Path

import logfire
import tiktoken

from josephus.analyzer.filters import FileFilter, FilteredFile
from josephus.analyzer.repo import AnalyzedFile, RepoAnalysis
from josephus.github import Repository


@dataclass
class LocalRepository:
    """Local repository metadata."""

    path: Path
    name: str
    description: str | None = None
    language: str | None = None

    def to_repository(self) -> Repository:
        """Convert to Repository dataclass for compatibility."""
        return Repository(
            id=0,
            name=self.name,
            full_name=self.name,
            description=self.description,
            default_branch="main",
            language=self.language,
            private=False,
            html_url=f"file://{self.path}",
        )


class LocalRepoAnalyzer:
    """Analyzes a local repository for documentation generation.

    Reads files from local disk and structures them for LLM processing.
    Compatible with the same output format as the GitHub-based RepoAnalyzer.
    """

    def __init__(
        self,
        max_tokens: int = 100_000,
        file_filter: FileFilter | None = None,
    ) -> None:
        """Initialize the analyzer.

        Args:
            max_tokens: Maximum tokens to include in analysis
            file_filter: File filter configuration
        """
        self.max_tokens = max_tokens
        self.file_filter = file_filter or FileFilter()

        # Use cl100k_base encoding (used by GPT-4, Claude approximation)
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self._tokenizer.encode(text))

    def analyze(
        self,
        repo_path: Path,
        name: str | None = None,
        description: str | None = None,
        language: str | None = None,
    ) -> RepoAnalysis:
        """Analyze a local repository.

        Args:
            repo_path: Path to repository root
            name: Repository name (defaults to directory name)
            description: Optional description
            language: Primary language (auto-detected if not provided)

        Returns:
            RepoAnalysis with files and metadata
        """
        repo_path = Path(repo_path).resolve()

        if not repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")

        if not repo_path.is_dir():
            raise ValueError(f"Repository path is not a directory: {repo_path}")

        repo_name = name or repo_path.name

        logfire.info("Starting local repository analysis", repo=repo_name, path=str(repo_path))

        # Collect all files
        all_files = self._collect_files(repo_path)

        # Filter files
        filtered_files = self._filter_files(all_files, repo_path)

        logfire.info(
            "Filtered local repository files",
            total_files=len(all_files),
            after_filter=len(filtered_files),
        )

        # Sort by likely importance
        prioritized_files = self._prioritize_files(filtered_files)

        # Read file contents up to token limit
        analyzed_files: list[AnalyzedFile] = []
        skipped_files: list[str] = []
        total_tokens = 0
        truncated = False

        for filtered_file in prioritized_files:
            if total_tokens >= self.max_tokens:
                skipped_files.append(filtered_file.path)
                truncated = True
                continue

            try:
                file_path = repo_path / filtered_file.path
                content = file_path.read_text(encoding="utf-8", errors="replace")

                token_count = self._count_tokens(content)

                # Skip if this file alone would exceed remaining budget
                if total_tokens + token_count > self.max_tokens:
                    skipped_files.append(filtered_file.path)
                    truncated = True
                    continue

                analyzed_files.append(
                    AnalyzedFile(
                        path=filtered_file.path,
                        content=content,
                        size=filtered_file.size,
                        extension=filtered_file.extension,
                        token_count=token_count,
                    )
                )
                total_tokens += token_count

            except Exception as e:
                logfire.warn(
                    "Failed to read file",
                    path=filtered_file.path,
                    error=str(e),
                )
                skipped_files.append(filtered_file.path)

        # Build directory structure
        directory_structure = self._build_directory_structure([f.path for f in analyzed_files])

        # Auto-detect language if not provided
        detected_language = language or self._detect_language(analyzed_files)

        # Create repository object
        local_repo = LocalRepository(
            path=repo_path,
            name=repo_name,
            description=description,
            language=detected_language,
        )

        logfire.info(
            "Local repository analysis complete",
            repo=repo_name,
            files_analyzed=len(analyzed_files),
            files_skipped=len(skipped_files),
            total_tokens=total_tokens,
            truncated=truncated,
        )

        return RepoAnalysis(
            repository=local_repo.to_repository(),
            files=analyzed_files,
            directory_structure=directory_structure,
            total_tokens=total_tokens,
            truncated=truncated,
            skipped_files=skipped_files,
        )

    def _collect_files(self, repo_path: Path) -> list[Path]:
        """Collect all files in repository."""
        files: list[Path] = []

        for file_path in repo_path.rglob("*"):
            if file_path.is_file():
                # Skip hidden directories
                if any(
                    part.startswith(".") for part in file_path.relative_to(repo_path).parts[:-1]
                ):
                    continue
                files.append(file_path)

        return files

    def _filter_files(self, files: list[Path], repo_path: Path) -> list[FilteredFile]:
        """Filter files using the file filter."""
        filtered: list[FilteredFile] = []

        for file_path in files:
            rel_path = str(file_path.relative_to(repo_path))
            size = file_path.stat().st_size

            if self.file_filter.should_include(rel_path, size):
                extension = file_path.suffix
                filtered.append(
                    FilteredFile(
                        path=rel_path,
                        size=size,
                        extension=extension,
                    )
                )

        return filtered

    def _prioritize_files(self, files: list[FilteredFile]) -> list[FilteredFile]:
        """Sort files by likely importance for documentation."""

        def priority_key(f: FilteredFile) -> tuple[int, str]:
            path_lower = f.path.lower()
            name = path_lower.split("/")[-1]

            # Priority 0: README
            if name.startswith("readme"):
                return (0, f.path)

            # Priority 1: Package/config files at root
            if "/" not in f.path and name in {
                "package.json",
                "pyproject.toml",
                "cargo.toml",
                "go.mod",
                "setup.py",
                "setup.cfg",
                "composer.json",
                "gemfile",
                "pubspec.yaml",
                "build.gradle",
                "pom.xml",
            }:
                return (1, f.path)

            # Priority 2: Entry points
            if name in {
                "main.py",
                "app.py",
                "index.py",
                "cli.py",
                "main.ts",
                "index.ts",
                "app.ts",
                "main.js",
                "index.js",
                "app.js",
                "main.go",
                "main.rs",
                "main.java",
            }:
                return (2, f.path)

            # Priority 3: API/routes
            if any(x in path_lower for x in ["api", "routes", "views", "handlers"]):
                return (3, f.path)

            # Priority 4: Source files
            if f.extension in {".py", ".ts", ".js", ".go", ".rs", ".java"}:
                return (4, f.path)

            # Priority 5: Config files
            if f.extension in {".json", ".yaml", ".yml", ".toml"}:
                return (5, f.path)

            # Priority 6: Documentation
            if f.extension in {".md", ".mdx", ".rst"}:
                return (6, f.path)

            # Priority 7: Everything else
            return (7, f.path)

        return sorted(files, key=priority_key)

    def _build_directory_structure(self, paths: list[str]) -> str:
        """Build a tree-like directory structure string."""
        if not paths:
            return "(empty)"

        tree: dict = {}
        for path in sorted(paths):
            parts = path.split("/")
            current = tree
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = None

        lines: list[str] = []
        self._render_tree(tree, "", lines)
        return "\n".join(lines)

    def _render_tree(
        self,
        tree: dict,
        prefix: str,
        lines: list[str],
    ) -> None:
        """Recursively render tree structure."""
        items = sorted(tree.items(), key=lambda x: (x[1] is not None, x[0]))

        for i, (name, subtree) in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "

            if subtree is None:
                lines.append(f"{prefix}{connector}{name}")
            else:
                lines.append(f"{prefix}{connector}{name}/")
                new_prefix = prefix + ("    " if is_last else "│   ")
                self._render_tree(subtree, new_prefix, lines)

    def _detect_language(self, files: list[AnalyzedFile]) -> str | None:
        """Detect primary language from file extensions."""
        extension_counts: dict[str, int] = {}

        for f in files:
            ext = f.extension.lower()
            if ext in {".py", ".ts", ".js", ".go", ".rs", ".java", ".rb", ".php"}:
                extension_counts[ext] = extension_counts.get(ext, 0) + 1

        if not extension_counts:
            return None

        # Map extensions to language names
        ext_to_lang = {
            ".py": "Python",
            ".ts": "TypeScript",
            ".js": "JavaScript",
            ".go": "Go",
            ".rs": "Rust",
            ".java": "Java",
            ".rb": "Ruby",
            ".php": "PHP",
        }

        top_ext = max(extension_counts, key=extension_counts.get)  # type: ignore
        return ext_to_lang.get(top_ext)


def analyze_local_repo(
    repo_path: Path | str,
    max_tokens: int = 100_000,
    name: str | None = None,
    description: str | None = None,
) -> RepoAnalysis:
    """Convenience function to analyze a local repository.

    Args:
        repo_path: Path to repository
        max_tokens: Maximum tokens to include
        name: Repository name (defaults to directory name)
        description: Optional description

    Returns:
        RepoAnalysis result
    """
    analyzer = LocalRepoAnalyzer(max_tokens=max_tokens)
    return analyzer.analyze(Path(repo_path), name=name, description=description)
