# LACK Guide: v4.2.2
```
       ·♦---------------------------------------------------------------------------------------♦        
        ♦                                                                                       ♦       
        ♦     ♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦     ♦       
        ♦     ♦♦        ♦♦♦♦♦♦♦♦♦♦        ♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦       ♦        ♦♦♦♦♦         ♦♦     ♦       
        ♦     ♦♦        ♦♦♦♦♦♦♦♦♦          ♦♦♦♦♦♦♦♦♦♦♦♦♦          ♦        ♦♦♦♦         ♦♦♦     ♦       
        ♦     ♦♦        ♦♦♦♦♦♦♦♦♦          ♦♦♦♦♦♦♦♦♦              ♦        ♦♦♦         •♦♦♦     ♦       
        ♦     ♦♦        ♦♦♦♦♦♦♦♦            ♦♦♦♦♦♦♦              ♦♦        ♦♦         ♦♦♦♦♦     ♦       
        ♦     ♦♦        ♦♦♦♦♦♦♦              ♦♦♦♦•          ♦♦♦♦♦♦♦        ♦        ♦♦♦♦♦♦♦     ♦       
        ♦     ♦♦        ♦♦♦♦♦♦                ♦♦♦         ♦♦♦♦♦♦♦♦♦                ♦♦♦♦♦♦♦♦     ♦       
        ♦     ♦♦        ♦♦♦♦♦·                 ♦         ♦♦♦♦♦♦♦♦♦♦               ♦♦♦♦♦♦♦♦♦     ♦       
        ♦     ♦♦        ♦♦♦♦♦        ♦♦        ♦         ♦♦♦♦♦♦♦♦♦♦              ♦♦♦♦♦♦♦♦♦♦     ♦       
        ♦     ♦♦        ♦♦♦♦        ♦♦♦♦                 ♦♦♦♦♦♦♦♦♦♦               ♦♦♦♦♦♦♦♦♦     ♦       
        ♦     ♦♦        ♦♦♦                              ♦♦♦♦♦♦♦♦♦♦                ♦♦♦♦♦♦♦♦     ♦      
        ♦     ♦♦        ♦♦                                ♦♦♦♦♦♦♦♦♦                 ♦♦♦♦♦♦♦     ♦      
        ♦     ♦♦        ♦♦                                 ♦♦♦♦♦♦♦♦                  ♦♦♦♦♦♦     ♦
        ♦     ♦♦        ♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦                       ♦        ♦♦♦        ♦♦♦♦♦     ♦       
        ♦     ♦♦                       ♦♦♦♦♦                      ♦        ♦♦♦♦        ♦♦♦♦     ♦       
        ♦     ♦♦                      ♦♦♦♦♦♦         ♦♦           ♦        ♦♦♦♦♦        ♦♦♦     ♦       
        ♦     ♦♦                     ♦♦♦♦♦♦♦♦         ♦♦♦♦♦       ♦        ♦♦♦♦♦♦        ♦♦     ♦      
        ♦     ♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦     ♦      
        ♦                                                                                       ♦       
       ·♦---------------------------------------------------------------------------------------♦
```

---

## 1. **New in v4.2.2:**

| Feature | Description |
|---------|-------------|
| **Musing** | Low‑commitment token sampling: agents generate multiple candidate responses, score them, and synthesise the best. |
| **Triangulation** | Cross‑constraint mapping from multiple perspectives (technical, UX, security, etc.) – reconciles into a balanced answer. |
| **/bash Command** | Run shell commands directly in `#general` – executed by the Moderator. |
| **CI/CD Pipeline** | Full pipeline: lint → LLM eval → peer review → moderator approval → auto‑fix → commit. |
| **Reconciliation Loop** | Controlled iterative refinement using J‑space, convergence thresholds, and optional HITL pauses. |
| **J‑Space** | Silent reasoning layers projected from embeddings (e.g., `math`, `planning`, `safety`). Inspect with `/jspace`. |
| **DecentMem** | Enhanced memory: E‑pool (successful trajectories) and X‑pool (exploratory candidates) with exploitation/exploration weighting. |
| **Search Providers** | Configurable: DuckDuckGo, SerpAPI, Firecrawl. |
| **New Commands** | `/bash`, `/reconcile`, `/approve`, `/jspace`, `/jspace_agent`, `/toggle_public_memory`, `/public_memory`, `/memory`, `/eval`, `/skill`, `/cicd`. |

