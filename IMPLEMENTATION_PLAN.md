# Josephus: UI Documentation — Implementation Plan

## Context

Josephus currently generates developer-facing documentation from source code. The generated docs read like technical architecture guides, not customer-facing help articles. The pivot: generate **UI documentation** by crawling a live deployment with Playwright (screenshots + DOM extraction) and combining that with source code analysis. Every screen gets documented with screenshots. Complex screens with tabs/sub-sections get sub-articles.

**Key shift**: Code analysis becomes *supplementary*. The primary understanding comes from **visually inspecting the live product** via Playwright browser automation.

PR #110 (large-repo handling) will be closed — reuse per-page generation pattern conceptually but don't merge.

---

## Architecture Overview

```
User provides: repo + deployment_url + auth_cookies + guidelines
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
  RepoAnalyzer          FrontendAnalyzer       SiteCrawler
  (existing code)       (route extraction)     (Playwright)
        │                     │                     │
        │                     └──────────┬──────────┘
        │                                │
        │                     Screen-to-code matching
        │                                │
        └────────────────────────────────┤
                                         ▼
                                  UIDocPlanner (LLM)
                                  → terminology extraction
                                  → structure planning
                                         │
                                         ▼
                                  UIDocGenerator (LLM per-screen)
                                  → screenshot + DOM + code context → markdown
                                         │
                                         ▼
                                  GitHubClient (commit markdown + screenshots as PR)
```

### Dual Analysis Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    UI CRAWL (Primary Input)                       │
├─────────────────────────────────────────────────────────────────┤
│  1. Launch Playwright browser                                    │
│  2. Inject auth (cookie/token)                                   │
│  3. Pre-crawl auth validation (check for login redirect / 401)   │
│  4. BFS crawl from base URL (SPA-aware: click + wait, not just   │
│     <a href> scraping)                                           │
│  5. Per screen: screenshot + structured DOM extraction            │
│  6. URL template deduplication (/users/1, /users/2 → one doc)    │
│  7. Produce SiteInventory (all CrawledPages)                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              CODE ANALYSIS (Supplementary Input)                  │
├─────────────────────────────────────────────────────────────────┤
│  1. Fetch repository via GitHub API                              │
│  2. Frontend-first file prioritization                           │
│  3. Route map extraction (URL → component mapping)               │
│  4. Match crawled screens to source files                        │
│  5. Produce RepoAnalysis with screen-to-code mapping             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    LLM PIPELINE                                   │
├─────────────────────────────────────────────────────────────────┤
│  1. Terminology pass: batch screenshots → glossary               │
│  2. Planning pass: screen inventory + code → doc structure       │
│  3. Per-screen generation (multimodal):                          │
│     - Screenshot (high detail)                                   │
│     - DOM extraction text                                        │
│     - Matched source files                                       │
│     - Terminology dict + plan context                            │
│  4. Output: markdown files with screenshot references            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Module Structure

### New Module: `src/josephus/crawler/`

```
crawler/
├── __init__.py
├── models.py              # CrawlConfig, AuthConfig, CrawledPage, DOMData, SiteInventory, ScreenshotConfig
├── browser.py             # BrowserManager - Playwright lifecycle, context creation
├── auth.py                # AuthInjector - cookie/token injection + pre-crawl validation
├── dom_extractor.py       # DOMExtractor - structured extraction (see details below)
├── page_crawler.py        # PageCrawler - single page: screenshot + DOM + link discovery
├── site_crawler.py        # SiteCrawler - BFS with SPA support + URL deduplication
└── screenshot.py          # ScreenshotManager - save, compress, encode, filename generation
```

### Key Data Models (`crawler/models.py`)

