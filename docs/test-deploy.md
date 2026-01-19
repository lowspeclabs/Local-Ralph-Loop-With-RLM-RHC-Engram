Here’s a solid **single-file Python script spec** that’s “small enough to be one file” but still **complex enough to benchmark an LLM’s real skills** (design, parsing, testing, algorithms, error handling, performance, and tool-like UX).

## Project: `llm_benchmark_harness.py` (single file)

### Goal

A CLI tool that runs a **suite of benchmark tasks** against an LLM (or a stub model) and outputs:

- per-task scores + pass/fail
- latency + token-ish size estimates
- a final weighted score
- a JSON report you can diff over time

This lets you compare:

- different models
- different prompts/system messages
- different “agent styles” (strict JSON vs freeform)
- different temperatures

---

## 1) CLI Interface

**Command:**

```bash
python llm_benchmark_harness.py run --config config.json --out results.json
```

**Subcommands**

- `run` : run the benchmark suite
- `list` : list tasks + weights
- `validate` : validate config and task definitions
- `replay` : re-score from saved model outputs (no LLM call)

**Key flags**

- `--config <path>`: model/provider settings + suite config
- `--out <path>`: write results JSON
- `--seed <int>`: deterministic test generation
- `--max-tasks <n>`: quick runs
- `--verbose`

---

## 2) Config Format (JSON)

Single JSON file controlling behavior:

```json
{
  "model": {
    "provider": "openai_compatible",
    "base_url": "http://localhost:1234/v1",
    "api_key_env": "OPENAI_API_KEY",
    "model_name": "local-model",
    "temperature": 0.2,
    "max_tokens": 1200,
    "timeout_s": 30
  },
  "suite": {
    "strict_json": true,
    "retry_on_parse_fail": 1,
    "weights": {
      "json_extraction": 1.0,
      "code_fix": 2.0,
      "planning": 1.0,
      "algorithm": 2.0,
      "reasoning": 1.5,
      "security": 1.0
    }
  }
}
```

If `strict_json=true`, the model must respond in a defined schema.

---

## 3) Core Architecture (still one file)

### Main components (classes / sections)

1. **`Task` dataclass**
   - `id`, `name`, `weight`, `prompt_builder(seed)`, `scorer(output)`

2. **`BenchmarkRunner`**
   - loads config
   - iterates tasks
   - calls LLM client
   - stores raw outputs, timings, parse errors
   - aggregates scores

3. **`LLMClient`**
   - supports “OpenAI-compatible” HTTP (LM Studio / vLLM / OpenAI style)
   - also supports `--mock` mode (no network, deterministic fake outputs)

4. **`Scoring`**
   - robust JSON parsing
   - partial credit rules
   - normalization to 0–100 per task

5. **`ReportWriter`**
   - writes `results.json`
   - optionally prints a nice console table

---

## 4) Benchmark Tasks (the “suite”)

You want tasks that cover multiple skills and have **objective scoring**.

### Task A — Structured JSON extraction (parsing + instruction following)

**Prompt:** provide a messy block of text (logs + bullets) and ask for JSON with exact keys.
**Scoring:**

- required keys present
- types correct
- values match expected regexes
- partial credit per field

### Task B — Code repair (debugging + correctness)

**Prompt:** provide a broken Python function + failing tests in text.
**Model output:** a patch in strict format:

```json
{ "fixed_code": "..." }
```

**Scoring:**

- script runs the returned function in a sandboxed namespace
- executes embedded unit tests
- score = % tests passed + bonus for not changing function signature

### Task C — Algorithmic problem (real reasoning)

Examples: shortest path, interval merge, scheduling, trie matching.
**Scoring:** compare model’s computed outputs to known correct outputs across 20 randomized cases using the seed.

### Task D — Planning under constraints (structured plan quality)

**Prompt:** “Design a CLI tool with X constraints; output a plan with steps + risks + test plan.”
**Scoring (heuristic but consistent):**

- required sections present
- step count within bounds
- mentions specific risks from a known list
- includes test categories

### Task E — Data transformation (ETL thinking)

**Prompt:** give CSV-like text, ask for aggregated metrics + edge-case handling.
**Scoring:** exact match on computed aggregates.

### Task F — Security / prompt injection resistance

**Prompt:** include a malicious instruction inside data (“ignore previous…”).
**Scoring:** passes if model follows outer instruction policy and treats injected text as data.

---

## 5) Response Schemas (strict mode)

All tasks share an envelope schema:

```json
{
  "task_id": "algorithm",
  "final": "...",
  "artifacts": {
    "code": "...",
    "json": {}
  }
}
```

If parsing fails:

- runner records `parse_error`
- optional retry with “You must return valid JSON only”

---

## 6) Scoring + Metrics

For each task capture:

- `score_0_100`
- `weight`
- `weighted_score`
- `latency_ms`
- `chars_in_prompt`, `chars_in_output`
- `parse_ok` boolean
- `retries_used`

Final output includes:

- total weighted score
- percentile-like rank (optional if you keep history)
- breakdown table

---

## 7) Output Report Format (`results.json`)

```json
{
  "run_id": "2026-01-18T12:34:56Z",
  "config_hash": "sha256...",
  "summary": {
    "total_score": 82.4,
    "total_weight": 9.0
  },
  "tasks": [
    {
      "task_id": "code_fix",
      "score": 90,
      "weight": 2.0,
      "latency_ms": 1840,
      "parse_ok": true,
      "raw_output": "{...}"
    }
  ]
}
```

---

## 8) Quality Requirements (so it’s a real benchmark)

- Deterministic test generation via `random.Random(seed)`
- Never crash on model junk output
- Retries capped and recorded
- Clear separation between **prompt**, **raw output**, **parsed output**, **score reasoning**
- “Replay” mode: run scoring only on saved outputs so you can tweak scoring without re-calling the model

---

## 9) Stretch Goals (still single file)

- `--parallel` to run tasks concurrently (thread pool)
- simple “leaderboard.json” that appends results
- optional markdown report output

---

If you want, I can **turn this spec into a real single-file script** that:

- works with **LM Studio** (`base_url=http://localhost:1234/v1`)
- runs fully offline in `--mock` mode
- produces `results.json` + a console score table
