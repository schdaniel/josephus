"""Josephus core service - orchestrates documentation generation workflow."""

from dataclasses import dataclass
from datetime import datetime

import logfire

from josephus.analyzer import FileFilter, RepoAnalysis, RepoAnalyzer
from josephus.generator import DocGenerator, GeneratedDocs, GenerationConfig
from josephus.github import GitHubClient
from josephus.llm import LLMProvider, get_provider


@dataclass
class DocumentationResult:
    """Result of documentation generation workflow."""

    # Repository info
    repo_full_name: str
    repo_url: str

    # Analysis
    analysis: RepoAnalysis
    files_analyzed: int
    total_tokens: int

    # Generation
    generated_docs: GeneratedDocs
    docs_generated: int

    # Commit/PR
    branch_name: str
    commit_sha: str
    pr_url: str | None = None
    pr_number: int | None = None

    # Timing
    started_at: datetime | None = None
    completed_at: datetime | None = None


class JosephusService:
    """Main service for documentation generation.

    Orchestrates the full workflow:
    1. Analyze repository
    2. Generate documentation
    3. Commit to branch
    4. Create pull request
    """

    def __init__(
        self,
        github_client: GitHubClient | None = None,
        llm_provider: LLMProvider | None = None,
        file_filter: FileFilter | None = None,
        max_tokens: int = 100_000,
    ) -> None:
        """Initialize the service.

        Args:
            github_client: GitHub API client
            llm_provider: LLM provider for generation
            file_filter: File filter configuration
            max_tokens: Max tokens for repository analysis
        """
        self.github = github_client or GitHubClient()
        self.llm = llm_provider or get_provider()
        self.file_filter = file_filter or FileFilter()
        self.max_tokens = max_tokens

    async def generate_documentation(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        guidelines: str = "",
        output_dir: str = "docs",
        branch_name: str | None = None,
        create_pr: bool = True,
        pr_title: str | None = None,
        pr_body: str | None = None,
    ) -> DocumentationResult:
        """Generate documentation for a repository.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            guidelines: Documentation guidelines
            output_dir: Output directory for docs
            branch_name: Branch name (auto-generated if not provided)
            create_pr: Whether to create a PR
            pr_title: PR title (auto-generated if not provided)
            pr_body: PR body (auto-generated if not provided)

        Returns:
            DocumentationResult with all workflow outputs
        """
        started_at = datetime.utcnow()

        logfire.info(
            "Starting documentation generation workflow",
            repo=f"{owner}/{repo}",
            installation_id=installation_id,
        )

        # Step 1: Analyze repository
        analyzer = RepoAnalyzer(
            github_client=self.github,
            max_tokens=self.max_tokens,
            file_filter=self.file_filter,
        )
        analysis = await analyzer.analyze(installation_id, owner, repo)

        logfire.info(
            "Repository analysis complete",
            files=len(analysis.files),
            tokens=analysis.total_tokens,
        )

        # Step 2: Generate documentation
        generator = DocGenerator(self.llm)
        config = GenerationConfig(
            guidelines=guidelines,
            output_dir=output_dir,
        )
        generated_docs = await generator.generate(analysis, config)

        logfire.info(
            "Documentation generated",
            files=len(generated_docs.files),
        )

        # Step 3: Commit to branch
        branch = branch_name or f"josephus/docs-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

        commit = await self.github.commit_files(
            installation_id=installation_id,
            owner=owner,
            repo=repo,
            branch=branch,
            files=generated_docs.files,
            message=f"docs: generate documentation with Josephus\n\nGenerated {len(generated_docs.files)} documentation files.",
        )

        logfire.info(
            "Documentation committed",
            branch=branch,
            commit_sha=commit["sha"],
        )

        # Step 4: Create PR (optional)
        pr_url = None
        pr_number = None

        if create_pr:
            title = pr_title or f"docs: Add generated documentation"
            body = pr_body or self._generate_pr_body(analysis, generated_docs)

            pr = await self.github.create_pull_request(
                installation_id=installation_id,
                owner=owner,
                repo=repo,
                title=title,
                body=body,
                head=branch,
                base=analysis.repository.default_branch,
            )

            pr_url = pr["html_url"]
            pr_number = pr["number"]

            logfire.info(
                "Pull request created",
                pr_number=pr_number,
                pr_url=pr_url,
            )

        completed_at = datetime.utcnow()

        return DocumentationResult(
            repo_full_name=analysis.repository.full_name,
            repo_url=analysis.repository.html_url,
            analysis=analysis,
            files_analyzed=len(analysis.files),
            total_tokens=analysis.total_tokens,
            generated_docs=generated_docs,
            docs_generated=len(generated_docs.files),
            branch_name=branch,
            commit_sha=commit["sha"],
            pr_url=pr_url,
            pr_number=pr_number,
            started_at=started_at,
            completed_at=completed_at,
        )

    def _generate_pr_body(
        self,
        analysis: RepoAnalysis,
        docs: GeneratedDocs,
    ) -> str:
        """Generate a PR description."""
        files_list = "\n".join(f"- `{path}`" for path in sorted(docs.files.keys()))

        return f"""## Summary

This PR adds automatically generated documentation for the repository.

### Generated Files

{files_list}

### Generation Details

- **Files analyzed:** {len(analysis.files)}
- **Tokens processed:** {analysis.total_tokens:,}
- **Input tokens (LLM):** {docs.llm_response.input_tokens:,}
- **Output tokens (LLM):** {docs.llm_response.output_tokens:,}
- **Model:** {docs.llm_response.model}

---

*Generated by [Josephus](https://github.com/schdaniel/josephus) - AI-powered documentation generator*
"""

    async def close(self) -> None:
        """Close all connections."""
        await self.github.close()
        await self.llm.close()