- **`CrawlConfig`**: base_url, auth, max_pages (50), max_depth (4), viewport, wait times, URL include/exclude patterns, screenshot config
- **`AuthConfig`**: strategy (cookies | token_header), cookies list, bearer token
- **`ScreenshotConfig`**: format (png | jpeg | webp), quality (for jpeg/webp, default 85), max_width (default 1280)
- **`DOMData`**: headings, nav_links, interactive_elements, form_fields, visible_text, aria_landmarks, detected_tabs, detected_modals
- **`InteractiveElement`**: element_type, label, action, target_url, CSS selector
- **`CrawledPage`**: url, title, nav_path, screenshot_bytes, dom (DOMData), page_type, parent_url, depth
- **`SiteInventory`**: base_url, pages list, total_pages, crawl_duration

### DOM Extraction Targets (`crawler/dom_extractor.py`)

The DOM extractor produces structured data that feeds into the LLM alongside screenshots:

- **Headings hierarchy** (`h1`-`h6`) — document structure
- **Navigation links** (text + href) — site structure and screen relationships
- **Interactive elements** (buttons, links, selects) with their labels — what actions are available
- **Form structure** (fields, labels, placeholders, validation messages) — data entry points
- **Visible text content** (excluding scripts/styles/hidden elements) — what the user reads
- **ARIA landmarks and roles** — accessibility-derived structure
- **Tab/modal indicators** (`[role="tab"]`, `[aria-selected]`, common framework selectors like `.MuiTab-root`, `.ant-tabs-tab`, `.nav-tabs`)

### Crawl Strategy (`crawler/site_crawler.py`)

BFS from base_url with SPA awareness:

1. Navigate to page, wait for network idle
2. Extract DOM structure
3. Take screenshot (configurable format)
4. Discover outbound links — **not just `<a href>` scraping**: follow `onclick` navigations via Playwright's click-and-wait, listen for URL changes via `hashchange`/`popstate`
5. **URL template deduplication**: detect parameterized URLs (`/users/123` → `/users/:id`) by comparing DOM structure similarity across pages with same path pattern. Only document one instance per template.
6. Enqueue unvisited URLs, respecting max_depth and max_pages
7. URL include/exclude patterns filter scope

### Auth Strategy (`crawler/auth.py`)

- Cookie injection into browser context before navigation
- Bearer token injection via extra HTTP headers
- **Pre-crawl auth validation**: navigate to base URL, check for redirect to login page or 401 response. Fail fast with clear error message instead of crawling an empty/login-only site.

---

### New File: `src/josephus/analyzer/frontend.py`

Route extraction and screen-to-code matching (single file in existing `analyzer/` module):

- `prioritize_frontend_files(files)` — routes/pages/components sorted first
- `extract_route_map(files, framework)` — parse Next.js `app/`, React Router, Vue Router configs → URL→component mapping
- `match_screens_to_code(screens, files, route_map)` — map `CrawledPage` URLs to source files
- Framework auto-detection from `package.json` dependencies

---

### Adapted Modules

#### `llm/provider.py` — Message-based multimodal API

Refactor to use a content-block model that mirrors how the Anthropic API actually works:

- Introduce `ContentBlock` union type: `TextBlock(text)` | `ImageBlock(data, media_type, detail)`
- Introduce `Message(role, content: list[ContentBlock])`
- Refactor `ClaudeProvider` to accept `list[Message]`
- Keep backward-compatible `generate(prompt, system)` wrapper that builds a single text message

This is a simplification (closer to the real API), not added complexity.

#### `generator/ui_planning.py` — Screen-inventory planning + terminology

- `UIDocPlanner` class (new file, not added to existing `planning.py`)
- Terminology extraction pass: batch low-detail screenshots → glossary of UI terms
- Structure planning pass: screen manifest + compressed code → `DocStructurePlan` with `PlannedScreen` entries (screen_url, screenshot_path, source_files, sub_pages)
- Complex screens (3+ tabs, substantial sub-sections) get sub-articles
- New templates: `ui_planning_system.xml.j2`, `ui_planning.xml.j2`, `ui_terminology.xml.j2`

#### `generator/ui_docs.py` — Multimodal per-screen generation