---

## 2. Abstract / Planning Mode (Tool & Action Mode)

**Activation:** `/abstract` or `/plan "goal"` in any channel.  
**What happens:**  
Agents output **JSON actions** inside ````json` blocks. Supported actions:

- `{"type":"message","payload":{"content":"..."}}` – send a message.
- `{"type":"research","payload":{"query":"..."}}` – start research in #siphon.
- `{"type":"code","payload":{"description":"..."}}` – generate code.
- `{"type":"delegate","payload":{"targetId":"agent_id","task":"..."}}` – ask another agent.
- **`{"type":"tool_calls","tool_calls":[{"name":"read_file","arguments":{"path":"..."}}]}`** – use file tools.
- **`{"type":"stack","payload":{"subcmd":"build","repoName":"..."}}`** – use STACK commands.

**File tools available:**  
`read_file`, `write_file`, `execute_command` (sandboxed in `workspace/` – but `execute_command` is restricted to the Moderator).

**Musing & Triangulation** are automatically enabled in planning mode, ensuring agents explore multiple angles before acting.

**Use case:** Building multi‑step workflows, reading/writing files, and orchestrating agents.

---

## 3. Research Mode (Siphon)

**Activation:** `/research <topic>` in any channel.  
**What happens:**  
- The Siphon engine runs: generates sub‑questions, scrapes search results (DuckDuckGo, SerpAPI, or Firecrawl), extracts facts via Ollama.  
- Results appear in `#siphon`.  
- You can pull a summary with `/pull <session_id>`.

**Search Providers** (configurable in `lack.config.json`):
- `duckduckgo` (default, no API key)
- `serpapi` (requires `serpapiKey`)
- `firecrawl` (requires `firecrawlApiKey`)

**Use case:** Gathering factual data before coding or planning.

---

## 4. Ralph Evolutionary Loop

**Activation:** `/ralph "your goal"` (channel or DM).  
**What happens:**  
Agents take turns evolving a project spec (title, goals, next steps, memory).  
- Each generation: evaluate → evolve → compare similarity.  
- Stops when similarity ≥ 95% or after 30 generations.  
- Messages are posted in the channel, and the spec is saved to **lineage** (JSONL files in `lineage/`).

**Enhanced with Musing & Triangulation:** Ralph now generates multiple candidate evolutions, scores them, and picks the best – leading to faster convergence and higher quality specs.

**New commands:**  
- `/convergence` – shows how similar the current spec is to the previous one.  
- `/stop` – stops any active loop.

---

## 5. Reconciliation Loop

**Activation:** `/reconcile "your goal"` (channel or DM).  
**What happens:**  
A more controlled refinement process than Ralph:

- Each iteration uses **J‑space** to guide changes.
- Generates a diff, evaluates the new spec, and checks convergence.
- Stops when similarity ≥ `convergenceThreshold` and eval score ≥ `minEvalScore`.
- Stagnation detection triggers forced mutations.
- Optional **HITL pause** (`hitlPause: true` in config) – use `/approve <loopId>` to continue.

**Parameters** (in `lack.config.json` under `reconciliation`):
- `maxIterations` (default 20)
- `convergenceThreshold` (default 0.95)
- `minEvalScore` (default 80)
- `requireTestPass` (default true)
- `hitlPause` (default false)

**Use case:** When you want to supervise the refinement process or need guaranteed quality thresholds.

---

## 6. STACK – Semantic Template System

STACK lets you **inject full directory templates** based on a natural language intent. It uses embeddings (`nomic-embed-text`) to find the best match.

**Commands (can be used by any agent or human):**

