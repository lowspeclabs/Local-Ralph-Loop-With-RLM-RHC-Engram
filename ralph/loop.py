import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from .proxy import LMStudioEngramProxy
from .parser import ResponseParser
from .utils import get_safe_path, clean_output, parse_pytest_summary, sanitize_goal_for_filename
from .config import CONFIG, DEFAULT_SYSTEM_PROMPT, SEPARATOR

class EngramRalphLoop:
    """Autonomous RALPH agent loop with observation windowing."""
    
    def __init__(self, goal: str, proxy: LMStudioEngramProxy, model: str = None, max_iterations: int = 10, workspace_dir: str = None, rlm_enabled: bool = None, rlm_depth: int = None, hitl_enabled: bool = None, debug_mode: bool = None):
        self.goal = goal
        self.brief_goal = self._extract_brief_goal(goal)
        self.proxy = proxy
        self.model = model or CONFIG.get('DEFAULT_MODEL_NAME', "local-model")
        self.max_iterations = max_iterations
        self.workspace = Path(workspace_dir or CONFIG['WORKSPACE_DIR']).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        
        # Override config if specified
        if rlm_enabled is not None: CONFIG['RLM_ENABLED'] = rlm_enabled
        if rlm_depth is not None: CONFIG['RLM_RECURSION_DEPTH'] = rlm_depth
        if hitl_enabled is not None: CONFIG['HITL_ENABLED'] = hitl_enabled
        if debug_mode is not None: CONFIG['DEBUG_MODE'] = debug_mode
        
        # #1 - Response deduplication cache (content_hash -> timestamp)
        self.response_cache = {}
        self.response_cache_size = 10  # Keep last 10 responses
        
        goal_hash = sanitize_goal_for_filename(goal)
        self.state_file = self.workspace.parent / f"ralph_state_{goal_hash}.json"
        
        self.state = {
            "iteration": 0,
            "goal": goal, # Keep goal in state for consistency, though self.goal exists
            "context": {}, # Original context, might be removed if not used
            "observations": [],
            "history_summary": "",
            "artifacts": {}, # Original artifacts, might be removed if not used
            "failures": [],
            "done": False,
            "error": None,
            "plan": {
                "tasks": [],
                "current_task_id": None
            },
            "iteration_log": [],
            "stagnation_count": 0,
            "loop_type": None,  # Tracks the type of detected loop
            "rch_metrics": {
                "compressions": 0,
                "total_chars_before": 0,
                "total_chars_after": 0,
                "total_tokens_saved": 0,
                "last_compression_ratio": 0,
                "history_size_trend": []
            }
        }
        
        # Save full spec to workspace for agent reference
        full_spec_path = get_safe_path(self.workspace, "_full_spec.md")
        full_spec_path.write_text(goal, encoding='utf-8')
        
        # Extract brief goal summary (first paragraph or first 500 chars)
        # brief_goal = self._extract_brief_goal(goal) # This is now self.brief_goal
        
        system_prompt = (
            f"{DEFAULT_SYSTEM_PROMPT}\n\n"
            f"=== YOUR GOAL (Brief) ===\n{self.brief_goal}\n\n"
            f"Full specification available in workspace: '_full_spec.md' (use read action to access)\n"
            f"Your plan status is sent with each iteration.\n"
            f"=================\n"
        )
        self.messages = [{"role": "system", "content": system_prompt}]
        
        self._load_state()

    def _extract_brief_goal(self, goal: str) -> str:
        """Extract a brief summary from the full goal specification."""
        lines = goal.split('\n')
        
        # Find first meaningful content (skip markdown headers)
        brief_lines = []
        char_count = 0
        max_chars = 500
        
        for line in lines:
            stripped = line.strip()
            # Skip empty lines and markdown separators
            if not stripped or stripped.startswith('---') or stripped.startswith('==='):
                continue
            # Stop at second header (indicating end of intro section)
            if stripped.startswith('#') and brief_lines and any(l.startswith('#') for l in brief_lines):
                break
            
            brief_lines.append(line)
            char_count += len(line)
            
            if char_count >= max_chars:
                break
        
        brief = '\n'.join(brief_lines[:15])  # Max 15 lines
        if len(brief) > max_chars:
            brief = brief[:max_chars] + "..."
        
        return brief if brief else "Build the application as specified."

    def _load_state(self):
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    saved = json.load(f)
                    if saved.get('goal') == self.goal:
                        # If HITL is enabled, ask the user if they want to resume
                        if CONFIG.get('HITL_ENABLED', False):
                            print(f"\n[RALPH] Existing state found from Iteration {saved.get('iteration', 0)}.")
                            choice = input("[USER] Resume from previous state? (Y/n): ").strip().lower()
                            if choice == 'n':
                                print("[RALPH] Starting fresh (ignoring previous state).")
                                return
                        
                        self.state.update(saved)
                        if "plan" not in self.state:
                            self.state["plan"] = {"tasks": [], "current_task_id": None}
                        if CONFIG.get('DEBUG_MODE'):
                            print(f"[RALPH] Resumed from iteration {self.state['iteration']}")
            except Exception as e:
                print(f"[RALPH] Error loading state: {e}")

    def _save_state(self):
        try:
            # Update iteration log with recent observations before saving
            if self.state["observations"]:
                latest_obs = " | ".join(str(o) for o in self.state["observations"][-3:])
                # Only add if it's a new iteration or different from last log
                if not self.state["iteration_log"] or self.state["iteration_log"][-1]["iter"] != self.state["iteration"]:
                    self.state["iteration_log"].append({
                        "iter": self.state["iteration"],
                        "task": self.state["plan"].get("current_task_id"),
                        "summary": latest_obs[:1000]
                    })

            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            self._sync_plan_to_file()
            self._sync_enhanced_state_files()
        except Exception as e:
            print(f"[RALPH] Error saving state: {e}")

    def _sync_enhanced_state_files(self):
        """Update whole.task.md and current.state.md for better failure recovery."""
        try:
            # 1. Update whole.task.md (Cumulative log)
            whole_md = [f"# RALPH Universal History\n\n**Goal**: {self.goal}\n", "## Full Plan\n"]
            tasks = self.state["plan"].get("tasks", [])
            for t in tasks:
                status = t.get("status", "todo")
                icon = "✅" if status == "done" else "⏳" if status == "in_progress" else "⚪"
                whole_md.append(f"- {icon} **{t.get('id')}**: {t.get('desc')}")
                if t.get("result"): whole_md.append(f"  - _Result_: {t.get('result')}")

            whole_md.append("\n## Iteration Log\n")
            for entry in self.state.get("iteration_log", []):
                task_str = f" [{entry.get('task')}]" if entry.get('task') else ""
                whole_md.append(f"### Iteration {entry['iter']}{task_str}")
                whole_md.append(f"{entry['summary']}\n")

            whole_path = get_safe_path(self.workspace, CONFIG['WHOLE_STATE_FILE'])
            whole_path.write_text("\n".join(whole_md), encoding='utf-8')

            # 2. Update current.state.md (Immediate snapshot)
            curr_md = [
                "# RALPH Current State",
                f"**Iteration**: {self.state['iteration']}",
                f"**Active Task**: {self.state['plan'].get('current_task_id') or 'Planning...'}",
                "\n## Recent Observations",
            ]
            for obs in self.state["observations"][-5:]:
                curr_md.append(f"- {str(obs)[:500]}")
            
            if self.state["failures"]:
                curr_md.append("\n## Recent Failures")
                for fail in self.state["failures"][-3:]:
                    curr_md.append(f"- {fail}")

            curr_path = get_safe_path(self.workspace, CONFIG['CURRENT_STATE_FILE'])
            curr_path.write_text("\n".join(curr_md), encoding='utf-8')
            
            if CONFIG.get('DEBUG_MODE'):
                print(f"[RALPH] Updated history: {CONFIG['WHOLE_STATE_FILE']}, {CONFIG['CURRENT_STATE_FILE']}")
        except Exception as e:
            print(f"[RALPH] Error syncing enhanced state: {e}")

    def _sync_plan_to_file(self):
        """Write the current plan to a human-readable markdown file in the workspace."""
        plan = self.state.get("plan", {})
        tasks = plan.get("tasks", [])

        md = [f"# RALPH Task Board\n\n**Goal**: {self.goal}\n", "## Plan Status\n"]
        if not tasks:
            md.append("_No tasks defined yet. Agent is planning..._")
        else:
            for t in tasks:
                status = t.get("status", "todo")
                icon = "✅" if status == "done" else "⏳" if status == "in_progress" else "⚪"
                current = " 👈 **ACTIVE**" if plan.get("current_task_id") == t.get("id") else ""
                md.append(f"- {icon} **{t.get('id')}**: {t.get('desc')}{current}")
                if t.get("result"):
                    md.append(f"  - _Result_: {t.get('result')}")

        try:
            path = get_safe_path(self.workspace, CONFIG['PLAN_FILE'])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(md), encoding='utf-8')
            if CONFIG.get('DEBUG_MODE'):
                print(f"[RALPH] Updated Task Board: {CONFIG['PLAN_FILE']}")
        except Exception as e:
            print(f"[RALPH] Error syncing plan file: {e}")

    def _summarize_observations(self):
        """Move older observations into history_summary to save context tokens."""
        # Summarize if too many items OR total length is too large
        total_len = sum(len(str(o)) for o in self.state["observations"])
        
        if len(self.state["observations"]) > CONFIG['MAX_OBSERVATIONS_BEFORE_SUMMARY'] or total_len > 4000:
            to_summarize = self.state["observations"][:-CONFIG['RECENT_OBSERVATIONS_COUNT']]
            
            # Group observations by iteration/task if possible, or just deduplicate
            summarized_list = []
            for obs in to_summarize:
                clean_obs = str(obs).strip()
                if not summarized_list or clean_obs != summarized_list[-1]:
                    # Skip noise like "Result: Exit 0" if it's too common
                    if not any(noise in clean_obs for noise in ["Exit 0", "Wrote 0 bytes"]):
                        # Truncate very long individual bits in summary
                        if len(clean_obs) > 500: clean_obs = clean_obs[:500] + "..."
                        summarized_list.append(clean_obs)
            
            if summarized_list:
                # Add to history summary
                summary_text = f"Iter {self.state['iteration']}: " + " | ".join(summarized_list)
                self.state["history_summary"] += (f"\n- {summary_text}")
            
            # Keep history_summary under control (last ~3000 chars)
            if len(self.state["history_summary"]) > 3000:
                self.state["history_summary"] = "... " + self.state["history_summary"][-3000:]
                
            self.state["observations"] = self.state["observations"][-CONFIG['RECENT_OBSERVATIONS_COUNT']:]
            
            if CONFIG.get('DEBUG_MODE'):
                print(f"[RALPH] Consolidated observations into history summary (removed {len(to_summarize)} entries)")

    def _recursive_summarize_history(self):
        """[RCH] Use LLM to compress history into high-density narrative."""
        if not CONFIG.get('ENABLE_RCH', False):
            return
        
        # Calculate context usage
        current_chars = sum(len(m['content']) for m in self.messages)
        max_chars = CONFIG.get('MAX_CONTEXT_CHARS', 100000)
        threshold_chars = max_chars * CONFIG.get('RCH_THRESHOLD_PERCENT', 0.9)
        
        # Trigger if context exceeds threshold % OR periodically as fallback
        # Periodically fallback ensures we don't go TOO long without summarizing
        should_trigger = (current_chars >= threshold_chars) or \
                         (self.state["iteration"] % CONFIG.get('RECURSIVE_SUMMARY_INTERVAL', 10) == 0)
        
        if not should_trigger:
            return
        
        # Skip if no history to compress
        if not self.state.get("history_summary") and len(self.state["observations"]) < 2:
            return
        
        # Initialize RCH metrics if not present
        if "rch_metrics" not in self.state:
            self.state["rch_metrics"] = {
                "compressions": 0,
                "total_chars_before": 0,
                "total_chars_after": 0,
                "total_tokens_saved": 0,
                "last_compression_ratio": 0,
                "history_size_trend": []
            }
        
        trigger_reason = f"Context at {current_chars/max_chars:.1%} usage" if current_chars >= threshold_chars else "Scheduled interval"
        if CONFIG.get('DEBUG_MODE'):
            print(f"\n{'='*60}")
            print(f"[PHASE 0] Performing Recursive History Summarization (RCH) - {trigger_reason}")
            print(f"Iteration: {self.state['iteration']} | Compression #{self.state['rch_metrics']['compressions'] + 1}")
            print(f"{'='*60}\n")
        
        # Prepare data for historian
        current_summary = self.state.get("history_summary", "")
        recent_obs = self.state["observations"][-10:]  # Last 10 observations
        iteration_log = self.state.get("iteration_log", [])[-5:]  # Last 5 iteration logs
        
        # Calculate pre-compression size
        raw_logs = []
        for i, obs in enumerate(recent_obs):
            raw_logs.append(f"• {obs}")
        
        raw_logs_text = "\n".join(raw_logs)
        pre_compression_size = len(current_summary) + len(raw_logs_text)
        
        historian_context = f"""
CURRENT HISTORY SUMMARY:
{current_summary if current_summary else '(No previous summary)'}

RECENT RAW LOGS (Last {len(recent_obs)} observations):
{raw_logs_text}

ITERATION LOG:
{chr(10).join([f"Iter {log.get('iter')}: Task {log.get('task')} - {log.get('summary', '')[:200]}" for log in iteration_log])}
"""
        
        historian_prompt = f"""You are a project historian tasked with creating a high-density narrative summary.

Your goal: Compress the raw logs into a coherent story (MAX {CONFIG['MAX_SUMMARY_CHARS']} chars) that captures:
1. KEY DECISIONS and the reasoning behind them
2. FAILURES and their root causes
3. SUCCESSFUL OUTCOMES and what enabled them  
4. ARCHITECTURAL CHANGES or pivots in approach
5. IMPORTANT CONTEXT that future iterations need

DISCARD noise such as:
- Successful file creations (unless architecturally significant)
- Repeated commands that didn't change anything
- Generic observations like "Exit 0" or "file written"
- Redundant status updates

PRESERVE intent and causality:
- WHY decisions were made, not just WHAT was done
- Connections between failures and subsequent fixes
- Evolution of the codebase/approach

Output ONLY the compressed summary, no preamble. Be concise and factual.

{historian_context}

COMPRESSED SUMMARY:"""

        try:
            import time
            start_time = time.time()
            
            # Call LLM to compress history using the correct method
            response = self.proxy.chat_completion(
                messages=[{"role": "user", "content": historian_prompt}],
                model=self.model,
                max_tokens=1000,
                temperature=0.3,  # Lower temp for more factual compression
                stream=False
            )
            
            compression_time = time.time() - start_time
            
            # Extract the compressed summary from response
            if isinstance(response, dict) and 'choices' in response and len(response['choices']) > 0:
                compressed_summary = response['choices'][0]['message']['content'].strip()
            else:
                raise Exception(f"Unexpected response format: {response}")
            
            # Enforce character limit
            if len(compressed_summary) > CONFIG['MAX_SUMMARY_CHARS']:
                compressed_summary = compressed_summary[:CONFIG['MAX_SUMMARY_CHARS']] + "..."
            
            post_compression_size = len(compressed_summary)
            
            # Calculate metrics
            chars_saved = pre_compression_size - post_compression_size
            compression_ratio = (1 - post_compression_size / pre_compression_size) * 100 if pre_compression_size > 0 else 0
            
            # Rough token estimation: ~4 chars per token
            tokens_saved = chars_saved // 4
            
            # Update metrics
            self.state["rch_metrics"]["compressions"] += 1
            self.state["rch_metrics"]["total_chars_before"] += pre_compression_size
            self.state["rch_metrics"]["total_chars_after"] += post_compression_size
            self.state["rch_metrics"]["total_tokens_saved"] += tokens_saved
            self.state["rch_metrics"]["last_compression_ratio"] = compression_ratio
            self.state["rch_metrics"]["history_size_trend"].append({
                "iteration": self.state["iteration"],
                "size": post_compression_size
            })
            
            # Update state
            self.state["history_summary"] = compressed_summary
            self.state["observations"] = self.state["observations"][-CONFIG['RECENT_OBSERVATIONS_COUNT']:]
            
            # Display metrics
            if CONFIG.get('DEBUG_MODE'):
                print(f"┌{'─'*58}┐")
                print(f"│ {'RCH COMPRESSION METRICS':<56} │")
                print(f"├{'─'*58}┤")
                print(f"│ Pre-compression:  {pre_compression_size:>6} chars (~{pre_compression_size//4:>5} tokens) {'':>16} │")
                print(f"│ Post-compression: {post_compression_size:>6} chars (~{post_compression_size//4:>5} tokens) {'':>16} │")
                print(f"│ {'─'*56} │")
                print(f"│ Chars saved:      {chars_saved:>6} ({compression_ratio:>5.1f}% reduction) {'':>14} │")
                print(f"│ Tokens saved:     ~{tokens_saved:>5} tokens {'':>28} │")
                print(f"│ Compression time:   {compression_time:.2f}s {'':>30} │")
                print(f"├{'─'*58}┤")
                print(f"│ Total compressions: {self.state['rch_metrics']['compressions']:>3} {'':>33} │")
                print(f"│ Total tokens saved: ~{self.state['rch_metrics']['total_tokens_saved']:>5} {'':>33} │")
                print(f"│ History plateau:    {post_compression_size:>4}/{CONFIG['MAX_SUMMARY_CHARS']} chars ({'✓ Bounded' if post_compression_size < CONFIG['MAX_SUMMARY_CHARS'] else '⚠ AT LIMIT'}) {'':>13} │")
                print(f"└{'─'*58}┘\n")
            
        except Exception as e:
            print(f"[RCH ERROR] Failed to perform recursive summarization: {e}")
            print(f"└{'─'*58}┘\n")
            # Fall back to standard summarization
            pass

    def _rlm_internal_dialogue(self, messages: List[Dict[str, str]], depth: int) -> str:
        """
        Recursive Layered Model (RLM) internal loop with Latency Tracking.
        """
        _rlm_start = time.time()
        timings = {}
        
        if CONFIG.get('DEBUG_MODE'): print(f"[RLM] Entering internal dialogue (Level: {depth})")
        
        # 1. Draft Phase
        phase_start = time.time()
        draft_content = self.proxy.chat_completion_sync(messages=messages, model=self.model, max_tokens=2000)
        timings['draft'] = time.time() - phase_start
        
        if depth <= 0:
            return draft_content

        # 2. Critique Phase
        if CONFIG.get('DEBUG_MODE'): print("[RLM]   -> Generating internal critique...")
        phase_start = time.time()
        critique_messages = messages + [
            {"role": "assistant", "content": draft_content},
            {"role": "user", "content": (
                "CRITIQUE: Review your previous plan for logic errors or missing data. "
                "CRITICAL: If the plan involves facts you aren't 100% sure of, suggest a SEARCH. "
                "If we just performed a search, did the results actually answer the user, or do we need to 'web_read' a specific URL? "
                "Highlight flaws and missing info, but DO NOT generate JSON yet."
            )}
        ]
        critique_content = self.proxy.chat_completion_sync(messages=critique_messages, model=self.model)
        timings['critique'] = time.time() - phase_start
        
        # 3. Refinement Phase
        if CONFIG.get('DEBUG_MODE'): print("[RLM]   -> Refining final action...")
        phase_start = time.time()
        refine_messages = critique_messages + [
            {"role": "assistant", "content": critique_content},
            {"role": "user", "content": (
                "FINAL REFINEMENT: Incorporate your self-critique. If you decided a search or web_read is needed, "
                "output that action now. Otherwise, provide the corrected implementation JSON."
            )}
        ]
        
        final_content = self.proxy.chat_completion_sync(messages=refine_messages, model=self.model, max_tokens=2000)
        timings['refinement'] = time.time() - phase_start
        
        total_time = time.time() - _rlm_start
        if CONFIG.get('DEBUG_MODE'):
            print(f"[RLM] Execution Summary: Draft={timings['draft']:.1f}s, Critique={timings['critique']:.1f}s, Refinement={timings['refinement']:.1f}s")
            print(f"[RLM] Total Thinking Time: {total_time:.1f}s")
        
        return final_content


    def _normalize_exec_data(self, data: Any) -> Dict[str, Any]:
        """Flatten nested action objects and handle common LLM hallucinations."""
        if not isinstance(data, dict):
            return {}
        
        # If action is an object like {"type": "write", "file": "..."}, flatten it
        action_val = data.get("action")
        if isinstance(action_val, dict):
            action_type = action_val.get("type", action_val.get("action"))
            for k, v in action_val.items():
                if k not in data: data[k] = v
            data["action"] = action_type
        elif not action_val and "type" in data:
            data["action"] = data.get("type")

        # Normalize common field aliases
        aliases = {"cmd": "command", "file_path": "file", "path_target": "path"}
        for alias, target in aliases.items():
            if alias in data and target not in data:
                data[target] = data[alias]
                
        return data

    def _handle_execution(self, exec_data: Dict[str, Any]) -> str:
        exec_data = self._normalize_exec_data(exec_data)
        action = exec_data.get("action")
        
        if action in ["write", "edit"]:
            filename = exec_data.get("file")
            content = exec_data.get("content", "")
            if not filename: return "Error: No filename"
            path = get_safe_path(self.workspace, filename)
            
            if CONFIG.get('DEBUG_MODE'):
                print(f"[RALPH] Executing {action}: {filename}")

            # Redundancy check: don't write if identical content already exists
            if path.exists():
                try:
                    existing = path.read_text(encoding='utf-8')
                    if existing == content:
                        return f"Skipped: Content for {filename} is already identical to existing file. Try a different approach."
                except Exception:
                    pass

            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding='utf-8')
                return f"Wrote {len(content)} bytes to {path.relative_to(self.workspace)}"
            except Exception as e:
                return f"Write error: {e}"

        elif action == "run":
            cmd = exec_data.get("command")
            if not cmd: return "Error: No command"
            if CONFIG.get('DEBUG_MODE'):
                print(f"[RALPH] Executing run: {cmd}")
            # Basic safety
            if any(f in f" {cmd}".lower() for f in ["rm ", "sudo ", "mv "]):
                return f"Error: Command blocked for safety: {cmd}"
            try:
                res = subprocess.run(cmd, shell=True, cwd=self.workspace, capture_output=True, text=True, timeout=60)
                out = clean_output(res.stdout + res.stderr)
                return f"Exit {res.returncode}\nOutput: {out[:1000]}"
            except Exception as e:
                return f"Run error: {e}"

        elif action == "ls":
            path_name = exec_data.get("path", ".")
            recursive = exec_data.get("recursive", False)
            try:
                dir_path = get_safe_path(self.workspace, path_name)
                if recursive:
                    results = []
                    for root, dirs, files in os.walk(dir_path):
                        rel_root = os.path.relpath(root, self.workspace)
                        if rel_root == ".": rel_root = ""
                        for f in files:
                            results.append(os.path.join(rel_root, f))
                    return f"Project Tree:\n" + "\n".join(results)
                else:
                    items = os.listdir(dir_path)
                    return f"Contents of {dir_path.relative_to(self.workspace)}: {', '.join(items)}"
            except Exception as e:
                return f"ls error: {e}"

        elif action == "read":
            filename = exec_data.get("file")
            if not filename: return "Error: No filename"
            try:
                path = get_safe_path(self.workspace, filename)
                content = path.read_text(encoding='utf-8')
                max_chars = CONFIG.get('MAX_OBSERVATION_CHARS', 1500)
                if len(content) > max_chars:
                    content = content[:max_chars] + f"\n\n[... Truncated {len(content) - max_chars} chars ...]"
                return f"Content of {filename}:\n---\n{content}\n---"
            except Exception as e:
                return f"read error: {e}"

        elif action == "mkdir":
            path_name = exec_data.get("path")
            if not path_name: return "Error: No path"
            try:
                path = get_safe_path(self.workspace, path_name)
                path.mkdir(parents=True, exist_ok=True)
                return f"Created directory: {path_name}"
            except Exception as e:
                return f"mkdir error: {e}"

        elif action == "grep":
            query = exec_data.get("query")
            if not query: return "Error: No query"
            try:
                res = subprocess.run(f"grep -rnE '{query}' .", shell=True, cwd=self.workspace, capture_output=True, text=True)
                return f"Search for '{query}':\n{res.stdout or 'No matches'}"
            except Exception as e:
                return f"grep error: {e}"
        elif action == "chat":
            return f"Chat message: {exec_data.get('message', 'No message content')}"

        elif action == "plan_update":
            return "Plan update requested. (Processed via top-level logic)"

        elif action == "search":
            query = exec_data.get("query")
            if not query: return "Error: No query"
            try:
                try:
                    from ddgs import DDGS
                except ImportError:
                    from duckduckgo_search import DDGS
                
                with DDGS() as ddgs:
                    results = [r for r in ddgs.text(query, max_results=8)]
                    
                    # If no results, try query relaxation (remove "current weather in" etc.)
                    if not results:
                        simplified = re.sub(r'^(current |today\'s )?weather in ', '', query, flags=re.I).strip()
                        if simplified != query:
                            results = [r for r in ddgs.text(simplified, max_results=5)]
                    
                    if not results:
                        return f"Search for '{query}' returned no results. Try a broader query."
                    
                    formatted = []
                    for r in results:
                        formatted.append(f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}\n")
                    return f"Search results for '{query}':\n\n" + "\n".join(formatted)
            except Exception as e:
                return f"Search error: {e}. (Recommend: pip install ddgs)"

        elif action == "web_read":
            url = exec_data.get("url")
            if not url: return "Error: No URL"
            try:
                import trafilatura
                downloaded = trafilatura.fetch_url(url)
                content = trafilatura.extract(downloaded)
                if not content: return "Error: Could not extract content from the URL."
                return f"Content of {url}:\n---\n{content[:2500]}\n---"
            except Exception as e:
                return f"Web read error: {e}. (Ensure 'trafilatura' is installed)"

        return f"Unknown action: {action}"

    def _compress_assistant_message(self, content: str) -> str:
        """
        Compress an assistant message to preserve intent and outcome while saving tokens.
        Returns a condensed version that keeps:
        - The observation (outcome)
        - Any execute blocks (intent/actions)
        - Any reasoning before JSON (if present)
        """
        from .parser import ResponseParser
        
        # Parse the full response to extract structured data
        update = ResponseParser.parse_state_update(content)
        
        # Build compressed summary
        parts = []
        
        # 1. Preserve any reasoning/thoughts (text before the JSON block)
        json_start = content.find('```json')
        if json_start > 50:  # If there's meaningful text before JSON
            reasoning = content[:json_start].strip()
            # Keep first N chars of reasoning
            if reasoning:
                max_reasoning = CONFIG.get('PRESERVE_REASONING_CHARS', 200)
                parts.append(f"Reasoning: {reasoning[:max_reasoning]}")
        
        # 2. Preserve execute intent (what was attempted)
        if "execute" in update:
            execs = update["execute"]
            if not isinstance(execs, list):
                execs = [execs]
            for ex in execs:
                action = ex.get("action", "unknown")
                if action == "write":
                    parts.append(f"Action: write {ex.get('file', 'unknown')}")
                elif action == "run":
                    parts.append(f"Action: run '{ex.get('command', 'unknown')}'")
                elif action == "read":
                    parts.append(f"Action: read {ex.get('file', 'unknown')}")
                elif action == "search":
                    parts.append(f"Action: search '{ex.get('query', 'unknown')}'")
                elif action == "web_read":
                    parts.append(f"Action: web_read {ex.get('url', 'unknown')}")
                else:
                    parts.append(f"Action: {action}")
        
        # 3. Preserve observation (outcome)
        obs = update.get("observation", "")
        if obs:
            # Truncate long observations
            max_obs = CONFIG.get('PRESERVE_OBSERVATION_CHARS', 300)
            obs_truncated = str(obs)[:max_obs]
            parts.append(f"Result: {obs_truncated}")
        
        # 4. Preserve plan change (if any)
        if "plan_update" in update:
            pu = update["plan_update"]
            if isinstance(pu, dict):
                current = pu.get("current_task_id")
                if current:
                    parts.append(f"Switched to: {current}")
        
        return " | ".join(parts) if parts else "[No significant action]"

    def _check_response_duplication(self, content: str) -> tuple[bool, str]:
        """
        #1 - Check if the response is a duplicate of recent responses.
        Returns (is_duplicate, cache_key)
        """
        import hashlib
        import time
        from .parser import ResponseParser
        
        # Extract the key content that makes a response unique
        update = ResponseParser.parse_state_update(content)
        
        # Create a signature from chat messages or actions
        signature_parts = []
        
        # If it's a chat message, use that
        if "chat" in update:
            signature_parts.append(f"chat:{update['chat']}")
        elif "message" in update:
            signature_parts.append(f"message:{update['message']}")
        
        # Add actions taken
        if "execute" in update:
            execs = update["execute"] if isinstance(update["execute"], list) else [update["execute"]]
            for ex in execs:
                action = ex.get("action", "?")
                if action == "chat":
                    signature_parts.append(f"chat:{ex.get('message', '')}")
                else:
                    signature_parts.append(f"{action}:{ex.get('file', ex.get('command', ex.get('query', '')))}")
        
        # If no signature could be extracted, it's not a duplicate-able response
        if not signature_parts:
            return False, None
        
        # Create hash
        signature = "|".join(signature_parts)
        cache_key = hashlib.md5(signature.encode()).hexdigest()[:12]
        
        # Check cache
        current_time = time.time()
        if cache_key in self.response_cache:
            # Found duplicate!
            last_time = self.response_cache[cache_key]
            if CONFIG.get('DEBUG_MODE'):
                print(f"[DEDUP] Response hash collision detected: {cache_key} (last seen {current_time - last_time:.1f}s ago)")
            return True, cache_key
        
        # Add to cache
        self.response_cache[cache_key] = current_time
        
        # Maintain cache size (keep only recent N entries)
        if len(self.response_cache) > self.response_cache_size:
            # Remove oldest entry
            oldest_key = min(self.response_cache, key=self.response_cache.get)
            del self.response_cache[oldest_key]
        
        return False, cache_key

        
    def _render_hitl_chat_history(self):
        """Render the last 4 messages in a beautiful, colored terminal format."""
        import textwrap
        ORANGE = "\033[38;5;208m"
        CYAN = "\033[36m"
        RESET = "\033[0m"
        BOLD = "\033[1m"
        
        # Filter out system messages
        chat_msgs = [m for m in self.messages if m['role'] != 'system']
        # Take the last 4
        display_msgs = chat_msgs[-4:]
        
        if not display_msgs:
            return

        print(f"\n  {BOLD}RECENT CONVERSATION:{RESET}")
        
        for msg in display_msgs:
            role = msg['role']
            content = msg['content']
            
            if role == 'user':
                # 1. Strip the "Current State" and "Directive" wrappers
                if "### USER DIRECTIVE ###" in content:
                    clean_content = content.split("### USER DIRECTIVE ###")[1].split("######################")[0].strip()
                elif "Proceed with next step." in content:
                    clean_content = "(No feedback - proceeding)"
                else:
                    # Fallback for simple prompts
                    clean_content = content.split("\n")[-1].strip() if "\n" in content else content
                
                # Right align user messages
                wrapped = textwrap.wrap(clean_content, width=50)
                for i, line in enumerate(wrapped):
                    prefix = f"{CYAN}You > {RESET}" if i == 0 else "      "
                    # Fixed width of 80 for the whole terminal
                    indent = 80 - len(line) - 8
                    print(" " * indent + f"{prefix}{line}")
            
            else: # assistant
                # Parse the JSON to get the 'chat' message or action summary
                from .parser import ResponseParser
                update = ResponseParser.parse_state_update(content)
                
                clean_content = None
                
                # 1. Look for top-level chat/message keys
                if "chat" in update: clean_content = str(update["chat"])
                elif "message" in update: clean_content = str(update["message"])
                
                # 2. Look for 'chat' action within execute list
                if not clean_content and "execute" in update:
                    execs = update["execute"] if isinstance(update["execute"], list) else [update["execute"]]
                    for ex in execs:
                        if ex.get("action") == "chat":
                            clean_content = ex.get("message") or ex.get("content") or ex.get("chat")
                            break
                
                # 3. Fallback to summarizing actions
                if not clean_content:
                    actions = []
                    if "execute" in update:
                        execs = update["execute"] if isinstance(update["execute"], list) else [update["execute"]]
                        for ex in execs:
                            actions.append(f"{ex.get('action')}({ex.get('file') or ex.get('command') or ''})")
                    clean_content = f"[Performing Actions: {', '.join(actions)}]" if actions else "[Thinking...]"

                # Left align assistant messages in Orange
                wrapped = textwrap.wrap(clean_content, width=60)
                for i, line in enumerate(wrapped):
                    prefix = f"{ORANGE}RALPH > {RESET}" if i == 0 else "        "
                    print(f"  {prefix}{ORANGE}{line}{RESET}")
        print()

    def run_step(self):
        self.state["iteration"] += 1
        self._summarize_observations()
        
        # [RCH] Perform recursive history summarization every N iterations
        self._recursive_summarize_history()
        
        if CONFIG.get('DEBUG_MODE') and not CONFIG.get('HITL_ENABLED'):
            print(f"\n{SEPARATOR}\n  Iteration {self.state['iteration']}\n{SEPARATOR}")
        
        # Enhanced repetition detection logic
        recent = self.state["observations"][-5:]
        is_looping = False
        loop_type = None
        
        if len(recent) >= 3:
            # (re-pasting the repetition logic)
            if all(x == recent[-1] for x in recent[-3:]):
                is_looping = True
                loop_type = "identical_observations"
            if recent[-1].startswith("Skipped:"):
                is_looping = True
                loop_type = "redundant_writes"
            recent_str = " | ".join(str(o) for o in recent[-3:])
            if "Action: read" in recent_str and "Action: write" not in recent_str and "Action: run" not in recent_str:
                if recent_str.count("Action: read") >= 2:
                    is_looping = True
                    loop_type = "read_loop"
            if recent_str.count("Plan updated") >= 2 and "Executing" not in recent_str:
                is_looping = True
                loop_type = "planning_loop"
            if "Action: run" in recent_str:
                run_commands = []
                for obs in recent[-5:]:
                    obs_str = str(obs)
                    if "Executing run:" in obs_str:
                        cmd = obs_str.split("Executing run:")[-1].strip()
                        run_commands.append(cmd)
                if len(run_commands) >= 3:
                    pip_installs = [cmd for cmd in run_commands if "pip install" in cmd.lower()]
                    if len(pip_installs) >= 3:
                        is_looping = True
                        loop_type = "command_loop"
        
        if is_looping:
            self.state["stagnation_count"] += 1
            self.state["loop_type"] = loop_type
            print(f"[RALPH] Stagnation detected ({loop_type}). Count: {self.state['stagnation_count']}/{CONFIG['STAGNATION_THRESHOLD']}")
        else:
            self.state["stagnation_count"] = 0
            self.state["loop_type"] = None

        repetition_note = ""
        if self.state["stagnation_count"] >= CONFIG['STAGNATION_THRESHOLD']:
            print(f"[RALPH] Safety Kill: Loop detected for {CONFIG['STAGNATION_THRESHOLD']} iterations.")
            self.state["error"] = f"Loop detected: Agent stopped to prevent token waste. Check {CONFIG['WHOLE_STATE_FILE']} to debug."
            self.state["done"] = True
            return

        if self.state["stagnation_count"] >= 2:
            # Provide targeted remediation based on loop type
            loop_type = self.state.get("loop_type", "unknown")
            
            if loop_type == "planning_loop":
                remediation = (
                    "You are stuck in a PLANNING LOOP - updating plans without executing actions.\n"
                    "REQUIRED ACTION: Stop planning and START EXECUTING:\n"
                    "  1. Use {'action': 'write', ...} to create/modify a file\n"
                    "  2. Use {'action': 'run', 'command': '...'} to test your code\n"
                    "  3. Use {'action': 'read', ...} only if you need to check file contents\n"
                    "DO NOT just read files and update plans. Take concrete action NOW."
                )
            elif loop_type == "read_loop":
                remediation = (
                    "You are stuck in a READ LOOP - reading files without taking action.\n"
                    "REQUIRED ACTION: Stop reading and START BUILDING:\n"
                    "  1. Write actual implementation code (not placeholders)\n"
                    "  2. Run tests to identify errors\n"
                    "  3. Fix the errors you find\n"
                    "Reading files will not make progress. Execute something concrete NOW."
                )
            elif loop_type == "redundant_writes":
                remediation = (
                    "You are trying to write identical content repeatedly.\n"
                    "REQUIRED ACTION: Change your approach:\n"
                    "  1. Read the file you're trying to write to understand what exists\n"
                    "  2. Identify what's DIFFERENT from what you want\n"
                    "  3. Write ONLY the changed version\n"
                    "  4. Or try a completely different approach to solve the problem"
                )
            elif loop_type == "command_loop":
                remediation = (
                    "You are stuck in a COMMAND LOOP - running the same commands repeatedly.\n"
                    "REQUIRED ACTION: Stop repeating commands and ANALYZE THE PROBLEM:\n"
                    "  1. The command likely succeeded - check if packages are already installed\n"
                    "  2. If you're getting errors, READ THE ERROR MESSAGE carefully\n"
                    "  3. Try a DIFFERENT approach instead of running the same command\n"
                    "  4. Consider: Are you solving the right problem?\n"
                    "Running 'pip install' repeatedly will NOT fix import errors caused by code issues."
                )
            else:
                remediation = (
                    f"Suggested: Read '{CONFIG['WHOLE_STATE_FILE']}' and '{CONFIG['PLAN_FILE']}' to re-orient yourself."
                )
            
            repetition_note = (
                f"\n\n{'='*60}\n"
                f"CRITICAL: You are STAGNANT (Count: {self.state['stagnation_count']}/{CONFIG['STAGNATION_THRESHOLD']}).\n"
                f"You have repeated the same observation multiple times.\n"
                f"YOU MUST CHANGE YOUR APPROACH IMMEDIATELY.\n"
                f"{'='*60}\n\n"
                f"{remediation}\n"
                f"{'='*60}\n"
            )
            
            # Print the warning to console so user can see it
            print(repetition_note)

        state_summary = {
            "iteration": self.state["iteration"],
            "active_task": self.state["plan"].get("current_task_id"),
            "stagnation_metrics": {
                "count": self.state["stagnation_count"],
                "threshold": CONFIG['STAGNATION_THRESHOLD'],
                "detected_loop": self.state.get("loop_type", "none")
            },
            "history_summary": self.state.get("history_summary", ""),
            "recent_observations": self.state["observations"],
            "plan_status": {t["id"]: t["status"] for t in self.state["plan"].get("tasks", [])}
        }
        
        
        if CONFIG.get('HITL_ENABLED', False):
            print(f"\n{SEPARATOR}")
            print(f"  HUMAN-IN-THE-LOOP DASHBOARD (Iter {self.state['iteration']})")
            print(f"{SEPARATOR}")
            print(f"  Current Task:    {state_summary['active_task'] or '---'}")
            
            # Smart observation display: show more if it's a chat message
            last_obs = str(self.state['observations'][-1]) if self.state['observations'] else '---'
            if "chat message:" in last_obs.lower():
                # Extract the actual message content
                if "Result: Chat message: " in last_obs:
                    msg_content = last_obs.split("Result: Chat message: ", 1)[1]
                elif "Chat message: " in last_obs:
                    msg_content = last_obs.split("Chat message: ", 1)[1]
                else:
                    msg_content = last_obs

                # Allow longer chat messages in dashboard (up to 1000 chars)
                if len(msg_content) > 1000: msg_content = msg_content[:997] + "..."
                
                # Simple multi-line wrap for clean dashboard
                import textwrap
                wrapped = textwrap.fill(msg_content, width=80, initial_indent="  ", subsequent_indent="  ")
                print(f"  Last Chat:\n{wrapped}")
            else:
                if len(last_obs) > 1000: last_obs = last_obs[:997] + "..."
                print(f"  Last Obs:        {last_obs}")
            
            # Turn-taking helper: only show for real tool results, not simple chat echoes
            last_obs_str = str(self.state["observations"][-1]) if self.state["observations"] else ""
            if last_obs_str and "Result:" in last_obs_str and "Chat message:" not in last_obs_str:
                print(f"  \033[93m[!] NEW DATA PENDING: Press ENTER to let RALPH process the tool results above.\033[0m")

            print(f"  Stagnation:      {self.state['stagnation_count']}/{CONFIG['STAGNATION_THRESHOLD']} ({self.state.get('loop_type', 'none')})")
            
            # Restore done_tasks definition
            done_tasks = [t['id'] for t in self.state['plan'].get('tasks', []) if t.get('status') == 'done']
            print(f"  Tasks Done:      {', '.join(done_tasks) if done_tasks else 'None'}")
            
            # Message History (Last 4: 2 User, 2 LLM)
            self._render_hitl_chat_history()

            print(f"{SEPARATOR}")
            user_input = input("\n[USER] Feedback/Correction (ENTER to proceed, type 'quit' or special commands like /reset): ").strip()
            
            # #5 - Special Commands
            if user_input.lower() in ["exit", "quit", "stop"]:
                print("\n[RALPH] HITL Session terminated by user.")
                self.state["done"] = True
                return
            
            elif user_input.lower().startswith("/reset"):
                print("\n[RALPH] 🔄 Resetting stagnation counter and observations...")
                self.state["stagnation_count"] = 0
                self.state["loop_type"] = None
                self.state["observations"] = []
                self.response_cache = {}  # Clear response cache
                print("[RALPH] ✓ Reset complete. Fresh start!")
                prompt_text = "The user has reset your state. Start fresh with your current task."
            
            elif user_input.lower().startswith("/replan"):
                print("\n[RALPH] 📋 Forcing replan...")
                self.state["plan"]["current_task_id"] = None
                prompt_text = "The user requests you to REPLAN from scratch. Review the goal and create a new plan."
            
            elif user_input.lower().startswith("/skip"):
                print("\n[RALPH] ⏭️  Skipping current task...")
                current_task_id = self.state["plan"].get("current_task_id")
                if current_task_id:
                    for task in self.state["plan"].get("tasks", []):
                        if task.get("id") == current_task_id:
                            task["status"] = "skipped"
                            print(f"[RALPH] ✓ Marked '{current_task_id}' as skipped.")
                            break
                self.state["plan"]["current_task_id"] = None
                prompt_text = "The user has skipped the current task. Move to the next task in your plan."
            
            elif user_input.lower().startswith("/clear"):
                print("\n[RALPH] 🧹 Clearing conversation history (keeping system prompt)...")
                self.messages = [self.messages[0]]  # Keep only system prompt
                self.state["history_summary"] = ""
                print("[RALPH] ✓ History cleared. Context is now fresh.")
                prompt_text = "The user has cleared the conversation history. Start fresh."
            
            # #5 - Auto-pause detection for repetition complaints
            elif any(phrase in user_input.lower() for phrase in ["don't repeat", "stop repeating", "you already said", "redundant"]):
                print("\n[RALPH] ⚠️  Repetition complaint detected. Forcing fresh perspective...")
                self.state["stagnation_count"] = 0
                self.response_cache = {}  # Clear to allow new responses
                prompt_text = f"\n\n### USER DIRECTIVE ###\n{user_input}\n\nCRITICAL: The user is frustrated with repetition. You MUST provide a completely DIFFERENT response or approach.\n######################\n"
            
            elif user_input:
                # Wrap user input as a high-priority Directive
                prompt_text = f"\n\n### USER DIRECTIVE ###\n{user_input}\n######################\n"
            else:
                prompt_text = "Proceed with next step."
        else:
            prompt_text = "Proceed with next step."

        user_prompt = f"Current State:\n{json.dumps(state_summary, indent=2)}\n\n{prompt_text}{repetition_note}"
        self.messages.append({"role": "user", "content": user_prompt})
        
        # Cache-Aware Sliding Window with Thinning
        current_context_chars = sum(len(m['content']) for m in self.messages)
        max_chars = CONFIG.get('MAX_CONTEXT_CHARS', 80000)
        
        # We only thin if we exceed the char budget OR the message count budget
        msg_count_before = len(self.messages)
        msg_limit = CONFIG['MAX_MESSAGE_HISTORY'] * 2
        
        if len(self.messages) > (msg_limit + 1) or current_context_chars > max_chars:
            system_msg = self.messages[0]
            # Keep the most recent turn fully intact (last 2 messages: user + assistant)
            recent_to_keep = self.messages[-msg_limit:]
            
            # If we're STILL over the char limit, we perform the aggressive thinning
            # on the messages we just decided to keep
            if current_context_chars > max_chars:
                print(f"[RALPH] Context budget exceeded ({current_context_chars} chars). Thinning history to preserve speed.")
                thinned_history = []
                for i, msg in enumerate(recent_to_keep):
                    # Only thin messages older than the last 4 messages to preserve immediate context
                    if i < (len(recent_to_keep) - 4):
                        if msg['role'] == 'assistant':
                            compressed = f"[Compressed] {self._compress_assistant_message(msg['content'])}"
                            thinned_history.append({"role": "assistant", "content": compressed})
                        elif msg['role'] == 'user' and "Current State:" in msg['content']:
                            parts = msg['content'].split("\n\nProceed with next step.")
                            prompt_end = parts[1] if len(parts) > 1 else ""
                            new_content = f"Previous State [truncated]...\n\nProceed with next step.{prompt_end}"
                            thinned_history.append({"role": "user", "content": new_content})
                        else:
                            thinned_history.append(msg)
                    else:
                        thinned_history.append(msg)
                
                self.messages = [system_msg] + thinned_history
            else:
                # If we're just over the message count but NOT the char limit, 
                # we just slide the window without thinning. This is CACHE FRIENDLY!
                # It just removes the oldest entry and shifts the cache.
                self.messages = [system_msg] + recent_to_keep
            
            if CONFIG.get('DEBUG_MODE'):
                print(f"[RALPH] Context Managed: {msg_count_before} \u2192 {len(self.messages)} messages. Cache stability: {'THINNED (Cache Reset)' if current_context_chars > max_chars else 'SLID (Cache Preserved)'}")

        # RLM triggering logic
        content = ""
        should_use_rlm = CONFIG.get('RLM_ENABLED') and CONFIG.get('RLM_RECURSION_DEPTH', 0) > 0
        
        if should_use_rlm and CONFIG.get('RLM_ONLY_ON_CONFUSION'):
            # Check for symptoms of confusion: stagnation or recent errors
            last_obs = str(self.state["observations"][-1]) if self.state["observations"] else ""
            is_error = "Error:" in last_obs or "failed" in last_obs.lower()
            
            # If not looping, not stagnating, and no recent error, skip RLM to save tokens/time
            if not (is_looping or is_error or self.state["stagnation_count"] > 0):
                should_use_rlm = False
        
        if should_use_rlm:
            if CONFIG.get('DEBUG_MODE'):
                print(f"[RLM] Confusion detected or RLM forced. Running recursive thinking (Level: {CONFIG['RLM_RECURSION_DEPTH']})...")
            else:
                print("  [ralph is thinking deeply (RLM)...]", end='', flush=True)
            
            content = self._rlm_internal_dialogue(self.messages, CONFIG['RLM_RECURSION_DEPTH'])
            
            if not CONFIG.get('DEBUG_MODE'):
                print(" done.")
            
            if CONFIG.get('DEBUG_MODE'):
                print(f"\n[RLM Final Answer]:\n{content}\n")
        else:
            if CONFIG.get('DEBUG_MODE'):
                print("[RALPH] Generating response (streaming)...")
                print("[RALPH] Thinking...", end='', flush=True)
            else:
                print("  [ralph is thinking...]", end='', flush=True)

            response = self.proxy.chat_completion(messages=self.messages, model=self.model, stream=True, max_tokens=2000)
            if isinstance(response, dict) and "error" in response:
                error = response.get('error', 'Unknown error')
                print(f"[RALPH] API Error: {error}")
                self.state["error"] = str(error)
                self.state["done"] = True
                return

            for chunk in response.iter_lines():
                if not chunk: continue
                line = chunk.decode('utf-8')
                if line.startswith('data: '):
                    data_str = line[6:]
                    if data_str == '[DONE]': break
                    try:
                        data = json.loads(data_str)
                        delta = data['choices'][0].get('delta', {})
                        if 'content' in delta:
                            c = delta['content']
                            if CONFIG.get('DEBUG_MODE'):
                                print(c, end='', flush=True)
                            content += c
                    except: continue
            if CONFIG.get('DEBUG_MODE'):
                print()
            else:
                print(" done.")
        # ------------------------------------

        # #1 - Check for response deduplication
        is_duplicate, cache_key = self._check_response_duplication(content)
        if is_duplicate:
            if CONFIG.get('DEBUG_MODE') or CONFIG.get('HITL_ENABLED'):
                print(f"\n⚠️  [DEDUP WARNING] This response appears identical to a recent one (hash: {cache_key})")
                print("    RALPH may be stuck in a response loop. Consider using /reset or providing new direction.\n")
            # Mark as potential stagnation
            self.state["observations"].append(f"[INTERNAL WARNING] Duplicate response detected")
        
        self.messages.append({"role": "assistant", "content": content})
        update = ResponseParser.parse_state_update(content)
        
        if "observation" in update: self.state["observations"].append(str(update["observation"]))
        if "done" in update: self.state["done"] = bool(update["done"])
        
        if "plan_update" in update:
            pu = update["plan_update"]
            if isinstance(pu, dict):
                # Update current_task_id if present
                if "current_task_id" in pu:
                    self.state["plan"]["current_task_id"] = pu["current_task_id"]
                
                # Update specific tasks if provided as a dict of id -> updates
                # or a list of task objects
                tasks_input = pu.get("tasks", [])
                if isinstance(tasks_input, list):
                    # Full list replacement or update
                    self.state["plan"]["tasks"] = tasks_input
                elif isinstance(tasks_input, dict):
                    # Targeted updates
                    for tid, changes in tasks_input.items():
                        for task in self.state["plan"]["tasks"]:
                            if task.get("id") == tid:
                                task.update(changes)
                                break
                if CONFIG.get('DEBUG_MODE'):
                    print(f"[RALPH] Plan updated. Current task: {self.state['plan']['current_task_id']}")
        
        if "execute" in update:
            execs = update["execute"]
            if not isinstance(execs, list): execs = [execs]
            for ex in execs:
                res = self._handle_execution(ex)
                self.state["observations"].append(f"Result: {res}")
        
        if "store_knowledge" in update:
            knowledge = update["store_knowledge"]
            pattern = str(knowledge.get("pattern", ""))
            info = str(knowledge.get("info", ""))
            if pattern and info:
                tokens = re.findall(r'\w+|[^\w\s]', pattern.lower())
                compressed = self.proxy.compressor.compress_sequence(tokens)
                self.proxy.memory_store.store(compressed, info[:500], {"source": "ralph_store"})
                if CONFIG.get('DEBUG_MODE'):
                    print(f"[Engram] Stored knowledge: {pattern[:50]}...")

        self.proxy.learn_from_conversation(user_prompt, content, {"iter": self.state["iteration"]})
        self._save_state()

    def start(self):
        while not self.state["done"] and self.state["iteration"] < self.max_iterations:
            self.run_step()
        
        # Display RCH session summary
        if CONFIG.get('DEBUG_MODE') and CONFIG.get('ENABLE_RCH', False) and "rch_metrics" in self.state:
            metrics = self.state["rch_metrics"]
            if metrics["compressions"] > 0:
                print(f"\n{'='*60}")
                print(f"  RCH SESSION SUMMARY")
                print(f"{'='*60}\n")
                print(f"┌{'─'*58}┐")
                print(f"│ {'RECURSIVE HISTORY SUMMARIZATION REPORT':<56} │")
                print(f"├{'─'*58}┤")
                print(f"│ Total iterations:      {self.state['iteration']:>4} {'':>33} │")
                print(f"│ RCH compressions:      {metrics['compressions']:>4} (every {CONFIG['RECURSIVE_SUMMARY_INTERVAL']} iters) {'':>18} │")
                print(f"│ {'─'*56} │")
                print(f"│ Total chars before:    {metrics['total_chars_before']:>6} {'':>31} │")
                print(f"│ Total chars after:     {metrics['total_chars_after']:>6} {'':>31} │")
                print(f"│ Total chars saved:     {metrics['total_chars_before'] - metrics['total_chars_after']:>6} {'':>31} │")
                print(f"│ Overall compression:   {((1 - metrics['total_chars_after']/metrics['total_chars_before'])*100 if metrics['total_chars_before'] > 0 else 0):>5.1f}% {'':>30} │")
                print(f"│ {'─'*56} │")
                print(f"│ Total tokens saved:    ~{metrics['total_tokens_saved']:>5} tokens {'':>25} │")
                print(f"│ Tokens saved per iter: ~{metrics['total_tokens_saved']//self.state['iteration'] if self.state['iteration'] > 0 else 0:>5} tokens/iter {'':>19} │")
                print(f"│ {'─'*56} │")
                print(f"│ Final history size:    {len(self.state.get('history_summary', '')):>4}/{CONFIG['MAX_SUMMARY_CHARS']} chars {'':>27} │")
                print(f"│ History bounded:       {'✓ YES' if len(self.state.get('history_summary', '')) < CONFIG['MAX_SUMMARY_CHARS'] else '⚠ AT LIMIT':>10} {'':>33} │")
                print(f"│ {'─'*56} │")
                
                # Show history size trend
                if metrics["history_size_trend"]:
                    trend = metrics["history_size_trend"]
                    sizes = [t["size"] for t in trend]
                    if len(sizes) >= 2:
                        is_growing = sizes[-1] > sizes[0]
                        trend_status = "⚠ Growing" if is_growing else "✓ Stable/Shrinking"
                    else:
                        trend_status = "─ N/A"
                    print(f"│ History trend:         {trend_status:>10} {'':>33} │")
                    print(f"│ Trend points:          {len(trend):>3} data points {'':>30} │")
                
                print(f"└{'─'*58}┘\n")
        
        print("\nRALPH Loop Terminated.")
