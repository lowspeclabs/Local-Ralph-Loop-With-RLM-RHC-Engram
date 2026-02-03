import argparse
import sys
from pathlib import Path
from ralph import EngramMemoryStore, LMStudioEngramProxy, EngramRalphLoop, CONFIG

def main():
    parser = argparse.ArgumentParser(description="RALPH: Scalable Autonomous Agent")
    parser.add_argument("--goal", type=str, help="Agent goal (direct text)")
    parser.add_argument("--prompt-file", type=str, help="Path to markdown/text file containing the goal")
    parser.add_argument("--url", type=str, default="http://localhost:1234", help="LM Studio URL")
    parser.add_argument("--iterations", type=int, default=50, help="Max iterations")
    parser.add_argument("--storage", type=str, default="./engram_memory", help="Memory storage path")
    parser.add_argument("--model", type=str, default=CONFIG.get("DEFAULT_MODEL_NAME", "local-model"), help="Model name")
    parser.add_argument("--deep-thought", action="store_true", help="Enable Recursive Layered Model (RLM)")
    parser.add_argument("--thinking-level", type=int, choices=range(1, 6), default=1, help="Recursion depth for RLM (1-5)")
    parser.add_argument("--hitl", action="store_true", help="Enable Human-in-the-Loop mode")
    parser.add_argument("--debug", action="store_true", help="Show full LLM JSON and debug logs")
    
    args = parser.parse_args()
    
    # Prompt for URL if default or not provided
    url = args.url
    print(f"\nTargeting LM Studio...")
    user_url = input(f"Enter LM Studio URL [{url}]: ").strip()
    if user_url:
        url = user_url
    
    goal = args.goal
    if args.prompt_file:
        prompt_path = Path(args.prompt_file)
        if not prompt_path.exists():
            print(f"Error: Prompt file not found: {prompt_path}")
            sys.exit(1)
        goal = prompt_path.read_text(encoding='utf-8').strip()
        print(f"[RALPH] Loaded goal from: {prompt_path}")

    if not goal:
        print("Error: Either --goal or --prompt-file is required.")
        sys.exit(1)
        
    print(f"Initializing RALPH...")
    memory = EngramMemoryStore(storage_path=args.storage)
    proxy = LMStudioEngramProxy(lm_studio_url=url, memory_store=memory)
    
    ralph = EngramRalphLoop(
        goal=goal, 
        proxy=proxy, 
        model=args.model, 
        max_iterations=args.iterations,
        rlm_enabled=args.deep_thought,
        rlm_depth=args.thinking_level,
        hitl_enabled=args.hitl,
        debug_mode=args.debug
    )
    
    try:
        ralph.start()
    except KeyboardInterrupt:
        print("\nInterrupted by user. Saving state...")
        ralph._save_state()
        sys.exit(0)

if __name__ == "__main__":
    main()
