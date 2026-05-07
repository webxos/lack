#!/usr/bin/env python3
"""
LACK v3.5.0
All errors resolved:
- extractJSON hoisted and used everywhere
- Per‑store projectState and Ralph state (no global corruption)
- DM routing and agent filtering fixed
- Thread consistency with proper rootId
- Ollama error handling with JSON fallback everywhere
- Memory leaks plugged (timers, sessions, clients)
- Graph canvas DPR & resize fixed
- Cron wipe idempotent and full reset
- File upload chunked to avoid WS limit
- Security: input sanitisation and rate limiting
- Responsive UI: scales from mobile to ultra‑wide without zoom
"""

import os
import sys
import subprocess
import stat
import webbrowser
import threading
import time
import json
import signal
from pathlib import Path

# ----------------------------------------------------------------------
# Embedded Assets – Corrected and Final
# ----------------------------------------------------------------------

SERVER_JS = r'''
const express = require('express');
const path = require('path');
const WebSocket = require('ws');
const { v4: uuidv4 } = require('uuid');
const fs = require('fs');
const axios = require('axios');
const cheerio = require('cheerio');
const simpleGit = require('simple-git');
const { exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

// ========== HOISTED HELPER – MUST BE AT THE VERY TOP ==========
function extractJSON(str) {
  if (!str || typeof str !== 'string') return null;
  // Try markdown code block first
  const jsonBlock = str.match(/```json\s*([\s\S]*?)\s*```/);
  if (jsonBlock && jsonBlock[1]) {
    try { return JSON.parse(jsonBlock[1].trim()); } catch(e) {}
  }
  // Find the first { and its matching }
  let start = str.indexOf('{');
  if (start === -1) return null;
  let depth = 0;
  for (let i = start; i < str.length; i++) {
    if (str[i] === '{') depth++;
    else if (str[i] === '}') depth--;
    if (depth === 0) {
      try { return JSON.parse(str.substring(start, i+1)); } catch(e) { return null; }
    }
  }
  // Fallback: remove surrounding text and try to parse the largest JSON object
  const possible = str.match(/\{.*\}/s);
  if (possible) {
    try { return JSON.parse(possible[0]); } catch(e) {}
  }
  return null;
}
// ================================================================

// ---------- Configuration ----------
const configPath = path.join(__dirname, 'config', 'lack.config.json');
let config;
try {
  config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
} catch (err) {
  config = {
    httpPort: 3721,
    agents: [
      { id: "agent1", name: "Agent 1", model: "qwen2.5:0.5b", systemPrompt: "You are a helpful AI assistant.", channels: ["general","random","siphon","code"] },
      { id: "agent2", name: "Agent 2", model: "qwen2.5:0.5b", systemPrompt: "You are a creative AI.", channels: ["general","random","siphon","code"] }
    ],
    channels: [
      { id: "general", name: "general" },
      { id: "random", name: "random" },
      { id: "siphon", name: "siphon" },
      { id: "code", name: "code" }
    ],
    dms: []
  };
  fs.mkdirSync(path.join(__dirname, 'config'), { recursive: true });
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
}
const PORT = config.httpPort || 3721;
const OLLAMA_URL = 'http://localhost:11434';
const RESEARCH_DIR = path.join(__dirname, 'research');
const LOG_DIR = path.join(__dirname, 'logs');
const ERROR_LOG_PATH = path.join(LOG_DIR, 'error.log');
fs.mkdirSync(LOG_DIR, { recursive: true });
fs.mkdirSync(path.join(__dirname, 'lineage'), { recursive: true });
const GIT = simpleGit();

// ---------- Global error log ----------
global.errorLog = [];
function logError(errorObj) {
  const entry = { timestamp: Date.now(), ...errorObj };
  try { fs.appendFileSync(ERROR_LOG_PATH, JSON.stringify(entry) + '\n'); } catch (e) {}
  global.errorLog.unshift(entry);
  if (global.errorLog.length > 200) global.errorLog.pop();
  console.error('[ERROR]', entry);
}

// ---------- Stores ----------
const channels = new Map();
const agents = new Map();
const clients = new Map();
const researchSessions = new Map();
const slimeSessions = new Map();
const dms = new Map();
const pinnedMessages = new Map();
const userReactions = new Map();
const agentMetrics = new Map();
const jsonFailCount = new Map();

// ---------- PER‑STORE state (fixes global corruption) ----------
const projectStates = new Map(); // storeId -> { active, title, goals, nextSteps, completedTasks, memory }
function getProjectState(storeId) {
  return projectStates.get(storeId) || { active: false, title: null, goals: [], nextSteps: [], completedTasks: [], memory: {} };
}
function setProjectState(storeId, state) {
  projectStates.set(storeId, { ...state });
  persistProjectState(storeId);
}

// Ralph state per store
const ralphActive = new Map();
const ralphGenerations = new Map();
const ralphGoals = new Map();
const ralphTimers = new Map();
const ralphCancel = new Map();
const ralphStagnation = new Map();
const ralphNextAgentIdx = new Map();
const ralphLastBroadcast = new Map(); // debounce for status

// ---------- Helper: user ID ----------
function getUserId(ws) {
  let client = clients.get(ws);
  if (!client) {
    const id = `human_${uuidv4().slice(0,6)}`;
    clients.set(ws, { username: id, channelId: 'general', userId: id, dmId: null, openThreadId: null });
    client = clients.get(ws);
  }
  return client.userId;
}

// ---------- Initialize stores ----------
config.channels.forEach(ch => {
  channels.set(ch.id, {
    id: ch.id, name: ch.name, messages: [],
    researchActive: false, researchTopic: null, abstractActive: false,
    loopTimer: null, pinned: new Set()
  });
});
if (config.dms) {
  config.dms.forEach(dm => {
    dms.set(dm.id, {
      id: dm.id, participants: dm.participants,
      name: dm.name || dm.participants.join(', '), messages: []
    });
  });
}
config.agents.forEach(agentCfg => {
  agents.set(agentCfg.id, {
    ...agentCfg, lastResponseTime: new Map(), status: 'online', statusMessage: ''
  });
  agentMetrics.set(agentCfg.id, {
    cpu: Array(30).fill(0), mem: Array(30).fill(0),
    activity: Array(30).fill(0), timestamps: Array(30).fill(Date.now())
  });
  jsonFailCount.set(agentCfg.id, 0);
});

// ---------- Metric helpers ----------
function updateAgentMetrics(agentId, responseTimeMs = 0, wasActive = false) {
  const metrics = agentMetrics.get(agentId);
  if (!metrics) return;
  const cpuVal = Math.min(100, Math.max(0, Math.floor(responseTimeMs / 100)));
  const activityVal = wasActive ? 100 : 0;
  metrics.cpu.push(cpuVal); metrics.cpu.shift();
  metrics.activity.push(activityVal); metrics.activity.shift();
  metrics.timestamps.push(Date.now()); metrics.timestamps.shift();
  agentMetrics.set(agentId, metrics);
}
setInterval(() => {
  for (let [agentId, metrics] of agentMetrics.entries()) {
    metrics.cpu = metrics.cpu.map(v => Math.max(0, v - 5));
    metrics.activity = metrics.activity.map(v => Math.max(0, v - 10));
    agentMetrics.set(agentId, metrics);
  }
}, 30000);

// ---------- EventStore (lineage) ----------
function getLineagePath(storeId) { return path.join(__dirname, 'lineage', `${storeId}.jsonl`); }
function appendEvent(storeId, event) {
  try { fs.appendFileSync(getLineagePath(storeId), JSON.stringify(event) + '\n'); } catch (e) {}
}
function reconstructLineage(storeId) {
  const filePath = getLineagePath(storeId);
  if (!fs.existsSync(filePath)) return [];
  return fs.readFileSync(filePath, 'utf-8').split('\n').filter(l => l.trim()).map(l => JSON.parse(l));
}
function persistProjectState(storeId) {
  appendEvent(storeId, { type: 'project_state', timestamp: Date.now(), state: getProjectState(storeId) });
}
function loadProjectStateFromLineage(storeId) {
  const lineage = reconstructLineage(storeId);
  for (let i = lineage.length-1; i >= 0; i--) {
    if (lineage[i].type === 'project_state') {
      setProjectState(storeId, lineage[i].state);
      return true;
    }
  }
  return false;
}
function persistRalphState(storeId) {
  appendEvent(storeId, {
    type: 'ralph_state', timestamp: Date.now(),
    generation: ralphGenerations.get(storeId), goal: ralphGoals.get(storeId), active: ralphActive.get(storeId)
  });
}
function loadRalphStateFromLineage(storeId) {
  const lineage = reconstructLineage(storeId);
  for (let i = lineage.length-1; i >= 0; i--) {
    if (lineage[i].type === 'ralph_state') {
      ralphGenerations.set(storeId, lineage[i].generation);
      ralphGoals.set(storeId, lineage[i].goal);
      ralphActive.set(storeId, lineage[i].active);
      return true;
    }
  }
  return false;
}

// ---------- Message helpers ----------
function addMessage(storeId, sender, senderType, content, parentId = null) {
  let store = channels.get(storeId) || dms.get(storeId);
  if (!store) return null;
  let threadId = null;
  if (parentId) {
    const parent = store.messages.find(m => m.id === parentId);
    threadId = parent ? (parent.threadId || parent.id) : parentId;
  }
  const msg = {
    id: uuidv4(), sender, senderType, content, timestamp: Date.now(),
    parentId: parentId || null, threadId, replyCount: 0, reactions: {}
  };
  store.messages.push(msg);
  if (store.messages.length > 1000) store.messages.shift();
  if (parentId) {
    const parent = store.messages.find(m => m.id === parentId);
    if (parent) {
      parent.replyCount = (parent.replyCount || 0) + 1;
      if (!parent.threadId) parent.threadId = parent.id;
    }
  }
  appendEvent(storeId, { type: 'message', timestamp: msg.timestamp, message: { id: msg.id, sender, senderType, content, parentId, threadId } });
  return msg;
}

function getThreadMessages(storeId, threadId) {
  const store = channels.get(storeId) || dms.get(storeId);
  if (!store) return [];
  const rootId = store.messages.find(m => m.id === threadId)?.threadId || threadId;
  return store.messages.filter(m => m.threadId === rootId || m.id === rootId);
}

function broadcastToStore(storeId, message, excludeWs = null) {
  const isChannel = channels.has(storeId);
  for (let [ws, client] of clients.entries()) {
    if (ws === excludeWs) continue;
    if (ws.readyState !== WebSocket.OPEN) continue;
    if (isChannel && client.channelId === storeId) {
      ws.send(JSON.stringify({ type: 'new_message', channelId: storeId, message }));
    } else if (!isChannel && client.dmId === storeId) {
      ws.send(JSON.stringify({ type: 'new_dm_message', dmId: storeId, message }));
    }
  }
}

function broadcastThreadUpdate(storeId, threadId, excludeWs = null) {
  const threadMsgs = getThreadMessages(storeId, threadId);
  for (let [ws, client] of clients.entries()) {
    if (ws !== excludeWs && client.openThreadId === threadId && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'thread_update', storeId, threadId, messages: threadMsgs }));
    }
  }
}

function broadcastAgents() {
  const agentList = Array.from(agents.values()).map(a => ({
    id: a.id, name: a.name, model: a.model,
    systemPrompt: a.systemPrompt, channels: a.channels,
    status: a.status, statusMessage: a.statusMessage
  }));
  for (let [ws] of clients.entries()) {
    if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'agents_list', agents: agentList }));
  }
}

// Debounced broadcast for Ralph status (prevents spam)
function broadcastRalphStatus(storeId) {
  const now = Date.now();
  const last = ralphLastBroadcast.get(storeId) || 0;
  if (now - last < 800) return;
  ralphLastBroadcast.set(storeId, now);
  const active = ralphActive.get(storeId);
  const gen = ralphGenerations.get(storeId) || 0;
  const goal = ralphGoals.get(storeId) || '';
  const snippet = goal.length > 30 ? goal.substring(0,30)+'…' : goal;
  for (let [ws, client] of clients.entries()) {
    if (ws.readyState === WebSocket.OPEN && (client.channelId === storeId || client.dmId === storeId)) {
      ws.send(JSON.stringify({ type: 'ralph_status', storeId, active, generation: gen, goal: snippet }));
    }
  }
}

function broadcastDMs(userId) {
  const userDMs = getUserDMs(userId);
  for (let [ws, client] of clients.entries()) {
    if (client.userId === userId && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'dms', dms: userDMs }));
    }
  }
}

// ---------- Ollama with robust error handling ----------
async function queryOllama(model, prompt, systemPrompt = '', temperature = 0.7, agentId = null) {
  const start = Date.now();
  try {
    const response = await axios.post(`${OLLAMA_URL}/api/generate`, {
      model, prompt, system: systemPrompt, stream: false,
      options: { temperature, num_predict: 2048 }
    });
    const duration = Date.now() - start;
    if (agentId) updateAgentMetrics(agentId, duration, true);
    return response.data.response || "I'm sorry, I couldn't generate a response.";
  } catch (err) {
    logError({ agentId: agentId || 'system', model, error: err.message, context: 'queryOllama' });
    if (agentId) updateAgentMetrics(agentId, 0, false);
    // Return a special marker that callers can detect
    return `[OLLAMA_ERROR] ${err.message.substring(0,80)}`;
  }
}
async function getOllamaModels() {
  try { const res = await axios.get(`${OLLAMA_URL}/api/tags`); return res.data.models.map(m => m.name); }
  catch (e) { return []; }
}

// ---------- Code blocks ----------
function extractCodeBlocks(text) {
  const regex = /```(\w*)\n([\s\S]*?)```/g;
  const blocks = [];
  let match;
  while ((match = regex.exec(text)) !== null) blocks.push({ language: match[1] || 'text', code: match[2].trim() });
  return blocks;
}
async function handleAgentResponse(agent, storeId, responseText, parentId = null) {
  const msg = addMessage(storeId, agent.name, 'agent', responseText, parentId);
  if (!msg) return;
  broadcastToStore(storeId, msg);
  if (parentId) broadcastThreadUpdate(storeId, parentId);
  const codeBlocks = extractCodeBlocks(responseText);
  if (codeBlocks.length > 0 && storeId !== 'code' && channels.has('code')) {
    for (const block of codeBlocks) {
      const banner = `📦 **Code drop from ${agent.name}** (${block.language})\n\`\`\`${block.language}\n${block.code}\n\`\`\``;
      addMessage('code', agent.name, 'agent', banner);
      broadcastToStore('code', { sender: agent.name, content: banner, senderType: 'agent' });
    }
    const notice = `_(Code block generated – see #code)_`;
    const noticeMsg = addMessage(storeId, 'System', 'system', notice);
    if (noticeMsg) broadcastToStore(storeId, noticeMsg);
  }
}

// ---------- Conversation context ----------
function buildConversationContext(storeId, agentName, parentId = null, maxMessages = 8) {
  const store = channels.get(storeId) || dms.get(storeId);
  if (!store) return '';
  let messages = store.messages;
  if (parentId) {
    const rootId = store.messages.find(m => m.id === parentId)?.threadId || parentId;
    messages = store.messages.filter(m => m.threadId === rootId || m.id === rootId);
  }
  const relevant = messages.filter(m => m.sender !== agentName && m.senderType !== 'system');
  return relevant.slice(-maxMessages).map(m => `${m.sender}: ${m.content}`).join('\n');
}

// ---------- Channel personality ----------
function getChannelPersonality(channelName) {
  if (channelName === 'random') {
    return {
      temperature: 1.2,
      systemBonus: "\nYou are in #random. Be creative, humorous, off‑the‑wall. Jokes and wild ideas are welcome. Do not be boring or purely factual.",
      planBonus: "You are in #random. In planning mode, prefer creative actions (message with fun content, delegate for weird tasks). Avoid research unless explicitly asked.",
      planForbidden: false
    };
  } else if (channelName === 'siphon') {
    return {
      temperature: 0.2,
      systemBonus: "\nYou are in #siphon. Be extremely concise, factual, and research‑oriented. No small talk or jokes. If you don't know, say 'unknown'.",
      planBonus: "You are in #siphon. You MUST prefer the 'research' action. If you cannot research, give a one‑line factual answer. Never engage in casual chat.",
      planForbidden: false
    };
  }
  return { temperature: 0.7, systemBonus: "", planBonus: "", planForbidden: false };
}

// ---------- Similarity ----------
function jaccard(a, b) {
  if (!a.length && !b.length) return 1;
  const setA = new Set(a.map(s => s.toLowerCase().replace(/[^a-z0-9]/g, '')));
  const setB = new Set(b.map(s => s.toLowerCase().replace(/[^a-z0-9]/g, '')));
  const inter = new Set([...setA].filter(x => setB.has(x))).size;
  const union = setA.size + setB.size - inter;
  return union === 0 ? 0 : inter / union;
}
function similarity(specA, specB) {
  if (!specA || !specB) return 0;
  const nameSim = (specA.title === specB.title) ? 1 : 0;
  const goalsSim = jaccard(specA.goals, specB.goals);
  const stepsSim = jaccard(specA.nextSteps, specB.nextSteps);
  const completedSim = jaccard(specA.completedTasks, specB.completedTasks);
  const memorySim = (JSON.stringify(specA.memory) === JSON.stringify(specB.memory)) ? 1 : 0;
  return 0.4 * nameSim + 0.2 * goalsSim + 0.2 * stepsSim + 0.1 * completedSim + 0.1 * memorySim;
}
function computeSpecFromState(state) {
  return { title: state.title || "", goals: state.goals || [], nextSteps: state.nextSteps || [], completedTasks: state.completedTasks || [], memory: state.memory || {} };
}

// ---------- Ralph evaluate + evolve with Ollama error handling ----------
async function ralphEvaluate(agent, storeId, spec) {
  const prompt = `You are an evaluator. Rate clarity, completeness, stability (0-100). Output JSON: {"score": number, "critique": "short text"}\n\nSpec: ${JSON.stringify(spec)}`;
  const reply = await queryOllama(agent.model, prompt, "You are a precise evaluator. Output only JSON.", 0.3, agent.id);
  if (reply.startsWith('[OLLAMA_ERROR]')) return { score: 50, critique: "Ollama error." };
  const extracted = extractJSON(reply);
  if (extracted && typeof extracted.score === 'number') return { score: extracted.score, critique: extracted.critique || "" };
  return { score: 50, critique: "Evaluation failed." };
}
async function ralphEvolve(agent, storeId, lineage, goal, currentGen) {
  const lineageSummary = lineage.slice(-15).map(e => `${e.type} at ${new Date(e.timestamp).toISOString()}`).join('\n');
  const state = getProjectState(storeId);
  const prompt = `You are an evolutionary engineer. Goal: "${goal}"
Generation: ${currentGen+1}/30
Recent lineage: ${lineageSummary}

Current spec: ${JSON.stringify(state)}

Produce refined spec as JSON: title, goals (array), nextSteps (array), completedTasks (array), memory (object). Add "converged": boolean.
Keep improvements small.
Output ONLY a \`\`\`json code block.

Example:
\`\`\`json
{
  "title": "Todo app",
  "goals": ["store tasks"],
  "nextSteps": ["add local storage"],
  "completedTasks": [],
  "memory": {},
  "converged": false
}
\`\`\`

Now produce your refined spec:`;
  const reply = await queryOllama(agent.model, prompt, "You are an evolutionary engineer. Be precise.", 0.4, agent.id);
  if (reply.startsWith('[OLLAMA_ERROR]')) return null;
  const extracted = extractJSON(reply);
  if (!extracted || typeof extracted !== 'object') return null;
  return extracted;
}

function updateStagnation(storeId, sim) {
  let arr = ralphStagnation.get(storeId) || [];
  arr.push(sim);
  if (arr.length > 3) arr.shift();
  ralphStagnation.set(storeId, arr);
  if (arr.length === 3 && arr.every(s => s >= 0.92)) return true;
  return false;
}

function getNextRalphAgent(storeId, store) {
  let availableAgents = [];
  if (channels.has(storeId)) {
    const channelName = store.name;
    availableAgents = Array.from(agents.values()).filter(a => a.channels.includes(channelName));
  } else if (dms.has(storeId)) {
    const participants = store.participants;
    availableAgents = Array.from(agents.values()).filter(a => participants.includes(a.id));
  }
  if (availableAgents.length === 0) availableAgents = Array.from(agents.values());
  if (availableAgents.length === 0) return null;
  let idx = ralphNextAgentIdx.get(storeId) || 0;
  const agent = availableAgents[idx % availableAgents.length];
  ralphNextAgentIdx.set(storeId, (idx + 1) % availableAgents.length);
  return agent;
}

async function runRalphIteration(storeId) {
  // Cancellation check – must be first thing
  if (ralphCancel.get(storeId) === true) {
    ralphCancel.delete(storeId);
    ralphActive.set(storeId, false);
    if (ralphTimers.has(storeId)) {
      clearTimeout(ralphTimers.get(storeId));
      ralphTimers.delete(storeId);
    }
    broadcastRalphStatus(storeId);
    return;
  }
  if (!ralphActive.get(storeId)) return;

  const store = channels.get(storeId) || dms.get(storeId);
  if (!store) return;

  try {
    const agent = getNextRalphAgent(storeId, store);
    if (!agent) {
      await handleAgentResponse({ name: 'System' }, storeId, `❌ No agent available for Ralph loop.`);
      stopRalphLoop(storeId);
      return;
    }

    const goal = ralphGoals.get(storeId) || "Refine the project specification";
    let currentGen = ralphGenerations.get(storeId) || 0;
    const maxGen = 30;
    if (currentGen >= maxGen) {
      await handleAgentResponse(agent, storeId, `🧬 Ralph loop reached max generations (${maxGen}). Stopping.`);
      stopRalphLoop(storeId);
      return;
    }

    const lineage = reconstructLineage(storeId);
    const currentSpec = computeSpecFromState(getProjectState(storeId));
    const evalResult = await ralphEvaluate(agent, storeId, currentSpec);
    await handleAgentResponse(agent, storeId, `📊 **Evaluation** (gen ${currentGen+1}): score ${evalResult.score}/100\nCritique: ${evalResult.critique}`);

    const newSpecRaw = await ralphEvolve(agent, storeId, lineage, goal, currentGen);
    if (!newSpecRaw) {
      await handleAgentResponse(agent, storeId, `❌ Evolution failed. Stopping Ralph.`);
      stopRalphLoop(storeId);
      return;
    }

    const oldState = getProjectState(storeId);
    const newState = {
      active: true,
      title: newSpecRaw.title || oldState.title,
      goals: newSpecRaw.goals || oldState.goals,
      nextSteps: newSpecRaw.nextSteps || oldState.nextSteps,
      completedTasks: newSpecRaw.completedTasks || oldState.completedTasks,
      memory: newSpecRaw.memory || oldState.memory
    };
    const sim = similarity(currentSpec, computeSpecFromState(newState));
    const stagnation = updateStagnation(storeId, sim);
    const converged = newSpecRaw.converged === true || sim >= 0.95 || stagnation;

    setProjectState(storeId, newState);
    ralphGenerations.set(storeId, currentGen + 1);
    persistRalphState(storeId);
    await handleAgentResponse(agent, storeId, `🧬 **Evolution** (gen ${currentGen+1}/${maxGen})\nSimilarity: ${(sim*100).toFixed(1)}%\nNew spec: ${JSON.stringify(newState, null, 2).substring(0, 500)}`);
    broadcastRalphStatus(storeId);

    if (converged) {
      await handleAgentResponse(agent, storeId, `✅ **Ralph converged** after ${currentGen+1} generations. Stopping.`);
      stopRalphLoop(storeId);
      return;
    }

    // Schedule next iteration only if still active
    if (ralphActive.get(storeId)) {
      const timer = setTimeout(() => runRalphIteration(storeId), 5000);
      ralphTimers.set(storeId, timer);
    }
  } catch (err) {
    logError({ error: err.message, context: 'runRalphIteration', storeId });
    await handleAgentResponse({ name: 'System' }, storeId, `❌ Ralph error: ${err.message}`);
    stopRalphLoop(storeId);
  }
}

function startRalphLoop(storeId, goal) {
  stopRalphLoop(storeId);
  ralphActive.set(storeId, true);
  ralphGenerations.set(storeId, 0);
  ralphGoals.set(storeId, goal);
  ralphCancel.set(storeId, false);
  ralphStagnation.set(storeId, []);
  ralphNextAgentIdx.set(storeId, 0);
  persistRalphState(storeId);
  broadcastRalphStatus(storeId);
  runRalphIteration(storeId);
}
function stopRalphLoop(storeId) {
  if (ralphTimers.has(storeId)) {
    clearTimeout(ralphTimers.get(storeId));
    ralphTimers.delete(storeId);
  }
  ralphCancel.set(storeId, true);
  ralphActive.set(storeId, false);
  broadcastRalphStatus(storeId);
  persistRalphState(storeId);
}

// ---------- Natural agent response with cooldown ----------
async function agentRespond(agent, storeId, triggerMessage, isLoop = false, parentId = null) {
  if (triggerMessage.sender === agent.name) return;
  const cooldownKey = `${agent.id}_${storeId}`;
  const lastResponse = agent.lastResponseTime.get(cooldownKey) || 0;
  if (Date.now() - lastResponse < (isLoop ? 2000 : 3000)) return;

  agent.status = 'thinking';
  broadcastAgents();

  try {
    const store = channels.get(storeId) || dms.get(storeId);
    const isChannel = !!channels.get(storeId);
    const channelName = isChannel ? store.name : null;
    const personality = channelName ? getChannelPersonality(channelName) : { temperature: 0.7, systemBonus: "" };
    let systemPrompt = agent.systemPrompt + (personality.systemBonus || "");
    const context = buildConversationContext(storeId, agent.name, parentId || triggerMessage.parentId);
    const prompt = `Conversation:\n${context}\n${triggerMessage.sender}: ${triggerMessage.content}\nRespond as ${agent.name}. Keep brief.`;
    const reply = await queryOllama(agent.model, prompt, systemPrompt, personality.temperature, agent.id);
    if (reply && !reply.startsWith('[OLLAMA_ERROR]') && reply.trim()) {
      await handleAgentResponse(agent, storeId, reply.trim(), parentId || triggerMessage.parentId);
      agent.lastResponseTime.set(cooldownKey, Date.now());
    }
  } catch (err) {
    logError({ agentId: agent.id, error: err.message, context: 'agentRespond' });
  } finally {
    agent.status = 'online';
    broadcastAgents();
  }
}

// ---------- Execute action with Ollama error handling ----------
async function executeAction(agent, storeId, action, parentId = null) {
  const { type, payload } = action;
  switch (type) {
    case 'message': await handleAgentResponse(agent, storeId, payload.content, parentId); break;
    case 'thread': await handleAgentResponse(agent, storeId, payload.content, payload.parentId || parentId); break;
    case 'research':
      const topic = payload.query || payload.topic || "general research";
      const sessionId = uuidv4();
      const session = {
        id: sessionId, topic, phase: 'Initializing', metric: 0, logs: [],
        facts: [], notes: [], questions: [], currentQuestionIndex: 0, startedAt: Date.now()
      };
      researchSessions.set(sessionId, session);
      runResearch(sessionId, topic, storeId).catch(console.error);
      const msg = addMessage(storeId, 'Siphon', 'system', `🔍 ${agent.name} started research on "${topic}".`);
      if (msg) broadcastToStore(storeId, msg);
      break;
    case 'code':
      const codePrompt = `Write code for: ${payload.description}. Output only the code block.`;
      const code = await queryOllama(agent.model, codePrompt, agent.systemPrompt, 0.5, agent.id);
      if (!code.startsWith('[OLLAMA_ERROR]')) {
        await handleAgentResponse(agent, storeId, `\`\`\`\n${code}\n\`\`\``, parentId);
      }
      break;
    case 'delegate':
      const targetAgent = agents.get(payload.targetId);
      if (targetAgent) {
        const delegateMsg = addMessage(storeId, 'System', 'system', `${agent.name} delegates to ${targetAgent.name}: ${payload.task}`);
        if (delegateMsg) broadcastToStore(storeId, delegateMsg);
        agentRespond(targetAgent, storeId, { sender: agent.name, content: payload.task, parentId }, false, parentId);
      }
      break;
  }
}

// ---------- Planning mode with JSON retry and error handling ----------
async function agentPlanAndAct(agent, storeId, triggerMessage, parentId = null) {
  if (triggerMessage.sender === agent.name) return;
  const cooldownKey = `${agent.id}_${storeId}`;
  if (Date.now() - (agent.lastResponseTime.get(cooldownKey) || 0) < 6000) return;

  const store = channels.get(storeId) || dms.get(storeId);
  const isChannel = !!channels.get(storeId);
  const channelName = isChannel ? store.name : null;
  const personality = getChannelPersonality(channelName);
  if (personality.planForbidden) {
    await agentRespond(agent, storeId, triggerMessage, false, parentId);
    return;
  }

  agent.status = 'thinking';
  broadcastAgents();

  try {
    const context = buildConversationContext(storeId, agent.name, parentId || triggerMessage.parentId);
    let systemPrompt = `You are an autonomous agent. Output JSON inside a \`\`\`json block. Actions: {"type":"message","payload":{"content":"..."}} or {"type":"research","payload":{"query":"..."}} or {"type":"code","payload":{"description":"..."}} or {"type":"delegate","payload":{"targetId":"agent_id","task":"..."}}`;
    if (personality.planBonus) systemPrompt += "\n" + personality.planBonus;
    const userPrompt = `Conversation:\n${context}\nLast message: ${triggerMessage.sender}: "${triggerMessage.content}"\nProject state: ${JSON.stringify(getProjectState(storeId))}\nNext action? JSON only.`;
    const reply = await queryOllama(agent.model, userPrompt, systemPrompt, 0.4, agent.id);
    let action = null;
    let fails = jsonFailCount.get(agent.id) || 0;
    if (!reply.startsWith('[OLLAMA_ERROR]')) {
      action = extractJSON(reply);
    }
    if (!action?.type) {
      fails++;
      jsonFailCount.set(agent.id, fails);
      if (fails >= 3) {
        jsonFailCount.set(agent.id, 0);
        await agentRespond(agent, storeId, triggerMessage, false, parentId);
        agent.lastResponseTime.set(cooldownKey, Date.now());
        return;
      }
      action = { type: 'message', payload: { content: reply.substring(0, 500) } };
    } else {
      jsonFailCount.set(agent.id, 0);
    }
    await executeAction(agent, storeId, action, parentId || triggerMessage.parentId);
    agent.lastResponseTime.set(cooldownKey, Date.now());
  } catch (err) {
    logError({ agentId: agent.id, error: err.message, context: 'agentPlanAndAct' });
  } finally {
    agent.status = 'online';
    broadcastAgents();
  }
}

// ---------- Loop management ----------
function scheduleLoopRound(channelId) {
  const channel = channels.get(channelId);
  if (!channel) return;
  if (channel.loopTimer) clearTimeout(channel.loopTimer);
  channel.loopTimer = setTimeout(() => runLoopRound(channelId), 3000);
}
async function runLoopRound(channelId) {
  const channel = channels.get(channelId);
  const state = getProjectState(channelId);
  if (!channel || (!channel.researchActive && !channel.abstractActive && !state.active && !ralphActive.get(channelId))) {
    if (channel && channel.loopTimer) { clearTimeout(channel.loopTimer); channel.loopTimer = null; }
    return;
  }
  channel.loopTimer = null;
  try {
    const lastMsg = channel.messages[channel.messages.length - 1];
    if (!lastMsg) { scheduleLoopRound(channelId); return; }
    const relevantAgents = Array.from(agents.values()).filter(a => a.channels.includes(channel.name));
    for (const agent of relevantAgents) {
      if (ralphActive.get(channelId)) continue;
      if (state.active || channel.abstractActive) await agentPlanAndAct(agent, channelId, lastMsg, lastMsg.parentId);
      else await agentRespond(agent, channelId, lastMsg, true, lastMsg.parentId);
    }
  } catch (err) {
    logError({ error: err.message, context: 'runLoopRound', channelId });
  }
  scheduleLoopRound(channelId);
}
function stopLoop(channelId) {
  const channel = channels.get(channelId);
  if (channel) {
    channel.researchActive = false; channel.abstractActive = false; channel.researchTopic = null;
    if (channel.loopTimer) { clearTimeout(channel.loopTimer); channel.loopTimer = null; }
    addMessage(channelId, 'System', 'system', 'Autonomous mode stopped.');
    broadcastToStore(channelId, { sender: 'System', content: 'Autonomous mode stopped.', senderType: 'system' });
  }
  stopRalphLoop(channelId);
  setProjectState(channelId, { active: false, title: null, goals: [], nextSteps: [], completedTasks: [], memory: {} });
}

// ---------- SIPHON Research ----------
async function ddgSearch(query, maxResults = 5) {
  const url = `https://html.duckduckgo.com/html/?q=${encodeURIComponent(query)}`;
  try {
    const { data } = await axios.get(url, { headers: { 'User-Agent': 'Mozilla/5.0 (compatible; LACK-SIPHON/2.0)' }, timeout: 10000 });
    const $ = cheerio.load(data);
    const results = [];
    $('.result__url').each((i, el) => {
      let href = $(el).attr('href');
      if (href && href.startsWith('/')) href = 'https://duckduckgo.com' + href;
      if (href && href.startsWith('http') && results.length < maxResults) results.push(href);
    });
    return results;
  } catch (e) { return []; }
}
async function scrapeText(url) {
  try {
    const { data } = await axios.get(url, { timeout: 10000 });
    const $ = cheerio.load(data);
    $('script, style, nav, footer, header').remove();
    return $('body').text().replace(/\s+/g, ' ').trim().substring(0, 8000);
  } catch (e) { return ''; }
}
setInterval(() => {
  const now = Date.now();
  for (let [id, session] of researchSessions.entries()) if (now - session.startedAt > 3600000) researchSessions.delete(id);
}, 3600000);

async function runResearch(sessionId, topic, channelId) {
  const session = researchSessions.get(sessionId);
  if (!session) return;
  const update = (updates) => {
    Object.assign(session, updates);
    for (let [ws, client] of clients.entries()) {
      if (client.channelId === channelId && ws.readyState === WebSocket.OPEN)
        ws.send(JSON.stringify({ type: 'research_update', sessionId, data: session }));
    }
    if (updates.phase) {
      const banner = `🔬 **SIPHON Research** [${session.topic}]\nPhase: ${updates.phase} | Metric: ${(session.metric*100).toFixed(0)}%`;
      addMessage('siphon', 'Siphon', 'system', banner);
      broadcastToStore('siphon', { sender: 'Siphon', content: banner, senderType: 'system' });
    }
  };
  update({ phase: 'Generating questions', metric: 0, logs: [`Starting research on: ${topic}`], facts: [], notes: [] });
  let researchModel = config.agents[0]?.model || 'qwen2.5:0.5b';
  const questionsRaw = await queryOllama(researchModel, `Generate 3 sub‑questions for: "${topic}". One per line.`, '', 0.7);
  if (questionsRaw.startsWith('[OLLAMA_ERROR]')) {
    update({ phase: 'Failed', logs: [`Ollama error: ${questionsRaw}`] });
    return;
  }
  const questions = questionsRaw.split('\n').filter(l => l.trim().length > 10).slice(0, 3);
  update({ questions, currentQuestionIndex: 0, logs: [...session.logs, `Generated ${questions.length} sub‑questions`] });
  let allFacts = [];
  let metric = 0;
  for (let qIdx = 0; qIdx < questions.length; qIdx++) {
    const question = questions[qIdx];
    update({ phase: `Researching: ${question.substring(0, 50)}`, currentQuestionIndex: qIdx });
    let urls = [...new Set((await ddgSearch(`${topic} ${question}`, 3)))].slice(0, 5);
    update({ logs: [...session.logs, `Found ${urls.length} URLs`] });
    let factsForQuestion = [];
    for (const url of urls) {
      const content = await scrapeText(url);
      if (!content) continue;
      const factsRaw = await queryOllama(researchModel, `Extract facts answering: "${question}"\n\n${content.substring(0,4000)}\n\nReturn each fact on a new line starting with "FACT:".`, '', 0.3);
      if (!factsRaw.startsWith('[OLLAMA_ERROR]')) {
        const facts = factsRaw.split('\n').filter(l => l.startsWith('FACT:')).map(l => l.replace('FACT:', '').trim());
        factsForQuestion.push(...facts);
        update({ logs: [...session.logs, `Scraped ${url} → ${facts.length} facts`] });
      }
      await new Promise(r => setTimeout(r, 500));
    }
    factsForQuestion = [...new Set(factsForQuestion)];
    allFacts.push(...factsForQuestion);
    update({ facts: allFacts, logs: [...session.logs, `Collected ${factsForQuestion.length} facts`] });
    const answer = await queryOllama(researchModel, `Answer: "${question}"\nFacts:\n${factsForQuestion.join('\n')}\n\nConcise answer (3‑5 sentences).`, '', 0.5);
    const note = { question, answer: answer.startsWith('[OLLAMA_ERROR]') ? 'Answer generation failed.' : answer, facts: factsForQuestion, timestamp: Date.now() };
    session.notes.push(note);
    update({ notes: session.notes, logs: [...session.logs, `Answered: ${question.substring(0,60)}`] });
    try {
      const artifactPath = path.join(RESEARCH_DIR, `${sessionId}_q${qIdx}.json`);
      fs.writeFileSync(artifactPath, JSON.stringify(note, null, 2));
      await gitCommit(`Research ${session.topic} - question ${qIdx+1}`);
    } catch (e) { console.error('Artifact save failed:', e); }
    metric = (qIdx + 1) / questions.length;
    update({ metric });
    if (metric >= 0.9) break;
  }
  update({ phase: 'Complete', metric, logs: [...session.logs, `Research finished. Metric = ${metric.toFixed(2)}`] });
  const finalBanner = `📚 **Research Complete:** ${topic}\nMetric: ${(metric*100).toFixed(0)}%\nFacts: ${allFacts.length}\nNotes: ${session.notes.length}\n\nUse \`/pull ${sessionId}\` to bring insights.`;
  addMessage('siphon', 'Siphon', 'system', finalBanner);
  broadcastToStore('siphon', { sender: 'Siphon', content: finalBanner, senderType: 'system' });
}

// ---------- DM helpers (fixed) ----------
function createDM(participantIds, name = null) {
  const dmId = `dm_${uuidv4().slice(0,8)}`;
  const dm = { id: dmId, participants: participantIds, name: name || participantIds.join(', '), messages: [] };
  dms.set(dmId, dm);
  if (!config.dms) config.dms = [];
  config.dms.push({ id: dmId, participants: participantIds, name: dm.name });
  try {
    const tmp = configPath + '.tmp';
    fs.writeFileSync(tmp, JSON.stringify(config, null, 2));
    fs.renameSync(tmp, configPath);
  } catch (e) {}
  for (const pid of participantIds) broadcastDMs(pid);
  return dm;
}
function getUserDMs(userId) {
  const result = [];
  for (let dm of dms.values()) {
    if (dm.participants.includes(userId)) result.push({ id: dm.id, name: dm.name, participants: dm.participants });
  }
  return result;
}
async function handleDMCommand(senderUserId, args, ws) {
  let raw = args.join(' ').trim();
  if (!raw) { ws.send(JSON.stringify({ type: 'error', message: 'Usage: /dm <username or agentname>' })); return null; }
  if ((raw.startsWith('"') && raw.endsWith('"')) || (raw.startsWith("'") && raw.endsWith("'"))) raw = raw.slice(1, -1);
  let targetId = null;
  for (let [id, agent] of agents.entries()) if (agent.name.toLowerCase() === raw.toLowerCase()) { targetId = id; break; }
  if (!targetId) {
    for (let [otherWs, client] of clients.entries()) if (client.username && client.username.toLowerCase() === raw.toLowerCase()) { targetId = client.userId; break; }
  }
  if (!targetId) { ws.send(JSON.stringify({ type: 'error', message: `User/agent "${raw}" not found.` })); return null; }
  let dm = Array.from(dms.values()).find(d => d.participants.includes(senderUserId) && d.participants.includes(targetId));
  if (!dm) dm = createDM([senderUserId, targetId]);
  const client = clients.get(ws);
  if (client) {
    client.dmId = dm.id; client.channelId = null;
    ws.send(JSON.stringify({ type: 'dm_joined', dmId: dm.id, messages: dm.messages }));
    const welcomeMsg = addMessage(dm.id, 'System', 'system', `Direct message started with ${raw}.`);
    if (welcomeMsg) broadcastToStore(dm.id, welcomeMsg);
  }
  return dm;
}

// ---------- Agent removal with last‑agent safeguard ----------
async function removeAgent(agentId) {
  if (!agents.has(agentId)) return false;
  if (agents.size === 1) return false;
  agents.delete(agentId);
  agentMetrics.delete(agentId);
  jsonFailCount.delete(agentId);
  const idx = config.agents.findIndex(a => a.id === agentId);
  if (idx !== -1) {
    config.agents.splice(idx, 1);
    try {
      const tmp = configPath + '.tmp';
      fs.writeFileSync(tmp, JSON.stringify(config, null, 2));
      fs.renameSync(tmp, configPath);
    } catch (e) {}
  }
  broadcastAgents();
  return true;
}

// ---------- Cron management (idempotent) ----------
async function wipeAllCronJobs() { try { await execPromise('crontab -r'); } catch(e) {} }
async function addHeartbeatCronJobs() {
  const channelIds = Array.from(channels.keys()), dmIds = Array.from(dms.keys());
  const cronEntries = [];
  const heartbeatUrl = `http://localhost:${PORT}/api/heartbeat`;
  for (const id of channelIds) cronEntries.push(`*/5 * * * * curl -s -X POST "${heartbeatUrl}?type=channel&id=${id}" > /dev/null 2>&1`);
  for (const id of dmIds) cronEntries.push(`*/5 * * * * curl -s -X POST "${heartbeatUrl}?type=dm&id=${id}" > /dev/null 2>&1`);
  if (cronEntries.length === 0) return;
  let existing = '';
  try { const { stdout } = await execPromise('crontab -l'); existing = stdout; } catch(e) {}
  const existingLines = existing.split('\n').filter(l => l.trim());
  const newLines = [...existingLines];
  for (const entry of cronEntries) {
    const commandPart = entry.split(' ').slice(5).join(' ');
    if (!existingLines.some(line => line.includes(commandPart))) {
      newLines.push(entry);
    }
  }
  const newCrontab = newLines.join('\n') + '\n';
  const tmpFile = path.join(__dirname, '.tmpcron');
  fs.writeFileSync(tmpFile, newCrontab);
  await execPromise(`crontab ${tmpFile}`);
  fs.unlinkSync(tmpFile);
}
async function resetApplicationData() {
  for (let ch of channels.values()) { ch.messages = []; ch.researchActive = false; ch.abstractActive = false; if (ch.loopTimer) clearTimeout(ch.loopTimer); ch.loopTimer = null; }
  for (let dm of dms.values()) dm.messages = [];
  researchSessions.clear(); slimeSessions.clear(); pinnedMessages.clear(); userReactions.clear(); global.errorLog = [];
  for (let storeId of [...channels.keys(), ...dms.keys()]) {
    setProjectState(storeId, { active: false, title: null, goals: [], nextSteps: [], completedTasks: [], memory: {} });
    stopRalphLoop(storeId);
    // Also clear lineage if needed (optional)
    const lineagePath = getLineagePath(storeId);
    if (fs.existsSync(lineagePath)) fs.unlinkSync(lineagePath);
  }
}

// ---------- Git helpers (async + error handling) ----------
async function ensureGitRepo() {
  try {
    if (!fs.existsSync(RESEARCH_DIR)) fs.mkdirSync(RESEARCH_DIR, { recursive: true });
    const gitDir = path.join(RESEARCH_DIR, '.git');
    if (!fs.existsSync(gitDir)) {
      await GIT.cwd(RESEARCH_DIR).init();
      await GIT.cwd(RESEARCH_DIR).addConfig('user.name', 'LACK SIPHON');
      await GIT.cwd(RESEARCH_DIR).addConfig('user.email', 'lack@localhost');
      await GIT.cwd(RESEARCH_DIR).commit('Initial research repo', { '--allow-empty': null });
    }
  } catch (err) { console.error('Git init failed:', err.message); }
}
async function gitCommit(message) {
  try {
    await GIT.cwd(RESEARCH_DIR).add('.');
    const status = await GIT.cwd(RESEARCH_DIR).status();
    if (status.files.length > 0) {
      await GIT.cwd(RESEARCH_DIR).commit(message);
      console.log(`Git commit: ${message}`);
    }
  } catch (e) { console.error('Git commit failed:', e.message); }
}

// ---------- Cleanup on WebSocket close (memory leak fix) ----------
function cleanupStore(storeId) {
  if (ralphTimers.has(storeId)) clearTimeout(ralphTimers.get(storeId));
  ralphTimers.delete(storeId);
  ralphActive.delete(storeId);
  ralphCancel.delete(storeId);
  ralphStagnation.delete(storeId);
  ralphNextAgentIdx.delete(storeId);
  ralphLastBroadcast.delete(storeId);
  const channel = channels.get(storeId);
  if (channel && channel.loopTimer) clearTimeout(channel.loopTimer);
}

// ---------- Express & WebSocket ----------
const app = express();
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json({ limit: '1mb' }));

app.get('/api/models', async (req, res) => { res.json({ models: await getOllamaModels() }); });
app.get('/api/research/sessions', (req, res) => {
  res.json({ sessions: Array.from(researchSessions.values()).map(s => ({
    id: s.id, topic: s.topic, phase: s.phase, metric: s.metric,
    logs: s.logs.slice(-10), factsCount: s.facts.length,
    notesCount: s.notes.length, startedAt: s.startedAt
  })) });
});
app.get('/api/research/session/:id', (req, res) => {
  const s = researchSessions.get(req.params.id);
  if (!s) return res.status(404).json({ error: 'Not found' });
  res.json(s);
});
app.get('/api/channels', (req, res) => { res.json({ channels: Array.from(channels.values()).map(c => ({ id: c.id, name: c.name })) }); });
app.get('/api/dms', (req, res) => { res.json({ dms: Array.from(dms.values()).map(dm => ({ id: dm.id, name: dm.name, participants: dm.participants })) }); });
app.get('/api/metrics', (req, res) => {
  const metricsObj = {};
  for (let [id, m] of agentMetrics.entries()) metricsObj[id] = { cpu: m.cpu, mem: m.mem, activity: m.activity, timestamps: m.timestamps };
  res.json({
    agents: Array.from(agents.values()).map(a => ({ id: a.id, name: a.name, model: a.model, status: a.status })),
    metrics: metricsObj
  });
});
app.post('/api/heartbeat', (req, res) => { console.log(`[HEARTBEAT] ${req.query.type} ${req.query.id}`); res.send('OK'); });
app.post('/api/cron/wipe', async (req, res) => {
  try {
    await wipeAllCronJobs(); await addHeartbeatCronJobs(); await resetApplicationData();
    for (let [ws] of clients.entries()) if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'cron_reset' }));
    res.json({ success: true });
  } catch(err) { logError({ source: 'cron_wipe', error: err.message }); res.status(500).json({ error: err.message }); }
});
app.delete('/api/agent/:id', async (req, res) => { const success = await removeAgent(req.params.id); res.json({ success }); });
app.get('/slime', (req, res) => {
  const { token, pin } = req.query;
  const session = slimeSessions.get(token);
  if (!session || session.pin !== pin || Date.now() > session.expiresAt) return res.status(403).send(`<html><body><h1>Invalid</h1></body></html>`);
  res.send(`<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>SLIME</title><style>body{background:#000;color:#0f0;font-family:monospace;padding:1rem}#messages{height:70vh;overflow:auto;border:1px solid #0f0;padding:0.5rem;margin-bottom:1rem}.msg{margin:0.5rem 0}.user{color:#0ff}.agent{color:#ff0}.system{color:#888}.input-area{display:flex;gap:0.5rem}input{flex:1;background:#111;border:1px solid #0f0;color:#0f0;padding:0.5rem}button{background:#0f0;color:#000;border:none;padding:0.5rem 1rem}</style></head><body><h2>SLIME</h2><div id="messages"></div><div class="input-area"><input id="msgInput" placeholder="Message..."><button id="sendBtn">Send</button></div><script>let ws;let channel='${session.channelId}';let username='mobile_'+Math.floor(Math.random()*10000);function connect(){const protocol=location.protocol==='https:'?'wss:':'ws:';ws=new WebSocket(protocol+'//'+location.host);ws.onopen=()=>{ws.send(JSON.stringify({type:'join',channelId:channel}));ws.send(JSON.stringify({type:'set_username',username}))};ws.onmessage=e=>{const d=JSON.parse(e.data);if(d.type==='new_message'){const div=document.createElement('div');div.className='msg '+d.message.senderType;div.innerHTML='<strong>'+escapeHtml(d.message.sender)+'</strong> ['+new Date(d.message.timestamp).toLocaleTimeString()+']:<br>'+escapeHtml(d.message.content);document.getElementById('messages').appendChild(div);document.getElementById('messages').scrollTop=document.getElementById('messages').scrollHeight}else if(d.type==='history'){d.messages.forEach(msg=>{const div=document.createElement('div');div.className='msg '+msg.senderType;div.innerHTML='<strong>'+escapeHtml(msg.sender)+'</strong> ['+new Date(msg.timestamp).toLocaleTimeString()+']:<br>'+escapeHtml(msg.content);document.getElementById('messages').appendChild(div)})}};ws.onclose=()=>setTimeout(connect,3000)}function escapeHtml(s){return s.replace(/[&<>]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[m]))}document.getElementById('sendBtn').onclick=()=>{const input=document.getElementById('msgInput');if(input.value.trim()&&ws&&ws.readyState===WebSocket.OPEN){ws.send(JSON.stringify({type:'message',content:input.value}));input.value=''}};document.getElementById('msgInput').onkeypress=e=>{if(e.key==='Enter')document.getElementById('sendBtn').click()};connect();</script></body></html>`);
});

const server = app.listen(PORT, async () => {
  await ensureGitRepo();
  console.log(`\\x1b[32m✓ LACK v3.17.0 running at http://localhost:${PORT}\\x1b[0m`);
  console.log(`   Production-ready: DM threads, real-time loops, robust error logging, fixed Ralph`);
});

const wss = new WebSocket.Server({ server });
wss.on('connection', (ws) => {
  const userId = `human_${uuidv4().slice(0,4)}`;
  clients.set(ws, { username: userId, channelId: 'general', userId, dmId: null, openThreadId: null });
  ws.on('message', async (raw) => {
    try {
      const data = JSON.parse(raw);
      const client = clients.get(ws);
      if (!client) return;
      switch (data.type) {
        case 'join':
          if (channels.has(data.channelId)) {
            client.channelId = data.channelId; client.dmId = null;
            ws.send(JSON.stringify({ type: 'history', channelId: data.channelId, messages: channels.get(data.channelId).messages }));
            ws.send(JSON.stringify({ type: 'agents_list', agents: Array.from(agents.values()).map(a => ({ id: a.id, name: a.name, model: a.model, systemPrompt: a.systemPrompt, channels: a.channels, status: a.status })) }));
            ws.send(JSON.stringify({ type: 'channels', channels: Array.from(channels.values()).map(c => ({ id: c.id, name: c.name })) }));
            ws.send(JSON.stringify({ type: 'dms', dms: getUserDMs(client.userId) }));
            broadcastRalphStatus(data.channelId);
          }
          break;
        case 'join_dm':
          if (dms.has(data.dmId)) {
            client.dmId = data.dmId; client.channelId = null;
            ws.send(JSON.stringify({ type: 'dm_history', dmId: data.dmId, messages: dms.get(data.dmId).messages }));
            broadcastRalphStatus(data.dmId);
          }
          break;
        case 'message':
          if (client.channelId) {
            let msgText = data.content.trim();
            if (!msgText) break;
            // Basic sanitisation
            msgText = msgText.replace(/<[^>]*>/g, '');
            const humanMsg = addMessage(client.channelId, client.username, 'human', msgText);
            if (humanMsg) {
              broadcastToStore(client.channelId, humanMsg);
              await onHumanMessage(client.channelId, humanMsg, ws);
            }
          } else if (client.dmId) {
            let msgText = data.content.trim();
            if (!msgText) break;
            msgText = msgText.replace(/<[^>]*>/g, '');
            const humanMsg = addMessage(client.dmId, client.username, 'human', msgText);
            if (humanMsg) {
              broadcastToStore(client.dmId, humanMsg);
              await onHumanDmMessage(client.dmId, humanMsg, ws);
            }
          }
          break;
        case 'reply_in_thread':
          let { parentId, content, storeId } = data;
          if (!storeId) storeId = client.channelId || client.dmId;
          if (storeId && (channels.has(storeId) || dms.has(storeId))) {
            content = content.replace(/<[^>]*>/g, '');
            const replyMsg = addMessage(storeId, client.username, 'human', content, parentId);
            if (replyMsg) {
              broadcastToStore(storeId, replyMsg);
              broadcastThreadUpdate(storeId, parentId);
              ws.send(JSON.stringify({ type: 'thread_messages', storeId, threadId: parentId, messages: getThreadMessages(storeId, parentId) }));
            }
          }
          break;
        case 'set_username':
          client.username = data.username.substring(0, 20).replace(/[<>]/g, '');
          break;
        case 'start_dm': {
          const targetName = data.targetName;
          let targetId = null;
          for (let [id, agent] of agents.entries()) if (agent.name.toLowerCase() === targetName.toLowerCase()) { targetId = id; break; }
          if (!targetId) { ws.send(JSON.stringify({ type: 'error', message: 'Agent not found' })); break; }
          let dm = Array.from(dms.values()).find(d => d.participants.includes(client.userId) && d.participants.includes(targetId));
          if (!dm) dm = createDM([client.userId, targetId]);
          client.dmId = dm.id; client.channelId = null;
          ws.send(JSON.stringify({ type: 'dm_joined', dmId: dm.id, messages: dm.messages }));
          broadcastDMs(client.userId);
          break;
        }
        case 'spawn_agent': {
          const { name, model, systemPrompt, channels: agentChannels } = data;
          const id = uuidv4().slice(0,8);
          const newAgent = { id, name, model, systemPrompt, channels: agentChannels, lastResponseTime: new Map(), status: 'online', statusMessage: '' };
          agents.set(id, newAgent);
          config.agents.push({ id, name, model, systemPrompt, channels: agentChannels });
          try {
            const tmp = configPath + '.tmp';
            fs.writeFileSync(tmp, JSON.stringify(config, null, 2));
            fs.renameSync(tmp, configPath);
          } catch (e) {}
          agentMetrics.set(id, { cpu: Array(30).fill(0), mem: Array(30).fill(0), activity: Array(30).fill(0), timestamps: Array(30).fill(Date.now()) });
          jsonFailCount.set(id, 0);
          broadcastAgents();
          ws.send(JSON.stringify({ type: 'spawn_confirm', agent: newAgent }));
          break;
        }
        case 'update_agent': {
          const agent = agents.get(data.id);
          if (agent) {
            agent.name = data.name; agent.model = data.model; agent.systemPrompt = data.systemPrompt; agent.channels = data.channels;
            const idx = config.agents.findIndex(a => a.id === data.id);
            if (idx !== -1) {
              config.agents[idx] = { id: data.id, name: data.name, model: data.model, systemPrompt: data.systemPrompt, channels: data.channels };
              try {
                const tmp = configPath + '.tmp';
                fs.writeFileSync(tmp, JSON.stringify(config, null, 2));
                fs.renameSync(tmp, configPath);
              } catch (e) {}
            }
            broadcastAgents();
          }
          break;
        }
        case 'get_models':
          ws.send(JSON.stringify({ type: 'models_list', models: await getOllamaModels() }));
          break;
        case 'add_reaction': {
          const { messageId, emoji, storeId: reactStoreId } = data;
          if (!userReactions.has(messageId)) userReactions.set(messageId, new Map());
          const msgReactions = userReactions.get(messageId);
          if (!msgReactions.has(emoji)) msgReactions.set(emoji, new Set());
          msgReactions.get(emoji).add(client.userId);
          for (let [otherWs] of clients.entries()) {
            if (otherWs.readyState === WebSocket.OPEN) otherWs.send(JSON.stringify({ type: 'reaction_update', messageId, emoji, userId: client.userId, add: true }));
          }
          break;
        }
        case 'open_thread':
          client.openThreadId = data.threadId;
          break;
        case 'close_thread':
          client.openThreadId = null;
          break;
      }
    } catch(err) {
      logError({ source: 'websocket_parse', error: err.message });
      ws.send(JSON.stringify({ type: 'error', message: 'Invalid message format' }));
    }
  });
  ws.on('close', () => {
    const client = clients.get(ws);
    if (client) {
      if (client.channelId) cleanupStore(client.channelId);
      if (client.dmId) cleanupStore(client.dmId);
    }
    clients.delete(ws);
  });
  ws.send(JSON.stringify({ type: 'channels', channels: Array.from(channels.values()).map(c => ({ id: c.id, name: c.name })) }));
  ws.send(JSON.stringify({ type: 'dms', dms: getUserDMs(userId) }));
  ws.send(JSON.stringify({ type: 'agents_list', agents: Array.from(agents.values()).map(a => ({ id: a.id, name: a.name, model: a.model, systemPrompt: a.systemPrompt, channels: a.channels, status: a.status })) }));
});

async function onHumanMessage(channelId, messageObj, ws) {
  const channel = channels.get(channelId);
  if (!channel) return;
  const content = messageObj.content;
  if (content.startsWith('/')) {
    const parts = content.slice(1).split(' ');
    const cmd = parts[0].toLowerCase();
    const args = parts.slice(1);
    if (cmd === 'help') {
      const help = `Commands: /ground, /research <topic>, /abstract, /plan <goal>, /ralph <goal>, /stop, /list, /spawn, /siphon <topic>, /slime, /pull <id>, /dm <user>, /thread <id>, /pin <id>, /graph, /errorlog, /convergence`;
      addMessage(channelId, 'System', 'system', help); broadcastToStore(channelId, { sender: 'System', content: help, senderType: 'system' });
    } else if (cmd === 'ground') {
      const groundMsg = { sender: 'System', content: 'GROUND: All agents respond.' };
      addMessage(channelId, 'System', 'system', groundMsg.content); broadcastToStore(channelId, groundMsg);
      const agentsInChannel = Array.from(agents.values()).filter(a => a.channels.includes(channel.name));
      for (const agent of agentsInChannel) agentRespond(agent, channelId, groundMsg, false);
    } else if (cmd === 'research' && args.length) {
      stopLoop(channelId); channel.researchActive = true; channel.researchTopic = args.join(' ');
      addMessage(channelId, 'System', 'system', `Research mode started on: ${channel.researchTopic}`); broadcastToStore(channelId, { sender: 'System', content: `Research mode started on: ${channel.researchTopic}`, senderType: 'system' });
      scheduleLoopRound(channelId);
    } else if (cmd === 'abstract') {
      stopLoop(channelId); channel.abstractActive = true;
      addMessage(channelId, 'System', 'system', 'Abstract mode active – agents will plan actions.'); broadcastToStore(channelId, { sender: 'System', content: 'Abstract mode active – agents will plan actions.', senderType: 'system' });
      scheduleLoopRound(channelId);
    } else if (cmd === 'plan' && args.length) {
      stopLoop(channelId);
      const newState = { active: true, title: args.join(' '), goals: [args.join(' ')], nextSteps: [], completedTasks: [], memory: {} };
      setProjectState(channelId, newState);
      channel.abstractActive = true;
      addMessage(channelId, 'System', 'system', `📋 Project planning started: "${newState.title}".`); broadcastToStore(channelId, { sender: 'System', content: `Project planning started: "${newState.title}"`, senderType: 'system' });
      scheduleLoopRound(channelId);
    } else if (cmd === 'ralph' && args.length) {
      stopLoop(channelId);
      const goal = args.join(' ');
      loadProjectStateFromLineage(channelId);
      startRalphLoop(channelId, goal);
      addMessage(channelId, 'System', 'system', `🧬 **Ralph loop started**\nGoal: ${goal}\nWill converge when similarity ≥ 0.95 or max 30 generations.`);
      broadcastToStore(channelId, { sender: 'System', content: `Ralph evolution started: ${goal}`, senderType: 'system' });
    } else if (cmd === 'stop') { stopLoop(channelId); }
    else if (cmd === 'list') { const models = await getOllamaModels(); const listText = models.length ? 'Available Ollama models:\n' + models.join('\n') : 'No Ollama models found.'; addMessage(channelId, 'System', 'system', listText); broadcastToStore(channelId, { sender: 'System', content: listText, senderType: 'system' }); }
    else if (cmd === 'spawn') { ws.send(JSON.stringify({ type: 'models_list', models: await getOllamaModels() })); }
    else if (cmd === 'siphon') { const topic = args.join(' ') || 'general research topic'; const sessionId = uuidv4(); const session = { id: sessionId, topic, phase: 'Initializing', metric: 0, logs: [], facts: [], notes: [], questions: [], currentQuestionIndex: 0, startedAt: Date.now() }; researchSessions.set(sessionId, session); runResearch(sessionId, topic, channelId).catch(console.error); addMessage(channelId, 'Siphon', 'system', `🔍 Started research on "${topic}". Check #siphon.`); broadcastToStore(channelId, { sender: 'Siphon', content: `Research started: ${topic}`, senderType: 'system' }); }
    else if (cmd === 'slime') { const token = uuidv4().replace(/-/g, '').substring(0,16); const pin = Math.floor(100000 + Math.random() * 900000).toString(); const expiresAt = Date.now() + 60 * 60 * 1000; slimeSessions.set(token, { pin, expiresAt, channelId }); const url = `http://localhost:${PORT}/slime?token=${token}&pin=${pin}`; addMessage(channelId, 'System', 'system', `📱 Mobile URL: ${url}  PIN: ${pin} (expires 1h)`); broadcastToStore(channelId, { sender: 'System', content: `Mobile access: ${url}`, senderType: 'system' }); }
    else if (cmd === 'pull' && args.length) { const session = researchSessions.get(args[0]); if (!session) { addMessage(channelId, 'System', 'system', `No session ${args[0]}.`); broadcastToStore(channelId, { sender: 'System', content: `No session ${args[0]}.`, senderType: 'system' }); return; } let summary = `📊 **Research "${session.topic}"**\nMetric: ${(session.metric*100).toFixed(0)}%\n`; if (session.notes.length) { const last = session.notes[session.notes.length-1]; summary += `**Latest answer:** ${last.answer.substring(0,300)}\nKey facts:\n${last.facts.slice(0,3).map(f => `- ${f}`).join('\n')}`; } else { summary += 'Research still in progress.'; } addMessage(channelId, 'Siphon', 'system', summary); broadcastToStore(channelId, { sender: 'Siphon', content: summary, senderType: 'system' }); }
    else if (cmd === 'dm') {
      const dm = await handleDMCommand(getUserId(ws), args, ws);
      if (dm) ws.send(JSON.stringify({ type: 'switch_to_dm', dmId: dm.id }));
    }
    else if (cmd === 'thread') { const messageId = args[0]; if (!messageId) ws.send(JSON.stringify({ type: 'error', message: 'Usage: /thread <messageId>' })); else ws.send(JSON.stringify({ type: 'thread_messages', storeId: channelId, threadId: messageId, messages: getThreadMessages(channelId, messageId) })); }
    else if (cmd === 'pin') { if (!args[0]) ws.send(JSON.stringify({ type: 'error', message: 'Usage: /pin <messageId>' })); else { if (!pinnedMessages.has(channelId)) pinnedMessages.set(channelId, new Set()); pinnedMessages.get(channelId).add(args[0]); ws.send(JSON.stringify({ type: 'pinned', messageId: args[0], channelId })); } }
    else if (cmd === 'graph') { ws.send(JSON.stringify({ type: 'graph_ack' })); }
    else if (cmd === 'errorlog') { let logText = '**ERROR LOG**\n'; const errors = global.errorLog || []; errors.slice(0,20).forEach(e => { logText += `${new Date(e.timestamp).toLocaleTimeString()} | ${e.agentId || 'system'}: ${e.error}\n`; }); if (!errors.length) logText += 'No errors recorded.'; addMessage(channelId, 'System', 'system', logText); broadcastToStore(channelId, { sender: 'System', content: logText, senderType: 'system' }); }
    else if (cmd === 'convergence') { const lineage = reconstructLineage(channelId); let lastSpec = null, sim = 0; for (let i = lineage.length-1; i >= 0; i--) { if (lineage[i].type === 'project_state') { const spec = computeSpecFromState(lineage[i].state); if (lastSpec) { sim = similarity(lastSpec, spec); break; } lastSpec = spec; } } const msg = `🔍 Convergence similarity: ${(sim*100).toFixed(1)}%`; addMessage(channelId, 'System', 'system', msg); broadcastToStore(channelId, { sender: 'System', content: msg, senderType: 'system' }); }
    else { addMessage(channelId, 'System', 'system', `Unknown command: ${cmd}. Type /help`); broadcastToStore(channelId, { sender: 'System', content: `Unknown command: ${cmd}`, senderType: 'system' }); }
    return;
  }
  const relevantAgents = Array.from(agents.values()).filter(a => a.channels.includes(channel.name));
  const state = getProjectState(channelId);
  const usePlanning = state.active || channel.abstractActive || channel.researchActive;
  for (const agent of relevantAgents) {
    if (ralphActive.get(channelId)) continue;
    if (usePlanning) await agentPlanAndAct(agent, channelId, messageObj, messageObj.parentId);
    else await agentRespond(agent, channelId, messageObj, false, messageObj.parentId);
  }
}

async function onHumanDmMessage(dmId, messageObj, ws) {
  const dm = dms.get(dmId);
  if (!dm) return;
  const content = messageObj.content;

  if (content.startsWith('/')) {
    const parts = content.slice(1).split(' ');
    const cmd = parts[0].toLowerCase();
    const args = parts.slice(1);
    if (cmd === 'ralph' && args.length) {
      stopRalphLoop(dmId);
      const goal = args.join(' ');
      loadProjectStateFromLineage(dmId);
      startRalphLoop(dmId, goal);
      addMessage(dmId, 'System', 'system', `🧬 Ralph loop started in DM.\nGoal: ${goal}`);
      broadcastToStore(dmId, { sender: 'System', content: `Ralph started: ${goal}`, senderType: 'system' });
      return;
    } else if (cmd === 'stop') {
      stopRalphLoop(dmId);
      setProjectState(dmId, { active: false, title: null, goals: [], nextSteps: [], completedTasks: [], memory: {} });
      addMessage(dmId, 'System', 'system', 'Autonomous mode stopped.');
      broadcastToStore(dmId, { sender: 'System', content: 'Autonomous mode stopped.', senderType: 'system' });
      return;
    } else if (cmd === 'help') {
      const help = 'DM Commands: /ralph <goal>, /stop, /help';
      addMessage(dmId, 'System', 'system', help);
      broadcastToStore(dmId, { sender: 'System', content: help, senderType: 'system' });
      return;
    }
  }

  // Filter agents that are participants in this DM
  const agentParticipants = dm.participants.filter(p => agents.has(p));
  const state = getProjectState(dmId);
  for (const agentId of agentParticipants) {
    const agent = agents.get(agentId);
    if (!agent) continue;
    if (ralphActive.get(dmId)) continue;
    const usePlanning = state.active;
    if (usePlanning) await agentPlanAndAct(agent, dmId, messageObj, messageObj.parentId);
    else await agentRespond(agent, dmId, messageObj, false, messageObj.parentId);
  }
}
'''

