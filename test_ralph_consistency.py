#!/usr/bin/env python3
"""
#4 - Iterative Testing System for RALPH

This script runs RALPH multiple times with the same goal and compares:
1. Actions taken
2. Files created
3. Test results  
4. Response consistency

Usage:
    python3 test_ralph_consistency.py --goal "Simple task" --runs 3
"""

import json
import subprocess
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any
import shutil
from difflib import SequenceMatcher


def similarity_ratio(a: str, b: str) -> float:
    """Calculate similarity between two strings (0.0 to 1.0)"""
    return SequenceMatcher(None, a, b).ratio()


def extract_actions_from_state(state_file: Path) -> List[Dict[str, Any]]:
    """Extract action sequence from a RALPH state file"""
    try:
        with open(state_file, 'r') as f:
            state = json.load(f)
        
        actions = []
        observations = state.get('observations', [])
        
        for obs in observations:
            obs_str = str(obs)
            if "Action:" in obs_str:
                actions.append(obs_str)
            elif "Result:" in obs_str:
                actions.append(obs_str)
        
        return actions
    except Exception as e:
        print(f"Failed to parse {state_file}: {e}")
        return []


def get_workspace_files(workspace_dir: Path) -> Dict[str, str]:
    """Get all files in workspace with their contents"""
    files = {}
    if not workspace_dir.exists():
        return files
    
    for file_path in workspace_dir.rglob('*'):
        if file_path.is_file() and not file_path.name.startswith('.'):
            try:
                rel_path = file_path.relative_to(workspace_dir)
                if not any(skip in str(rel_path) for skip in ['__pycache__', '.pyc', '_full_spec.md']):
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    files[str(rel_path)] = content
            except Exception:
                pass
    
    return files


def run_ralph_test(goal: str, run_id: int, max_iterations: int = 5, keep_workspace: bool = False) -> Dict[str,  Any]:
    """Run a single RALPH test iteration"""
    separator = "=" * 60
    print(f"\n{separator}")
    print(f"  RUN #{run_id}")
    print(f"{separator}\n")
    
    workspace_dir = Path('./ralph_workspace')
    state_dir = Path('.')
    
    if not keep_workspace and workspace_dir.exists():
        print(f"Cleaning workspace from previous run...")
        shutil.rmtree(workspace_dir)
    
    for state_file in state_dir.glob('ralph_state_*.json'):
        state_file.unlink()
    
    start_time = time.time()
    cmd = ['python3', 'run_ralph.py', '--goal', goal, '--max-iterations', str(max_iterations)]
    
    print(f"Running: {' '.join(cmd)}\n")
    
    try:
        result = subprocess.run(cmd, timeout=120, capture_output=True, text=True)
        elapsed = time.time() - start_time
        
        state_files = list(state_dir.glob('ralph_state_*.json'))
        state_file = state_files[0] if state_files else None
        
        actions = extract_actions_from_state(state_file) if state_file else []
        workspace_files = get_workspace_files(workspace_dir)
        
        final_state = {}
        if state_file:
            with open(state_file, 'r') as f:
                final_state = json.load(f)
        
        return {
            'run_id': run_id,
            'elapsed_time': elapsed,
            'exit_code': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'actions': actions,
            'workspace_files': workspace_files,
            'final_state': final_state,
            'iterations': final_state.get('iteration', 0),
            'done': final_state.get('done', False),
            'error': final_state.get('error'),
            'success': result.returncode == 0 and not final_state.get('error')
        }
    
    except subprocess.TimeoutExpired:
        print("TIMEOUT: RALPH took too long")
        return {'run_id': run_id, 'elapsed_time': 120, 'exit_code': -1, 'error': 'TIMEOUT', 'success': False}
    except Exception as e:
        print(f"Error running RALPH: {e}")
        return {'run_id': run_id, 'error': str(e), 'success': False}