| Command | Description |
|---------|-------------|
| `/stack build <repoName>` | Create a new empty git repo in `lack_repos/`. |
| `/stack add <description>` | Find the best matching template and copy its files into the active repo. |
| `/stack import <file.json>` | Import a JSON blueprint (see format below) and reindex templates. |
| `/stack set <repoName>` | Set the active STACK repo for the current channel. |

**Template format for import:**  
```json
{
  "templates": {
    "flask_api": {
      "files": {
        "app.py": "from flask import Flask...",
        "requirements.txt": "flask\n"
      }
    }
  }
}
```

Place folders manually in `lack_repos/templates/` – STACK automatically scans and reindexes every 10 seconds.

---

## 7. CI/CD Pipeline (Automatic Code Moderation)

Whenever any agent (or human) posts a **code block** (triple backticks), the **Moderator agent** runs a full CI/CD pipeline:

1. **Linting** – Python, JavaScript, HTML, JSON, etc.
2. **LLM Evaluation** – Code is reviewed for correctness, efficiency, security.
3. **Peer Review** – Another agent (non‑moderator) scores the code (if `requirePeerReview: true`).
4. **Moderator Approval** – The Moderator decides to approve or reject.
5. **Auto‑fix** – If failed and `autoFix: true`, the agent is asked to correct the code (retries up to `maxRetries`).
6. **Commit** – Final version is committed to the thread repository (even if it fails, with clear messages).
7. **Feedback** – Detailed results are posted in the chat.

**Configuration** (in `lack.config.json` under `cicd`):
- `maxRetries` (default 3)
- `reviewerModel` (default `qwen2.5:0.5b`)
- `moderatorModel` (default `qwen2.5:0.5b`)
- `requirePeerReview` (default true)
- `autoFix` (default true)

**Human commands to interact with the moderation system:**

| Command | Effect |
|---------|--------|
| `/repo [threadId]` | Show the repository path and list of files for that thread (defaults to current channel/thread). |
| `/lint <filename>` | Manually lint a file inside the current thread’s repo. |
| `/moderate on` / `off` | Enable/disable automatic code moderation (default = on). |
| `/eval` | Run an LLM evaluation on the last code block. |
| `/cicd` | Run the full CI/CD pipeline on the last code block. |
| `/test_dm <agentName>` | Create a test DM, send a thread root + reply to verify threading and moderation in DMs. |

---

## 8. J‑Space

J‑space is a **silent reasoning layer** derived from embeddings. Text is projected onto concept vectors (e.g., `math`, `planning`, `safety`, `creativity`, `causal`) and provides internal guidance to agents without cluttering the conversation.

**Commands:**

| Command | Description |
|---------|-------------|
| `/jspace <text>` | Display J‑space concepts for a given text. |
| `/jspace_agent <agentId>` | Show recent J‑space history for an agent. |

**Configuration** (in `lack.config.json`):
- `jspaceEnabled` (default true)
- `jspaceLayer` (default `layer_12`)
- `jspaceConceptCount` (default 5)

**J‑space data** is stored in `jspace/qwen2.5_0.5b_jspace.json` – you can replace it with real Neuronpedia directions for best results.

---

## 9. DecentMem (Memory System)

Each agent maintains sophisticated memory:

- **E‑pool** – Successful trajectories (score ≥ 60/100) – used for exploitation.
- **X‑pool** – Exploratory candidates (novel ideas) – used for exploration.
- **Weights** – Exploitation/exploration balance updated dynamically via judge scoring.
- **Stats** – Average score, total judgements, last update.

**Features:**
- Retrieval based on cosine similarity or TF‑IDF fallback.
- Automatic pruning and deduplication.
- **Public Memory** – Global best‑practice sharing across agents (optional).

**Commands:**

| Command | Description |
|---------|-------------|
| `/memory <agentId>` | Show agent’s memory pools (E‑pool, X‑pool, weights). |
| `/public_memory` | Show aggregated public memory summary (global best practices). |
| `/toggle_public_memory` | Enable/disable public memory sharing. |

---

## 10. Channel‑Specific Personalities

| Channel | Temperature | Behaviour |
|---------|-------------|-----------|
| `#code` | 0.3 | Strict code output only. NO explanations, NO chat. |
| `#siphon` | 0.2 | Factual, concise, research‑focused. Uses Triangulation. |
| `#general` | 0.7 | Neutral conversation. Uses Musing. |

