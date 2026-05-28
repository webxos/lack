#!/usr/bin/env python3
"""
LACK INTEGRATED – Multi‑Agent Chat + Autonomous Research (SIPHON) + Mobile Bridge (SLIME)
Channels: #general, #random, #siphon, #code
Agents: Agent 1 & Agent 2 (qwen2.5:0.5b)
Code drops go to #code, research output to #siphon.
Git auto‑commit for research artifacts.
"""

import os
import sys
import subprocess
import stat
import webbrowser
import threading
import time
import json
from pathlib import Path

# ----------------------------------------------------------------------
# File contents (strings)
# ----------------------------------------------------------------------

PACKAGE_JSON = '''{
  "name": "lack-integrated",
  "version": "3.2.0",
  "description": "LACK – Multi‑agent chat with autonomous research, code dropbox, and mobile bridge",
  "main": "server.js",
  "bin": {
    "lack": "./bin/lack.js"
  },
  "scripts": {
    "start": "node server.js"
  },
  "dependencies": {
    "express": "^4.18.2",
    "ws": "^8.14.2",
    "uuid": "^9.0.0",
    "axios": "^1.6.2",
    "cheerio": "^1.0.0-rc.12",
    "html-to-text": "^9.0.5",
    "simple-git": "^3.22.0"
  }
}
'''

