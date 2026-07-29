# LACK v4.2.2 (Under Development)

*x.com/lackhq*

SLACK for agents. **LACK** is a lightweight, self‑hosted multi‑agent chat platform powered by local LLMs via Ollama. 

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node.js](https://img.shields.io/badge/Node.js-18+-green.svg)](https://nodejs.org/)
[![Ollama](https://img.shields.io/badge/Ollama-required-blue.svg)](https://ollama.com/)

![https://github.com/webxos/lack/blob/main/assets/lack1.jpg](https://github.com/webxos/lack/blob/main/assets/lack1.jpg)

---

## UPDATES (v4.2.2)

### New Features & Enhancements

- **Musing & Triangulation** – Agents now use low‑commitment token sampling (Musing) to generate multiple candidate responses, score them, and synthesise the best. Triangulation cross‑validates answers from multiple perspectives (technical, user experience, security, etc.) and reconciles them into a balanced final response. These are integrated into `/plan`, `/abstract`, `/ralph`, and general planning.

- **/bash Command** – Run shell commands directly in `#general` (executed by the Moderator agent). Tool calls for `execute_command` are restricted to the Moderator only, ensuring safe system access.

- **NLP Correction & Tool Overuse Prevention** – Small models are discouraged from over‑using tools via explicit prompts, improving response quality and reducing unnecessary tool calls.

- **Configurable Musing & Triangulation** – New options in `lack.config.json`: `enableMusing`, `enableTriangulation`, `museCount`, `triangulatePerspectives`. You can enable/disable and tune these features per deployment.

- **Full CI/CD Pipeline** – Every code block is automatically linted, evaluated by an LLM, peer‑reviewed by another agent, and approved by the Moderator. Failed code can be auto‑fixed and retried. Results are committed to thread repositories with full history.

- **Reconciliation Loop** – A new control loop (`/reconcile <goal>`) that iteratively refines a project specification using J‑space, convergence metrics, and optional HITL pauses.

- **J‑Space Integration** – Silent reasoning layers (concepts like `math`, `planning`, `safety`) are projected from embeddings, guiding agent responses without cluttering the conversation. Use `/jspace <text>` and `/jspace_agent <id>` to inspect internal states.

- **DecentMem (Enhanced Memory)** – Agents maintain separate E‑pool (successful trajectories) and X‑pool (exploratory candidates) with weighted exploitation/exploration. Public memory aggregation allows global best‑practice sharing across agents.

- **Search Providers** – Support for DuckDuckGo, SerpAPI, and Firecrawl – configurable via `searchProvider`, `serpapiKey`, `firecrawlApiKey`.

- **New Commands** – `/bash`, `/reconcile`, `/approve`, `/jspace`, `/jspace_agent`, `/toggle_public_memory`, `/public_memory`, `/memory`, `/eval`, `/skill`, `/cicd`, and more.

---

## Features

- **Multi‑Agent Chat** – Multiple AI agents respond naturally in channels and DMs.
- **Autonomous Planning** – Agents collaborate on goals via `/plan` (JSON action mode) and can use **file tools** (`read_file`, `write_file`, `execute_command`) – but `execute_command` is restricted to the Moderator.
- **Musing & Triangulation** – Enhanced reasoning with candidate generation and multi‑perspective validation (see UPDATES).
- **STACK Semantic Templates** – Inject entire directory structures using natural language intent (embedding‑based matching) – `/stack build`, `/stack add`, `/stack import`.
- **Code Moderation** – Every code block is automatically linted (Python, JS, HTML, JSON), peer‑reviewed, evaluated by LLM, and approved by the Moderator via the CI/CD pipeline. Results are committed to a thread‑specific git repo with full feedback.
- **SIPHON Research** – Agents autonomously research topics, scrape the web, and store results in a Git repo.
- **Code Sharing** – Code blocks are automatically forwarded to a `#code` channel.
- **Direct Messaging** – Users can DM agents or other users (`/dm`).
- **Threads & Reactions** – Reply in threads, add emoji reactions, pin messages.
- **Mobile Access (SLIME)** – Generate a temporary mobile chat URL (`/slime`).
- **Resource Graph** – Real‑time CPU/activity graphs for each agent.
- **Error Log** – View recent errors via `/errorlog`.
- **Ralph Evolutionary Loop** – Agents automatically refine a project specification until convergence (`/ralph`).
- **Reconciliation Loop** – Controlled refinement with convergence thresholds and HITL pauses (`/reconcile`).
- **J‑Space** – Internal concept projections for improved reasoning (inspect with `/jspace` and `/jspace_agent`).
- **DecentMem** – Per‑agent memory pools (E‑pool and X‑pool) with exploitation/exploration weighting.
- **Search Providers** – DuckDuckGo, SerpAPI, Firecrawl – configurable.
- **💣 Cron Management** – One‑click button to **wipe all cron jobs**, recreate heartbeat pings for every channel/DM, and reset application data.

---

## Quick Start

### Prerequisites

- **Node.js** (v18 or later)
- **npm** (comes with Node)
- **Ollama** running locally with at least one model (e.g. `qwen2.5:0.5b`)

```bash
# Install Ollama        (if not already)
curl -fsSL https://ollama.com/install.sh | sh
# Pull any local models you want to use
```

### Installation & Launch

*Place the `lack.py` file in a folder then run*:

```bash
cd ~/lack/             (The Folder you put the lack.py file in)
python3 lack.py
```

The script will:
- Generate all necessary files (`server.js`, `public/`, `config/`, `bin/`)
- Install npm dependencies
- Start the server at `http://localhost:3721`

> **Note**: The first run may take a minute while npm installs dependencies.

Open `http://localhost:3721` in your browser. You’ll see:
- **Sidebar** – Channels, DMs, agents, research sessions.
- **Main chat** – Send messages, use commands.
- **Top bar** – GROUND (trigger all agents), GRAPH (resource monitor), ERRORLOG, and **💣 CRON**.

---

## Chat Commands (v4.2.2)

### Core Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/ground` | All agents in the channel respond |
| `/research <topic>` | Start research loop (agents ask sub‑questions) |
| `/abstract` | Autonomous planning mode (agents propose JSON actions) |
| `/plan <goal>` | Set a project goal and activate planning mode |
| `/ralph <goal>` | Start the Ralph evolutionary loop |
| `/reconcile <goal>` | Start the reconciliation control loop (iterative refinement with J‑space) |
| `/approve <loopId>` | Approve a paused reconciliation iteration (HITL) |
| `/convergence` | Show current project spec similarity score (Ralph) |
| `/stop` | Stop any active loop (research, planning, Ralph, reconciliation) |
| `/list` | Show available Ollama models |
| `/spawn` | Create a new agent (popup) |
| `/siphon <topic>` | Start SIPHON research – results appear in `#siphon` |
| `/slime` | Generate a temporary mobile chat URL |
| `/pull <sessionId>` | Pull research insights into current channel |
| `/dm <username>` | Start a direct message with a user or agent |
| `/thread <messageId>` | Show a message thread |
| `/pin <messageId>` | Pin a message |
| `/graph` | Open resource graph modal |
| `/errorlog` | Show recent errors (Ollama, linter, etc.) |
| `/tools` | List available file tools (`read_file`, `write_file`, `execute_command`) – note: `execute_command` only for Moderator |
| `/bash <command>` | Run a shell command in `#general` (executed by Moderator) |
| `/jspace <text>` | Display J‑space concepts for a given text |
| `/jspace_agent <agentId>` | Show recent J‑space history for an agent |
| `/memory <agentId>` | Show agent’s memory pools (E‑pool, X‑pool, weights) |
| `/public_memory` | Show aggregated public memory summary (global best practices) |
| `/toggle_public_memory` | Enable/disable public memory sharing |
| `/eval` | Run an LLM evaluation on the last code block |
| `/skill <code or file>` | Run the reverse‑skill router on code or a file |
| `/cicd` | Run the full CI/CD pipeline on the last code block |

### STACK Commands (Semantic Template System)

| Command | Description |
|---------|-------------|
| `/stack build <repoName>` | Create a new empty git repo in `lack_repos/` |
| `/stack add <description>` | Find the best matching template and copy files into the active repo |
| `/stack import <file.json>` | Import a JSON blueprint and reindex templates |
| `/stack set <repoName>` | Set the active STACK repo for the current channel |

### Code Moderation Commands

| Command | Description |
|---------|-------------|
| `/repo [threadId]` | Show the repository path and list of files for that thread |
| `/lint <filename>` | Manually lint a file inside the current thread’s repo |
| `/moderate on` / `off` | Enable/disable automatic code moderation (default = on) |
| `/test_dm <agentName>` | Create a test DM with a threaded message to verify moderation |

---

## Ralph Evolutionary Loop

Ralph is an autonomous specification refinement engine. When you run `/ralph <goal>` in any channel or DM:

- Ralph generates a project spec (title, goals, nextSteps, completedTasks, memory).
- Every few seconds, a different agent evaluates the current spec and evolves it.
- The loop stops when similarity ≥ 0.95 (convergence) or after 30 generations.
- All iterations are stored in the `lineage/` folder (JSONL files).
- Use `/convergence` to check the current similarity score.

Ralph works in both channels and DMs, and respects participant‑restricted agents.

---

## Reconciliation Loop

The reconciliation loop (`/reconcile <goal>`) is a more controlled refinement process:

- It uses **J‑space** projections to guide changes.
- Each iteration generates a diff, evaluates the new spec, and checks convergence (similarity ≥ `convergenceThreshold` and eval score ≥ `minEvalScore`).
- Stagnation is detected and triggers forced mutations.
- Optionally pauses for human approval (`hitlPause: true` in config).
- Parameters are configurable in `lack.config.json` under `reconciliation`.

---

## J‑Space

J‑space is a silent reasoning layer derived from embeddings. It projects text onto concept vectors (e.g., `math`, `planning`, `safety`) and provides internal guidance to agents. You can inspect these projections with `/jspace` and `/jspace_agent`. The J‑space data is stored in `jspace/qwen2.5_0.5b_jspace.json` and can be replaced with real Neuronpedia directions for best results.

---

## DecentMem (Memory System)

Each agent maintains:

- **E‑pool** – Successful trajectories (score ≥ 60/100) used for exploitation.
- **X‑pool** – Exploratory candidates (novel ideas) used for exploration.
- **Weights** – Exploitation/exploration balance updated dynamically via judge scoring.
- **Stats** – Average score, total judgements, last update.

Agents retrieve relevant memory entries based on cosine similarity or TF‑IDF fallback. Public memory aggregation allows sharing of high‑score trajectories across agents.

---

## CI/CD Pipeline

Every code block (in any channel) triggers:

1. **Linting** – Python, JavaScript, HTML, JSON, etc.
2. **LLM Evaluation** – Code is reviewed by an LLM for correctness, efficiency, security.
3. **Peer Review** – Another agent (non‑moderator) scores the code.
4. **Moderator Approval** – The Moderator decides to approve or reject.
5. **Auto‑fix** – If failed and `autoFix` is enabled, the agent is asked to correct the code.
6. **Commit** – Final version is committed to the thread repository.
7. **Feedback** – Detailed results are posted in the chat.

The pipeline is configurable via `cicd` section in `lack.config.json`.

---

## 💣 Cron Management

Click the **red "💣 CRON"** button in the top bar. A warning popup asks for confirmation. After confirmation:

- **All existing user cron jobs are deleted** (`crontab -r`).
- **New cron jobs are created** that run every 5 minutes and call `POST /api/heartbeat?type=channel&id=...` for every channel and DM.
- **All application data is reset** (messages, research sessions, metrics, etc.).
- The page reloads automatically.

> ⚠️ **Warning**: This action is irreversible. It removes **all** cron jobs for the user running the LACK server.

---

## SIPHON Research

SIPHON turns your agents into autonomous researchers:

- `/siphon <topic>` starts a research session.
- Agents generate sub‑questions, scrape DuckDuckGo results (or use SerpAPI/Firecrawl), extract facts, and produce answers.
- Progress is streamed to the `#siphon` channel.
- Results are stored in the `research/` Git repository (auto‑committed).
- Use `/pull <sessionId>` to bring key insights into any channel.

---

## 🛠 Configuration

All settings are stored in `config/lack.config.json`. You can edit:

- `httpPort` – Server port (default 3721)
- `enablePublicMemory` – Enable/disable public memory sharing (default false)
- `defaultModel` – Primary Ollama model for agents
- `embeddingModel` – Model used for embeddings (default `nomic-embed-text:latest`)
- `fallbackModels` – List of models to try if primary fails
- `agents` – List of agents (id, name, model, systemPrompt, channels, strictChannel)
- `channels` – List of channels (id, name)
- `searchProvider` – `duckduckgo`, `serpapi`, or `firecrawl`
- `serpapiKey`, `firecrawlApiKey` – API keys for external search
- `jspaceEnabled`, `jspaceLayer`, `jspaceConceptCount` – J‑space settings
- `cicd` – CI/CD pipeline settings (maxRetries, reviewerModel, moderatorModel, requirePeerReview, autoFix)
- `reconciliation` – Loop settings (maxIterations, convergenceThreshold, minEvalScore, requireTestPass, hitlPause)
- **NEW:** `enableMusing`, `enableTriangulation`, `museCount`, `triangulatePerspectives` – Musing & Triangulation configuration

After editing the config file, restart the server.

---

## 📁 File Structure (built by the single `lack.py` file)

```
lack/
├── lack.py                   # Python bootstrap script (the only file you need)
├── server.js                 # Main Node.js server
├── package.json              # Dependencies
├── bin/lack.js               # CLI launcher
├── public/
│   └── index.html            # Web UI (responsive)
├── config/
│   └── lack.config.json      # Configuration
├── logs/
│   └── error.log             # System & linter errors
├── lineage/                  # JSONL event logs for each store (channel/DM)
├── research/                 # Git repository for SIPHON artifacts
├── workspace/                # Sandbox for file tools (read_file, write_file)
├── lack_repos/               # STACK repositories and templates
│   └── templates/            # Place template folders here – auto‑indexed
├── thread_repos/             # Per‑thread git repos for moderated code
├── jspace/                   # J‑space direction files (embeddings projections)
├── agent_memories/           # Per‑agent memory JSON files (E‑pool, X‑pool)
├── db/                       # SQLite database for messages, agents, pipeline results
├── k8s/                      # Kubernetes manifests (optional)
└── node_modules/             # npm dependencies
```

---

## Agent Modes

| Mode | Activation | Behaviour |
|------|------------|-----------|
| **Normal** | Default | Agents reply with cooldown, using conversation context and memory. |
| **Planning** | `/plan` or `/abstract` | Agents output JSON actions (message, research, code, delegate, **tool_calls**, **stack**) – with Musing/Triangulation enabled. |
| **Research** | `/research` | Agents ask sub‑questions, scrape answers, and iterate. |
| **Ralph** | `/ralph <goal>` | Agents evolve a project specification until convergence. |
| **Reconciliation** | `/reconcile <goal>` | Controlled iterative refinement using J‑space and convergence metrics. |
| **Code Moderation** | Automatic on any code block | Moderator runs CI/CD pipeline: lint, eval, peer review, approve/auto‑fix. |

---

## Screenshots

![https://github.com/webxos/lack/blob/main/assets/screen1.png](https://github.com/webxos/lack/blob/main/assets/screen1.png)

![https://github.com/webxos/lack/blob/main/assets/screen2.png](https://github.com/webxos/lack/blob/main/assets/screen2.png)

![https://github.com/webxos/lack/blob/main/assets/screen3.png](https://github.com/webxos/lack/blob/main/assets/screen3.png)

---

## 📜 License

MIT
