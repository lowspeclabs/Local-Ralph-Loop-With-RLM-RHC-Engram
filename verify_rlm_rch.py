#!/usr/bin/env python3
"""
Automated RLM + RCH Verification Script

Runs RALPH and automatically verifies that both RLM and RCH
are working correctly and interacting properly.
"""

import json
import subprocess
import sys
from pathlib import Path
import time

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def check_config():
    """Verify configuration settings"""
    print_header("STEP 1: Checking Configuration")
    
    try:
        import ralph.config as config
        cfg = config.CONFIG
        
        checks = {
            'RLM_ENABLED': cfg.get('RLM_ENABLED'),
            'RLM_RECURSION_DEPTH': cfg.get('RLM_RECURSION_DEPTH'),
            'ENABLE_RCH': cfg.get('ENABLE_RCH'),
            'RECURSIVE_SUMMARY_INTERVAL': cfg.get('RECURSIVE_SUMMARY_INTERVAL'),
            'DEBUG_MODE': cfg.get('DEBUG_MODE'),
        }
        
        all_good = True
        for key, value in checks.items():
            status = "✓" if value else "✗"
            print(f"  {status} {key}: {value}")
            
            if key in ['RLM_ENABLED', 'ENABLE_RCH'] and not value:
                all_good = False
        
        if not all_good:
            print(f"\n⚠️  WARNING: RLM or RCH is disabled")
            print(f"   Enable them in ralph/config.py for full testing\n")
            return False
        
        print(f"\n✅ Configuration looks good!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return False

def run_ralph_test(iterations=10):
    """Run RALPH for testing"""
    print_header(f"STEP 2: Running RALPH ({iterations} iterations)")
    
    # Clean up old state files
    for f in Path('.').glob('ralph_state_*.json'):
        f.unlink()
    
    goal = "Create a simple calculator with add, subtract, and multiply functions"
    
    print(f"Goal: {goal}")
    print(f"Iterations: {iterations}\n")
    print("Running...\n")
    
    cmd = [
        'python3', 'run_ralph.py',
        '--goal', goal,
        '--iterations', str(iterations),
        '--url', 'http://192.168.1.9:1234',  # Use configured LM Studio URL
    ]
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            input="\n"  # Press ENTER to accept URL
        )
        
        elapsed = time.time() - start_time
        
        print(f"✓ Completed in {elapsed:.1f}s\n")
        
        return result.returncode == 0, result.stdout, result.stderr
        
    except subprocess.TimeoutExpired:
        print(f"❌ Timeout after 5 minutes")
        return False, "", ""
    except Exception as e:
        print(f"❌ Error running RALPH: {e}")
        return False, "", ""

def verify_rch(stdout):
    """Verify RCH metrics from output"""
    print_header("STEP 3: Verifying RCH (Recursive History Compression)")
    
    # Check for RCH compression boxes in output
    compression_count = stdout.count("RCH COMPRESSION METRICS")
    
    print(f"  Compression boxes found: {compression_count}")
    
    # Check state file
    state_files = list(Path('.').glob('ralph_state_*.json'))
    if not state_files:
        print(f"  ❌ No state file found")
        return False
    
    with open(state_files[0]) as f:
        state = json.load(f)
    
    if 'rch_metrics' not in state:
        print(f"  ❌ No RCH metrics in state file")
        return False
    
    metrics = state['rch_metrics']
    compressions = metrics.get('compressions', 0)
    tokens_saved = metrics.get('total_tokens_saved', 0)
    history_size = len(state.get('history_summary', ''))
    max_size = 2000
    
    print(f"  Compressions performed: {compressions}")
    print(f"  Tokens saved: ~{tokens_saved}")
    print(f"  History size: {history_size}/{max_size} chars")
    
    if compressions > 0:
        ratio = metrics.get('last_compression_ratio', 0)
        print(f"  Last compression ratio: {ratio:.1f}%")
        
        if history_size < max_size:
            print(f"\n✅ RCH IS WORKING CORRECTLY!")
            return True
        else:
            print(f"\n⚠️  RCH working but history at limit")
            return True
    else:
        print(f"\n⚠️  RCH didn't trigger (need 5+ iterations)")
        return False

