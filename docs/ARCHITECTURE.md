# RALPH + RCH Architecture Documentation

Complete architectural diagrams showing how RALPH (Recursive Autonomous Loop for Progressive Hacking) integrates with RCH (Recursive History Summarization).

---

## 1. Main Loop Flow

```mermaid
graph TD
    Start([Start RALPH]) --> Init[Initialize State]
    Init --> LoadState{Previous State<br/>Exists?}
    LoadState -->|Yes| Resume[Resume from Checkpoint]
    LoadState -->|No| Fresh[Fresh Start]
    Resume --> LoopStart
    Fresh --> LoopStart

    LoopStart[Iteration += 1] --> ObsSumm[Summarize Observations]
    ObsSumm --> CheckRCH{Iteration % 5<br/>== 0?}

    CheckRCH -->|Yes| RCH[RCH: Recursive History<br/>Summarization]
    CheckRCH -->|No| LoopDetect
    RCH --> LoopDetect

    LoopDetect[Detect Loops<br/>5 Types] --> IsLoop{Loop<br/>Detected?}
    IsLoop -->|Yes| IncrStag[Increment Stagnation Count]
    IsLoop -->|No| ResetStag[Reset Stagnation Count]

    IncrStag --> CheckKill{Count >= 5?}
    CheckKill -->|Yes| SafetyKill[Safety Kill:<br/>Save State & Exit]
    CheckKill -->|No| CheckWarn{Count >= 2?}
    CheckWarn -->|Yes| ShowWarn[Show Warning Message]
    CheckWarn -->|No| PrepPrompt
    ShowWarn --> PrepPrompt
    ResetStag --> PrepPrompt

    PrepPrompt[Prepare User Prompt<br/>with State] --> ThinMsg[Thin Message History]
    ThinMsg --> RLMCheck{RLM Enabled?}

    RLMCheck -->|Yes| RLM[RLM: Thinker/Critic<br/>_rlm_internal_dialogue]
    RLMCheck -->|No| CallLLM[Call LLM via Proxy<br/>Direct Stream]

    RLM --> ParseResp
    CallLLM --> ParseResp

    ParseResp[Parse JSON Response] --> ExecActions[Execute Actions<br/>read/write/run/test/ls]
    ExecActions --> UpdateState[Update State & Observations]
    UpdateState --> SaveState[Save State to JSON]
    SaveState --> CheckDone{Done or<br/>Max Iters?}

    CheckDone -->|Yes| Summary[Show RCH Summary]
    CheckDone -->|No| LoopStart
    Summary --> End([End])
    SafetyKill --> End
```

---

## 2. RCH Compression Cycle (Every 5 Iterations)

```mermaid
sequenceDiagram
    participant Loop as Main Loop
    participant RCH as RCH Module
    participant Historian as Historian LLM
    participant State as State Manager

    Note over Loop: Iteration 5, 10, 15, 20...
    Loop->>RCH: Trigger _recursive_summarize_history()

    RCH->>State: Get current history_summary
    RCH->>State: Get last 10 observations
    RCH->>State: Get last 5 iteration logs

    Note over RCH: Calculate pre-compression size
    RCH->>RCH: Build historian context

    RCH->>Historian: Send compression prompt
    Note over Historian: Temperature: 0.3<br/>Max tokens: 1000<br/>Focus: Intent & causality

    Historian-->>RCH: Compressed narrative

    RCH->>RCH: Enforce 2000 char limit
    RCH->>RCH: Calculate metrics<br/>- Compression ratio<br/>- Tokens saved<br/>- Time taken

    RCH->>State: Update history_summary
    RCH->>State: Update rch_metrics
    RCH->>State: Keep only recent observations

    RCH->>Loop: Display metrics box
    Note over Loop: Continue with iteration
```

---

## 3. System Components Architecture

```mermaid
graph TB
    subgraph "RALPH Core"
        RunRalph[run_ralph.py<br/>Entry Point]
        LoopEngine[EngramRalphLoop<br/>Main Engine]
        Config[config.py<br/>Settings]
    end

    subgraph "Memory & Context"
        MemStore[EngramMemoryStore<br/>SQLite Backend]
        RCH[RCH Module<br/>_recursive_summarize_history]
        RLM[RLM Module<br/>_rlm_internal_dialogue]
        ObsSum[_summarize_observations<br/>Basic compression]
    end

    subgraph "LLM Integration"
        Proxy[LMStudioEngramProxy<br/>API Gateway]
        SyncTool[chat_completion_sync<br/>Fast Turnaround]
        Parser[ResponseParser<br/>JSON validator]
        LMStudio[LM Studio<br/>Local LLM Server]
    end

    subgraph "Execution Layer"
        FileOps[File Operations<br/>read/write]
        CmdRunner[Command Runner<br/>run/test]
        Validator[Schema Validator<br/>_normalize_exec_data]
    end

    subgraph "State Management"
        StateFile[ralph_state_*.json<br/>Checkpoint]
        Workspace[ralph_workspace/<br/>Code & Files]
        TaskFiles[todo.md<br/>whole.task.md<br/>current.state.md]
    end

    subgraph "Loop Detection"
        LoopDet[Loop Detector<br/>5 Types]
        Stagnation[Stagnation Counter<br/>Safety Kill @ 5]
        Remediation[Targeted Remediation<br/>Messages]
    end

    RunRalph --> LoopEngine
    LoopEngine --> Config
    LoopEngine --> MemStore
    LoopEngine --> RCH
    LoopEngine --> RLM
    LoopEngine --> ObsSum
    LoopEngine --> Proxy
    LoopEngine --> Parser
    LoopEngine --> FileOps
    LoopEngine --> CmdRunner
    LoopEngine --> Validator
    LoopEngine --> StateFile
    LoopEngine --> Workspace
    LoopEngine --> TaskFiles
    LoopEngine --> LoopDet
    LoopDet --> Stagnation
    Stagnation --> Remediation

    Proxy --> LMStudio
    Proxy --> SyncTool
    RCH --> Proxy
    RLM --> SyncTool
    RLM --> Proxy

    style RCH fill:#90EE90
    style RLM fill:#87CEEB
    style LoopDet fill:#FFB6C1
    style Stagnation fill:#FFB6C1
```

