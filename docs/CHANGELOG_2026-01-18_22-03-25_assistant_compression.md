# CHANGELOG: Assistant Message Compression Implementation

**Date & Time**: 2026-01-18 22:03:25 UTC  
**Author**: Antigravity (AI Assistant)  
**Change Type**: Feature Implementation - Prompt Size Optimization

---

## Problem Statement

### Issue

The RALPH agent's prompt size was growing unbounded during long-running tasks:

- At iteration 74: ~43,859 characters
- At iteration 75: ~51,092 characters
- Growth rate: ~7,000+ characters per iteration

### Root Cause

RALPH was keeping full assistant messages in conversation history, where each message contained:

- Complete task list (9+ tasks × ~100 chars each = 900+ chars)
- Full JSON schema with all metadata
- Repeated plan_update blocks containing identical task information

This resulted in **~1,200 tokens per assistant message**, and with 8 message pairs in history, the context was ballooning to 50KB+ at iteration 96.

### Impact

- Risk of hitting LLM context limits
- Increased latency and token costs
- At iteration 95, RALPH entered stagnation (repeating the same observation)

---

## Solution Implemented

Implemented intelligent compression of assistant messages in the conversation history while preserving critical decision-making context.

---

## Files Modified

### 1. `/scripts/Scalable_loopup/ralph/config.py`

**Lines Changed**: 18-21 (added 3 new configuration parameters)

**Before**:

```python
CONFIG = {
    # ... existing config ...
    'STAGNATION_THRESHOLD': 5,
    'LOOP_DETECTION_WINDOW': 10,
}
```

**After**:

```python
CONFIG = {
    # ... existing config ...
    'STAGNATION_THRESHOLD': 5,
    'LOOP_DETECTION_WINDOW': 10,
    'COMPRESS_ASSISTANT_AFTER': 3,       # Start compressing assistant messages after this many turns back
    'PRESERVE_REASONING_CHARS': 200,     # How much reasoning text to keep in compressed assistant messages
    'PRESERVE_OBSERVATION_CHARS': 300,   # How much observation to keep in compressed assistant messages
}
```

### 2. `/scripts/Scalable_loopup/ralph/loop.py`

#### Change A: New Helper Method

**Lines Added**: 298-355 (58 new lines)

**Purpose**: Extract and preserve key information from assistant messages while discarding redundant JSON bloat.

**Added Method**:

```python
def _compress_assistant_message(self, content: str) -> str:
    """
    Compress an assistant message to preserve intent and outcome while saving tokens.
    Returns a condensed version that keeps:
    - The observation (outcome)
    - Any execute blocks (intent/actions)
    - Any reasoning before JSON (if present)
    """
    # ... implementation details in file ...
```

#### Change B: Enhanced Message History Thinning

**Lines Changed**: 406-446 (replaced 26 lines with 41 lines)

**Before**:

```python
# Sliding window for messages with thinning
msg_count_before = len(self.messages)
if msg_count_before > (CONFIG['MAX_MESSAGE_HISTORY'] * 2 + 1):
    system_msg = self.messages[0]
    recent_history = self.messages[-(CONFIG['MAX_MESSAGE_HISTORY'] * 2):]

    # Thin out older user messages in history to save tokens
    thinned_history = []
    user_msg_indices = [i for i, m in enumerate(recent_history) if m['role'] == 'user']

    for i, msg in enumerate(recent_history):
        # If it's a user message and NOT the latest one, strip the huge state block
        if msg['role'] == 'user' and i != user_msg_indices[-1]:
            # ... user thinning logic ...
        thinned_history.append(msg)

    self.messages = [system_msg] + thinned_history
    print(f"[RALPH] Trimmed and thinned message history: {msg_count_before} → {len(self.messages)} messages")
```

**After**:

```python
# Sliding window for messages with thinning
msg_count_before = len(self.messages)
if msg_count_before > (CONFIG['MAX_MESSAGE_HISTORY'] * 2 + 1):
    system_msg = self.messages[0]
    recent_history = self.messages[-(CONFIG['MAX_MESSAGE_HISTORY'] * 2):]

    # Safety check: If agent is stagnating, preserve full history for debugging
    if self.state.get("stagnation_count", 0) >= 2:
        print(f"[RALPH] Stagnation detected - preserving full history for debugging")
        self.messages = [system_msg] + recent_history
    else:
        # Thin out older user messages and assistant messages to save tokens
        thinned_history = []
        user_msg_indices = [i for i, m in enumerate(recent_history) if m['role'] == 'user']
        assistant_msg_indices = [i for i, m in enumerate(recent_history) if m['role'] == 'assistant']

        for i, msg in enumerate(recent_history):
            # Thin USER messages (existing logic)
            if msg['role'] == 'user' and user_msg_indices and i != user_msg_indices[-1]:
                # ... user thinning logic ...
                continue

            # Thin ASSISTANT messages (NEW LOGIC)
            elif msg['role'] == 'assistant' and assistant_msg_indices and i < (len(recent_history) - 2):
                # Don't thin the very last assistant message (keep last 2 turns fully intact)
                compressed = self._compress_assistant_message(msg['content'])
                thinned_history.append({"role": "assistant", "content": f"[Compressed] {compressed}"})
                continue

            # Keep message as-is
            thinned_history.append(msg)

        self.messages = [system_msg] + thinned_history
        print(f"[RALPH] Trimmed and thinned message history: {msg_count_before} → {len(self.messages)} messages")
```

