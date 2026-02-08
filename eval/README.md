# Evaluation Dataset

This directory contains the evaluation dataset for measuring documentation quality and PR detection accuracy.

## Structure

```
eval/
├── repos.yaml           # Repository configuration
├── repos/               # Repository snapshots to evaluate
│   ├── small-cli-tool/  # Simple: <50 files
│   ├── medium-api/      # Medium: 50-200 files
│   └── large-monorepo/  # Large: 500+ files
├── ground_truth/        # Reference documentation
│   └── <repo-name>/
│       ├── crawled_docs/    # Crawled documentation from GitHub
│       └── annotations.json # Feature coverage checklist
├── pr_scenarios/        # PRs with known doc relevance
│   ├── should_update/   # PRs that need doc changes
│   ├── should_ignore/   # PRs that don't (refactoring, tests)
│   └── labels.json      # Ground truth labels
└── guidelines_variations/ # Different user configs to test
```

## Running Evaluations

```bash
# Run quick evaluation (limited samples)
python -m josephus.eval --dataset eval --quick

# Run full evaluation
python -m josephus.eval --dataset eval --verbose

# Check metrics against thresholds
python -m josephus.eval --dataset eval --check \
    --coverage-min 0.85 \
    --accuracy-min 0.80 \
    --pr-f1-min 0.88

# Compare to baseline
python -m josephus.eval --dataset eval --compare-baseline baseline.json

# Save as new baseline
python -m josephus.eval --dataset eval --save-baseline baseline.json
```

## Adding New Repos

1. Add repository configuration to `repos.yaml`:
   ```yaml
   my-repo:
     url: https://github.com/owner/repo.git
     language: python
     size: small  # small (<50 files), medium (50-200), large (500+)
     description: "Brief description"
     docs_url: https://docs.example.com/  # Public docs URL (for reference)
     docs_path: docs  # Path to docs in the repo
     # Optional: docs_repo if docs are in a different repo
     # docs_repo: owner/docs-repo
     # Optional: docs_format if not markdown
     # docs_format: asciidoc  # or lektor
     # Optional: exclude specific directories
     # exclude_dirs:
     #   - contributing
     #   - internal
   ```

2. Crawl the documentation:
   ```bash
   python -m josephus.eval.crawl --repos my-repo
   ```

3. Create `ground_truth/<name>/annotations.json` with expected items:
   ```json
   {
     "expected_items": ["function_a", "ClassB", "endpoint_c"],
     "categories": {
       "api_endpoints": ["GET /api/v1/items", "POST /api/v1/items"],
       "core_classes": ["ItemService", "ItemRepository"]
     }
   }
   ```

## Crawling Documentation

The `josephus.eval.crawl` module fetches documentation from GitHub repositories:

```bash
# List all repos with their doc sources and status
python -m josephus.eval.crawl --list

# Crawl all repos
python -m josephus.eval.crawl

# Crawl specific repos
python -m josephus.eval.crawl --repos ackee miniflux

# Force re-crawl (overwrite existing)
python -m josephus.eval.crawl --repos ackee --force

# Limit files per repo (default: 200)
python -m josephus.eval.crawl --max-files 100
```

Supported documentation formats:
- **markdown**: `.md`, `.mdx`, `.markdown` files (default)
- **asciidoc**: `.adoc`, `.asciidoc`, `.asc` files
- **lektor**: `contents.lr` files (Lektor CMS format)

## PR Scenarios

Add PR diff files to `pr_scenarios/should_update/` or `pr_scenarios/should_ignore/`,
then update `labels.json`:

```json
{
  "repo-name": {
    "scenario-1": true,   // Should update docs
    "scenario-2": false   // Should not update docs
  }
}
```

## Metrics

### Documentation Quality
- **Coverage Score**: % of public APIs/features documented (target: >90%)
- **Accuracy Score**: LLM-as-judge comparing to ground truth (target: >85%)
- **Hallucination Rate**: Claims not supported by code (target: <5%)
- **Readability**: Flesch-Kincaid grade level (target: 8-10)
- **Structure Score**: Correct headings, code blocks, links (target: >95%)

### PR Detection
- **Precision**: True positives / (True + False positives) (target: >85%)
- **Recall**: True positives / (True + False negatives) (target: >95%)
- **F1 Score**: Harmonic mean of precision/recall (target: >90%)
- **Latency**: Time from webhook to decision (target: <30s)