- `UIDocGenerator` class (new file)
- Always per-page, multimodal (screenshot image block + text prompt)
- Inputs: high-detail screenshot, DOM data, matched source files, terminology dict, plan context
- Output: markdown with `![Screenshot](screenshots/screen-name.ext)` references
- New templates: `ui_system.xml.j2`, `ui_page.xml.j2`

#### `core/service.py` — New UIDocService

- `UIDocService` alongside existing `JosephusService` (not replacing it)
- Pipeline: crawl → analyze → plan (terminology + structure) → generate → collect results

#### `core/config.py` — Crawler settings

- `playwright_headless`, `crawler_max_pages`, `crawler_max_depth`, `crawler_timeout_ms`
- `screenshot_format`, `screenshot_quality`, `screenshot_max_width`
- `screenshot_dir` (temp directory for crawl output)

#### `github/client.py` — Binary file support

- Extend `commit_files()` to support binary content (screenshots as base64 blobs)
- Size warning if screenshots exceed 10MB total per PR (recommend Git LFS for larger repos)

#### `worker/tasks.py` — New Celery task

- `generate_ui_documentation` task

#### `api/routes/api_v1.py` — New endpoint

- `POST /api/v1/generate-ui`

#### `cli/commands/generate.py` — New CLI options

- `--deployment-url`, `--auth-cookie`, `--auth-header` flags
- `--mode ui` flag

---

## Configuration

### `.josephus.yml` additions

```yaml
# Deployment to crawl
deployment:
  url: "https://app.example.com"
  auth:
    strategy: cookies          # cookies | token_header
    cookies:
      - name: session
        value: "abc123"
        domain: ".example.com"
    # OR
    bearer_token: "eyJ..."

# Crawler settings
crawl:
  max_pages: 50
  max_depth: 4
  include_patterns:
    - "/dashboard/**"
    - "/settings/**"
  exclude_patterns:
    - "/admin/**"
    - "/api/**"

# Screenshot settings
screenshots:
  format: png                  # png | jpeg | webp
  quality: 85                  # only applies to jpeg/webp (1-100)
  max_width: 1280              # resize if wider
```

---

## Token Budget for Vision

- `detail="low"`: ~85 tokens per image (resized to 768px)
- `detail="high"`: up to ~1,590 tokens per image
- Strategy: `detail="low"` for planning/terminology passes, `detail="high"` for the specific screen being documented
- Per-screen call: 1 main screenshot (high) + 3 tab screenshots (low) ~ 1,845 tokens for images — leaves ~170K for code context and output

---

## New Dependencies

```toml
"playwright>=1.48.0"  # Browser automation
```

Post-install: `playwright install chromium`

---

## Phased Implementation

### Phase 1: Crawler Foundation (standalone, no LLM)

**Goal**: Crawl a URL → `SiteInventory` with screenshots + structured DOM data. No LLM involvement.

**Create**:
- All files in `src/josephus/crawler/`
- Tests: `test_crawler_models.py`, `test_dom_extractor.py`, `test_site_crawler.py`, `test_screenshot_manager.py`
- Bundled test fixture: minimal static HTML site (5 pages, tabs, modal) in `tests/fixtures/test_site/`, served by Python's `http.server` during tests

**Key capabilities**:
- SPA-aware link discovery from day one (click + wait, not just `<a href>`)
- URL template deduplication (detect `/items/1` and `/items/2` as same template)
- Pre-crawl auth validation
- Configurable screenshot format (PNG default, JPEG/WebP with quality setting)

**Done when**: `SiteCrawler` crawls the test fixture site, produces correct `CrawledPage` objects with screenshots and structured DOM data. Cookie auth injection works.

### Phase 2: Frontend Code Analysis + LLM Multimodal Support

Two parallel workstreams:

**2a. Frontend Analysis** (`analyzer/frontend.py`):
- `prioritize_frontend_files(files)` — routes/pages/components first
- `extract_route_map(files, framework)` — parse Next.js `app/`, React Router, Vue Router
- `match_screens_to_code(screens, files, route_map)` — map crawled URLs to source files
- Framework auto-detection from `package.json`
- Tests with fixture source files for each supported framework

