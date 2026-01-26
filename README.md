# RALPH v0.01

## Recursive Autonomous Loop with Progressive Hacking

**Version**: 0.1  
**Release Date**: 2026-01-19  
**Status**: Production Ready

---

## 📦 Installation

### Automated Installation (Recommended)

```bash
cd /scripts/Scalable-loops-RHC-RLM-HITL-0.1
python3 install_ralph.py
```

This will:

- Create a virtual environment (`.venv`)
- Upgrade pip
- Install all dependencies (requests, etc.)
- Verify the installation

### Manual Installation

```bash
cd /scripts/Scalable-loops-RHC-RLM-HITL-0.1

# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate  # Linux/Mac
# OR
.venv\Scripts\activate     # Windows

# Install dependencies
pip install --upgrade pip
pip install requests

# Verify installation
python3 quick_check.py
```

### Requirements

- Python 3.8 or higher
- `requests` library (for LLM API calls)
- LM Studio or compatible API server

---

## 🚀 Quick Start

**After installation:**

```bash
# Activate virtual environment (if not already active)
source .venv/bin/activate

# Check system status
python3 quick_check.py

# Run RALPH
python3 run_ralph.py --goal "Your task here" --iterations 10

# Run with Human-in-the-Loop
python3 run_ralph.py --goal "Your task" --hitl

# Enable debug mode
python3 run_ralph.py --goal "Your task" --debug
```

---

## 📚 Documentation

All documentation is in the `docs/` folder:

**Start Here**:

- [`docs/INDEX.md`](docs/INDEX.md) - Master documentation index
- [`docs/QUICKSTART.md`](docs/QUICKSTART.md) - Quick start guide
- [`docs/COMPLETE_SUMMARY.md`](docs/COMPLETE_SUMMARY.md) - Full implementation summary

**Feature Documentation**:

