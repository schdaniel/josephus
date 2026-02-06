"""Unit tests for audience inference."""


from josephus.analyzer.audience import (
    AudienceInference,
    AudienceType,
    _analyze_file_structure,
    _check_explicit_audience,
    infer_audience,
)
from josephus.analyzer.repo import AnalyzedFile, RepoAnalysis
from josephus.github import Repository


def make_analysis(
    files: list[tuple[str, str]] | None = None,
    description: str = "",
) -> RepoAnalysis:
    """Create a test RepoAnalysis."""
    repo = Repository(
        id=1,
        name="test-repo",
        full_name="owner/test-repo",
        description=description,
        default_branch="main",
        language="Python",
        private=False,
        html_url="https://github.com/owner/test-repo",
    )

    analyzed_files = []
    if files:
        for path, content in files:
            ext = "." + path.split(".")[-1] if "." in path else ""
            analyzed_files.append(
                AnalyzedFile(
                    path=path,
                    content=content,
                    size=len(content),
                    extension=ext,
                    token_count=len(content) // 4,
                )
            )

    return RepoAnalysis(
        repository=repo,
        files=analyzed_files,
        directory_structure="",
        total_tokens=sum(f.token_count for f in analyzed_files),
    )


class TestExplicitAudience:
    """Tests for explicit audience detection in guidelines."""

    def test_explicit_developer_audience(self) -> None:
        """Test detection of explicit developer audience."""
        guidelines = "This is documentation for developers using our API."
        result = _check_explicit_audience(guidelines)

        assert result is not None
        assert result.audience == AudienceType.DEVELOPERS
        assert result.confidence == 1.0

    def test_explicit_technical_audience(self) -> None:
        """Test detection of technical audience keyword."""
        guidelines = "Write for a technical audience familiar with Python."
        result = _check_explicit_audience(guidelines)

        assert result is not None
        assert result.audience == AudienceType.DEVELOPERS

    def test_explicit_end_user_audience(self) -> None:
        """Test detection of explicit end user audience."""
        guidelines = "Documentation for end users of the application."
        result = _check_explicit_audience(guidelines)

        assert result is not None
        assert result.audience == AudienceType.END_USERS
        assert result.confidence == 1.0

    def test_explicit_non_technical_audience(self) -> None:
        """Test detection of non-technical audience keyword."""
        guidelines = "Write for a non-technical audience."
        result = _check_explicit_audience(guidelines)

        assert result is not None
        assert result.audience == AudienceType.END_USERS

    def test_no_explicit_audience(self) -> None:
        """Test no explicit audience in guidelines."""
        guidelines = "Keep documentation concise and well-organized."
        result = _check_explicit_audience(guidelines)

        assert result is None

    def test_empty_guidelines(self) -> None:
        """Test empty guidelines."""
        result = _check_explicit_audience("")
        assert result is None


class TestFileStructureAnalysis:
    """Tests for file structure analysis."""

    def test_python_package_signals(self) -> None:
        """Test detection of Python package signals."""
        file_paths = ["pyproject.toml", "src/mylib/__init__.py", "src/mylib/core.py"]
        dev_score, user_score, signals = _analyze_file_structure(file_paths, 0, 0, [])

        assert dev_score > user_score
        assert "Python package" in signals

    def test_cli_application_signals(self) -> None:
        """Test detection of CLI application signals."""
        file_paths = ["cli.py", "commands.py", "main.py"]
        dev_score, user_score, signals = _analyze_file_structure(file_paths, 0, 0, [])

        assert dev_score > user_score
        assert "CLI application" in signals

    def test_api_signals(self) -> None:
        """Test detection of API signals."""
        file_paths = ["openapi.yaml", "api/routes.py", "api/handlers.py"]
        dev_score, user_score, signals = _analyze_file_structure(file_paths, 0, 0, [])

        assert dev_score > user_score
        assert "OpenAPI spec" in signals

    def test_desktop_app_signals(self) -> None:
        """Test detection of desktop app signals."""
        file_paths = ["electron.js", "main.js", "preload.js"]
        dev_score, user_score, signals = _analyze_file_structure(file_paths, 0, 0, [])

        assert user_score > 0
        assert "Electron app" in signals