**2b. Multimodal LLM refactor** (`llm/provider.py`):
- `ContentBlock` type: `TextBlock` | `ImageBlock`
- `Message(role, content: list[ContentBlock])`
- Refactor `ClaudeProvider` to use message-based API
- Backward-compatible `generate(prompt, system)` wrapper
- Tests for multimodal message construction

**Done when**: Route extraction works on fixture repos. LLM provider can send screenshot+text prompts.

### Phase 3: Planning + Terminology

**Goal**: LLM plans doc structure from screens + code, extracts consistent terminology.

**Create**:
- `src/josephus/generator/ui_planning.py` — `UIDocPlanner`
- Templates: `ui_planning_system.xml.j2`, `ui_planning.xml.j2`, `ui_terminology.xml.j2`
- Tests: `test_ui_planning.py`

**Pipeline**:
1. Terminology pass: batch low-detail screenshots → glossary of UI terms
2. Structure planning pass: screen inventory + compressed code + glossary → `DocStructurePlan`

**Done when**: Planner produces reasonable doc structure + glossary from 10+ crawled screens.

### Phase 4: Per-Screen Multimodal Generation

**Goal**: End-to-end local generation: URL → markdown docs with screenshots.

**Create**:
- `src/josephus/generator/ui_docs.py` — `UIDocGenerator`
- Templates: `ui_system.xml.j2`, `ui_page.xml.j2`
- `UIDocService` in `core/service.py`
- Tests: `test_ui_generator.py`

**Modify**:
- `core/config.py` — crawler settings
- `.josephus.yml` schema — `deployment`, `crawl`, `screenshots` sections
- CLI: `--deployment-url`, `--auth-cookie`, `--auth-header`, `--mode ui`

**Done when**: End-to-end: crawl → analyze → plan → generate docs with screenshot references, running locally via CLI.

### Phase 5: GitHub Integration + API

**Goal**: Wire into Celery/GitHub. PRs with docs + screenshots.

**Modify**:
- `github/client.py` — binary file support in `commit_files()`
- `worker/tasks.py` — new `generate_ui_documentation` task
- `api/routes/api_v1.py` — new `POST /api/v1/generate-ui` endpoint

**Done when**: POST to `/api/v1/generate-ui` → PR created with docs + screenshots in target repo.

### Phase 6 (future): Interactions, Flows & Updates

- Tab/modal click-and-capture (role-based, ARIA, framework-specific selectors)
- Multi-step user flow documentation ("How to create a scan")
- Form login auth strategy
- Sub-section detection for complex pages
- **Incremental updates**: re-crawl, diff screenshots, update only changed docs
- PR-triggered doc updates (compare crawl before/after UI changes)
- Eval framework adaptation for UI docs (screenshot quality, screen coverage, visual accuracy metrics)

---

## What to Remove

- `src/josephus/analyzer/audience.py` — audience is always end-users for UI docs
- Single-shot generation path in `generator/docs.py` — keep per-page only
- PR #110 branch — close the PR

---

## Output Structure Example

```
docs/
  index.md                         # Product overview, navigation
  getting-started.md               # First-time user guide
  dashboard.md                     # Dashboard screen docs
  dashboard/
    analytics.md                   # Dashboard > Analytics tab
    reports.md                     # Dashboard > Reports tab
  settings.md                      # Settings screen docs
  settings/
    general.md                     # Settings > General tab
    integrations.md                # Settings > Integrations tab
  glossary.md                      # Terminology definitions
  screenshots/
    dashboard.png
    dashboard-analytics-tab.png
    dashboard-reports-tab.png
    settings-general.png
    settings-integrations.png
```

---

## Verification

After each phase:
1. `ruff check . && ruff format .`
2. `pytest tests/unit -v` (no regressions)
3. Phase-specific integration test against bundled test fixture site
4. Phase 4: End-to-end test generating docs for the test fixture
5. Phase 5: Test PR creation on a test repo
