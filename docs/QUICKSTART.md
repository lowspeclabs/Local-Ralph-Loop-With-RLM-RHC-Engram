# Quick Start Guide - RALPH Enhancements

## ✅ Implementation Complete

Three new features have been added to RALPH:

## 🎮 Feature #5: Special HITL Commands

**Try it now:**

```bash
python3 run_ralph.py --goal "Create a hello.py file" --hitl --max-iterations 5
```

**Available commands** (type at the HITL prompt):

- `/reset` - Fresh start (clears stagnation, observations, cache)
- `/replan` - Force RALPH to create a new plan
- `/skip` - Skip the current task
- `/clear` - Clear conversation history
- `quit` / `exit` / `stop` - End session

**Anti-repetition**: Type phrases like "don't repeat" or "stop repeating yourself" and RALPH will automatically reset and try a different approach.

---

## 🔍 Feature #1: Response Deduplication

**Automatic** - No action needed!

RALPH now detects when he generates identical responses and warns you:

```
⚠️  [DEDUP WARNING] This response appears identical to a recent one (hash: a3b5c7d9e1f2)
    RALPH may be stuck in a response loop. Consider using /reset or providing new direction.
```

To see detailed deduplication output, edit `ralph/config.py`:

```python
CONFIG = {
    'DEBUG_MODE': True,  # Shows hash collisions
    # ...
}
```

---

## 🧪 Feature #4: Iterative Testing

**Test RALPH's consistency:**

```bash
# Run same goal 3 times and compare results
python3 test_ralph_consistency.py \
  --goal "Create a file test.txt with 'Hello World'" \
  --runs 3 \
  --max-iterations 5
```

**Sample output:**

```
Success Rate: 100.0% (3/3 runs)
DRIFT SCORE: 4.7%
   ✅ EXCELLENT - Highly consistent behavior
```

**Save results:**

```bash
python3 test_ralph_consistency.py \
  --goal "Your task here" \
  --runs 3 \
  --output results.json
```

---

## 📝 Example Workflow

### 1. Normal Run (with HITL control)

```bash
cd /scripts/Scalable-loops-RHC-RLM-HITL

python3 run_ralph.py \
  --goal "Build a simple calculator script" \
  --hitl \
  --max-iterations 10

# During execution:
# - Press ENTER to continue
# - Type feedback to guide RALPH
# - Use /reset if stuck
# - Use /skip to skip a task
# - Type 'quit' to stop
```

### 2. Test Consistency

```bash
# Test if RALPH builds the calculator the same way every time
python3 test_ralph_consistency.py \
  --goal "Build a simple calculator script" \
  --runs 3 \
  --max-iterations 10 \
  --output calculator_test.json

# Check drift score:
# - 0-10%: Excellent
# - 10-30%: Moderate variation
# - 30%+: High drift (investigate)
```

### 3. Debug Repetition Issues

```bash
# Enable debug mode to see deduplication in action
# Edit ralph/config.py: DEBUG_MODE = True

python3 run_ralph.py \
  --goal "Read the same file 5 times" \
  --max-iterations 10

# You'll see:
# [DEDUP] Response hash collision detected: a3b5c7d9e1f2 (last seen 2.3s ago)
```

---

## 🔧 Configuration

Edit `ralph/config.py` to tune behavior:

```python
CONFIG = {
    # ... existing settings ...

    'HITL_ENABLED': True,      # Enable HITL mode
    'DEBUG_MODE': False,       # Show detailed dedup output
    'RLM_ENABLED': True,       # Keep internal thinking mode
    'ENABLE_RCH': True,        # Keep history compression
}
```

---

## 📊 Files Created

| File                        | Purpose                                    |
| --------------------------- | ------------------------------------------ |
| `ralph/loop.py`             | **Modified** - Added dedup + HITL commands |
| `test_ralph_consistency.py` | **New** - Testing harness                  |
| `ENHANCEMENTS.md`           | **New** - Full documentation               |
| `IMPLEMENTATION_SUMMARY.md` | **New** - Technical details                |
| `QUICKSTART.md`             | **New** - This file                        |

---

## ✅ Validation Checklist

Test everything works:

```bash
# 1. Syntax check
python3 -m py_compile ralph/loop.py
python3 -m py compile test_ralph_consistency.py

# 2. Import test
python3 -c "from ralph.loop import EngramRalphLoop; print('✓ OK')"

# 3. Quick HITL test (3 iterations, hit CTRL+C or type 'quit')
python3 run_ralph.py --goal "Say hello" --hitl --max-iterations 3

# 4. Consistency test (simple goal)
python3 test_ralph_consistency.py --goal "Echo test" --runs 2 --max-iterations 2
```

---

## 🎯 Next Steps

1. **Try the HITL commands** - Run with `--hitl` and test `/reset`, `/skip`, `/clear`
2. **Test consistency** - Run the same task 3 times and check drift score
3. **Enable DEBUG_MODE** - See deduplication warnings in detail
4. **Report issues** - If you see unexpected behavior, check the logs

---

## 💡 Tips

- Use `/reset` liberally - it's safe and often helps when RALPH is stuck
- Check drift scores regularly to ensure consistent behavior
- The response cache only keeps 10 entries, so it's lightweight
- All special commands work only in HITL mode (`--hitl` flag)

---

**Ready to go!** 🚀

Start with:

```bash
python3 run_ralph.py --goal "Your task here" --hitl
```

And experiment with the new commands!
