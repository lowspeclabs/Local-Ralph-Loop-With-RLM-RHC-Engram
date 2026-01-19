# RLM + RCH Verification Guide

## How to Verify Both Layers Are Working Together

This guide shows you how to verify that **RLM** (Recursive Layered Model) and **RCH** (Recursive History Compression) are both correctly implemented and interacting properly.

---

## 🎯 Quick Verification Checklist

Run this test to verify everything works:

```bash
cd /scripts/Scalable-loops-RHC-RLM-HITL

# Run with DEBUG_MODE enabled to see all the details
python3 run_ralph.py \
  --goal "Create a simple calculator script with add, subtract, multiply functions" \
  --max-iterations 10 \
  --debug

# Then check for all the indicators below ↓
```

**Expected to see:**

- ✅ RLM thinking messages (Draft → Critique → Refine)
- ✅ RCH compression every 5 iterations
- ✅ Both systems working together without conflicts

---

## 📊 Part 1: Verify RCH (Recursive History Compression)

### What to Look For

#### Every 5 Iterations (5, 10, 15, 20...)

You should see this box:

```
┌──────────────────────────────────────────────────────────┐
│ RCH COMPRESSION METRICS                                  │
├──────────────────────────────────────────────────────────┤
│ Pre-compression:    3245 chars (~ 811 tokens)            │
│ Post-compression:   1847 chars (~ 461 tokens)            │
│ ──────────────────────────────────────────────────────── │
│ Chars saved:        1398 (43.1% reduction)               │
│ Tokens saved:        ~349 tokens                         │
│ Compression time:   1.23s                                │
├──────────────────────────────────────────────────────────┤
│ Total compressions:   2                                  │
│ Total tokens saved:  ~687                                │
│ History plateau:    1847/2000 chars (✓ Bounded)          │
└──────────────────────────────────────────────────────────┘
```

### Terminal Command to Verify

```bash
# After running, check state file
python3 << 'EOF'
import json
from pathlib import Path

# Find the state file
state_files = list(Path('.').glob('ralph_state_*.json'))
if not state_files:
    print("❌ No state file found")
    exit(1)

with open(state_files[0]) as f:
    state = json.load(f)

# Check RCH metrics
if 'rch_metrics' not in state:
    print("❌ RCH not initialized")
    exit(1)

metrics = state['rch_metrics']
compressions = metrics.get('compressions', 0)

print(f"✓ RCH Metrics Found")
print(f"  Compressions: {compressions}")
print(f"  Tokens saved: ~{metrics.get('total_tokens_saved', 0)}")
print(f"  History size: {len(state.get('history_summary', ''))}/{2000} chars")

if compressions > 0:
    print(f"\n✅ RCH IS WORKING")
    print(f"   Compression ratio: {metrics.get('last_compression_ratio', 0):.1f}%")
else:
    print(f"\n⚠️  RCH hasn't triggered yet (need iteration 5+)")
EOF
```

### Expected Output:

```
✓ RCH Metrics Found
  Compressions: 2
  Tokens saved: ~687
  History size: 1847/2000 chars

✅ RCH IS WORKING
   Compression ratio: 43.1%
```

---

## 🧠 Part 2: Verify RLM (Recursive Layered Model)

### What to Look For

When RLM triggers, you should see (with DEBUG_MODE=True):

```
[RLM] Entering internal dialogue (Level: 1)
[RLM]   -> Generating internal critique...
[RLM]   -> Refining final action...
[RLM] Execution Summary: Draft=1.2s, Critique=0.9s, Refinement=1.1s
[RLM] Total Thinking Time: 3.2s
```

When DEBUG_MODE=False, you'll just see:

```
  [ralph is thinking deeply (RLM)...] done.
```

### RLM Trigger Conditions

By default (`RLM_ONLY_ON_CONFUSION=False`), RLM runs **every iteration**.

If `RLM_ONLY_ON_CONFUSION=True`, RLM only triggers when:

- Loop detected (stagnation_count > 0)
- Recent error in observations
- RALPH is confused

### Terminal Command to Verify

```bash
# Check if RLM is enabled in config
grep -A2 "RLM Settings" ralph/config.py

# Should show:
# 'RLM_ENABLED': True,
# 'RLM_RECURSION_DEPTH': 1,
# 'RLM_ONLY_ON_CONFUSION': False,
```

### Live Test - See RLM in Action

```bash
# Run with debug to see RLM thinking
python3 run_ralph.py \
  --goal "Search for the current weather in New York" \
  --max-iterations 5 \
  --debug

# Watch for the [RLM] messages
```

**You should see:**

1. `[RLM] Entering internal dialogue (Level: 1)`
2. Draft phase (generates initial response)
3. Critique phase (reviews for errors, suggests search)
4. Refinement phase (applies critique, outputs final JSON)

---

## 🔗 Part 3: Verify RLM + RCH Interaction

### The Interaction Flow

