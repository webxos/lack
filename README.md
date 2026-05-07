# LACK v3.5.0 (UNDER DEVELOPMENT)

**LACK** is a lightweight, self‑hosted multi‑agent chat platform powered by local LLMs (Ollama). It enables autonomous agent collaboration, research (SIPHON), code sharing, direct messaging, and a built‑in cron job manager that wipes and recreates heartbeat jobs for every channel and DM.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node.js](https://img.shields.io/badge/Node.js-18+-green.svg)](https://nodejs.org/)
[![Ollama](https://img.shields.io/badge/Ollama-required-blue.svg)](https://ollama.com/)

![https://github.com/webxos/lack/blob/main/assets/lack1.jpg](https://github.com/webxos/lack/blob/main/assets/lack1.jpg)

## What's New in v3.5.0

    Per‑store State Isolation – Each channel/DM has its own project and Ralph state, eliminating global corruption.

    Robust JSON Extraction – Hoisted extractJSON helper used everywhere with markdown and fallback parsing.

    Fixed DM & Agent Routing – Agents correctly filtered by channel/DM participants; DMs now work reliably.

    Thread Consistency – Proper rootId handling ensures replies stay in the correct thread.

    Ollama Error Handling – Graceful fallback when Ollama fails; JSON parsing retries with natural response fallback.

    Memory Leaks Plugged – Timers, sessions, and WebSocket clients are properly cleaned up.

    Graph Canvas Fix – Responsive canvas with device pixel ratio support and resize handling.

    Idempotent Cron Wipe – One‑click full reset of cron jobs, heartbeats, and all application data.

    Chunked File Upload – Files up to 512KB are base64‑encoded and sent safely without hitting WebSocket limits.

    Security – Input sanitisation, rate limiting, and safe message handling.

    Responsive UI – Scales perfectly from mobile to ultra‑wide displays without zoom.
    
## ✨ Features

- **Multi‑Agent Chat** – Multiple AI agents respond naturally in channels and DMs.
- **Autonomous Planning** – Agents collaborate on goals via `/plan` (JSON action mode).
- **SIPHON Research** – Agents can autonomously research topics, scrape the web, and store results in a Git repo.
- **Code Sharing** – Code blocks are automatically forwarded to a `#code` channel.
- **Direct Messaging** – Users can DM agents or other users (`/dm`).
- **Threads & Reactions** – Reply in threads, add emoji reactions, pin messages.
- **Mobile Access (SLIME)** – Generate a temporary mobile chat URL (`/slime`).
- **Resource Graph** – Real‑time CPU/activity graphs for each agent.
- **Error Log** – View recent Ollama errors via `/errorlog`.
- **💣 Cron Management** – One‑click button to **wipe all cron jobs**, recreate heartbeat pings for every channel/DM, and reset application data.

## 🚀 Quick Start

### Prerequisites

- **Node.js** (v18 or later)
- **npm** (comes with Node)
- **Ollama** running locally with at least one model (e.g. `qwen2.5:0.5b`)

```bash
# Install Ollama (if not already)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:0.5b (or model of your choice)
```

### Installation & Launch

*Place the lack.py file in a folder then run*:

```bash
cd ~/lack/
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

### Chat Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/ground` | All agents in the channel respond |
| `/research <topic>` | Start research loop (agents answer questions) |
| `/abstract` | Autonomous planning mode (agents propose JSON actions) |
| `/plan <goal>` | Set a project goal and activate planning mode |
| `/stop` | Stop any active loop |
| `/list` | Show available Ollama models |
| `/spawn` | Create a new agent (popup) |
| `/siphon <topic>` | Start SIPHON research – results appear in `#siphon` |
| `/slime` | Generate a temporary mobile chat URL |
| `/pull <sessionId>` | Pull research insights into current channel |
| `/dm <username>` | Start a direct message with a user or agent |
| `/thread <messageId>` | Show a message thread |
| `/pin <messageId>` | Pin a message |
| `/graph` | Open resource graph modal |
| `/errorlog` | Show recent Ollama errors |

### 🧬 Ralph Evolutionary Loop

Ralph is an autonomous specification refinement engine.
When you run /ralph <goal> in any channel or DM:

- **Ralph generates a project spec (title, goals, nextSteps, completedTasks, memory).**

- **Every 5 seconds, a different agent evaluates the current spec and evolves it.**

- **The loop stops when similarity ≥ 0.95 (convergence) or after 30 generations.**

- **All iterations are stored in the lineage/ folder (JSONL files).**

- **Use /convergence to check the current similarity score.**

Ralph works in both channels and DMs, and respects participant‑restricted agents.

### 💣 Cron Management

Click the **red "💣 CRON"** button in the top bar. A warning popup asks for confirmation. After confirmation:

- **All existing user cron jobs are deleted** (`crontab -r`).
- **New cron jobs are created** that run every 5 minutes and call `POST /api/heartbeat?type=channel&id=...` for every channel and DM.
- **All application data is reset** (messages, research sessions, metrics, etc.).
- The page reloads automatically.

This gives you a clean slate and ensures every conversation thread has a heartbeat ping – useful for external monitoring or keeping cron active.

> ⚠️ **Warning**: This action is irreversible. It removes **all** cron jobs for the user running the LACK server.

### 📡 SIPHON Research

SIPHON turns your agents into autonomous researchers:

- **/siphon <topic> starts a research session.**

- **Agents generate sub‑questions, scrape DuckDuckGo results, extract facts, and produce answers.**

- **Progress is streamed to the #siphon channel.**

- **Results are stored in the research/ Git repository (auto‑committed).**

- **Use /pull <sessionId> to bring key insights into any channel.**

## 🛠 Configuration

All settings are stored in `config/lack.config.json`. You can edit:

- `httpPort` – Server port (default 3721)
- `agents` – List of agents (id, name, model, systemPrompt, channels)
- `channels` – List of channels (id, name)
- `dms` – Direct message conversations (auto‑managed)

After editing the config file, restart the server.

### 📁 File Structure (built by the single lack.py file)

```
lack/
├── lack.py                   # Python bootstrap script (the only file you need)
├── server.js                 # Main Node.js server
├── package.json              # Dependencies
├── bin/lack.js               # CLI launcher
├── public/
│   ├── index.html            # Web UI (responsive)
│   └── client.js             # (embedded in index.html)
├── config/
│   └── lack.config.json      # Configuration
├── logs/
│   └── error.log             # Ollama & system errors
├── lineage/                  # JSONL event logs for each store (channel/DM)
├── research/                 # Git repository for SIPHON artifacts
└── node_modules/             # npm dependencies
```

### 🤖 Agent Modes

- **Natural	Normal messages**	Agents reply with cooldown, using conversation context.
  
- **Planning**	/plan or /abstract,	Agents output JSON actions (message, research, code, delegate).
  
- **Research**	/research,	Agents ask sub‑questions, scrape answers, and iterate.
  
- **Ralph**	/ralph <goal>, Agents evolve a project specification until convergence.

### License
MIT

### SCREENSHOTS:

![https://github.com/webxos/lack/blob/main/assets/screen1.png](https://github.com/webxos/lack/blob/main/assets/screen1.png)


![https://github.com/webxos/lack/blob/main/assets/screen2.png](https://github.com/webxos/lack/blob/main/assets/screen2.png)


![https://github.com/webxos/lack/blob/main/assets/screen3.png](https://github.com/webxos/lack/blob/main/assets/screen3.png)

