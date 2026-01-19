# RALPH: Unified (RLM + RHC + Cache-Aware Slider)

This branch implements the **Unified Ralph Architecture**, merging Recursive History Summarization (RCH), the Recursive Layered Model (RLM), and **Cache-Aware Context Management**.

## Architecture Layers

### 1. Deep Memory: Recursive History (RCH)

Prevents "Context Drift" by summarizing logs into a high-density narrative every 5 iterations. This ensures intent is preserved while tokens are capped.

### 2. Deep Reasoning: Thinking Model (RLM)

A Draft-Critique-Refine cycle that triggers conditionally on **Confusion**. If the agent detects stagnation, errors, or loops, it enters internal dialogue to self-correct.

### 3. Hot Cache: Cache-Aware Slider (Performance Only)

The most recent discovery in optimization for Local LLMs (LM Studio/Llama.cpp).

#### The Problem: KV Cache Invalidation

Previously, aggressive "Thinning" would rewrite the middle of the conversation to save space. While this reduced tokens, it **invalidated the Key-Value (KV) Cache**, forcing the LLM to re-process the entire prompt on every turn, causing a significant drop in speed (Tokens Per Second).

#### The Solution: Slide-not-Thin

The agent now uses a **Cache-Aware Sliding Window**:

- **Steady State (turns 1-25)**: History is kept 100% static.
- **Sliding Phase**: When the window limit is reached, Ralph drops the _oldest_ turn and slides the rest of the history forward.
- **Result**: LM Studio reuses 95%+ of the previous turn's tokens. Tokens are processed instantly, and TPS remains at the hardware limit.

## Configuration (Optimized for 32k Window)

Controlled in `ralph/config.py`:

- `MAX_MESSAGE_HISTORY`: **25** (Keep 50 messages of "Hot Cache" history).
- `MAX_CONTEXT_CHARS`: **100,000** (~25k tokens).
- `RLM_ONLY_ON_CONFUSION`: `True` (Preserve speed unless stuck).
- `RECURSIVE_SUMMARY_INTERVAL`: `5` (Deep history rewrite every 5 turns).

## Key Benefits

1.  **Hardware Efficiency**: Maximizes 32k+ token windows by keeping the "Hot Cache" static.
2.  **Instant Responses**: Turn processing is near-instant compared to the "Re-Tokenize Every Turn" approach.
3.  **No Amnesia**: The Historian (RCH) ensures that even when messages fall off the "Hot Cache," their significance is saved in the Deep Memory.

## Usage

```bash
cd /scripts/Scalable-loops-RHC-RLM/
python3 run_ralph.py --prompt-file task.md --deep-thought --thinking-level 1
```