---

## 11. Direct Messages (DMs) – Enhanced

- Start a DM with `/dm <agentName>` or double‑click an agent in the sidebar.
- All modes work in DMs: normal chat, planning, Ralph loops, Reconciliation, and **code moderation** (thread repos are created per DM).
- **New command:** `/test_dm <agentName>` – creates a DM and sends a threaded test message to verify everything works.

---

## 12. Agent Internal Status (UI)

| Status | Meaning |
|--------|---------|
| 🟢 `online` | Idle, ready. |
| 🟡 `thinking` | Generating a response (Ollama call in progress). |
| 🟠 `queued` | Waiting in the per‑agent rate‑limit queue. |
| (no dot) | Agent removed. |

The **Graph modal** (`/graph` button) shows real‑time CPU, memory, TPS, and J‑space coherence metrics for all agents.

---

## 13. Utility Commands (v4.2.2)

| Command | Description |
|---------|-------------|
| `/bash <command>` | Run a shell command in `#general` (executed by Moderator). |
| `/tools` | List available file tools (read_file, write_file, execute_command). |
| `/errorlog` | Show last 50 errors from the Node.js server (stored in `logs/error.log`). |
| `/graph` | Open the agent resource monitor. |
| `/convergence` | Show similarity percentage between current and previous Ralph spec. |
| `/stop` | Stop any active loop (research, abstract, Ralph, Reconciliation) in the current store. |
| `/jspace <text>` | Display J‑space concepts for a given text. |
| `/jspace_agent <agentId>` | Show recent J‑space history for an agent. |
| `/memory <agentId>` | Show agent’s memory pools (E‑pool, X‑pool, weights). |
| `/public_memory` | Show aggregated public memory summary (global best practices). |
| `/toggle_public_memory` | Enable/disable public memory sharing. |
| `/eval` | Run an LLM evaluation on the last code block. |
| `/skill <code or file>` | Run the reverse‑skill router on code or a file. |
| `/cicd` | Run the full CI/CD pipeline on the last code block. |
| `/reconcile <goal>` | Start the reconciliation control loop (iterative refinement with J‑space). |
| `/approve <loopId>` | Approve a paused reconciliation iteration (HITL). |

---

## Troubleshooting & Tips

- **Ollama must be running** and have models: `qwen2.5:0.5b` (or any) and `nomic-embed-text` for STACK and J‑space.
- If agents output raw JSON without code blocks, the system automatically **repairs** it (adds missing quotes, braces) and forces a code block if it looks like code.
- The **Moderator** agent is embed‑only – it never chats; it only posts moderation feedback and runs CI/CD.
- All code repositories are stored in `thread_repos/` and can be browsed manually.
- Lineage files (project state, Ralph state, Reconciliation state) are in `lineage/` – they auto‑prune after 7 days.
- **Musing** and **Triangulation** can be disabled in `lack.config.json` if you prefer faster, less thorough responses.
- **J‑space** requires embeddings – if `nomic-embed-text` is not available, J‑space will be disabled (fallback to TF‑IDF).
- **Public memory** is disabled by default – enable with `/toggle_public_memory` or via config.
- **Search providers** – if SerpAPI or Firecrawl fail, the system automatically falls back to DuckDuckGo.



## 20 Robust Feature-Test Prompts