```
Iteration N:
  1. _summarize_observations()      ← Basic compression
  2. _recursive_summarize_history() ← RCH (every 5 iterations)
  3. Loop detection
  4. Build context from state
  5. _rlm_internal_dialogue()       ← RLM thinking
  6. Parse response
  7. Execute actions
  8. Save state
```

### Key Interaction Points

#### 1. RCH Compresses, Then RLM Thinks

RCH runs **before** RLM, so:

- RCH creates a smaller context
- RLM receives that compressed context
- RLM's thinking is faster due to smaller input

#### 2. RLM Can Trigger on Confusion

If RCH fails or produces errors:

- Error gets logged to observations
- On next iteration, RLM detects error
- RLM triggers to analyze the problem

### Verification Test

```bash
# Run a 15-iteration test
python3 run_ralph.py \
  --goal "Build a simple TODO list manager with add/remove/list functions" \
  --max-iterations 15 \
  --debug 2>&1 | tee test_output.log

# Then analyze the log
grep "\[RLM\]" test_output.log | head -20
grep "RCH COMPRESSION" test_output.log | wc -l
```

**Expected**:

- `[RLM]` appears on most/all iterations
- RCH compression boxes appear 3 times (iterations 5, 10, 15)
- No conflicts or errors between them

---

## 🧪 Part 4: Interactive Verification Tests

### Test 1: RCH Alone (Baseline)

```bash
# Edit config.py temporarily:
# 'RLM_ENABLED': False,

python3 run_ralph.py \
  --goal "Create hello.py" \
  --max-iterations 10

# Verify: RCH still works without RLM
```

### Test 2: RLM Alone (Baseline)

```bash
# Edit config.py temporarily:
# 'RLM_ENABLED': True,
# 'ENABLE_RCH': False,

python3 run_ralph.py \
  --goal "Create hello.py" \
  --max-iterations 10

# Verify: RLM still works without RCH
```

### Test 3: Both Together (Full System)

```bash
# Edit config.py:
# 'RLM_ENABLED': True,
# 'ENABLE_RCH': True,

python3 run_ralph.py \
  --goal "Create hello.py" \
  --max-iterations 10

# Verify: Both work together
```

### Test 4: Confusion Detection

```bash
# Force RALPH into an error state
python3 run_ralph.py \
  --goal "Read a file that doesn't exist: /nonexistent/path.txt" \
  --max-iterations 5 \
  --debug

# With RLM_ONLY_ON_CONFUSION=True:
# - Iteration 1: Error occurs
# - Iteration 2: RLM should trigger (detected error)
# - Watch for [RLM] Confusion detected message
```

---

## 📈 Part 5: Performance Metrics

### Expected Performance (15 iterations)

| Metric                   | Without RLM/RCH | With RCH Only | With RLM Only | With Both   |
| ------------------------ | --------------- | ------------- | ------------- | ----------- |
| **Total Time**           | ~30s            | ~33s          | ~45s          | ~48s        |
| **Avg Response Time**    | 2.0s            | 1.7s          | 3.0s          | 2.8s        |
| **Context Size (final)** | ~8000 chars     | ~2000 chars   | ~8000 chars   | ~2000 chars |
| **Token Efficiency**     | Baseline        | +40%          | -30%          | +10%        |

### Interpretation

- **RCH**: Faster responses over time (smaller context)
- **RLM**: Slower per iteration (3x LLM calls), but higher quality
- **Both**: RCH speeds up RLM by reducing context size

---

## 🔍 Part 6: Debug Commands

### Check Current Configuration

```bash
cd /scripts/Scalable-loops-RHC-RLM-HITL

python3 << 'EOF'
import ralph.config as config

print("Current Configuration:")
print(f"  RLM_ENABLED: {config.CONFIG['RLM_ENABLED']}")
print(f"  RLM_RECURSION_DEPTH: {config.CONFIG['RLM_RECURSION_DEPTH']}")
print(f"  RLM_ONLY_ON_CONFUSION: {config.CONFIG['RLM_ONLY_ON_CONFUSION']}")
print(f"  ENABLE_RCH: {config.CONFIG['ENABLE_RCH']}")
print(f"  RECURSIVE_SUMMARY_INTERVAL: {config.CONFIG['RECURSIVE_SUMMARY_INTERVAL']}")
print(f"  MAX_SUMMARY_CHARS: {config.CONFIG['MAX_SUMMARY_CHARS']}")
print(f"  DEBUG_MODE: {config.CONFIG['DEBUG_MODE']}")
print(f"  HITL_ENABLED: {config.CONFIG['HITL_ENABLED']}")
EOF
```

### Monitor Live Execution

```bash
# Run with real-time monitoring
python3 run_ralph.py --goal "Test task" --max-iterations 10 --debug | grep -E "\[RLM\]|\[RCH\]|RCH COMPRESSION"
```

### Check State File Details