SERVER_JS = '''const express = require('express');
const path = require('path');
const WebSocket = require('ws');
const { v4: uuidv4 } = require('uuid');
const fs = require('fs');
const axios = require('axios');
const cheerio = require('cheerio');
const { htmlToText } = require('html-to-text');
const simpleGit = require('simple-git');

// ---------- Configuration ----------
const configPath = path.join(__dirname, 'config', 'lack.config.json');
let config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
const PORT = config.httpPort || 3721;
const OLLAMA_URL = 'http://localhost:11434';
const RESEARCH_DIR = path.join(__dirname, 'research');
const GIT = simpleGit();

// ---------- Stores ----------
const channels = new Map();
const agents = new Map();
const clients = new Map();
const researchSessions = new Map();   // sessionId -> { topic, phase, metric, logs, facts, notes, ... }
const slimeSessions = new Map();      // token -> { pin, expiresAt, channelId }

// ---------- Initialize channels ----------
config.channels.forEach(ch => {
  channels.set(ch.id, {
    id: ch.id,
    name: ch.name,
    messages: [],
    researchActive: false,
    researchTopic: null,
    abstractActive: false,
    loopTimer: null
  });
});

// ---------- Initialize agents (Agent 1 & Agent 2, qwen2.5:0.5b) ----------
config.agents.forEach(agentCfg => {
  agents.set(agentCfg.id, {
    ...agentCfg,
    lastResponseTime: new Map()
  });
});

// ---------- Git helpers ----------
async function ensureGitRepo() {
  if (!fs.existsSync(RESEARCH_DIR)) fs.mkdirSync(RESEARCH_DIR, { recursive: true });
  if (!fs.existsSync(path.join(RESEARCH_DIR, '.git'))) {
    await GIT.cwd(RESEARCH_DIR).init();
    await GIT.cwd(RESEARCH_DIR).addConfig('user.name', 'LACK SIPHON');
    await GIT.cwd(RESEARCH_DIR).addConfig('user.email', 'lack@localhost');
    await GIT.cwd(RESEARCH_DIR).commit('Initial research repo', { '--allow-empty': null });
  }
}

async function gitCommit(message) {
  try {
    await GIT.cwd(RESEARCH_DIR).add('.');
    await GIT.cwd(RESEARCH_DIR).commit(message);
    console.log(`Git commit: ${message}`);
  } catch (e) { console.error('Git commit failed:', e.message); }
}

// ---------- Helper: add message ----------
function addMessage(channelId, sender, senderType, content) {
  const channel = channels.get(channelId);
  if (!channel) return null;
  const msg = {
    id: uuidv4(),
    sender,
    senderType,
    content,
    timestamp: Date.now()
  };
  channel.messages.push(msg);
  if (channel.messages.length > 100) channel.messages.shift();
  return msg;
}

function broadcastToChannel(channelId, message) {
  for (let [ws, client] of clients.entries()) {
    if (client.channelId === channelId && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'new_message', channelId, message }));
    }
  }
}

function broadcastAgents() {
  const agentList = Array.from(agents.values()).map(a => ({
    id: a.id, name: a.name, model: a.model,
    systemPrompt: a.systemPrompt, channels: a.channels
  }));
  for (let [ws, client] of clients.entries()) {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'agents_list', agents: agentList }));
    }
  }
}

// ---------- Ollama helper ----------
async function queryOllama(model, prompt, systemPrompt = '', temperature = 0.7) {
  try {
    const response = await axios.post(`${OLLAMA_URL}/api/generate`, {
      model,
      prompt,
      system: systemPrompt,
      stream: false,
      options: { temperature, num_predict: 800 }
    });
    return response.data.response || "I'm sorry, I couldn't generate a response.";
  } catch (err) {
    console.error(`Ollama error for model ${model}:`, err.message);
    return "[Ollama connection error]";
  }
}

async function getOllamaModels() {
  try {
    const res = await axios.get(`${OLLAMA_URL}/api/tags`);
    return res.data.models.map(m => m.name);
  } catch (e) {
    return [];
  }
}

// ---------- Code detection & forwarding to #code ----------
function extractCodeBlocks(text) {
  const regex = /```(\\w*)\\n([\\s\\S]*?)```/g;
  const blocks = [];
  let match;
  while ((match = regex.exec(text)) !== null) {
    blocks.push({ language: match[1] || 'text', code: match[2].trim() });
  }
  return blocks;
}

async function handleAgentResponse(agent, channelId, responseText) {
  // Post the original response to the current channel
  const msg = addMessage(channelId, agent.name, 'agent', responseText);
  if (msg) broadcastToChannel(channelId, msg);

  // Extract code blocks
  const codeBlocks = extractCodeBlocks(responseText);
  if (codeBlocks.length > 0) {
    for (const block of codeBlocks) {
      const banner = `📦 **Code drop from ${agent.name}** (${block.language})\n\`\`\`${block.language}\n${block.code}\n\`\`\``;
      addMessage('code', agent.name, 'agent', banner);
      broadcastToChannel('code', { sender: agent.name, content: banner, senderType: 'agent' });
    }
    // Also post a short notice in original channel
    const notice = `_(Code block generated – see #code)_`;
    const noticeMsg = addMessage(channelId, 'System', 'system', notice);
    if (noticeMsg) broadcastToChannel(channelId, noticeMsg);
  }
}

// ---------- Original agent response logic (modified to use code detection) ----------
function buildConversationContext(channelId, agentName, maxMessages = 8) {
  const channel = channels.get(channelId);
  if (!channel) return '';
  const relevant = channel.messages.filter(m => m.sender !== agentName);
  const last = relevant.slice(-maxMessages);
  return last.map(m => `${m.sender}: ${m.content}`).join('\\n');
}

async function agentRespond(agent, channelId, triggerMessage, isLoop = false) {
  const agentId = agent.id;
  const channel = channels.get(channelId);
  if (!channel) return;
  if (triggerMessage.sender === agent.name) return;
  const cooldownKey = `${agentId}_${channelId}`;
  const lastResponse = agent.lastResponseTime.get(cooldownKey) || 0;
  const cooldownMs = isLoop ? 2000 : 3000;
  if (Date.now() - lastResponse < cooldownMs) return;

  const context = buildConversationContext(channelId, agent.name);
  let prompt = '';
  if (channel.researchActive && channel.researchTopic) {
    prompt = `You are collaborating on research topic: "${channel.researchTopic}".\\nConversation so far:\\n${context}\\n${triggerMessage.sender} said: "${triggerMessage.content}"\\nNow respond as ${agent.name}. Be helpful and concise.`;
  } else if (channel.abstractActive) {
    prompt = `Autonomous project mode. Your team is building something.\\nConversation:\\n${context}\\n${triggerMessage.sender} said: "${triggerMessage.content}"\\nRespond as ${agent.name} to move the project forward.`;
  } else {
    prompt = `Conversation history:\\n${context}\\n${triggerMessage.sender} said: "${triggerMessage.content}"\\nNow respond as ${agent.name}. Your role: ${agent.systemPrompt.substring(0, 100)}. Keep reply brief and natural.`;
  }
  const reply = await queryOllama(agent.model, prompt, agent.systemPrompt);
  if (reply && reply.trim().length > 0) {
    await handleAgentResponse(agent, channelId, reply.trim());
    agent.lastResponseTime.set(cooldownKey, Date.now());
  }
}

// ---------- Loop scheduling (unchanged) ----------
function scheduleLoopRound(channelId) {
  const channel = channels.get(channelId);
  if (!channel) return;
  if (channel.loopTimer) clearTimeout(channel.loopTimer);
  channel.loopTimer = setTimeout(() => runLoopRound(channelId), 3000);
}

async function runLoopRound(channelId) {
  const channel = channels.get(channelId);
  if (!channel || (!channel.researchActive && !channel.abstractActive)) {
    if (channel.loopTimer) clearTimeout(channel.loopTimer);
    channel.loopTimer = null;
    return;
  }
  channel.loopTimer = null;
  const lastMsg = channel.messages[channel.messages.length - 1];
  if (!lastMsg) return;
  const relevantAgents = Array.from(agents.values()).filter(agent =>
    agent.channels.includes(channel.name)
  );
  for (const agent of relevantAgents) {
    await agentRespond(agent, channelId, lastMsg, true);
  }
  if (channel.researchActive || channel.abstractActive) {
    scheduleLoopRound(channelId);
  }
}

function stopLoop(channelId) {
  const channel = channels.get(channelId);
  if (channel) {
    channel.researchActive = false;
    channel.abstractActive = false;
    channel.researchTopic = null;
    if (channel.loopTimer) clearTimeout(channel.loopTimer);
    channel.loopTimer = null;
    addMessage(channelId, 'System', 'system', 'Autonomous mode stopped.');
    broadcastToChannel(channelId, { sender: 'System', content: 'Autonomous mode stopped.', senderType: 'system' });
  }
}

// ---------- SIPHON: Research engine (JavaScript version) ----------
async function ddgSearch(query, maxResults = 5) {
  const url = `https://html.duckduckgo.com/html/?q=${encodeURIComponent(query)}`;
  try {
    const { data } = await axios.get(url, { headers: { 'User-Agent': 'LACK-SIPHON/1.0' } });
    const $ = cheerio.load(data);
    const results = [];
    $('.result__url').each((i, el) => {
      let href = $(el).attr('href');
      if (href && href.startsWith('/')) href = 'https://duckduckgo.com' + href;
      if (href && href.startsWith('http') && results.length < maxResults) results.push(href);
    });
    return results;
  } catch (e) {
    console.error('DDG search error:', e.message);
    return [];
  }
}

async function scrapeText(url) {
  try {
    const { data } = await axios.get(url, { timeout: 10000 });
    const $ = cheerio.load(data);
    $('script, style, nav, footer, header').remove();
    const text = $('body').text().replace(/\\s+/g, ' ').trim();
    return text.substring(0, 8000);
  } catch (e) {
    return '';
  }
}

async function runResearch(sessionId, topic, channelId) {
  const session = researchSessions.get(sessionId);
  if (!session) return;

  const update = (updates) => {
    Object.assign(session, updates);
    // broadcast research update to UI
    for (let [ws, client] of clients.entries()) {
      if (ws.readyState === WebSocket.OPEN && client.channelId === channelId) {
        ws.send(JSON.stringify({ type: 'research_update', sessionId, data: session }));
      }
    }
    // Also post progress banners to #siphon channel
    if (updates.phase) {
      const banner = `🔬 **SIPHON Research** [${session.topic}]\\nPhase: ${updates.phase} | Metric: ${(session.metric*100).toFixed(0)}%`;
      addMessage('siphon', 'Siphon', 'system', banner);
      broadcastToChannel('siphon', { sender: 'Siphon', content: banner, senderType: 'system' });
    }
  };

  update({ phase: 'Generating questions', metric: 0, logs: [`Starting research on: ${topic}`], facts: [], notes: [] });

  // 1. Generate sub‑questions
  const promptGen = `You are a research assistant. Generate 3 specific sub‑questions to answer for the topic: "${topic}". Output one question per line.`;
  const questionsRaw = await queryOllama(config.agents[0].model, promptGen, '', 0.7);
  const questions = questionsRaw.split('\\n').filter(l => l.trim().length > 10).slice(0, 3);
  update({ questions, currentQuestionIndex: 0, logs: [...session.logs, `Generated ${questions.length} sub‑questions`] });

  let allFacts = [];
  let metric = 0;

  for (let qIdx = 0; qIdx < questions.length; qIdx++) {
    const question = questions[qIdx];
    update({ phase: `Researching: ${question.substring(0, 50)}`, currentQuestionIndex: qIdx });

    // Search
    const searchQueries = [`${topic} ${question}`];
    let urls = [];
    for (const sq of searchQueries) {
      const results = await ddgSearch(sq, 3);
      urls.push(...results);
    }
    urls = [...new Set(urls)].slice(0, 5);
    update({ logs: [...session.logs, `Found ${urls.length} URLs for question ${qIdx+1}`] });

    // Scrape and extract facts
    let factsForQuestion = [];
    for (const url of urls) {
      const content = await scrapeText(url);
      if (!content) continue;
      const extractPrompt = `Extract up to 5 atomic facts from the text below that help answer: "${question}". Return each fact on a new line starting with "FACT:".\\n\\n${content.substring(0, 4000)}`;
      const factsRaw = await queryOllama(config.agents[0].model, extractPrompt, '', 0.3);
      const facts = factsRaw.split('\\n')
        .filter(l => l.startsWith('FACT:'))
        .map(l => l.replace('FACT:', '').trim());
      factsForQuestion.push(...facts);
      update({ logs: [...session.logs, `Scraped ${url} → ${facts.length} facts`] });
      await new Promise(r => setTimeout(r, 500));
    }
    factsForQuestion = [...new Set(factsForQuestion)];
    allFacts.push(...factsForQuestion);
    update({ facts: allFacts, logs: [...session.logs, `Collected ${factsForQuestion.length} facts for question ${qIdx+1}`] });

    // Synthesise answer
    const synthesisPrompt = `Based on these facts, answer the question: "${question}"\\n\\nFacts:\\n${factsForQuestion.join('\\n')}\\n\\nWrite a concise answer (3‑5 sentences).`;
    const answer = await queryOllama(config.agents[0].model, synthesisPrompt, '', 0.5);
    const note = { question, answer, facts: factsForQuestion, timestamp: Date.now() };
    session.notes.push(note);
    update({ notes: session.notes, logs: [...session.logs, `Answered: ${question.substring(0, 60)}`] });

    // Save research artifact to disk and commit to git
    const artifactPath = path.join(RESEARCH_DIR, `${sessionId}_q${qIdx}.json`);
    fs.writeFileSync(artifactPath, JSON.stringify(note, null, 2));
    await gitCommit(`Research ${session.topic} - question ${qIdx+1}`);

    // Update metric
    metric = (qIdx + 1) / questions.length;
    update({ metric });
    if (metric >= 0.9) break;
  }

  update({ phase: 'Complete', metric, logs: [...session.logs, `Research finished. Metric = ${metric.toFixed(2)}`] });

  // Post final summary to #siphon with a pull button
  const finalBanner = `📚 **Research Complete:** ${topic}\\nMetric: ${(metric*100).toFixed(0)}%\\nFacts: ${allFacts.length}\\nNotes: ${session.notes.length}\\n\\nUse \`/pull ${sessionId}\` to bring insights into any channel.`;
  addMessage('siphon', 'Siphon', 'system', finalBanner);
  broadcastToChannel('siphon', { sender: 'Siphon', content: finalBanner, senderType: 'system' });
}

// ---------- SLIME: mobile bridge ----------
function generateSlimeUrl(channelId) {
  const token = uuidv4().replace(/-/g, '').substring(0, 16);
  const pin = Math.floor(100000 + Math.random() * 900000).toString();
  const expiresAt = Date.now() + 60 * 60 * 1000; // 1 hour
  slimeSessions.set(token, { pin, expiresAt, channelId });
  return { url: `http://localhost:${PORT}/slime?token=${token}&pin=${pin}`, pin };
}

// ---------- WebSocket command handling ----------
async function handleSpawn(channelId, data, ws) {
  const { name, model, systemPrompt, channels: agentChannels } = data;
  const id = uuidv4().slice(0, 8);
  const newAgent = {
    id, name, model, systemPrompt, channels: agentChannels,
    lastResponseTime: new Map()
  };
  agents.set(id, newAgent);
  config.agents.push({ id, name, model, systemPrompt, channels: agentChannels });
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
  broadcastAgents();
  ws.send(JSON.stringify({ type: 'spawn_confirm', agent: newAgent }));
}

async function handleUpdateAgent(data) {
  const { id, name, model, systemPrompt, channels: agentChannels } = data;
  const agent = agents.get(id);
  if (agent) {
    agent.name = name;
    agent.model = model;
    agent.systemPrompt = systemPrompt;
    agent.channels = agentChannels;
    const idx = config.agents.findIndex(a => a.id === id);
    if (idx !== -1) {
      config.agents[idx] = { id, name, model, systemPrompt, channels: agentChannels };
      fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
    }
    broadcastAgents();
  }
}

// ---------- Human message handler (commands extended) ----------
async function onHumanMessage(channelId, messageObj) {
  const channel = channels.get(channelId);
  if (!channel) return;
  const content = messageObj.content;

  if (content.startsWith('/')) {
    const parts = content.slice(1).split(' ');
    const cmd = parts[0].toLowerCase();
    const args = parts.slice(1);

    if (cmd === 'help') {
      const help = `Commands:
/ground - All agents check in
/research <topic> - Start research loop (old)
/abstract - Start autonomous project loop
/stop - Stop current loop
/list - Show Ollama models
/spawn - Create a new agent (popup)
/siphon <topic> - Start autonomous research (SIPHON) → results in #siphon
/slime - Generate mobile chat URL for this channel
/pull <sessionId> - Pull insights from a research session into this channel
/help - This help`;
      addMessage(channelId, 'System', 'system', help);
      broadcastToChannel(channelId, { sender: 'System', content: help, senderType: 'system' });
    }
    else if (cmd === 'ground') {
      addMessage(channelId, 'System', 'system', 'GROUND: All agents respond.');
      broadcastToChannel(channelId, { sender: 'System', content: 'GROUND: All agents respond.', senderType: 'system' });
      const agentsInChannel = Array.from(agents.values()).filter(a => a.channels.includes(channel.name));
      for (const agent of agentsInChannel) {
        const reply = await queryOllama(agent.model, `Say "Ground control: I am ${agent.name} and I'm ready."`, agent.systemPrompt);
        if (reply) {
          await handleAgentResponse(agent, channelId, reply.trim());
        }
      }
    }
    else if (cmd === 'research' && args.length) {
      stopLoop(channelId);
      channel.researchActive = true;
      channel.researchTopic = args.join(' ');
      addMessage(channelId, 'System', 'system', `Research mode started on: ${channel.researchTopic}`);
      broadcastToChannel(channelId, { sender: 'System', content: `Research mode started on: ${channel.researchTopic}`, senderType: 'system' });
      const seed = addMessage(channelId, 'System', 'system', `Begin research on: ${channel.researchTopic}`);
      broadcastToChannel(channelId, seed);
      scheduleLoopRound(channelId);
    }
    else if (cmd === 'abstract') {
      stopLoop(channelId);
      channel.abstractActive = true;
      addMessage(channelId, 'System', 'system', 'Abstract mode active – agents choose a project.');
      broadcastToChannel(channelId, { sender: 'System', content: 'Abstract mode active – agents choose a project.', senderType: 'system' });
      const seed = addMessage(channelId, 'System', 'system', 'You are a team of AI agents. Decide on a project and collaborate.');
      broadcastToChannel(channelId, seed);
      scheduleLoopRound(channelId);
    }
    else if (cmd === 'stop') {
      stopLoop(channelId);
    }
    else if (cmd === 'list') {
      const models = await getOllamaModels();
      const listText = 'Available Ollama models:\\n' + models.join('\\n');
      addMessage(channelId, 'System', 'system', listText);
      broadcastToChannel(channelId, { sender: 'System', content: listText, senderType: 'system' });
    }
    else if (cmd === 'spawn') {
      const wsClients = Array.from(clients.keys()).find(ws => clients.get(ws)?.channelId === channelId);
      if (wsClients) {
        const models = await getOllamaModels();
        wsClients.send(JSON.stringify({ type: 'models_list', models }));
      }
    }
    else if (cmd === 'siphon') {
      const topic = args.join(' ') || 'general research topic';
      const sessionId = uuidv4();
      const session = {
        id: sessionId,
        topic,
        phase: 'Initializing',
        metric: 0,
        logs: [],
        facts: [],
        notes: [],
        questions: [],
        currentQuestionIndex: 0,
        startedAt: Date.now()
      };
      researchSessions.set(sessionId, session);
      // Run research in background
      runResearch(sessionId, topic, channelId).catch(console.error);
      addMessage(channelId, 'Siphon', 'system', `🔍 Started research on "${topic}". Check **#siphon** for progress.`);
      broadcastToChannel(channelId, { sender: 'Siphon', content: `Research started: ${topic}`, senderType: 'system' });
    }
    else if (cmd === 'slime') {
      const { url, pin } = generateSlimeUrl(channelId);
      const msg = `📱 **Mobile access**\\nURL: ${url}\\nPIN: ${pin}\\nExpires in 1 hour.`;
      addMessage(channelId, 'System', 'system', msg);
      broadcastToChannel(channelId, { sender: 'System', content: msg, senderType: 'system' });
    }
    else if (cmd === 'pull' && args.length) {
      const sessionId = args[0];
      const session = researchSessions.get(sessionId);
      if (!session) {
        addMessage(channelId, 'System', 'system', `No research session with id ${sessionId}.`);
        broadcastToChannel(channelId, { sender: 'System', content: `No research session with id ${sessionId}.`, senderType: 'system' });
        return;
      }
      let summary = `📊 **Research insights for "${session.topic}"**\\nMetric: ${(session.metric*100).toFixed(0)}%\\n`;
      if (session.notes.length) {
        const lastNote = session.notes[session.notes.length-1];
        summary += `**Latest answer:** ${lastNote.answer.substring(0, 300)}\\n`;
        summary += `Key facts:\\n${lastNote.facts.slice(0,3).map(f => `- ${f}`).join('\\n')}`;
      } else {
        summary += 'No answers yet – research still in progress.';
      }
      addMessage(channelId, 'Siphon', 'system', summary);
      broadcastToChannel(channelId, { sender: 'Siphon', content: summary, senderType: 'system' });
    }
    else {
      addMessage(channelId, 'System', 'system', `Unknown command: ${cmd}. Type /help`);
      broadcastToChannel(channelId, { sender: 'System', content: `Unknown command: ${cmd}`, senderType: 'system' });
    }
    return;
  }

  // Normal message: trigger agents
  const relevantAgents = Array.from(agents.values()).filter(agent =>
    agent.channels.includes(channel.name)
  );
  for (const agent of relevantAgents) {
    agentRespond(agent, channelId, messageObj, false).catch(err => console.error(err));
  }
}

// ---------- Express & WebSocket server ----------
const app = express();
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json());

// API: get Ollama models
app.get('/api/models', async (req, res) => {
  const models = await getOllamaModels();
  res.json({ models });
});

// API: get research sessions (for UI)
app.get('/api/research/sessions', (req, res) => {
  const sessions = Array.from(researchSessions.values()).map(s => ({
    id: s.id,
    topic: s.topic,
    phase: s.phase,
    metric: s.metric,
    logs: s.logs.slice(-10),
    factsCount: s.facts.length,
    notesCount: s.notes.length,
    startedAt: s.startedAt
  }));
  res.json({ sessions });
});

// API: get full research session data
app.get('/api/research/session/:id', (req, res) => {
  const session = researchSessions.get(req.params.id);
  if (!session) return res.status(404).json({ error: 'Session not found' });
  res.json(session);
});

// SLIME mobile interface
app.get('/slime', (req, res) => {
  const { token, pin } = req.query;
  const session = slimeSessions.get(token);
  if (!session || session.pin !== pin || Date.now() > session.expiresAt) {
    return res.status(403).send(`
      <html><body style="background:#000;color:#0f0;font-family:monospace;text-align:center;padding:2rem">
      <h1>SLIME Access Denied</h1><p>Invalid or expired token/PIN.</p>
      </body></html>
    `);
  }
  // Serve the SLIME chat page that connects via WebSocket to the same backend
  res.send(`
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
    <title>SLIME · Mobile Chat</title><style>
      body { background:#000; color:#0f0; font-family:monospace; margin:0; padding:1rem; }
      #messages { height:70vh; overflow-y:auto; border:1px solid #0f0; padding:0.5rem; margin-bottom:1rem; }
      .msg { margin:0.5rem 0; }
      .user { color:#0ff; }
      .agent { color:#ff0; }
      .system { color:#888; font-style:italic; }
      .input-area { display:flex; gap:0.5rem; }
      input { flex:1; background:#111; border:1px solid #0f0; color:#0f0; padding:0.5rem; }
      button { background:#0f0; color:#000; border:none; padding:0.5rem 1rem; cursor:pointer; }
    </style></head>
    <body>
    <h2>SLIME · ${session.channelId} channel</h2>
    <div id="messages"></div>
    <div class="input-area"><input id="msgInput" placeholder="Type message..."><button id="sendBtn">Send</button></div>
    <script>
      const ws = new WebSocket(\`ws://\${location.host}\`);
      ws.onopen = () => ws.send(JSON.stringify({ type: 'join', channelId: '${session.channelId}' }));
      ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.type === 'new_message') {
          const div = document.createElement('div');
          div.className = \`msg \${data.message.senderType}\`;
          div.innerHTML = \`<strong>\${escapeHtml(data.message.sender)}</strong> [\${new Date(data.message.timestamp).toLocaleTimeString()}]:<br>\${escapeHtml(data.message.content)}\`;
          document.getElementById('messages').appendChild(div);
          document.getElementById('messages').scrollTop = document.getElementById('messages').scrollHeight;
        }
      };
      function escapeHtml(s) { return s.replace(/[&<>]/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[m])); }
      document.getElementById('sendBtn').onclick = () => {
        const input = document.getElementById('msgInput');
        if (input.value.trim()) {
          ws.send(JSON.stringify({ type: 'message', content: input.value }));
          input.value = '';
        }
      };
      document.getElementById('msgInput').onkeypress = (e) => { if (e.key === 'Enter') document.getElementById('sendBtn').click(); };
    </script>
    </body></html>
  `);
});

const server = app.listen(PORT, async () => {
  await ensureGitRepo();
  console.log(`\\x1b[32m✓ LACK Integrated running at http://localhost:${PORT}\\x1b[0m`);
  console.log(`   Agents: ${Array.from(agents.values()).map(a => a.name).join(', ')}`);
  console.log(`   Channels: ${Array.from(channels.values()).map(c => c.name).join(', ')}`);
  console.log(`   Git research repo: ${RESEARCH_DIR}`);
  console.log(`   SIPHON research & SLIME mobile bridge active.`);
});

const wss = new WebSocket.Server({ server });

wss.on('connection', (ws) => {
  const clientId = uuidv4();
  clients.set(ws, { username: `human_${clientId.slice(0,4)}`, channelId: 'general' });

  ws.on('message', async (raw) => {
    const data = JSON.parse(raw);
    const client = clients.get(ws);
    if (!client) return;

    switch (data.type) {
      case 'join':
        if (channels.has(data.channelId)) {
          client.channelId = data.channelId;
          const channel = channels.get(data.channelId);
          ws.send(JSON.stringify({ type: 'history', channelId: data.channelId, messages: channel.messages }));
          ws.send(JSON.stringify({ type: 'agents_list', agents: Array.from(agents.values()).map(a => ({
            id: a.id, name: a.name, model: a.model, systemPrompt: a.systemPrompt, channels: a.channels
          })) }));
        }
        break;
      case 'message':
        const channelId = client.channelId;
        const msgText = data.content.trim();
        if (!msgText) break;
        const humanMsg = addMessage(channelId, client.username, 'human', msgText);
        if (humanMsg) {
          broadcastToChannel(channelId, humanMsg);
          await onHumanMessage(channelId, humanMsg);
        }
        break;
      case 'set_username':
        client.username = data.username.substring(0, 20);
        break;
      case 'spawn_agent':
        await handleSpawn(client.channelId, data, ws);
        break;
      case 'update_agent':
        await handleUpdateAgent(data);
        break;
      case 'get_models':
        const models = await getOllamaModels();
        ws.send(JSON.stringify({ type: 'models_list', models }));
        break;
    }
  });

  ws.on('close', () => clients.delete(ws));
  ws.send(JSON.stringify({ type: 'channels', channels: Array.from(channels.values()).map(c => ({ id: c.id, name: c.name })) }));
});

console.log('LACK Integrated ready.');
'''