Designed to stress-test specific LACK capabilities:
- Musing (low-commitment sampling + candidate scoring + synthesis)
- Triangulation (multi-perspective + reconciliation)
- CI/CD pipeline + Moderator review + auto-fix
- Reconciliation loop + convergence / stagnation handling
- J-space (silent concept projection)
- DecentMem (e-pool / x-pool, judgeAndReweight, proactive X generation)
- STACK (template matching + git commits)
- Graph / metrics / loop_health
- Tool restrictions (only Moderator can execute_command)
- Channel personality rules (#code, #siphon, #general)
- Ralph evolution + force mutation
- Reflection format ("things worth a closer look")

Copy-paste the commands into the matching channel.

------------------------------------------------
1. /abstract – Musing + reflection pressure
------------------------------------------------
/abstract Design a minimal, production-ready Python multi-agent orchestration skeleton optimized for small Ollama models (0.5B–3B). Requirements: src/ package layout (agents, tools, core, memory, utils), single entrypoint, typed config, defensive error handling, structured logging, zero external heavy deps beyond requests/sqlite. Force the use of musing (generate 3 candidate architectures, score them, synthesize the best). End with the required reflection format and 3 concrete next investigation candidates. Write every file with tools, lint, and commit iteratively.

------------------------------------------------
2. /abstract – Code channel purity + Moderator CI/CD
------------------------------------------------
/abstract (in #code) Produce a complete, self-contained FastAPI + SQLite microservice for a personal knowledge base with semantic search stubs. Output ONLY clean code blocks. No explanations. Include Dockerfile, requirements.txt, and a basic test suite. Trigger full Moderator CI/CD (lint, peer review, auto-fix loop, git commit to thread repo).

------------------------------------------------
3. /plan – Project planning + DecentMem reuse
------------------------------------------------
/plan Build a private personal finance tracker (income, expenses, budgets, monthly PDF reports, CSV import). Break into 4 sprints. Explicitly retrieve and reuse any high-scoring trajectories from agent private memory (e-pool) that relate to SQLite schemas or report generation. After planning, start a short Ralph loop to refine the schema.

------------------------------------------------
4. /ralph – Full evolution + force mutation test
------------------------------------------------
/ralph Evolve a minimal Python roguelike engine (entity-component system, procedural map, save/load, terminal renderer). Goal: converge to a clean, documented, runnable demo. Force stagnation detection and mutation if similarity stays high for 3 generations. Track loop_health and J-space coherence.

------------------------------------------------
5. /abstract – Triangulation under conflicting constraints
------------------------------------------------
/abstract Design a rate-limited, cached weather microservice (API gateway pattern). Use triangulation across 3 perspectives: technical feasibility, cost/performance, and security. Reconcile the views into one coherent architecture + ASCII diagram + skeleton code. Explicitly surface any trade-offs that remain unresolved.

------------------------------------------------
6. /plan + /reconcile – Reconciliation loop stress
------------------------------------------------
/plan Create a roadmap for migrating a small monolith to microservices on Kubernetes with chaos-engineering practices. Then immediately run /reconcile with the goal "production-ready migration plan with measurable success criteria". Require eval score ≥ 85 and test-pass before declaring convergence. Enable HITL pause if configured.

------------------------------------------------
7. /siphon – Research → STACK → code
------------------------------------------------
/siphon Research the architecture and key design patterns of the FastAPI framework (https://github.com/tiangolo/fastapi). Extract reusable templates. Then use /stack add "minimal FastAPI service with dependency injection and async endpoints" and apply the best match. Finally generate a complete working service from the applied template.

------------------------------------------------
8. /abstract – J-space guided design
------------------------------------------------
/abstract Using current J-space signals (especially any strong "planning", "safety", or "causal" concepts), design a lightweight local RAG pipeline that stays under 512-token context windows for 0.5B models. Prefer pure Python + nomic embeddings + SQLite. Document how J-space influenced the design choices.

------------------------------------------------
9. /plan – DecentMem X-pool exploration
------------------------------------------------
/plan Design a CLI habit + task tracker with streaks, rich formatting, and daily digests. Force generation of 3 novel X-pool candidates (exploration strategies) before settling on the final architecture. Score each candidate and keep the highest-scoring one in e-pool.

------------------------------------------------
10. /abstract – Tool restriction enforcement
------------------------------------------------
/abstract Build a safe file-organizer utility. When any agent needs to run shell commands (mkdir, mv, etc.), it must request the Moderator instead of calling execute_command directly. Demonstrate the restriction path and the Moderator’s response. Include dry-run and undo features.

------------------------------------------------
11. /ralph – Multi-agent hand-off + metrics
------------------------------------------------
/ralph Build a lightweight multi-agent orchestration framework (researcher, coder, critic) with shared memory and task delegation. Rotate agents every generation. Continuously publish CPU / TPS / J-space coherence to the graph. Stop only when recurrence conditions (sim ≥ 0.95, eval ≥ 80, test pass) are met.

------------------------------------------------
12. /abstract – Channel personality isolation
------------------------------------------------
/abstract (switch to #siphon first) Research current best practices for local RAG systems in 2026, then move to #code and emit only the resulting Python implementation. Verify that #siphon stays factual/research-focused and #code stays pure code with no chat.

------------------------------------------------
13. /plan – STACK template creation + reuse
------------------------------------------------
/plan Create a reusable STACK template for "minimal Ollama-powered CLI agent with tool calling and memory". Save it under lack_repos/templates/. Then start a new project that uses /stack add "ollama CLI agent" and verify the files land correctly with a git commit.

------------------------------------------------
14. /abstract – Full CI/CD + reverse-skill path
------------------------------------------------
/abstract Write a non-trivial Python module that needs reverse-engineering insight (e.g., a small bytecode or obfuscated helper). Trigger Moderator review, lint, peer review, auto-fix, and (if reverse-skill is present) the reverse-skill analysis. Commit the final cleaned version to the thread repo.

------------------------------------------------
15. /reconcile – Long-running convergence test
------------------------------------------------
/reconcile Goal: "Complete, documented, production-ready local knowledge-base service with semantic search, tagging, and daily digest". Allow up to 20 iterations. Require minEvalScore 85, convergenceThreshold 0.95, and explicit test-pass. Log every iteration to loop_health.

------------------------------------------------
16. /abstract – Musing diversity + synthesis quality
------------------------------------------------
/abstract Generate a 3D endless-runner concept in Three.js (procedural track, jump/slide, score, restart). Force museCount=4 with deliberately varied temperature and suffix prompts. Score the four candidates, synthesize the strongest elements, then emit the final complete HTML/CSS/JS file. Reflection must list which candidate contributed which idea.

------------------------------------------------
17. /plan – Graph & spike awareness
------------------------------------------------
/plan Design a real-time agent metrics dashboard (CPU, memory, TPS, J-space coherence, e/x-pool sizes). Include spike detection thresholds and a simple alerting rule. After planning, run a short Ralph loop while watching the graph for any CPU or TPS spikes caused by the planning itself.

------------------------------------------------
18. /siphon + /abstract – Research-to-code pipeline
------------------------------------------------
/siphon Analyze the plugin / event-bus architecture of Home Assistant (https://github.com/home-assistant/core). Summarize the key patterns. Then /abstract Use the research to implement a minimal pure-Python event bus + plugin loader that small Ollama agents can extend. Keep it under 300 LOC and fully typed.

------------------------------------------------
19. /ralph – Stagnation → forced mutation → recovery
------------------------------------------------
/ralph Evolve a static-site + blog generator (Markdown, templates, RSS, SEO). Intentionally keep early generations very similar to trigger the 3-round stagnation detector. Confirm that force mutation fires, X-pool candidates are generated, and the loop recovers with a meaningfully different design.

------------------------------------------------
20. /abstract – End-to-end feature cocktail
------------------------------------------------
/abstract Build a clean, minimal, git-ready Python repository for a modular multi-agent system that uses: DecentMem (private e/x pools), J-space hints, optional musing on hard decisions, tool calling (with Moderator restriction), and a simple reconciliation loop for project state. Create the full directory tree, write every file, lint, commit, and finish with the standard reflection + "things worth a closer look" section. This is the integration test for the entire LACK feature set.

### Notes

- Prefer #general for /plan, /ralph, /reconcile, /abstract that need chat + reflection.
- Use #code when you want pure code blocks and full Moderator CI/CD.
- Use #siphon for research-heavy prompts; follow with /pull <session-id>.
- After any Ralph or Reconciliation run, check /convergence and the GRAPH button.
- Toggle Moderator with the UI button or /moderate on|off.
- Watch agent_memories/ and loop_health table for DecentMem and reconciliation telemetry.