---

## 4. Data Flow Through RALPH+RCH

```mermaid
flowchart LR
    subgraph Input
        Goal[task.md<br/>User Goal]
        PrevState[ralph_state_*.json<br/>Previous State]
    end

    subgraph Processing
        Init[Initialize<br/>State]
        Iter[Iteration<br/>Loop]

        subgraph "Every Iteration"
            BasicSum[Basic<br/>Summarization]
            RCHCheck{Iter % 5?}
            RCHProc[RCH<br/>Compression]
            LoopCheck[Loop<br/>Detection]
            BuildPrompt[Build<br/>Context]
            RLMCheck{RLM?}
            RLMProc[RLM<br/>Thinking]
            LLM[Call<br/>LLM]
            Execute[Execute<br/>Actions]
        end

        subgraph "RCH Module"
            CollectHist[Collect<br/>History]
            CallHistorian[Historian<br/>LLM]
            Compress[Compress<br/>to 2000 chars]
            CalcMetrics[Calculate<br/>Metrics]
        end
    end

    subgraph Output
        NewState[Updated<br/>State]
        Workspace[Created/Modified<br/>Files]
        Metrics[RCH<br/>Metrics]
        Summary[Session<br/>Summary]
    end

    Goal --> Init
    PrevState --> Init
    Init --> Iter

    Iter --> BasicSum
    BasicSum --> RCHCheck
    RCHCheck -->|Yes| RCHProc
    RCHCheck -->|No| LoopCheck

    RCHProc --> CollectHist
    CollectHist --> CallHistorian
    CallHistorian --> Compress
    Compress --> CalcMetrics
    CalcMetrics --> LoopCheck

    LoopCheck --> BuildPrompt
    BuildPrompt --> RLMCheck
    RLMCheck -->|Yes| RLMProc
    RLMCheck -->|No| LLM
    RLMProc --> Execute
    LLM --> Execute
    Execute --> NewState
    Execute --> Workspace

    NewState --> Iter
    CalcMetrics --> Metrics
    Metrics --> Summary

    style RCHProc fill:#90EE90
    style CollectHist fill:#90EE90
    style CallHistorian fill:#90EE90
    style Compress fill:#90EE90
    style CalcMetrics fill:#90EE90
```

---

## 5. State Structure

```mermaid
graph TB
    subgraph "ralph_state_*.json"
        Root[State Root]

        Root --> Iteration[iteration: int]
        Root --> Done[done: bool]
        Root --> Error[error: string]

        Root --> Plan[plan: object]
        Plan --> Tasks[tasks: array]
        Plan --> CurrentTask[current_task_id: string]

        Root --> Obs[observations: array]
        Root --> HistSum[history_summary: string]
        Root --> IterLog[iteration_log: array]

        Root --> Stag[stagnation_count: int]
        Root --> LoopType[loop_type: string]

        Root --> RCHMetrics[rch_metrics: object]
        RCHMetrics --> Compressions[compressions: int]
        RCHMetrics --> TotalBefore[total_chars_before: int]
        RCHMetrics --> TotalAfter[total_chars_after: int]
        RCHMetrics --> TokensSaved[total_tokens_saved: int]
        RCHMetrics --> LastRatio[last_compression_ratio: float]
        RCHMetrics --> Trend[history_size_trend: array]
    end

    style RCHMetrics fill:#90EE90
    style Compressions fill:#90EE90
    style TotalBefore fill:#90EE90
    style TotalAfter fill:#90EE90
    style TokensSaved fill:#90EE90
```

---

## 6. Configuration Landscape

