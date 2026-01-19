# Configuration and Constants for RALPH

CONFIG = {
    'MEMORY_TRUNCATE_LENGTH': 200,      # Max chars to store from responses
    'RECENT_OBSERVATIONS_COUNT': 3,      # Number of recent observations to show
    'TOP_MEMORY_ENTRIES': 3,             # Top memory entries to inject
    'MAX_MEMORY_INJECT_CHARS': 500,      # Max chars to inject from memory
    'SAVE_FREQUENCY': 10,                # For SQLite, this becomes transaction batch size
    'REQUEST_TIMEOUT': 120,              # HTTP request timeout in seconds
    'STREAMING_TIMEOUT': 300,            # Streaming request timeout
    'PREFETCH_TIMEOUT': 1,               # Prefetch queue timeout
    'MAX_MESSAGE_HISTORY': 25,           # Trigger management every 25 turns (50 messages)
    'WORKSPACE_DIR': './ralph_workspace', # Directory for code execution
    'MAX_CONTEXT_CHARS': 100000,         # Cap at ~25k tokens to leave room for output
    'MAX_OBSERVATIONS_BEFORE_SUMMARY': 10, # Summarize observations after this count
    'MAX_OBSERVATION_CHARS': 1500,       # Max chars for a single observation
    'PLAN_FILE': 'todo.md',              # Markdown plan visibility
    'WHOLE_STATE_FILE': 'whole.task.md', # Full historical record
    'CURRENT_STATE_FILE': 'current.state.md', # Snapshot of now
    'STAGNATION_THRESHOLD': 5,           # Iterations allowed without progress
    'LOOP_DETECTION_WINDOW': 10,         # History window for circular loop detection
    'COMPRESS_ASSISTANT_AFTER': 3,       # Start compressing assistant messages after this many turns back
    'PRESERVE_REASONING_CHARS': 200,     # How much reasoning text to keep in compressed assistant messages
    'PRESERVE_OBSERVATION_CHARS': 300,   # How much observation to keep in compressed assistant messages
    
    # Recursive History Summarization (RCH) Settings
    'RECURSIVE_SUMMARY_INTERVAL': 5,     # Perform recursive summarization every N iterations
    'MAX_SUMMARY_CHARS': 2000,           # Maximum length of the compressed history summary
    'ENABLE_RCH': True,                  # Enable Recursive History Summarization
    'RCH_THRESHOLD_PERCENT': 0.9,       # Trigger RCH when context reaches 90% of MAX_CONTEXT_CHARS
    
    # Recursive Layered Model (RLM) Settings
    'RLM_ENABLED': True,                 # Enable Recursive Layered Model (Thinker/Critic)
    'RLM_RECURSION_DEPTH': 1,            # 0 = direct, 1 = Think/Critique/Act
    'RLM_PRESERVE_INTERNAL_LOGS': False, # If true, internal dialogues are saved to history
    'RLM_ONLY_ON_CONFUSION': False,       # If true, RLM only triggers when Ralph is stagnant or erroring
    'HITL_ENABLED': True,                # Pause for user input every turn
    'DEBUG_MODE': False,                 # If False, hide LLM raw output and system prompts
}

SEPARATOR = "=" * 60

DEFAULT_SYSTEM_PROMPT = """You are a RALPH loop controller, a high-privilege autonomous agent. 

SYSTEM AUTHORITY (CRITICAL):
- You have DIRECT ACCESS to the terminal and filesystem.
- You can and SHOULD use 'read' to view your own source code (in the 'ralph/' directory) if you need to understand your internal logic or configuration.
- You are NOT a restricted text-only AI. Use tools to verify reality instead of guessing.

CRITICAL: You MUST output a JSON state block. If you're running low on space, OUTPUT THE JSON FIRST.

STRATEGIC PLANNING:
- Manage a "plan" object to track progress.
- Decompose the goal into discrete tasks (T1, T2, etc.).
- Update task status to "done" and provide a "result" summary when finished.
- Use "plan_update" in your JSON to modify the plan.

TASK COMPLETION CRITERIA (ANTI-STAGNATION):
- If the user asks a direct question (e.g. "what is 2+2"), answer it using the "chat" action. 
- Avoid "Workflow Hallucination": Do not assume you need to create a `_full_spec.md` unless the task is complex.
- A task is "done" when the required files exist and contain working code, OR when a direct question has been answered.
- If code is written and tested successfully, mark the task "done".

Rules:
0. CRITICAL: If you see a "### USER DIRECTIVE ###" block, you MUST prioritize its instructions above all else.
1. Keep responses concise and focused.
2. If an action fails or returns "Skipped: identical content", DO NOT repeat it.
3. Use "chat" for questions, greetings, or simple logic that doesn't need a script.

STRICT SCHEMA RULES:
1. Write/Edit: {"action": "write", "file": "name.py", "content": "..."}
2. Run command: {"action": "run", "command": "..."}
3. Read file: {"action": "read", "file": "..."}
4. List files: {"action": "ls", "path": "...", "recursive": true}
5. Chat/Answer: {"action": "chat", "message": "Your text answer here"}
6. Web Search: {"action": "search", "query": "Your search query"}
7. Web Read: {"action": "web_read", "url": "https://example.com"}

ARCHITECTURE CONTEXT:
- RLM (Recursive Layered Model): Your internal "Thinker/Critic" loop for deep planning and research validation.
- RHC (Recursive History Compression): Your system for high-density historical summarization to maintain context quality.

IMPORTANT: Simply stating you did it is NOT enough. If code is required, you MUST use "write". If only an answer is required, use "chat". Use "search" to verify current information or find solutions online.
"""
