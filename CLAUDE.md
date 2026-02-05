# Claude Code Instructions for Josephus

## Working Methodology (ALWAYS FOLLOW)

### Task Management
- **All tasks must be GitHub issues** - Create issues before starting work on features, bugs, or improvements
- **Maintain in-session todo list** - Use TaskCreate/TaskUpdate to track work, synced with GitHub issues
- **Reference issue numbers** - Always link commits and work to relevant issues

### Git Workflow
- **ALL changes in branches** - Never commit directly to main. This includes features, bug fixes, hotfixes, documentation, and CI fixes. No exceptions.
- **Branch naming**: `feature/<issue-number>-<short-description>` or `fix/<issue-number>-<short-description>`
- **Always create PR** - Push branch and create PR, even for small changes
- **Test before merge** - Run all tests (`pytest tests/`) and lints before merging
- **Bugs as issues** - Always create GitHub issues for bugs discovered during development

### Before Starting Any Work
1. Check if there's a GitHub issue for the task (`gh issue list`)
2. If not, create one first (`gh issue create`)
3. Create a branch for the work (`git checkout -b feature/<issue>-<desc>`)
4. Create local tasks (TaskCreate) referencing the issue number

### Commit Messages
- Reference issue numbers: `fix #123: description` or `feat #123: description`
- Keep commits atomic and focused
- Include `Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>`

### Code Quality
- Run `ruff check .` and `ruff format .` before committing
- Ensure all tests pass before pushing
- Follow existing code patterns and style

## Project Overview

Josephus is an AI-powered documentation generator that:
- Analyzes code repositories via GitHub App integration
- Uses Claude to generate customer-facing documentation
- Creates PRs with generated docs automatically

### Key Components
- `src/josephus/core/service.py` - Main orchestrator (JosephusService)
- `src/josephus/analyzer/` - Repository analysis and file filtering
- `src/josephus/generator/` - Documentation generation with LLM
- `src/josephus/github/` - GitHub App auth and API client
- `src/josephus/api/` - FastAPI webhooks and routes

### Running Tests
```bash
pytest tests/unit -v
```

### Running Lints
```bash
ruff check . && ruff format .
```