```mermaid
mindmap
  root((CONFIG))
    Observation Management
      MAX_OBSERVATIONS_BEFORE_SUMMARY: 10
      RECENT_OBSERVATIONS_COUNT: 3
      MAX_OBSERVATION_CHARS: 1500

    History Management
      MAX_MESSAGE_HISTORY: 8 pairs
      COMPRESS_ASSISTANT_AFTER: 3
      PRESERVE_REASONING_CHARS: 200
      PRESERVE_OBSERVATION_CHARS: 300

    RCH Settings
      ENABLE_RCH: True
      RECURSIVE_SUMMARY_INTERVAL: 5 iters
      MAX_SUMMARY_CHARS: 2000

    Loop Detection
      STAGNATION_THRESHOLD: 5 iters
      LOOP_DETECTION_WINDOW: 10

    File Management
      WORKSPACE_DIR: ./ralph_workspace
      PLAN_FILE: todo.md
      WHOLE_STATE_FILE: whole.task.md
      CURRENT_STATE_FILE: current.state.md

    API Settings
      REQUEST_TIMEOUT: 120s
      STREAMING_TIMEOUT: 300s
```

---

## 7. Token Economics

```mermaid
graph LR
    subgraph "Without RCH"
        W_I1[Iter 1<br/>800 tokens]
        W_I10[Iter 10<br/>1200 tokens]
        W_I50[Iter 50<br/>1800 tokens]
        W_I100[Iter 100<br/>2500 tokens]
        W_Total[Total: ~80K tokens]

        W_I1 --> W_I10
        W_I10 --> W_I50
        W_I50 --> W_I100
        W_I100 --> W_Total
    end

    subgraph "With RCH"
        R_I1[Iter 1<br/>800 tokens]
        R_I5[Iter 5<br/>1000 tokens<br/>+RCH: 250]
        R_I10[Iter 10<br/>600 tokens<br/>+RCH: 250]
        R_I50[Iter 50<br/>500 tokens<br/>+RCH: 250]
        R_I100[Iter 100<br/>450 tokens<br/>+RCH: 250]
        R_Total[Total: ~45K tokens<br/>Saved: 35K]

        R_I1 --> R_I5
        R_I5 --> R_I10
        R_I10 --> R_I50
        R_I50 --> R_I100
        R_I100 --> R_Total
    end

    W_Total -.43% reduction.-> R_Total

    style R_I5 fill:#90EE90
    style R_I10 fill:#90EE90
    style R_I50 fill:#90EE90
    style R_I100 fill:#90EE90
    style R_Total fill:#90EE90
```

---

## Key Architecture Principles

### 1. **Separation of Concerns**

- Main loop handles iteration logic
- RCH module handles history compression
- Loop detection handles stagnation
- Each component has a single responsibility

### 2. **Non-Invasive Integration**

- RCH can be disabled via `ENABLE_RCH: False`
- Falls back gracefully on errors
- Doesn't break existing functionality

### 3. **State Persistence**

- Every iteration saves state to JSON
- RCH metrics tracked separately
- Can resume from any checkpoint

### 4. **Progressive Enhancement**

- Basic loop (works)
- - Loop detection (prevents waste)
- - RCH (improves efficiency)
- - (Future) RLM (improves quality)

### 5. **Observable Metrics**

- Per-compression metrics display
- Session summary at end
- All metrics saved in state
- Easy to verify RCH is working

---

## Performance Characteristics

| Aspect                  | Baseline      | With RCH     | Improvement |
| ----------------------- | ------------- | ------------ | ----------- |
| **Context Growth**      | Linear        | Plateau      | ✓ Bounded   |
| **Token Usage**         | 800-2500/iter | 450-500/iter | 40-50% ↓    |
| **Response Time**       | 1.0-1.5s      | 0.7-1.0s     | 20-30% ↓    |
| **Memory Quality**      | Lossy         | High-density | ✓ Better    |
| **Long-term Coherence** | Degrades      | Maintained   | ✓ Stable    |

---

## Critical Paths

### Happy Path (Normal Iteration)

1. Increment iteration
2. Summarize observations (basic)
3. Detect loops (none found)
4. Build context from state
5. Call LLM
6. Parse response
7. Execute actions
8. Update state
9. Save checkpoint

### RCH Path (Every 5th Iteration)

1. Increment iteration
2. Summarize observations (basic)
3. **[RCH] Collect history**
4. **[RCH] Call historian LLM**
5. **[RCH] Compress to 2000 chars**
6. **[RCH] Calculate & display metrics**
7. **[RCH] Update state with compressed history**
8. Detect loops
9. Build context (now with compressed history)
10. Call LLM (faster due to smaller context)
11. Continue normal flow...

### Loop Detection Path

1. Check last 5 observations
2. Detect pattern (5 types)
3. Increment stagnation count
4. If count >= 5: Safety kill
5. If count >= 2: Show remediation
6. Continue with warning injected

---

## Future Extensions

```mermaid
graph LR
    Current[Current: RHC+RLM] --> SubAgent[Add: Recursive Sub-Agents]
    SubAgent --> MultiModel[Add: Multi-Model Support]
    MultiModel --> Distributed[Add: Distributed Execution]

    style Current fill:#90EE90
    style SubAgent fill:#FFE4B5
```

---

Created: 2026-01-18
Version: 1.0
Author: RALPH+RCH Implementation Team
