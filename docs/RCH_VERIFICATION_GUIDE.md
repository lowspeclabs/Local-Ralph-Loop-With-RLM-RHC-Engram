# RCH Verification Guide - How to Confirm It's Working

## 🎯 Key Metrics to Track

### 1. **PHASE 0 Triggers**

Look for this message every 5 iterations:

```
============================================================
[PHASE 0] Performing Recursive History Summarization (RCH)...
Iteration: 10 | Compression #2
============================================================
```

### 2. **Compression Metrics Box**

After each PHASE 0, you'll see:

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

### 3. **Session Summary** (End of Run)

When RALPH finishes, you'll see a comprehensive summary:

```
============================================================
  RCH SESSION SUMMARY
============================================================

┌──────────────────────────────────────────────────────────┐
│ RECURSIVE HISTORY SUMMARIZATION REPORT                   │
├──────────────────────────────────────────────────────────┤
│ Total iterations:       25                               │
│ RCH compressions:        5 (every 5 iters)               │
│ ──────────────────────────────────────────────────────── │
│ Total chars before:   15234                              │
│ Total chars after:     8923                              │
│ Total chars saved:     6311                              │
│ Overall compression:   41.4%                             │
│ ──────────────────────────────────────────────────────── │
│ Total tokens saved:   ~1577 tokens                       │
│ Tokens saved per iter:  ~63 tokens/iter                  │
│ ──────────────────────────────────────────────────────── │
│ Final history size:   1923/2000 chars                    │
│ History bounded:       ✓ YES                             │
│ ──────────────────────────────────────────────────────── │
│ History trend:         ✓ Stable/Shrinking                │
│ Trend points:            5 data points                   │
└──────────────────────────────────────────────────────────┘
```

## 📊 What Each Metric Means

| Metric                    | What It Tells You           | Good Value               |
| ------------------------- | --------------------------- | ------------------------ |
| **Pre-compression**       | Size before RCH runs        | Growing over time        |
| **Post-compression**      | Size after RCH runs         | < 2000 chars             |
| **Compression ratio**     | How much RCH compressed     | 30-60%                   |
| **Tokens saved**          | Token efficiency gain       | Hundreds per compression |
| **History plateau**       | Is history bounded?         | ✓ Bounded (not at limit) |
| **History trend**         | Is it growing or stable?    | ✓ Stable/Shrinking       |
| **Tokens saved per iter** | Average efficiency over run | 30-100 tokens/iter       |

## ✅ How to Verify RCH is Working

### Test 1: Quick Verification (10 iterations)

```bash
cd /scripts/Scalable-loops-RCH
python3 run_ralph.py --prompt-file task.md --iterations 10
```

**Expected output**:

- Iteration 5: See `[PHASE 0]` message + metrics box
- Iteration 10: See second `[PHASE 0]` message + metrics box
- End: See session summary with 2 compressions

### Test 2: Monitor History Growth (25 iterations)

```bash
python3 run_ralph.py --prompt-file task.md --iterations 25
```

**Watch for**:

- PHASE 0 at iterations: 5, 10, 15, 20, 25
- History size staying under 2000 chars
- "✓ Stable/Shrinking" trend status

### Test 3: Compare RCH vs Non-RCH

**Without RCH** (RALL):

```bash
cd /scripts/Scalable-loops-RALL
python3 run_ralph.py --prompt-file task.md --iterations 25
# Watch your history_summary in state file grow unbounded
```

**With RCH**:

```bash
cd /scripts/Scalable-loops-RCH
python3 run_ralph.py --prompt-file task.md --iterations 25
# Watch your history stay under 2000 chars
```

## 🔍 Verification Commands

### Check if RCH triggered

```bash
# After running RCH, check the logs for PHASE 0
grep "PHASE 0" /path/to/your/run/output.log

# You should see it every 5 iterations
```

### Check state file metrics

```bash
cd /scripts/Scalable-loops-RCH
python3 -c "
import json
state_file = 'ralph_state_heres_a_benchmark-friendly_spec_for_a_simple_pytho.json'
with open(state_file) as f:
    state = json.load(f)
    if 'rch_metrics' in state:
        metrics = state['rch_metrics']
        print(f'Compressions: {metrics[\"compressions\"]}')
        print(f'Total tokens saved: ~{metrics[\"total_tokens_saved\"]}')
        print(f'Compression ratio: {metrics[\"last_compression_ratio\"]:.1f}%')
        print(f'History size: {len(state.get(\"history_summary\", \"\"))}/2000 chars')
    else:
        print('RCH metrics not found - may not have triggered yet')
"
```

### Compare history sizes

```bash
# RCH enabled (should be bounded)
ls -lh /scripts/Scalable-loops-RCH/ralph_state_*.json

# RCH disabled (may grow large)
ls -lh /scripts/Scalable-loops-RALL/ralph_state_*.json
```

## 🎨 Visual Indicators

### ✓ RCH is Working Well

- See `[PHASE 0]` every 5 iterations
- Compression ratio: 30-60%
- History plateau: ✓ Bounded
- History trend: ✓ Stable/Shrinking
- Tokens saved per iter: 30+ tokens

### ⚠ RCH May Need Tuning

- Compression ratio: < 20% (not compressing much)
- History plateau: ⚠ AT LIMIT (hitting 2000 char cap)
- History trend: ⚠ Growing (not stabilizing)

### ❌ RCH Not Working

- No `[PHASE 0]` messages
- No compression metrics boxes
- No RCH session summary at end
- State file has no `rch_metrics` key

## 🐛 Troubleshooting

### "No PHASE 0 messages"

**Cause**: RCH not triggering
**Check**:

```python
# Verify config
grep ENABLE_RCH /scripts/Scalable-loops-RCH/ralph/config.py
# Should show: 'ENABLE_RCH': True

# Verify iteration count
# RCH won't trigger until iteration 5
```

### "RCH ERROR" messages

**Cause**: LLM call failed
**Check**: LM Studio is running and accessible

```bash
curl http://192.168.1.9:1234/v1/models
```

### "History still growing"

**Cause**: Interval too large or max too high
**Fix**: Adjust config

```python
'RECURSIVE_SUMMARY_INTERVAL': 3,  # Reduce from 5 to 3
'MAX_SUMMARY_CHARS': 1500,        # Reduce from 2000
```

## 📈 Expected Performance

Based on typical runs:

| Iterations | Compressions | Tokens Saved | Time Added |
| ---------- | ------------ | ------------ | ---------- |
| 10         | 2            | ~500         | +2-3s      |
| 25         | 5            | ~1500        | +5-7s      |
| 50         | 10           | ~3000        | +10-15s    |
| 100        | 20           | ~6000        | +20-30s    |

**Token savings compound** - the longer the run, the more efficient RCH becomes!

## 🎯 Success Criteria

RCH is working correctly if:

1. ✅ PHASE 0 triggers every N iterations
2. ✅ Compression metrics display after each PHASE 0
3. ✅ History stays under MAX_SUMMARY_CHARS
4. ✅ Compression ratio is 20%+
5. ✅ Session summary shows total savings
6. ✅ History trend is stable/shrinking

All these should be visible in your terminal output!