---

## Expected Impact

### Token Savings

- **Per compressed assistant message**: ~95% reduction (1,200 tokens → 50 tokens)
- **At iteration 100**: Estimated 40-50% total prompt reduction
- **Scaling**: Prompt size should now remain bounded even at 200+ iterations

### Context Preservation

The compression preserves:

- ✅ **Intent**: What action was attempted (execute blocks)
- ✅ **Reasoning**: Why it was attempted (pre-JSON thoughts, 200 chars)
- ✅ **Outcome**: What the result was (observation, 300 chars)
- ✅ **Progress**: Task switches (plan updates)

### Safety Features

1. Disables compression when `stagnation_count >= 2` (preserves full history for debugging)
2. Always keeps last 2 conversation turns intact
3. Graceful handling of parse failures

---

## How to Revert These Changes

### Step 1: Revert `ralph/config.py`

**Option A: Manual Edit**

1. Open `/scripts/Scalable_loopup/ralph/config.py`
2. Navigate to lines 18-21
3. Delete these three lines:
   ```python
   'COMPRESS_ASSISTANT_AFTER': 3,
   'PRESERVE_REASONING_CHARS': 200,
   'PRESERVE_OBSERVATION_CHARS': 300,
   ```
4. Save the file

**Option B: Using Git (if tracked)**

```bash
cd /scripts/Scalable_loopup
git diff ralph/config.py  # Review changes
git checkout ralph/config.py  # Revert to last commit
```

**Option C: Using sed (automated)**

```bash
cd /scripts/Scalable_loopup
# Create backup first
cp ralph/config.py ralph/config.py.backup

# Remove the three added lines
sed -i "/COMPRESS_ASSISTANT_AFTER/d; /PRESERVE_REASONING_CHARS/d; /PRESERVE_OBSERVATION_CHARS/d" ralph/config.py
```

### Step 2: Revert `ralph/loop.py`

**Option A: Manual Edit**

1. Open `/scripts/Scalable_loopup/ralph/loop.py`

2. **Delete the new method** (lines 298-355):
   - Navigate to line 298
   - Delete from `def _compress_assistant_message(self, content: str) -> str:`
   - Through the line `return " | ".join(parts) if parts else "[No significant action]"`
   - Delete the blank line after it (line 356)

