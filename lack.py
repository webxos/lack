#!/usr/bin/env python3
"""
LACK v3.4.3 – Fully fixed agent loop + enhanced research/DM/graph/error log + cron mgmt
Generates all necessary files and starts the server.
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
# Embedded file contents (generated on first run)
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

// ---------- Configuration ----------
const configPath = path.join(__dirname, 'config', 'lack.config.json');
let config;
try {
  config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
} catch (err) {
  config = {
    httpPort: 3721,
    agents: [
      { id: "agent1", name: "Agent 1", model: "qwen2.5:0.5b", systemPrompt: "You are a helpful AI assistant.", channels: ["general", "random", "siphon", "code"] },
      { id: "agent2", name: "Agent 2", model: "qwen2.5:0.5b", systemPrompt: "You are a creative AI.", channels: ["general", "random", "siphon", "code"] }
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
const GIT = simpleGit();

// ---------- Stores ----------
const channels = new Map();
const agents = new Map();
const clients = new Map();        // ws -> { username, channelId, userId, dmId }
const researchSessions = new Map(); // sessionId -> session
const slimeSessions = new Map();
const dms = new Map();
const pinnedMessages = new Map();
const userReactions = new Map();
const agentMetrics = new Map();
const jsonFailCount = new Map();   // agentId -> consecutive JSON parse failures

// Shared project state
let projectState = {
  active: false,
  title: null,
  goals: [],
  nextSteps: [],
  completedTasks: [],
  memory: {}
};

// ---------- Helper: consistent user ID ----------
function getUserId(ws) {
  let client = clients.get(ws);
  if (!client) {
    const id = `human_${uuidv4().slice(0,6)}`;
    clients.set(ws, { username: id, channelId: 'general', userId: id, dmId: null });
    client = clients.get(ws);
  }
  return client.userId;
}

// ---------- Initialize stores ----------
config.channels.forEach(ch => {
  channels.set(ch.id, {
    id: ch.id,
    name: ch.name,
    messages: [],
    researchActive: false,
    researchTopic: null,
    abstractActive: false,
    loopTimer: null,
    pinned: new Set()
  });
});
if (config.dms) {
  config.dms.forEach(dm => {
    dms.set(dm.id, {
      id: dm.id,
      participants: dm.participants,
      name: dm.name || dm.participants.join(', '),
      messages: []
    });
  });
}
config.agents.forEach(agentCfg => {
  agents.set(agentCfg.id, {
    ...agentCfg,
    lastResponseTime: new Map(), // key: "agentId_channelId"
    status: 'online',
    statusMessage: ''
  });
  agentMetrics.set(agentCfg.id, {
    cpu: Array(30).fill(0),
    mem: Array(30).fill(0),
    activity: Array(30).fill(0),
    timestamps: Array(30).fill(Date.now())
  });
  jsonFailCount.set(agentCfg.id, 0);
});

// ---------- Git helpers ----------
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

// ---------- Message helpers ----------
function addMessage(storeId, sender, senderType, content, parentId = null) {
  let store = channels.get(storeId);
  let isDm = false;
  if (!store) {
    store = dms.get(storeId);
    if (store) isDm = true;
    else return null;
  }
  let threadId = null;
  if (parentId) {
    const parent = store.messages.find(m => m.id === parentId);
    if (parent) threadId = parent.threadId || parent.id;
    else threadId = parentId;
  }
  const msg = {
    id: uuidv4(),
    sender,
    senderType,
    content,
    timestamp: Date.now(),
    parentId: parentId || null,
    threadId: threadId,
    replyCount: 0,
    reactions: {}
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
  return msg;
}

function getThreadMessages(storeId, threadId) {
  const store = channels.get(storeId) || dms.get(storeId);
  if (!store) return [];
  return store.messages.filter(m => m.threadId === threadId || m.id === threadId);
}

function broadcastToChannel(channelId, message, excludeWs = null) {
  for (let [ws, client] of clients.entries()) {
    if (ws !== excludeWs && client.channelId === channelId && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'new_message', channelId, message }));
    }
  }
}
function broadcastToDm(dmId, message, excludeWs = null) {
  for (let [ws, client] of clients.entries()) {
    if (ws !== excludeWs && client.dmId === dmId && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'new_dm_message', dmId, message }));
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
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'agents_list', agents: agentList }));
    }
  }
}

// ---------- Logging ----------
function logError(errorObj) {
  const entry = { timestamp: Date.now(), ...errorObj };
  const logLine = JSON.stringify(entry) + '\n';
  fs.appendFileSync(ERROR_LOG_PATH, logLine);
  // keep in memory as well
  if (global.errorLog) global.errorLog.unshift(entry);
  else global.errorLog = [entry];
  if (global.errorLog.length > 100) global.errorLog.pop();
  console.error('[ERROR]', errorObj);
}

// ---------- Ollama with metrics ----------
async function queryOllama(model, prompt, systemPrompt = '', temperature = 0.7, agentId = null) {
  const startTime = Date.now();
  try {
    const response = await axios.post(`${OLLAMA_URL}/api/generate`, {
      model, prompt, system: systemPrompt, stream: false,
      options: { temperature, num_predict: 2048 }
    });
    const duration = Date.now() - startTime;
    const tokens = response.data.eval_count || Math.floor(duration / 25);
    if (agentId && agentMetrics.has(agentId)) {
      const metrics = agentMetrics.get(agentId);
      metrics.cpu.shift(); metrics.cpu.push(Math.min(95, Math.floor(tokens / 8)));
      metrics.mem.shift(); metrics.mem.push(Math.min(98, Math.floor(duration / 40)));
      metrics.activity.shift(); metrics.activity.push(Math.min(100, Math.floor(duration / 15)));
      metrics.timestamps.shift(); metrics.timestamps.push(Date.now());
    } else if (!agentId && agentMetrics.size > 0) {
      // fallback: update first agent's metrics for system calls
      const firstAgentId = Array.from(agentMetrics.keys())[0];
      const metrics = agentMetrics.get(firstAgentId);
      if (metrics) {
        metrics.activity.shift(); metrics.activity.push(Math.min(100, Math.floor(duration / 20)));
        metrics.timestamps.shift(); metrics.timestamps.push(Date.now());
      }
    }
    return response.data.response || "I'm sorry, I couldn't generate a response.";
  } catch (err) {
    logError({ agentId: agentId || 'system', model, error: err.message, promptLength: prompt.length });
    return `[Ollama error: ${err.message.substring(0,80)}]`;
  }
}
async function getOllamaModels() {
  try {
    const res = await axios.get(`${OLLAMA_URL}/api/tags`);
    return res.data.models.map(m => m.name);
  } catch (e) { return []; }
}

// ---------- Code blocks ----------
function extractCodeBlocks(text) {
  const regex = /```(\w*)\n([\s\S]*?)```/g;
  const blocks = [];
  let match;
  while ((match = regex.exec(text)) !== null) {
    blocks.push({ language: match[1] || 'text', code: match[2].trim() });
  }
  return blocks;
}
async function handleAgentResponse(agent, channelId, responseText) {
  const msg = addMessage(channelId, agent.name, 'agent', responseText);
  if (msg) broadcastToChannel(channelId, msg);
  const codeBlocks = extractCodeBlocks(responseText);
  if (codeBlocks.length > 0 && channelId !== 'code') {
    for (const block of codeBlocks) {
      const banner = `📦 **Code drop from ${agent.name}** (${block.language})\n\`\`\`${block.language}\n${block.code}\n\`\`\``;
      addMessage('code', agent.name, 'agent', banner);
      broadcastToChannel('code', { sender: agent.name, content: banner, senderType: 'agent' });
    }
    const notice = `_(Code block generated – see #code)_`;
    const noticeMsg = addMessage(channelId, 'System', 'system', notice);
    if (noticeMsg) broadcastToChannel(channelId, noticeMsg);
  }
}

// ---------- Conversation context ----------
function buildConversationContext(channelId, agentName, maxMessages = 8) {
  const channel = channels.get(channelId);
  if (!channel) return '';
  const relevant = channel.messages.filter(m => m.sender !== agentName && m.senderType !== 'system');
  const last = relevant.slice(-maxMessages);
  return last.map(m => `${m.sender}: ${m.content}`).join('\n');
}

// ---------- Natural agent response ----------
async function agentRespond(agent, channelId, triggerMessage, isLoop = false) {
  if (triggerMessage.sender === agent.name) return;
  const cooldownKey = `${agent.id}_${channelId}`;
  const lastResponse = agent.lastResponseTime.get(cooldownKey) || 0;
  const cooldownMs = isLoop ? 2000 : 3000;
  if (Date.now() - lastResponse < cooldownMs) return;

  agent.status = 'thinking';
  broadcastAgents();

  try {
    const context = buildConversationContext(channelId, agent.name);
    let prompt = '';
    const channelObj = channels.get(channelId);
    if (channelObj && channelObj.researchActive && channelObj.researchTopic) {
      prompt = `Research topic: "${channelObj.researchTopic}".\nConversation:\n${context}\n${triggerMessage.sender}: ${triggerMessage.content}\nRespond as ${agent.name} (helpful, concise).`;
    } else if (channelObj && channelObj.abstractActive) {
      prompt = `Autonomous project mode.\nConversation:\n${context}\n${triggerMessage.sender}: ${triggerMessage.content}\nRespond as ${agent.name} to move project forward.`;
    } else {
      prompt = `Conversation:\n${context}\n${triggerMessage.sender}: ${triggerMessage.content}\nRespond as ${agent.name}. Role: ${agent.systemPrompt}. Keep reply brief.`;
    }
    const reply = await queryOllama(agent.model, prompt, agent.systemPrompt, 0.7, agent.id);
    if (reply && reply.trim().length > 0) {
      await handleAgentResponse(agent, channelId, reply.trim());
      agent.lastResponseTime.set(cooldownKey, Date.now());
      jsonFailCount.set(agent.id, 0); // reset JSON fail counter on successful natural response
    }
  } catch (err) {
    console.error(`Agent ${agent.name} error:`, err);
  } finally {
    agent.status = 'online';
    broadcastAgents();
  }
}

// ---------- JSON extraction (balanced braces) ----------
function extractJSON(str) {
  let start = str.indexOf('{');
  if (start === -1) return null;
  let depth = 0;
  for (let i = start; i < str.length; i++) {
    if (str[i] === '{') depth++;
    else if (str[i] === '}') depth--;
    if (depth === 0) {
      try {
        return JSON.parse(str.substring(start, i+1));
      } catch (e) { return null; }
    }
  }
  return null;
}

// ---------- Execute action (planning mode) ----------
async function executeAction(agent, channelId, action) {
  const { type, payload } = action;
  console.log(`[ACTION] ${agent.name} executes ${type}`);
  switch (type) {
    case 'message':
      await handleAgentResponse(agent, channelId, payload.content);
      break;
    case 'research':
      const topic = payload.query || payload.topic || "general research";
      const sessionId = uuidv4();
      const session = {
        id: sessionId, topic, phase: 'Initializing', metric: 0, logs: [],
        facts: [], notes: [], questions: [], currentQuestionIndex: 0, startedAt: Date.now()
      };
      researchSessions.set(sessionId, session);
      runResearch(sessionId, topic, channelId).catch(console.error);
      addMessage(channelId, 'Siphon', 'system', `🔍 ${agent.name} started research on "${topic}". Check #siphon.`);
      broadcastToChannel(channelId, { sender: 'Siphon', content: `Research started by ${agent.name}: ${topic}`, senderType: 'system' });
      break;
    case 'code':
      const codePrompt = `Write code for: ${payload.description}. Output only the code block with language.`;
      const code = await queryOllama(agent.model, codePrompt, agent.systemPrompt, 0.5, agent.id);
      await handleAgentResponse(agent, channelId, `\`\`\`\n${code}\n\`\`\``);
      break;
    case 'delegate':
      const targetAgent = agents.get(payload.targetId);
      if (targetAgent) {
        addMessage(channelId, 'System', 'system', `${agent.name} delegates to ${targetAgent.name}: ${payload.task}`);
        broadcastToChannel(channelId, { sender: 'System', content: `${agent.name} → ${targetAgent.name}: ${payload.task}`, senderType: 'system' });
        const fakeMsg = { sender: agent.name, content: payload.task };
        agentRespond(targetAgent, channelId, fakeMsg).catch(console.error);
      }
      break;
    default:
      console.warn(`Unknown action: ${type}`);
  }
}

// ---------- Planning mode with failover ----------
async function agentPlanAndAct(agent, channelId, triggerMessage) {
  if (triggerMessage.sender === agent.name) return;
  const cooldownKey = `${agent.id}_${channelId}`;
  const lastResponse = agent.lastResponseTime.get(cooldownKey) || 0;
  if (Date.now() - lastResponse < 6000) return;

  agent.status = 'thinking';
  broadcastAgents();

  try {
    const context = buildConversationContext(channelId, agent.name);
    const systemPlanPrompt = `You are an autonomous agent. Output ONLY a JSON action: {"type":"message","payload":{"content":"..."}} or {"type":"research","payload":{"query":"..."}} or {"type":"code","payload":{"description":"..."}} or {"type":"delegate","payload":{"targetId":"agent_id","task":"..."}}.`;
    const userPlanPrompt = `Conversation:\n${context}\nLast message: ${triggerMessage.sender}: "${triggerMessage.content}"\nProject state: ${JSON.stringify(projectState)}\nNext action? JSON only.`;
    const reply = await queryOllama(agent.model, userPlanPrompt, systemPlanPrompt, 0.6, agent.id);
    let action = extractJSON(reply);
    if (!action || !action.type) {
      let fails = jsonFailCount.get(agent.id) || 0;
      fails++;
      jsonFailCount.set(agent.id, fails);
      if (fails >= 3) {
        console.log(`Agent ${agent.name} failed JSON 3 times, falling back to natural response`);
        jsonFailCount.set(agent.id, 0);
        await agentRespond(agent, channelId, triggerMessage, false);
        agent.lastResponseTime.set(cooldownKey, Date.now());
        return;
      }
      action = { type: 'message', payload: { content: reply.substring(0, 500) } };
    } else {
      jsonFailCount.set(agent.id, 0);
    }
    await executeAction(agent, channelId, action);
    agent.lastResponseTime.set(cooldownKey, Date.now());
  } catch (err) {
    console.error(`Plan/Act error for ${agent.name}:`, err);
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
  if (!channel || (!channel.researchActive && !channel.abstractActive && !projectState.active)) {
    if (channel.loopTimer) clearTimeout(channel.loopTimer);
    channel.loopTimer = null;
    return;
  }
  channel.loopTimer = null;
  const lastMsg = channel.messages[channel.messages.length - 1];
  if (!lastMsg) return;
  const relevantAgents = Array.from(agents.values()).filter(agent => agent.channels.includes(channel.name));
  for (const agent of relevantAgents) {
    if (projectState.active || channel.abstractActive) {
      await agentPlanAndAct(agent, channelId, lastMsg);
    } else {
      await agentRespond(agent, channelId, lastMsg, true);
    }
  }
  scheduleLoopRound(channelId);
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
  projectState.active = false;
}

// ---------- SIPHON Research (enhanced) ----------
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
    const text = $('body').text().replace(/\s+/g, ' ').trim();
    return text.substring(0, 8000);
  } catch (e) { return ''; }
}
// Cleanup old research sessions every hour
setInterval(() => {
  const now = Date.now();
  for (let [id, session] of researchSessions.entries()) {
    if (now - session.startedAt > 3600000) researchSessions.delete(id);
  }
}, 3600000);

async function runResearch(sessionId, topic, channelId) {
  const session = researchSessions.get(sessionId);
  if (!session) return;
  const update = (updates) => {
    Object.assign(session, updates);
    for (let [ws, client] of clients.entries()) {
      if (ws.readyState === WebSocket.OPEN && client.channelId === channelId) {
        ws.send(JSON.stringify({ type: 'research_update', sessionId, data: session }));
      }
    }
    if (updates.phase) {
      const banner = `🔬 **SIPHON Research** [${session.topic}]\nPhase: ${updates.phase} | Metric: ${(session.metric*100).toFixed(0)}%`;
      addMessage('siphon', 'Siphon', 'system', banner);
      broadcastToChannel('siphon', { sender: 'Siphon', content: banner, senderType: 'system' });
    }
  };
  update({ phase: 'Generating questions', metric: 0, logs: [`Starting research on: ${topic}`], facts: [], notes: [] });
  let researchModel = config.agents[0]?.model;
  if (!researchModel) {
    const models = await getOllamaModels();
    researchModel = models.find(m => m.includes('qwen') || m.includes('llama')) || models[0];
    if (!researchModel) researchModel = 'qwen2.5:0.5b';
  }
  const promptGen = `Generate 3 specific sub‑questions to answer for the topic: "${topic}". Output one question per line.`;
  const questionsRaw = await queryOllama(researchModel, promptGen, '', 0.7);
  const questions = questionsRaw.split('\n').filter(l => l.trim().length > 10).slice(0, 3);
  update({ questions, currentQuestionIndex: 0, logs: [...session.logs, `Generated ${questions.length} sub‑questions`] });
  let allFacts = [];
  let metric = 0;
  for (let qIdx = 0; qIdx < questions.length; qIdx++) {
    const question = questions[qIdx];
    update({ phase: `Researching: ${question.substring(0, 50)}`, currentQuestionIndex: qIdx });
    let urls = [];
    for (const sq of [`${topic} ${question}`]) {
      const results = await ddgSearch(sq, 3);
      urls.push(...results);
    }
    urls = [...new Set(urls)].slice(0, 5);
    update({ logs: [...session.logs, `Found ${urls.length} URLs for question ${qIdx+1}`] });
    let factsForQuestion = [];
    for (const url of urls) {
      const content = await scrapeText(url);
      if (!content) continue;
      const extractPrompt = `Extract up to 5 atomic facts from the text below that help answer: "${question}". Return each fact on a new line starting with "FACT:".\n\n${content.substring(0, 4000)}`;
      const factsRaw = await queryOllama(researchModel, extractPrompt, '', 0.3);
      const facts = factsRaw.split('\n')
        .filter(l => l.startsWith('FACT:'))
        .map(l => l.replace('FACT:', '').trim());
      factsForQuestion.push(...facts);
      update({ logs: [...session.logs, `Scraped ${url} → ${facts.length} facts`] });
      await new Promise(r => setTimeout(r, 500));
    }
    factsForQuestion = [...new Set(factsForQuestion)];
    allFacts.push(...factsForQuestion);
    update({ facts: allFacts, logs: [...session.logs, `Collected ${factsForQuestion.length} facts for question ${qIdx+1}`] });
    const synthesisPrompt = `Based on these facts, answer the question: "${question}"\n\nFacts:\n${factsForQuestion.join('\n')}\n\nWrite a concise answer (3‑5 sentences).`;
    const answer = await queryOllama(researchModel, synthesisPrompt, '', 0.5);
    const note = { question, answer, facts: factsForQuestion, timestamp: Date.now() };
    session.notes.push(note);
    update({ notes: session.notes, logs: [...session.logs, `Answered: ${question.substring(0, 60)}`] });
    try {
      const artifactPath = path.join(RESEARCH_DIR, `${sessionId}_q${qIdx}.json`);
      fs.writeFileSync(artifactPath, JSON.stringify(note, null, 2));
      await gitCommit(`Research ${session.topic} - question ${qIdx+1}`);
    } catch (e) { console.error('Research artifact save failed:', e); }
    metric = (qIdx + 1) / questions.length;
    update({ metric });
    if (metric >= 0.9) break;
  }
  update({ phase: 'Complete', metric, logs: [...session.logs, `Research finished. Metric = ${metric.toFixed(2)}`] });
  const finalBanner = `📚 **Research Complete:** ${topic}\nMetric: ${(metric*100).toFixed(0)}%\nFacts: ${allFacts.length}\nNotes: ${session.notes.length}\n\nUse \`/pull ${sessionId}\` to bring insights into any channel.`;
  addMessage('siphon', 'Siphon', 'system', finalBanner);
  broadcastToChannel('siphon', { sender: 'Siphon', content: finalBanner, senderType: 'system' });
}

// ---------- DM Helpers ----------
function createDM(participantIds, name = null) {
  const dmId = `dm_${uuidv4().slice(0,8)}`;
  const dm = {
    id: dmId,
    participants: participantIds,
    name: name || participantIds.join(', '),
    messages: []
  };
  dms.set(dmId, dm);
  if (!config.dms) config.dms = [];
  config.dms.push({ id: dmId, participants: participantIds, name: dm.name });
  const tmpConfig = configPath + '.tmp';
  fs.writeFileSync(tmpConfig, JSON.stringify(config, null, 2));
  fs.renameSync(tmpConfig, configPath);
  return dm;
}
function getUserDMs(userId) {
  const result = [];
  for (let dm of dms.values()) {
    if (dm.participants.includes(userId)) result.push(dm);
  }
  return result;
}
async function handleDMCommand(senderUserId, args, ws) {
  let raw = args.join(' ').trim();
  if (!raw) {
    ws.send(JSON.stringify({ type: 'error', message: 'Usage: /dm <username>' }));
    return;
  }
  if ((raw.startsWith('"') && raw.endsWith('"')) || (raw.startsWith("'") && raw.endsWith("'"))) raw = raw.slice(1, -1);
  const targetName = raw;
  let targetId = null;
  for (let [id, agent] of agents.entries()) {
    if (agent.name.toLowerCase() === targetName.toLowerCase()) { targetId = id; break; }
  }
  if (!targetId) {
    for (let [otherWs, client] of clients.entries()) {
      if (client.username && client.username.toLowerCase() === targetName.toLowerCase()) {
        targetId = client.userId; break;
      }
    }
  }
  if (!targetId) {
    ws.send(JSON.stringify({ type: 'error', message: `User "${targetName}" not found.` }));
    return;
  }
  let dm = Array.from(dms.values()).find(d => d.participants.includes(senderUserId) && d.participants.includes(targetId));
  if (!dm) dm = createDM([senderUserId, targetId]);
  const client = clients.get(ws);
  if (client) {
    client.dmId = dm.id;
    client.channelId = null;
    ws.send(JSON.stringify({ type: 'dm_joined', dmId: dm.id, messages: dm.messages }));
    const welcomeMsg = addMessage(dm.id, 'System', 'system', `Direct message started with ${targetName}.`);
    if (welcomeMsg) broadcastToDm(dm.id, welcomeMsg);
  }
}

// ---------- Cron Management ----------
async function wipeAllCronJobs() {
  try { await execPromise('crontab -r'); console.log('[CRON] Removed all user cron jobs.'); }
  catch (err) { console.log('[CRON] No crontab to remove.'); }
}
async function addHeartbeatCronJobs() {
  const channelIds = Array.from(channels.keys());
  const dmIds = Array.from(dms.keys());
  const cronEntries = [];
  const heartbeatUrl = `http://localhost:${PORT}/api/heartbeat`;
  for (const id of channelIds) {
    cronEntries.push(`*/5 * * * * curl -s -X POST "${heartbeatUrl}?type=channel&id=${id}" > /dev/null 2>&1`);
  }
  for (const id of dmIds) {
    cronEntries.push(`*/5 * * * * curl -s -X POST "${heartbeatUrl}?type=dm&id=${id}" > /dev/null 2>&1`);
  }
  if (cronEntries.length === 0) return;
  let existing = '';
  try {
    const { stdout } = await execPromise('crontab -l');
    existing = stdout;
  } catch (err) {}
  const lines = existing.split('\n').filter(line => line.trim() && !line.includes('/api/heartbeat'));
  const newCrontab = [...lines, ...cronEntries].join('\n') + '\n';
  const tmpFile = path.join(__dirname, '.tmpcron');
  fs.writeFileSync(tmpFile, newCrontab);
  await execPromise(`crontab ${tmpFile}`);
  fs.unlinkSync(tmpFile);
  console.log(`[CRON] Added ${cronEntries.length} heartbeat jobs.`);
}
async function resetApplicationData() {
  for (let ch of channels.values()) {
    ch.messages = [];
    ch.researchActive = false;
    ch.abstractActive = false;
    if (ch.loopTimer) clearTimeout(ch.loopTimer);
    ch.loopTimer = null;
  }
  for (let dm of dms.values()) dm.messages = [];
  researchSessions.clear();
  slimeSessions.clear();
  pinnedMessages.clear();
  userReactions.clear();
  global.errorLog = [];
  projectState = { active: false, title: null, goals: [], nextSteps: [], completedTasks: [], memory: {} };
  console.log('[CRON] Application data reset.');
}

// ---------- Express & WebSocket ----------
const app = express();
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json());

app.get('/api/models', async (req, res) => {
  res.json({ models: await getOllamaModels() });
});
app.get('/api/research/sessions', (req, res) => {
  const sessions = Array.from(researchSessions.values()).map(s => ({
    id: s.id, topic: s.topic, phase: s.phase, metric: s.metric,
    logs: s.logs.slice(-10), factsCount: s.facts.length,
    notesCount: s.notes.length, startedAt: s.startedAt
  }));
  res.json({ sessions });
});
app.get('/api/research/session/:id', (req, res) => {
  const session = researchSessions.get(req.params.id);
  if (!session) return res.status(404).json({ error: 'Session not found' });
  res.json(session);
});
app.get('/api/channels', (req, res) => {
  res.json({ channels: Array.from(channels.values()).map(c => ({ id: c.id, name: c.name })) });
});
app.get('/api/dms', (req, res) => {
  res.json({ dms: Array.from(dms.values()).map(dm => ({ id: dm.id, name: dm.name, participants: dm.participants })) });
});
app.get('/api/metrics', (req, res) => {
  const metricsObj = {};
  for (let [id, m] of agentMetrics.entries()) {
    metricsObj[id] = { cpu: m.cpu, mem: m.mem, activity: m.activity, timestamps: m.timestamps };
  }
  res.json({
    agents: Array.from(agents.values()).map(a => ({ id: a.id, name: a.name, model: a.model, status: a.status })),
    metrics: metricsObj
  });
});
app.post('/api/heartbeat', (req, res) => {
  console.log(`[HEARTBEAT] ${req.query.type} ${req.query.id} at ${new Date().toISOString()}`);
  res.status(200).send('OK');
});
app.post('/api/cron/wipe', async (req, res) => {
  try {
    await wipeAllCronJobs();
    await addHeartbeatCronJobs();
    await resetApplicationData();
    for (let [ws] of clients.entries()) {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'cron_reset' }));
    }
    res.json({ success: true });
  } catch (err) {
    logError({ source: 'cron_wipe', error: err.message });
    res.status(500).json({ success: false, error: err.message });
  }
});

// SLIME mobile endpoint (unchanged but functional)
app.get('/slime', (req, res) => {
  const { token, pin } = req.query;
  const session = slimeSessions.get(token);
  if (!session || session.pin !== pin || Date.now() > session.expiresAt) {
    return res.status(403).send(`<html><body><h1>Invalid or expired</h1></body></html>`);
  }
  const channelId = session.channelId;
  res.send(`<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>SLIME</title><style>body{background:#000;color:#0f0;font-family:monospace;padding:1rem}#messages{height:70vh;overflow:auto;border:1px solid #0f0;padding:0.5rem;margin-bottom:1rem}.msg{margin:0.5rem 0}.user{color:#0ff}.agent{color:#ff0}.system{color:#888}.input-area{display:flex;gap:0.5rem}input{flex:1;background:#111;border:1px solid #0f0;color:#0f0;padding:0.5rem}button{background:#0f0;color:#000;border:none;padding:0.5rem 1rem}</style></head><body><h2>SLIME · ${channelId}</h2><div id="messages"></div><div class="input-area"><input id="msgInput" placeholder="Message..."><button id="sendBtn">Send</button></div><script>let ws;let channel='${channelId}';let username='mobile_'+Math.floor(Math.random()*10000);function connect(){const protocol=location.protocol==='https:'?'wss:':'ws:';ws=new WebSocket(protocol+'//'+location.host);ws.onopen=()=>{ws.send(JSON.stringify({type:'join',channelId:channel}));ws.send(JSON.stringify({type:'set_username',username}))};ws.onmessage=e=>{const d=JSON.parse(e.data);if(d.type==='new_message'){const div=document.createElement('div');div.className='msg '+d.message.senderType;div.innerHTML='<strong>'+escapeHtml(d.message.sender)+'</strong> ['+new Date(d.message.timestamp).toLocaleTimeString()+']:<br>'+escapeHtml(d.message.content);document.getElementById('messages').appendChild(div);document.getElementById('messages').scrollTop=document.getElementById('messages').scrollHeight}else if(d.type==='history'){d.messages.forEach(msg=>{const div=document.createElement('div');div.className='msg '+msg.senderType;div.innerHTML='<strong>'+escapeHtml(msg.sender)+'</strong> ['+new Date(msg.timestamp).toLocaleTimeString()+']:<br>'+escapeHtml(msg.content);document.getElementById('messages').appendChild(div)})}};ws.onclose=()=>setTimeout(connect,3000)}function escapeHtml(s){return s.replace(/[&<>]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[m]))}document.getElementById('sendBtn').onclick=()=>{const input=document.getElementById('msgInput');if(input.value.trim()&&ws&&ws.readyState===WebSocket.OPEN){ws.send(JSON.stringify({type:'message',content:input.value}));input.value=''}};document.getElementById('msgInput').onkeypress=e=>{if(e.key==='Enter')document.getElementById('sendBtn').click()};connect();</script></body></html>`);
});

const server = app.listen(PORT, async () => {
  await ensureGitRepo();
  console.log(`\\x1b[32m✓ LACK v3.4.3 running at http://localhost:${PORT}\\x1b[0m`);
  console.log(`   Agents: ${Array.from(agents.values()).map(a => a.name).join(', ')}`);
  console.log(`   Enhanced: fixed agent loop, research TTL, DM consistency, graph metrics, error log to disk.`);
});

const wss = new WebSocket.Server({ server });
wss.on('connection', (ws) => {
  const userId = `human_${uuidv4().slice(0,4)}`;
  clients.set(ws, { username: userId, channelId: 'general', userId, dmId: null });
  ws.on('message', async (raw) => {
    try {
      const data = JSON.parse(raw);
      const client = clients.get(ws);
      if (!client) return;
      switch (data.type) {
        case 'join':
          if (channels.has(data.channelId)) {
            client.channelId = data.channelId; client.dmId = null;
            const channel = channels.get(data.channelId);
            ws.send(JSON.stringify({ type: 'history', channelId: data.channelId, messages: channel.messages }));
            ws.send(JSON.stringify({ type: 'agents_list', agents: Array.from(agents.values()).map(a => ({ id: a.id, name: a.name, model: a.model, systemPrompt: a.systemPrompt, channels: a.channels, status: a.status })) }));
            ws.send(JSON.stringify({ type: 'channels', channels: Array.from(channels.values()).map(c => ({ id: c.id, name: c.name })) }));
            ws.send(JSON.stringify({ type: 'dms', dms: getUserDMs(client.userId) }));
          }
          break;
        case 'join_dm':
          if (dms.has(data.dmId)) {
            client.dmId = data.dmId; client.channelId = null;
            const dm = dms.get(data.dmId);
            ws.send(JSON.stringify({ type: 'dm_history', dmId: data.dmId, messages: dm.messages }));
          }
          break;
        case 'message':
          if (client.channelId) {
            const msgText = data.content.trim();
            if (!msgText) break;
            const humanMsg = addMessage(client.channelId, client.username, 'human', msgText);
            if (humanMsg) {
              broadcastToChannel(client.channelId, humanMsg);
              await onHumanMessage(client.channelId, humanMsg, ws);
            }
          } else if (client.dmId) {
            const msgText = data.content.trim();
            if (!msgText) break;
            const humanMsg = addMessage(client.dmId, client.username, 'human', msgText);
            if (humanMsg) broadcastToDm(client.dmId, humanMsg);
          }
          break;
        case 'reply_in_thread':
          const { parentId, content: replyContent, channelId: threadChannelId } = data;
          if (threadChannelId && channels.has(threadChannelId)) {
            const replyMsg = addMessage(threadChannelId, client.username, 'human', replyContent, parentId);
            if (replyMsg) {
              broadcastToChannel(threadChannelId, replyMsg);
              const threadMsgs = getThreadMessages(threadChannelId, parentId);
              ws.send(JSON.stringify({ type: 'thread_messages', threadId: parentId, messages: threadMsgs }));
            }
          }
          break;
        case 'set_username':
          client.username = data.username.substring(0, 20);
          break;
        case 'spawn_agent':
          const { name, model, systemPrompt, channels: agentChannels } = data;
          const id = uuidv4().slice(0,8);
          const newAgent = { id, name, model, systemPrompt, channels: agentChannels, lastResponseTime: new Map(), status: 'online', statusMessage: '' };
          agents.set(id, newAgent);
          config.agents.push({ id, name, model, systemPrompt, channels: agentChannels });
          const tmpConfig = configPath + '.tmp';
          fs.writeFileSync(tmpConfig, JSON.stringify(config, null, 2));
          fs.renameSync(tmpConfig, configPath);
          agentMetrics.set(id, { cpu: Array(30).fill(0), mem: Array(30).fill(0), activity: Array(30).fill(0), timestamps: Array(30).fill(Date.now()) });
          jsonFailCount.set(id, 0);
          broadcastAgents();
          ws.send(JSON.stringify({ type: 'spawn_confirm', agent: newAgent }));
          break;
        case 'update_agent':
          const agent = agents.get(data.id);
          if (agent) {
            agent.name = data.name; agent.model = data.model; agent.systemPrompt = data.systemPrompt; agent.channels = data.channels;
            const idx = config.agents.findIndex(a => a.id === data.id);
            if (idx !== -1) {
              config.agents[idx] = { id: data.id, name: data.name, model: data.model, systemPrompt: data.systemPrompt, channels: data.channels };
              const tmp = configPath + '.tmp';
              fs.writeFileSync(tmp, JSON.stringify(config, null, 2));
              fs.renameSync(tmp, configPath);
            }
            broadcastAgents();
          }
          break;
        case 'get_models':
          ws.send(JSON.stringify({ type: 'models_list', models: await getOllamaModels() }));
          break;
        case 'add_reaction':
          const { messageId, emoji, channelId: reactChannelId } = data;
          if (!userReactions.has(messageId)) userReactions.set(messageId, new Map());
          const msgReactions = userReactions.get(messageId);
          if (!msgReactions.has(emoji)) msgReactions.set(emoji, new Set());
          msgReactions.get(emoji).add(client.userId);
          for (let [otherWs] of clients.entries()) {
            if (otherWs.readyState === WebSocket.OPEN) otherWs.send(JSON.stringify({ type: 'reaction_update', messageId, emoji, userId: client.userId, add: true }));
          }
          break;
      }
    } catch (err) {
      logError({ source: 'websocket_parse', error: err.message });
      ws.send(JSON.stringify({ type: 'error', message: 'Invalid message format' }));
    }
  });
  ws.on('close', () => clients.delete(ws));
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
      const help = `Commands: /ground, /research <topic>, /abstract, /plan <goal>, /stop, /list, /spawn, /siphon <topic>, /slime, /pull <id>, /dm <user>, /thread <id>, /pin <id>, /graph, /errorlog`;
      addMessage(channelId, 'System', 'system', help);
      broadcastToChannel(channelId, { sender: 'System', content: help, senderType: 'system' });
    } else if (cmd === 'ground') {
      const groundMsg = { sender: 'System', content: 'GROUND: All agents respond.' };
      addMessage(channelId, 'System', 'system', groundMsg.content);
      broadcastToChannel(channelId, groundMsg);
      const agentsInChannel = Array.from(agents.values()).filter(a => a.channels.includes(channel.name));
      for (const agent of agentsInChannel) agentRespond(agent, channelId, groundMsg, false);
    } else if (cmd === 'research' && args.length) {
      stopLoop(channelId);
      channel.researchActive = true;
      channel.researchTopic = args.join(' ');
      addMessage(channelId, 'System', 'system', `Research mode started on: ${channel.researchTopic}`);
      broadcastToChannel(channelId, { sender: 'System', content: `Research mode started on: ${channel.researchTopic}`, senderType: 'system' });
      scheduleLoopRound(channelId);
    } else if (cmd === 'abstract') {
      stopLoop(channelId);
      channel.abstractActive = true;
      addMessage(channelId, 'System', 'system', 'Abstract mode active – agents will plan actions.');
      broadcastToChannel(channelId, { sender: 'System', content: 'Abstract mode active – agents will plan actions.', senderType: 'system' });
      scheduleLoopRound(channelId);
    } else if (cmd === 'plan' && args.length) {
      stopLoop(channelId);
      projectState.active = true;
      projectState.title = args.join(' ');
      projectState.goals = [projectState.title];
      projectState.nextSteps = [];
      projectState.completedTasks = [];
      channel.abstractActive = true;
      addMessage(channelId, 'System', 'system', `📋 Project planning started: "${projectState.title}". Agents will collaborate.`);
      broadcastToChannel(channelId, { sender: 'System', content: `Project planning started: "${projectState.title}"`, senderType: 'system' });
      scheduleLoopRound(channelId);
    } else if (cmd === 'stop') {
      stopLoop(channelId);
    } else if (cmd === 'list') {
      const models = await getOllamaModels();
      const listText = models.length ? 'Available Ollama models:\n' + models.join('\n') : 'No Ollama models found.';
      addMessage(channelId, 'System', 'system', listText);
      broadcastToChannel(channelId, { sender: 'System', content: listText, senderType: 'system' });
    } else if (cmd === 'spawn') {
      ws.send(JSON.stringify({ type: 'models_list', models: await getOllamaModels() }));
    } else if (cmd === 'siphon') {
      const topic = args.join(' ') || 'general research topic';
      const sessionId = uuidv4();
      const session = { id: sessionId, topic, phase: 'Initializing', metric: 0, logs: [], facts: [], notes: [], questions: [], currentQuestionIndex: 0, startedAt: Date.now() };
      researchSessions.set(sessionId, session);
      runResearch(sessionId, topic, channelId).catch(console.error);
      addMessage(channelId, 'Siphon', 'system', `🔍 Started research on "${topic}". Check #siphon.`);
      broadcastToChannel(channelId, { sender: 'Siphon', content: `Research started: ${topic}`, senderType: 'system' });
    } else if (cmd === 'slime') {
      const token = uuidv4().replace(/-/g, '').substring(0,16);
      const pin = Math.floor(100000 + Math.random() * 900000).toString();
      const expiresAt = Date.now() + 60 * 60 * 1000;
      slimeSessions.set(token, { pin, expiresAt, channelId });
      const url = `http://localhost:${PORT}/slime?token=${token}&pin=${pin}`;
      addMessage(channelId, 'System', 'system', `📱 Mobile URL: ${url}  PIN: ${pin} (expires 1h)`);
      broadcastToChannel(channelId, { sender: 'System', content: `Mobile access: ${url}`, senderType: 'system' });
    } else if (cmd === 'pull' && args.length) {
      const session = researchSessions.get(args[0]);
      if (!session) {
        addMessage(channelId, 'System', 'system', `No session ${args[0]}.`);
        broadcastToChannel(channelId, { sender: 'System', content: `No session ${args[0]}.`, senderType: 'system' });
        return;
      }
      let summary = `📊 **Research "${session.topic}"**\nMetric: ${(session.metric*100).toFixed(0)}%\n`;
      if (session.notes.length) {
        const last = session.notes[session.notes.length-1];
        summary += `**Latest answer:** ${last.answer.substring(0,300)}\nKey facts:\n${last.facts.slice(0,3).map(f => `- ${f}`).join('\n')}`;
      } else { summary += 'Research still in progress.'; }
      addMessage(channelId, 'Siphon', 'system', summary);
      broadcastToChannel(channelId, { sender: 'Siphon', content: summary, senderType: 'system' });
    } else if (cmd === 'dm') {
      await handleDMCommand(getUserId(ws), args, ws);
    } else if (cmd === 'thread') {
      const messageId = args[0];
      if (!messageId) ws.send(JSON.stringify({ type: 'error', message: 'Usage: /thread <messageId>' }));
      else ws.send(JSON.stringify({ type: 'thread_messages', threadId: messageId, messages: getThreadMessages(channelId, messageId) }));
    } else if (cmd === 'pin') {
      if (!args[0]) ws.send(JSON.stringify({ type: 'error', message: 'Usage: /pin <messageId>' }));
      else { if (!pinnedMessages.has(channelId)) pinnedMessages.set(channelId, new Set()); pinnedMessages.get(channelId).add(args[0]); ws.send(JSON.stringify({ type: 'pinned', messageId: args[0], channelId })); }
    } else if (cmd === 'graph') {
      ws.send(JSON.stringify({ type: 'graph_ack' }));
    } else if (cmd === 'errorlog') {
      let logText = '**ERROR LOG**\n';
      const errors = global.errorLog || [];
      errors.slice(0,20).forEach(e => { logText += `${new Date(e.timestamp).toLocaleTimeString()} | ${e.agentId || 'system'}: ${e.error}\n`; });
      if (!errors.length) logText += 'No errors recorded.';
      addMessage(channelId, 'System', 'system', logText);
      broadcastToChannel(channelId, { sender: 'System', content: logText, senderType: 'system' });
    } else {
      addMessage(channelId, 'System', 'system', `Unknown command: ${cmd}. Type /help`);
      broadcastToChannel(channelId, { sender: 'System', content: `Unknown command: ${cmd}`, senderType: 'system' });
    }
    return;
  }
  const relevantAgents = Array.from(agents.values()).filter(a => a.channels.includes(channel.name));
  const usePlanning = projectState.active || channel.abstractActive || channel.researchActive;
  for (const agent of relevantAgents) {
    if (usePlanning) await agentPlanAndAct(agent, channelId, messageObj);
    else await agentRespond(agent, channelId, messageObj, false);
  }
}
'''

INDEX_HTML = r'''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>LACK v3.4.3 – Autonomous Agents + Cron Mgmt</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    :root { --white: #fff; --off-white: #f8f8f8; --light-gray: #e0e0e0; --gray: #a0a0a0; --dark-gray: #666; --black: #000; --shadow-dark: rgba(0,0,0,0.2); }
    .dark-mode { --white: #0a0a0a; --off-white: #1a1a1a; --light-gray: #2a2a2a; --gray: #555; --dark-gray: #999; --black: #f0f0f0; --shadow-dark: rgba(255,255,255,0.1); }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: monospace; }
    body { background: var(--white); color: var(--black); overflow: hidden; transition: 0.3s; }
    .neuro-menu { position: fixed; top: 0; left: 0; right: 0; height: 40px; background: var(--white); border-bottom: 2px solid var(--black); display: flex; align-items: center; padding: 0 20px; z-index: 10000; }
    .menu-item { padding: 0 16px; border-right: 1px solid var(--light-gray); font-size: 11px; font-weight: 600; }
    .neuro-status { margin-left: auto; display: flex; gap: 20px; align-items: center; font-size: 10px; }
    .dark-mode-toggle, .ground-btn, .cron-btn { background: var(--white); border: 1px solid var(--black); border-radius: 20px; padding: 4px 12px; cursor: pointer; }
    .cron-btn { background: #ff4444; color: white; border-color: #ff4444; }
    .neuro-desktop { position: absolute; top: 40px; left: 0; right: 0; bottom: 0; background: var(--off-white); padding: 20px; }
    .chat-container { background: var(--white); border: 2px solid var(--black); box-shadow: 8px 8px 0 var(--shadow-dark); width: 100%; height: 100%; display: flex; }
    .sidebar { width: 260px; border-right: 2px solid var(--black); display: flex; flex-direction: column; overflow-y: auto; background: var(--white); }
    .sidebar-section { border-bottom: 1px solid var(--light-gray); }
    .sidebar-header { padding: 12px; font-weight: 600; font-size: 12px; background: var(--off-white); cursor: pointer; }
    .sidebar-header i { margin-right: 6px; }
    .channel-list, .agent-list, .research-list, .dm-list { padding: 8px; }
    .channel-item, .agent-item, .research-item, .dm-item { padding: 8px; margin: 4px 0; cursor: pointer; border: 1px solid transparent; font-size: 11px; display: flex; align-items: center; gap: 8px; }
    .channel-item:hover, .agent-item:hover, .research-item:hover, .dm-item:hover { background: var(--light-gray); }
    .channel-item.active { background: var(--black); color: var(--white); }
    .agent-item { justify-content: space-between; }
    .agent-name { font-weight: 600; }
    .agent-model { font-size: 9px; color: var(--gray); }
    .agent-status { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-left: 6px; }
    .status-online { background: #2eb67d; }
    .status-thinking { background: #ecb22e; animation: pulse 1s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    .research-item { flex-direction: column; align-items: flex-start; }
    .research-title { font-weight: bold; }
    .research-progress { font-size: 9px; color: var(--gray); }
    .main-chat { flex: 1; display: flex; flex-direction: column; background: var(--white); }
    .chat-header { padding: 12px; border-bottom: 2px solid var(--black); font-weight: 600; background: var(--white); }
    .messages-area { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px; background: var(--off-white); }
    .message-group { margin-bottom: 8px; }
    .message { display: flex; gap: 12px; padding: 4px 0; }
    .message-avatar { width: 32px; height: 32px; background: var(--light-gray); border: 1px solid var(--black); display: flex; align-items: center; justify-content: center; font-weight: bold; }
    .message-content { flex: 1; }
    .message-sender { font-weight: 600; font-size: 12px; margin-bottom: 2px; }
    .message-timestamp { font-size: 9px; color: var(--dark-gray); margin-left: 8px; }
    .message-text { font-size: 12px; line-height: 1.4; word-wrap: break-word; }
    .message-text pre { background: #111; color: #0f0; padding: 8px; overflow-x: auto; }
    .message-actions { display: none; gap: 8px; margin-top: 4px; }
    .message:hover .message-actions { display: flex; }
    .action-icon { font-size: 10px; color: var(--dark-gray); cursor: pointer; padding: 2px 4px; border: 1px solid var(--light-gray); background: var(--white); }
    .reply-badge { font-size: 10px; color: var(--black); cursor: pointer; margin-top: 4px; text-decoration: underline; }
    .input-area { padding: 16px; border-top: 2px solid var(--black); display: flex; gap: 12px; background: var(--white); }
    .input-area textarea { flex: 1; background: var(--white); border: 1px solid var(--black); padding: 8px; font-family: monospace; resize: none; }
    .input-area button { background: var(--white); border: 2px solid var(--black); padding: 8px 16px; cursor: pointer; font-weight: bold; }
    .bottom-bar { position: fixed; bottom: 0; left: 0; right: 0; background: var(--white); border-top: 2px solid var(--black); padding: 6px 16px; font-size: 0.7rem; display: flex; justify-content: space-between; z-index: 10000; }
    .thread-panel { width: 320px; background: var(--white); border-left: 2px solid var(--black); display: none; flex-direction: column; }
    .thread-panel.open { display: flex; }
    .thread-header { padding: 12px; border-bottom: 2px solid var(--black); display: flex; justify-content: space-between; }
    .thread-messages { flex: 1; overflow-y: auto; padding: 12px; }
    .thread-input { padding: 12px; border-top: 1px solid var(--light-gray); display: flex; gap: 8px; flex-direction: column; }
    .thread-input textarea { width: 100%; padding: 6px; border: 1px solid var(--black); font-family: monospace; }
    .modal { display: none; position: fixed; z-index: 20000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); }
    .modal-content { background: var(--white); margin: 10% auto; padding: 20px; border: 2px solid var(--black); width: 450px; max-width: 90%; }
    .modal-content input, .modal-content select, .modal-content textarea { width: 100%; margin: 8px 0; padding: 6px; font-family: monospace; }
    .modal-buttons { display: flex; justify-content: flex-end; gap: 12px; margin-top: 16px; }
    .slash-suggestions { position: absolute; bottom: 100%; left: 0; background: var(--white); border: 1px solid var(--black); list-style: none; padding: 4px; margin-bottom: 4px; max-height: 150px; overflow-y: auto; z-index: 10; }
    .slash-suggestions li { padding: 4px 8px; cursor: pointer; font-size: 11px; }
    .slash-suggestions li:hover { background: var(--light-gray); }
  </style>
</head>
<body>
<div class="neuro-menu">
  <div class="menu-item">LACK v3.4.3</div>
  <div class="neuro-status">
    <span id="agentCount">Agents: 0</span>
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
      <div class="chat-header" id="currentChannelName">#general</div>
      <div class="messages-area" id="messagesArea"></div>
      <div class="input-area">
        <textarea id="messageInput" rows="1" placeholder="Type /help ..."></textarea>
        <button id="sendBtn">SEND</button>
      </div>
    </div>
    <div class="thread-panel" id="threadPanel">
      <div class="thread-header"><span>Thread</span><i class="fas fa-times" id="closeThreadBtn" style="cursor:pointer"></i></div>
      <div class="thread-messages" id="threadMessages"></div>
      <div class="thread-input"><textarea id="threadReplyInput" rows="2" placeholder="Reply..."></textarea><button id="sendThreadReply">Reply</button></div>
    </div>
  </div>
</div>
<div class="bottom-bar"><span>LACK · Fixed agent loop + enhanced research/DM/graph/cron</span><span id="statusText">CONNECTED</span></div>

<div id="agentModal" class="modal"><div class="modal-content"><h3>Edit Agent</h3><input type="text" id="editAgentId" hidden><label>Name:</label><input type="text" id="editAgentName"><label>Model:</label><select id="editAgentModel"></select><label>System Prompt:</label><textarea id="editAgentPrompt" rows="3"></textarea><label>Channels (comma):</label><input type="text" id="editAgentChannels"><div class="modal-buttons"><button id="saveAgentBtn">Save</button><button id="closeModalBtn">Cancel</button></div></div></div>
<div id="quickSwitcherModal" class="modal"><div class="modal-content"><input type="text" id="switcherInput" placeholder="Jump... Ctrl+K"><div class="shortcut-hint">Ctrl+K</div></div></div>
<div id="graphModal" class="modal"><div class="modal-content" style="width:820px; max-width:95%; height:620px; display:flex; flex-direction:column;"><div style="display:flex; justify-content:space-between;"><h3>🧪 Agent Resource Monitor</h3><button id="closeGraphBtn" style="background:none;border:none;font-size:24px;">✕</button></div><div style="flex:1; background:var(--off-white); margin:12px 0; border:2px solid var(--black);"><canvas id="agentGraph" width="780" height="420" style="width:100%; height:100%;"></canvas></div><div id="graphLegend" style="display:flex; gap:16px; flex-wrap:wrap; font-size:11px;"></div><div style="font-size:10px; text-align:center;">CPU (solid) & Activity (semi)</div></div></div>

<script>
let ws, currentChannelId = 'general', currentDmId = null, username = localStorage.getItem('lack_username') || 'human_' + Math.floor(Math.random()*1000), userId = '', agents = [], researchSessions = [], channels = [], dms = [], currentThreadId = null, graphInterval = null, graphCanvas, graphCtx, resizeListener = false;
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
}
function connect() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(protocol+'//'+location.host);
  ws.onopen = () => { document.getElementById('statusText').innerText = 'CONNECTED'; ws.send(JSON.stringify({type:'join',channelId:currentChannelId})); ws.send(JSON.stringify({type:'set_username',username})); };
  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    switch(d.type) {
      case 'channels': channels = d.channels; renderSidebar(); break;
      case 'dms': dms = d.dms; renderSidebar(); break;
      case 'agents_list': agents = d.agents; document.getElementById('agentCount').innerText = 'Agents: '+agents.length; renderSidebar(); break;
      case 'history': renderMessages(d.messages); break;
      case 'new_message': if(d.channelId === currentChannelId) appendMessage(d.message); break;
      case 'dm_history': renderMessages(d.messages); break;
      case 'new_dm_message': if(d.dmId === currentDmId) appendMessage(d.message); break;
      case 'research_update': fetchResearchSessions(); break;
      case 'thread_messages': renderThreadMessages(d.messages); currentThreadId = d.threadId; openThreadPanel(); break;
      case 'models_list': populateModelSelect(d.models); break;
      case 'spawn_confirm': appendSystemMessage('Agent '+d.agent.name+' created.'); break;
      case 'error': alert(d.message); break;
      case 'cron_reset': location.reload(); break;
    }
  };
  ws.onclose = () => { document.getElementById('statusText').innerText = 'DISCONNECTED'; setTimeout(connect,3000); };
}
function renderSidebar() {
  const sidebar = document.getElementById('sidebar'); if(!sidebar) return;
  sidebar.innerHTML = '';
  addSection('CHANNELS', channels.map(c => ({ id: c.id, name: '#'+c.name, type:'channel', icon:'fa-hashtag' })));
  addSection('DIRECT MESSAGES', dms.map(d => ({ id: d.id, name: d.name, type:'dm', icon:'fa-comment' })));
  addSection('AGENTS', agents.map(a => ({ id: a.id, name: a.name, type:'agent', icon:'fa-robot', status:a.status })));
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
    const div = document.createElement('div'); div.className = 'channel-item';
    div.innerHTML = `<i class="fas ${item.icon}"></i> ${escapeHtml(item.name)}`;
    if(item.status) { let s = document.createElement('span'); s.className = `agent-status status-${item.status}`; div.appendChild(s); }
    if(item.progress !== undefined) { let p = document.createElement('span'); p.style.fontSize='0.7rem'; p.style.marginLeft='auto'; p.innerText = `${Math.round(item.progress*100)}%`; div.appendChild(p); }
    div.onclick = () => {
      if(item.type === 'channel') switchToChannel(item.id);
      else if(item.type === 'dm') switchToDm(item.id);
      else if(item.type === 'agent') openEditModal(agents.find(a=>a.id===item.id));
      else if(item.type === 'research') sendCommand('/pull '+item.id);
    };
    itemsDiv.appendChild(div);
  });
  section.appendChild(itemsDiv); sidebar.appendChild(section);
}
function switchToChannel(id) { currentChannelId = id; currentDmId = null; const ch = channels.find(c=>c.id===id); document.getElementById('currentChannelName').innerText = ch ? '#'+ch.name : id; ws.send(JSON.stringify({type:'join',channelId:id})); closeThreadPanel(); }
function switchToDm(id) { currentDmId = id; currentChannelId = null; const dm = dms.find(d=>d.id===id); document.getElementById('currentChannelName').innerText = dm ? dm.name : 'DM'; ws.send(JSON.stringify({type:'join_dm',dmId:id})); closeThreadPanel(); }
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
  actions.innerHTML = `<i class="fas fa-reply action-icon" title="Reply"></i><i class="fas fa-plus-circle action-icon" title="React"></i><i class="fas fa-thumbtack action-icon" title="Pin"></i><i class="fas fa-copy action-icon" title="Copy"></i><i class="fas fa-share action-icon" title="Share"></i>`;
  actions.querySelector('.fa-reply').onclick = () => fetchThread(msg.id);
  actions.querySelector('.fa-plus-circle').onclick = () => showReactionPicker(msg.id);
  actions.querySelector('.fa-thumbtack').onclick = () => sendCommand(`/pin ${msg.id}`);
  actions.querySelector('.fa-copy').onclick = () => navigator.clipboard.writeText(msg.content);
  actions.querySelector('.fa-share').onclick = () => { const to = prompt('Share to channel or DM id:'); if(to) sendCommand(`/share ${msg.id} ${to}`); };
  contentDiv.appendChild(actions);
  div.appendChild(avatar); div.appendChild(contentDiv);
  return div;
}
function appendMessage(msg) { const container = document.getElementById('messagesArea'); const groupDiv = document.createElement('div'); groupDiv.className = 'message-group'; groupDiv.appendChild(createMessageElement(msg,true)); container.appendChild(groupDiv); container.scrollTop = container.scrollHeight; }
function appendSystemMessage(text) { const container = document.getElementById('messagesArea'); const div = document.createElement('div'); div.className = 'message'; div.innerHTML = `<div class="message-avatar">S</div><div class="message-content"><em>${escapeHtml(text)}</em></div>`; container.appendChild(div); container.scrollTop = container.scrollHeight; }
function fetchThread(mid) { ws.send(JSON.stringify({type:'reply_in_thread',parentId:mid,content:'',channelId:currentChannelId})); }
function renderThreadMessages(messages) { const container = document.getElementById('threadMessages'); container.innerHTML = ''; for(const msg of messages) { const div = document.createElement('div'); div.className = 'message'; div.innerHTML = `<strong>${escapeHtml(msg.sender)}</strong> ${formatTime(msg.timestamp)}<br>${formatCode(escapeHtml(msg.content))}`; container.appendChild(div); } container.scrollTop = container.scrollHeight; }
function sendThreadReply() { const txt = document.getElementById('threadReplyInput').value.trim(); if(txt && currentThreadId) { ws.send(JSON.stringify({type:'reply_in_thread',parentId:currentThreadId,content:txt,channelId:currentChannelId})); document.getElementById('threadReplyInput').value = ''; } }
function openThreadPanel() { document.getElementById('threadPanel').classList.add('open'); }
function closeThreadPanel() { document.getElementById('threadPanel').classList.remove('open'); currentThreadId = null; }
function sendMessage() { const input = document.getElementById('messageInput'); const txt = input.value.trim(); if(!txt || !ws) return; if(txt.startsWith('/spawn')) { handleSpawn(); input.value=''; return; } ws.send(JSON.stringify({type:'message',content:txt})); input.value=''; autoGrow(); }
function sendCommand(cmd) { if(ws) ws.send(JSON.stringify({type:'message',content:cmd})); }
function formatTime(ts) { return new Date(ts).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}); }
function formatCode(t) { return t.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>'); }
function autoGrow() { const ta = document.getElementById('messageInput'); ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight,200)+'px'; }
function handleSlash(e) { if(e.key !== '/') return; const input = e.target; if(input.selectionStart === 0 || input.value[input.selectionStart-1] === ' ') { if(slashTimeout) clearTimeout(slashTimeout); const existing = document.querySelector('.slash-suggestions'); if(existing) existing.remove(); const commands = ['help','ground','research','abstract','stop','list','spawn','siphon','slime','pull','dm','thread','pin','graph','errorlog','plan']; const sug = document.createElement('ul'); sug.className = 'slash-suggestions'; commands.forEach(cmd => { const li = document.createElement('li'); li.innerText = '/'+cmd; li.onclick = () => { input.value = '/'+cmd+' '; input.focus(); sug.remove(); }; sug.appendChild(li); }); input.parentNode.style.position = 'relative'; input.parentNode.appendChild(sug); slashTimeout = setTimeout(() => { if(sug.parentNode) sug.remove(); },5000); document.addEventListener('click', function close(e) { if(!sug.contains(e.target) && e.target !== input) { sug.remove(); document.removeEventListener('click', close); } }); } }
function showReactionPicker(mid) { const emojis = ['👍','❤️','😂','😮','😢','🔥']; const picker = document.createElement('div'); picker.style.position='fixed'; picker.style.background='var(--white)'; picker.style.border='1px solid var(--black)'; picker.style.borderRadius='20px'; picker.style.padding='4px'; picker.style.display='flex'; picker.style.gap='8px'; picker.style.zIndex=1000; emojis.forEach(emoji => { const btn = document.createElement('span'); btn.innerText=emoji; btn.style.cursor='pointer'; btn.style.fontSize='1.2rem'; btn.style.padding='4px'; btn.onclick = () => { ws.send(JSON.stringify({type:'add_reaction',messageId:mid,emoji,channelId:currentChannelId})); picker.remove(); }; picker.appendChild(btn); }); document.body.appendChild(picker); picker.style.left = (window.event.clientX-50)+'px'; picker.style.top = (window.event.clientY-40)+'px'; setTimeout(()=>picker.remove(),3000); }
function handleQuickSwitch() { const q = document.getElementById('switcherInput').value.toLowerCase(); const ch = channels.find(c=>c.name.toLowerCase().includes(q)); if(ch) switchToChannel(ch.id); const dm = dms.find(d=>d.name.toLowerCase().includes(q)); if(dm) switchToDm(dm.id); const ag = agents.find(a=>a.name.toLowerCase().includes(q)); if(ag) openEditModal(ag); document.getElementById('quickSwitcherModal').style.display='none'; }
function fetchResearchSessions() { fetch('/api/research/sessions').then(r=>r.json()).then(d=>{ researchSessions = d.sessions; renderSidebar(); }).catch(console.error); }
async function openEditModal(agent) { document.getElementById('editAgentId').value = agent.id; document.getElementById('editAgentName').value = agent.name; document.getElementById('editAgentPrompt').value = agent.systemPrompt; document.getElementById('editAgentChannels').value = agent.channels.join(','); const resp = await fetch('/api/models'); const data = await resp.json(); const sel = document.getElementById('editAgentModel'); sel.innerHTML = ''; (data.models||[]).forEach(m => { const opt = document.createElement('option'); opt.value=m; opt.textContent=m; if(m===agent.model) opt.selected=true; sel.appendChild(opt); }); document.getElementById('agentModal').style.display='block'; }
function populateModelSelect(models) { const sel = document.getElementById('editAgentModel'); if(sel) { sel.innerHTML = ''; models.forEach(m => { const opt = document.createElement('option'); opt.value=m; opt.textContent=m; sel.appendChild(opt); }); } }
function handleSpawn() { ws.send(JSON.stringify({type:'get_models'})); const orig = ws.onmessage; ws.onmessage = e => { const d = JSON.parse(e.data); if(d.type === 'models_list') { if(!d.models.length) alert('No Ollama models'); else { const name = prompt('Agent name:'); if(name) { const model = prompt('Model:',d.models[0]); const promptText = prompt('System prompt:','You are helpful.'); const channels = prompt('Channels (comma):','general').split(',').map(s=>s.trim()); ws.send(JSON.stringify({type:'spawn_agent',name,model,systemPrompt:promptText,channels})); } } ws.onmessage = orig; } else if(orig) orig(e); }; }
function escapeHtml(s) { return s.replace(/[&<>]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[m])); }
async function openGraphModal() { document.getElementById('graphModal').style.display='flex'; graphCanvas = document.getElementById('agentGraph'); if(!graphCanvas) return; resizeGraphCanvas(); await fetchAndDrawGraph(); if(graphInterval) clearInterval(graphInterval); graphInterval = setInterval(fetchAndDrawGraph,3000); if(!resizeListener) { window.addEventListener('resize',handleGraphResize); resizeListener=true; } }
function handleGraphResize() { if(document.getElementById('graphModal').style.display === 'flex') { resizeGraphCanvas(); fetchAndDrawGraph(); } }
function resizeGraphCanvas() { if(!graphCanvas) return; const container = graphCanvas.parentElement; const w = container.clientWidth, h = container.clientHeight; if(w===0||h===0) return; const dpr = window.devicePixelRatio||1; graphCanvas.width = w*dpr; graphCanvas.height = h*dpr; graphCanvas.style.width = w+'px'; graphCanvas.style.height = h+'px'; graphCtx = graphCanvas.getContext('2d'); graphCtx.setTransform(1,0,0,1,0,0); graphCtx.scale(dpr,dpr); }
async function fetchAndDrawGraph() { try { const res = await fetch('/api/metrics'); const data = await res.json(); if(!data.agents) return; const legend = document.getElementById('graphLegend'); const colors = ['#ff3b5c','#00f0ff','#39ff14','#ffeb3b','#c84cff']; legend.innerHTML = ''; data.agents.forEach((a,i) => { const c = colors[i%colors.length]; const d = document.createElement('div'); d.style.display='flex'; d.style.alignItems='center'; d.style.gap='6px'; d.style.fontSize='11px'; d.innerHTML = `<span style="display:inline-block;width:20px;height:3px;background:${c};border-radius:2px;"></span> ${escapeHtml(a.name)}`; legend.appendChild(d); }); drawGraph(data); } catch(e) { console.error(e); } }
function drawGraph(data) { if(!graphCtx||!graphCanvas) return; const container = graphCanvas.parentElement; const w = container.clientWidth, h = container.clientHeight; if(w===0||h===0) return; const isDark = document.body.classList.contains('dark-mode'); const bg = isDark?'#0a0a0a':'#f8f8f8'; const grid = isDark?'#2a2a2a':'#e0e0e0'; const text = isDark?'#f0f0f0':'#000'; graphCtx.clearRect(0,0,w,h); graphCtx.fillStyle=bg; graphCtx.fillRect(0,0,w,h); const pad=40, pw=w-2*pad, ph=h-2*pad; if(pw<=0||ph<=0) return; graphCtx.strokeStyle=grid; graphCtx.lineWidth=1; for(let i=0;i<=5;i++){ let y=pad+ph*(i/5); graphCtx.beginPath(); graphCtx.moveTo(pad,y); graphCtx.lineTo(w-pad,y); graphCtx.stroke(); } for(let i=0;i<=4;i++){ let x=pad+pw*(i/4); graphCtx.beginPath(); graphCtx.moveTo(x,pad); graphCtx.lineTo(x,h-pad); graphCtx.stroke(); } graphCtx.fillStyle=text; graphCtx.font='10px monospace'; graphCtx.fillText('100%',pad-30,pad+5); graphCtx.fillText('0%',pad-25,h-pad-5); graphCtx.fillText('Time →',w/2,h-10); const colors = ['#ff3b5c','#00f0ff','#39ff14','#ffeb3b','#c84cff']; let allZero=true; for(const a of data.agents){ const m=data.metrics[a.id]; if(m&&m.cpu&&m.cpu.some(v=>v>0)){ allZero=false; break; } } if(allZero){ graphCtx.fillStyle=text; graphCtx.font='12px monospace'; graphCtx.textAlign='center'; graphCtx.fillText('Waiting for agent activity...',w/2,h/2); graphCtx.textAlign='left'; return; } data.agents.forEach((a,idx)=>{ const m=data.metrics[a.id]; if(!m||!m.cpu||!m.activity) return; const cpu=m.cpu, act=m.activity; const col=colors[idx%colors.length]; graphCtx.beginPath(); graphCtx.strokeStyle=col; graphCtx.lineWidth=2.5; graphCtx.shadowBlur=3; graphCtx.shadowColor=col; for(let i=0;i<cpu.length;i++){ let x=pad+pw*(i/(cpu.length-1)); let y=h-pad-ph*(cpu[i]/100); if(i===0) graphCtx.moveTo(x,y); else graphCtx.lineTo(x,y); } graphCtx.stroke(); graphCtx.beginPath(); graphCtx.strokeStyle=col+'dd'; graphCtx.lineWidth=2; graphCtx.shadowBlur=0; for(let i=0;i<act.length;i++){ let x=pad+pw*(i/(act.length-1)); let y=h-pad-ph*(act[i]/100); if(i===0) graphCtx.moveTo(x,y); else graphCtx.lineTo(x,y); } graphCtx.stroke(); }); graphCtx.shadowBlur=0; }
document.getElementById('saveAgentBtn').onclick = () => { const id = document.getElementById('editAgentId').value, name = document.getElementById('editAgentName').value, model = document.getElementById('editAgentModel').value, prompt = document.getElementById('editAgentPrompt').value, channels = document.getElementById('editAgentChannels').value.split(',').map(s=>s.trim()); ws.send(JSON.stringify({type:'update_agent',id,name,model,systemPrompt:prompt,channels})); document.getElementById('agentModal').style.display='none'; };
document.getElementById('closeModalBtn').onclick = () => document.getElementById('agentModal').style.display='none';
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
  console.log('\\x1b[36m[ LACK v3.4.3 ] Starting (fixed loop + enhanced)...\\x1b[0m');
  if (!await checkOllama()) { console.error('\\x1b[31m✗ Ollama not running\\x1b[0m'); process.exit(1); }
  console.log('\\x1b[32m✓ Ollama detected\\x1b[0m');
  const server = spawn('node', ['server.js'], { stdio: 'inherit', cwd: projectRoot });
  server.on('error', (err) => { console.error('Failed to start server:', err); process.exit(1); });
  process.on('SIGINT', () => { server.kill('SIGINT'); process.exit(); });
}
main();
'''

# ----------------------------------------------------------------------
# Bootstrap
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
    print("=== LACK v3.4.3 – Fixed agent loop + enhanced research/DM/graph/error log + cron ===")
    create_directory("config")
    create_directory("public")
    create_directory("bin")
    create_directory("logs")

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
        run_command(["npm", "install", "express", "ws", "uuid", "axios", "cheerio", "html-to-text", "simple-git"])
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
    except Exception:
        print("⚠ Ollama not running. Agents will fail to respond.")

    threading.Thread(target=open_browser, daemon=True).start()
    print("\nStarting LACK v3.4.3 – agents now respect cooldown, JSON failsafe, research TTL, etc.")
    print("CRON button wipes all cron jobs, adds heartbeats, and resets data.\n")
    run_command(["node", "server.js"])

if __name__ == "__main__":
    main()