```bash
# Examine complete state after run
python3 << 'EOF'
import json
from pathlib import Path
import pprint

state_file = list(Path('.').glob('ralph_state_*.json'))[0]
with open(state_file) as f:
    state = json.load(f)

print("=== STATE ANALYSIS ===\n")

# RCH Metrics
if 'rch_metrics' in state:
    print("RCH Metrics:")
    pprint.pprint(state['rch_metrics'])
else:
    print("⚠️  No RCH metrics found")

print(f"\nHistory Summary Length: {len(state.get('history_summary', ''))}")
print(f"Iteration: {state.get('iteration', 0)}")
print(f"Observations Count: {len(state.get('observations', []))}")
print(f"Stagnation Count: {state.get('stagnation_count', 0)}")
EOF
```

---

## ✅ Success Criteria

Both RLM and RCH are working correctly if:

### RCH Success Indicators:

1. ✅ RCH compression box appears every 5 iterations
2. ✅ `rch_metrics` exists in state file
3. ✅ History size stays under 2000 chars
4. ✅ Compression ratio is 20-60%
5. ✅ Session summary shows token savings

### RLM Success Indicators:

1. ✅ `[RLM]` messages appear when expected
2. ✅ Three-phase execution (Draft → Critique → Refine)
3. ✅ Timing metrics show ~2-4s per RLM call
4. ✅ Higher quality outputs (e.g., suggests search when uncertain)

### Integration Success Indicators:

1. ✅ Both systems run without errors
2. ✅ RCH runs before RLM (check timing)
3. ✅ RLM uses compressed context from RCH
4. ✅ Total time is reasonable (not 2x slower)
5. ✅ No conflicts in state management

---

## 🐛 Troubleshooting

### "No RCH compression boxes"

**Possible causes:**

- `ENABLE_RCH: False` in config
- Less than 5 iterations completed
- LLM is down

**Fix:**

```bash
# Verify config
grep ENABLE_RCH ralph/config.py

# Verify LLM is running
curl http://192.168.1.9:1234/v1/models
```

### "No RLM messages"

**Possible causes:**

- `RLM_ENABLED: False` in config
- `DEBUG_MODE: False` (messages are hidden)
- `RLM_RECURSION_DEPTH: 0` (RLM disabled)

**Fix:**

```bash
# Enable debug mode to see RLM messages
# Edit ralph/config.py:
'DEBUG_MODE': True,
'RLM_ENABLED': True,
'RLM_RECURSION_DEPTH': 1,
```

### "RLM and RCH seem to conflict"

**Symptoms:**

- Errors during RCH compression
- RLM gets stuck
- State corruption

**Debug:**

```bash
# Run with full debug output
python3 run_ralph.py --goal "Simple test" --max-iterations 5 --debug > full_debug.log 2>&1

# Check for errors
grep -i "error\|exception\|failed" full_debug.log
```

---

## 📋 Quick Reference Commands

```bash
# Enable everything for testing
cd /scripts/Scalable-loops-RHC-RLM-HITL
sed -i "s/'DEBUG_MODE': False/'DEBUG_MODE': True/" ralph/config.py
sed -i "s/'RLM_ENABLED': .*/RLM_ENABLED': True,/" ralph/config.py
sed -i "s/'ENABLE_RCH': .*/ENABLE_RCH': True,/" ralph/config.py

# Run verification test
python3 run_ralph.py --goal "Create a calculator" --max-iterations 10 --debug

# Check results
python3 -c "
import json
from pathlib import Path
state = json.load(open(list(Path('.').glob('ralph_state_*.json'))[0]))
print(f\"RCH Compressions: {state['rch_metrics']['compressions']}\")
print(f\"Iterations: {state['iteration']}\")
print(f\"History size: {len(state['history_summary'])}/2000\")
"

# Restore config
git checkout ralph/config.py  # If using git
```

---

## 📄 Expected Output Summary

For a 10-iteration run with both RLM and RCH enabled:

```
===========================================
Iteration 1: [ralph is thinking deeply (RLM)...] done.
Iteration 2: [ralph is thinking deeply (RLM)...] done.
Iteration 3: [ralph is thinking deeply (RLM)...] done.
Iteration 4: [ralph is thinking deeply (RLM)...] done.
Iteration 5: [RCH COMPRESSION BOX] done.
           : [ralph is thinking deeply (RLM)...] done.
Iteration 6: [ralph is thinking deeply (RLM)...] done.
Iteration 7: [ralph is thinking deeply (RLM)...] done.
Iteration 8: [ralph is thinking deeply (RLM)...] done.
Iteration 9: [ralph is thinking deeply (RLM)...] done.
Iteration 10: [RCH COMPRESSION BOX] done.
            : [ralph is thinking deeply (RLM)...] done.

===========================================
SESSION SUMMARY
===========================================
[RCH SESSION SUMMARY BOX]
- Total compressions: 2
- Tokens saved: ~687
- History bounded: ✓ YES

RALPH Loop Terminated.
```

**That's a successful run with both systems working!**

---

**Last Updated**: 2026-01-19  
**For**: RALPH RHC-RLM-HITL Version  
**Status**: Production Ready
