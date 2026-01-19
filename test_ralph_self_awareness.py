#!/usr/bin/env python3
"""
Test: Can RALPH read his own source code?
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from ralph.utils import get_safe_path

workspace = Path(__file__).parent / "ralph_workspace"

print("=" * 60)
print("TESTING: Can RALPH read his own source code?")
print("=" * 60)

attempts = [
    ("Direct path", "../ralph/loop.py"),
    ("Double parent", "../../Scalable-loops-RHC-RLM-HITL/ralph/loop.py"),
    ("Absolute path", "/scripts/Scalable-loops-RHC-RLM-HITL/ralph/loop.py"),
    ("No parent traverse", "ralph/loop.py"),
]

actual_source = Path(__file__).parent / "ralph" / "loop.py"
print(f"\nActual source location: {actual_source}")
print(f"Actual source exists: {actual_source.exists()}")
print(f"Actual source size: {actual_source.stat().st_size} bytes\n")

for name, attempt in attempts:
    result = get_safe_path(workspace, attempt)
    can_read = result.exists() and result.is_file()
    is_actual = result.resolve() == actual_source.resolve() if can_read else False
    
    print(f"{name}:")
    print(f"  Input:  {attempt}")
    print(f"  Output: {result}")
    print(f"  Exists: {can_read}")
    print(f"  Is actual source: {is_actual}")
    print()

print("=" * 60)
print("CONCLUSION:")
if not any(get_safe_path(workspace, a[1]).exists() for a in attempts):
    print("❌ RALPH CANNOT read his own source code")
    print("   (System prompt is incorrect)")
else:
    print("✓ RALPH CAN read his source")
print("=" * 60)