def verify_rlm(stdout, stderr):
    """Verify RLM from output"""
    print_header("STEP 4: Verifying RLM (Recursive Layered Model)")
    
    # Check for RLM messages
    rlm_entering = stdout.count("[RLM] Entering internal dialogue")
    rlm_thinking = stdout.count("[ralph is thinking deeply (RLM)")
    
    # In non-debug mode, we see the thinking message
    # In debug mode, we see detailed RLM logs
    
    print(f"  RLM thinking indicators: {rlm_thinking + rlm_entering}")
    
    if rlm_entering > 0:
        # Debug mode output
        critique = stdout.count("Generating internal critique")
        refining = stdout.count("Refining final action")
        
        print(f"  Draft phases: {rlm_entering}")
        print(f"  Critique phases: {critique}")
        print(f"  Refinement phases: {refining}")
        
        if rlm_entering > 0 and critique > 0 and refining > 0:
            print(f"\n✅ RLM IS WORKING CORRECTLY (Three-phase execution confirmed)")
            return True
    
    elif rlm_thinking > 0:
        # Non-debug mode output
        print(f"  RLM triggered: {rlm_thinking} times")
        print(f"\n✅ RLM IS WORKING (Enable DEBUG_MODE to see details)")
        return True
    
    else:
        print(f"\n❌ RLM not detected in output")
        print(f"   Check that RLM_ENABLED=True and RLM_RECURSION_DEPTH > 0")
        return False

def verify_interaction(stdout):
    """Verify RLM and RCH are interacting correctly"""
    print_header("STEP 5: Verifying RLM + RCH Interaction")
    
    # Check that both appear in same run
    has_rch = "RCH COMPRESSION" in stdout
    has_rlm = "[RLM]" in stdout or "thinking deeply (RLM)" in stdout
    
    print(f"  RCH present: {'✓' if has_rch else '✗'}")
    print(f"  RLM present: {'✓' if has_rlm else '✗'}")
    
    if has_rch and has_rlm:
        print(f"\n✅ Both systems are running together!")
        
        # Check there are no errors
        if "RCH ERROR" in stdout or "RLM ERROR" in stdout:
            print(f"⚠️  Errors detected in output - check logs")
            return False
        
        print(f"✅ No conflicts detected")
        return True
    else:
        print(f"\n⚠️  One or both systems not detected")
        return False

def generate_report():
    """Generate final verification report"""
    print_header("VERIFICATION REPORT")
    
    state_files = list(Path('.').glob('ralph_state_*.json'))
    if not state_files:
        print("No state file available for report")
        return
    
    with open(state_files[0]) as f:
        state = json.load(f)
    
    print("Final State:")
    print(f"  Iterations completed: {state.get('iteration', 0)}")
    print(f"  Task completed: {state.get('done', False)}")
    print(f"  Errors: {state.get('error', 'None')}")
    
    if 'rch_metrics' in state:
        metrics = state['rch_metrics']
        print(f"\nRCH Performance:")
        print(f"  Compressions: {metrics.get('compressions', 0)}")
        print(f"  Total tokens saved: ~{metrics.get('total_tokens_saved', 0)}")
        print(f"  Final history size: {len(state.get('history_summary', ''))}/2000")
    
    print(f"\n{'='*60}\n")

def main():
    print("\n" + "="*60)
    print("  RLM + RCH AUTOMATED VERIFICATION")
    print("="*60)
    print("\nThis script will:")
    print("  1. Check configuration")
    print("  2. Run RALPH for 10 iterations")
    print("  3. Verify RCH is working")
    print("  4. Verify RLM is working")
    print("  5. Verify they interact correctly")
    print("\nExpected runtime: ~2-3 minutes\n")
    
    input("Press ENTER to start verification...")
    
    # Step 1: Check config
    if not check_config():
        print("\n❌ Configuration check failed")
        print("   Fix configuration and run again")
        sys.exit(1)
    
    # Step 2: Run RALPH
    success, stdout, stderr = run_ralph_test(iterations=10)
    
    if not success:
        print("\n❌ RALPH run failed")
        if stderr:
            print(f"\nError output:\n{stderr[:500]}")
        sys.exit(1)
    
    # Step 3: Verify RCH
    rch_ok = verify_rch(stdout)
    
    # Step 4: Verify RLM
    rlm_ok = verify_rlm(stdout, stderr)
    
    # Step 5: Verify interaction
    interaction_ok = verify_interaction(stdout)
    
    # Final report
    generate_report()
    
    # Summary
    print_header("FINAL RESULT")
    
    if rch_ok and rlm_ok and interaction_ok:
        print("✅ ALL CHECKS PASSED!")
        print("\nBoth RLM and RCH are correctly implemented")
        print("and working together without issues.\n")
        sys.exit(0)
    else:
        print("⚠️  SOME CHECKS FAILED")
        print(f"\n  RCH: {'✓' if rch_ok else '✗'}")
        print(f"  RLM: {'✓' if rlm_ok else '✗'}")
        print(f"  Interaction: {'✓' if interaction_ok else '✗'}")
        print(f"\nSee details above for troubleshooting.\n")
        sys.exit(1)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n⚠️  Verification interrupted by user\n")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