def compare_runs(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compare multiple RALPH runs for consistency"""
    separator = "=" * 60
    print(f"\n\n{separator}")
    print("  CONSISTENCY ANALYSIS")
    print(f"{separator}\n")
    
    if len(runs) < 2:
        print("Need at least 2 runs to compare")
        return {}
    
    successful_runs = [r for r in runs if r.get(' success')]
    success_rate = len(successful_runs) / len(runs) * 100
    print(f"Success Rate: {success_rate:.1f}% ({len(successful_runs)}/{len(runs)} runs)\n")
    
    print("Action Sequence Comparison:")
    action_sequences = [r.get('actions', []) for r in runs]
    
    if all(action_sequences):
        for i in range(len(action_sequences) - 1):
            seq_a = "|".join(action_sequences[i])
            seq_b = "|".join(action_sequences[i+1])
            similarity = similarity_ratio(seq_a, seq_b)
            print(f"   Run {i+1} vs Run {i+2}: {similarity*100:.1f}% similar")
    
    print(f"\nWorkspace File Consistency:")
    file_sets = [set(r.get('workspace_files', {}).keys()) for r in runs]
    
    common_files = set()
    if all(file_sets):
        common_files = set.intersection(*file_sets)
        all_files = set.union(*file_sets)
        
        print(f"   Common files across all runs: {len(common_files)}")
        print(f"   Total unique files created: {len(all_files)}")
        
        if common_files:
            print(f"\n   Common files: {', '.join(sorted(common_files))}")
        
        if common_files and len(runs) >= 2:
            print(f"\n   Content Similarity:")
            for filepath in sorted(common_files):
                contents = [r['workspace_files'].get(filepath, '') for r in runs]
                if len(contents) >= 2:
                    sim = similarity_ratio(contents[0], contents[1])
                    status = "GOOD" if sim > 0.9 else "WARN" if sim > 0.7 else "BAD"
                    print(f"      [{status}] {filepath}: {sim*100:.1f}%")
    
    print(f"\nIteration Counts:")
    iterations = [r.get('iterations', 0) for r in runs]
    avg_iterations = sum(iterations) / len(iterations) if iterations else 0
    print(f"   Average: {avg_iterations:.1f}")
    print(f"   Range: {min(iterations)} - {max(iterations)}")
    
    action_drift = 0
    if len(action_sequences) >= 2 and action_sequences[0] and action_sequences[1]:
        action_drift = (1 - similarity_ratio("|".join(action_sequences[0]), "|".join(action_sequences[1]))) * 100
    
    print(f"\nDRIFT SCORE: {action_drift:.1f}%")
    if action_drift < 10:
        print("   EXCELLENT - Highly consistent behavior")
    elif action_drift < 30:
        print("   MODERATE - Some variation in approach")
    else:
        print("   HIGH - Significant behavioral drift")
    
    return {
        'success_rate': success_rate,
        'avg_iterations': avg_iterations,
        'common_files': len(common_files),
        'drift_score': action_drift
    }


def main():
    parser = argparse.ArgumentParser(description='Test RALPH consistency across multiple runs')
    parser.add_argument('--goal', type=str, required=True, help='Goal to test')
    parser.add_argument('--runs', type=int, default=3, help='Number of test runs (default: 3)')
    parser.add_argument('--max-iterations', type=int, default=5, help='Max iterations per run (default: 5)')
    parser.add_argument('--keep-workspace', action='store_true', help='Keep workspace between runs')
    parser.add_argument('--output', type=str, help='Save results to JSON file')
    
    args = parser.parse_args()
    
    separator = "#" * 60
    print(f"\n{separator}")
    print(f"  RALPH ITERATIVE TESTING SYSTEM")
    print(f"{separator}\n")
    print(f"Goal: {args.goal}")
    print(f"Runs: {args.runs}")
    print(f"Max Iterations: {args.max_iterations}")
    print(f"Workspace Mode: {'Stateful' if args.keep_workspace else 'Clean'}\n")
    
    results = []
    for run_id in range(1, args.runs + 1):
        run_result = run_ralph_test(args.goal, run_id, args.max_iterations, args.keep_workspace)
        results.append(run_result)
        
        if run_result.get('success'):
            print(f"Run #{run_id} completed in {run_result.get('elapsed_time', 0):.1f}s ({run_result.get('iterations', 0)} iterations)")
        else:
            print(f"Run #{run_id} failed: {run_result.get('error', 'Unknown error')}")
    
    analysis = compare_runs(results)
    
    if args.output:
        output_data = {
            'goal': args.goal,
            'runs': results,
            'analysis': analysis,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\nResults saved to: {output_path}")
    
    separator = "=" * 60
    print(f"\n{separator}")
    print("  TESTING COMPLETE")
    print(f"{separator}\n")


if __name__ == '__main__':
    main()