3. **Revert the thinning logic** (lines 406-446):

   Replace this entire block:

   ```python
   # Sliding window for messages with thinning
   msg_count_before = len(self.messages)
   if msg_count_before > (CONFIG['MAX_MESSAGE_HISTORY'] * 2 + 1):
       system_msg = self.messages[0]
       recent_history = self.messages[-(CONFIG['MAX_MESSAGE_HISTORY'] * 2):]

       # Safety check: If agent is stagnating, preserve full history for debugging
       if self.state.get("stagnation_count", 0) >= 2:
           print(f"[RALPH] Stagnation detected - preserving full history for debugging")
           self.messages = [system_msg] + recent_history
       else:
           # Thin out older user messages and assistant messages to save tokens
           thinned_history = []
           user_msg_indices = [i for i, m in enumerate(recent_history) if m['role'] == 'user']
           assistant_msg_indices = [i for i, m in enumerate(recent_history) if m['role'] == 'assistant']

           for i, msg in enumerate(recent_history):
               # Thin USER messages (existing logic)
               if msg['role'] == 'user' and user_msg_indices and i != user_msg_indices[-1]:
                   content = msg['content']
                   if "Current State:" in content:
                       parts = content.split("\n\nProceed with next step.")
                       if len(parts) > 1:
                           # Keep only the part after the state (repetition notes etc.)
                           prompt_end = parts[1]
                           new_content = f"Previous State [truncated for space]...\n\nProceed with next step.{prompt_end}"
                           thinned_history.append({"role": "user", "content": new_content})
                           continue

               # Thin ASSISTANT messages (NEW LOGIC)
               elif msg['role'] == 'assistant' and assistant_msg_indices and i < (len(recent_history) - 2):
                   # Don't thin the very last assistant message (keep last 2 turns fully intact)
                   compressed = self._compress_assistant_message(msg['content'])
                   thinned_history.append({"role": "assistant", "content": f"[Compressed] {compressed}"})
                   continue

               # Keep message as-is
               thinned_history.append(msg)

           self.messages = [system_msg] + thinned_history
           print(f"[RALPH] Trimmed and thinned message history: {msg_count_before} → {len(self.messages)} messages")
   ```

   With the original:

   ```python
   # Sliding window for messages with thinning
   msg_count_before = len(self.messages)
   if msg_count_before > (CONFIG['MAX_MESSAGE_HISTORY'] * 2 + 1):
       system_msg = self.messages[0]
       recent_history = self.messages[-(CONFIG['MAX_MESSAGE_HISTORY'] * 2):]

       # Thin out older user messages in history to save tokens
       thinned_history = []
       user_msg_indices = [i for i, m in enumerate(recent_history) if m['role'] == 'user']

       for i, msg in enumerate(recent_history):
           # If it's a user message and NOT the latest one, strip the huge state block
           if msg['role'] == 'user' and i != user_msg_indices[-1]:
               content = msg['content']
               if "Current State:" in content:
                   parts = content.split("\n\nProceed with next step.")
                   if len(parts) > 1:
                       # Keep only the part after the state (repetition notes etc.)
                       prompt_end = parts[1]
                       new_content = f"Previous State [truncated for space]...\n\nProceed with next step.{prompt_end}"
                       thinned_history.append({"role": "user", "content": new_content})
                       continue
           thinned_history.append(msg)

       self.messages = [system_msg] + thinned_history
       print(f"[RALPH] Trimmed and thinned message history: {msg_count_before} → {len(self.messages)} messages")
   ```

4. Save the file

**Option B: Using Git (if tracked)**

```bash
cd /scripts/Scalable_loopup
git checkout ralph/loop.py
```

**Option C: Using a Patch File**

1. Create this revert patch file (`revert.patch`):

```diff
--- a/ralph/config.py
+++ b/ralph/config.py
@@ -18,9 +18,6 @@
     'CURRENT_STATE_FILE': 'current.state.md',
     'STAGNATION_THRESHOLD': 5,
     'LOOP_DETECTION_WINDOW': 10,
-    'COMPRESS_ASSISTANT_AFTER': 3,
-    'PRESERVE_REASONING_CHARS': 200,
-    'PRESERVE_OBSERVATION_CHARS': 300,
 }
```

2. Apply it:

```bash
cd /scripts/Scalable_loopup
patch -p1 -R < revert.patch
```

### Step 3: Verify Reversion

Run these checks to ensure proper reversion:

```bash
cd /scripts/Scalable_loopup

# Check config.py - should NOT contain these strings
grep -c "COMPRESS_ASSISTANT_AFTER" ralph/config.py
# Expected output: 0

# Check loop.py - should NOT contain the compression method
grep -c "_compress_assistant_message" ralph/loop.py
# Expected output: 0

# Check line count in loop.py
wc -l ralph/loop.py
# Expected output: ~452 lines (original was 452, modified is 526)
```

### Step 4: Restart RALPH (if running)

If RALPH is currently running, restart it to load the reverted code:

```bash
# Find the running process
ps aux | grep run_ralph.py

# Kill it (replace PID with actual process ID)
kill <PID>

# Or use pkill
pkill -f run_ralph.py

# Restart (if desired)
python3 /scripts/Scalable_loopup/run_ralph.py --prompt-file /scripts/Scalable_loopup/task.md
```

---

## Backup Files Created

The following backup file was created during this change session:

- `/scripts/Scalable_loopup/.agent/ASSISTANT_MESSAGE_COMPRESSION.md` - Implementation documentation

To restore from manual backup (if you created one):

```bash
cp ralph/config.py.backup ralph/config.py
cp ralph/loop.py.backup ralph/loop.py
```

---

## Testing After Reversion

To verify RALPH is working correctly after reversion:

1. Check that RALPH starts without errors
2. Monitor prompt growth - it should return to the original growing pattern
3. Observe debug output - should NO longer show "Compressed" messages

---

## Notes

- This change does NOT modify the state file (`ralph_state_*.json`) or workspace files
- Reverting will not affect RALPH's task progress - it will continue from its current state
- If you see errors after reversion, check that both files were completely reverted
- The original prompt growth issue will return after reversion

---

## Questions or Issues?

If you encounter problems during reversion:

1. Check file permissions: `ls -l ralph/config.py ralph/loop.py`
2. Verify Python syntax: `python3 -m py_compile ralph/loop.py`
3. Review full file diff if available: `diff -u ralph/loop.py.backup ralph/loop.py`