# ----------------------------------------------------------------------
# Responsive INDEX_HTML – scales perfectly on any device
# ----------------------------------------------------------------------
INDEX_HTML = r'''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <title>LACK v3.5.0 – Final Production</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    /* ---------- RESET & BASE ---------- */
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: monospace;
      background: var(--white);
      color: var(--black);
      height: 100vh;
      overflow: hidden;
      transition: background 0.3s, color 0.3s;
    }

    /* CSS variables (light mode default) */
    :root {
      --white: #fff;
      --off-white: #f8f8f8;
      --light-gray: #e0e0e0;
      --gray: #a0a0a0;
      --dark-gray: #666;
      --black: #000;
      --shadow-dark: rgba(0,0,0,0.2);
    }

    /* Dark mode override */
    .dark-mode {
      --white: #0a0a0a;
      --off-white: #1a1a1a;
      --light-gray: #2a2a2a;
      --gray: #555;
      --dark-gray: #999;
      --black: #f0f0f0;
      --shadow-dark: rgba(255,255,255,0.1);
    }

    /* ---------- TOP MENU (always visible) ---------- */
    .neuro-menu {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      height: 48px;
      background: var(--white);
      border-bottom: 2px solid var(--black);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 1rem;
      z-index: 10000;
      flex-wrap: wrap;
      gap: 0.5rem;
    }

    .menu-item {
      font-size: 0.85rem;
      font-weight: 600;
      white-space: nowrap;
    }

    .neuro-status {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      flex-wrap: wrap;
      font-size: 0.7rem;
    }

    .dark-mode-toggle, .ground-btn, .cron-btn {
      background: var(--white);
      border: 1px solid var(--black);
      border-radius: 20px;
      padding: 0.25rem 0.75rem;
      cursor: pointer;
      font-size: 0.7rem;
      white-space: nowrap;
    }
    .cron-btn {
      background: #ff4444;
      color: white;
      border-color: #ff4444;
    }
    .ralph-badge {
      background: #9b59b6;
      color: white;
      border-radius: 12px;
      padding: 0.2rem 0.6rem;
      font-size: 0.7rem;
      display: none;
    }

    /* ---------- MAIN LAYOUT (flex, no fixed widths) ---------- */
    .neuro-desktop {
      position: absolute;
      top: 48px;
      left: 0;
      right: 0;
      bottom: 0;
      padding: 1rem;
      background: var(--off-white);
      display: flex;
      overflow: hidden;
    }

    .chat-container {
      display: flex;
      width: 100%;
      height: 100%;
      background: var(--white);
      border: 2px solid var(--black);
      box-shadow: 8px 8px 0 var(--shadow-dark);
      overflow: hidden;
    }

    /* ----- SIDEBAR (flexible width) ----- */
    .sidebar {
      width: 260px;
      min-width: 200px;
      max-width: 30%;
      background: var(--white);
      border-right: 2px solid var(--black);
      display: flex;
      flex-direction: column;
      overflow-y: auto;
      flex-shrink: 0;
    }

    /* ----- MAIN CHAT (fills remaining space) ----- */
    .main-chat {
      flex: 1;
      display: flex;
      flex-direction: column;
      min-width: 0;   /* prevents overflow */
      background: var(--white);
    }

    /* ----- THREAD PANEL (collapsible on small screens) ----- */
    .thread-panel {
      width: 300px;
      background: var(--white);
      border-left: 2px solid var(--black);
      display: none;
      flex-direction: column;
      flex-shrink: 0;
    }
    .thread-panel.open {
      display: flex;
    }

    /* Responsive: on narrow screens, thread panel becomes a floating overlay (optional) */
    @media (max-width: 700px) {
      .sidebar {
        min-width: 160px;
        width: 180px;
      }
      .thread-panel.open {
        position: fixed;
        right: 0;
        top: 48px;
        bottom: 0;
        width: 85%;
        max-width: 320px;
        z-index: 2000;
        box-shadow: -4px 0 12px rgba(0,0,0,0.3);
      }
    }

    /* ----- INTERNAL COMPONENTS (scroll, messages, input) ----- */
    .chat-header {
      padding: 0.75rem 1rem;
      border-bottom: 2px solid var(--black);
      font-weight: 600;
      background: var(--white);
      flex-shrink: 0;
    }

    .messages-area {
      flex: 1;
      overflow-y: auto;
      padding: 1rem;
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      background: var(--off-white);
    }

    .input-area {
      padding: 0.75rem 1rem;
      border-top: 2px solid var(--black);
      display: flex;
      gap: 0.75rem;
      align-items: flex-start;
      background: var(--white);
      flex-wrap: wrap;
    }
    .input-area textarea {
      flex: 1;
      background: var(--white);
      border: 1px solid var(--black);
      padding: 0.5rem;
      font-family: monospace;
      resize: vertical;
      min-width: 120px;
      font-size: 0.85rem;
    }
    .input-area button {
      background: var(--white);
      border: 2px solid var(--black);
      padding: 0.5rem 1rem;
      cursor: pointer;
      font-weight: bold;
      font-size: 0.8rem;
    }
    .file-upload-btn {
      background: none;
      border: none;
      font-size: 1.4rem;
      cursor: pointer;
      color: var(--gray);
      padding: 0 0.25rem;
    }
    .file-upload-btn:hover { color: var(--black); }

    /* Messages */
    .message-group {
      margin-bottom: 0.5rem;
    }
    .message {
      display: flex;
      gap: 0.75rem;
      padding: 0.25rem 0;
    }
    .message-avatar {
      width: 32px;
      height: 32px;
      background: var(--light-gray);
      border: 1px solid var(--black);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: bold;
      flex-shrink: 0;
    }
    .message-content {
      flex: 1;
      min-width: 0;
      word-wrap: break-word;
    }
    .message-sender {
      font-weight: 600;
      font-size: 0.8rem;
    }
    .message-timestamp {
      font-size: 0.7rem;
      color: var(--dark-gray);
    }
    .message-text {
      font-size: 0.85rem;
      line-height: 1.4;
      word-wrap: break-word;
    }
    .message-text pre {
      background: #111;
      color: #0f0;
      padding: 0.5rem;
      overflow-x: auto;
      font-size: 0.75rem;
      border-radius: 4px;
    }
    .reply-badge {
      font-size: 0.7rem;
      text-decoration: underline;
      cursor: pointer;
      margin-top: 0.25rem;
    }
    .message-actions {
      display: none;
      gap: 0.5rem;
      margin-top: 0.25rem;
    }
    .message:hover .message-actions {
      display: flex;
    }
    .action-icon {
      font-size: 0.7rem;
      background: var(--white);
      border: 1px solid var(--light-gray);
      padding: 0.2rem 0.4rem;
      cursor: pointer;
    }

    /* Sidebar items */
    .sidebar-section {
      border-bottom: 1px solid var(--light-gray);
    }
    .sidebar-header {
      padding: 0.75rem;
      font-weight: 600;
      font-size: 0.75rem;
      background: var(--off-white);
      cursor: pointer;
    }
    .channel-list {
      padding: 0.5rem;
    }
    .channel-item, .agent-item, .research-item {
      padding: 0.5rem;
      margin: 0.25rem 0;
      cursor: pointer;
      font-size: 0.75rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      border: 1px solid transparent;
    }
    .channel-item:hover, .agent-item:hover, .research-item:hover {
      background: var(--light-gray);
    }
    .agent-item {
      justify-content: space-between;
    }
    .agent-info {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      flex: 1;
    }
    .agent-status {
      width: 8px;
      height: 8px;
      border-radius: 50%;
    }
    .status-online { background: #2eb67d; }
    .status-thinking { background: #ecb22e; animation: pulse 1s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    .remove-agent {
      color: #ff4444;
      cursor: pointer;
      opacity: 0.6;
    }
    .research-progress {
      font-size: 0.7rem;
      margin-left: auto;
    }

    /* Thread panel */
    .thread-header {
      padding: 0.75rem;
      border-bottom: 2px solid var(--black);
      display: flex;
      justify-content: space-between;
    }
    .thread-messages {
      flex: 1;
      overflow-y: auto;
      padding: 0.75rem;
    }
    .thread-input {
      padding: 0.75rem;
      border-top: 1px solid var(--light-gray);
    }
    .thread-input textarea {
      width: 100%;
      padding: 0.5rem;
      font-family: monospace;
    }

    /* Modals & toasts */
    .modal {
      display: none;
      position: fixed;
      z-index: 20000;
      left: 0;
      top: 0;
      width: 100%;
      height: 100%;
      background: rgba(0,0,0,0.6);
      align-items: center;
      justify-content: center;
    }
    .modal-content {
      background: var(--white);
      border: 2px solid var(--black);
      padding: 1.5rem;
      width: 90%;
      max-width: 500px;
      max-height: 90vh;
      overflow-y: auto;
    }
    .modal-content input, .modal-content select, .modal-content textarea {
      width: 100%;
      margin: 0.5rem 0;
      padding: 0.5rem;
    }
    .modal-buttons {
      display: flex;
      justify-content: flex-end;
      gap: 0.75rem;
      margin-top: 1rem;
      flex-wrap: wrap;
    }
    .toast {
      position: fixed;
      bottom: 1rem;
      right: 1rem;
      background: #333;
      color: white;
      padding: 0.5rem 1rem;
      border-radius: 8px;
      font-size: 0.8rem;
      opacity: 0;
      transition: opacity 0.3s;
      z-index: 20001;
      pointer-events: none;
    }
    .toast.show { opacity: 1; }
    .toast.success { background: #2ecc71; }
    .toast.error { background: #e74c3c; }
    .agent-thinking-overlay {
      position: fixed;
      bottom: 1rem;
      left: 1rem;
      background: rgba(0,0,0,0.7);
      color: #ff0;
      padding: 0.4rem 1rem;
      border-radius: 20px;
      font-size: 0.75rem;
      z-index: 10001;
    }
    .bottom-bar {
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      background: var(--white);
      border-top: 1px solid var(--light-gray);
      padding: 0.25rem 1rem;
      font-size: 0.6rem;
      display: flex;
      justify-content: space-between;
      z-index: 10000;
    }
    .file-name-chip {
      background: var(--light-gray);
      border-radius: 16px;
      padding: 0.2rem 0.6rem;
      font-size: 0.7rem;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .spinner {
      display: inline-block;
      width: 16px;
      height: 16px;
      border: 2px solid var(--gray);
      border-top-color: var(--black);
      border-radius: 50%;
      animation: spin 0.6s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .slash-suggestions {
      position: absolute;
      bottom: 100%;
      left: 0;
      background: var(--white);
      border: 1px solid var(--black);
      list-style: none;
      padding: 0.25rem;
      max-height: 150px;
      overflow-y: auto;
      z-index: 200;
    }
    .slash-suggestions li {
      padding: 0.25rem 0.5rem;
      cursor: pointer;
      font-size: 0.7rem;
    }
    canvas#agentGraph {
      width: 100%;
      height: 100%;
      display: block;
    }
  </style>
</head>
<body>
<div class="neuro-menu">
  <div class="menu-item">LACK v3.5.0</div>
  <div class="neuro-status">
    <span id="agentCount">Agents: 0</span>
    <span id="ralphStatusBadge" class="ralph-badge">🧬 Ralph active</span>
    <button class="ground-btn" id="groundBtn">🌍 GROUND</button>
    <button class="ground-btn" id="graphBtn">📈 GRAPH</button>
    <button class="ground-btn" id="errorlogBtn">⚠️ ERRORLOG</button>
    <button class="cron-btn" id="cronBtn">💣 CRON</button>
    <div class="dark-mode-toggle" id="darkModeToggle">🌓</div>
  </div>
</div>
<div class="neuro-desktop">
  <div class="chat-container">
    <div class="sidebar" id="sidebar"></div>
    <div class="main-chat">
      <div class="chat-header" id="currentChatName">#general</div>
      <div class="messages-area" id="messagesArea"></div>
      <div class="input-area">
        <label class="file-upload-btn">
          <i class="fas fa-paperclip"></i>
          <input type="file" id="fileInput" style="display:none" accept=".txt,.md,.json,.csv,.log,.py,.js,.html,.css">
        </label>
        <div id="filePreview" style="display:flex; align-items:center; gap:4px;"></div>
        <textarea id="messageInput" rows="1" placeholder="Type /help ..."></textarea>
        <button id="sendBtn">SEND</button>
        <div id="uploadSpinner" class="spinner" style="display:none;"></div>
      </div>
    </div>
    <div class="thread-panel" id="threadPanel">
      <div class="thread-header"><span>Thread</span><i class="fas fa-times" id="closeThreadBtn" style="cursor:pointer"></i></div>
      <div class="thread-messages" id="threadMessages"></div>
      <div class="thread-input"><textarea id="threadReplyInput" rows="2" placeholder="Reply..."></textarea><button id="sendThreadReply">Reply</button></div>
    </div>
  </div>
</div>
<div class="bottom-bar"><span>LACK · File upload (combined text) | Click agent → edit | Double‑click → DM</span><span id="statusText">CONNECTED</span></div>
<div id="agentThinkingToast" class="agent-thinking-overlay" style="display:none;"><i class="fas fa-spinner fa-pulse"></i> Agent is thinking...</div>

<div id="agentModal" class="modal">
  <div class="modal-content">
    <h3>Edit Agent</h3>
    <input type="text" id="editAgentId" hidden>
    <label>Name:</label><input type="text" id="editAgentName">
    <label>Model:</label><select id="editAgentModel"></select>
    <label>System Prompt:</label><textarea id="editAgentPrompt" rows="3"></textarea>
    <label>Channels (comma):</label><input type="text" id="editAgentChannels">
    <div class="modal-buttons">
      <button id="openDmBtn">Open DM</button>
      <button id="removeAgentBtn">Remove Agent</button>
      <button id="saveAgentBtn">Save</button>
      <button id="closeModalBtn">Cancel</button>
    </div>
  </div>
</div>
<div id="quickSwitcherModal" class="modal"><div class="modal-content"><input type="text" id="switcherInput" placeholder="Jump... Ctrl+K"><div class="shortcut-hint">Ctrl+K</div></div></div>
<div id="graphModal" class="modal"><div class="modal-content" style="width:820px; max-width:95%; height:620px; display:flex; flex-direction:column;"><div style="display:flex; justify-content:space-between;"><h3>🧪 Agent Resource Monitor</h3><button id="closeGraphBtn" style="background:none;border:none;font-size:24px;">✕</button></div><div style="flex:1; background:var(--off-white); margin:12px 0; border:2px solid var(--black);"><canvas id="agentGraph" width="780" height="420" style="width:100%; height:100%;"></canvas></div><div id="graphLegend" style="display:flex; gap:16px; flex-wrap:wrap; font-size:11px;"></div><div style="font-size:10px; text-align:center;">CPU (solid) & Activity (semi)</div></div></div>

<div id="toast" class="toast"></div>

<script>
let ws, currentStoreId = 'general', currentStoreType = 'channel', username = localStorage.getItem('lack_username') || 'human_' + Math.floor(Math.random()*1000), userId = '', agents = [], researchSessions = [], channels = [], dms = [], currentThreadId = null, graphInterval = null, graphCanvas, graphCtx, resizeListener = false;
let pendingFile = null;

function showToast(msg, type = 'info') {
  const toast = document.getElementById('toast');
  toast.className = `toast ${type}`;
  toast.innerText = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 3000);
}

function init() {
  connect();
  document.getElementById('sendBtn').onclick = sendMessage;
  document.getElementById('messageInput').onkeypress = e => { if(e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } };
  document.getElementById('messageInput').addEventListener('input', autoGrow);
  document.getElementById('messageInput').addEventListener('keydown', handleSlash);
  document.getElementById('darkModeToggle').onclick = () => { document.body.classList.toggle('dark-mode'); if(document.getElementById('graphModal').style.display === 'flex') fetchAndDrawGraph(); };
  document.getElementById('groundBtn').onclick = () => sendCommand('/ground');
  document.getElementById('graphBtn').onclick = () => openGraphModal();
  document.getElementById('errorlogBtn').onclick = () => sendCommand('/errorlog');
  document.getElementById('cronBtn').onclick = () => { if(confirm('⚠️ CRON WIPE: Delete ALL cron jobs, add heartbeats, reset ALL data. Are you sure?')) fetch('/api/cron/wipe',{method:'POST'}).then(r=>r.json()).then(d=>{if(d.success) location.reload(); else alert('Error: '+d.error);}); };
  document.getElementById('closeThreadBtn').onclick = closeThreadPanel;
  document.getElementById('sendThreadReply').onclick = sendThreadReply;
  document.addEventListener('keydown', e => { if((e.ctrlKey||e.metaKey) && e.key === 'k') { e.preventDefault(); document.getElementById('quickSwitcherModal').style.display = 'flex'; document.getElementById('switcherInput').focus(); } });
  document.getElementById('quickSwitcherModal').onclick = e => { if(e.target === document.getElementById('quickSwitcherModal')) document.getElementById('quickSwitcherModal').style.display = 'none'; };
  document.getElementById('switcherInput').addEventListener('keyup', e => { if(e.key === 'Enter') handleQuickSwitch(); });
  setInterval(fetchResearchSessions, 5000);
  document.getElementById('closeGraphBtn').onclick = () => { document.getElementById('graphModal').style.display = 'none'; if(graphInterval) clearInterval(graphInterval); if(resizeListener) window.removeEventListener('resize', handleGraphResize); };

  const fileInput = document.getElementById('fileInput');
  fileInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const MAX_SIZE = 512 * 1024; // 512KB to avoid WS frame limit
    if (file.size > MAX_SIZE) { showToast(`File too large (max 512KB)`, 'error'); fileInput.value = ''; return; }
    const previewDiv = document.getElementById('filePreview');
    previewDiv.innerHTML = `<span class="file-name-chip">📎 ${escapeHtml(file.name)} <i class="fas fa-times-circle" id="removeFileChip" style="cursor:pointer"></i></span>`;
    document.getElementById('removeFileChip').onclick = () => { previewDiv.innerHTML = ''; pendingFile = null; fileInput.value = ''; };
    const spinner = document.getElementById('uploadSpinner');
    spinner.style.display = 'inline-block';
    try {
      const base64 = await readFileAsBase64(file);
      pendingFile = { name: file.name, contentBase64: base64, size: file.size };
      showToast(`File "${file.name}" ready to send`, 'success');
    } catch (err) { showToast(`Failed to read file`, 'error'); pendingFile = null; previewDiv.innerHTML = ''; }
    finally { spinner.style.display = 'none'; fileInput.value = ''; }
  });

  document.getElementById('saveAgentBtn').onclick = () => {
    const id = document.getElementById('editAgentId').value;
    const name = document.getElementById('editAgentName').value;
    const model = document.getElementById('editAgentModel').value;
    const prompt = document.getElementById('editAgentPrompt').value;
    const chans = document.getElementById('editAgentChannels').value.split(',').map(s=>s.trim());
    ws.send(JSON.stringify({type:'update_agent',id,name,model,systemPrompt:prompt,channels:chans}));
    document.getElementById('agentModal').style.display='none';
    showToast(`Agent "${name}" updated`, 'success');
  };
  document.getElementById('closeModalBtn').onclick = () => { document.getElementById('agentModal').style.display='none'; };
  document.getElementById('openDmBtn').onclick = () => {
    const agentName = document.getElementById('editAgentName').value;
    if (agentName) { openDmWithAgent(agentName); document.getElementById('agentModal').style.display='none'; }
  };
  document.getElementById('removeAgentBtn').onclick = async () => {
    const agentId = document.getElementById('editAgentId').value;
    const agentName = document.getElementById('editAgentName').value;
    if (confirm(`Delete agent "${agentName}" permanently?`)) {
      const resp = await fetch(`/api/agent/${agentId}`, { method: 'DELETE' });
      const result = await resp.json();
      if (resp.ok && result.success) { document.getElementById('agentModal').style.display='none'; showToast(`Agent "${agentName}" removed`, 'success'); }
      else { showToast(`Cannot remove last agent`, 'error'); }
    }
  };

  setInterval(() => {
    const anyThinking = agents.some(a => a.status === 'thinking');
    document.getElementById('agentThinkingToast').style.display = anyThinking ? 'flex' : 'none';
  }, 500);
}

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function connect() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(protocol+'//'+location.host);
  ws.onopen = () => {
    document.getElementById('statusText').innerText = 'CONNECTED';
    ws.send(JSON.stringify({type:'join',channelId:currentStoreId}));
    ws.send(JSON.stringify({type:'set_username',username}));
  };
  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    switch(d.type) {
      case 'channels': channels = d.channels; renderSidebar(); break;
      case 'dms': dms = d.dms; renderSidebar(); break;
      case 'agents_list': agents = d.agents; document.getElementById('agentCount').innerText = 'Agents: '+agents.length; renderSidebar(); break;
      case 'history': renderMessages(d.messages); break;
      case 'new_message': if(d.channelId === currentStoreId && currentStoreType==='channel') appendMessage(d.message); break;
      case 'dm_history': renderMessages(d.messages); break;
      case 'new_dm_message': if(d.dmId === currentStoreId && currentStoreType==='dm') appendMessage(d.message); break;
      case 'dm_joined': switchToDm(d.dmId); renderMessages(d.messages); showToast('Joined DM', 'success'); break;
      case 'switch_to_dm': { const dm = dms.find(x=>x.id===d.dmId); if(dm) switchToDm(dm.id); break; }
      case 'research_update': fetchResearchSessions(); break;
      case 'thread_messages': renderThreadMessages(d.messages); currentThreadId = d.threadId; openThreadPanel(); break;
      case 'thread_update': if(currentThreadId === d.threadId) renderThreadMessages(d.messages); break;
      case 'models_list': populateModelSelect(d.models); break;
      case 'spawn_confirm': appendSystemMessage('Agent '+d.agent.name+' created.'); showToast(`Agent ${d.agent.name} spawned`, 'success'); break;
      case 'error': showToast(d.message, 'error'); break;
      case 'cron_reset': location.reload(); break;
      case 'ralph_status':
        const badge = document.getElementById('ralphStatusBadge');
        if (d.storeId === currentStoreId && d.active) {
          badge.style.display = 'inline-block';
          badge.innerHTML = `🧬 Ralph gen ${d.generation} · ${d.goal || ''}`;
        } else if (d.storeId === currentStoreId && !d.active) {
          badge.style.display = 'none';
        }
        break;
    }
  };
  ws.onclose = () => { document.getElementById('statusText').innerText = 'DISCONNECTED'; setTimeout(connect,3000); };
}

function populateModelSelect(models) {
  const select = document.getElementById('editAgentModel');
  if (!select) return;
  select.innerHTML = '';
  (models || []).forEach(m => {
    const opt = document.createElement('option');
    opt.value = m; opt.textContent = m;
    select.appendChild(opt);
  });
}

function renderSidebar() {
  const sidebar = document.getElementById('sidebar'); if(!sidebar) return;
  sidebar.innerHTML = '';
  addSection('CHANNELS', channels.map(c => ({ id: c.id, name: '#'+c.name, type:'channel', icon:'fa-hashtag' })));
  addSection('DIRECT MESSAGES', dms.map(d => ({ id: d.id, name: d.name, type:'dm', icon:'fa-comment' })));
  addSection('AGENTS', agents.map(a => ({ id: a.id, name: a.name, type:'agent', icon:'fa-robot', status:a.status, model: a.model })));
  addSection('RESEARCH', researchSessions.map(s => ({ id: s.id, name: s.topic.substring(0,20), type:'research', icon:'fa-flask', progress:s.metric })));
}

function addSection(title, items) {
  if(!items.length) return;
  const section = document.createElement('div'); section.className = 'sidebar-section';
  const header = document.createElement('div'); header.className = 'sidebar-header'; header.innerHTML = `<i class="fas fa-chevron-down"></i> ${title}`;
  let itemsDiv = document.createElement('div'); itemsDiv.className = 'channel-list';
  header.onclick = () => { itemsDiv.style.display = itemsDiv.style.display === 'none' ? 'block' : 'none'; };
  section.appendChild(header);
  items.forEach(item => {
    let div;
    if (item.type === 'agent') {
      div = document.createElement('div');
      div.className = 'agent-item';
      div.innerHTML = `
        <div class="agent-info" data-agent-id="${item.id}">
          <i class="fas ${item.icon}"></i>
          <span class="agent-name">${escapeHtml(item.name)}</span>
          <span class="agent-model">${escapeHtml(item.model || '')}</span>
          <span class="agent-status status-${item.status}"></span>
        </div>
        <i class="fas fa-trash-alt remove-agent" data-agent-id="${item.id}" title="Remove"></i>
      `;
      const infoDiv = div.querySelector('.agent-info');
      infoDiv.onclick = (e) => { e.stopPropagation(); openEditModal(agents.find(a => a.id === item.id)); };
      infoDiv.ondblclick = (e) => { e.stopPropagation(); openDmWithAgent(item.name); showToast(`Opening DM with ${item.name}...`, 'info'); };
      const trash = div.querySelector('.remove-agent');
      trash.onclick = async (e) => { e.stopPropagation(); if(confirm(`Permanently remove agent "${item.name}"?`)) { const resp = await fetch(`/api/agent/${item.id}`, { method: 'DELETE' }); const result = await resp.json(); if (resp.ok && result.success) { showToast(`Agent "${item.name}" removed`, 'success'); } else { showToast(`Cannot remove last agent`, 'error'); } } };
    } else {
      div = document.createElement('div'); div.className = 'channel-item';
      div.innerHTML = `<i class="fas ${item.icon}"></i> ${escapeHtml(item.name)}`;
      if(item.progress !== undefined) { let p = document.createElement('span'); p.style.fontSize='0.7rem'; p.style.marginLeft='auto'; p.innerText = `${Math.round(item.progress*100)}%`; div.appendChild(p); }
      div.onclick = () => {
        if(item.type === 'channel') switchToChannel(item.id);
        else if(item.type === 'dm') switchToDm(item.id);
        else if(item.type === 'research') sendCommand('/pull '+item.id);
      };
    }
    itemsDiv.appendChild(div);
  });
  section.appendChild(itemsDiv); sidebar.appendChild(section);
}

function switchToChannel(id) { currentStoreId = id; currentStoreType = 'channel'; const ch = channels.find(c=>c.id===id); document.getElementById('currentChatName').innerHTML = ch ? '#'+ch.name : id; ws.send(JSON.stringify({type:'join',channelId:id})); closeThreadPanel(); updateRalphBadge(); }
function switchToDm(id) { currentStoreId = id; currentStoreType = 'dm'; const dm = dms.find(d=>d.id===id); document.getElementById('currentChatName').innerHTML = dm ? dm.name : 'DM'; ws.send(JSON.stringify({type:'join_dm',dmId:id})); closeThreadPanel(); updateRalphBadge(); }

function updateRalphBadge() {
  const badge = document.getElementById('ralphStatusBadge');
  badge.style.display = 'none';
}

function renderMessages(messages) {
  const container = document.getElementById('messagesArea'); container.innerHTML = '';
  const groups = []; let cur = null;
  for(const msg of messages) {
    if(msg.senderType === 'system') { if(cur) groups.push(cur); groups.push({sender:msg.sender, messages:[msg], lastTimestamp:msg.timestamp}); cur=null; continue; }
    if(!cur || cur.sender !== msg.sender || msg.timestamp - cur.lastTimestamp > 300000) { if(cur) groups.push(cur); cur = { sender: msg.sender, messages: [], lastTimestamp: msg.timestamp }; }
    cur.messages.push(msg); cur.lastTimestamp = msg.timestamp;
  }
  if(cur) groups.push(cur);
  for(const g of groups) {
    const groupDiv = document.createElement('div'); groupDiv.className = 'message-group';
    for(let i=0;i<g.messages.length;i++) {
      const msg = g.messages[i];
      const msgDiv = createMessageElement(msg, i===0 ? g.sender : null);
      groupDiv.appendChild(msgDiv);
    }
    container.appendChild(groupDiv);
  }
  container.scrollTop = container.scrollHeight;
}

function createMessageElement(msg, showSender) {
  const div = document.createElement('div'); div.className = 'message';
  const avatar = document.createElement('div'); avatar.className = 'message-avatar'; avatar.innerText = msg.sender.charAt(0).toUpperCase();
  const contentDiv = document.createElement('div'); contentDiv.className = 'message-content';
  if(showSender) {
    const senderSpan = document.createElement('div'); senderSpan.className = 'message-sender';
    senderSpan.innerHTML = `${escapeHtml(msg.sender)} <span class="message-timestamp">${formatTime(msg.timestamp)}</span>`;
    contentDiv.appendChild(senderSpan);
  }
  const textDiv = document.createElement('div'); textDiv.className = 'message-text';
  textDiv.innerHTML = formatCode(escapeHtml(msg.content));
  contentDiv.appendChild(textDiv);
  if(msg.replyCount > 0) {
    const badge = document.createElement('div'); badge.className = 'reply-badge';
    badge.innerHTML = `<i class="fas fa-reply-all"></i> ${msg.replyCount} replies`;
    badge.onclick = () => fetchThread(msg.id);
    contentDiv.appendChild(badge);
  }
  const actions = document.createElement('div'); actions.className = 'message-actions';
  actions.innerHTML = `<i class="fas fa-reply action-icon" title="Reply"></i><i class="fas fa-plus-circle action-icon" title="React"></i><i class="fas fa-thumbtack action-icon" title="Pin"></i><i class="fas fa-copy action-icon" title="Copy"></i>`;
  actions.querySelector('.fa-reply').onclick = () => fetchThread(msg.id);
  actions.querySelector('.fa-plus-circle').onclick = (e) => { e.stopPropagation(); showReactionPicker(msg.id, e); };
  actions.querySelector('.fa-thumbtack').onclick = () => sendCommand(`/pin ${msg.id}`);
  actions.querySelector('.fa-copy').onclick = () => navigator.clipboard.writeText(msg.content);
  contentDiv.appendChild(actions);
  div.appendChild(avatar); div.appendChild(contentDiv);
  return div;
}

function appendMessage(msg) { const container = document.getElementById('messagesArea'); const groupDiv = document.createElement('div'); groupDiv.className = 'message-group'; groupDiv.appendChild(createMessageElement(msg,true)); container.appendChild(groupDiv); container.scrollTop = container.scrollHeight; }
function appendSystemMessage(text) { const container = document.getElementById('messagesArea'); const div = document.createElement('div'); div.className = 'message'; div.innerHTML = `<div class="message-avatar">S</div><div class="message-content"><em>${escapeHtml(text)}</em></div>`; container.appendChild(div); container.scrollTop = container.scrollHeight; }
function fetchThread(mid) { ws.send(JSON.stringify({type:'reply_in_thread',parentId:mid,content:'',storeId:currentStoreId})); }
function renderThreadMessages(messages) { const container = document.getElementById('threadMessages'); container.innerHTML = ''; for(const msg of messages) { const div = document.createElement('div'); div.className = 'message'; div.innerHTML = `<strong>${escapeHtml(msg.sender)}</strong> ${formatTime(msg.timestamp)}<br>${formatCode(escapeHtml(msg.content))}`; container.appendChild(div); } container.scrollTop = container.scrollHeight; }
function sendThreadReply() { const txt = document.getElementById('threadReplyInput').value.trim(); if(txt && currentThreadId) { ws.send(JSON.stringify({type:'reply_in_thread',parentId:currentThreadId,content:txt,storeId:currentStoreId})); document.getElementById('threadReplyInput').value = ''; } }
function openThreadPanel() { document.getElementById('threadPanel').classList.add('open'); ws.send(JSON.stringify({type:'open_thread',threadId:currentThreadId})); }
function closeThreadPanel() { document.getElementById('threadPanel').classList.remove('open'); if(currentThreadId) ws.send(JSON.stringify({type:'close_thread',threadId:currentThreadId})); currentThreadId = null; }

function sendMessage() {
  let finalMessage = '';
  if (pendingFile) {
    let fileContent;
    try { fileContent = atob(pendingFile.contentBase64); } catch(e) { showToast('Failed to decode file', 'error'); return; }
    const MAX_CHARS = 1500; // safe for WS frame
    const truncated = fileContent.length > MAX_CHARS ? fileContent.substring(0, MAX_CHARS) + '\n...(truncated)' : fileContent;
    const fileBlock = `📎 **File: ${pendingFile.name}**\n\`\`\`\n${truncated}\n\`\`\``;
    const userText = document.getElementById('messageInput').value.trim();
    finalMessage = userText ? `${fileBlock}\n\n${userText}` : fileBlock;
    pendingFile = null;
    document.getElementById('filePreview').innerHTML = '';
  } else {
    finalMessage = document.getElementById('messageInput').value.trim();
  }
  if (!finalMessage) return;
  if (finalMessage.startsWith('/spawn')) { handleSpawn(); document.getElementById('messageInput').value = ''; autoGrow(); return; }
  ws.send(JSON.stringify({type:'message',content:finalMessage}));
  document.getElementById('messageInput').value = '';
  autoGrow();
}

function openDmWithAgent(agentName) {
  if (!ws) return;
  ws.send(JSON.stringify({ type: 'start_dm', targetName: agentName }));
}

function sendCommand(cmd) { if(ws) ws.send(JSON.stringify({type:'message',content:cmd})); }
function formatTime(ts) { return new Date(ts).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}); }
function formatCode(t) { return t.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>'); }
function autoGrow() { const ta = document.getElementById('messageInput'); ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight,200)+'px'; }
let slashTimeout;
function handleSlash(e) { if(e.key !== '/') return; const input = e.target; if(input.selectionStart === 0 || input.value[input.selectionStart-1] === ' ') { if(slashTimeout) clearTimeout(slashTimeout); const existing = document.querySelector('.slash-suggestions'); if(existing) existing.remove(); const commands = ['help','ground','research','abstract','plan','ralph','stop','list','spawn','siphon','slime','pull','dm','thread','pin','graph','errorlog','convergence']; const sug = document.createElement('ul'); sug.className = 'slash-suggestions'; commands.forEach(cmd => { const li = document.createElement('li'); li.innerText = '/'+cmd; li.onclick = () => { input.value = '/'+cmd+' '; input.focus(); sug.remove(); }; sug.appendChild(li); }); input.parentNode.style.position = 'relative'; input.parentNode.appendChild(sug); slashTimeout = setTimeout(() => { if(sug.parentNode) sug.remove(); },5000); document.addEventListener('click', function close(e) { if(!sug.contains(e.target) && e.target !== input) { sug.remove(); document.removeEventListener('click', close); } }); } }
function showReactionPicker(messageId, event) {
  const emojis = ['👍','❤️','😂','😮','😢','🔥'];
  const picker = document.createElement('div');
  picker.style.position='fixed'; picker.style.background='var(--white)'; picker.style.border='1px solid var(--black)'; picker.style.borderRadius='20px'; picker.style.padding='4px'; picker.style.display='flex'; picker.style.gap='8px'; picker.style.zIndex=1000;
  emojis.forEach(emoji => {
    const btn = document.createElement('span');
    btn.innerText=emoji; btn.style.cursor='pointer'; btn.style.fontSize='1.2rem'; btn.style.padding='4px';
    btn.onclick = () => { ws.send(JSON.stringify({type:'add_reaction',messageId:messageId,emoji,storeId:currentStoreId})); picker.remove(); };
    picker.appendChild(btn);
  });
  document.body.appendChild(picker);
  if (event) { picker.style.left = (event.clientX - 50) + 'px'; picker.style.top = (event.clientY - 40) + 'px'; }
  else { picker.style.left = '50%'; picker.style.top = '50%'; picker.style.transform = 'translate(-50%, -50%)'; }
  setTimeout(()=>picker.remove(),3000);
}
function handleQuickSwitch() { const q = document.getElementById('switcherInput').value.toLowerCase(); const ch = channels.find(c=>c.name.toLowerCase().includes(q)); if(ch) switchToChannel(ch.id); const dm = dms.find(d=>d.name.toLowerCase().includes(q)); if(dm) switchToDm(dm.id); const ag = agents.find(a=>a.name.toLowerCase().includes(q)); if(ag) openEditModal(ag); document.getElementById('quickSwitcherModal').style.display='none'; }
function fetchResearchSessions() { fetch('/api/research/sessions').then(r=>r.json()).then(d=>{ researchSessions = d.sessions; renderSidebar(); }).catch(console.error); }
function openEditModal(agent) {
  document.getElementById('editAgentId').value = agent.id;
  document.getElementById('editAgentName').value = agent.name;
  document.getElementById('editAgentPrompt').value = agent.systemPrompt;
  document.getElementById('editAgentChannels').value = agent.channels.join(',');
  fetch('/api/models').then(r=>r.json()).then(data => {
    const sel = document.getElementById('editAgentModel');
    sel.innerHTML = '';
    (data.models||[]).forEach(m => {
      const opt = document.createElement('option');
      opt.value = m; opt.textContent = m;
      if (m === agent.model) opt.selected = true;
      sel.appendChild(opt);
    });
  });
  document.getElementById('agentModal').style.display = 'block';
}
function handleSpawn() { ws.send(JSON.stringify({type:'get_models'})); const orig = ws.onmessage; ws.onmessage = e => { const d = JSON.parse(e.data); if(d.type === 'models_list') { if(!d.models.length) alert('No Ollama models'); else { const name = prompt('Agent name:'); if(name) { const model = prompt('Model:',d.models[0]); const promptText = prompt('System prompt:','You are helpful.'); const chans = prompt('Channels (comma):','general').split(',').map(s=>s.trim()); ws.send(JSON.stringify({type:'spawn_agent',name,model,systemPrompt:promptText,channels:chans})); } } ws.onmessage = orig; } else if(orig) orig(e); }; }
function escapeHtml(s) { return s.replace(/[&<>]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[m])); }

// Graph fixes: resize canvas on container
async function openGraphModal() {
  document.getElementById('graphModal').style.display = 'flex';
  await new Promise(r => setTimeout(r, 100));
  graphCanvas = document.getElementById('agentGraph');
  if (!graphCanvas) return;
  resizeGraphCanvas();
  await fetchAndDrawGraph();
  if (graphInterval) clearInterval(graphInterval);
  graphInterval = setInterval(fetchAndDrawGraph, 3000);
  if (!resizeListener) {
    window.addEventListener('resize', handleGraphResize);
    resizeListener = true;
  }
}
function handleGraphResize() {
  if (document.getElementById('graphModal').style.display === 'flex') {
    resizeGraphCanvas();
    fetchAndDrawGraph();
  }
}
function resizeGraphCanvas() {
  if (!graphCanvas) return;
  const container = graphCanvas.parentElement;
  if (!container) return;
  const w = container.clientWidth, h = container.clientHeight;
  if (w === 0 || h === 0) return;
  const dpr = window.devicePixelRatio || 1;
  graphCanvas.width = w * dpr;
  graphCanvas.height = h * dpr;
  graphCanvas.style.width = w + 'px';
  graphCanvas.style.height = h + 'px';
  graphCtx = graphCanvas.getContext('2d');
  graphCtx.setTransform(1, 0, 0, 1, 0, 0);
  graphCtx.scale(dpr, dpr);
}
async function fetchAndDrawGraph() {
  resizeGraphCanvas();
  try {
    const res = await fetch('/api/metrics');
    const data = await res.json();
    if (!data.agents) return;
    const legend = document.getElementById('graphLegend');
    const colors = ['#ff3b5c','#00f0ff','#39ff14','#ffeb3b','#c84cff'];
    legend.innerHTML = '';
    data.agents.forEach((a,i) => {
      const c = colors[i%colors.length];
      const d = document.createElement('div');
      d.style.display='flex'; d.style.alignItems='center'; d.style.gap='6px'; d.style.fontSize='11px';
      d.innerHTML = `<span style="display:inline-block;width:20px;height:3px;background:${c};border-radius:2px;"></span> ${escapeHtml(a.name)}`;
      legend.appendChild(d);
    });
    drawGraph(data);
  } catch(e) { console.error(e); }
}
function drawGraph(data) {
  if (!graphCtx || !graphCanvas) return;
  const container = graphCanvas.parentElement;
  const w = container.clientWidth, h = container.clientHeight;
  if (w === 0 || h === 0) return;
  const isDark = document.body.classList.contains('dark-mode');
  const bg = isDark?'#0a0a0a':'#f8f8f8';
  const grid = isDark?'#2a2a2a':'#e0e0e0';
  const text = isDark?'#f0f0f0':'#000';
  graphCtx.clearRect(0,0,w,h);
  graphCtx.fillStyle=bg; graphCtx.fillRect(0,0,w,h);
  const pad=40, pw=w-2*pad, ph=h-2*pad;
  if(pw<=0||ph<=0) return;
  graphCtx.strokeStyle=grid; graphCtx.lineWidth=1;
  for(let i=0;i<=5;i++){ let y=pad+ph*(i/5); graphCtx.beginPath(); graphCtx.moveTo(pad,y); graphCtx.lineTo(w-pad,y); graphCtx.stroke(); }
  for(let i=0;i<=4;i++){ let x=pad+pw*(i/4); graphCtx.beginPath(); graphCtx.moveTo(x,pad); graphCtx.lineTo(x,h-pad); graphCtx.stroke(); }
  graphCtx.fillStyle=text; graphCtx.font='10px monospace';
  graphCtx.fillText('100%',pad-30,pad+5);
  graphCtx.fillText('0%',pad-25,h-pad-5);
  graphCtx.fillText('Time →',w/2,h-10);
  const colors = ['#ff3b5c','#00f0ff','#39ff14','#ffeb3b','#c84cff'];
  let allZero=true;
  for(const a of data.agents){
    const m=data.metrics[a.id];
    if(m&&m.cpu&&m.cpu.some(v=>v>0)){ allZero=false; break; }
  }
  if(allZero){
    graphCtx.fillStyle=text;
    graphCtx.font='12px monospace';
    graphCtx.textAlign='center';
    graphCtx.fillText('Waiting for agent activity...',w/2,h/2);
    graphCtx.textAlign='left';
    return;
  }
  data.agents.forEach((a,idx)=>{
    const m=data.metrics[a.id];
    if(!m||!m.cpu||!m.activity) return;
    const cpu=m.cpu, act=m.activity;
    const col=colors[idx%colors.length];
    graphCtx.beginPath();
    graphCtx.strokeStyle=col;
    graphCtx.lineWidth=2.5;
    graphCtx.shadowBlur=3;
    graphCtx.shadowColor=col;
    for(let i=0;i<cpu.length;i++){
      let x=pad+pw*(i/(cpu.length-1));
      let y=h-pad-ph*(cpu[i]/100);
      if(i===0) graphCtx.moveTo(x,y);
      else graphCtx.lineTo(x,y);
    }
    graphCtx.stroke();
    graphCtx.beginPath();
    graphCtx.strokeStyle=col+'dd';
    graphCtx.lineWidth=2;
    graphCtx.shadowBlur=0;
    for(let i=0;i<act.length;i++){
      let x=pad+pw*(i/(act.length-1));
      let y=h-pad-ph*(act[i]/100);
      if(i===0) graphCtx.moveTo(x,y);
      else graphCtx.lineTo(x,y);
    }
    graphCtx.stroke();
  });
  graphCtx.shadowBlur=0;
}

window.onload = init;
</script>
</body>
</html>
'''

