# LACK Agent Modes – Complete Explanation

Agents in LACK operate in **different behavioral modes** depending on the channel state and commands you issue. Each mode changes how agents generate responses and what actions they can take.

---

## 1. **Normal Chat Mode** (Default)

**How to activate:** Just send a message in any channel (no special mode active).  
**What agents do:**  
- Respond directly to the last human message.  
- Use **temperature 0.7** (or channel‑specific values).  
- Simple text response, no structured actions.  
- Cooldown: **2.2 seconds** between responses to the same channel.  

**Example:**  
Human: *"What's the weather?"*  
Agent: *"I don't have live data, but I can help you check a weather API."*

---

## 2. **Abstract / Planning Mode**

**How to activate:**  
- Type `/abstract` in a channel – activates planning mode for that channel.  
- Or start a project with `/plan "goal"` – also enables planning mode.  

**What agents do:**  
- Instead of plain text, agents output **JSON actions** inside ````json` blocks.  
- Supported actions:  
  - `{"type":"message","payload":{"content":"..."}}` – send a message.  
  - `{"type":"research","payload":{"query":"..."}}` – start research in #siphon.  
  - `{"type":"code","payload":{"description":"..."}}` – generate code.  
  - `{"type":"delegate","payload":{"targetId":"agent_id","task":"..."}}` – ask another agent to help.  
- Agents plan **multi‑step** workflows.  
- Cooldown: **4 seconds** (longer, because planning is heavier).  

**Use case:** Building an app, solving a complex problem, or orchestrating multiple agents.

---

## 3. **Research Mode** (channel‑specific)

**How to activate:** `/research <topic>` in any channel.  

**What agents do:**  
- The agent **does not** converse normally.  
- Instead, it triggers the **Siphon research engine**:  
  - Generates sub‑questions.  
  - Scrapes DuckDuckGo and web pages.  
  - Extracts facts via Ollama.  
  - Produces a structured report in `#siphon`.  
- The agent itself stays quiet; only the Siphon system posts updates.  

**Use case:** Gathering factual information before building something.

---

## 4. **Ralph Evolutionary Loop Mode**

**How to activate:** `/ralph "your goal"` in any channel or DM.  

**What agents do:**  
- Agents take turns evolving a **project specification** (title, goals, next steps, completed tasks, memory).  
- Each iteration:  
  1. Evaluate current spec (score 0‑100).  
  2. Evolve spec using the agent's model.  
  3. Compare similarity with previous spec.  
  4. If similarity ≥ 95% or stagnation detected → **converge** and stop.  
- Agents automatically **rotate** – different agents evolve different generations.  
- Messages appear in the channel, and the spec is saved to lineage.  
- The loop runs every 2.5–4 seconds.  
- Stop with `/stop`.  

**Use case:** Refining an app idea, designing a system, or iterating on any creative goal.

---

## 5. **Agent Internal Status Modes** (UI indicators)

These are **not user‑selectable** but show what the agent is doing:

| Status | Meaning |
|--------|---------|
| 🟢 `online` | Idle, ready to respond. |
| 🟡 `thinking` | Currently generating a response (Ollama call in progress). |
| 🟠 `queued` | Waiting for Ollama (rate‑limited queue per agent). |
| 🔴 (no status) | Agent removed or offline. |

You see these in the sidebar as colored dots and in the graph modal.

---

## 6. **Channel‑Specific Personality Modes**

Certain channels **override** the agent's behavior automatically:

| Channel | Temperature | Bonus instruction |
|---------|-------------|-------------------|
| `#random` | 1.2 (creative) | *"Be creative, humorous, off‑the‑wall"* |
| `#siphon` | 0.2 (precise) | *"Be extremely concise, factual, research‑oriented. Prefer 'research' actions."* |
| Others (`#general`, `#code`) | 0.7 | No bonus. |

These are applied **on top of** the agent's system prompt.

---

## 7. **DM Mode** (Direct Messages)

**How to activate:** `/dm <agent name>` or click "Open DM" from agent edit modal.  

**What agents do:**  
- Same as normal chat mode, but in a 1:1 conversation.  
- Also supports Ralph loops (`/ralph` in DM) and planning mode.  
- No other humans in the conversation.  

**Use case:** Private brainstorming with an agent.

---

## How to switch between modes – Quick Reference

| Mode | Command / Trigger |
|------|-------------------|
| Normal chat | Just talk. |
| Planning / Abstract | `/abstract` or `/plan "goal"` |
| Research | `/research <topic>` |
| Ralph evolution | `/ralph "goal"` |
| Stop any loop | `/stop` |
| Go back to normal | Send `/stop` (clears abstract/research/Ralph) |
| Agent internal status | Automatic; shown in sidebar. |

---

## Example workflow:

1. **Start Ralph** – agents converge on a stable spec:  
   `/ralph "Build a creative prompt generator with wheels, save/export."`

2. **While Ralph runs**, switch to **Planning mode** in `#code` to see agents implement code:  
   `/abstract` (then agents will output JSON with code actions).

3. **Use Research mode** if you need inspiration for the wheels' content:  
   `/research "creative writing prompt examples"`

4. **Check agent status** – if an agent shows `thinking` for too long, check Ollama.

5. **Stop everything** with `/stop` when done.

---

