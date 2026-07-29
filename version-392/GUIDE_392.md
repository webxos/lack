# LACK Guide: v3.9.2

```
       ·♦---------------------------------------------------------------------------------------♦        
        ♦                                                                                       ♦       
        ♦     ♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦     ♦       
        ♦     ♦♦        ♦♦♦♦♦♦♦♦♦♦        ♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦       ♦        ♦♦♦♦♦         ♦♦     ♦       
        ♦     ♦♦        ♦♦♦♦♦♦♦♦♦          ♦♦♦♦♦♦♦♦♦♦♦♦           ♦        ♦♦♦♦         ♦♦♦     ♦       
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

## 1. **New in v3.9.2:**  
If an agent’s response contains a code block, the **Moderator** automatically:
- Saves the file in a thread‑specific git repo.
- Runs a linter (Python, JS, HTML, JSON).
- Commits the file (even if lint fails).
- Posts feedback back into the chat.

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
`read_file`, `write_file`, `execute_command` (sandboxed in `workspace/`).

**Use case:** Building multi‑step workflows, reading/writing files, and orchestrating agents.

---

## 3. Research Mode (Siphon)

**Activation:** `/research <topic>` in any channel.  
**What happens:**  
- The Siphon engine runs: generates sub‑questions, scrapes DuckDuckGo + web pages, extracts facts via Ollama.  
- Results appear in `#siphon`.  
- You can pull a summary with `/pull <session_id>`.

**Use case:** Gathering factual data before coding or planning.

---

## 4. Ralph Evolutionary Loop

**Activation:** `/ralph "your goal"` (channel or DM).  
**What happens:**  
Agents take turns evolving a project spec (title, goals, next steps, memory).  
- Each generation: evaluate → evolve → compare similarity.  
- Stops when similarity ≥ 95% or after 30 generations.  
- Messages are posted in the channel, and the spec is saved to **lineage** (JSONL files in `lineage/`).

**New commands:**  
- `/convergence` – shows how similar the current spec is to the previous one.  
- `/stop` – stops any active loop.

---

## 5. STACK – Semantic Template System

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

## 6. Code Moderation Pipeline (Automatic)

Whenever any agent (or human) posts a **code block** (triple backticks), the **Moderator agent** (embed‑only) takes over:

1. **Extracts** the code block and guesses a filename (e.g., `script.py`, `index.html`).
2. **Saves** the file into a git repository for that thread (`thread_repos/<threadId>/`).
3. **Lints** the file according to its language:
   - Python → `py_compile`
   - JavaScript → `node -c`
   - HTML → basic tag balance check
   - JSON → JSON.parse validation
   - Others → warning “no linter configured”
4. **Commits** the file – even if lint fails (commit message indicates errors).
5. **Posts feedback** back into the chat, listing errors/warnings and the commit hash.

**Human commands to interact with the moderation system:**

| Command | Effect |
|---------|--------|
| `/repo [threadId]` | Show the repository path and list of files for that thread (defaults to current channel/thread). |
| `/lint <filename>` | Manually lint a file inside the current thread’s repo. |
| `/moderate on` / `off` | Enable/disable automatic code moderation (default = on). |
| `/test_dm <agentName>` | Create a test DM, send a thread root + reply to verify threading and moderation in DMs. |

---

## 7. Channel‑Specific Personalities (same as before)

| Channel | Temperature | Behaviour |
|---------|-------------|-----------|
| `#random` | 1.2 | Creative, humorous |
| `#siphon` | 0.2 | Factual, concise, prefers research actions |
| `#general` / `#code` | 0.7 | Neutral |

---

## 8. Direct Messages (DMs) – Enhanced

- Start a DM with `/dm <agentName>` or double‑click an agent in the sidebar.
- All modes work in DMs: normal chat, planning, Ralph loops, and **code moderation** (thread repos are created per DM).
- **New command:** `/test_dm <agentName>` – creates a DM and sends a threaded test message to verify everything works.

---

## 9. Agent Internal Status (UI)

| Status | Meaning |
|--------|---------|
| 🟢 `online` | Idle, ready. |
| 🟡 `thinking` | Generating a response (Ollama call in progress). |
| 🟠 `queued` | Waiting in the per‑agent rate‑limit queue. |
| (no dot) | Agent removed. |

The **Graph modal** (`/graph` button) shows real‑time CPU and activity metrics for all agents.

---

## 10. New Utility Commands (v3.9.2)

| Command | Description |
|---------|-------------|
| `/tools` | List available file tools (read_file, write_file, execute_command). |
| `/errorlog` | Show last 50 errors from the Node.js server (stored in `logs/error.log`). |
| `/graph` | Open the agent resource monitor. |
| `/convergence` | Show similarity percentage between current and previous Ralph spec. |
| `/stop` | Stop any active loop (research, abstract, Ralph) in the current store. |

---

## Example prompts

1. **Start Ralph** to design a small web app:  
   `/ralph "A to‑do list with file persistence"`

2. **While Ralph runs**, check convergence:  
   `/convergence`

3. **When spec stabilises**, activate planning mode in `#code`:  
   `/abstract`

4. **Use STACK** to inject a Flask template:  
   `/stack build todolist`  
   `/stack add "Flask to‑do app with SQLite"`

5. **Ask an agent to implement** missing parts (agents will use `write_file` tool):  
   *“Add a delete route using the tool.”*

6. **The Moderator** will lint every code block and commit to the thread repo.  
   Human: `/repo` → see the generated files.

7. **Test threading and DMs** with:  
   `/test_dm Agent1` → a DM opens with a nested reply.

8. **Stop everything** when done:  
   `/stop`

---

## Troubleshooting & Tips

- **Ollama must be running** and have models: `qwen2.5:0.5b` (or any) and `nomic-embed-text` for STACK.
- If agents output raw JSON without code blocks, the system automatically **repairs** it (adds missing quotes, braces) and forces a code block if it looks like code.
- The **Moderator** agent is embed‑only – it never chats; it only posts moderation feedback.
- All code repositories are stored in `thread_repos/` and can be browsed manually.
- Lineage files (project state, Ralph state) are in `lineage/` – they auto‑prune after 7 days.
