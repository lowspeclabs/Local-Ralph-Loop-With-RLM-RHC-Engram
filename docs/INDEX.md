# 📚 RALPH Documentation Index

Welcome to the RALPH (Recursive Autonomous Loop for Progressive Hacking) documentation!

## 🎯 Start Here

**New to RALPH?**

1. Start with: [`QUICKSTART.md`](QUICKSTART.md) - Get up and running in 5 minutes
2. Read: [`ARCHITECTURE.md`](ARCHITECTURE.md) - Understand how RALPH works

**Want to verify RLM + RCH?**

- Quick: Run `python3 quick_check.py` (10 seconds)
- Full: See [`RLM_RCH_VERIFICATION_GUIDE.md`](RLM_RCH_VERIFICATION_GUIDE.md)

## 📖 Documentation by Topic

### Core Documentation

| File                                         | Purpose                         | When to Read             |
| -------------------------------------------- | ------------------------------- | ------------------------ |
| [`COMPLETE_SUMMARY.md`](COMPLETE_SUMMARY.md) | Everything we implemented today | Start here for overview  |
| [`ARCHITECTURE.md`](ARCHITECTURE.md)         | System architecture diagrams    | To understand the design |
| [`README.md`](README.md)                     | Project overview                | First time setup         |

### Features & Enhancements