class TestAudienceInference:
    """Tests for full audience inference."""

    def test_infer_library_audience(self) -> None:
        """Test inference for a library project."""
        analysis = make_analysis(
            files=[
                ("pyproject.toml", "[project]\nname = 'mylib'\n"),
                ("src/mylib/__init__.py", "from .core import MyClass\n"),
                ("README.md", "# MyLib\n\nA Python library for...\n\n```python\nimport mylib\n```"),
            ],
            description="A library for data processing",
        )

        result = infer_audience(analysis)

        assert result.audience == AudienceType.DEVELOPERS
        assert result.confidence > 0.5

    def test_infer_cli_audience(self) -> None:
        """Test inference for a CLI tool."""
        analysis = make_analysis(
            files=[
                ("cli.py", "import click\n@click.command()\ndef main(): pass"),
                ("README.md", "# MyCLI\n\nCommand-line tool for...\n\n## CLI Usage\n"),
            ],
            description="CLI tool for developers",
        )

        result = infer_audience(analysis)

        assert result.audience == AudienceType.DEVELOPERS

    def test_infer_with_explicit_guidelines(self) -> None:
        """Test that explicit guidelines override inference."""
        analysis = make_analysis(
            files=[
                ("pyproject.toml", "[project]"),
                ("src/lib.py", "def api_function(): pass"),
            ],
        )

        # Should be developers based on structure
        result_no_guidelines = infer_audience(analysis, guidelines="")
        assert result_no_guidelines.audience == AudienceType.DEVELOPERS

        # Should be end users based on explicit guidelines
        result_with_guidelines = infer_audience(
            analysis,
            guidelines="Write documentation for end users who download the app.",
        )
        assert result_with_guidelines.audience == AudienceType.END_USERS
        assert result_with_guidelines.confidence == 1.0

    def test_infer_default_for_code_repo(self) -> None:
        """Test default inference for generic code repository."""
        analysis = make_analysis(
            files=[
                ("main.py", "print('hello')"),
            ],
        )

        result = infer_audience(analysis)

        # Should default to developers for code repos
        assert result.audience in {AudienceType.DEVELOPERS, AudienceType.MIXED}

    def test_description_influences_inference(self) -> None:
        """Test that repo description influences inference."""
        analysis_sdk = make_analysis(
            files=[("src/client.py", "class Client: pass")],
            description="SDK for the FooBar API",
        )
        result_sdk = infer_audience(analysis_sdk)
        assert (
            "sdk" in [s.lower() for s in result_sdk.signals]
            or result_sdk.audience == AudienceType.DEVELOPERS
        )

        analysis_app = make_analysis(
            files=[("app.py", "def run(): pass")],
            description="A desktop application for managing photos",
        )
        result_app = infer_audience(analysis_app)
        # Application description should contribute to user score
        assert any("app" in s.lower() for s in result_app.signals)


class TestAudienceInferenceOutput:
    """Tests for AudienceInference output formatting."""

    def test_to_prompt_context_developers(self) -> None:
        """Test prompt context generation for developers."""
        inference = AudienceInference(
            audience=AudienceType.DEVELOPERS,
            confidence=0.85,
            signals=["Python package", "CLI application"],
            tone_guidance="Write technical documentation.",
        )

        context = inference.to_prompt_context()

        assert "Technical (Developers)" in context
        assert "85%" in context
        assert "Python package" in context
        assert "code examples" in context.lower()

    def test_to_prompt_context_end_users(self) -> None:
        """Test prompt context generation for end users."""
        inference = AudienceInference(
            audience=AudienceType.END_USERS,
            confidence=0.75,
            signals=["Electron app"],
            tone_guidance="Write user-friendly guides.",
        )

        context = inference.to_prompt_context()

        assert "Non-Technical (End Users)" in context
        assert "75%" in context
        assert "jargon-free" in context.lower()

    def test_to_prompt_context_mixed(self) -> None:
        """Test prompt context generation for mixed audience."""
        inference = AudienceInference(
            audience=AudienceType.MIXED,
            confidence=0.6,
            signals=["Web pages", "API structure"],
            tone_guidance="Balance technical and user content.",
        )

        context = inference.to_prompt_context()

        assert "Mixed" in context
        assert "developers and end users" in context.lower()