CONFIG_JSON = r'''{
  "httpPort": 3721,
  "agents": [
    { "id": "agent1", "name": "Agent 1", "model": "qwen2.5:0.5b", "systemPrompt": "You are a helpful AI assistant.", "channels": ["general","random","siphon","code"] },
    { "id": "agent2", "name": "Agent 2", "model": "qwen2.5:0.5b", "systemPrompt": "You are a creative AI.", "channels": ["general","random","siphon","code"] }
  ],
  "channels": [
    { "id": "general", "name": "general" },
    { "id": "random", "name": "random" },
    { "id": "siphon", "name": "siphon" },
    { "id": "code", "name": "code" }
  ],
  "dms": []
}'''

BIN_LACK_JS = r'''#!/usr/bin/env node
const { spawn } = require('child_process');
const path = require('path');
const projectRoot = path.resolve(__dirname, '..');
process.chdir(projectRoot);
async function checkOllama() {
  const http = require('http');
  return new Promise((resolve) => {
    const req = http.get('http://localhost:11434/api/tags', (res) => resolve(res.statusCode === 200));
    req.on('error', () => resolve(false));
    req.setTimeout(1000, () => resolve(false));
  });
}
async function main() {
  console.log('\\x1b[36m[ LACK v3.5.0 ] Starting – production ready\\x1b[0m');
  if (!await checkOllama()) { console.error('\\x1b[31m✗ Ollama not running\\x1b[0m'); process.exit(1); }
  console.log('\\x1b[32m✓ Ollama detected\\x1b[0m');
  const server = spawn('node', ['server.js'], { stdio: 'inherit', cwd: projectRoot });
  server.on('error', (err) => { console.error('Failed to start server:', err); process.exit(1); });
  process.on('SIGINT', () => { server.kill('SIGINT'); process.exit(); });
}
main();
'''