| File                                                     | Purpose                          | When to Read             |
| -------------------------------------------------------- | -------------------------------- | ------------------------ |
| [`ENHANCEMENTS.md`](ENHANCEMENTS.md)                     | New features (#5, #1, #4) docs   | To use new HITL commands |
| [`QUICKSTART.md`](QUICKSTART.md)                         | Quick start guide                | To get started fast      |
| [`IMPLEMENTATION_SUMMARY.md`](IMPLEMENTATION_SUMMARY.md) | Technical implementation details | For developers           |

### Verification & Testing

| File                                                             | Purpose                          | When to Read           |
| ---------------------------------------------------------------- | -------------------------------- | ---------------------- |
| [`RLM_RCH_VERIFICATION_GUIDE.md`](RLM_RCH_VERIFICATION_GUIDE.md) | Complete RLM+RCH verification    | To verify both systems |
| [`RCH_VERIFICATION_GUIDE.md`](RCH_VERIFICATION_GUIDE.md)         | RCH-only verification            | Legacy, RCH-specific   |
| `quick_check.py`                                                 | Fast status check script         | Run anytime            |
| `verify_rlm_rch.py`                                              | Automated verification           | Full system test       |
| `test_ralph_consistency.py`                                      | Consistency testing (Feature #4) | To test reliability    |

### Technical References

| File                                             | Purpose                    | When to Read        |
| ------------------------------------------------ | -------------------------- | ------------------- |
| [`RCH_IMPLEMENTATION.md`](RCH_IMPLEMENTATION.md) | RCH implementation details | Deep dive into RCH  |
| `ralph/config.py`                                | Configuration file         | To tune settings    |
| `ralph/loop.py`                                  | Main loop logic            | Core implementation |

## 🚀 Common Tasks

### "I want to run RALPH"

```bash
python3 run_ralph.py --goal "Your task" --iterations 10
```

See: [`QUICKSTART.md`](QUICKSTART.md)

### "I want to verify RLM and RCH are working"

```bash
python3 quick_check.py  # Fast check
python3 verify_rlm_rch.py  # Full verification
```

See: [`RLM_RCH_VERIFICATION_GUIDE.md`](RLM_RCH_VERIFICATION_GUIDE.md)

### "I want to use the new HITL commands"

Run with `--hitl` flag, then use:

- `/reset` - Clear stagnation
- `/skip` - Skip current task
- `/clear` - Clear history
  See: [`ENHANCEMENTS.md`](ENHANCEMENTS.md) Section #5

### "I want to test RALPH's consistency"

```bash
python3 test_ralph_consistency.py --goal "Simple task" --runs 3
```

See: [`ENHANCEMENTS.md`](ENHANCEMENTS.md) Section #4

### "I want to understand the architecture"

See: [`ARCHITECTURE.md`](ARCHITECTURE.md) - Interactive Mermaid diagrams

### "I want to debug an issue"

1. Enable debug: Edit `ralph/config.py`, set `'DEBUG_MODE': True`
2. See: [`RLM_RCH_VERIFICATION_GUIDE.md`](RLM_RCH_VERIFICATION_GUIDE.md) Troubleshooting section

## 📁 File Structure

```
/scripts/Scalable-loops-RHC-RLM-HITL/
│
├── 📘 Documentation/
│   ├── INDEX.md                       ← You are here
│   ├── COMPLETE_SUMMARY.md            ← Today's work summary
│   ├── ARCHITECTURE.md                ← System diagrams
│   ├── QUICKSTART.md                  ← Quick start guide
│   ├── ENHANCEMENTS.md                ← New features docs
│   ├── IMPLEMENTATION_SUMMARY.md      ← Implementation details
│   ├── RLM_RCH_VERIFICATION_GUIDE.md  ← RLM+RCH verification
│   ├── RCH_VERIFICATION_GUIDE.md      ← RCH-only (legacy)
│   └── RCH_IMPLEMENTATION.md          ← RCH implementation
│
├── 🧪 Scripts/
│   ├── run_ralph.py                   ← Main entry point
│   ├── quick_check.py                 ← Fast status check
│   ├── verify_rlm_rch.py              ← Full verification
│   ├── test_ralph_consistency.py      ← Consistency testing
│   └── test_ralph_self_awareness.py   ← Self-awareness test
│
├── ⚙️ Source Code/
│   └── ralph/
│       ├── loop.py                    ← Main loop (RLM + RCH + features)
│       ├── config.py                  ← Configuration
│       ├── proxy.py                   ← LLM proxy
│       ├── parser.py                  ← JSON parser
│       ├── memory.py                  ← Memory store
│       └── utils.py                   ← Utilities (sandboxing)
│
└── 📦 Workspace/
    └── ralph_workspace/               ← RALPH's sandbox
```

## 🎓 Learning Path

**Beginner** → **Intermediate** → **Advanced**

### Beginner (First time user)

1. Read: [`QUICKSTART.md`](QUICKSTART.md)
2. Run: `python3 quick_check.py`
3. Try: `python3 run_ralph.py --goal "Hello world" --iterations 3`

### Intermediate (Regular user)

1. Read: [`ENHANCEMENTS.md`](ENHANCEMENTS.md)
2. Try HITL: `python3 run_ralph.py --goal "Test" --hitl`
3. Test consistency: `python3 test_ralph_consistency.py --goal "Test" --runs 3`

### Advanced (Developer)

1. Read: [`ARCHITECTURE.md`](ARCHITECTURE.md)
2. Read: [`IMPLEMENTATION_SUMMARY.md`](IMPLEMENTATION_SUMMARY.md)
3. Modify: `ralph/config.py` for custom tuning
4. Study: `ralph/loop.py` for implementation details

## 🔍 Find Information By Question

| Question                     | Answer Location                                                                  |
| ---------------------------- | -------------------------------------------------------------------------------- |
| How do I run RALPH?          | [`QUICKSTART.md`](QUICKSTART.md)                                                 |
| What are the new features?   | [`ENHANCEMENTS.md`](ENHANCEMENTS.md)                                             |
| How do I verify RLM/RCH?     | [`RLM_RCH_VERIFICATION_GUIDE.md`](RLM_RCH_VERIFICATION_GUIDE.md)                 |
| What is RLM?                 | [`ARCHITECTURE.md`](ARCHITECTURE.md) Section 2                                   |
| What is RCH?                 | [`ARCHITECTURE.md`](ARCHITECTURE.md) Section 3                                   |
| How do I use `/reset`?       | [`ENHANCEMENTS.md`](ENHANCEMENTS.md) Feature #5                                  |
| What's the drift score?      | [`ENHANCEMENTS.md`](ENHANCEMENTS.md) Feature #4                                  |
| Can RALPH modify himself?    | [`COMPLETE_SUMMARY.md`](COMPLETE_SUMMARY.md) "What RALPH Cannot Do"              |
| How do I debug?              | [`RLM_RCH_VERIFICATION_GUIDE.md`](RLM_RCH_VERIFICATION_GUIDE.md) Troubleshooting |
| What did we implement today? | [`COMPLETE_SUMMARY.md`](COMPLETE_SUMMARY.md)                                     |

## 📊 Status Dashboard

**Current Status** (2026-01-19):

- ✅ RLM: Enabled and working
- ✅ RCH: Enabled and working
- ✅ Feature #5: HITL commands implemented
- ✅ Feature #1: Response deduplication implemented
- ✅ Feature #4: Consistency testing implemented
- ✅ Documentation: Complete
- ✅ Verification: Tools ready

**Quick Check**:

```bash
python3 quick_check.py
```

## 🆘 Quick Help

**Something not working?**

1. Run: `python3 quick_check.py`
2. Check: [`RLM_RCH_VERIFICATION_GUIDE.md`](RLM_RCH_VERIFICATION_GUIDE.md) Troubleshooting
3. Enable debug: Edit `ralph/config.py`, set `'DEBUG_MODE': True`

**Need more details?**

- See: [`COMPLETE_SUMMARY.md`](COMPLETE_SUMMARY.md) - Everything about today's work
- See: [`ARCHITECTURE.md`](ARCHITECTURE.md) - System architecture

**Want examples?**

- See: [`QUICKSTART.md`](QUICKSTART.md) - Example workflows
- See: [`ENHANCEMENTS.md`](ENHANCEMENTS.md) - Feature examples

---

**Last Updated**: 2026-01-19  
**Version**: 1.0  
**Next**: Read [`COMPLETE_SUMMARY.md`](COMPLETE_SUMMARY.md) for the full story!
