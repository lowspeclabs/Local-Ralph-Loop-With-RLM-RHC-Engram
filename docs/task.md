Here’s a **benchmark-friendly spec** for a “simple Python app” that’s still **complicated enough to stress-test an LLM** across architecture, edge-cases, testing, and correctness.

---

# Spec: “NetWatch” — A Concurrent Network Check + Report CLI

## 1) Goal

Build a Python CLI that:

- Reads a list of targets (hosts/URLs + checks) from a config file
- Runs multiple types of checks concurrently (DNS, TCP connect, HTTP GET)
- Produces deterministic output artifacts (JSON + HTML report)
- Maintains a small local history database for trend summaries
- Has a clean plugin-style design for adding new checks

This is “simple” (a monitoring tool) but forces real-world complexity: **I/O, concurrency, retries, timeouts, structured output, persistence, testing, and packaging**.

---

## 2) Core User Stories

1. As a user, I can run `netwatch run config.yml` and get a report.
2. I can choose concurrency, timeout, retries, and “fail-fast”.
3. I can store results locally and query “last 24h” uptime summary.
4. I can extend checks by adding a new plugin file.

---

## 3) CLI Commands

### `netwatch run <config.yml>`

Runs checks and writes outputs:

- `./out/latest.json`
- `./out/latest.html`
- optionally persists to SQLite

Key flags:

- `--out ./out`
- `--db ./netwatch.db` (optional)
- `--concurrency 50`
- `--timeout 2.5`
- `--retries 2`
- `--retry-backoff 0.2` (seconds, exponential)
- `--fail-fast` (stop after N critical failures)
- `--format json|html|both`
- `--seed 123` (forces deterministic ordering of output)

### `netwatch summary --db ./netwatch.db --since 24h`

Shows:

- uptime %
- avg latency
- error breakdown
- top 10 worst endpoints

### `netwatch validate <config.yml>`

Validates config schema + prints resolved plan (what will run).

---

## 4) Config Format (YAML)

```yaml
project: "HomeLab Checks"
defaults:
  timeout: 2.0
  retries: 2
  retry_backoff: 0.2
  tags: ["prod"]

targets:
  - name: "router"
    host: "192.168.1.1"
    checks:
      - type: "tcp"
        port: 443

  - name: "dns-google"
    host: "8.8.8.8"
    checks:
      - type: "dns"
        query: "example.com"
        record_type: "A"

  - name: "site"
    url: "https://example.com"
    checks:
      - type: "http"
        method: "GET"
        expect_status: [200, 301, 302]
        expect_contains: "Example Domain"
```

Rules:

- A target has either `host` or `url`
- Each check can override defaults
- Allow tags for filtering runs later

---

## 5) Checks (Minimum Set)

### A) DNS Check

- Input: `query`, `record_type`
- Behavior: resolve using system resolver
- Metrics: `latency_ms`, `resolved_values[]`
- Failure cases: NXDOMAIN, timeout, empty answer

### B) TCP Check

- Input: `host`, `port`
- Behavior: attempt connect with timeout
- Metrics: `latency_ms`
- Failure cases: refused, timeout, unreachable

### C) HTTP Check

- Input: `url`, `method`, `expect_status[]`, optional `expect_contains`
- Behavior: make request, measure time, capture:
  - status code
  - small response snippet (first N chars, safe)

- Failure cases: TLS error, timeout, wrong status, content mismatch

---

## 6) Concurrency Model

Use `asyncio` with:

- a semaphore for concurrency limiting
- per-check timeouts
- retries with exponential backoff
- jitter is optional but if used must be deterministic when `--seed` is set

Determinism requirement:

- Output ordering must be stable:
  - sort by target name, then check type, then check parameters

- All timestamps should be UTC ISO-8601
- Randomness only allowed via seed

---

## 7) Data Model (Result Schema)

Each run produces:

```json
{
  "run_id": "uuid",
  "started_at": "2026-01-18T12:34:56Z",
  "duration_ms": 1234,
  "config_hash": "sha256...",
  "results": [
    {
      "target": "site",
      "check": {
        "type": "http",
        "method": "GET",
        "url": "https://example.com"
      },
      "ok": true,
      "latency_ms": 120,
      "status": 200,
      "error": null,
      "attempts": 1,
      "tags": ["prod"]
    }
  ],
  "summary": {
    "ok": 10,
    "fail": 2,
    "p95_latency_ms": 240
  }
}
```

---

## 8) Persistence (SQLite)

If `--db` provided:

- Store each run + each check result

Tables:

- `runs(run_id, started_at, duration_ms, config_hash)`
- `results(id, run_id, target, check_type, ok, latency_ms, error_code, error_message, meta_json)`

Indexes:

- by `started_at`
- by `target + check_type`

---

## 9) HTML Report

Generate a single static HTML file:

- Header: project name, run time, summary
- Table: each check row with status badge and latency
- “Failures” section at top
- No external JS/CSS dependencies (keep it portable)

---

## 10) Plugin System (Benchmark Hook)

Checks must be implemented via a registry:

- `Check` base class with:
  - `validate(config)`
  - `async run(context) -> CheckResult`

- Registry loads built-ins + optional `plugins/` folder (Python files)
- Plugin discovery:
  - safe import (errors reported cleanly)
  - version compatibility check

This is perfect for benchmarking because LLMs often struggle with:

- clean interfaces
- error handling
- discovery mechanics
- deterministic behavior

---

## 11) Observability / Logging

- Use `logging` with levels
- `--verbose` enables debug logs
- Print a progress line:
  - completed/total, fail count, ETA-ish (optional)

---

## 12) Testing Requirements

Use `pytest`.

Must include:

1. Config validation tests (valid + invalid)
2. Deterministic ordering test (`--seed`)
3. Retry behavior test (use mocked check that fails twice then succeeds)
4. Timeout handling test
5. SQLite persistence test (temp db)
6. Report generation test (HTML contains key sections)

No real network calls in unit tests:

- use mocks/fakes for DNS/TCP/HTTP layers

---

## 13) Non-Functional Requirements

- Python 3.11+
- Type hints + `mypy` clean (or at least strongly typed)
- `ruff` formatting/lint
- Should run on Windows + Linux

---

## 14) Suggested Repo Layout

```
netwatch/
  netwatch/
    __init__.py
    cli.py
    config.py
    models.py
    runner.py
    checks/
      __init__.py
      base.py
      dns.py
      tcp.py
      http.py
    report/
      html.py
    storage/
      sqlite.py
    plugins/
      loader.py
  tests/
  pyproject.toml
  README.md
```

---

## 15) Benchmark Scoring Ideas (How to Grade the LLM)

- **Correctness**: output schema matches spec, retries/timeouts correct
- **Design**: separation of concerns, plugin interface clean
- **Determinism**: stable output ordering, seeded jitter if present
- **Resilience**: handles partial failure, doesn’t crash on one bad target
- **Test quality**: meaningful tests, good use of fakes, minimal flakiness

---

If you want, I can also provide:

- a **grading rubric (0–100)** with specific pass/fail checks, or
- a “starter harness” that runs the app against a fixed config and compares outputs (golden-file style) for repeatable LLM benchmarking.