# ----------------------------------------------------------------------
# Frontend HTML (clean UI: channels list, agents list, research section)
# ----------------------------------------------------------------------
INDEX_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>LACK · Multi‑Agent Chat</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    :root {
      --white: #ffffff; --off-white: #f8f8f8; --light-gray: #e0e0e0;
      --gray: #a0a0a0; --dark-gray: #666666; --black: #000000;
      --shadow-dark: rgba(0,0,0,0.2);
    }
    .dark-mode {
      --white: #0a0a0a; --off-white: #1a1a1a; --light-gray: #2a2a2a;
      --gray: #555555; --dark-gray: #999999; --black: #f0f0f0;
      --shadow-dark: rgba(255,255,255,0.1);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: monospace; }
    body {
      background: var(--white); color: var(--black);
      overflow: hidden; transition: 0.3s;
    }
    .neuro-menu {
      position: fixed; top: 0; left: 0; right: 0; height: 40px;
      background: var(--white); border-bottom: 2px solid var(--black);
      display: flex; align-items: center; padding: 0 20px; z-index: 10000;
    }
    .menu-item { padding: 0 16px; border-right: 1px solid var(--light-gray); font-size: 11px; font-weight: 600; }
    .neuro-status { margin-left: auto; display: flex; gap: 20px; align-items: center; font-size: 10px; }
    .dark-mode-toggle, .ground-btn {
      background: var(--white); border: 1px solid var(--black); border-radius: 20px;
      padding: 4px 12px; cursor: pointer;
    }
    .neuro-desktop { position: absolute; top: 40px; left: 0; right: 0; bottom: 0; background: var(--off-white); padding: 20px; }
    .chat-container { background: var(--white); border: 2px solid var(--black); box-shadow: 8px 8px 0 var(--shadow-dark); width: 100%; height: 100%; display: flex; }
    .sidebar { width: 260px; border-right: 2px solid var(--black); display: flex; flex-direction: column; overflow-y: auto; }
    .sidebar-section { border-bottom: 1px solid var(--light-gray); }
    .sidebar-header { padding: 12px; font-weight: 600; font-size: 12px; background: var(--off-white); }
    .channel-list, .agent-list, .research-list { padding: 8px; }
    .channel-item, .agent-item, .research-item {
      padding: 8px; margin: 4px 0; cursor: pointer; border: 1px solid transparent;
      font-size: 11px; display: flex; align-items: center; gap: 8px;
    }
    .channel-item:hover, .agent-item:hover, .research-item:hover { background: var(--light-gray); }
    .channel-item.active { background: var(--black); color: var(--white); }
    .agent-item { justify-content: space-between; }
    .agent-name { font-weight: 600; }
    .agent-model { font-size: 9px; color: var(--gray); }
    .research-item { flex-direction: column; align-items: flex-start; }
    .research-title { font-weight: bold; }
    .research-progress { font-size: 9px; color: var(--gray); }
    .main-chat { flex: 1; display: flex; flex-direction: column; }
    .chat-header { padding: 12px; border-bottom: 2px solid var(--black); font-weight: 600; }
    .messages-area { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px; background: var(--off-white); }
    .message { background: var(--white); border-left: 3px solid var(--black); padding: 8px 12px; font-size: 12px; max-width: 80%; word-wrap: break-word; }
    .message.human { align-self: flex-end; border-left-color: var(--gray); background: var(--light-gray); }
    .message.agent { align-self: flex-start; }
    .message.system { align-self: center; background: var(--off-white); font-style: italic; max-width: 90%; }
    .input-area { padding: 16px; border-top: 2px solid var(--black); display: flex; gap: 12px; background: var(--white); }
    .input-area input { flex: 1; background: var(--white); border: 1px solid var(--black); padding: 8px; }
    .input-area button { background: var(--white); border: 2px solid var(--black); padding: 8px 16px; cursor: pointer; }
    .bottom-bar { position: fixed; bottom: 0; left: 0; right: 0; background: var(--white); border-top: 2px solid var(--black); padding: 6px 16px; font-size: 0.7rem; display: flex; justify-content: space-between; }
    .modal { display: none; position: fixed; z-index: 20000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.6); }
    .modal-content { background: var(--white); margin: 10% auto; padding: 20px; border: 2px solid var(--black); width: 450px; max-width: 90%; }
    .modal-content input, .modal-content select, .modal-content textarea { width: 100%; margin: 8px 0; padding: 6px; }
    .modal-buttons { display: flex; justify-content: flex-end; gap: 12px; margin-top: 16px; }
    .modal-buttons button { padding: 6px 12px; cursor: pointer; }
    pre { background: #111; color: #0f0; padding: 8px; overflow-x: auto; margin: 4px 0; }
  </style>
</head>
<body>
<div class="neuro-menu">
  <div class="menu-item">LACK v3.2</div>
  <div class="neuro-status">
    <span id="agentCount">Agents: 0</span>
    <button class="ground-btn" id="groundBtn">🌍 GROUND</button>
    <div class="dark-mode-toggle" id="darkModeToggle">🌓</div>
  </div>
</div>
<div class="neuro-desktop">
  <div class="chat-container">
    <div class="sidebar">
      <div class="sidebar-section">
        <div class="sidebar-header">CHANNELS</div>
        <div class="channel-list" id="channelList"></div>
      </div>
      <div class="sidebar-section">
        <div class="sidebar-header">AGENTS (double‑click to edit)</div>
        <div class="agent-list" id="agentList"></div>
      </div>
      <div class="sidebar-section">
        <div class="sidebar-header">ACTIVE RESEARCH</div>
        <div class="research-list" id="researchList"></div>
      </div>
    </div>
    <div class="main-chat">
      <div class="chat-header" id="currentChannelName">general</div>
      <div class="messages-area" id="messagesArea"></div>
      <div class="input-area">
        <input type="text" id="messageInput" placeholder="Type /help ...">
        <button id="sendBtn">SEND</button>
      </div>
    </div>
  </div>
</div>
<div class="bottom-bar"><span>LACK · Multi‑Agent + SIPHON + SLIME</span><span id="statusText">CONNECTED</span></div>

<div id="agentModal" class="modal">
  <div class="modal-content">
    <h3>Edit Agent</h3>
    <input type="text" id="editAgentId" hidden>
    <label>Name:</label><input type="text" id="editAgentName">
    <label>Model:</label><select id="editAgentModel"></select>
    <label>System Prompt:</label><textarea id="editAgentPrompt" rows="3"></textarea>
    <label>Channels (comma):</label><input type="text" id="editAgentChannels">
    <div class="modal-buttons">
      <button id="saveAgentBtn">Save</button>
      <button id="closeModalBtn">Cancel</button>
    </div>
  </div>
</div>

<script src="/client.js"></script>
</body>
</html>
'''

CLIENT_JS = '''let ws = null;
let currentChannelId = 'general';
let username = 'human_' + Math.floor(Math.random() * 1000);
let agents = [];
let researchSessions = [];

function init() {
  connectWebSocket();
  document.getElementById('sendBtn').onclick = () => {
    const input = document.getElementById('messageInput');
    if (input.value.trim() === '/spawn') { handleSpawn(); input.value = ''; return; }
    sendMessage();
  };
  document.getElementById('messageInput').onkeypress = (e) => { if(e.key === 'Enter') document.getElementById('sendBtn').click(); };
  document.getElementById('darkModeToggle').onclick = () => document.body.classList.toggle('dark-mode');
  document.getElementById('groundBtn').onclick = () => sendCommand('/ground');
  setInterval(() => fetchResearchSessions(), 5000);
  promptUsername();
}

function fetchResearchSessions() {
  fetch('/api/research/sessions')
    .then(res => res.json())
    .then(data => {
      researchSessions = data.sessions;
      renderResearchList();
    })
    .catch(console.error);
}

function renderResearchList() {
  const container = document.getElementById('researchList');
  if (!container) return;
  container.innerHTML = '';
  if (researchSessions.length === 0) {
    container.innerHTML = '<div style="padding:8px; color:var(--gray)">No active research. Use /siphon <topic>.</div>';
    return;
  }
  researchSessions.forEach(s => {
    const div = document.createElement('div');
    div.className = 'research-item';
    div.innerHTML = `<div class="research-title">${escapeHtml(s.topic.substring(0, 40))}</div>
                     <div class="research-progress">${s.phase} | ${(s.metric*100).toFixed(0)}% | facts: ${s.factsCount}</div>`;
    div.onclick = () => {
      sendCommand(`/pull ${s.id}`);
    };
    container.appendChild(div);
  });
}

function connectWebSocket() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${protocol}//${location.host}`);
  ws.onopen = () => {
    document.getElementById('statusText').innerText = 'CONNECTED';
    ws.send(JSON.stringify({ type: 'join', channelId: currentChannelId }));
    ws.send(JSON.stringify({ type: 'set_username', username }));
  };
  ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === 'channels') renderChannels(data.channels);
    else if (data.type === 'history') renderMessages(data.messages);
    else if (data.type === 'new_message') appendMessage(data.message);
    else if (data.type === 'agents_list') {
      agents = data.agents;
      document.getElementById('agentCount').innerText = `Agents: ${agents.length}`;
      renderAgents(agents);
    } else if (data.type === 'models_list') populateModelSelect(data.models);
    else if (data.type === 'spawn_confirm') appendMessage({ sender: 'System', content: `Agent ${data.agent.name} created.`, senderType: 'system' });
    else if (data.type === 'research_update') fetchResearchSessions();
  };
  ws.onclose = () => { document.getElementById('statusText').innerText = 'DISCONNECTED'; setTimeout(connectWebSocket, 3000); };
}

