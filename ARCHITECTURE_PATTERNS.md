# Architecture Patterns Research

> Patterns extracted from Repomix, DeepWiki-Open, Probot, and other relevant projects.

---

## 1. Repository Packing (from Repomix)

### Key Patterns to Adopt

**File Filtering Stack:**
```
.gitignore → .ignore → .repomixignore → explicit includes/excludes
```
- Respect existing ignore files automatically
- Allow project-specific overrides via `.josephus.yml`
- Support glob patterns for fine-grained control

**Security-First Scanning:**
- Integrate secret detection (Secretlint or similar) before processing
- Never send credentials/tokens to LLM
- Warn users if sensitive files detected

**Token-Aware Processing:**
- Count tokens per file and total
- Stay within LLM context windows
- Prioritize important files when context limited

**Code Compression (Tree-sitter):**
- Extract structural elements (function signatures, class definitions)
- Reduce token usage while preserving architecture understanding
- Useful for large codebases that exceed context limits

**Output Format - XML for Claude:**
> "XML tags can help parse prompts more accurately, leading to higher-quality outputs."

Structure:
```xml
<repository>
  <file_summary>...</file_summary>
  <directory_structure>...</directory_structure>
  <files>
    <file path="src/index.ts">...</file>
  </files>
  <instruction>...</instruction>
</repository>
```

### Patterns to Consider Later
- Git history inclusion (`--include-logs`) for understanding evolution
- Remote repository processing without local clone
- Composition with Unix tools (find, grep) for advanced selection

---

## 2. RAG Pipeline (from DeepWiki-Open)

### Processing Pipeline
```
1. Repository Ingestion (clone/fetch)
       ↓
2. Code Structure Analysis (parse, identify relationships)
       ↓
3. Embedding Generation (vectorize for semantic search)
       ↓
4. Documentation Generation (LLM + context)
       ↓
5. Output (markdown + diagrams)
```

### Key Patterns to Adopt

**Configuration-Driven Architecture:**
```
generator.json  → LLM provider settings
embedder.json   → Embedding/chunking config
repo.json       → File filtering, size limits
```
- Externalize behavior in config files
- No code changes needed for new models
- Easy to swap providers

**Multi-Provider Abstraction:**
```python
# Provider interface
class LLMProvider:
    def generate(prompt, context) -> str
    def embed(text) -> List[float]

# Implementations
class ClaudeProvider(LLMProvider): ...
class OpenAIProvider(LLMProvider): ...
class OllamaProvider(LLMProvider): ...  # Local/self-hosted
```

**Configurable Text Splitting:**
- Chunk size and overlap as config parameters
- Language-aware splitting (respect function boundaries)
- Balance between context and retrieval precision

**Environment Variable Overrides:**
```bash
DEEPWIKI_EMBEDDER_TYPE=openai  # Switch embedding provider
OPENAI_BASE_URL=https://...    # Custom endpoint for enterprise
LOG_LEVEL=debug                # Operational observability
```

### Patterns for Later Phases
- "DeepResearch" multi-turn investigation (iterative retrieval)
- Mermaid diagram generation for architecture visualization
- Private repo authentication via PATs

---

## 3. GitHub App / Webhook Handling (from Probot et al.)

### Core Architecture
```
GitHub Event → Webhook → Signature Verify → Event Router → Handler → GitHub API
```

### Key Patterns to Adopt

**Use Probot Framework (Node.js):**
- Battle-tested, maintained by GitHub
- Built-in webhook handling
- Typed event payloads
- Easy testing utilities

**Or Build Custom (Python/FastAPI):**
```python
@app.post("/webhook")
async def handle_webhook(request: Request):
    # 1. Verify signature (HMAC)
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_signature(await request.body(), signature):
        raise HTTPException(401)

    # 2. Parse event
    event_type = request.headers.get("X-GitHub-Event")
    payload = await request.json()

    # 3. Route to handler
    if event_type == "pull_request":
        await handle_pr(payload)
    elif event_type == "installation":
        await handle_installation(payload)
```

**HMAC Signature Verification (Critical):**
```python
import hmac
import hashlib

def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

**Event Types to Handle:**
| Event | Trigger | Our Action |
|-------|---------|------------|
| `installation` | App installed/removed | Setup/cleanup project |
| `pull_request.opened` | New PR | Analyze for doc relevance |
| `pull_request.synchronize` | PR updated | Re-analyze changes |
| `push` (to main) | Code merged | Rebuild full docs if needed |

**Stateless Execution:**
- Each webhook = independent job
- No in-memory state between requests
- Use database for persistence
- Enables horizontal scaling

**Token Management:**
```python
# Generate installation access token (short-lived)
async def get_installation_token(installation_id: int) -> str:
    jwt = generate_app_jwt(app_id, private_key)
    response = await github_api.post(
        f"/app/installations/{installation_id}/access_tokens",
        headers={"Authorization": f"Bearer {jwt}"}
    )
    return response["token"]