- [`docs/ENHANCEMENTS.md`](docs/ENHANCEMENTS.md) - New features (#5, #1, #4)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - System architecture

**Verification**:

- [`docs/RLM_RCH_VERIFICATION_GUIDE.md`](docs/RLM_RCH_VERIFICATION_GUIDE.md) - How to verify RLM+RCH
- `quick_check.py` - Fast status check (10 seconds)
- `verify_rlm_rch.py` - Full automated verification

---

## ✨ What's New in v0.1

### Implemented Features

1. **#5 - User Feedback Integration** ✅
   - Special HITL commands: `/reset`, `/replan`, `/skip`, `/clear`
   - Auto-detection of repetition complaints
   - Enhanced user control during execution

2. **#1 - Dynamic State Management** ✅
   - Response deduplication cache (tracks last 10 responses)
   - Hash-based duplicate detection
   - Warnings when RALPH repeats himself

3. **#4 - Iterative Testing System** ✅
   - Consistency testing across multiple runs
   - Drift score calculation
   - Automated regression testing

### Core Systems

- **RLM (Recursive Layered Model)**: Internal thinking system
  - Draft → Critique → Refine workflow
  - Enabled by default
- **RCH (Recursive History Compression)**: Context management
  - Compresses history every 5 iterations
  - Keeps context under 2000 chars
  - Saves tokens and improves performance

---

## 📁 Project Structure

```
Scalable-loops-RHC-RLM-HITL-0.1/
├── README.md                    ← You are here
│
├── docs/                        ← All documentation
│   ├── INDEX.md                 ← Documentation index
│   ├── COMPLETE_SUMMARY.md      ← Full implementation details
│   ├── ARCHITECTURE.md          ← System diagrams
│   ├── QUICKSTART.md            ← Quick start guide
│   ├── ENHANCEMENTS.md          ← New features
│   ├── RLM_RCH_VERIFICATION_GUIDE.md  ← Verification guide
│   └── ... (more docs)
│
├── ralph/                       ← Source code
│   ├── __init__.py
│   ├── loop.py                  ← Main loop (RLM + RCH + features)
│   ├── config.py                ← Configuration
│   ├── proxy.py                 ← LLM proxy
│   ├── parser.py                ← JSON parser
│   ├── memory.py                ← Memory store
│   └── utils.py                 ← Utilities
│
├── Scripts:
│   ├── run_ralph.py             ← Main entry point
│   ├── quick_check.py           ← Fast status check
│   ├── verify_rlm_rch.py        ← Full verification
│   └── test_ralph_consistency.py ← Consistency testing
│
└── ralph_workspace/             ← RALPH's sandbox (empty)
```

---

## ⚙️ Configuration

Edit `ralph/config.py` to customize:

```python
CONFIG = {
    # RCH (History Compression)
    'ENABLE_RCH': True,
    'RECURSIVE_SUMMARY_INTERVAL': 5,
    'MAX_SUMMARY_CHARS': 2000,

    # RLM (Internal Thinking)
    'RLM_ENABLED': True,
    'RLM_RECURSION_DEPTH': 1,
    'RLM_ONLY_ON_CONFUSION': False,

    # HITL (Human-in-the-Loop)
    'HITL_ENABLED': True,

    # Debug
    'DEBUG_MODE': False,
}
```

---

## 🧪 Verification

### Quick Check (10 seconds)

```bash
python3 quick_check.py
```

Expected output:

```
✅ Both systems are enabled and working
  RLM: ✓ Enabled (depth: 1)
  RCH: ✓ Enabled (interval: every 5 iters)
```

### Full Verification

See: [`docs/RLM_RCH_VERIFICATION_GUIDE.md`](docs/RLM_RCH_VERIFICATION_GUIDE.md)

---

## 🎮 Usage Examples

### Basic Usage

```bash
python3 run_ralph.py \
  --goal "Create a calculator with add/subtract/multiply functions" \
  --iterations 20
```

### With Human-in-the-Loop

```bash
python3 run_ralph.py \
  --goal "Build a TODO list manager" \
  --hitl \
  --iterations 15
```

During execution, try these commands:

- `/reset` - Clear stagnation and start fresh
- `/skip` - Skip current task
- `/clear` - Clear conversation history
- Type "stop repeating" to force a new approach

### With Debug Output

```bash
python3 run_ralph.py \
  --goal "Your task" \
  --debug \
  --iterations 10
```

### Test Consistency

```bash
python3 test_ralph_consistency.py \
  --goal "Create hello.py" \
  --runs 3 \
  --max-iterations 5
```

---

## 🔍 Troubleshooting

### "RLM not working"

```bash
# Check config
grep RLM_ENABLED ralph/config.py

# Enable debug mode to see RLM messages
# Edit ralph/config.py: 'DEBUG_MODE': True
```

### "RCH not working"

```bash
# Check config
grep ENABLE_RCH ralph/config.py

# RCH triggers at iteration 5+
# Run at least 10 iterations to see compression
```

### "Connection refused"

```bash
# Make sure LM Studio is running
curl http://192.168.1.9:1234/v1/models

# Or update the URL
python3 run_ralph.py --url http://your-server:port
```

See full troubleshooting: [`docs/RLM_RCH_VERIFICATION_GUIDE.md`](docs/RLM_RCH_VERIFICATION_GUIDE.md)

---

## 📊 Success Indicators

### RCH Working:

- ✓ Compression box every 5 iterations
- ✓ History stays under 2000 chars
- ✓ Compression ratio 20-60%

### RLM Working:

- ✓ `[RLM]` messages in debug mode
- ✓ "thinking deeply (RLM)" in normal mode
- ✓ Better quality outputs

### New Features Working:

- ✓ `/reset` clears stagnation
- ✓ Duplicate warnings when repeating
- ✓ Consistency test produces drift score

---

## 🛡️ Safety Features

- **Workspace Sandboxing**: RALPH cannot escape `ralph_workspace/`
- **Command Blocking**: Dangerous commands (`rm`, `sudo`, `mv`) are blocked
- **Path Validation**: `get_safe_path()` prevents directory traversal
- **Self-Modification Protection**: RALPH cannot modify his own source code

---

## 📈 Performance

**Expected Performance** (10 iterations):

- Time: ~2-3 minutes
- RCH Compressions: 2
- Tokens Saved: ~500-700
- Context Size: Stable at ~2000 chars

---

## 🤝 Contributing

This is a production release (v0.1). For modifications:

1. Make changes in a copy
2. Test with `python3 verify_rlm_rch.py`
3. Run consistency tests
4. Update documentation

---

## 📄 License

See project root for license information.

---

## 🔗 Links

- **Documentation Index**: [`docs/INDEX.md`](docs/INDEX.md)
- **Quick Start**: [`docs/QUICKSTART.md`](docs/QUICKSTART.md)
- **Architecture**: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Verification Guide**: [`docs/RLM_RCH_VERIFICATION_GUIDE.md`](docs/RLM_RCH_VERIFICATION_GUIDE.md)

---

**RALPH v0.1** - Ready for production use! 🚀

For questions or issues, see the full documentation in `docs/`.