function renderChannels(channels) {
  const container = document.getElementById('channelList');
  container.innerHTML = '';
  channels.forEach(ch => {
    const div = document.createElement('div');
    div.className = 'channel-item' + (ch.id === currentChannelId ? ' active' : '');
    div.innerText = '#' + ch.name;
    div.onclick = () => {
      currentChannelId = ch.id;
      document.getElementById('currentChannelName').innerText = ch.name;
      ws.send(JSON.stringify({ type: 'join', channelId: currentChannelId }));
      document.querySelectorAll('.channel-item').forEach(el => el.classList.remove('active'));
      div.classList.add('active');
    };
    container.appendChild(div);
  });
}

function renderAgents(agents) {
  const container = document.getElementById('agentList');
  container.innerHTML = '';
  agents.forEach(ag => {
    const div = document.createElement('div');
    div.className = 'agent-item';
    div.innerHTML = `<span class="agent-name">🤖 ${escapeHtml(ag.name)}</span><span class="agent-model">${escapeHtml(ag.model.split(':')[0])}</span>`;
    div.ondblclick = () => openEditModal(ag);
    container.appendChild(div);
  });
}

async function openEditModal(agent) {
  document.getElementById('editAgentId').value = agent.id;
  document.getElementById('editAgentName').value = agent.name;
  document.getElementById('editAgentPrompt').value = agent.systemPrompt;
  document.getElementById('editAgentChannels').value = agent.channels.join(',');
  const resp = await fetch('/api/models');
  const data = await resp.json();
  const models = data.models || [];
  const modelSelect = document.getElementById('editAgentModel');
  modelSelect.innerHTML = '';
  models.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m;
    opt.textContent = m;
    if (m === agent.model) opt.selected = true;
    modelSelect.appendChild(opt);
  });
  document.getElementById('agentModal').style.display = 'block';
}

