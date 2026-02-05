# Josephus - AI-Powered Documentation Generator

> Automatically generate and maintain customer-facing product documentation from code repositories using AI.

---

## 1. Project Vision

Josephus transforms code repositories into living, customer-facing documentation. It handles both the initial generation of comprehensive docs and the ongoing maintenance as code evolves through PRs.

**Key differentiators:**
- Focus on **customer-facing** docs (not internal/developer docs)
- **Natural language configuration** for tone, scope, and style
- **PR-aware** - automatically detects documentation-relevant changes
- **CI/CD native** - integrates seamlessly with GitHub workflows

---

## 2. Market Analysis

### Existing AI Documentation Tools

| Tool | Strengths | Gaps for Our Use Case |
|------|-----------|----------------------|
| [DeepWiki](https://deepwiki.com/) | Instant wiki from any repo, RAG-powered Q&A | Internal/developer focused, no PR integration, no CI/CD |
| [DeepWiki-Open](https://github.com/AsyncFuncAI/deepwiki-open) | Open source, multi-provider LLM support | Maintenance moving to AsyncReview, no PR workflow |
| [Mintlify](https://mintlify.com/) | Beautiful docs, AI assistant, git-native | $150+/mo, API-focused, no auto-generation from code |
| [DocuWriter.ai](https://docuwriter.ai/) | Auto-generates from source code | Developer docs focus, not customer-facing |
| [Repomix](https://repomix.com/) | Packs codebase for AI context | Tool, not a complete solution |

### Documentation Platforms (User's Choice)

We generate markdown - users render with their preferred platform:

| Platform | Best For | Notes |
|----------|----------|-------|
| **Docusaurus** | React teams, versioned docs | Most popular, feature-rich |
| **MkDocs** | Python teams | Simple, Material theme popular |
| **Nextra** | Next.js teams | Lightweight |
| **GitBook** | Non-technical editors | WYSIWYG option |
| **Mintlify** | Beautiful API docs | Paid, polished |
| **GitHub Pages** | Zero setup | Raw markdown rendering |

### Our Approach: Platform-Agnostic Markdown

**We are NOT a docs platform.** We are a markdown generation engine.

**What we output:**
- Standard markdown files with optional frontmatter
- Mermaid diagrams (widely supported)
- Compatible folder structure

**What users do:**
- Plug our output into any docs platform
- Use their existing docs infrastructure
- Full control over rendering/hosting

---

## 3. Core Features

### 3.1 Onboarding Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                     ONBOARDING FLOW                              │
├─────────────────────────────────────────────────────────────────┤
│  1. Install App  →  2. Select Repo  →  3. Configure Guidelines  │
│                                                │                 │
│                                                ▼                 │
│  6. Review & Edit  ←  5. Generate Docs  ←  4. Analyze Codebase │
│         │                                                        │
│         ▼                                                        │
│  7. Commit to Repo (PR)  →  Done! (CI already active)           │
└─────────────────────────────────────────────────────────────────┘
```

**Steps:**
1. **Install GitHub App** - Single integration: user auth + repo access + webhooks
2. **Repository Selection** - Choose repo(s) to document from installed repos
3. **Configuration** - Natural language guidelines (see 3.4)
4. **Codebase Analysis** - AI scans and understands the codebase
5. **Documentation Generation** - Creates initial doc structure
6. **Review & Edit** - User reviews, edits, approves
7. **Commit to Repo** - PR with docs committed to `/docs` folder

*Note: CI/webhooks are active immediately after app installation - no separate step needed.*

**Deployment (user's choice):**
- GitHub Pages (built-in, free)
- Vercel / Netlify (automatic deploys)
- Self-hosted

### 3.2 Initial Documentation Generation

**Inputs:**
- Source code repository
- README, existing docs (if any)
- Configuration guidelines
- Optional: Product briefs, marketing materials

**Outputs:**
- Getting Started guide
- Installation/Setup instructions
- Core concepts/Overview
- Feature documentation
- API reference (if applicable)
- FAQ (generated from code patterns)
- Changelog structure

**AI Tasks:**
- Identify public API surface
- Detect user-facing features vs internal implementation
- Extract configuration options
- Generate code examples
- Create architecture diagrams (Mermaid)

### 3.3 Repository Analysis Pipeline

*Pattern adopted from Repomix and DeepWiki-Open*

```
1. Clone/Fetch Repository
       ↓
2. File Filtering (.gitignore → .josephus.yml rules)
       ↓
3. Secret Scanning (reject if credentials detected)
       ↓
4. Token Counting (estimate LLM context usage)
       ↓
5. Code Compression (Tree-sitter for large repos)
       ↓
6. Context Assembly (XML structure for Claude)
       ↓
7. LLM Processing
```

**File Filtering Stack:**
```
.gitignore          → Respect existing ignores
.josephus.yml       → Project-specific overrides
Default excludes    → node_modules, .git, binaries, etc.
```

**Security Scanning:**
- Integrate secret detection before LLM processing
- Block generation if credentials/tokens found
- Warn user with specific file locations

**Token Management:**
- Count tokens per file and total before sending
- Prioritize important files when context limited
- Use Tree-sitter compression for large codebases (extract signatures, skip implementations)

**Context Format (XML for Claude):**
```xml
<repository name="project">
  <file_summary>Overview of repo structure...</file_summary>
  <directory_structure>src/, docs/, tests/...</directory_structure>
  <files>
    <file path="src/api.ts">...content...</file>
  </files>
  <guidelines>User's natural language config...</guidelines>
</repository>
```

### 3.4 PR Documentation Updates (CI/CD)

```
┌─────────────────────────────────────────────────────────────────┐
│                     PR WORKFLOW                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PR Created/Updated                                              │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────────┐                                            │
│  │ Analyze Changes │ ◄── Compare with doc-relevance criteria    │
│  └────────┬────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐     ┌─────────────────┐                   │
│  │ Doc Relevant?   │─No─►│ Add label:      │                   │
│  │                 │     │ "no-doc-change" │                   │
│  └────────┬────────┘     └─────────────────┘                   │
│           │ Yes                                                  │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Generate Doc    │                                            │
│  │ Update Diff     │                                            │
│  └────────┬────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐     ┌─────────────────┐                   │
│  │ Commit to PR    │────►│ Add label:      │                   │
│  │ (new commit)    │     │ "docs-updated"  │                   │
│  └─────────────────┘     └─────────────────┘                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Detection Criteria (AI-evaluated):**
- New public functions/classes/endpoints
- Changed function signatures
- Modified configuration options
- New/removed features
- Breaking changes
- New error types or messages

**Output Options:**
1. **Auto-commit** - Commits doc changes directly to PR branch
2. **Suggestion mode** - Adds PR comment with suggested changes
3. **Draft PR** - Creates separate docs PR linked to code PR

### 3.4 Natural Language Configuration

Users configure documentation behavior through natural language guidelines stored in a config file.

**Example `.josephus.yml`:**
```yaml
# Documentation Guidelines
guidelines: |
  Target audience: Non-technical product managers and business users.
  Tone: Professional but friendly, avoid jargon.
  Focus on use cases and outcomes, not implementation details.
  Include practical examples for every feature.
  Skip internal utilities and developer-only features.

# Scope Configuration
scope:
  include: |
    All REST API endpoints
    Configuration options
    User-facing features in the dashboard
  exclude: |
    Internal microservices communication
    Database schemas
    Development/debugging utilities

# PR Detection Rules
pr_rules: |
  Document changes to:
    - API endpoints (new, modified, deprecated)
    - User-visible features
    - Configuration changes that affect users
  Ignore changes to:
    - Test files
    - CI/CD configurations
    - Internal refactoring without behavior change
    - Performance optimizations

# Style Preferences
style:
  code_examples: "TypeScript and Python"
  diagram_style: "Mermaid flowcharts"
  max_page_length: "Keep pages focused, split if over 500 words"
```

---

## 4. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           JOSEPHUS ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐            │
│  │   Web App    │     │  GitHub App  │     │   CLI Tool   │            │
│  │  (Frontend)  │     │  (Webhooks)  │     │  (Optional)  │            │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘            │
│         │                    │                    │                     │
│         └────────────────────┼────────────────────┘                     │
│                              │                                          │
│                              ▼                                          │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │                        API Layer                              │      │
│  │  - REST/GraphQL API                                          │      │
│  │  - GitHub App (auth + webhooks)                              │      │
│  └──────────────────────────────┬───────────────────────────────┘      │
│                                 │                                       │
│         ┌───────────────────────┼───────────────────────┐              │
│         │                       │                       │              │
│         ▼                       ▼                       ▼              │
│  ┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐       │
│  │  Repo       │    │  Doc Generation  │    │  PR Analysis    │       │
│  │  Analyzer   │    │  Engine          │    │  Service        │       │
│  │             │    │                  │    │                 │       │
│  │  - Clone    │    │  - LLM Provider  │    │  - Diff parser  │       │
│  │  - Parse    │    │  - RAG pipeline  │    │  - Relevance    │       │
│  │  - Index    │    │  - Template gen  │    │  - Doc updates  │       │
│  └─────────────┘    └──────────────────┘    └─────────────────┘       │
│         │                       │                       │              │
│         └───────────────────────┼───────────────────────┘              │
│                                 │                                       │
│                                 ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │                      Data Layer                               │      │
│  │  - PostgreSQL (projects, configs, generation history)        │      │
│  │  - Vector DB (code embeddings for RAG)                       │      │
│  └──────────────────────────────────────────────────────────────┘      │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │                   Output: Markdown to Git                     │      │
│  │  - Standard markdown + frontmatter                           │      │
│  │  - Committed to user's repo (/docs or configurable path)     │      │
│  │  - User renders with platform of choice                      │      │
│  └──────────────────────────────────────────────────────────────┘      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Technical Requirements

### 5.1 Tech Stack (Proposed)

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Backend API** | Python (FastAPI) | Strong AI/ML ecosystem, async native |
| **Frontend** | Next.js + TypeScript | Modern React, SSR, great DX |
| **Database** | PostgreSQL | Reliable, JSON support, full-text search |
| **Vector Store** | pgvector | Simpler ops (no separate service), proven |
| **Queue** | Celery + Redis | Mature Python job processing, scalable |
| **Code Parsing** | Tree-sitter | Language-aware AST extraction |
| **LLM Provider** | Config-driven multi-provider | Claude (primary), OpenAI, Ollama fallback |
| **Output Format** | Markdown + frontmatter | Platform-agnostic, universal |
| **Doc Storage** | Git (user's repo) | Docs as code, no vendor lock-in |
| **API Hosting** | Railway / Render | Easy deployment, Docker support |

### 5.2 GitHub Integration (App Only)

Single GitHub App handles everything: user authentication, repo access, and webhooks.

**GitHub App Permissions Required:**
- `contents: write` - Read repo files, commit doc updates
- `pull_requests: write` - Create PRs, add comments and labels
- `metadata: read` - Repository metadata
- `checks: write` - Create check runs for doc status

**Webhook Events:**
- `pull_request` - opened, synchronize, closed
- `push` - to main/master (for doc site rebuilds)
- `installation` - app installed/uninstalled

**Webhook Security (Critical):**
```python
# HMAC signature verification - MUST implement
def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

**Token Management:**
- Generate short-lived installation tokens per request
- Never store long-lived tokens
- Tokens scoped to specific installation

**Webhook Processing Pattern:**
```
Webhook received → Verify signature → Queue job → Return 200 immediately
                                          ↓
                              Worker processes async (Celery)
```

**Why App-only (no separate OAuth):**
- Single installation flow for users
- App can authenticate users via built-in OAuth
- Webhooks work immediately after install
- Cleaner permissions model

### 5.3 LLM Requirements

**Tasks requiring LLM:**
1. Codebase analysis and understanding
2. Documentation content generation
3. PR change relevance classification
4. Natural language guideline interpretation
5. Code example generation

**Model considerations:**
- Long context window (100k+) for large codebases
- Strong code understanding
- Consistent output formatting
- Cost efficiency for high-volume PR analysis

**Recommended models:**
- **Generation:** Claude 3.5 Sonnet (quality) or Claude Haiku (speed/cost)
- **Classification:** Claude Haiku (fast, cheap for PR triage)
- **Embeddings:** OpenAI text-embedding-3-small or local alternative

**Config-Driven Provider Pattern:**
```yaml
# config/llm_providers.yml
providers:
  claude:
    api_key_env: ANTHROPIC_API_KEY
    models:
      generation: claude-3-5-sonnet-20241022
      classification: claude-3-5-haiku-20241022
  openai:
    api_key_env: OPENAI_API_KEY
    base_url_env: OPENAI_BASE_URL  # For Azure/enterprise
    models:
      generation: gpt-4o
      embeddings: text-embedding-3-small
  ollama:
    base_url: http://localhost:11434
    models:
      generation: llama3.2
```

**Environment overrides for enterprise:**
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`
- `OPENAI_BASE_URL` - Custom endpoint (Azure, proxies)
- `LLM_PROVIDER` - Override default provider

### 5.4 Security Requirements

**Webhook Security:**
- [ ] HMAC signature verification on all webhooks (critical)
- [ ] Reject requests with invalid/missing signatures
- [ ] Use timing-safe comparison (`hmac.compare_digest`)

**Code Handling:**
- [ ] No persistent storage of source code
- [ ] Process in memory, discard after generation
- [ ] Secret scanning before LLM processing (block if found)
- [ ] Never send detected credentials to LLM

**Token Security:**
- [ ] GitHub App tokens encrypted at rest
- [ ] Short-lived installation tokens only
- [ ] API keys in environment variables, not config files

**Infrastructure:**
- [ ] Stateless webhook handlers (horizontal scaling)
- [ ] Rate limiting on API and LLM calls
- [ ] Audit logging for all actions
- [ ] Private repo support with explicit permissions

**Compliance (Phase 4):**
- [ ] SOC 2 compliance path (if B2B SaaS)
- [ ] Data residency options for enterprise

---

## 6. User Experience

### 6.1 Onboarding UI Flow

```
Screen 1: Landing
├── "Install Josephus" CTA → GitHub App installation flow
│
Screen 2: Repository Selection
├── List repos where app is installed
├── Search/filter
├── Multi-select support
│
Screen 3: Configuration Wizard
├── Audience selector (technical/non-technical/mixed)
├── Tone selector (formal/friendly/casual)
├── Scope definition (natural language textarea)
├── "Advanced" expandable for detailed config
│
Screen 4: Analysis Progress
├── Real-time progress indicators
├── "Found X public APIs, Y features..."
├── Preview snippets during generation
│
Screen 5: Review Generated Docs
├── Side-by-side: code context ↔ generated doc
├── Edit inline
├── Approve/regenerate per section
│
Screen 6: Commit to Repo
├── Preview PR with docs changes
├── Choose target branch / folder path
├── Create PR button
├── (Optional) Guide for GitHub Pages / Vercel setup
├── Done! CI already active from app installation
```

### 6.2 PR Experience

**For PR Authors:**
- Automatic doc updates committed to their branch
- Clear commit message: "docs: update API reference for new endpoint"
- Label added for visibility

**For Reviewers:**
- Doc changes visible in PR diff
- Can review docs alongside code
- Check status shows doc generation result

---

## 7. Development Phases

### Phase 1: Foundation (MVP)
- [ ] GitHub App integration (auth + repo access)
- [ ] Single repo onboarding
- [ ] Basic doc generation (README → Getting Started)
- [ ] Manual trigger only (no CI webhooks yet)
- [ ] Single LLM provider (Claude)
- [ ] Commit markdown docs to user's repo via PR

### Phase 2: Core Product
- [ ] Full onboarding wizard
- [ ] Comprehensive doc generation
- [ ] Natural language configuration
- [ ] PR webhook handling (auto-detect doc-relevant changes)
- [ ] Auto-commit doc updates to PRs
- [ ] Multi-provider LLM support

### Phase 3: Scale & Polish
- [ ] Team collaboration features
- [ ] Doc versioning support (version-aware generation)
- [ ] Analytics (generation stats, PR coverage)
- [ ] API for programmatic access
- [ ] CLI tool for local generation/preview

### Phase 4: Enterprise
- [ ] Self-hosted option
- [ ] SSO/SAML
- [ ] Audit logs
- [ ] Custom LLM integration (Azure OpenAI, private models)
- [ ] GitHub Enterprise support

---

## 8. Open Questions

### Product Questions
1. **Pricing model?** Per-repo, per-seat, usage-based?
2. ~~**Doc hosting included?**~~ **DECIDED:** Generate files to user's repo, they choose hosting
3. **Multi-repo docs?** Single docs site for monorepo or multiple repos?
4. **Localization?** Auto-translate docs to other languages?

### Technical Questions
1. ~~**Docusaurus vs custom?**~~ **DECIDED:** Neither - output platform-agnostic markdown
2. ~~**Vector DB choice?**~~ **DECIDED:** pgvector (simpler ops, no separate service)
3. ~~**Doc storage?**~~ **DECIDED:** Git-based - docs committed to user's repo
4. ~~**Job queue?**~~ **DECIDED:** Celery + Redis (mature Python ecosystem)
5. **Real-time vs batch?** Generate on-demand or pre-compute?

### Scope Questions
1. **API docs focus?** Should we specialize in API documentation first?
2. **Framework support?** Priority frameworks (React, Node, Python, etc.)?
3. **Existing docs?** How to handle repos with existing documentation?

---

## 9. Evaluation Methodology

### 9.1 What We Need to Measure

| Dimension | Question | Why It Matters |
|-----------|----------|----------------|
| **Accuracy** | Is the generated doc factually correct? | Wrong docs are worse than no docs |
| **Completeness** | Does it cover all user-facing features? | Missing features = support tickets |
| **Relevance** | Does PR detection catch the right changes? | False negatives = stale docs |
| **Clarity** | Is it understandable by target audience? | Jargon-free for non-technical users |
| **Consistency** | Same style/tone across all pages? | Professional appearance |
| **Freshness** | Are docs updated when code changes? | The core value prop |

### 9.2 Evaluation Datasets

**Golden Dataset (Manual Curation):**
```
eval/
├── repos/                    # 10-20 curated open source repos
│   ├── small-cli-tool/       # Simple: <50 files
│   ├── medium-api/           # Medium: 50-200 files
│   ├── large-monorepo/       # Large: 500+ files
│   └── ...
├── ground_truth/             # Human-written ideal docs
│   ├── small-cli-tool/
│   │   ├── expected_docs/    # What good docs look like
│   │   └── annotations.json  # Feature coverage checklist
│   └── ...
├── pr_scenarios/             # PRs with known doc relevance
│   ├── should_update/        # PRs that need doc changes
│   ├── should_ignore/        # PRs that don't (refactoring, tests)
│   └── labels.json           # Ground truth labels
└── guidelines_variations/    # Different user configs to test
```

**Repo Selection Criteria:**
- Mix of languages (Python, TypeScript, Go, Rust)
- Mix of project types (CLI, API, library, web app)
- Existing good documentation to compare against
- Clear public API surface
- Active development (for PR scenarios)

**Candidate repos:**
- `httpie/httpie` - CLI tool, excellent docs
- `fastapi/fastapi` - API framework, great examples
- `supabase/supabase` - Large, multi-component
- `ollama/ollama` - Go CLI, clean API
- Custom synthetic repos for edge cases

### 9.3 Automated Evaluation Metrics

**Documentation Quality:**

| Metric | How to Measure | Target |
|--------|----------------|--------|
| **Coverage Score** | % of public APIs/features documented | > 90% |
| **Accuracy Score** | LLM-as-judge comparing to ground truth | > 85% |
| **Hallucination Rate** | Claims not supported by code | < 5% |
| **Readability** | Flesch-Kincaid grade level | 8-10 (accessible) |
| **Structure Score** | Correct headings, code blocks, links | > 95% |

**PR Detection:**

| Metric | How to Measure | Target |
|--------|----------------|--------|
| **Precision** | True positives / (True + False positives) | > 85% |
| **Recall** | True positives / (True + False negatives) | > 95% |
| **F1 Score** | Harmonic mean of precision/recall | > 90% |
| **Latency** | Time from PR webhook to decision | < 30s |

**LLM-as-Judge Prompt (for accuracy):**
```
You are evaluating AI-generated documentation against ground truth.

<generated_doc>
{generated}
</generated_doc>

<ground_truth>
{expected}
</ground_truth>

<source_code>
{code_context}
</source_code>

Rate the generated documentation on:
1. Factual accuracy (1-5): Are all claims supported by the code?
2. Completeness (1-5): Are all features from ground truth covered?
3. Clarity (1-5): Would a non-technical user understand this?
4. No hallucinations (1-5): Any invented features or incorrect behavior?

Return JSON: {"accuracy": N, "completeness": N, "clarity": N, "hallucinations": N, "issues": [...]}
```

### 9.4 Human Evaluation

**When to use:** Weekly during development, before major releases

**Evaluation Protocol:**
1. Generate docs for 5 repos from golden dataset
2. 3 human reviewers score each (blind, randomized)
3. Rubric: Accuracy, Completeness, Clarity, Would-you-use-it (1-5 each)
4. Inter-rater reliability check (Krippendorff's alpha > 0.7)

**Dogfooding:**
- Generate docs for Josephus itself
- Use them as our actual documentation
- If we won't use our own output, it's not ready

### 9.5 Regression Testing

**On every PR to Josephus:**
```yaml
# .github/workflows/eval.yml
eval-suite:
  runs-on: ubuntu-latest
  steps:
    - name: Run eval on golden dataset
      run: python -m josephus.eval --dataset eval/repos --quick

    - name: Check metrics
      run: |
        python -m josephus.eval.check \
          --coverage-min 0.85 \
          --accuracy-min 0.80 \
          --pr-f1-min 0.88

    - name: Compare to baseline
      run: python -m josephus.eval.compare --baseline main
```

**Nightly full evaluation:**
- Full dataset (all repos, all PR scenarios)
- Cost tracking (tokens used, $ spent)
- Performance benchmarks (latency p50, p95, p99)

### 9.6 Production Monitoring

**Metrics to track (Logfire/Prometheus):**

```python
# Key metrics to instrument
metrics = {
    # Quality signals
    "user_rating": Histogram,           # 1-5 stars from users
    "regeneration_rate": Counter,       # How often users regenerate
    "edit_rate": Gauge,                 # % of docs edited before commit

    # PR detection
    "pr_detection_decisions": Counter,  # Labels: relevant/not_relevant
    "pr_false_positive_reports": Counter,  # User says "not relevant"
    "pr_missed_reports": Counter,       # User says "should have updated"

    # Performance
    "generation_latency_seconds": Histogram,
    "pr_analysis_latency_seconds": Histogram,
    "tokens_used": Counter,             # Labels: model, task

    # Errors
    "generation_failures": Counter,     # Labels: error_type
    "webhook_errors": Counter,
}
```

**Alerts:**
- Accuracy score drops > 10% week-over-week
- Regeneration rate > 30% (users unhappy with output)
- PR detection precision < 80%
- p95 latency > 2 minutes

### 9.7 A/B Testing Infrastructure

**For testing prompt/model changes:**

```python
@feature_flag("doc_generation_v2")
async def generate_docs(repo, config):
    if is_in_experiment("doc_generation_v2", repo.owner_id):
        return await generate_docs_v2(repo, config)
    return await generate_docs_v1(repo, config)
```

**Experiment tracking:**
- Variant assignment logged
- All quality metrics segmented by variant
- Statistical significance before rollout (p < 0.05)

---

## 10. Testing Infrastructure

### 10.1 Test Pyramid

```
                    ┌───────────┐
                    │    E2E    │  ← Few, slow, expensive
                    │  (real    │    GitHub App + LLM calls
                    │   GitHub) │
                   ─┴───────────┴─
                  ┌───────────────┐
                  │  Integration  │  ← Mock GitHub, real LLM
                  │   (mocked     │    or mock LLM responses
                  │    GitHub)    │
                 ─┴───────────────┴─
                ┌───────────────────┐
                │       Unit        │  ← Fast, no external deps
                │  (pure functions) │    Repo analysis, parsing
               ─┴───────────────────┴─
```

### 10.2 Test Categories

**Unit Tests (pytest):**
```python
# tests/unit/test_repo_analyzer.py
def test_file_filtering_respects_gitignore():
    ...

def test_token_counting_accuracy():
    ...

def test_secret_detection_finds_api_keys():
    ...

# tests/unit/test_pr_relevance.py
def test_new_endpoint_is_relevant():
    ...

def test_test_file_changes_not_relevant():
    ...
```

**Integration Tests (with mocks):**
```python
# tests/integration/test_doc_generation.py
@pytest.fixture
def mock_github():
    return MockGitHubClient(repo_fixture="small-cli-tool")

@pytest.fixture
def mock_llm():
    return MockLLMProvider(responses_file="fixtures/llm_responses.json")

async def test_full_generation_flow(mock_github, mock_llm):
    result = await generate_docs(repo="test/repo", config=default_config)
    assert "## Getting Started" in result.files["index.md"]
    assert result.files_count >= 3
```

**E2E Tests (real GitHub, staging):**
```python
# tests/e2e/test_github_app.py
@pytest.mark.e2e
@pytest.mark.slow
async def test_installation_webhook():
    # Uses real GitHub App in staging
    ...

@pytest.mark.e2e
async def test_pr_creates_doc_commit():
    # Creates real PR, checks for doc commit
    ...
```

### 10.3 LLM Testing Strategy

**Challenge:** LLM outputs are non-deterministic

**Solutions:**

1. **Snapshot testing with fuzzy matching:**
```python
def test_getting_started_structure():
    result = generate_getting_started(repo)

    # Check structure, not exact content
    assert has_heading(result, "Installation")
    assert has_heading(result, "Quick Start")
    assert has_code_block(result, language="bash")
```

2. **Deterministic seed for reproducibility:**
```python
@pytest.fixture
def deterministic_llm():
    return LLMProvider(temperature=0, seed=42)
```

3. **Contract testing:**
```python
def test_llm_response_schema():
    result = classify_pr_relevance(diff)

    # Validate response structure
    assert "relevant" in result
    assert isinstance(result["relevant"], bool)
    assert "reason" in result
```

4. **Mock responses for unit tests:**
```python
# fixtures/llm_responses.json
{
    "classify_pr:add_endpoint": {
        "relevant": true,
        "reason": "New public API endpoint added"
    },
    "classify_pr:refactor_internal": {
        "relevant": false,
        "reason": "Internal refactoring, no API changes"
    }
}
```

### 10.4 CI Pipeline

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: ruff check .
      - run: ruff format --check .
      - run: mypy .

  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -e ".[dev]"
      - run: pytest tests/unit -v --cov=josephus --cov-report=xml
      - uses: codecov/codecov-action@v4

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
      redis:
        image: redis:7
    steps:
      - uses: actions/checkout@v4
      - run: pip install -e ".[dev]"
      - run: pytest tests/integration -v
    env:
      DATABASE_URL: postgresql://localhost/test
      REDIS_URL: redis://localhost

  eval-quick:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v4
      - run: pip install -e ".[dev]"
      - run: python -m josephus.eval --quick --compare-baseline
    env:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

  e2e-tests:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - run: pytest tests/e2e -v --timeout=300
    env:
      GITHUB_APP_ID: ${{ secrets.STAGING_APP_ID }}
      GITHUB_APP_KEY: ${{ secrets.STAGING_APP_KEY }}
```

### 10.5 Local Development Testing

```bash
# Run unit tests (fast, no deps)
pytest tests/unit -v

# Run with coverage
pytest tests/unit --cov=josephus --cov-report=html

# Run integration tests (needs docker-compose up)
docker-compose up -d postgres redis
pytest tests/integration -v

# Run single eval repo
python -m josephus.eval --repo eval/repos/small-cli-tool --verbose

# Run PR detection eval
python -m josephus.eval.pr_detection --dataset eval/pr_scenarios
```

### 10.6 Test Data Management

**Fixtures location:**
```
tests/
├── fixtures/
│   ├── repos/              # Small synthetic repos for unit tests
│   │   ├── minimal/        # 3 files, simple structure
│   │   └── with_secrets/   # For testing secret detection
│   ├── llm_responses/      # Mocked LLM outputs
│   ├── webhooks/           # Sample GitHub webhook payloads
│   └── configs/            # Various .josephus.yml configs
└── eval/                   # Larger evaluation dataset (git-lfs)
```

**Updating fixtures:**
```bash
# Record new LLM responses for mocking
python -m josephus.test_utils.record_llm --scenario "new_endpoint"

# Validate fixtures match current schemas
pytest tests/fixtures/validate.py
```

---

## 11. Success Metrics

| Metric | Target (6 months) |
|--------|-------------------|
| Time to first docs | < 10 minutes |
| Doc accuracy (LLM-judge) | > 85% |
| Doc accuracy (user rating) | > 4/5 stars |
| PR detection F1 score | > 90% |
| User retention (monthly) | > 60% |
| Regeneration rate | < 20% |
| Repos documented | 1,000+ |

---

## 12. Competitive Positioning

```
                    │ Customer-Facing Focus
                    │
         Josephus   │   Mintlify
              ●     │      ●
                    │
────────────────────┼────────────────────
  Auto-Generated    │            Manual
                    │
        DeepWiki    │    GitBook
           ●        │       ●
                    │
                    │ Developer Focus
```

**Our niche:** Auto-generated, customer-facing documentation with CI/CD integration.

---

## 13. Next Steps

1. [x] Review and refine these requirements
2. [x] Research architecture patterns (see `ARCHITECTURE_PATTERNS.md`)
3. [ ] Make decisions on remaining open questions
4. [ ] Create GitHub repository
5. [ ] Set up project structure and CI
6. [ ] Begin Phase 1 implementation

---

## Related Documents

- [`ARCHITECTURE_PATTERNS.md`](./ARCHITECTURE_PATTERNS.md) - Patterns extracted from Repomix, DeepWiki-Open, Probot

---

*Document version: 0.6*
*Last updated: 2026-02-05*
