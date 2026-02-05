"""Repository analyzer - fetches and structures codebase for LLM processing."""

from dataclasses import dataclass, field

import logfire
import tiktoken

from josephus.analyzer.filters import FileFilter, FilteredFile, filter_tree
from josephus.github import GitHubClient, Repository


@dataclass
class AnalyzedFile:
    """A file with its content, ready for LLM processing."""

    path: str
    content: str
    size: int
    extension: str
    token_count: int


@dataclass
class RepoAnalysis:
    """Complete analysis of a repository."""

    repository: Repository
    files: list[AnalyzedFile]
    directory_structure: str
    total_tokens: int
    truncated: bool = False
    skipped_files: list[str] = field(default_factory=list)


class RepoAnalyzer:
    """Analyzes a repository to prepare context for documentation generation.

    Fetches repository contents, filters files, and structures them
    for efficient LLM processing.
    """

    def __init__(
        self,
        github_client: GitHubClient,
        max_tokens: int = 100_000,
        file_filter: FileFilter | None = None,
    ) -> None:
        """Initialize the analyzer.

        Args:
            github_client: GitHub API client
            max_tokens: Maximum tokens to include in analysis
            file_filter: File filter configuration
        """
        self.github = github_client
        self.max_tokens = max_tokens
        self.file_filter = file_filter or FileFilter()

        # Use cl100k_base encoding (used by GPT-4, Claude approximation)
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self._tokenizer.encode(text))

    async def analyze(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        ref: str | None = None,
    ) -> RepoAnalysis:
        """Analyze a repository.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            ref: Git ref (branch, tag, commit) - defaults to default branch

        Returns:
            RepoAnalysis with files and metadata
        """
        logfire.info("Starting repository analysis", repo=f"{owner}/{repo}", ref=ref)

        # Get repository metadata
        repository = await self.github.get_repository(installation_id, owner, repo)
        target_ref = ref or repository.default_branch

        # Get full tree
        tree = await self.github.get_tree(installation_id, owner, repo, target_ref, recursive=True)

        # Filter files
        filtered_files = filter_tree(tree.tree, self.file_filter)

        logfire.info(
            "Filtered repository files",
            total_in_tree=len(tree.tree),
            after_filter=len(filtered_files),
            truncated=tree.truncated,
        )

        # Sort by likely importance
        prioritized_files = self._prioritize_files(filtered_files)

        # Fetch file contents up to token limit
        analyzed_files: list[AnalyzedFile] = []
        skipped_files: list[str] = []
        total_tokens = 0
        truncated = tree.truncated

        for filtered_file in prioritized_files:
            # Check if we're approaching token limit
            if total_tokens >= self.max_tokens:
                skipped_files.append(filtered_file.path)
                truncated = True
                continue

            try:
                file_content = await self.github.get_file_content(
                    installation_id, owner, repo, filtered_file.path, ref=target_ref
                )

                token_count = self._count_tokens(file_content.content)

                # Skip if this file alone would exceed remaining budget
                if total_tokens + token_count > self.max_tokens:
                    skipped_files.append(filtered_file.path)
                    truncated = True
                    continue

                analyzed_files.append(
                    AnalyzedFile(
                        path=filtered_file.path,
                        content=file_content.content,
                        size=filtered_file.size,
                        extension=filtered_file.extension,
                        token_count=token_count,
                    )
                )
                total_tokens += token_count

            except Exception as e:
                logfire.warn(
                    "Failed to fetch file",
                    path=filtered_file.path,
                    error=str(e),
                )
                skipped_files.append(filtered_file.path)

        # Build directory structure
        directory_structure = self._build_directory_structure([f.path for f in analyzed_files])

        logfire.info(
            "Repository analysis complete",
            repo=f"{owner}/{repo}",
            files_analyzed=len(analyzed_files),
            files_skipped=len(skipped_files),
            total_tokens=total_tokens,
            truncated=truncated,
        )

        return RepoAnalysis(
            repository=repository,
            files=analyzed_files,
            directory_structure=directory_structure,
            total_tokens=total_tokens,
            truncated=truncated,
            skipped_files=skipped_files,
        )

    def _prioritize_files(self, files: list[FilteredFile]) -> list[FilteredFile]:
        """Sort files by likely importance for documentation.

        Priority order:
        1. README and documentation files
        2. Package/config files (package.json, pyproject.toml, etc.)
        3. Main entry points
        4. Source files by extension
        5. Everything else
        """

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

        # Build tree structure
        tree: dict = {}
        for path in sorted(paths):
            parts = path.split("/")
            current = tree
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            # Mark files with None
            current[parts[-1]] = None

        # Render tree
        lines = []
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
                # File
                lines.append(f"{prefix}{connector}{name}")
            else:
                # Directory
                lines.append(f"{prefix}{connector}{name}/")
                new_prefix = prefix + ("    " if is_last else "│   ")
                self._render_tree(subtree, new_prefix, lines)


def format_for_llm(analysis: RepoAnalysis, guidelines: str = "") -> str:
    """Format repository analysis as XML context for Claude.

    Args:
        analysis: Repository analysis result
        guidelines: User's documentation guidelines

    Returns:
        XML-formatted string for LLM context
    """
    parts = [
        f'<repository name="{analysis.repository.name}">',
        f"<description>{analysis.repository.description or 'No description'}</description>",
        f"<language>{analysis.repository.language or 'Unknown'}</language>",
        f"<default_branch>{analysis.repository.default_branch}</default_branch>",
        "",
        "<directory_structure>",
        analysis.directory_structure,
        "</directory_structure>",
        "",
    ]

    if guidelines:
        parts.extend(
            [
                "<documentation_guidelines>",
                guidelines,
                "</documentation_guidelines>",
                "",
            ]
        )

    parts.append("<files>")

    for file in analysis.files:
        parts.extend(
            [
                f'<file path="{file.path}">',
                file.content,
                "</file>",
                "",
            ]
        )

    parts.append("</files>")

    if analysis.truncated or analysis.skipped_files:
        parts.extend(
            [
                "",
                "<note>",
                f"Analysis was truncated. {len(analysis.skipped_files)} files were skipped ",
                "due to token limits. Focus on the included files for documentation.",
                "</note>",
            ]
        )

    parts.append("</repository>")

    return "\n".join(parts)