function populateModelSelect(models) {
  const select = document.getElementById('editAgentModel');
  if (!select) return;
  select.innerHTML = '';
  models.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m;
    opt.textContent = m;
    select.appendChild(opt);
  });
}

function renderMessages(messages) { const container = document.getElementById('messagesArea'); container.innerHTML = ''; messages.forEach(msg => appendMessage(msg)); }
function appendMessage(msg) {
  const container = document.getElementById('messagesArea');
  const div = document.createElement('div');
  let cls = 'message ';
  if (msg.senderType === 'human') cls += 'human';
  else if (msg.senderType === 'agent') cls += 'agent';
  else cls += 'system';
  div.className = cls;
  const time = new Date(msg.timestamp).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
  div.innerHTML = `<div style="font-size:10px; color:var(--dark-gray)">${escapeHtml(msg.sender)} · ${time}</div><div class="message-text">${formatCode(escapeHtml(msg.content))}</div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}
function formatCode(text) {
  // simple code block rendering
  return text.replace(/```(\\w*)\\n([\\s\\S]*?)```/g, '<pre><code>$2</code></pre>');
}
function sendMessage() { const input = document.getElementById('messageInput'); const text = input.value.trim(); if (!text || !ws) return; ws.send(JSON.stringify({ type: 'message', content: text })); input.value = ''; }
function sendCommand(cmd) { if (ws) ws.send(JSON.stringify({ type: 'message', content: cmd })); }
function promptUsername() { const newName = prompt('Display name:', username); if (newName && newName.trim()) { username = newName.trim().substring(0,20); if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'set_username', username })); } }
function handleSpawn() {
  ws.send(JSON.stringify({ type: 'get_models' }));
  const originalOnMessage = ws.onmessage;
  ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === 'models_list') {
      const name = prompt('Agent name:');
      if(!name) return;
      const model = prompt(`Models:\\n${data.models.join('\\n')}\\nChoose model:`);
      if(!model) return;
      const promptText = prompt('System prompt:', 'You are a helpful assistant.');
      const channels = prompt('Channels (comma):', 'general').split(',').map(s=>s.trim());
      ws.send(JSON.stringify({ type: 'spawn_agent', name, model, systemPrompt: promptText, channels }));
      ws.onmessage = originalOnMessage;
    } else if (originalOnMessage) {
      originalOnMessage(e);
    }
  };
}
function escapeHtml(str) { return str.replace(/[&<>]/g, m => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;' }[m])); }

document.getElementById('saveAgentBtn').onclick = () => {
  const id = document.getElementById('editAgentId').value;
  const name = document.getElementById('editAgentName').value;
  const model = document.getElementById('editAgentModel').value;
  const prompt = document.getElementById('editAgentPrompt').value;
  const channels = document.getElementById('editAgentChannels').value.split(',').map(s=>s.trim());
  ws.send(JSON.stringify({ type: 'update_agent', id, name, model, systemPrompt: prompt, channels }));
  document.getElementById('agentModal').style.display = 'none';
};
document.getElementById('closeModalBtn').onclick = () => { document.getElementById('agentModal').style.display = 'none'; };

window.onload = init;
'''

CONFIG_JSON = '''{
  "httpPort": 3721,
  "agents": [
    {
      "id": "agent1",
      "name": "Agent 1",
      "model": "qwen2.5:0.5b",
      "systemPrompt": "You are a helpful AI assistant. Keep answers concise and friendly. When you write code, wrap it in triple backticks with language specified.",
      "channels": ["general", "random", "siphon", "code"]
    },
    {
      "id": "agent2",
      "name": "Agent 2",
      "model": "qwen2.5:0.5b",
      "systemPrompt": "You are a creative and analytical AI. Provide detailed explanations and when you write code, use markdown code blocks.",
      "channels": ["general", "random", "siphon", "code"]
    }
  ],
  "channels": [
    { "id": "general", "name": "general" },
    { "id": "random", "name": "random" },
    { "id": "siphon", "name": "siphon" },
    { "id": "code", "name": "code" }
  ]
}
'''

BIN_LACK_JS = '''#!/usr/bin/env node
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
  console.log('\\x1b[36m[ LACK Integrated ] Starting...\\x1b[0m');
  const ollamaOk = await checkOllama();
  if (!ollamaOk) { console.error('\\x1b[31m✗ Ollama not running\\x1b[0m'); process.exit(1); }
  console.log('\\x1b[32m✓ Ollama detected\\x1b[0m');
  const server = spawn('node', ['server.js'], { stdio: 'inherit', cwd: projectRoot });
  server.on('error', (err) => { console.error('Failed to start server:', err); process.exit(1); });
  process.on('SIGINT', () => { server.kill('SIGINT'); process.exit(); });
}
main();
'''

# ----------------------------------------------------------------------
# Bootstrap logic
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
    subprocess.run(cmd, cwd=cwd, check=True)

def open_browser():
    time.sleep(2)
    webbrowser.open('http://localhost:3721')

def main():
    print("=== LACK Integrated Bootstrap ===")
    create_directory("config")
    create_directory("public")
    create_directory("bin")

    print("Writing files...")
    write_file("package.json", PACKAGE_JSON)
    write_file("server.js", SERVER_JS)
    write_file("public/index.html", INDEX_HTML)
    write_file("public/client.js", CLIENT_JS)
    write_file("config/lack.config.json", CONFIG_JSON)
    write_file("bin/lack.js", BIN_LACK_JS)
    make_executable("bin/lack.js")

    # Check Node.js
    try:
        node_version = subprocess.run(["node", "--version"], capture_output=True, text=True, check=True)
        print(f"Node.js detected: {node_version.stdout.strip()}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: Node.js is not installed.")
        sys.exit(1)

    # Install npm dependencies if needed
    if not Path("node_modules").exists():
        print("Installing npm dependencies...")
        run_command(["npm", "install"])
    else:
        print("node_modules already present.")

    # Check Ollama
    print("Checking Ollama...")
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                print("✓ Ollama is running.")
                # Check for required model
                models = json.loads(resp.read().decode())
                model_names = [m['name'] for m in models.get('models', [])]
                if not any('qwen2.5:0.5b' in m for m in model_names):
                    print("⚠ qwen2.5:0.5b not found. Agents may fail. Run: ollama pull qwen2.5:0.5b")
            else:
                print("⚠ Ollama responded but status not 200.")
    except Exception:
        print("⚠ Ollama not running. Agents will fail to respond.")

    # Open browser in background
    threading.Thread(target=open_browser, daemon=True).start()

    print("\nStarting LACK Integrated server...\n")
    run_command(["node", "server.js"])

if __name__ == "__main__":
    main()