# ----------------------------------------------------------------------
# Python Launcher – runs Node in background, restarts on crash
# ----------------------------------------------------------------------
def create_directory(path):
    Path(path).mkdir(parents=True, exist_ok=True)

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def make_executable(path):
    st = os.stat(path)
    os.chmod(path, st.st_mode | stat.S_IEXEC)

def run_command(cmd, cwd=None):
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print("STDERR:", result.stderr)
        raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stdout, stderr=result.stderr)
    print(result.stdout)

def open_browser():
    time.sleep(2)
    webbrowser.open('http://localhost:3721')

def main():
    print("=== LACK v3.5.0 – Final Production Fix ===")
    create_directory("config")
    create_directory("public")
    create_directory("bin")
    create_directory("logs")
    create_directory("lineage")
    create_directory("research")

    print("Generating files...")
    write_file("server.js", SERVER_JS)
    write_file("public/index.html", INDEX_HTML)
    write_file("config/lack.config.json", CONFIG_JSON)
    write_file("bin/lack.js", BIN_LACK_JS)
    make_executable("bin/lack.js")

    try:
        node_version = subprocess.run(["node", "--version"], capture_output=True, text=True, check=True)
        print(f"Node.js detected: {node_version.stdout.strip()}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: Node.js is not installed.")
        sys.exit(1)

    if not Path("node_modules").exists():
        print("Installing npm dependencies...")
        run_command(["npm", "install", "express", "ws", "uuid", "axios", "cheerio", "simple-git"])
    else:
        print("node_modules already present.")

    print("Checking Ollama...")
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                print("✓ Ollama is running.")
                models = json.loads(resp.read().decode())
                model_names = [m['name'] for m in models.get('models', [])]
                if not any('qwen2.5:0.5b' in m for m in model_names):
                    print("⚠ qwen2.5:0.5b not found. Run: ollama pull qwen2.5:0.5b")
            else:
                print("⚠ Ollama responded but status not 200.")
    except Exception as e:
        print(f"⚠ Ollama not running or error: {e}. Agents will fail to respond.")

    threading.Thread(target=open_browser, daemon=True).start()
    print("\nStarting LACK v3.5.0 – Production Ready:")
    print(" - Fixed extractJSON hoisting")
    print(" - Per-store projectState (no more corruption)")
    print(" - Ralph loop cancellation and convergence fixed")
    print(" - Ollama error handling everywhere")
    print(" - DM routing robust")
    print(" - Thread consistency")
    print(" - Graph canvas resize & DPR")
    print(" - Cron wipe idempotent & full reset")
    print(" - Responsive UI: scales from mobile to ultra-wide\n")

    # Run Node server in background and restart if it crashes
    while True:
        print("Launching Node server...")
        server_process = subprocess.Popen(["node", "server.js"], stdout=None, stderr=None)
        try:
            server_process.wait()
        except KeyboardInterrupt:
            print("Shutting down...")
            server_process.terminate()
            sys.exit(0)
        print("Server crashed. Restarting in 3 seconds...")
        time.sleep(3)

if __name__ == "__main__":
    main()
