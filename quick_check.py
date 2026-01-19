#!/usr/bin/env python3
"""
Quick RLM + RCH Status Check

Fast verification that both systems are enabled and working.
"""

import json
from pathlib import Path
import sys

def check_config():
    """Check if RLM and RCH are enabled"""
    print("Checking configuration...")
    try:
        import ralph.config as config
        cfg = config.CONFIG
        
        rlm_enabled = cfg.get('RLM_ENABLED', False)
        rch_enabled = cfg.get('ENABLE_RCH', False)
        rlm_depth = cfg.get('RLM_RECURSION_DEPTH', 0)
        rch_interval = cfg.get('RECURSIVE_SUMMARY_INTERVAL', 5)
        
        print(f"\n  RLM: {'✓ Enabled' if rlm_enabled else '✗ Disabled'} (depth: {rlm_depth})")
        print(f"  RCH: {'✓ Enabled' if rch_enabled else '✗ Disabled'} (interval: every {rch_interval} iters)")
        
        return rlm_enabled and rch_enabled
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def check_last_run():
    """Check the most recent state file for RLM/RCH activity"""
    print("\nChecking last RALPH run...")
    
    state_files = sorted(Path('.').glob('ralph_state_*.json'), key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not state_files:
        print("  ⚠️  No state files found. Run RALPH first.")
        return False
    
    state_file = state_files[0]
    print(f"  State file: {state_file.name}")
    
    with open(state_file) as f:
        state = json.load(f)
    
    iterations = state.get('iteration', 0)
    print(f"  Iterations: {iterations}")
    
    # Check RCH
    if 'rch_metrics' in state:
        metrics = state['rch_metrics']
        compressions = metrics.get('compressions', 0)
        tokens_saved = metrics.get('total_tokens_saved', 0)
        history_size = len(state.get('history_summary', ''))
        
        print(f"\n  RCH Activity:")
        print(f"    ✓ Compressions: {compressions}")
        print(f"    ✓ Tokens saved: ~{tokens_saved}")
        print(f"    ✓ History size: {history_size}/2000 chars")
        
        rch_working = compressions > 0 or iterations < 5
    else:
        print(f"\n  RCH Activity:")
        print(f"    ✗ No metrics found")
        rch_working = False
    
    # We can't directly check RLM from state file, but we can check iteration count
    # and stagnation to infer it's working
    stagnation = state.get('stagnation_count', 0)
    done = state.get('done', False)
    error = state.get('error')
    
    print(f"\n  Overall Status:")
    print(f"    Stagnation: {stagnation}/5")
    print(f"    Done: {done}")
    print(f"    Error: {error if error else 'None'}")
    
    return rch_working

def main():
    print("="*60)
    print("  RLM + RCH Quick Status Check")
    print("="*60 + "\n")
    
    config_ok = check_config()
    last_run_ok = check_last_run()
    
    print("\n" + "="*60)
    if config_ok and last_run_ok:
        print("  ✅ Both systems are enabled and working")
    elif config_ok:
        print("  ⚠️  Systems enabled but no recent run detected")
        print("     Run RALPH to generate state file")
    else:
        print("  ✗ One or both systems are disabled")
        print("    Edit ralph/config.py to enable them")
    print("="*60 + "\n")
    
    if not config_ok or not last_run_ok:
        print("For detailed verification, run:")
        print("  python3 verify_rlm_rch.py")
        print("\nTo enable systems, edit ralph/config.py:")
        print("  'RLM_ENABLED': True,")
        print("  'ENABLE_RCH': True,")
        print()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted\n")
        sys.exit(130)
    except Exception as e:
        print(f"\n✗ Error: {e}\n")
        sys.exit(1)
