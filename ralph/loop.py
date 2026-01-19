import time
import json
import sys
import os
import subprocess
from pathlib import Path
from datetime import datetime
from .utils import get_safe_path
from .parser import parse_json
from .config import CONFIG

class EngramRalphLoop:
    def __init__(self, goal, proxy, model, max_iterations, rlm_enabled, rlm_depth, hitl_enabled, debug_mode):
        self.goal = goal
        self.proxy = proxy
        self.model = model
        self.max_iterations = max_iterations
        self.rlm_enabled = rlm_enabled
        self.rlm_depth = rlm_depth
        self.hitl_enabled = hitl_enabled
        self.debug_mode = debug_mode

        self.workspace = Path("ralph_workspace")
        self.workspace.mkdir(exist_ok=True)

        self.history = [] # List of dicts {role, content} or interaction objects
        self.history_summary = ""
        self.iteration = 0
        self.done = False
        self.error = None
        self.stagnation_count = 0
        self.last_action_hash = None

        # RCH state
        self.rch_enabled = CONFIG.get('ENABLE_RCH', True)
        self.rch_interval = CONFIG.get('RECURSIVE_SUMMARY_INTERVAL', 5)
        self.rch_metrics = {
            'compressions': 0,
            'total_tokens_saved': 0,
            'last_compression_ratio': 0.0
        }

        # State logging
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.state_file = Path(f"ralph_state_{self.timestamp}.json")

    def start(self):
        print(f"[RALPH] Starting with goal: {self.goal}")

        # Initial system message
        self._add_to_history("system", self._get_system_prompt())
        self._add_to_history("user", f"Goal: {self.goal}")

        while not self.done and self.iteration < self.max_iterations:
            self.iteration += 1
            print(f"\n--- Iteration {self.iteration}/{self.max_iterations} ---")

            # HITL
            if self.hitl_enabled:
                action = self._handle_hitl()
                if action == "stop":
                    break
                elif action == "skip":
                    print("Skipping iteration...")
                    continue
                elif action == "replan":
                    print("Replanning...")
                    self._add_to_history("user", "Please replan your approach.")

            # RLM Logic (Thinking)
            if self.rlm_enabled:
                response = self._run_rlm()
            else:
                response = self._get_completion(self.history)

            if self.debug_mode:
                print(f"[DEBUG] Raw Response:\n{response}")

            # Parse Action
            parsed = parse_json(response)

            if not parsed:
                print("⚠ Failed to parse JSON action")
                self._add_to_history("assistant", response)
                self._add_to_history("system", "Error: Your response was not valid JSON. Please respond with valid JSON only.")
                continue

            # Execute Action
            if isinstance(parsed, list):
                # Handle list of actions? Assuming single action for now or executing all
                results = []
                for action in parsed:
                    res = self._execute_action(action)
                    results.append(res)
                result_str = "\n".join(results)
            else:
                result_str = self._execute_action(parsed)

            # Record Assistant Action and System Result
            self._add_to_history("assistant", json.dumps(parsed))
            self._add_to_history("user", f"Result:\n{result_str}")

            print(f"Result: {result_str[:200]}..." if len(result_str) > 200 else f"Result: {result_str}")

            # RCH (Compression)
            if self.rch_enabled and self.iteration % self.rch_interval == 0:
                self._run_rch()

            # Duplicate detection / Stagnation check
            current_hash = hash(json.dumps(parsed, sort_keys=True))
            if self.last_action_hash == current_hash:
                self.stagnation_count += 1
                if self.stagnation_count > 2:
                    print("⚠ Warning: Detected repetition")
                    self._add_to_history("system", "Warning: You are repeating the same action. Try a different approach.")
            else:
                self.stagnation_count = 0
            self.last_action_hash = current_hash

            self._save_state()

        if self.done:
            print("\n[RALPH] Goal accomplished!")
        elif self.iteration >= self.max_iterations:
            print("\n[RALPH] Max iterations reached.")

    def _get_system_prompt(self):
        return """You are RALPH (Recursive Autonomous Loop with Progressive Hacking), an advanced AI agent.
Your workspace is limited to the 'ralph_workspace' directory.
You can execute commands and manipulate files.

You must respond with a JSON object describing your action.
Available actions:
1. run_cmd: Execute a shell command.
   {"command": "run_cmd", "args": {"cmd": "ls -l"}}
   ALLOWED: ls, cat, grep, find, python3, echo, mkdir, touch
   BLOCKED: sudo, rm -rf /, mv (outside workspace)

2. read_file: Read a file.
   {"command": "read_file", "args": {"path": "filename.txt"}}

3. write_file: Write to a file (overwrites).
   {"command": "write_file", "args": {"path": "filename.txt", "content": "hello world"}}

4. finish: Mark the task as done.
   {"command": "finish", "args": {"reason": "Task completed"}}

Ensure your JSON is valid. Do not include markdown formatting outside the JSON if possible, or wrap it in ```json ... ```.
"""

    def _add_to_history(self, role, content):
        self.history.append({"role": role, "content": content})

    def _get_completion(self, messages):
        # Use proxy to get completion
        try:
            # Prepare messages: Prepend summary if exists
            final_messages = []
            if self.history_summary:
                final_messages.append({"role": "system", "content": f"Previous History Summary:\n{self.history_summary}"})

            final_messages.extend(messages)

            response = self.proxy.chat_completion(
                messages=final_messages,
                model=self.model,
                temperature=0.7
            )

            if 'choices' in response and response['choices']:
                return response['choices'][0]['message']['content']
            elif 'error' in response:
                return f"Error: {response['error']}"
            else:
                return "Error: No response from model"
        except Exception as e:
            return f"Error communicating with LLM: {e}"

    def _run_rlm(self):
        """Recursive Layered Model: Draft -> Critique -> Refine"""
        print("[ralph is thinking deeply (RLM)...]")
        if self.debug_mode:
            print("[RLM] Entering internal dialogue")

        # 1. Draft
        draft_messages = self.history + [{"role": "system", "content": "First, draft a plan or action to achieve the current goal. Think step-by-step."}]
        draft = self._get_completion(draft_messages)
        if self.debug_mode:
            print(f"[RLM] Draft: {draft[:100]}...")

        # 2. Critique
        critique_messages = draft_messages + [
            {"role": "assistant", "content": draft},
            {"role": "user", "content": "Critique this plan. Identify any potential errors, safety issues, or inefficiencies."}
        ]
        if self.debug_mode:
            print("[RLM] Generating internal critique...")
        critique = self._get_completion(critique_messages)

        # 3. Refine
        refine_messages = critique_messages + [
            {"role": "assistant", "content": critique},
            {"role": "user", "content": "Based on the critique, provide the final optimized JSON action."}
        ]
        if self.debug_mode:
            print("[RLM] Refining final action...")
        final_action = self._get_completion(refine_messages)

        return final_action

    def _run_rch(self):
        """Recursive History Compression"""
        print("\n[RCH COMPRESSION METRICS]")

        original_len = sum(len(m['content']) for m in self.history)

        # Compress
        summary_messages = [
            {"role": "system", "content": "Summarize the following conversation history, preserving key facts, actions, and results. Keep it concise."},
            {"role": "user", "content": json.dumps(self.history)}
        ]
        summary = self._get_completion(summary_messages)

        self.history_summary = summary
        # Keep last few messages?
        keep_last = 2
        if len(self.history) > keep_last:
            self.history = self.history[-keep_last:]

        new_len = len(summary) + sum(len(m['content']) for m in self.history)
        saved = original_len - new_len
        ratio = (1 - new_len/original_len) * 100 if original_len > 0 else 0

        self.rch_metrics['compressions'] += 1
        self.rch_metrics['total_tokens_saved'] += saved // 4 # Approx
        self.rch_metrics['last_compression_ratio'] = ratio

        print(f"  Compressed history: {original_len} -> {new_len} chars")
        print(f"  Ratio: {ratio:.1f}%")
        print(f"  Tokens Saved: ~{saved // 4}")

    def _handle_hitl(self):
        """Human-in-the-Loop interaction"""
        print("\n[HITL] Paused for human input.")
        print("Commands: /continue (default), /reset, /skip, /replan, /stop, or enter instructions.")
        try:
            user_input = input("User > ").strip()
        except EOFError:
            return "stop"

        if not user_input or user_input == "/continue":
            return "continue"
        elif user_input == "/stop":
            return "stop"
        elif user_input == "/skip":
            return "skip"
        elif user_input == "/replan":
            return "replan"
        elif user_input == "/reset":
            self.history = []
            self._add_to_history("system", self._get_system_prompt())
            self._add_to_history("user", f"Goal: {self.goal}")
            print("History cleared.")
            return "continue"
        else:
            # Treat as instruction
            self._add_to_history("user", f"Instruction: {user_input}")
            return "continue"

    def _execute_action(self, action_json):
        if not isinstance(action_json, dict):
            return "Error: Action must be a JSON object"

        command = action_json.get("command")
        args = action_json.get("args", {})

        if command == "run_cmd":
            cmd = args.get("cmd")
            if not cmd:
                return "Error: Missing 'cmd' argument"

            # Basic safety check
            if "sudo" in cmd:
                return "Error: Dangerous command blocked (sudo)"
            if "rm " in cmd:
                return "Error: Dangerous command blocked (rm)"
            if "mv " in cmd:
                return "Error: Dangerous command blocked (mv)"

            # Execute in workspace
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=self.workspace,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            except Exception as e:
                return f"Error executing command: {e}"

        elif command == "read_file":
            path = args.get("path")
            if not path:
                return "Error: Missing 'path'"
            try:
                safe_path = get_safe_path(self.workspace, path)
                if not safe_path.exists():
                    return "Error: File not found"
                return safe_path.read_text()
            except Exception as e:
                return f"Error reading file: {e}"

        elif command == "write_file":
            path = args.get("path")
            content = args.get("content")
            if not path or content is None:
                return "Error: Missing path or content"
            try:
                safe_path = get_safe_path(self.workspace, path)
                # Ensure parent exists
                safe_path.parent.mkdir(parents=True, exist_ok=True)
                safe_path.write_text(content)
                return f"Successfully wrote to {path}"
            except Exception as e:
                return f"Error writing file: {e}"

        elif command == "finish":
            self.done = True
            return f"Task completed. Reason: {args.get('reason')}"

        else:
            return f"Unknown command: {command}"

    def _save_state(self):
        state = {
            'timestamp': self.timestamp,
            'goal': self.goal,
            'iteration': self.iteration,
            'done': self.done,
            'history_summary': self.history_summary,
            'rch_metrics': self.rch_metrics,
            'stagnation_count': self.stagnation_count,
            'error': self.error,
            # We don't save full history to keep state file small-ish, or maybe we do?
            'observations': [h['content'] for h in self.history if h['role'] == 'user' and 'Result' in h['content']]
        }
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"Error saving state: {e}")
