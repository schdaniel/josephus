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

### Documentation Platforms (Foundations)

| Platform | License | Best For | Considerations |
|----------|---------|----------|----------------|
| **Docusaurus** | MIT (Free) | Full control, React teams | Self-host, requires React knowledge |
| **GitBook** | Freemium | Mixed teams, collaboration | Per-seat pricing, less customizable |
| **Mintlify** | Commercial | Beautiful API docs | $150+/mo, opinionated structure |
| **MkDocs** | MIT (Free) | Python teams, simplicity | Less modern UI, limited interactivity |
| **Nextra** | MIT (Free) | Next.js teams | Lighter than Docusaurus |

### Recommendation: Build on Docusaurus

**Rationale:**
1. **Free & open source** - No licensing costs or vendor lock-in
2. **Battle-tested** - Powers React Native, Supabase, Figma docs
3. **Versioning built-in** - Critical for product documentation
4. **MDX support** - Markdown + React components
5. **Large ecosystem** - Plugins, themes, community support
6. **SEO optimized** - Important for customer-facing docs

**Alternative consideration:** Nextra if we want a lighter footprint with Next.js.

---

## 3. Core Features

### 3.1 Onboarding Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                     ONBOARDING FLOW                              │
├─────────────────────────────────────────────────────────────────┤
│  1. GitHub OAuth  →  2. Select Repo  →  3. Configure Guidelines │
│                                                │                 │
│                                                ▼                 │
│  6. Review & Edit  ←  5. Generate Docs  ←  4. Analyze Codebase │
│         │                                                        │
│         ▼                                                        │
│  7. Commit to Repo (PR)  →  8. Install GitHub App (CI)          │
└─────────────────────────────────────────────────────────────────┘
```

**Steps:**
1. **GitHub Integration** - OAuth flow to connect account
2. **Repository Selection** - Choose repo(s) to document
3. **Configuration** - Natural language guidelines (see 3.4)
4. **Codebase Analysis** - AI scans and understands the codebase
5. **Documentation Generation** - Creates initial doc structure
6. **Review & Edit** - User reviews, edits, approves
7. **Commit to Repo** - PR with docs committed to `/docs` folder
8. **CI Installation** - Install GitHub App for PR monitoring

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

### 3.3 PR Documentation Updates (CI/CD)

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
│  │  - GitHub OAuth                                              │      │
│  │  - Webhook handlers                                          │      │
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
│  │                   Git-Based Doc Storage                       │      │
│  │  - Docs committed to user's repo (/docs or configurable)     │      │
│  │  - Docusaurus config committed alongside                     │      │
│  │  - User deploys via GitHub Pages / Vercel / Netlify          │      │
│  └──────────────────────────────────────────────────────────────┘      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Technical Requirements

### 5.1 Tech Stack (Proposed)

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Backend API** | Python (FastAPI) | Strong AI/ML ecosystem, async support |
| **Frontend** | Next.js + TypeScript | Modern React, SSR, great DX |
| **Database** | PostgreSQL | Reliable, JSON support, full-text search |
| **Vector Store** | pgvector or Pinecone | RAG for codebase understanding |
| **Queue** | Redis + BullMQ | Job processing for doc generation |
| **Doc Platform** | Docusaurus | See Section 2 recommendation |
| **LLM Provider** | Multi-provider | Claude, GPT-4, Gemini (configurable) |
| **Doc Storage** | Git (user's repo) | Docs as code, no vendor lock-in |
| **API Hosting** | Vercel/Railway | Easy deployment, scalable |

### 5.2 GitHub Integration

**GitHub App Permissions Required:**
- `contents: read` - Read repository files
- `pull_requests: write` - Comment on and modify PRs
- `metadata: read` - Repository metadata
- `checks: write` - Create check runs for doc status

**Webhook Events:**
- `pull_request` - opened, synchronize, closed
- `push` - to main/master (for doc site rebuilds)
- `installation` - app installed/uninstalled

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

**Recommended:** Claude 3.5 Sonnet for generation, Claude Haiku for classification

### 5.4 Security Requirements

- [ ] OAuth tokens encrypted at rest
- [ ] No storage of source code (process in memory, discard)
- [ ] Audit logging for all actions
- [ ] SOC 2 compliance path (if B2B SaaS)
- [ ] Private repo support with explicit permissions
- [ ] Rate limiting on API and LLM calls

---

## 6. User Experience

### 6.1 Onboarding UI Flow

```
Screen 1: Landing
├── "Connect GitHub" CTA
│
Screen 2: Repository Selection
├── List connected repos
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
Screen 6: Commit & Setup CI
├── Preview PR with docs changes
├── Choose target branch / folder path
├── Create PR button
├── Install GitHub App for ongoing PR monitoring
├── (Optional) Guide for GitHub Pages / Vercel setup
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
- [ ] GitHub OAuth integration
- [ ] Single repo onboarding
- [ ] Basic doc generation (README → Getting Started)
- [ ] Manual trigger only (no CI)
- [ ] Single LLM provider (Claude)
- [ ] Commit Docusaurus docs to user's repo via PR

### Phase 2: Core Product
- [ ] Full onboarding wizard
- [ ] Comprehensive doc generation
- [ ] Natural language configuration
- [ ] GitHub App for PR detection
- [ ] Auto-commit doc updates to PRs
- [ ] Multi-provider LLM support

### Phase 3: Scale & Polish
- [ ] Custom domains
- [ ] Team collaboration features
- [ ] Doc versioning
- [ ] Analytics (doc usage, coverage)
- [ ] API for programmatic access
- [ ] CLI tool for local preview

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
1. **Docusaurus vs custom?** Build on Docusaurus or custom doc renderer?
2. **Vector DB choice?** pgvector (simpler) vs Pinecone (managed)?
3. ~~**Doc storage?**~~ **DECIDED:** Git-based - docs committed to user's repo
4. **Real-time vs batch?** Generate on-demand or pre-compute?

### Scope Questions
1. **API docs focus?** Should we specialize in API documentation first?
2. **Framework support?** Priority frameworks (React, Node, Python, etc.)?
3. **Existing docs?** How to handle repos with existing documentation?

---

## 9. Success Metrics

| Metric | Target (6 months) |
|--------|-------------------|
| Time to first docs | < 10 minutes |
| Doc accuracy (user rating) | > 4/5 stars |
| PR doc detection accuracy | > 90% |
| User retention (monthly) | > 60% |
| Repos documented | 1,000+ |

---

## 10. Competitive Positioning

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

## Next Steps

1. [ ] Review and refine these requirements
2. [ ] Make decisions on open questions
3. [ ] Create technical design document
4. [ ] Set up project structure and CI
5. [ ] Begin Phase 1 implementation

---

*Document version: 0.2*
*Last updated: 2026-02-05*
