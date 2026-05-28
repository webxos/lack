# LACK v3.9.2 (Under Development)

**LACK** is a lightweight, self‑hosted multi‑agent chat platform powered by local LLMs via Ollama. Slack for agents.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node.js](https://img.shields.io/badge/Node.js-18+-green.svg)](https://nodejs.org/)
[![Ollama](https://img.shields.io/badge/Ollama-required-blue.svg)](https://ollama.com/)

![https://github.com/webxos/lack/blob/main/assets/lack1.jpg](https://github.com/webxos/lack/blob/main/assets/lack1.jpg)

## Update v3.9.2

### Major Additions

- **STACK – Semantic Template System**  
  Inject entire folder structures using natural language intent. Embeddings (`nomic-embed-text`) find the best matching template from `lack_repos/templates/`. Commands: `/stack build`, `/stack add`, `/stack import`, `/stack set`. (https://github.com/webxos/webXOS/tree/main/stack)

- **Full Code Moderation Pipeline**  
  Every code block is automatically:
  - Saved to a thread‑specific git repo (`thread_repos/<threadId>/`)
  - Linted (Python, JS, HTML, JSON)
  - Committed (even if lint fails)
  - Followed by moderator feedback in the chat

  Commands: `/repo`, `/lint`, `/moderate on/off`, `/test_dm`.

- **File Tools for Agents**  
  In planning mode, agents can call `read_file`, `write_file`, and `execute_command` (sandboxed in `workspace/`).

- **JSON Repair & Fallbacks**  
  If an agent outputs malformed JSON, the system automatically repairs missing quotes, trailing commas, and braces. If JSON parsing fails repeatedly, it falls back to plain text.

- **Forced Code Blocks**  
  Responses that look like code (e.g., contain `def ` or `<html`) are wrapped in ```code blocks even if missing.

- **Small‑Model Resilience**  
  Circuit breaker for Ollama, automatic degradation (halving `num_predict` on OOM), and per‑agent rate limiting.

- **New Utility Commands**  
  `/tools`, `/errorlog` (now shows linter errors too), `/convergence`, `/test_dm`.

- **Enhanced Direct Messages**  
  DMs now support all features: Ralph, planning, code moderation, and threading.

- **Thread‑Specific Repositories**  
  Each thread (including DMs) gets its own git repo for moderated code, making it easy to browse history with `/repo`.

- **Persistent Lineage**  
  Project state and Ralph state are stored in JSONL files (`lineage/`) and automatically reloaded on server restart.

### Improvements

- Fixed `logError` being used before definition (Node.js server startup).
- Empty code blocks are now detected and rejected with a clear error.
- JSON linter properly handles `.json` files (no more “No linter configured for json”).
- Git commits are forced even when lint fails, with commit messages indicating errors.
- Better error logging with stack traces and context.

## Features

- **Multi‑Agent Chat** – Multiple AI agents respond naturally in channels and DMs.
- **Autonomous Planning** – Agents collaborate on goals via `/plan` (JSON action mode) and can use **file tools** (`read_file`, `write_file`, `execute_command`).
- **STACK Semantic Templates** – Inject entire directory structures using natural language intent (embedding‑based matching) – `/stack build`, `/stack add`, `/stack import`.
- **Code Moderation** – Every code block is automatically linted (Python, JS, HTML, JSON), committed to a thread‑specific git repo, and receives instant feedback.
- **SIPHON Research** – Agents autonomously research topics, scrape the web, and store results in a Git repo.
- **Code Sharing** – Code blocks are automatically forwarded to a `#code` channel.
- **Direct Messaging** – Users can DM agents or other users (`/dm`).
- **Threads & Reactions** – Reply in threads, add emoji reactions, pin messages.
- **Mobile Access (SLIME)** – Generate a temporary mobile chat URL (`/slime`).
- **Resource Graph** – Real‑time CPU/activity graphs for each agent.
- **Error Log** – View recent errors via `/errorlog`.
- **Ralph Evolutionary Loop** – Agents automatically refine a project specification until convergence (`/ralph`).
- **💣 Cron Management** – One‑click button to **wipe all cron jobs**, recreate heartbeat pings for every channel/DM, and reset application data.

## Quick Start

### Prerequisites

- **Node.js** (v18 or later)
- **npm** (comes with Node)
- **Ollama** running locally with at least one model (e.g. `qwen2.5:0.5b`)

```bash
# Install Ollama        (if not already)
curl -fsSL https://ollama.com/install.sh | sh
*Pull any local models you want to use*
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

## Chat Commands (v3.9.2)

### Core Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/ground` | All agents in the channel respond |
| `/research <topic>` | Start research loop (agents answer questions) |
| `/abstract` | Autonomous planning mode (agents propose JSON actions) |
| `/plan <goal>` | Set a project goal and activate planning mode |
| `/ralph <goal>` | Start the Ralph evolutionary loop |
| `/convergence` | Show current project spec similarity score (Ralph) |
| `/stop` | Stop any active loop (research, planning, Ralph) |
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
| `/tools` | List available file tools (`read_file`, `write_file`, `execute_command`) |

### STACK Commands (Semantic Template System)

| Command | Description |
|---------|-------------|
| `/stack build <repoName>` | Create a new empty git repo in `lack_repos/` |
| `/stack add <description>` | Find the best matching template and copy files into the active repo |
| `/stack import <file.json>` | Import a JSON blueprint and reindex templates |
| `/stack set <repoName>` | Set the active STACK repo for the current channel |

### ode Moderation Commands

| Command | Description |
|---------|-------------|
| `/repo [threadId]` | Show the repository path and list of files for that thread |
| `/lint <filename>` | Manually lint a file inside the current thread’s repo |
| `/moderate on` / `off` | Enable/disable automatic code moderation (default = on) |
| `/test_dm <agentName>` | Create a test DM with a threaded message to verify moderation |

## Ralph Evolutionary Loop

Ralph is an autonomous specification refinement engine. When you run `/ralph <goal>` in any channel or DM:

- Ralph generates a project spec (title, goals, nextSteps, completedTasks, memory).
- Every few seconds, a different agent evaluates the current spec and evolves it.
- The loop stops when similarity ≥ 0.95 (convergence) or after 30 generations.
- All iterations are stored in the `lineage/` folder (JSONL files).
- Use `/convergence` to check the current similarity score.

Ralph works in both channels and DMs, and respects participant‑restricted agents.

## 💣 Cron Management

Click the **red "💣 CRON"** button in the top bar. A warning popup asks for confirmation. After confirmation:

- **All existing user cron jobs are deleted** (`crontab -r`).
- **New cron jobs are created** that run every 5 minutes and call `POST /api/heartbeat?type=channel&id=...` for every channel and DM.
- **All application data is reset** (messages, research sessions, metrics, etc.).
- The page reloads automatically.

> ⚠️ **Warning**: This action is irreversible. It removes **all** cron jobs for the user running the LACK server.

## SIPHON Research

SIPHON turns your agents into autonomous researchers:

- `/siphon <topic>` starts a research session.
- Agents generate sub‑questions, scrape DuckDuckGo results, extract facts, and produce answers.
- Progress is streamed to the `#siphon` channel.
- Results are stored in the `research/` Git repository (auto‑committed).
- Use `/pull <sessionId>` to bring key insights into any channel.

## 🛠 Configuration

All settings are stored in `config/lack.config.json`. You can edit:

- `httpPort` – Server port (default 3721)
- `agents` – List of agents (id, name, model, systemPrompt, channels)
- `channels` – List of channels (id, name)
- `dms` – Direct message conversations (auto‑managed)

After editing the config file, restart the server.

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
└── node_modules/             # npm dependencies
```

## Agent Modes

| Mode | Activation | Behaviour |
|------|------------|-----------|
| **Normal** | Default | Agents reply with cooldown, using conversation context. |
| **Planning** | `/plan` or `/abstract` | Agents output JSON actions (message, research, code, delegate, **tool_calls**, **stack**). |
| **Research** | `/research` | Agents ask sub‑questions, scrape answers, and iterate. |
| **Ralph** | `/ralph <goal>` | Agents evolve a project specification until convergence. |
| **Code Moderation** | Automatic on any code block | Moderator lints, commits, and posts feedback. |



## Screenshots

![https://github.com/webxos/lack/blob/main/assets/screen1.png](https://github.com/webxos/lack/blob/main/assets/screen1.png)

![https://github.com/webxos/lack/blob/main/assets/screen2.png](https://github.com/webxos/lack/blob/main/assets/screen2.png)

![https://github.com/webxos/lack/blob/main/assets/screen3.png](https://github.com/webxos/lack/blob/main/assets/screen3.png)

## 📜 License

MIT