```

### Performance Patterns (from AI review bots)
- **Async processing:** Don't block webhook response
- **Job queue:** Offload doc generation to background workers
- **Caching:** Cache repo analysis between PR updates
- **Incremental analysis:** Only analyze changed files for PR updates

---

## 4. Recommended Architecture for Josephus

### System Components

```
┌─────────────────────────────────────────────────────────────────────┐
│                         JOSEPHUS SYSTEM                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐     ┌─────────────────┐     ┌─────────────┐       │
│  │   Web App   │     │  GitHub App     │     │   Workers   │       │
│  │  (Next.js)  │     │  (Webhooks)     │     │  (Celery)   │       │
│  └──────┬──────┘     └────────┬────────┘     └──────┬──────┘       │
│         │                     │                     │               │
│         └─────────────────────┼─────────────────────┘               │
│                               │                                      │
│                               ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                     FastAPI Backend                           │   │
│  │                                                               │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │   │
│  │  │ Webhook     │  │ API         │  │ GitHub              │  │   │
│  │  │ Handler     │  │ Routes      │  │ Client              │  │   │
│  │  │ (verify +   │  │ (REST)      │  │ (Octokit/PyGithub)  │  │   │
│  │  │  route)     │  │             │  │                     │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
│                                 │                                    │
│         ┌───────────────────────┼───────────────────────┐           │
│         │                       │                       │           │
│         ▼                       ▼                       ▼           │
│  ┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐    │
│  │  Repo       │    │  Doc Generation  │    │  PR Analysis    │    │
│  │  Analyzer   │    │  Engine          │    │  Service        │    │
│  │             │    │                  │    │                 │    │
│  │  - Repomix  │    │  - LLM Provider  │    │  - Diff parser  │    │
│  │    patterns │    │    abstraction   │    │  - Relevance    │    │
│  │  - Tree-    │    │  - RAG pipeline  │    │    classifier   │    │
│  │    sitter   │    │  - Config-driven │    │  - Incremental  │    │
│  │  - Secret   │    │                  │    │    updates      │    │
│  │    scanning │    │                  │    │                 │    │
│  └─────────────┘    └──────────────────┘    └─────────────────┘    │
│         │                       │                       │           │
│         └───────────────────────┼───────────────────────┘           │
│                                 │                                    │
│                                 ▼                                    │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                      Data Layer                               │   │
│  │                                                               │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │   │
│  │  │ PostgreSQL  │  │ pgvector    │  │ Redis               │  │   │
│  │  │ (projects,  │  │ (embeddings │  │ (job queue,         │  │   │
│  │  │  configs)   │  │  for RAG)   │  │  caching)           │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Webhook framework** | Custom FastAPI | Python ecosystem for AI/ML, async native |
| **LLM abstraction** | Config-driven providers | Easy to swap/add providers |
| **Repo analysis** | Repomix patterns + Tree-sitter | Proven approach, token-efficient |
| **Vector store** | pgvector | Simpler ops (no separate service) |
| **Job processing** | Celery + Redis | Mature, scalable background jobs |
| **Caching** | Redis | Fast, handles both cache and queue |

### Configuration Files

```
.josephus.yml          # User's repo - guidelines, scope, style
config/
  generator.json       # LLM provider settings
  embedder.json        # Embedding/chunking config
  repo_defaults.json   # Default file filtering rules
```

---

## 5. Implementation Priority

### Phase 1 (MVP) - Core Patterns Needed:
1. ✅ GitHub App webhook handling (signature verify, event routing)
2. ✅ Basic repo analysis (file listing, content extraction)
3. ✅ Single LLM provider (Claude)
4. ✅ Markdown generation
5. ✅ Git commit via GitHub API

### Phase 2 - Enhanced Patterns:
1. ⬜ RAG pipeline with pgvector
2. ⬜ Tree-sitter code compression
3. ⬜ Multi-provider LLM abstraction
4. ⬜ PR diff analysis and relevance classification
5. ⬜ Incremental doc updates

### Phase 3 - Scale Patterns:
1. ⬜ Celery workers for background processing
2. ⬜ Caching layer for repo analysis
3. ⬜ Secret scanning integration
4. ⬜ Token counting and context management

---

## Sources

- [Repomix](https://github.com/yamadashy/repomix) - Repository packing patterns
- [DeepWiki-Open](https://github.com/AsyncFuncAI/deepwiki-open) - RAG pipeline architecture
- [Probot](https://github.com/probot/probot) - GitHub App framework
- [Claude Hub](https://claude-did-this.com/claude-hub/overview) - AI-powered GitHub bot patterns
- [Palantir Policy-Bot](https://github.com/palantir/policy-bot) - PR policy enforcement patterns

---

*Document version: 0.1*
*Last updated: 2026-02-05*
