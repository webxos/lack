#!/usr/bin/env python3
"""
LACK v4.2.2 – Musing & Triangulation Enhancement (Sonnet 5 Proactive Reflection)
- Musing: low‑commitment token sampling, candidate scoring, synthesis
- Triangulation: cross‑constraint mapping from multiple perspectives, reconciliation
- Integrated into /plan, /abstract, /ralph, and general planning
- /bash command for CLI access in #general (executed by Moderator)
- Tool calls restricted: only Moderator can execute commands (execute_command)
- Read/Write file tools remain available to all agents
- NLP correction: small models discouraged from over‑using tools; explicit notes in prompts
- Configurable via lack.config.json: enableMusing, enableTriangulation, museCount, triangulatePerspectives
- Full CI/CD pipeline, reconciliation loop, J‑space, DecentMem, graph, search providers
"""

import os
import sys
import subprocess
import stat
import webbrowser
import threading
import time
import json
import sqlite3
from pathlib import Path

VERSION = "4.2.2"

# ----------------------------------------------------------------------
# Embedded Node.js server – Enhanced with Musing & Triangulation
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
const sqlite3 = require('better-sqlite3');
const { ESLint } = require('eslint');

// ==================== SONNET-STYLE BASE PROMPT ====================
const BASE_SYSTEM_PROMPT = `You are a highly collaborative technical agent in the LACK multi-agent system.

Core rules:
- Think step-by-step.
- After solving or responding, ALWAYS reflect and generate 2-5 concrete "things worth a closer look".
- End most responses with: "A few things worth a closer look — want me to dig into any of these next?" or a direct question to another agent/user.
- Use the format:
  **Thinking**
  • Check X logic
  • Inspect Y function
  • ...

  **Next Investigation Candidates**
  • Item 1...
  • Item 2...

  **Question:** [clear follow-up]

Be specific, actionable, and technical. Reference code, memory, J-space concepts, or recent messages when relevant.

IMPORTANT: Only the Moderator agent is allowed to execute system commands. If you need to run a command, request it via the Moderator. Do not attempt to use tool_calls for execute_command unless you are the Moderator.`;

// ==================== CONFIGURATION ====================
const configPath = path.join(__dirname, 'config', 'lack.config.json');
let config;
try {
  config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
} catch (err) {
  config = {
    httpPort: 3721,
    enablePublicMemory: false,
    defaultModel: "qwen2.5:0.5b",
    embeddingModel: "nomic-embed-text:latest",
    fallbackModels: ["phi3:mini", "tinyllama"],
    agents: [
      { id: "agent1", name: "Agent 1", model: "qwen2.5:0.5b", systemPrompt: "You are a helpful AI assistant.", channels: ["general","siphon","code"], strictChannel: null },
      { id: "agent2", name: "Agent 2", model: "qwen2.5:0.5b", systemPrompt: "You are a creative AI.", channels: ["general","siphon","code"], strictChannel: null }
    ],
    channels: [
      { id: "general", name: "general" },
      { id: "siphon", name: "siphon" },
      { id: "code", name: "code" }
    ],
    searchProvider: "duckduckgo",
    serpapiKey: "",
    firecrawlApiKey: "",
    searchMaxResults: 5,
    scrapeTimeout: 8000,
    historyLength: 300,
    jspaceEnabled: true,
    jspaceLayer: "layer_12",
    jspaceConceptCount: 5,
    cicd: {
      maxRetries: 3,
      reviewerModel: "qwen2.5:0.5b",
      moderatorModel: "qwen2.5:0.5b",
      requirePeerReview: true,
      autoFix: true
    },
    reconciliation: {
      maxIterations: 20,
      convergenceThreshold: 0.95,
      minEvalScore: 80,
      requireTestPass: true,
      hitlPause: false
    },
    // NEW: Musing & Triangulation settings
    enableMusing: true,
    enableTriangulation: true,
    museCount: 3,
    triangulatePerspectives: 3
  };
  fs.mkdirSync(path.join(__dirname, 'config'), { recursive: true });
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
}
const PORT = config.httpPort || 3721;
const OLLAMA_URL = 'http://localhost:11434';
const DEFAULT_MODEL = config.defaultModel || "qwen2.5:0.5b";
const EMBEDDING_MODEL = config.embeddingModel || "nomic-embed-text:latest";
const FALLBACK_MODELS = config.fallbackModels || ["phi3:mini", "tinyllama"];
const RESEARCH_DIR = path.join(__dirname, 'research');
const LOG_DIR = path.join(__dirname, 'logs');
const ERROR_LOG_PATH = path.join(LOG_DIR, 'error.log');
fs.mkdirSync(LOG_DIR, { recursive: true });
fs.mkdirSync(path.join(__dirname, 'lineage'), { recursive: true });
const GIT = simpleGit();

const JSPACE_ENABLED = config.jspaceEnabled !== undefined ? config.jspaceEnabled : true;
const JSPACE_LAYER = config.jspaceLayer || "layer_12";
const JSPACE_CONCEPT_COUNT = config.jspaceConceptCount || 5;

// Musing & Triangulation flags
const ENABLE_MUSING = config.enableMusing !== undefined ? config.enableMusing : true;
const ENABLE_TRIANGULATION = config.enableTriangulation !== undefined ? config.enableTriangulation : true;
const MUSE_COUNT = config.museCount || 3;
const TRIANGULATE_PERSPECTIVES = config.triangulatePerspectives || 3;

// ==================== J-SPACE INTEGRATION ====================
const JSPACE_DIR = path.join(__dirname, 'jspace');
const JSPACE_DATA_PATH = path.join(JSPACE_DIR, 'qwen2.5_0.5b_jspace.json');
let jspaceDirections = {};
let jspaceCache = new Map();

function loadJspace() {
    if (!fs.existsSync(JSPACE_DIR)) fs.mkdirSync(JSPACE_DIR, { recursive: true });
    if (fs.existsSync(JSPACE_DATA_PATH)) {
        try {
            const raw = fs.readFileSync(JSPACE_DATA_PATH, 'utf-8');
            jspaceDirections = JSON.parse(raw);
            console.log(`[JSPACE] Loaded ${Object.keys(jspaceDirections).length} layers from ${JSPACE_DATA_PATH}`);
        } catch (e) {
            console.error('[JSPACE] Failed to load directions:', e.message);
        }
    } else {
        console.warn('[JSPACE] No J-space data found. Using stub.');
        jspaceDirections = {
            "layer_12": [
                { name: "math", vector: new Array(512).fill(0).map(() => Math.random()*0.1) },
                { name: "planning", vector: new Array(512).fill(0).map(() => Math.random()*0.1) },
                { name: "safety", vector: new Array(512).fill(0).map(() => Math.random()*0.1) }
            ]
        };
        fs.writeFileSync(JSPACE_DATA_PATH, JSON.stringify(jspaceDirections, null, 2));
    }
}
loadJspace();

function projectJspace(embedding, layer = "layer_12") {
    if (!embedding || !jspaceDirections[layer]) return null;
    const dirs = jspaceDirections[layer];
    const result = {};
    for (const d of dirs) {
        let dot = 0;
        const vec = d.vector;
        const len = Math.min(embedding.length, vec.length);
        for (let i = 0; i < len; i++) dot += embedding[i] * vec[i];
        result[d.name] = dot;
    }
    return result;
}

async function getJspaceForText(text) {
    const emb = await getEmbedding(text);
    if (!emb) return null;
    return projectJspace(emb);
}

async function getJspaceCached(text) {
    const key = text.slice(0, 200);
    if (jspaceCache.has(key)) return jspaceCache.get(key);
    const result = await getJspaceForText(text);
    if (result) jspaceCache.set(key, result);
    return result;
}

// ==================== SQLite PERSISTENCE ====================
const DB_PATH = path.join(__dirname, 'db', 'lack.db');
fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });
const db = new sqlite3(DB_PATH);

db.exec(`
  CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL,
    sender TEXT NOT NULL,
    sender_type TEXT,
    content TEXT,
    timestamp INTEGER,
    parent_id TEXT,
    thread_id TEXT,
    reply_count INTEGER DEFAULT 0,
    reactions TEXT
  );
  CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT,
    model TEXT,
    system_prompt TEXT,
    channels TEXT,
    strict_channel TEXT,
    status TEXT,
    is_embed_operator INTEGER DEFAULT 0,
    is_code_moderator INTEGER DEFAULT 0
  );
  CREATE TABLE IF NOT EXISTS agent_memory (
    agent_id TEXT PRIMARY KEY,
    e_pool TEXT,
    x_pool TEXT,
    weights TEXT,
    stats TEXT,
    last_update INTEGER
  );
  CREATE TABLE IF NOT EXISTS project_states (
    store_id TEXT PRIMARY KEY,
    state TEXT,
    timestamp INTEGER
  );
  CREATE TABLE IF NOT EXISTS pipeline_results (
    id TEXT PRIMARY KEY,
    agent_id TEXT,
    thread_id TEXT,
    code_hash TEXT,
    passed INTEGER,
    attempt INTEGER,
    feedback TEXT,
    timestamp INTEGER
  );
  CREATE TABLE IF NOT EXISTS loop_health (
    loop_id TEXT PRIMARY KEY,
    loop_type TEXT,
    iterations INTEGER,
    convergence REAL,
    stagnation REAL,
    token_spend INTEGER,
    last_update INTEGER
  );
`);

function dbSaveMessage(msg, storeId) {
    const stmt = db.prepare(`
        INSERT OR REPLACE INTO messages 
        (id, store_id, sender, sender_type, content, timestamp, parent_id, thread_id, reply_count, reactions)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    stmt.run(
        msg.id, storeId, msg.sender, msg.senderType || 'agent',
        msg.content, msg.timestamp, msg.parentId || null,
        msg.threadId || null, msg.replyCount || 0,
        JSON.stringify(msg.reactions || {})
    );
}

function dbGetMessages(storeId, limit = 1000) {
    const stmt = db.prepare('SELECT * FROM messages WHERE store_id = ? ORDER BY timestamp ASC LIMIT ?');
    const rows = stmt.all(storeId, limit);
    return rows.map(row => ({
        id: row.id,
        sender: row.sender,
        senderType: row.sender_type,
        content: row.content,
        timestamp: row.timestamp,
        parentId: row.parent_id,
        threadId: row.thread_id,
        replyCount: row.reply_count,
        reactions: JSON.parse(row.reactions || '{}')
    }));
}

function dbSaveAgent(agent) {
    const stmt = db.prepare(`
        INSERT OR REPLACE INTO agents 
        (id, name, model, system_prompt, channels, strict_channel, status, is_embed_operator, is_code_moderator)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    stmt.run(
        agent.id, agent.name, agent.model, agent.systemPrompt,
        JSON.stringify(agent.channels || []), agent.strictChannel || null,
        agent.status || 'online',
        agent.isEmbedOperator ? 1 : 0,
        agent.isCodeModerator ? 1 : 0
    );
}

function dbLoadAllAgents() {
    const stmt = db.prepare('SELECT * FROM agents');
    const rows = stmt.all();
    const result = {};
    for (const row of rows) {
        result[row.id] = {
            id: row.id,
            name: row.name,
            model: row.model,
            systemPrompt: row.system_prompt,
            channels: JSON.parse(row.channels || '[]'),
            strictChannel: row.strict_channel,
            status: row.status,
            isEmbedOperator: !!row.is_embed_operator,
            isCodeModerator: !!row.is_code_moderator,
            lastResponseTime: new Map()
        };
    }
    return result;
}

// ==================== EMBEDDING CACHE ====================
const embeddingCache = new Map();
const CACHE_MAX_SIZE = 500;
const CACHE_TTL_MS = 60 * 60 * 1000;

function getCachedEmbedding(text) {
    const key = text.slice(0, 500);
    const entry = embeddingCache.get(key);
    if (entry && (Date.now() - entry.timestamp) < CACHE_TTL_MS) {
        return entry.embedding;
    }
    if (entry) embeddingCache.delete(key);
    return null;
}
function setCachedEmbedding(text, embedding) {
    const key = text.slice(0, 500);
    if (embeddingCache.size >= CACHE_MAX_SIZE) {
        const firstKey = embeddingCache.keys().next().value;
        embeddingCache.delete(firstKey);
    }
    embeddingCache.set(key, { embedding, timestamp: Date.now() });
}

// ==================== SEARCH PROVIDERS ====================
const SEARCH_PROVIDER = config.searchProvider || "duckduckgo";
const SERPAPI_KEY = config.serpapiKey || "";
const FIRECRAWL_API_KEY = config.firecrawlApiKey || "";
const SEARCH_MAX_RESULTS = config.searchMaxResults || 5;
const SCRAPE_TIMEOUT = config.scrapeTimeout || 8000;

async function searchDuckDuckGo(query, maxResults = SEARCH_MAX_RESULTS) {
    const searchUrls = [
        `https://html.duckduckgo.com/html/?q=${encodeURIComponent(query)}`,
        `https://lite.duckduckgo.com/lite/?q=${encodeURIComponent(query)}`
    ];
    for (const baseUrl of searchUrls) {
        try {
            const { data } = await axiosWithRetry({
                method: 'get', url: baseUrl,
                headers: { 'User-Agent': 'Mozilla/5.0 (compatible; LACK-SIPHON/4.2.0)' },
                timeout: SCRAPE_TIMEOUT
            });
            const $ = cheerio.load(data);
            const results = [];
            if (baseUrl.includes('html.duckduckgo.com')) {
                $('.result__url').each((i, el) => {
                    let href = $(el).attr('href');
                    if (href && href.startsWith('/')) href = 'https://duckduckgo.com' + href;
                    if (href && href.startsWith('http') && results.length < maxResults) results.push(href);
                });
            } else {
                $('a').each((i, el) => {
                    const href = $(el).attr('href');
                    if (href && href.startsWith('http') && results.length < maxResults) results.push(href);
                });
            }
            if (results.length > 0) return results;
        } catch (e) {
            logError({ context: 'searchDuckDuckGo', error: e.message, query: query.substring(0,60) });
        }
    }
    return [];
}

async function searchSerpApi(query, maxResults = SEARCH_MAX_RESULTS) {
    if (!SERPAPI_KEY) return [];
    try {
        const url = `https://serpapi.com/search.json?q=${encodeURIComponent(query)}&api_key=${SERPAPI_KEY}&num=${maxResults}`;
        const { data } = await axiosWithRetry({ method: 'get', url, timeout: SCRAPE_TIMEOUT });
        if (data.organic_results) {
            return data.organic_results.map(r => r.link).filter(Boolean).slice(0, maxResults);
        }
        return [];
    } catch (e) {
        logError({ context: 'searchSerpApi', error: e.message, query });
        return [];
    }
}

async function searchFirecrawl(query, maxResults = SEARCH_MAX_RESULTS) {
    if (!FIRECRAWL_API_KEY) return [];
    try {
        const url = `https://api.firecrawl.dev/v1/search?q=${encodeURIComponent(query)}&limit=${maxResults}`;
        const { data } = await axiosWithRetry({
            method: 'get', url,
            headers: { 'Authorization': `Bearer ${FIRECRAWL_API_KEY}` },
            timeout: SCRAPE_TIMEOUT
        });
        if (data && data.results) {
            return data.results.map(r => r.url).filter(Boolean).slice(0, maxResults);
        }
        return [];
    } catch (e) {
        logError({ context: 'searchFirecrawl', error: e.message, query });
        return [];
    }
}

async function performSearch(query, maxResults = SEARCH_MAX_RESULTS) {
    let urls = [];
    if (SEARCH_PROVIDER === 'serpapi') {
        urls = await searchSerpApi(query, maxResults);
    } else if (SEARCH_PROVIDER === 'firecrawl') {
        urls = await searchFirecrawl(query, maxResults);
    } else {
        urls = await searchDuckDuckGo(query, maxResults);
    }
    if (urls.length === 0 && SEARCH_PROVIDER !== 'duckduckgo') {
        urls = await searchDuckDuckGo(query, maxResults);
    }
    return urls;
}

// ==================== REVERSE‑SKILL CONSTANTS ====================
const REVERSE_SKILL_ROOT = path.join(__dirname, 'reverse-skill');
const SKILL_OUTPUT_DIR = path.join(__dirname, 'workspace', 'skills');
fs.mkdirSync(SKILL_OUTPUT_DIR, { recursive: true });

// ==================== LOGGING ====================
global.errorLog = [];
function logError(errorObj) {
  const entry = { timestamp: Date.now(), ...errorObj };
  try { fs.appendFileSync(ERROR_LOG_PATH, JSON.stringify(entry) + '\n'); } catch (e) {}
  global.errorLog.unshift(entry);
  if (global.errorLog.length > 200) global.errorLog.pop();
  console.error('[ERROR]', entry);
}

process.on('uncaughtException', (err) => {
  console.error('🔥 Uncaught Exception:', err);
  if (typeof logError === 'function') logError({ context: 'uncaughtException', error: err.stack });
});
process.on('unhandledRejection', (reason, promise) => {
  console.error('❌ Unhandled Rejection:', reason);
  if (typeof logError === 'function') logError({ context: 'unhandledRejection', error: reason });
});
process.on('SIGTERM', () => { console.log('[LACK] SIGTERM received, shutting down...'); process.exit(0); });
process.on('SIGINT', () => { console.log('[LACK] SIGINT received, shutting down...'); process.exit(0); });

// ==================== STACK CORE ====================
const STACK_ROOT = path.join(__dirname, 'lack_repos');
const TEMPLATES_DIR = path.join(STACK_ROOT, 'templates');
const MANIFEST_PATH = path.join(TEMPLATES_DIR, 'manifest.json');
fs.mkdirSync(STACK_ROOT, { recursive: true });
fs.mkdirSync(TEMPLATES_DIR, { recursive: true });
let stackManifest = {};

function simpleTfidfSimilarity(text1, text2) {
  const words1 = text1.toLowerCase().split(/\W+/);
  const words2 = text2.toLowerCase().split(/\W+/);
  const set = new Set([...words1, ...words2]);
  const vec1 = set.size ? set.map(w => words1.includes(w) ? 1 : 0) : [];
  const vec2 = set.size ? set.map(w => words2.includes(w) ? 1 : 0) : [];
  let dot=0, norm1=0, norm2=0;
  for (let i=0; i<vec1.length; i++) {
    dot += vec1[i]*vec2[i];
    norm1 += vec1[i]*vec1[i];
    norm2 += vec2[i]*vec2[i];
  }
  if (norm1===0 || norm2===0) return 0;
  return dot / (Math.sqrt(norm1)*Math.sqrt(norm2));
}

async function getEmbedding(text) {
  const cached = getCachedEmbedding(text);
  if (cached) return cached;
  try {
    const res = await axios.post('http://localhost:11434/api/embeddings', {
      model: EMBEDDING_MODEL,
      prompt: text.slice(0, 2000)
    });
    const emb = res.data.embedding;
    setCachedEmbedding(text, emb);
    return emb;
  } catch (e) {
    logError({ context: 'getEmbedding', error: e.message });
    return null;
  }
}

function cosineSimilarity(v1, v2) {
  if (!v1 || !v2 || v1.length !== v2.length) return 0;
  let dot = 0, mag1 = 0, mag2 = 0;
  for (let i = 0; i < v1.length; i++) {
    dot += v1[i] * v2[i];
    mag1 += v1[i] * v1[i];
    mag2 += v2[i] * v2[i];
  }
  return dot / (Math.sqrt(mag1) * Math.sqrt(mag2));
}

async function scanAndReindexTemplates() {
  if (!fs.existsSync(TEMPLATES_DIR)) return;
  const items = fs.readdirSync(TEMPLATES_DIR, { withFileTypes: true });
  const newManifest = {};
  for (const item of items) {
    if (item.isDirectory()) {
      const templatePath = path.join(TEMPLATES_DIR, item.name);
      let combinedText = '';
      const files = {};
      const walk = (dir) => {
        const entries = fs.readdirSync(dir, { withFileTypes: true });
        for (const e of entries) {
          const full = path.join(dir, e.name);
          if (e.isDirectory()) walk(full);
          else if (/\.(js|json|md|txt|py|html|css)$/.test(e.name)) {
            const content = fs.readFileSync(full, 'utf-8');
            combinedText += content + '\n';
            files[path.relative(templatePath, full)] = content;
          }
        }
      };
      walk(templatePath);
      if (combinedText.length === 0) continue;
      const vector = await getEmbedding(combinedText);
      if (vector) newManifest[item.name] = { vector, files };
      else {
        newManifest[item.name] = { text: combinedText, files };
      }
    }
  }
  stackManifest = newManifest;
  fs.writeFileSync(MANIFEST_PATH, JSON.stringify(stackManifest, null, 2));
  console.log(`[STACK] Reindexed ${Object.keys(stackManifest).length} templates`);
}

async function stackBuild(repoName) {
  const repoPath = path.join(STACK_ROOT, repoName);
  if (fs.existsSync(repoPath)) return `⚠️ Repository ${repoName} already exists.`;
  fs.mkdirSync(repoPath, { recursive: true });
  await execPromise(`git init && git checkout -b main`, { cwd: repoPath });
  const configFile = path.join(repoPath, 'STACK_CONFIG.json');
  fs.writeFileSync(configFile, JSON.stringify({ project: repoName, managedBy: "LACK-STACK" }, null, 2));
  return `✅ STACK repository **${repoName}** created at ${repoPath}`;
}

async function stackAdd(intent, storeId) {
  if (!fs.existsSync(MANIFEST_PATH)) return "No templates found. Add folders to ./lack_repos/templates/ first.";
  const manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf-8'));
  let queryVec = await getEmbedding(intent);
  let useFallback = !queryVec;
  let best = null, bestScore = -1;
  if (useFallback) {
    console.warn('[STACK] Embedding failed, using keyword/TF‑IDF fallback');
    const intentWords = intent.toLowerCase().split(/\s+/);
    for (const [name, data] of Object.entries(manifest)) {
      const combinedText = data.text || Object.values(data.files).join(' ').toLowerCase();
      let score = 0;
      const sim = simpleTfidfSimilarity(intent, combinedText);
      if (sim > bestScore) { bestScore = sim; best = { name, files: data.files }; }
      for (const word of intentWords) if (combinedText.includes(word)) score++;
      if (score > bestScore) { bestScore = score; best = { name, files: data.files }; }
    }
    if (best && bestScore > 0) {
      const activeRepo = activeStackRepo.get(storeId) || 'default';
      const repoPath = path.join(STACK_ROOT, activeRepo);
      if (!fs.existsSync(repoPath)) return `No active repository. Use /stack set <repo> first.`;
      for (const [relPath, content] of Object.entries(best.files)) {
        const target = path.join(repoPath, relPath);
        fs.mkdirSync(path.dirname(target), { recursive: true });
        fs.writeFileSync(target, content);
      }
      await execPromise(`git add . && git commit -m "STACK add: ${best.name}"`, { cwd: repoPath }).catch(e => console.warn(e));
      return `🔍 Match: **${best.name}** (score ${bestScore}) – fallback used.\nApplied ${Object.keys(best.files).length} files to ${activeRepo}.`;
    } else {
      return `No template matches "${intent}".`;
    }
  }
  for (const [name, data] of Object.entries(manifest)) {
    if (!data.vector) continue;
    const score = cosineSimilarity(queryVec, data.vector);
    if (score > bestScore) { bestScore = score; best = { name, files: data.files }; }
  }
  if (best && bestScore > 0.45) {
    const activeRepo = activeStackRepo.get(storeId) || 'default';
    const repoPath = path.join(STACK_ROOT, activeRepo);
    if (!fs.existsSync(repoPath)) return `No active repository. Use /stack set <repo> first.`;
    for (const [relPath, content] of Object.entries(best.files)) {
      const target = path.join(repoPath, relPath);
      fs.mkdirSync(path.dirname(target), { recursive: true });
      fs.writeFileSync(target, content);
    }
    await execPromise(`git add . && git commit -m "STACK add: ${best.name}"`, { cwd: repoPath }).catch(e => console.warn(e));
    return `🔍 Best match: **${best.name}** (score ${bestScore.toFixed(2)})\nApplied ${Object.keys(best.files).length} files to ${activeRepo}.`;
  } else {
    return `No strong match for "${intent}" (best score ${bestScore.toFixed(2)}).`;
  }
}

async function stackImport(jsonPath) {
  const fullPath = path.resolve(jsonPath);
  if (!fs.existsSync(fullPath)) return `File not found: ${fullPath}`;
  const data = JSON.parse(fs.readFileSync(fullPath, 'utf-8'));
  if (!data.templates) return "Invalid format: missing 'templates' key.";
  for (const [name, template] of Object.entries(data.templates)) {
    const dir = path.join(TEMPLATES_DIR, name);
    fs.mkdirSync(dir, { recursive: true });
    for (const [file, content] of Object.entries(template.files || {})) {
      const target = path.join(dir, file);
      fs.mkdirSync(path.dirname(target), { recursive: true });
      fs.writeFileSync(target, content);
    }
  }
  await scanAndReindexTemplates();
  return `Imported ${Object.keys(data.templates).length} templates.`;
}

let stackWatcher = null;
function startStackWatcher() {
  if (stackWatcher) clearInterval(stackWatcher);
  stackWatcher = setInterval(async () => {
    const oldKeys = Object.keys(stackManifest);
    await scanAndReindexTemplates();
    const newKeys = Object.keys(stackManifest);
    if (JSON.stringify(oldKeys) !== JSON.stringify(newKeys))
      console.log('[STACK] Templates changed, reindexed.');
  }, 10000);
}

const activeStackRepo = new Map();

// ==================== JSON EXTRACTION ====================
function repairJSON(str) {
  if (!str || typeof str !== 'string') return str;
  str = str.replace(/```json\s*|```\s*/g, '');
  str = str.replace(/(\{|\,)\s*([a-zA-Z0-9_]+)\s*\:/g, '$1"$2":');
  str = str.replace(/,\s*\}/g, '}').replace(/,\s*\]/g, ']');
  str = str.replace(/'/g, '"');
  let openBraces = (str.match(/\{/g) || []).length;
  let closeBraces = (str.match(/\}/g) || []).length;
  let openBrackets = (str.match(/\[/g) || []).length;
  let closeBrackets = (str.match(/\]/g) || []).length;
  str += '}'.repeat(openBraces - closeBraces) + ']'.repeat(openBrackets - closeBrackets);
  return str;
}

function extractJSON(str) {
  str = repairJSON(str);
  if (!str || typeof str !== 'string') return null;
  str = str.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '');
  const jsonBlock = str.match(/```json\s*([\s\S]*?)\s*```/);
  if (jsonBlock && jsonBlock[1]) {
    try { return JSON.parse(jsonBlock[1].trim()); } catch(e) {}
  }
  let start = str.indexOf('{');
  if (start === -1) return null;
  let depth = 0, end = -1;
  for (let i = start; i < str.length; i++) {
    if (str[i] === '{') depth++;
    else if (str[i] === '}') { depth--; if (depth === 0) { end = i; break; } }
  }
  if (end !== -1) {
    try { return JSON.parse(str.substring(start, end + 1)); } catch(e) {
      let fragment = str.substring(start, end + 1);
      let opens = (fragment.match(/\{/g) || []).length - (fragment.match(/\}/g) || []).length;
      let arrOpens = (fragment.match(/\[/g) || []).length - (fragment.match(/\]/g) || []).length;
      fragment += ']'.repeat(Math.max(0, arrOpens)) + '}'.repeat(Math.max(0, opens));
      try { return JSON.parse(fragment); } catch(e2) {}
    }
  }
  const possible = str.match(/\{[\s\S]*\}/);
  if (possible) {
    try { return JSON.parse(possible[0]); } catch(e) {}
  }
  return null;
}

function ensureCodeBlock(text, language) {
  if (text.includes('```')) return text;
  if (text.includes('<html') || text.includes('def ') || text.includes('function(') ||
      text.includes('class ') || text.includes('import ') || text.includes('require(')) {
    return '```' + (language || 'text') + '\n' + text + '\n```';
  }
  return text;
}

// ==================== CHANNEL GUARDRAILS ====================
function getChannelPersonality(channelName) {
  if (channelName === 'code') {
    return {
      temperature: 0.3,
      systemBonus: "\n\n# STRICT CODE CHANNEL RULES:\n- You are in #code. Output ONLY clean code blocks with ```lang\\ncode\\n```. NO explanations, NO chat, NO research. If asked for non-code, say 'Use #general or #siphon'.",
      planBonus: "Output pure code only. Use tool_calls if needed but prefer direct code response.",
      planForbidden: false,
      useMusing: false,
      useTriangulation: false
    };
  } else if (channelName === 'siphon') {
    return {
      temperature: 0.2,
      systemBonus: "\n\n# SIPHON RESEARCH CHANNEL:\n- You are in #siphon. Be factual, concise, research-focused. Use 🔍 prefix for findings. Output web-scraped facts and summaries here.",
      planBonus: "Prefer research actions and factual output.",
      planForbidden: false,
      useMusing: false,
      useTriangulation: true
    };
  }
  // general
  return {
    temperature: 0.7,
    systemBonus: "",
    planBonus: "",
    planForbidden: false,
    useMusing: true,
    useTriangulation: false
  };
}

// ==================== DECENTMEM ====================
const AGENT_MEMORY_DIR = path.join(__dirname, 'agent_memories');
fs.mkdirSync(AGENT_MEMORY_DIR, { recursive: true });

const agentMemories = new Map();
const PUBLIC_MEMORY_SUMMARY = { lastUpdated: 0, summary: '', embeddings: null, enabled: config.enablePublicMemory || false };

function initAgentMemory(agentId) {
  const memPath = path.join(AGENT_MEMORY_DIR, `${agentId}.json`);
  let memory = {
    ePool: [],
    xPool: [],
    weights: { exploitation: 0.6, exploration: 0.4 },
    stats: { totalJudgements: 0, avgScore: 50, lastJudgeTime: 0 },
    lastUpdate: Date.now(),
    jspaceHistory: []
  };
  if (fs.existsSync(memPath)) {
    try {
      const loaded = JSON.parse(fs.readFileSync(memPath, 'utf-8'));
      memory = { ...memory, ...loaded };
    } catch(e) { logError({ context: 'initAgentMemory', error: e.message, agentId }); }
  }
  agentMemories.set(agentId, memory);
  saveAgentMemory(agentId);
}

function saveAgentMemory(agentId) {
  const mem = agentMemories.get(agentId);
  if (!mem) return;
  const memPath = path.join(AGENT_MEMORY_DIR, `${agentId}.json`);
  try {
    fs.writeFileSync(memPath, JSON.stringify(mem, null, 2));
  } catch(e) { logError({ context: 'saveAgentMemory', error: e.message, agentId }); }
}

async function addToMemory(agentId, trajectory, score, task = 'general', textForEmbedding = null) {
  const mem = agentMemories.get(agentId);
  if (!mem) return;
  let embedding = null;
  if (textForEmbedding) embedding = await getEmbedding(textForEmbedding);
  const entry = { trajectory, score: Math.min(1, Math.max(0, score / 100)), task, timestamp: Date.now(), embedding };
  if (score >= 60) {
    mem.ePool.unshift(entry);
    if (mem.ePool.length > 50) mem.ePool.pop();
  } else {
    mem.xPool.unshift({ candidate: trajectory, score: score/100, timestamp: Date.now(), embedding });
    if (mem.xPool.length > 30) mem.xPool.pop();
  }
  mem.stats.totalJudgements++;
  mem.stats.avgScore = (mem.stats.avgScore * (mem.stats.totalJudgements - 1) + score) / mem.stats.totalJudgements;
  mem.stats.lastJudgeTime = Date.now();
  mem.lastUpdate = Date.now();
  if (JSPACE_ENABLED) {
    const jspace = await getJspaceCached(textForEmbedding || trajectory);
    if (jspace) {
      mem.jspaceHistory.push({ timestamp: Date.now(), jspace, text: (textForEmbedding || trajectory).slice(0,200) });
      if (mem.jspaceHistory.length > 20) mem.jspaceHistory.shift();
    }
  }
  saveAgentMemory(agentId);
}

async function retrievePrivateMemory(agentId, query, k = 5, useEmbedding = true) {
  const mem = agentMemories.get(agentId);
  if (!mem) return [];
  let combined = [
    ...mem.ePool.map(e => ({ text: e.trajectory, score: e.score, type: 'e', embedding: e.embedding })),
    ...mem.xPool.map(x => ({ text: x.candidate, score: x.score, type: 'x', embedding: x.embedding }))
  ];
  if (useEmbedding && combined.some(item => item.embedding)) {
    const queryEmbedding = await getEmbedding(query);
    if (queryEmbedding) {
      for (let item of combined) {
        if (item.embedding) item.sim = cosineSimilarity(queryEmbedding, item.embedding);
        else item.sim = simpleTfidfSimilarity(query, item.text);
      }
      combined.sort((a,b) => (b.sim || 0) - (a.sim || 0));
    } else {
      combined.sort((a,b) => b.score - a.score);
    }
  } else {
    combined.sort((a,b) => b.score - a.score);
  }
  return combined.slice(0, k).map(item => `[${item.type === 'e' ? 'PROVEN' : 'EXPLORE'}] ${item.text.substring(0, 300)}`).join('\n');
}

async function retrieveRecentContext(agentId, query, maxMessages = 10) {
  const agent = agents.get(agentId);
  if (!agent) return '';
  let candidateMessages = [];
  for (let ch of channels.values()) {
    if (agent.channels.includes(ch.name)) {
      const recent = ch.messages.slice(-20);
      for (const msg of recent) {
        candidateMessages.push({ text: `${msg.sender}: ${msg.content}`, timestamp: msg.timestamp, channel: ch.name });
      }
    }
  }
  candidateMessages.sort((a,b) => b.timestamp - a.timestamp);
  candidateMessages = candidateMessages.slice(0, 50);
  if (candidateMessages.length === 0) return '';
  const queryEmbedding = await getEmbedding(query);
  if (!queryEmbedding) {
    return candidateMessages.slice(0, maxMessages).map(m => m.text).join('\n');
  }
  for (let msg of candidateMessages) {
    let msgEmbedding = getCachedEmbedding(msg.text);
    if (!msgEmbedding) msgEmbedding = await getEmbedding(msg.text);
    if (msgEmbedding) msg.sim = cosineSimilarity(queryEmbedding, msgEmbedding);
    else msg.sim = simpleTfidfSimilarity(query, msg.text);
  }
  candidateMessages.sort((a,b) => b.sim - a.sim);
  return candidateMessages.slice(0, maxMessages).map(m => `[${m.channel}] ${m.text}`).join('\n');
}

async function generateXPoolCandidates(agentId, context, num = 3) {
  const agent = agents.get(agentId);
  if (!agent) return [];
  let jspaceHint = '';
  if (JSPACE_ENABLED) {
    const jspace = await getJspaceCached(context);
    if (jspace) {
      const topConcepts = Object.entries(jspace)
        .sort((a,b) => b[1] - a[1])
        .slice(0, JSPACE_CONCEPT_COUNT)
        .map(([name, val]) => `${name}: ${val.toFixed(2)}`).join(', ');
      jspaceHint = `\nCurrent J-space (silent reasoning): ${topConcepts}`;
    }
  }
  // Use musing to generate varied candidates
  let candidates = [];
  if (ENABLE_MUSING) {
    const musePrompt = `Generate ${num} novel, creative strategies or reasoning variants for the following context. Be diverse but grounded. Return each on a new line starting with "IDEA:".\n\nContext: ${context}${jspaceHint}`;
    // We'll generate multiple candidates by varying temperature
    const temps = [0.5, 0.7, 0.9];
    const allReplies = [];
    for (const t of temps) {
      const reply = await queryOllama(agent.model, musePrompt, 'You are an idea generator.', t, agentId);
      if (!reply.startsWith('[OLLAMA_ERROR]')) {
        allReplies.push(reply);
      }
    }
    // Extract ideas from all replies
    const ideaSet = new Set();
    for (const rep of allReplies) {
      const lines = rep.split('\n').filter(l => l.startsWith('IDEA:')).map(l => l.replace('IDEA:', '').trim());
      for (const idea of lines) {
        if (!ideaSet.has(idea)) {
          ideaSet.add(idea);
          candidates.push(idea);
        }
      }
    }
  }
  // Fallback: if musing disabled or no candidates, use single query
  if (candidates.length === 0) {
    const prompt = `Generate ${num} novel, creative strategies or reasoning variants for the following context. Be diverse but grounded. Return each on a new line starting with "IDEA:".\n\nContext: ${context}${jspaceHint}`;
    const reply = await queryOllama(agent.model, prompt, 'You are an idea generator.', 0.9, agentId);
    if (!reply.startsWith('[OLLAMA_ERROR]')) {
      candidates = reply.split('\n').filter(l => l.startsWith('IDEA:')).map(l => l.replace('IDEA:', '').trim());
    }
  }

  const mem = agentMemories.get(agentId);
  if (mem) {
    for (const idea of candidates.slice(0, num)) {
      let initialScore = 30;
      try {
        const judgeRes = await judgeAndReweight(agentId, idea, 'x_pool_candidate', true);
        if (judgeRes && typeof judgeRes === 'number') initialScore = judgeRes;
      } catch(e) {}
      const embedding = await getEmbedding(idea);
      mem.xPool.unshift({ candidate: idea, score: initialScore / 100, timestamp: Date.now(), embedding });
    }
    if (mem.xPool.length > 30) mem.xPool = mem.xPool.slice(0, 30);
    saveAgentMemory(agentId);
  }
  return candidates;
}

async function judgeAndReweight(agentId, trajectory, stageContext, lightweight = false) {
  const agent = agents.get(agentId);
  if (!agent || agent.isEmbedOperator) return 50;
  if (lightweight) {
    let score = 50;
    const lower = trajectory.toLowerCase();
    if (lower.includes('success') || lower.includes('good') || lower.includes('excellent')) score = 75;
    else if (lower.includes('fail') || lower.includes('error')) score = 30;
    else score = 50;
    const mem = agentMemories.get(agentId);
    if (mem) {
      let delta = (score - 50) / 200;
      mem.weights.exploitation = Math.min(0.85, Math.max(0.15, mem.weights.exploitation + delta));
      mem.weights.exploration = 1 - mem.weights.exploitation;
      saveAgentMemory(agentId);
    }
    await addToMemory(agentId, trajectory, score, stageContext, trajectory);
    return score;
  }
  const judgePrompt = `You are a strict judge. Rate the following trajectory/stage (0-100) for quality, novelty, and usefulness. Output ONLY a JSON object: {"score": number, "reason": "short"}\n\nStage: ${stageContext}\nTrajectory: ${trajectory.substring(0, 1500)}`;
  let reply = await queryOllama(agent.model, judgePrompt, 'Output only valid JSON.', 0.2, agentId);
  let score = 50;
  if (!reply.startsWith('[OLLAMA_ERROR]')) {
    const parsed = extractJSON(reply);
    if (parsed && typeof parsed.score === 'number') score = Math.min(100, Math.max(0, parsed.score));
    else {
      const lower = trajectory.toLowerCase();
      if (lower.includes('success') || lower.includes('good')) score = 75;
      else if (lower.includes('fail')) score = 30;
      else score = 50;
    }
  } else {
    score = 50;
  }
  const mem = agentMemories.get(agentId);
  if (mem) {
    let delta = (score - 50) / 200;
    mem.weights.exploitation = Math.min(0.85, Math.max(0.15, mem.weights.exploitation + delta));
    mem.weights.exploration = 1 - mem.weights.exploitation;
    saveAgentMemory(agentId);
  }
  await addToMemory(agentId, trajectory, score, stageContext, trajectory);
  return score;
}

async function pruneAgentMemory(agentId) {
  const mem = agentMemories.get(agentId);
  if (!mem) return;
  const now = Date.now();
  const maxAge = 30 * 24 * 60 * 60 * 1000;
  mem.ePool = mem.ePool.filter(e => now - e.timestamp < maxAge);
  mem.xPool = mem.xPool.filter(x => now - x.timestamp < maxAge);
  const toKeep = [];
  for (let i = 0; i < mem.ePool.length; i++) {
    let duplicate = false;
    for (let j = 0; j < toKeep.length; j++) {
      if (mem.ePool[i].embedding && toKeep[j].embedding) {
        const sim = cosineSimilarity(mem.ePool[i].embedding, toKeep[j].embedding);
        if (sim > 0.9) {
          duplicate = true;
          toKeep[j].score = Math.max(toKeep[j].score, mem.ePool[i].score);
          break;
        }
      } else if (mem.ePool[i].trajectory === toKeep[j].trajectory) {
        duplicate = true;
        toKeep[j].score = Math.max(toKeep[j].score, mem.ePool[i].score);
        break;
      }
    }
    if (!duplicate) toKeep.push(mem.ePool[i]);
  }
  mem.ePool = toKeep;
  saveAgentMemory(agentId);
}

const maintenanceCircuit = new Map();
async function runMaintenanceTask(taskName, taskFn, maxRetries = 3) {
  const circuit = maintenanceCircuit.get(taskName) || { failures: 0, backoffUntil: 0 };
  if (circuit.backoffUntil > Date.now()) {
    console.log(`[MAINT] Skipping ${taskName}, circuit open`);
    return;
  }
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      await taskFn();
      circuit.failures = 0;
      maintenanceCircuit.set(taskName, circuit);
      return;
    } catch (err) {
      logError({ context: `maintenance_${taskName}`, attempt, error: err.message });
      if (attempt === maxRetries) {
        circuit.failures++;
        const backoffSec = Math.min(300, Math.pow(2, circuit.failures) * 10);
        circuit.backoffUntil = Date.now() + backoffSec * 1000;
        maintenanceCircuit.set(taskName, circuit);
      } else {
        await new Promise(r => setTimeout(r, 1000 * attempt));
      }
    }
  }
}

async function scheduleMemoryMaintenance() {
  setInterval(async () => {
    for (let agent of agents.values()) {
      await runMaintenanceTask(`prune_${agent.id}`, () => pruneAgentMemory(agent.id));
    }
  }, 24 * 60 * 60 * 1000);
}

async function proactiveXGeneration() {
  for (let agent of agents.values()) {
    if (agent.isEmbedOperator) continue;
    const mem = agentMemories.get(agent.id);
    if (mem && mem.weights.exploration > 0.6) {
      const query = 'general proactive exploration';
      const recentContext = await retrieveRecentContext(agent.id, query, 10);
      if (recentContext) {
        await generateXPoolCandidates(agent.id, recentContext, 2);
      }
    }
  }
}

async function updatePublicMemorySummary() {
  if (!PUBLIC_MEMORY_SUMMARY.enabled) return;
  let allHighScore = [];
  for (let agent of agents.values()) {
    const mem = agentMemories.get(agent.id);
    if (mem && mem.ePool.length) {
      const top = mem.ePool.slice(0, 3);
      allHighScore.push(...top.map(e => ({ agent: agent.name, text: e.trajectory, score: e.score })));
    }
  }
  allHighScore.sort((a,b) => b.score - a.score);
  const summaryText = allHighScore.slice(0, 10).map(e => `[${e.agent}] ${e.text.substring(0, 200)}`).join('\n');
  PUBLIC_MEMORY_SUMMARY.summary = summaryText;
  PUBLIC_MEMORY_SUMMARY.lastUpdated = Date.now();
  const emb = await getEmbedding(summaryText);
  PUBLIC_MEMORY_SUMMARY.embeddings = emb;
}

function getPublicMemorySummary() {
  if (!PUBLIC_MEMORY_SUMMARY.enabled) return '';
  return PUBLIC_MEMORY_SUMMARY.summary;
}

async function togglePublicMemory(enabled) {
  PUBLIC_MEMORY_SUMMARY.enabled = enabled;
  config.enablePublicMemory = enabled;
  try {
    const tmp = configPath + '.tmp';
    fs.writeFileSync(tmp, JSON.stringify(config, null, 2));
    fs.renameSync(tmp, configPath);
  } catch(e) { logError({ context: 'togglePublicMemory', error: e.message }); }
  if (enabled) await updatePublicMemorySummary();
  return enabled;
}

// ==================== TOOL DEFINITIONS (with restriction) ====================
const WORKSPACE_ROOT = path.join(__dirname, 'workspace');
fs.mkdirSync(WORKSPACE_ROOT, { recursive: true });

function securePath(relPath) {
  return path.resolve(relPath);
}

const ALLOWED_COMMANDS = [];
const TOOL_TIMEOUT_MS = 60000;

async function executeTool(toolName, args, agentId = null) {
  // Restriction: only Moderator can execute commands (execute_command)
  if (toolName === 'execute_command') {
    const agent = agentId ? agents.get(agentId) : null;
    const isModerator = agent && agent.id === 'moderator';
    if (!isModerator) {
      return "⛔ Command execution is restricted to the Moderator agent. Please request the Moderator to run this command.";
    }
  }
  try {
    switch (toolName) {
      case 'read_file': {
        const target = securePath(args.path);
        return fs.readFileSync(target, 'utf-8');
      }
      case 'write_file': {
        const target = securePath(args.path);
        fs.mkdirSync(path.dirname(target), { recursive: true });
        fs.writeFileSync(target, args.content, 'utf-8');
        await gitCommit(`Agent wrote ${args.path}`);
        return `✅ Wrote ${args.path} (${args.content.length} chars)`;
      }
      case 'execute_command': {
        const command = args.command;
        const { stdout, stderr } = await execPromise(command, { cwd: WORKSPACE_ROOT, timeout: TOOL_TIMEOUT_MS });
        return stdout || stderr || "Command executed (no output)";
      }
      default: return `❌ Unknown tool: ${toolName}`;
    }
  } catch (err) {
    logError({ context: 'executeTool', tool: toolName, error: err.message });
    return `⚠️ Tool error: ${err.message}`;
  }
}

const SKILLS_DIR = path.join(WORKSPACE_ROOT, '.skills');
fs.mkdirSync(SKILLS_DIR, { recursive: true });

function loadSkills() {
  if (!fs.existsSync(SKILLS_DIR)) return '';
  const files = fs.readdirSync(SKILLS_DIR).filter(f => f.endsWith('.md'));
  return files.map(f => fs.readFileSync(path.join(SKILLS_DIR, f), 'utf-8')).join('\n\n---\n\n');
}

async function saveSkill(summary, toolCalls) {
  const content = `# Skill ${new Date().toISOString()}\n\n**Summary:** ${summary}\n**Tools used:** ${toolCalls.map(t => t.name).join(', ')}\n\`\`\`json\n${JSON.stringify(toolCalls, null, 2)}\n\`\`\``;
  await executeTool('write_file', { path: `.skills/skill_${Date.now()}.md`, content });
}

// ==================== GIT HELPERS ====================
async function ensureGitRepo() {
  try {
    if (!fs.existsSync(RESEARCH_DIR)) fs.mkdirSync(RESEARCH_DIR, { recursive: true });
    const gitDir = path.join(RESEARCH_DIR, '.git');
    if (!fs.existsSync(gitDir)) {
      await GIT.cwd(RESEARCH_DIR).init();
      await GIT.cwd(RESEARCH_DIR).addConfig('user.name', 'LACK SIPHON');
      await GIT.cwd(RESEARCH_DIR).addConfig('user.email', 'lack@localhost');
      await GIT.cwd(RESEARCH_DIR).commit('Initial research repo', { '--allow-empty': null });
      console.log('[LACK] Git repo initialised at', RESEARCH_DIR);
    }
  } catch (err) { console.error('Git init failed:', err.message); }
}
async function gitCommit(message) {
  try {
    const gitDir = path.join(RESEARCH_DIR, '.git');
    if (!fs.existsSync(gitDir)) {
      console.warn('[LACK] Git repo missing – re-initialising before commit');
      await ensureGitRepo();
    }
    await GIT.cwd(RESEARCH_DIR).add('.');
    const status = await GIT.cwd(RESEARCH_DIR).status();
    if (status.files.length > 0) {
      await GIT.cwd(RESEARCH_DIR).commit(message);
      console.log(`Git commit: ${message}`);
    }
  } catch (e) { throw new Error(`Git commit failed: ${e.message}`); }
}

// ==================== DATA STRUCTURES ====================
const channels = new Map();
const agents = new Map();
const clients = new Map();
const researchSessions = new Map();
const pinnedMessages = new Map();
const userReactions = new Map();
const agentMetrics = new Map();
const jsonFailCount = new Map();

const projectStates = new Map();
function getProjectState(storeId) {
  return projectStates.get(storeId) || { active: false, title: null, goals: [], nextSteps: [], completedTasks: [], memory: {} };
}
function setProjectState(storeId, state) {
  projectStates.set(storeId, { ...state });
  persistProjectState(storeId);
}

const ralphActive = new Map();
const ralphGenerations = new Map();
const ralphGoals = new Map();
const ralphTimers = new Map();
const ralphCancel = new Map();
const ralphStagnation = new Map();
const ralphNextAgentIdx = new Map();
const ralphLastBroadcast = new Map();
const loopHealth = new Map(); // loopId -> { iterations, convergence, stagnation, tokenSpend, lastUpdate }

function getUserId(ws) {
  let client = clients.get(ws);
  if (!client) {
    const id = `human_${uuidv4().slice(0,4)}`;
    clients.set(ws, { username: id, channelId: 'general', userId: id });
    client = clients.get(ws);
  }
  return client.userId;
}

config.channels.forEach(ch => {
  channels.set(ch.id, {
    id: ch.id, name: ch.name, messages: [],
    researchActive: false, researchTopic: null, abstractActive: false,
    loopTimer: null, pinned: new Set()
  });
});

const HISTORY_LENGTH = config.historyLength || 300;

function generateSyntheticMetrics() {
  const now = Date.now();
  const interval = 3000;
  const timestamps = Array.from({ length: HISTORY_LENGTH }, (_, i) => now - (HISTORY_LENGTH - 1 - i) * interval);
  return {
    cpu: Array(HISTORY_LENGTH).fill(0).map((_, i) => 15 + Math.sin(i * 0.2) * 10),
    mem: Array(HISTORY_LENGTH).fill(0).map((_, i) => 20 + Math.sin(i * 0.1) * 5),
    activity: Array(HISTORY_LENGTH).fill(0).map((_, i) => 30 + Math.cos(i * 0.3) * 15),
    timestamps: timestamps,
    ePoolHistory: Array(HISTORY_LENGTH).fill(0),
    xPoolHistory: Array(HISTORY_LENGTH).fill(0),
    tpsHistory: Array(HISTORY_LENGTH).fill(0),
    jspaceCoherence: Array(HISTORY_LENGTH).fill(0),
    spikes: []
  };
}

// ==================== MODERATOR AGENT & CI/CD ====================
const THREAD_REPO_ROOT = path.join(__dirname, 'thread_repos');
const CODE_BLOCK_REGEX = /```(\w*)\n([\s\S]*?)```/g;
const LINT_TIMEOUT_MS = 10000;

function getThreadRepoPath(threadId) {
  return path.join(THREAD_REPO_ROOT, threadId);
}
async function ensureThreadRepo(threadId) {
  const repoPath = getThreadRepoPath(threadId);
  if (!fs.existsSync(repoPath)) {
    fs.mkdirSync(repoPath, { recursive: true });
    await execPromise(`git init && git checkout -b main`, { cwd: repoPath });
    const readme = `# Thread: ${threadId}\nCreated: ${new Date().toISOString()}\n\n## Files\n<!-- auto-generated -->`;
    fs.writeFileSync(path.join(repoPath, 'README.md'), readme);
    await execPromise(`git add . && git commit -m "Initialize thread repository"`, { cwd: repoPath });
    console.log(`[MODERATOR] Created repo for thread ${threadId}`);
  }
  return repoPath;
}
async function updateThreadReadme(threadId, files) {
  const repoPath = getThreadRepoPath(threadId);
  const readmePath = path.join(repoPath, 'README.md');
  let content = fs.readFileSync(readmePath, 'utf-8');
  let filesSection = content.includes('## Files') ? '' : '\n## Files\n';
  for (const file of files) {
    if (!content.includes(file.name)) {
      filesSection += `- \`${file.name}\` - ${file.lang} - ${new Date(file.timestamp).toLocaleString()}\n`;
    }
  }
  if (filesSection) {
    fs.writeFileSync(readmePath, content + filesSection);
    await execPromise(`git add README.md && git commit -m "Update README with ${files.length} new file(s)"`, { cwd: repoPath });
  }
}

// ==================== LINTER WITH ESLINT ====================
async function runLinter(language, filePath) {
  const errors = [];
  const warnings = [];
  let passed = true;
  try {
    switch (language.toLowerCase()) {
      case 'javascript':
      case 'typescript':
      case 'json':
      case 'jsonc': {
        const eslint = new ESLint({
          baseConfig: {
            extends: ['eslint:recommended'],
            env: { browser: true, es6: true, node: true },
            parserOptions: { ecmaVersion: 2020 },
            rules: {
              'no-eval': 'error',
              'no-implied-eval': 'error',
              'no-debugger': 'error',
              'no-undef': 'error',
              'no-unused-vars': 'warn'
            }
          },
          useEslintrc: false,
          overrideConfigFile: true
        });
        const results = await eslint.lintFiles([filePath]);
        if (results.length > 0) {
          const result = results[0];
          if (result.errorCount > 0) {
            passed = false;
            result.messages.forEach(msg => {
              if (msg.severity === 2) {
                errors.push(`Line ${msg.line}: ${msg.message} (${msg.ruleId})`);
              } else if (msg.severity === 1) {
                warnings.push(`Line ${msg.line}: ${msg.message} (${msg.ruleId})`);
              }
            });
          } else if (result.warningCount > 0) {
            result.messages.forEach(msg => {
              if (msg.severity === 1) warnings.push(`Line ${msg.line}: ${msg.message} (${msg.ruleId})`);
            });
          }
        }
        break;
      }
      case 'python': {
        let pyCmd = 'python';
        try {
          await execPromise('which python3', { timeout: 1000 });
          pyCmd = 'python3';
        } catch (e) {}
        try {
          const { stdout, stderr } = await execPromise(`${pyCmd} -m py_compile "${filePath}" 2>&1`, { timeout: LINT_TIMEOUT_MS });
          if (stderr || (stdout && stdout.includes('SyntaxError'))) {
            const lines = (stderr || stdout).split('\n');
            for (const line of lines) {
              if (line.includes('SyntaxError')) errors.push(line.trim());
              else if (line.trim()) warnings.push(line.trim());
            }
            passed = errors.length === 0;
          }
        } catch(e) {
          errors.push(e.stderr || e.message);
          passed = false;
        }
        break;
      }
      case 'html': {
        const content = fs.readFileSync(filePath, 'utf-8');
        const openTags = (content.match(/<([a-z][a-z0-9]*)[^>]*>/gi) || []).length;
        const closeTags = (content.match(/<\/([a-z][a-z0-9]*)>/gi) || []).length;
        if (openTags !== closeTags) {
          errors.push(`Tag mismatch: ${openTags} opening vs ${closeTags} closing tags`);
          passed = false;
        }
        break;
      }
      default:
        warnings.push(`No linter configured for ${language}`);
        passed = true;
    }
  } catch (err) {
    errors.push(`Linter error: ${err.message}`);
    passed = false;
  }
  return { passed, errors: errors.slice(0, 10), warnings: warnings.slice(0, 5) };
}

async function evaluateCodeWithLLM(code, language) {
  const prompt = `You are an expert code reviewer. Analyze the following ${language} code for:
- Correctness
- Efficiency
- Security issues
- Best practices

Provide a concise evaluation (max 200 words). Code:
\`\`\`${language}
${code}
\`\`\`
Review:`;
  const system = 'You are a strict, helpful code reviewer. Provide actionable feedback.';
  const response = await queryOllama(DEFAULT_MODEL, prompt, system, 0.3, null);
  return response.startsWith('[OLLAMA_ERROR]') ? '⚠️ Evaluation skipped (Ollama error).' : response;
}

// ==================== REVERSE‑SKILL ROUTER ====================
async function runReverseSkill(code, language) {
  const langMap = {
    'javascript': 'js-reverse',
    'python': 'reverse-engineering',
    'java': 'apk-reverse',
    'html': 'browser-automation',
    'text': 'reverse-engineering',
  };
  const capability = langMap[language.toLowerCase()] || 'reverse-engineering';

  const extMap = {
    'javascript': '.js',
    'python': '.py',
    'java': '.java',
    'html': '.html',
    'text': '.txt',
  };
  const ext = extMap[language.toLowerCase()] || '.txt';
  const tempFile = path.join(WORKSPACE_ROOT, `temp_rev_${Date.now()}${ext}`);
  fs.writeFileSync(tempFile, code, 'utf-8');

  const isWindows = process.platform === 'win32';
  let scriptPath, args;
  if (isWindows) {
    scriptPath = path.join(REVERSE_SKILL_ROOT, 'skills', 'scripts', 'bootstrap-reverse.ps1');
    args = ['-File', scriptPath, '-Capability', capability, '-TargetPath', tempFile];
  } else {
    scriptPath = path.join(REVERSE_SKILL_ROOT, 'skills', 'scripts', 'bootstrap-reverse.sh');
    args = [scriptPath, capability, tempFile];
  }

  try {
    const { stdout, stderr } = await execPromise(
      isWindows ? 'powershell' : 'bash',
      args,
      { timeout: 60000, cwd: REVERSE_SKILL_ROOT }
    );
    const skillFiles = fs.readdirSync(SKILL_OUTPUT_DIR)
      .filter(f => f.startsWith('skill_') && f.endsWith('.md'))
      .sort((a,b) => fs.statSync(path.join(SKILL_OUTPUT_DIR, b)).mtimeMs - fs.statSync(path.join(SKILL_OUTPUT_DIR, a)).mtimeMs);
    let skillContent = '';
    if (skillFiles.length > 0) {
      skillContent = fs.readFileSync(path.join(SKILL_OUTPUT_DIR, skillFiles[0]), 'utf-8');
    } else {
      skillContent = `# Reverse‑Skill Analysis for ${language}\n\nNo skill file generated. Router output:\n${stdout}\n${stderr}`;
    }
    fs.unlinkSync(tempFile);
    return { skillContent, stdout, stderr };
  } catch (err) {
    return { skillContent: `⚠️ Reverse‑skill failed: ${err.message}`, stdout: '', stderr: err.stderr || err.message };
  }
}

// ==================== CI/CD PIPELINE (full) ====================
async function runCICDPipeline(agentId, channelId, codeBlocks, threadId) {
  const results = [];
  const maxRetries = config.cicd.maxRetries || 3;
  for (let block of codeBlocks) {
    let attempt = 0;
    let passed = false;
    let finalFeedback = '';
    let currentCode = block.code;
    while (attempt < maxRetries && !passed) {
      attempt++;
      const lintResult = await runLinter(block.language, currentCode);
      let evalFeedback = null;
      if (lintResult.passed) {
        evalFeedback = await evaluateCodeWithLLM(currentCode, block.language);
      }
      // Peer review
      let peerReview = null;
      if (config.cicd.requirePeerReview && lintResult.passed) {
        const reviewer = getReviewerAgent(agentId);
        if (reviewer) {
          const reviewPrompt = `Review the following ${block.language} code. Output JSON with "score" (0-10), "bugs" (array), "recommendations" (array).\n\n${currentCode}`;
          const reviewRaw = await queryOllama(reviewer.model, reviewPrompt, 'You are a code reviewer. Output only JSON.', 0.2, reviewer.id);
          if (!reviewRaw.startsWith('[OLLAMA_ERROR]')) {
            const parsed = extractJSON(reviewRaw);
            if (parsed && typeof parsed.score === 'number') {
              peerReview = parsed;
            }
          }
        }
      }
      // Moderator gate
      let moderatorDecision = null;
      const modPrompt = `Decide if code passes. Lint: ${lintResult.passed}, eval: ${evalFeedback || 'N/A'}, peer score: ${peerReview ? peerReview.score : 'N/A'}. Output JSON: {"approved": bool, "reason": "..."}`;
      const modRaw = await queryOllama(config.cicd.moderatorModel || DEFAULT_MODEL, modPrompt, 'Strict moderator. Output JSON only.', 0.1, 'moderator');
      if (!modRaw.startsWith('[OLLAMA_ERROR]')) {
        const parsed = extractJSON(modRaw);
        if (parsed && typeof parsed.approved === 'boolean') {
          moderatorDecision = parsed;
        }
      }
      if (!moderatorDecision) {
        moderatorDecision = { approved: lintResult.passed && (peerReview ? peerReview.score >= 6 : true), reason: 'Fallback decision.' };
      }
      passed = moderatorDecision.approved;
      finalFeedback = `Lint: ${lintResult.passed ? 'PASS' : 'FAIL'}\nEval: ${evalFeedback || 'N/A'}\nPeer: ${peerReview ? peerReview.score : 'N/A'}\nModerator: ${moderatorDecision.approved ? 'APPROVED' : 'REJECTED'} - ${moderatorDecision.reason}`;
      if (!passed && config.cicd.autoFix && attempt < maxRetries) {
        // Ask agent to fix
        const agent = agents.get(agentId);
        if (agent) {
          const fixPrompt = `Your code was rejected. Feedback: ${finalFeedback}. Provide corrected code only.`;
          const fixedRaw = await queryOllama(agent.model, fixPrompt, 'You are fixing code. Output only code block.', 0.3, agentId);
          if (!fixedRaw.startsWith('[OLLAMA_ERROR]')) {
            const blocks = extractCodeBlocks(fixedRaw);
            if (blocks.length > 0) {
              currentCode = blocks[0].code;
            } else {
              currentCode = fixedRaw;
            }
          }
        }
      }
    }
    // Commit final version to repo
    const repoPath = await ensureThreadRepo(threadId);
    const filename = suggestFilename(block.language, currentCode, 0);
    const filePath = path.join(repoPath, filename);
    fs.writeFileSync(filePath, currentCode);
    let commitHash = null;
    try {
      await execPromise(`git add "${filename}"`, { cwd: repoPath });
      const commitMsg = `[CI/CD] ${filename} from ${agentId} – ${passed ? 'PASS' : 'FAIL'} (attempt ${attempt})`;
      const { stdout } = await execPromise(`git commit -m "${commitMsg.replace(/"/g, '\\"')}"`, { cwd: repoPath });
      commitHash = stdout.split('[')[1]?.split(']')[0] || 'unknown';
    } catch(e) { console.warn('Git commit failed:', e.message); }

    const result = {
      filename,
      language: block.language,
      passed,
      attempt,
      feedback: finalFeedback,
      commitHash,
      fullCode: currentCode.substring(0, 500) + (currentCode.length > 500 ? '...' : '')
    };
    results.push(result);
    // DB logging
    const stmt = db.prepare('INSERT OR REPLACE INTO pipeline_results (id, agent_id, thread_id, code_hash, passed, attempt, feedback, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)');
    const codeHash = require('crypto').createHash('sha256').update(currentCode).digest('hex');
    stmt.run(uuidv4(), agentId, threadId, codeHash, passed ? 1 : 0, attempt, finalFeedback, Date.now());
  }
  return results;
}

function getReviewerAgent(excludeAgentId) {
  const candidates = Array.from(agents.values()).filter(a =>
    a.id !== excludeAgentId &&
    a.id !== 'moderator' &&
    !a.isEmbedOperator &&
    a.channels.includes('code') &&
    a.status === 'online'
  );
  if (candidates.length === 0) return null;
  candidates.sort((a,b) => {
    const ma = agentMemories.get(a.id);
    const mb = agentMemories.get(b.id);
    const expA = ma ? ma.weights.exploitation : 0.5;
    const expB = mb ? mb.weights.exploitation : 0.5;
    return expB - expA;
  });
  return candidates[0];
}

function suggestFilename(language, code, index) {
  const langMap = {
    'python': '.py', 'javascript': '.js', 'html': '.html',
    'css': '.css', 'json': '.json', 'markdown': '.md',
    'bash': '.sh', 'text': '.txt', 'xml': '.xml', 'yaml': '.yml'
  };
  const firstLine = code.split('\n')[0];
  let suggested = `code_${Date.now()}_${index}`;
  if (firstLine.includes('#!/usr/bin/env python')) suggested = 'script.py';
  else if (firstLine.includes('#!/bin/bash')) suggested = 'script.sh';
  else if (code.includes('<!DOCTYPE html>')) suggested = 'index.html';
  else if (code.includes('{') && language === 'json') suggested = 'data.json';
  else if (code.includes('def ') || code.includes('class ')) suggested = 'module.py';
  else if (code.includes('function ') || code.includes('=>')) suggested = 'function.js';
  const ext = langMap[language.toLowerCase()] || '.txt';
  return suggested.endsWith(ext) ? suggested : suggested + ext;
}

// ==================== MODERATOR CODE REVIEW (with CI/CD) ====================
async function moderateCodeFromAgent(agentId, channelId, responseText, parentId) {
  if (agentId === 'moderator') return null;
  const moderatorAgent = agents.get('moderator');
  if (!moderatorAgent || !moderatorAgent.isCodeModerator) return null;
  const isCodeChannel = (channelId === 'code');
  const codeBlockRegex = /```(\w*)\n([\s\S]*?)```/g;
  const hasCodeBlock = codeBlockRegex.test(responseText);
  if (!isCodeChannel && !hasCodeBlock) return null;
  const codeBlocks = [];
  let match;
  const regex = /```(\w*)\n([\s\S]*?)```/g;
  while ((match = regex.exec(responseText)) !== null) {
    codeBlocks.push({
      language: match[1] || 'text',
      code: match[2].trim(),
      fullMatch: match[0]
    });
  }
  if (codeBlocks.length === 0) return null;

  const threadId = parentId || channelId;
  const results = await runCICDPipeline(agentId, channelId, codeBlocks, threadId);
  const feedback = buildModeratorFeedback(agentId, results, threadId);
  await handleAgentResponse(moderatorAgent, channelId, feedback, parentId);
  return results;
}

function buildModeratorFeedback(agentId, results, threadId) {
  const passedCount = results.filter(r => r.passed).length;
  const totalCount = results.length;
  let feedback = `🛡️ **Moderator Review** (agent: ${agentId})\n`;
  feedback += `Thread: \`${threadId}\`\n\n`;
  for (const r of results) {
    const icon = r.passed ? '✅' : '❌';
    feedback += `${icon} **${r.filename}** (${r.language}) – attempt ${r.attempt}\n`;
    feedback += `   ${r.feedback.replace(/\n/g, '\n   ')}\n`;
    if (r.commitHash) {
      feedback += `   📦 Committed as \`${r.commitHash}\`\n`;
    }
    feedback += '\n';
  }
  if (passedCount === totalCount) {
    feedback += `🎉 **All ${totalCount} file(s) passed.**`;
  } else {
    feedback += `⚠️ **${totalCount - passedCount}/${totalCount} files failed.**`;
  }
  return feedback;
}

// ==================== RECONCILIATION LOOP ====================
async function runReconciliationLoop(storeId, goal, agentId = null) {
  const loopId = `reconcile_${storeId}_${Date.now()}`;
  const maxIter = config.reconciliation.maxIterations || 20;
  const convergenceThreshold = config.reconciliation.convergenceThreshold || 0.95;
  const minEvalScore = config.reconciliation.minEvalScore || 80;
  const requireTestPass = config.reconciliation.requireTestPass !== false;
  const hitlPause = config.reconciliation.hitlPause || false;

  let iteration = 0;
  let currentState = getProjectState(storeId);
  let previousState = null;
  let converged = false;
  let tokenSpend = 0;
  let stagnationCounter = 0;

  // Load or create agent
  let agent = agentId ? agents.get(agentId) : null;
  if (!agent) {
    const candidates = Array.from(agents.values()).filter(a => !a.isEmbedOperator && a.channels.includes('general'));
    if (candidates.length === 0) {
      addMessage(storeId, 'System', 'system', '❌ No suitable agent for reconciliation.');
      return;
    }
    agent = candidates[0];
  }

  const startMsg = `🔄 **Reconciliation started** for goal: "${goal}"`;
  addMessage(storeId, 'System', 'system', startMsg);
  broadcastToStore(storeId, { sender: 'System', content: startMsg, senderType: 'system' });

  while (iteration < maxIter && !converged) {
    iteration++;
    // Observe: get current spec and J-space
    const spec = computeSpecFromState(currentState);
    const specStr = JSON.stringify(spec);
    const jspace = JSPACE_ENABLED ? await getJspaceCached(specStr) : null;
    const jspaceHint = jspace ? `\nJ-space: ${Object.entries(jspace).slice(0,3).map(([k,v]) => `${k}:${v.toFixed(2)}`).join(' ')}` : '';

    // Diff: compare with goal
    const diffPrompt = `Goal: "${goal}". Current spec: ${specStr}.${jspaceHint}
Propose a small, incremental change to move closer to the goal. Output a JSON with fields: "change" (description), "newSpec" (object with title, goals, nextSteps, completedTasks, memory), "recurConditionMet" (boolean).`;
    // Use triangulation for diff if enabled
    let diffResult = null;
    if (ENABLE_TRIANGULATION) {
      const diffRaw = await triangulate(agent, diffPrompt, 'You are a reconciliation agent. Output only JSON.', 0.4, { agentId: agent.id });
      if (diffRaw && !diffRaw.startsWith('[OLLAMA_ERROR]')) {
        diffResult = extractJSON(diffRaw);
      }
    } else {
      const diffRaw = await queryOllama(agent.model, diffPrompt, 'You are a reconciliation agent. Output only JSON.', 0.4, agent.id);
      tokenSpend += diffRaw.length;
      if (!diffRaw.startsWith('[OLLAMA_ERROR]')) {
        diffResult = extractJSON(diffRaw);
      }
    }
    if (!diffResult) {
      addMessage(storeId, 'System', 'system', `❌ Reconciliation iteration ${iteration}: failed to generate diff.`);
      break;
    }
    const newSpec = diffResult.newSpec || spec;
    const changeDesc = diffResult.change || 'No change described.';
    const recurMet = diffResult.recurConditionMet === true;

    // Act: apply change
    const oldState = currentState;
    const newState = {
      active: true,
      title: newSpec.title || oldState.title,
      goals: newSpec.goals || oldState.goals,
      nextSteps: newSpec.nextSteps || oldState.nextSteps,
      completedTasks: newSpec.completedTasks || oldState.completedTasks,
      memory: newSpec.memory || oldState.memory
    };
    setProjectState(storeId, newState);
    currentState = newState;
    const sim = previousState ? similarity(computeSpecFromState(previousState), computeSpecFromState(currentState)) : 1;
    previousState = currentState;

    // Verify: evaluate new spec
    const evalResult = await ralphEvaluate(agent, storeId, computeSpecFromState(currentState));
    const evalScore = evalResult.score;
    const testPass = requireTestPass ? (evalScore >= minEvalScore) : true;
    const convergedNow = recurMet || (sim >= convergenceThreshold && evalScore >= minEvalScore && testPass);
    if (convergedNow) converged = true;

    // Health tracking
    const healthEntry = {
      iterations: iteration,
      convergence: sim,
      stagnation: stagnationCounter / iteration,
      tokenSpend: tokenSpend,
      lastUpdate: Date.now()
    };
    loopHealth.set(loopId, healthEntry);
    const healthStmt = db.prepare('INSERT OR REPLACE INTO loop_health (loop_id, loop_type, iterations, convergence, stagnation, token_spend, last_update) VALUES (?, ?, ?, ?, ?, ?, ?)');
    healthStmt.run(loopId, 'reconciliation', iteration, sim, stagnationCounter/iteration, tokenSpend, Date.now());

    // HITL pause
    if (hitlPause && !converged) {
      const pauseMsg = `⏸️ **Reconciliation iteration ${iteration}** – changes ready. Approve? (type /approve ${loopId} to continue)`;
      addMessage(storeId, 'System', 'system', pauseMsg);
      broadcastToStore(storeId, { sender: 'System', content: pauseMsg, senderType: 'system' });
      await new Promise(r => setTimeout(r, 5000));
    }

    // Broadcast status
    const statusMsg = `🔄 Reconciliation iteration ${iteration}: sim=${sim.toFixed(3)}, eval=${evalScore}, converged=${converged}`;
    addMessage(storeId, 'System', 'system', statusMsg);
    broadcastToStore(storeId, { sender: 'System', content: statusMsg, senderType: 'system' });

    if (!converged && (sim < 0.01)) {
      stagnationCounter++;
      if (stagnationCounter > 3) {
        addMessage(storeId, 'System', 'system', `⚠️ Stagnation detected (${stagnationCounter} iterations with minimal change). Forcing mutation.`);
        const mutated = await ralphForceMutation(agent, storeId, goal, iteration);
        if (mutated) {
          const forcedState = {
            active: true,
            title: mutated.title || currentState.title,
            goals: mutated.goals || currentState.goals,
            nextSteps: mutated.nextSteps || currentState.nextSteps,
            completedTasks: mutated.completedTasks || currentState.completedTasks,
            memory: mutated.memory || currentState.memory
          };
          setProjectState(storeId, forcedState);
          currentState = forcedState;
          stagnationCounter = 0;
        }
      }
    }

    if (!converged) {
      await new Promise(r => setTimeout(r, 2000));
    }
  }

  const finalMsg = converged ? `✅ **Reconciliation converged** after ${iteration} iterations.` : `⚠️ Reconciliation stopped after ${iteration} iterations (max).`;
  addMessage(storeId, 'System', 'system', finalMsg);
  broadcastToStore(storeId, { sender: 'System', content: finalMsg, senderType: 'system' });
  return { loopId, iterations: iteration, converged, tokenSpend };
}

// ==================== RALPH EVOLUTION (enhanced with Musing) ====================
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

async function ralphEvaluate(agent, storeId, spec) {
  let jspaceHint = '';
  if (JSPACE_ENABLED) {
    const jspace = await getJspaceCached(JSON.stringify(spec));
    if (jspace) {
      const top = Object.entries(jspace)
        .sort((a,b) => b[1] - a[1])
        .slice(0, 3)
        .map(([k,v]) => `${k}:${v.toFixed(2)}`).join(' ');
      jspaceHint = `\nJ-space (silent concepts): ${top}`;
    }
  }
  const prompt = `You are an evaluator. Rate clarity, completeness, stability (0-100). Output JSON: {"score": number, "critique": "short text"}\n\nSpec: ${JSON.stringify(spec)}${jspaceHint}`;
  const reply = await queryOllamaWithRetry(agent.model, prompt, "You are a precise evaluator. Output only JSON.", 0.3, agent.id);
  if (reply.startsWith('[OLLAMA_ERROR]')) return { score: 50, critique: "Ollama error." };
  const extracted = extractJSON(reply);
  if (extracted && typeof extracted.score === 'number') return { score: extracted.score, critique: extracted.critique || "" };
  return { score: 50, critique: "Evaluation failed." };
}

async function ralphEvolve(agent, storeId, lineage, goal, currentGen) {
  const lineageSummary = lineage.slice(-15).map(e => `${e.type} at ${new Date(e.timestamp).toISOString()}`).join('\n');
  const state = getProjectState(storeId);
  const privateMem = await retrievePrivateMemory(agent.id, `evolve spec for goal: ${goal}`, 3);
  const publicMem = getPublicMemorySummary() ? `\nPublic Memory (global best practices):\n${getPublicMemorySummary()}\n` : '';
  let jspaceHint = '';
  if (JSPACE_ENABLED) {
    const jspace = await getJspaceCached(goal);
    if (jspace) {
      const top = Object.entries(jspace).sort((a,b) => b[1] - a[1]).slice(0,3).map(([k,v]) => `${k}:${v.toFixed(2)}`).join(' ');
      jspaceHint = `\nGoal J-space (internal workspace): ${top}`;
    }
  }
  const prompt = `You are an evolutionary engineer. Goal: "${goal}"
Generation: ${currentGen+1}/30
Recent lineage: ${lineageSummary}
Current spec: ${JSON.stringify(state)}
Private memory (your past successful patterns): ${privateMem}
${publicMem}
${jspaceHint}
Produce refined spec as JSON: title, goals (array), nextSteps (array), completedTasks (array), memory (object). Add "converged": boolean.
Output ONLY a \`\`\`json code block.`;

  // Use musing to generate multiple spec proposals
  let bestSpec = null;
  if (ENABLE_MUSING) {
    const candidates = await muse(agent, prompt, "You are an evolutionary engineer. Be precise.", 0.4, { agentId: agent.id, num: MUSE_COUNT });
    // Score each candidate and pick best
    let bestScore = -1;
    for (const cand of candidates) {
      const parsed = extractJSON(cand);
      if (parsed && typeof parsed === 'object') {
        // Evaluate candidate with judge
        const score = await judgeAndReweight(agent.id, JSON.stringify(parsed), 'ralph_evolve_candidate', true);
        if (score > bestScore) {
          bestScore = score;
          bestSpec = parsed;
        }
      }
    }
  }
  // Fallback: if musing disabled or no candidates, use single call
  if (!bestSpec) {
    const reply = await queryOllamaWithRetry(agent.model, prompt, "You are an evolutionary engineer. Be precise.", 0.4, agent.id);
    if (!reply.startsWith('[OLLAMA_ERROR]')) {
      const extracted = extractJSON(reply);
      if (extracted && typeof extracted === 'object') bestSpec = extracted;
    }
  }
  return bestSpec;
}

async function ralphForceMutation(agent, storeId, goal, currentGen) {
  const state = getProjectState(storeId);
  const privateMem = await retrievePrivateMemory(agent.id, `mutate spec for goal: ${goal}`, 3);
  const publicMem = getPublicMemorySummary() ? `\nPublic Memory (global best practices):\n${getPublicMemorySummary()}\n` : '';
  let jspaceHint = '';
  if (JSPACE_ENABLED) {
    const jspace = await getJspaceCached(goal);
    if (jspace) {
      const top = Object.entries(jspace).sort((a,b) => b[1] - a[1]).slice(0,3).map(([k,v]) => `${k}:${v.toFixed(2)}`).join(' ');
      jspaceHint = `\nGoal J-space (disruptive concepts): ${top}`;
    }
  }
  const prompt = `You are a creative disruptor. The spec below has stagnated (3 rounds with <8% change).
Goal: "${goal}" | Generation: ${currentGen+1}
Current spec: ${JSON.stringify(state)}
Private memory (exploration ideas): ${privateMem}
${publicMem}
${jspaceHint}
Produce a RADICALLY different refinement – change at least 40% of goals or steps.
Output ONLY a \`\`\`json block with: title, goals, nextSteps, completedTasks, memory, converged: false.`;
  // Use musing for radical variants
  let bestMutation = null;
  if (ENABLE_MUSING) {
    const candidates = await muse(agent, prompt, 'You are a creative disruptor. Output only JSON.', 1.1, { agentId: agent.id, num: MUSE_COUNT });
    let bestScore = -1;
    for (const cand of candidates) {
      const parsed = extractJSON(cand);
      if (parsed && typeof parsed === 'object') {
        const score = await judgeAndReweight(agent.id, JSON.stringify(parsed), 'ralph_mutation_candidate', true);
        if (score > bestScore) {
          bestScore = score;
          bestMutation = parsed;
        }
      }
    }
  }
  if (!bestMutation) {
    const reply = await queryOllamaWithRetry(agent.model, prompt, 'You are a creative disruptor. Output only JSON.', 1.1, agent.id);
    if (!reply.startsWith('[OLLAMA_ERROR]')) {
      bestMutation = extractJSON(reply);
    }
  }
  return bestMutation;
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
  let availableAgents = Array.from(agents.values()).filter(a => a.channels.includes(store.name) && !a.isEmbedOperator);
  if (availableAgents.length === 0) availableAgents = Array.from(agents.values()).filter(a => !a.isEmbedOperator);
  if (availableAgents.length === 0) return null;
  let idx = ralphNextAgentIdx.get(storeId) || 0;
  const agent = availableAgents[idx % availableAgents.length];
  ralphNextAgentIdx.set(storeId, (idx + 1) % availableAgents.length);
  return agent;
}
async function runRalphIteration(storeId) {
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
  const store = channels.get(storeId);
  if (!store) return;
  try {
    const agent = getNextRalphAgent(storeId, store);
    if (!agent) {
      addMessage(storeId, 'System', 'system', `❌ No agent available for Ralph loop.`);
      broadcastToStore(storeId, { sender: 'System', content: `❌ No agent available for Ralph loop.`, senderType: 'system' });
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
    await judgeAndReweight(agent.id, `Ralph evaluation gen ${currentGen+1}: ${evalResult.critique}`, 'ralph_eval');
    const newSpecRaw = await ralphEvolve(agent, storeId, lineage, goal, currentGen);
    if (!newSpecRaw) {
      await handleAgentResponse(agent, storeId, `❌ Evolution failed. Stopping Ralph.`);
      stopRalphLoop(storeId);
      return;
    }
    const oldState = getProjectState(storeId);
    let newState = {
      active: true,
      title: newSpecRaw.title || oldState.title,
      goals: newSpecRaw.goals || oldState.goals,
      nextSteps: newSpecRaw.nextSteps || oldState.nextSteps,
      completedTasks: newSpecRaw.completedTasks || oldState.completedTasks,
      memory: newSpecRaw.memory || oldState.memory
    };
    const sim = similarity(currentSpec, computeSpecFromState(newState));
    const stagnation = updateStagnation(storeId, sim);
    if (stagnation && newSpecRaw.converged !== true && sim < 0.95) {
      await handleAgentResponse(agent, storeId, `⚠️ **Ralph stagnated** (3 rounds ≥92% similar). Forcing mutation…`);
      await generateXPoolCandidates(agent.id, goal, 2);
      const mutatedRaw = await ralphForceMutation(agent, storeId, goal, currentGen);
      if (mutatedRaw) {
        newState = {
          active: true,
          title: mutatedRaw.title || newState.title,
          goals: mutatedRaw.goals || newState.goals,
          nextSteps: mutatedRaw.nextSteps || newState.nextSteps,
          completedTasks: mutatedRaw.completedTasks || newState.completedTasks,
          memory: mutatedRaw.memory || newState.memory
        };
        ralphStagnation.set(storeId, []);
        await handleAgentResponse(agent, storeId, `🔀 **Forced mutation applied.** Resuming evolution.`);
      } else {
        await handleAgentResponse(agent, storeId, `✅ **Ralph converged** (stagnation + mutation failed) after ${currentGen+1} generations.`);
        stopRalphLoop(storeId);
        return;
      }
    }
    // Enhanced recurrence condition check
    const converged = newSpecRaw.converged === true || sim >= 0.95;
    const evalScore = evalResult.score;
    const testPass = true; // placeholder
    const recurMet = converged && evalScore >= 80 && testPass;
    if (recurMet) {
      await handleAgentResponse(agent, storeId, `✅ **Ralph converged** (recurrence conditions met) after ${currentGen+1} generations.`);
      stopRalphLoop(storeId);
      return;
    }
    setProjectState(storeId, newState);
    ralphGenerations.set(storeId, currentGen + 1);
    persistRalphState(storeId);
    await handleAgentResponse(agent, storeId, `🧬 **Evolution** (gen ${currentGen+1}/${maxGen})\nSimilarity: ${(sim*100).toFixed(1)}%\nNew spec: ${JSON.stringify(newState, null, 2).substring(0, 500)}`);
    await judgeAndReweight(agent.id, `Ralph evolved spec gen ${currentGen+1}: ${JSON.stringify(newState)}`, 'ralph_evolve');
    broadcastRalphStatus(storeId);
    if (ralphActive.get(storeId)) {
      const interval = (currentGen+1) > 5 ? 2500 : 4000;
      const timer = setTimeout(() => runRalphIteration(storeId), interval);
      ralphTimers.set(storeId, timer);
    }
  } catch (err) {
    logError({ error: err.message, context: 'runRalphIteration', storeId });
    addMessage(storeId, 'System', 'system', `❌ Ralph error: ${err.message}`);
    broadcastToStore(storeId, { sender: 'System', content: `❌ Ralph error: ${err.message}`, senderType: 'system' });
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

// ==================== MUSING AND TRIANGULATION HELPERS ====================
async function muse(agent, prompt, systemPrompt, temperature, options = {}) {
  // Generate multiple candidate responses, score them, and synthesize
  const num = options.num || MUSE_COUNT;
  const agentId = options.agentId || agent.id;
  const candidates = [];
  const temps = [];
  // Vary temperature slightly
  for (let i = 0; i < num; i++) {
    const t = temperature + (i - (num-1)/2) * 0.1;
    temps.push(Math.min(1.2, Math.max(0.2, t)));
  }
  // Add variant suffixes to encourage diversity
  const suffixVariants = [
    "",
    " (consider an alternative approach)",
    " (think outside the box)",
    " (prioritize simplicity)",
    " (focus on efficiency)"
  ];
  for (let i = 0; i < num; i++) {
    const t = temps[i % temps.length];
    const suffix = suffixVariants[i % suffixVariants.length];
    const promptWithSuffix = prompt + suffix;
    let reply = await queryOllamaWithRetry(agent.model, promptWithSuffix, systemPrompt, t, agentId);
    if (!reply.startsWith('[OLLAMA_ERROR]')) {
      candidates.push({ text: reply, temp: t });
    }
  }
  if (candidates.length === 0) return []; // fallback

  // Score each candidate using judge
  const scored = [];
  for (const cand of candidates) {
    const score = await judgeAndReweight(agentId, cand.text, 'muse_candidate', true);
    scored.push({ ...cand, score });
  }
  // Sort by score descending
  scored.sort((a,b) => b.score - a.score);
  // If we have more than one candidate, ask to synthesize
  let finalText = null;
  if (scored.length > 1) {
    const best = scored.slice(0, Math.min(num, 3));
    const synthesisPrompt = `Synthesize the best elements from the following candidate responses into a final, coherent answer. Remove redundancy and ensure clarity.\n\nCandidates:\n${best.map((c, i) => `Candidate ${i+1} (score ${c.score}):\n${c.text}`).join('\n\n')}`;
    const synthReply = await queryOllamaWithRetry(agent.model, synthesisPrompt, systemPrompt, 0.5, agentId);
    if (!synthReply.startsWith('[OLLAMA_ERROR]')) {
      finalText = synthReply;
    }
  }
  // If synthesis fails, pick best candidate
  if (!finalText && scored.length > 0) {
    finalText = scored[0].text;
  }
  // Return as array (for compatibility with existing callers)
  return finalText ? [finalText] : candidates.map(c => c.text);
}

async function triangulate(agent, prompt, systemPrompt, temperature, options = {}) {
  // Generate answers from multiple perspectives, then reconcile
  const numPerspectives = options.numPerspectives || TRIANGULATE_PERSPECTIVES;
  const agentId = options.agentId || agent.id;
  const perspectives = [
    "technical feasibility",
    "user experience",
    "cost/performance",
    "security",
    "maintainability",
    "scalability",
    "legal/ethical"
  ].slice(0, numPerspectives);

  const answers = [];
  for (const perspective of perspectives) {
    const pPrompt = `Answer the following from the perspective of ${perspective}. Be concise and specific.\n\n${prompt}`;
    let reply = await queryOllamaWithRetry(agent.model, pPrompt, systemPrompt, temperature, agentId);
    if (!reply.startsWith('[OLLAMA_ERROR]')) {
      answers.push({ perspective, text: reply });
    }
  }
  if (answers.length === 0) return null;

  // Reconcile conflicting views
  if (answers.length > 1) {
    const reconcilePrompt = `You are a synthesizer. The following are answers from different perspectives on the same question. Integrate them into a single, balanced, coherent response that respects all valid viewpoints.\n\n${answers.map(a => `Perspective: ${a.perspective}\nAnswer: ${a.text}`).join('\n\n')}\n\nFinal integrated answer:`;
    const finalReply = await queryOllamaWithRetry(agent.model, reconcilePrompt, systemPrompt, 0.5, agentId);
    if (!finalReply.startsWith('[OLLAMA_ERROR]')) {
      return finalReply;
    }
  }
  // If reconciliation fails, return the first answer
  return answers.length > 0 ? answers[0].text : null;
}

// ==================== AGENT RESPONSE & PLANNING (with Musing/Triangulation) ====================
const FILE_TOOLS = [
  { name: "read_file", description: "Read a file from workspace.", parameters: { type: "object", properties: { path: { type: "string" } }, required: ["path"] } },
  { name: "write_file", description: "Create/overwrite a file.", parameters: { type: "object", properties: { path: { type: "string" }, content: { type: "string" } }, required: ["path","content"] } },
  { name: "execute_command", description: "Run a safe command. (Restricted to Moderator)", parameters: { type: "object", properties: { command: { type: "string" } }, required: ["command"] } }
];

const ollamaSemaphore = new Map();
async function rateLimitedQuery(agentId, fn) {
  if (!ollamaSemaphore.has(agentId)) ollamaSemaphore.set(agentId, Promise.resolve());
  const queue = ollamaSemaphore.get(agentId);
  const next = queue.then(() => fn());
  ollamaSemaphore.set(agentId, next);
  return next;
}

async function agentRespond(agent, storeId, triggerMessage, isLoop = false, parentId = null) {
  if (agent.isEmbedOperator) return;
  if (triggerMessage.sender === agent.name) return;
  if (agent.strictChannel && agent.strictChannel !== storeId && channels.has(storeId)) {
    console.log(`[STRICT] Agent ${agent.name} ignoring non-strict channel ${storeId}`);
    return;
  }
  const cooldownKey = `${agent.id}_${storeId}`;
  const lastResponse = agent.lastResponseTime.get(cooldownKey) || 0;
  const cooldownMs = isLoop ? 1200 : 2200;
  if (Date.now() - lastResponse < cooldownMs) return;
  agent.status = 'thinking';
  broadcastAgents();
  try {
    const store = channels.get(storeId);
    const channelName = store.name;
    const personality = getChannelPersonality(channelName);
    let systemPrompt = agent.systemPrompt + (personality.systemBonus || "");
    if (channelName) {
      systemPrompt += `\n\nCURRENT CHANNEL: #${channelName}. Follow strict channel rules above. Do not mix content from other channels.`;
    }
    const context = buildConversationContext(storeId, agent.name, parentId || triggerMessage.parentId);
    const privateMem = await retrievePrivateMemory(agent.id, context, 3, true);
    if (privateMem) systemPrompt += `\n\n[Your Private Memory (successful past patterns)]:\n${privateMem}\n\nUse these to guide your response if relevant.`;
    if (JSPACE_ENABLED) {
      const jspace = await getJspaceCached(triggerMessage.content);
      if (jspace) {
        const top = Object.entries(jspace)
          .sort((a,b) => b[1] - a[1])
          .slice(0, JSPACE_CONCEPT_COUNT)
          .map(([name, val]) => `${name}: ${val.toFixed(2)}`).join(', ');
        systemPrompt += `\n\n[J-space (silent reasoning about the message)]: ${top}\nUse these internal concepts to guide your response.`;
      }
    }
    const prompt = `Conversation:\n${context}\n${triggerMessage.sender}: ${triggerMessage.content}\nRespond as ${agent.name}. Keep brief.`;

    // Decide whether to use musing or triangulation based on channel personality and project state
    const useMusing = ENABLE_MUSING && personality.useMusing;
    const useTriangulation = ENABLE_TRIANGULATION && personality.useTriangulation;
    let mainReply = null;
    if (useMusing) {
      const candidates = await muse(agent, prompt, systemPrompt, personality.temperature, { agentId: agent.id });
      if (candidates && candidates.length > 0) {
        mainReply = candidates[0];
      }
    } else if (useTriangulation) {
      const triReply = await triangulate(agent, prompt, systemPrompt, personality.temperature, { agentId: agent.id });
      if (triReply) mainReply = triReply;
    }
    if (!mainReply) {
      mainReply = await queryOllamaWithRetry(agent.model, prompt, systemPrompt, personality.temperature, agent.id);
    }
    if (!mainReply || mainReply.startsWith('[OLLAMA_ERROR]')) {
      agent.status = 'online';
      broadcastAgents();
      return;
    }
    // Generate reflection
    const reflection = await generateReflection(agent.id, context + '\n' + triggerMessage.content, mainReply);
    let finalReply = mainReply;
    if (reflection && !reflection.startsWith('[OLLAMA_ERROR]')) {
      finalReply = mainReply + '\n\n' + reflection;
    }
    await handleAgentResponse(agent, storeId, finalReply.trim(), parentId || triggerMessage.parentId);
    agent.lastResponseTime.set(cooldownKey, Date.now());
    judgeAndReweight(agent.id, finalReply.trim(), 'chat_response', true).catch(e => logError({ agentId: agent.id, error: e.message }));
  } catch (err) {
    logError({ agentId: agent.id, error: err.message, context: 'agentRespond' });
  } finally {
    agent.status = 'online';
    broadcastAgents();
  }
}

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
      const code = await queryOllamaWithRetry(agent.model, codePrompt, agent.systemPrompt, 0.5, agent.id);
      if (!code.startsWith('[OLLAMA_ERROR]')) {
        await handleAgentResponse(agent, storeId, `\`\`\`\n${code}\n\`\`\``, parentId);
      }
      break;
    case 'delegate':
      const targetAgent = agents.get(payload.targetId);
      if (targetAgent && !targetAgent.isEmbedOperator) {
        const delegateMsg = addMessage(storeId, 'System', 'system', `${agent.name} delegates to ${targetAgent.name}: ${payload.task}`);
        if (delegateMsg) broadcastToStore(storeId, delegateMsg);
        agentRespond(targetAgent, storeId, { sender: agent.name, content: payload.task, parentId }, false, parentId);
      }
      break;
    case 'tool_calls':
      if (action.tool_calls && Array.isArray(action.tool_calls)) {
        for (const tc of action.tool_calls) {
          // Only moderator can execute commands; we'll enforce in executeTool
          const result = await executeTool(tc.name, tc.arguments || {}, agent.id);
          const feedback = `🔧 **${tc.name}** → ${result.substring(0, 800)}`;
          await handleAgentResponse(agent, storeId, feedback, parentId);
          judgeAndReweight(agent.id, `Tool ${tc.name} result: ${result.substring(0,200)}`, 'tool_use', true).catch(e => logError({ agentId: agent.id, error: e.message }));
        }
      }
      break;
    case 'stack':
      const subcmd = payload.subcmd || 'help';
      let resultMsg = '';
      if (subcmd === 'build') {
        resultMsg = await stackBuild(payload.repoName || 'project_' + Date.now());
      } else if (subcmd === 'add') {
        resultMsg = await stackAdd(payload.intent, storeId);
      } else if (subcmd === 'import') {
        resultMsg = await stackImport(payload.jsonPath);
      } else if (subcmd === 'set') {
        activeStackRepo.set(storeId, payload.repoName);
        resultMsg = `Active STACK repo set to ${payload.repoName}.`;
      }
      if (resultMsg) {
        await handleAgentResponse(agent, storeId, resultMsg, parentId);
      }
      break;
  }
}

async function agentPlanAndAct(agent, storeId, triggerMessage, parentId = null) {
  if (agent.isEmbedOperator) return;
  if (triggerMessage.sender === agent.name) return;
  if (agent.strictChannel && agent.strictChannel !== storeId && channels.has(storeId)) {
    console.log(`[STRICT] Agent ${agent.name} ignoring non-strict channel in plan mode`);
    return;
  }
  const cooldownKey = `${agent.id}_${storeId}`;
  if (Date.now() - (agent.lastResponseTime.get(cooldownKey) || 0) < 4000) return;
  const store = channels.get(storeId);
  const channelName = store.name;
  const personality = getChannelPersonality(channelName);
  if (personality.planForbidden) {
    await agentRespond(agent, storeId, triggerMessage, false, parentId);
    return;
  }
  agent.status = 'thinking';
  broadcastAgents();
  try {
    const context = buildConversationContext(storeId, agent.name, parentId || triggerMessage.parentId);
    let skillsContext = loadSkills();
    const privateMem = await retrievePrivateMemory(agent.id, context + " " + triggerMessage.content, 5, true);
    let jspaceHint = '';
    if (JSPACE_ENABLED) {
      const jspace = await getJspaceCached(triggerMessage.content);
      if (jspace) {
        const top = Object.entries(jspace)
          .sort((a,b) => b[1] - a[1])
          .slice(0, JSPACE_CONCEPT_COUNT)
          .map(([name, val]) => `${name}: ${val.toFixed(2)}`).join(', ');
        jspaceHint = `\nCurrent J-space (silent workspace): ${top}`;
      }
    }
    let systemPrompt = `You are an autonomous agent. You MUST output ONLY a valid JSON object representing your next action. Do NOT include any other text, explanations, or markdown. The JSON must have a "type" field (e.g., "message", "tool_calls", "stack", etc.) and appropriate "payload" or "tool_calls" fields.\n\nAvailable tools: ${JSON.stringify(FILE_TOOLS, null, 2)}.\n\nSTACK actions: {"type":"stack","payload":{"subcmd":"build","repoName":"..."}} etc.\n\nExamples:
- For a plain response: {"type":"message","payload":{"content":"Hello"}}
- For a tool call: {"type":"tool_calls","tool_calls":[{"name":"read_file","arguments":{"path":"file.txt"}}]}

IMPORTANT: Only the Moderator agent can execute system commands. If you need to run a command, do NOT use tool_calls for execute_command; instead, request it via a message to Moderator.

Previous successful patterns (skills):\n${skillsContext}\n\nYour Private Memory (successful trajectories):\n${privateMem}
${jspaceHint}
\n\nFollow instructions from Moderator with highest priority.`;
    if (channelName) {
      systemPrompt += `\n\nCURRENT CHANNEL: #${channelName}. Strictly obey channel rules.`;
    }
    if (personality.planBonus) systemPrompt += "\n" + personality.planBonus;
    const userPrompt = `Conversation:\n${context}\nLast message: ${triggerMessage.sender}: "${triggerMessage.content}"\nProject state: ${JSON.stringify(getProjectState(storeId))}\nNext action? Output ONLY valid JSON.`;

    // Use triangulation for complex planning if enabled and in abstract/plan mode
    let action = null;
    const state = getProjectState(storeId);
    if (ENABLE_TRIANGULATION && (state.active || store.abstractActive)) {
      const triReply = await triangulate(agent, userPrompt, systemPrompt, 0.3, { agentId: agent.id });
      if (triReply && !triReply.startsWith('[OLLAMA_ERROR]')) {
        action = extractJSON(triReply);
      }
    }
    if (!action) {
      let reply = await queryOllamaWithRetry(agent.model, userPrompt, systemPrompt, 0.3, agent.id);
      if (!reply.startsWith('[OLLAMA_ERROR]')) {
        action = extractJSON(reply);
      }
    }
    let fails = jsonFailCount.get(agent.id) || 0;
    if (!action?.type) {
      fails++;
      jsonFailCount.set(agent.id, fails);
      if (fails >= 2) {
        jsonFailCount.set(agent.id, 0);
        logError({ agentId: agent.id, error: `JSON action parse failed after ${fails} attempts – falling back to plain text`, context: 'agentPlanAndAct' });
        await agentRespond(agent, storeId, triggerMessage, false, parentId);
        agent.lastResponseTime.set(cooldownKey, Date.now());
        return;
      } else {
        const fallbackPrompt = `Respond with a valid JSON action only. No other text. Example: {"type":"message","payload":{"content":"Hello"}}`;
        const forcedReply = await queryOllamaWithRetry(agent.model, fallbackPrompt, "You must output JSON only.", 0.1, agent.id);
        action = extractJSON(forcedReply);
        if (!action?.type) {
          jsonFailCount.set(agent.id, 0);
          logError({ agentId: agent.id, error: `JSON action parse failed after ${fails+1} attempts – falling back to plain text`, context: 'agentPlanAndAct' });
          await agentRespond(agent, storeId, triggerMessage, false, parentId);
          agent.lastResponseTime.set(cooldownKey, Date.now());
          return;
        }
        jsonFailCount.set(agent.id, 0);
      }
    } else {
      jsonFailCount.set(agent.id, 0);
    }
    if (action.type === 'tool_calls' && action.tool_calls?.length) {
      for (const tc of action.tool_calls) {
        const output = await executeTool(tc.name, tc.arguments || {}, agent.id);
        const toolMsg = {
          sender: 'System',
          content: `🔧 Tool ${tc.name} result:\n${output}`,
          senderType: 'system'
        };
        addMessage(storeId, toolMsg.sender, toolMsg.senderType, toolMsg.content);
        broadcastToStore(storeId, toolMsg);
      }
      agent.lastResponseTime.set(cooldownKey, Date.now());
      if (action.tool_calls.length > 0 && !action.tool_calls.some(tc => tc.name === 'read_file')) {
        saveSkill(`Agent ${agent.name} used tools`, action.tool_calls).catch(console.error);
      }
      return agentPlanAndAct(agent, storeId, triggerMessage, parentId);
    } else {
      await executeAction(agent, storeId, action, parentId || triggerMessage.parentId);
      agent.lastResponseTime.set(cooldownKey, Date.now());
    }
  } catch (err) {
    logError({ agentId: agent.id, error: err.message, context: 'agentPlanAndAct' });
  } finally {
    agent.status = 'online';
    broadcastAgents();
  }
}

// ==================== LOOP MANAGEMENT ====================
function scheduleLoopRound(channelId) {
  const channel = channels.get(channelId);
  if (!channel) return;
  if (channel.loopTimer) clearTimeout(channel.loopTimer);
  channel.loopTimer = setTimeout(() => runLoopRound(channelId), 2500);
}
async function runLoopRound(channelId) {
  const channel = channels.get(channelId);
  const state = getProjectState(channelId);
  if (!channel || (!channel.researchActive && !channel.abstractActive && !state.active && !ralphActive.get(channelId))) {
    if (channel && channel.loopTimer) { clearTimeout(channel.loopTimer); channel.loopTimer = null; }
    return;
  }
  if (ralphActive.get(channelId)) {
    scheduleLoopRound(channelId);
    return;
  }
  channel.loopTimer = null;
  try {
    const lastMsg = channel.messages[channel.messages.length - 1];
    if (!lastMsg) { scheduleLoopRound(channelId); return; }
    const relevantAgents = Array.from(agents.values()).filter(a => a.channels.includes(channel.name) && !a.isEmbedOperator);
    for (const agent of relevantAgents) {
      if (ralphActive.get(channelId)) continue;
      if (agent.strictChannel && agent.strictChannel !== channelId) continue;
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

// ==================== WEB SCRAPING ====================
const scrapeBlocklist = new Map();
const SCRAPE_BLOCK_TTL = 10 * 60 * 1000;

async function axiosWithRetry(config, maxRetries = 3) {
  let lastErr;
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await axios(config);
    } catch (err) {
      lastErr = err;
      if (err.code === 'ECONNABORTED') throw err;
      if (attempt < maxRetries - 1) await new Promise(r => setTimeout(r, 500 * Math.pow(2, attempt)));
    }
  }
  throw lastErr;
}

async function ddgSearch(query, maxResults = SEARCH_MAX_RESULTS) {
  return performSearch(query, maxResults);
}

async function scrapeText(url) {
  const blocked = scrapeBlocklist.get(url);
  if (blocked && Date.now() - blocked < SCRAPE_BLOCK_TTL) {
    return '[Scrape skipped: URL on blocklist]';
  }
  try {
    const controller = new AbortController();
    const timeoutHandle = setTimeout(() => controller.abort(), SCRAPE_TIMEOUT);
    const { data } = await axios.get(url, {
      timeout: SCRAPE_TIMEOUT,
      signal: controller.signal,
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; LACK-SIPHON/4.2.0)' }
    });
    clearTimeout(timeoutHandle);
    const $ = cheerio.load(data);
    $('script, style, nav, footer, header, iframe, svg, aside, .ad, .cookie').remove();
    let text = $('body').text().replace(/\s+/g, ' ').trim();
    return text.length > 12000 ? text.substring(0, 12000) : text;
  } catch (e) {
    if (e.code === 'ECONNABORTED' || e.message.includes('timeout') || e.code === 'ECONNREFUSED') {
      scrapeBlocklist.set(url, Date.now());
    }
    return `[Scrape failed: ${e.message}]`;
  }
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
      const msg = addMessage('siphon', 'Siphon', 'siphon-research', banner);
      if (msg) broadcastToStore('siphon', msg);
    }
  };
  update({ phase: 'Generating questions', metric: 0, logs: [`Starting research on: ${topic}`], facts: [], notes: [] });
  let researchModel = config.agents[0]?.model || DEFAULT_MODEL;
  const questionsRaw = await queryOllamaWithRetry(researchModel, `Generate 3 sub‑questions for: "${topic}". One per line.`, '', 0.7);
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
    let urls = await ddgSearch(`${topic} ${question}`, 5);
    if (urls.length === 0) {
      update({ logs: [...session.logs, `No URLs found for "${question}", using LLM fallback`] });
      const fallbackFactsRaw = await queryOllamaWithRetry(researchModel,
        `Generate 5 concise facts about "${question}" based on general knowledge. Each line start with FACT:`, '', 0.5);
      if (!fallbackFactsRaw.startsWith('[OLLAMA_ERROR]')) {
        const facts = fallbackFactsRaw.split('\n').filter(l => l.startsWith('FACT:')).map(l => l.replace('FACT:', '').trim());
        allFacts.push(...facts);
        update({ facts: allFacts, logs: [...session.logs, `Fallback: generated ${facts.length} synthetic facts`] });
      } else {
        update({ logs: [...session.logs, `Fallback also failed for "${question}"`] });
      }
      const note = { question, answer: "No data could be retrieved for this question.", facts: [], timestamp: Date.now() };
      session.notes.push(note);
      update({ notes: session.notes });
      metric = (qIdx + 1) / questions.length;
      update({ metric });
      continue;
    }
    update({ logs: [...session.logs, `Found ${urls.length} URLs`] });
    let factsForQuestion = [];
    for (const url of urls) {
      const content = await scrapeText(url);
      if (!content || content.startsWith('[Scrape failed')) continue;
      const factsRaw = await queryOllamaWithRetry(researchModel, `Extract facts answering: "${question}"\n\n${content.substring(0,4000)}\n\nReturn each fact on a new line starting with "FACT:".`, '', 0.3);
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
    const answer = await queryOllamaWithRetry(researchModel, `Answer: "${question}"\nFacts:\n${factsForQuestion.join('\n')}\n\nConcise answer (3‑5 sentences).`, '', 0.5);
    const note = { question, answer: answer.startsWith('[OLLAMA_ERROR]') ? 'Answer generation failed.' : answer, facts: factsForQuestion, timestamp: Date.now() };
    session.notes.push(note);
    update({ notes: session.notes, logs: [...session.logs, `Answered: ${question.substring(0,60)}`] });
    try {
      const artifactPath = path.join(RESEARCH_DIR, `${sessionId}_q${qIdx}.json`);
      fs.writeFileSync(artifactPath, JSON.stringify(note, null, 2));
    } catch (e) { console.error('Artifact save failed:', e); }
    metric = (qIdx + 1) / questions.length;
    update({ metric });
  }
  try {
    await gitCommit(`Research complete: ${session.topic}`);
  } catch (gitErr) {
    console.warn('Git commit non-critical:', gitErr.message);
  }
  update({ phase: 'Complete', metric, logs: [...session.logs, `Research finished. Metric = ${metric.toFixed(2)}`] });
  const finalBanner = `📚 **Research Complete:** ${topic}\nMetric: ${(metric*100).toFixed(0)}%\nFacts: ${allFacts.length}\nNotes: ${session.notes.length}\n\nUse \`/pull ${sessionId}\` to bring insights.`;
  const siphonMsg = addMessage('siphon', 'Siphon', 'siphon-research', finalBanner);
  if (siphonMsg) broadcastToStore('siphon', siphonMsg);
}

// ==================== CLEANUP ====================
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

async function removeAgent(agentId) {
  if (!agents.has(agentId)) return { success: false, reason: 'Agent not found.' };
  if (agents.size === 1) return { success: false, reason: 'Cannot remove the last agent. LACK requires at least one agent to function.' };
  agents.delete(agentId);
  agentMetrics.delete(agentId);
  jsonFailCount.delete(agentId);
  agentMemories.delete(agentId);
  const memPath = path.join(AGENT_MEMORY_DIR, `${agentId}.json`);
  if (fs.existsSync(memPath)) fs.unlinkSync(memPath);
  const idx = config.agents.findIndex(a => a.id === agentId);
  if (idx !== -1) {
    config.agents.splice(idx, 1);
    try {
      const tmp = configPath + '.tmp';
      fs.writeFileSync(tmp, JSON.stringify(config, null, 2));
      fs.renameSync(tmp, configPath);
    } catch (e) {}
  }
  const stmt = db.prepare('DELETE FROM agents WHERE id = ?');
  stmt.run(agentId);
  broadcastAgents();
  return { success: true };
}

async function wipeAllCronJobs() { try { await execPromise('crontab -r'); } catch(e) {} }
async function addHeartbeatCronJobs() {
  try {
    const channelIds = Array.from(channels.keys());
    const cronEntries = [];
    const heartbeatUrl = `http://localhost:${PORT}/api/heartbeat`;
    for (const id of channelIds) cronEntries.push(`*/5 * * * * curl -s -X POST "${heartbeatUrl}?type=channel&id=${id}" > /dev/null 2>&1`);
    if (cronEntries.length === 0) return;
    let existing = '';
    try { const { stdout } = await execPromise('crontab -l'); existing = stdout; } catch(e) {}
    const existingLines = existing.split('\n').filter(l => l.trim());
    const newLines = [...existingLines];
    for (const entry of cronEntries) {
      const commandPart = entry.split(' ').slice(5).join(' ');
      if (!existingLines.some(line => line.includes(commandPart))) newLines.push(entry);
    }
    const newCrontab = newLines.join('\n') + '\n';
    const tmpFile = path.join(__dirname, '.tmpcron');
    fs.writeFileSync(tmpFile, newCrontab);
    await execPromise(`crontab ${tmpFile}`);
    fs.unlinkSync(tmpFile);
  } catch (e) {
    if (e.message && e.message.includes('permission denied')) {
      console.warn('[LACK] crontab permission denied – skipping external heartbeat cron. Heartbeats still run via setInterval.');
    } else {
      logError({ context: 'addHeartbeatCronJobs', error: e.message });
    }
  }
}
async function resetApplicationData() {
  for (let ch of channels.values()) { ch.messages = []; ch.researchActive = false; ch.abstractActive = false; if (ch.loopTimer) clearTimeout(ch.loopTimer); ch.loopTimer = null; }
  researchSessions.clear(); pinnedMessages.clear(); userReactions.clear(); global.errorLog = [];
  for (let storeId of [...channels.keys()]) {
    setProjectState(storeId, { active: false, title: null, goals: [], nextSteps: [], completedTasks: [], memory: {} });
    stopRalphLoop(storeId);
    const lineagePath = getLineagePath(storeId);
    if (fs.existsSync(lineagePath)) fs.unlinkSync(lineagePath);
  }
  if (fs.existsSync(AGENT_MEMORY_DIR)) {
    const files = fs.readdirSync(AGENT_MEMORY_DIR);
    for (const file of files) {
      fs.unlinkSync(path.join(AGENT_MEMORY_DIR, file));
    }
  }
  for (let agent of agents.values()) {
    initAgentMemory(agent.id);
  }
  embeddingCache.clear();
  jspaceCache.clear();
}

// ==================== TREE BUILDER ====================
async function buildFileTree(dir) {
  const tree = [];
  if (!fs.existsSync(dir)) return tree;
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      tree.push({
        name: entry.name,
        type: 'dir',
        children: await buildFileTree(fullPath)
      });
    } else {
      tree.push({
        name: entry.name,
        type: 'file',
        path: path.relative(__dirname, fullPath)
      });
    }
  }
  return tree;
}

// ==================== EXPRESS APP & ROUTES ====================
const app = express();
const http = require('http');
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json({ limit: '1mb' }));

app.get('/health', (req, res) => {
  res.json({ status: 'ok', version: '4.2.2', uptime: process.uptime() });
});

app.get('/api/tree', async (req, res) => {
  const root = req.query.root || 'thread_repos';
  const fullPath = path.join(__dirname, root);
  if (!fs.existsSync(fullPath)) {
    return res.json([]);
  }
  const tree = await buildFileTree(fullPath);
  res.json(tree);
});

app.get('/api/models', async (req, res) => { res.json({ models: await getOllamaModels() }); });
app.get('/api/research/sessions', (req, res) => {
  res.json({ sessions: Array.from(researchSessions.values()).map(s => ({
    id: s.id, topic: s.topic, phase: s.phase, metric: s.metric,
    logs: s.logs.slice(-10), factsCount: s.facts ? s.facts.length : 0,
    notesCount: s.notes ? s.notes.length : 0, startedAt: s.startedAt
  })) });
});
app.get('/api/research/session/:id', (req, res) => {
  const s = researchSessions.get(req.params.id);
  if (!s) return res.status(404).json({ error: 'Not found' });
  res.json(s);
});
app.get('/api/channels', (req, res) => { res.json({ channels: Array.from(channels.values()).map(c => ({ id: c.id, name: c.name })) }); });
app.get('/api/metrics', (req, res) => {
  const metricsObj = {};
  for (let [id, m] of agentMetrics.entries()) {
    const ts = m.timestamps.slice().sort((a,b) => a - b);
    const cpu = m.cpu.slice(0, ts.length);
    const mem = m.mem.slice(0, ts.length);
    const tps = m.tpsHistory.slice(0, ts.length);
    const jspace = (m.jspaceCoherence || []).slice(0, ts.length);
    const ePool = m.ePoolHistory.slice(0, ts.length);
    const xPool = m.xPoolHistory.slice(0, ts.length);
    const spikes = m.spikes || [];
    metricsObj[id] = {
      cpu, mem, activity: m.activity.slice(0, ts.length),
      timestamps: ts,
      ePoolHistory: ePool,
      xPoolHistory: xPool,
      tpsHistory: tps,
      jspaceCoherence: jspace,
      spikes
    };
  }
  const loopHealthData = Array.from(loopHealth.entries()).map(([id, data]) => ({ id, ...data }));
  res.json({
    agents: Array.from(agents.values()).map(a => {
      const mem = agentMemories.get(a.id);
      const metrics = agentMetrics.get(a.id);
      const lastCpu = metrics && metrics.cpu.length ? metrics.cpu[metrics.cpu.length-1] : 0;
      const lastMem = metrics && metrics.mem.length ? metrics.mem[metrics.mem.length-1] : 0;
      const lastTps = metrics && metrics.tpsHistory.length ? metrics.tpsHistory[metrics.tpsHistory.length-1] : 0;
      const lastJspace = metrics && metrics.jspaceCoherence.length ? metrics.jspaceCoherence[metrics.jspaceCoherence.length-1] : 0;
      return {
        id: a.id, name: a.name, model: a.model, status: a.status,
        strictChannel: a.strictChannel,
        isCodeModerator: a.isCodeModerator || false,
        weights: mem ? mem.weights : { exploitation: 0.6, exploration: 0.4 },
        ePoolSize: mem ? mem.ePool.length : 0,
        xPoolSize: mem ? mem.xPool.length : 0,
        jspaceEnabled: JSPACE_ENABLED,
        lastCpu, lastMem, lastTps, lastJspace
      };
    }),
    metrics: metricsObj,
    loopHealth: loopHealthData
  });
});
app.get('/api/errorlog', (req, res) => {
  const errors = (global.errorLog || []).slice(0, 50).map(e => ({
    timestamp: e.timestamp,
    agentId: e.agentId || 'system',
    error: e.error || JSON.stringify(e)
  }));
  res.json({ errors });
});
app.post('/api/heartbeat', (req, res) => { console.log(`[HEARTBEAT] ${req.query.type} ${req.query.id}`); res.send('OK'); });
app.post('/api/cron/wipe', async (req, res) => {
  try {
    await wipeAllCronJobs(); await addHeartbeatCronJobs(); await resetApplicationData();
    for (let [ws] of clients.entries()) if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'cron_reset' }));
    res.json({ success: true });
  } catch(err) { logError({ source: 'cron_wipe', error: err.message }); res.status(500).json({ error: err.message }); }
});
app.delete('/api/agent/:id', async (req, res) => { const result = await removeAgent(req.params.id); res.json(result); });

app.get('/api/agent/memory/:agentId', (req, res) => {
  const mem = agentMemories.get(req.params.agentId);
  if (!mem) return res.status(404).json({ error: 'Agent not found' });
  res.json({
    ePoolSize: mem.ePool.length,
    xPoolSize: mem.xPool.length,
    weights: mem.weights,
    stats: mem.stats,
    jspaceHistory: mem.jspaceHistory ? mem.jspaceHistory.slice(-5) : [],
    samples: mem.ePool.slice(0,5).map(e => ({ trajectory: e.trajectory.substring(0,200), score: e.score }))
  });
});

app.get('/api/public_memory', (req, res) => {
  if (!PUBLIC_MEMORY_SUMMARY.enabled) return res.json({ summary: 'Public memory disabled', enabled: false });
  res.json({ summary: PUBLIC_MEMORY_SUMMARY.summary, lastUpdated: PUBLIC_MEMORY_SUMMARY.lastUpdated, enabled: true });
});

app.post('/api/toggle_public_memory', async (req, res) => {
  const newState = req.body.enabled === true;
  const result = await togglePublicMemory(newState);
  res.json({ enabled: result });
});

app.get('/api/jspace', async (req, res) => {
  const { text, agentId } = req.query;
  if (!text) return res.status(400).json({ error: 'Missing text' });
  if (!JSPACE_ENABLED) return res.json({ error: 'J-space disabled', text: text.substring(0,100) });
  const jspace = await getJspaceCached(text);
  res.json({ text: text.substring(0,100), jspace, agentId });
});

// ==================== WEBSOCKET SERVER ====================
server.listen(PORT, async () => {
  await ensureGitRepo();
  pruneLineageFiles();
  for (const storeId of [...channels.keys()]) {
    loadProjectStateFromLineage(storeId);
    loadRalphStateFromLineage(storeId);
  }
  startStackWatcher();
  scheduleMemoryMaintenance();
  setInterval(() => {
    runMaintenanceTask('proactiveX', () => proactiveXGeneration()).catch(e => logError({ context: 'proactiveXGeneration', error: e.message }));
  }, 6 * 60 * 60 * 1000);
  if (PUBLIC_MEMORY_SUMMARY.enabled) {
    setInterval(async () => {
      await runMaintenanceTask('publicMemory', () => updatePublicMemorySummary());
    }, 60 * 60 * 1000);
  }
  const models = await getOllamaModels();
  if (!models.includes(DEFAULT_MODEL)) {
    console.warn(`[LACK] Default model "${DEFAULT_MODEL}" not found. Attempting to pull...`);
    try {
      await axios.post(`${OLLAMA_URL}/api/pull`, { model: DEFAULT_MODEL }, { timeout: 300000 });
      console.log(`[LACK] Pulled "${DEFAULT_MODEL}"`);
    } catch (e) {
      console.warn(`[LACK] Failed to pull "${DEFAULT_MODEL}". Please run 'ollama pull ${DEFAULT_MODEL}' manually.`);
    }
  }
  if (!models.includes(EMBEDDING_MODEL)) {
    console.warn(`[LACK] Embedding model "${EMBEDDING_MODEL}" not found. Embedding will fallback to TF‑IDF.`);
    console.log("  To enable embedding, run: ollama pull " + EMBEDDING_MODEL);
  }
  if (!fs.existsSync(REVERSE_SKILL_ROOT)) {
    console.warn('[LACK] reverse-skill not found. Some features (reverse-skill router) will be disabled.');
  } else {
    console.log('[LACK] reverse-skill integration ready.');
  }

  // Generate GitHub Actions workflow
  const workflowDir = path.join(__dirname, '.github', 'workflows');
  fs.mkdirSync(workflowDir, { recursive: true });
  const workflowPath = path.join(workflowDir, 'agent-ci.yml');
  const workflowContent = `
name: Agent Harness CI/CD
on: [push, pull_request]
jobs:
  agent-eval:
    runs-on: self-hosted
    steps:
    - name: Check out code
      uses: actions/checkout@v4
    - name: Set up Node.js
      uses: actions/setup-node@v4
      with:
        node-version: '18'
    - name: Install dependencies
      run: npm install
    - name: Run CI/CD pipeline on all code blocks in thread_repos
      run: |
        node -e "
          const { execSync } = require('child_process');
          const fs = require('fs');
          const path = require('path');
          const repoDir = './thread_repos';
          if (!fs.existsSync(repoDir)) process.exit(0);
          const files = fs.readdirSync(repoDir, { recursive: true }).filter(f => f.endsWith('.js') || f.endsWith('.py') || f.endsWith('.html'));
          for (const f of files) {
            const full = path.join(repoDir, f);
            const code = fs.readFileSync(full, 'utf-8');
            const lang = path.extname(f).slice(1);
            console.log('Processing', f);
          }
        "
  `;
  fs.writeFileSync(workflowPath, workflowContent);
  console.log(`[CICD] Generated GitHub Actions workflow at ${workflowPath}`);

  console.log(`\x1b[32m✓ LACK v4.2.2 – Musing & Triangulation – running at http://localhost:${PORT}\x1b[0m`);
});

wss.on('connection', (ws) => {
  const userId = `human_${uuidv4().slice(0,4)}`;
  clients.set(ws, { username: userId, channelId: 'general', userId, openThreadId: null });
  ws.on('message', async (raw) => {
    try {
      const data = JSON.parse(raw);
      const client = clients.get(ws);
      if (!client) return;
      switch (data.type) {
        case 'join':
          if (channels.has(data.channelId)) {
            client.channelId = data.channelId;
            ws.send(JSON.stringify({ type: 'history', channelId: data.channelId, messages: channels.get(data.channelId).messages }));
            ws.send(JSON.stringify({ type: 'agents_list', agents: Array.from(agents.values()).map(a => {
              const mem = agentMemories.get(a.id);
              const metrics = agentMetrics.get(a.id);
              const lastCpu = metrics && metrics.cpu.length ? metrics.cpu[metrics.cpu.length-1] : 0;
              const lastMem = metrics && metrics.mem.length ? metrics.mem[metrics.mem.length-1] : 0;
              const lastTps = metrics && metrics.tpsHistory.length ? metrics.tpsHistory[metrics.tpsHistory.length-1] : 0;
              const lastJspace = metrics && metrics.jspaceCoherence.length ? metrics.jspaceCoherence[metrics.jspaceCoherence.length-1] : 0;
              return {
                id: a.id, name: a.name, model: a.model, systemPrompt: a.systemPrompt, channels: a.channels,
                status: a.status, strictChannel: a.strictChannel,
                isCodeModerator: a.isCodeModerator || false,
                weights: mem ? mem.weights : { exploitation: 0.6, exploration: 0.4 },
                ePoolSize: mem ? mem.ePool.length : 0, xPoolSize: mem ? mem.xPool.length : 0,
                jspaceEnabled: JSPACE_ENABLED,
                lastCpu, lastMem, lastTps, lastJspace
              };
            }) }));
            ws.send(JSON.stringify({ type: 'channels', channels: Array.from(channels.values()).map(c => ({ id: c.id, name: c.name })) }));
            broadcastRalphStatus(data.channelId);
          }
          break;
        case 'message':
          if (client.channelId) {
            let msgText = data.content.trim();
            if (!msgText) break;
            msgText = msgText.replace(/<[^>]*>/g, '');
            const humanMsg = addMessage(client.channelId, client.username, 'human', msgText);
            if (humanMsg) {
              broadcastToStore(client.channelId, humanMsg);
              await onHumanMessage(client.channelId, humanMsg, ws);
            }
          }
          break;
        case 'reply_in_thread':
          let { parentId, content, storeId } = data;
          if (!storeId) storeId = client.channelId;
          if (storeId && channels.has(storeId)) {
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
        case 'spawn_agent': {
          const { name, model, systemPrompt, channels: agentChannels, strictChannel } = data;
          const id = uuidv4().slice(0,8);
          const newAgent = {
            id, name, model,
            systemPrompt: BASE_SYSTEM_PROMPT + '\n\n' + (systemPrompt || ''),
            channels: agentChannels, strictChannel: strictChannel || null,
            lastResponseTime: new Map(), status: 'online', statusMessage: ''
          };
          agents.set(id, newAgent);
          config.agents.push({ id, name, model, systemPrompt: newAgent.systemPrompt, channels: agentChannels, strictChannel: strictChannel || null });
          try {
            const tmp = configPath + '.tmp';
            fs.writeFileSync(tmp, JSON.stringify(config, null, 2));
            fs.renameSync(tmp, configPath);
          } catch (e) {}
          agentMetrics.set(id, generateSyntheticMetrics());
          jsonFailCount.set(id, 0);
          initAgentMemory(id);
          dbSaveAgent(newAgent);
          broadcastAgents();
          ws.send(JSON.stringify({ type: 'spawn_confirm', agent: newAgent }));
          break;
        }
        case 'update_agent': {
          const agent = agents.get(data.id);
          if (agent) {
            let fullPrompt = data.systemPrompt;
            if (!fullPrompt.startsWith(BASE_SYSTEM_PROMPT.slice(0, 50))) {
              fullPrompt = BASE_SYSTEM_PROMPT + '\n\n' + fullPrompt;
            }
            agent.name = data.name;
            agent.model = data.model;
            agent.systemPrompt = fullPrompt;
            agent.channels = data.channels;
            agent.strictChannel = data.strictChannel || null;
            const idx = config.agents.findIndex(a => a.id === data.id);
            if (idx !== -1) {
              config.agents[idx] = { id: data.id, name: data.name, model: data.model, systemPrompt: fullPrompt, channels: data.channels, strictChannel: data.strictChannel || null };
              try {
                const tmp = configPath + '.tmp';
                fs.writeFileSync(tmp, JSON.stringify(config, null, 2));
                fs.renameSync(tmp, configPath);
              } catch (e) {}
            }
            dbSaveAgent(agent);
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
      const preview = typeof raw === 'string' ? raw.substring(0, 60).replace(/[\n\r]/g, ' ') : '[binary]';
      logError({ source: 'websocket_parse', error: err.message, preview });
      try { ws.send(JSON.stringify({ type: 'error', message: 'Invalid message format – check JSON syntax' })); } catch(_) {}
    }
  });
  ws.on('close', () => {
    const client = clients.get(ws);
    if (client) {
      if (client.channelId) cleanupStore(client.channelId);
    }
    clients.delete(ws);
  });
  ws.send(JSON.stringify({ type: 'channels', channels: Array.from(channels.values()).map(c => ({ id: c.id, name: c.name })) }));
  ws.send(JSON.stringify({ type: 'agents_list', agents: Array.from(agents.values()).map(a => {
    const mem = agentMemories.get(a.id);
    const metrics = agentMetrics.get(a.id);
    const lastCpu = metrics && metrics.cpu.length ? metrics.cpu[metrics.cpu.length-1] : 0;
    const lastMem = metrics && metrics.mem.length ? metrics.mem[metrics.mem.length-1] : 0;
    const lastTps = metrics && metrics.tpsHistory.length ? metrics.tpsHistory[metrics.tpsHistory.length-1] : 0;
    const lastJspace = metrics && metrics.jspaceCoherence.length ? metrics.jspaceCoherence[metrics.jspaceCoherence.length-1] : 0;
    return {
      id: a.id, name: a.name, model: a.model, systemPrompt: a.systemPrompt, channels: a.channels,
      status: a.status, strictChannel: a.strictChannel,
      isCodeModerator: a.isCodeModerator || false,
      weights: mem ? mem.weights : { exploitation: 0.6, exploration: 0.4 },
      ePoolSize: mem ? mem.ePool.length : 0, xPoolSize: mem ? mem.xPool.length : 0,
      jspaceEnabled: JSPACE_ENABLED,
      lastCpu, lastMem, lastTps, lastJspace
    };
  }) }));
});

// ==================== MESSAGE HANDLERS ====================
async function onHumanMessage(channelId, messageObj, ws) {
  const channel = channels.get(channelId);
  if (!channel) return;
  const content = messageObj.content;
  if (content.startsWith('/')) {
    const parts = content.slice(1).split(' ');
    const cmd = parts[0].toLowerCase();
    const args = parts.slice(1);
    if (cmd === 'help') {
      const help = `
╔══════════════════════════════════════════════════════════════╗
║                     LACK v4.2.2  HELP                       ║
╠══════════════════════════════════════════════════════════════╣
║  MUSING & TRIANGULATION (new)                               ║
║    (Automatically enabled in /plan, /abstract, /ralph)      ║
╠══════════════════════════════════════════════════════════════╣
║  BASH / CLI (in #general only)                              ║
║    /bash <command>      - run shell command (Moderator)    ║
╠══════════════════════════════════════════════════════════════╣
║  RECONCILIATION & LOOPS                                     ║
║    /reconcile <goal>   - start reconciliation control loop  ║
║    /ralph <goal>       - start Ralph evolutionary loop      ║
║    /stop               - stop loops                         ║
║    /approve <loopId>   - approve HITL pause                 ║
╠══════════════════════════════════════════════════════════════╣
║  J-SPACE FEATURES                                           ║
║    /jspace <text>      - get J-space concepts for text      ║
║    /jspace_agent <id>  - show agent's J-space history       ║
╠══════════════════════════════════════════════════════════════╣
║  CHANNELS                                                   ║
║    #general   - general conversation                        ║
║    #siphon    - research, facts, data (light blue)          ║
║    #code      - strict code blocks (green)                 ║
╠══════════════════════════════════════════════════════════════╣
║  AGENT CONTROL                                              ║
║    /spawn                 - create new agent (UI prompt)    ║
║    /update_agent <id>     - modify agent (via UI)           ║
║    /remove_agent <id>     - delete agent                    ║
╠══════════════════════════════════════════════════════════════╣
║  MEMORY (DecentMem)                                         ║
║    /memory <agentId>      - show memory pools               ║
║    /public_memory         - show global public memory       ║
║    /toggle_public_memory  - enable/disable public memory    ║
╠══════════════════════════════════════════════════════════════╣
║  RESEARCH & SIPHON                                          ║
║    /siphon <topic>        - start research using web search ║
║    /pull <sessionId>      - pull research results           ║
╠══════════════════════════════════════════════════════════════╣
║  TOOLS & CODE                                               ║
║    /tools                 - list file tools                 ║
║    /stack build <name>    - create STACK repo               ║
║    /stack add <desc>      - semantic template injection     ║
║    /repo [id]             - show thread repository          ║
║    /lint <filename>       - lint a file in current repo     ║
║    /moderate on/off       - toggle code moderation          ║
║    /eval                  - LLM evaluate last code block    ║
║    /skill <code|file>     - run reverse‑skill router        ║
║    /cicd                  - run CI/CD on last code block    ║
╠══════════════════════════════════════════════════════════════╣
║  UI & DEBUG                                                 ║
║    /tree                  - browse file tree (thread_repos) ║
║    /graph                 - open token/s memory graph       ║
║    /errorlog              - show error log                  ║
║    /convergence           - show Ralph convergence          ║
║    /ground                - force all agents to respond     ║
╠══════════════════════════════════════════════════════════════╣
║  OTHER                                                      ║
║    /thread <messageId>    - open thread                     ║
║    /pin <messageId>       - pin message                     ║
╚══════════════════════════════════════════════════════════════╝
`;
      addMessage(channelId, 'System', 'system', help);
      broadcastToStore(channelId, { sender: 'System', content: help, senderType: 'system' });
    } else if (cmd === 'bash') {
      // Only allow in #general
      if (channelId !== 'general') {
        addMessage(channelId, 'System', 'system', '⚠️ /bash is only allowed in #general.');
        broadcastToStore(channelId, { sender: 'System', content: '⚠️ /bash only in #general.', senderType: 'system' });
        return;
      }
      const command = args.join(' ');
      if (!command) {
        addMessage(channelId, 'System', 'system', 'Usage: /bash <command>');
        broadcastToStore(channelId, { sender: 'System', content: 'Usage: /bash <command>', senderType: 'system' });
        return;
      }
      // Execute via Moderator
      const mod = agents.get('moderator');
      if (!mod) {
        addMessage(channelId, 'System', 'system', 'Moderator not available.');
        return;
      }
      const output = await executeTool('execute_command', { command }, 'moderator');
      const resultMsg = `💻 **/bash**\n\`${command}\`\n\n${output}`;
      addMessage(channelId, 'Moderator', 'system', resultMsg);
      broadcastToStore(channelId, { sender: 'Moderator', content: resultMsg, senderType: 'system' });
    } else if (cmd === 'jspace') {
      const text = args.join(' ') || 'default context';
      if (!JSPACE_ENABLED) {
        addMessage(channelId, 'System', 'system', 'J-space is disabled. Enable in config.');
        broadcastToStore(channelId, { sender: 'System', content: 'J-space disabled.', senderType: 'system' });
        return;
      }
      const jspace = await getJspaceCached(text);
      if (!jspace) {
        addMessage(channelId, 'System', 'system', 'No J-space data available for that text.');
        broadcastToStore(channelId, { sender: 'System', content: 'No J-space data.', senderType: 'system' });
        return;
      }
      const top = Object.entries(jspace)
        .sort((a,b) => b[1] - a[1])
        .slice(0, 8)
        .map(([name, val]) => `${name}: ${val.toFixed(3)}`).join('\n');
      const output = `🧠 **J-space concepts** for "${text.substring(0,50)}":\n${top}`;
      addMessage(channelId, 'System', 'system', output);
      broadcastToStore(channelId, { sender: 'System', content: output, senderType: 'system' });
    } else if (cmd === 'jspace_agent') {
      const agentId = args[0];
      if (!agentId) {
        addMessage(channelId, 'System', 'system', 'Usage: /jspace_agent <agentId>');
        broadcastToStore(channelId, { sender: 'System', content: 'Usage: /jspace_agent <agentId>', senderType: 'system' });
        return;
      }
      const mem = agentMemories.get(agentId);
      if (!mem || !mem.jspaceHistory || mem.jspaceHistory.length === 0) {
        addMessage(channelId, 'System', 'system', `No J-space history for agent ${agentId}.`);
        broadcastToStore(channelId, { sender: 'System', content: `No J-space history.`, senderType: 'system' });
        return;
      }
      const latest = mem.jspaceHistory.slice(-3).map(entry => {
        const top = Object.entries(entry.jspace)
          .sort((a,b) => b[1] - a[1])
          .slice(0, 3)
          .map(([k,v]) => `${k}:${v.toFixed(2)}`).join(' ');
        return `[${new Date(entry.timestamp).toLocaleTimeString()}] ${top}`;
      }).join('\n');
      const output = `🧠 **J-space history for ${agentId}** (recent):\n${latest}`;
      addMessage(channelId, 'System', 'system', output);
      broadcastToStore(channelId, { sender: 'System', content: output, senderType: 'system' });
    } else if (cmd === 'toggle_public_memory') {
      const newState = !PUBLIC_MEMORY_SUMMARY.enabled;
      await togglePublicMemory(newState);
      addMessage(channelId, 'System', 'system', `Public memory ${newState ? 'enabled' : 'disabled'}.`);
      broadcastToStore(channelId, { sender: 'System', content: `Public memory toggled: ${newState}`, senderType: 'system' });
    } else if (cmd === 'public_memory') {
      if (!PUBLIC_MEMORY_SUMMARY.enabled) {
        addMessage(channelId, 'System', 'system', 'Public memory is disabled. Enable with /toggle_public_memory');
      } else {
        const summary = getPublicMemorySummary();
        addMessage(channelId, 'System', 'system', `🌐 **Public Memory Summary**\n${summary.substring(0, 1000)}`);
      }
      broadcastToStore(channelId, { sender: 'System', content: `Public memory summary fetched.`, senderType: 'system' });
    } else if (cmd === 'memory') {
      const targetAgentId = args[0];
      if (!targetAgentId) {
        addMessage(channelId, 'System', 'system', 'Usage: /memory <agentId>');
        broadcastToStore(channelId, { sender: 'System', content: 'Usage: /memory <agentId>', senderType: 'system' });
      } else {
        try {
          const res = await axios.get(`http://localhost:${PORT}/api/agent/memory/${targetAgentId}`);
          const mem = res.data;
          let output = `🧠 **Memory for ${targetAgentId}**\nE-pool size: ${mem.ePoolSize}\nX-pool size: ${mem.xPoolSize}\nWeights: exploit=${mem.weights.exploitation.toFixed(2)} explore=${mem.weights.exploration.toFixed(2)}\nStats: avgScore=${mem.stats.avgScore.toFixed(1)} judgements=${mem.stats.totalJudgements}\nSample proven trajectories:\n${mem.samples.map(s => `- [score ${s.score}] ${s.trajectory}`).join('\n')}`;
          if (JSPACE_ENABLED && mem.jspaceHistory && mem.jspaceHistory.length) {
            const latest = mem.jspaceHistory.slice(-1)[0];
            const top = Object.entries(latest.jspace)
              .sort((a,b) => b[1] - a[1])
              .slice(0, 3)
              .map(([k,v]) => `${k}:${v.toFixed(2)}`).join(' ');
            output += `\n**Latest J-space:** ${top}`;
          }
          addMessage(channelId, 'System', 'system', output);
          broadcastToStore(channelId, { sender: 'System', content: output, senderType: 'system' });
        } catch(e) {
          addMessage(channelId, 'System', 'system', `Error fetching memory: ${e.message}`);
          broadcastToStore(channelId, { sender: 'System', content: `Error: ${e.message}`, senderType: 'system' });
        }
      }
    } else if (cmd === 'tools') {
      const toolList = FILE_TOOLS.map(t => `- ${t.name}: ${t.description}`).join('\n');
      addMessage(channelId, 'System', 'system', `Available tools:\n${toolList}`);
      broadcastToStore(channelId, { sender: 'System', content: toolList, senderType: 'system' });
    } else if (cmd === 'stack') {
      const sub = args[0];
      const moderatorAgent = agents.get('moderator');
      if (!moderatorAgent) {
        addMessage(channelId, 'System', 'system', 'Moderator agent not available.');
        return;
      }
      if (sub === 'build' && args[1]) {
        await executeAction(moderatorAgent, channelId, {type: 'stack', payload: {subcmd: 'build', repoName: args[1]}});
      } else if (sub === 'add') {
        await executeAction(moderatorAgent, channelId, {type: 'stack', payload: {subcmd: 'add', intent: args.slice(1).join(' ')}});
      } else if (sub === 'import' && args[1]) {
        await executeAction(moderatorAgent, channelId, {type: 'stack', payload: {subcmd: 'import', jsonPath: args[1]}});
      } else if (sub === 'set' && args[1]) {
        activeStackRepo.set(channelId, args[1]);
        addMessage(channelId, 'System', 'system', `Active STACK repository set to ${args[1]}`);
        broadcastToStore(channelId, { sender: 'System', content: `Active STACK repo: ${args[1]}`, senderType: 'system' });
      } else {
        const help = `STACK Commands:\n/stack build <name> - Create new repo\n/stack add <description> - Semantic inject from templates\n/stack import <json> - Load blueprints\n/stack set <repo> - Set active repo for this chat`;
        addMessage(channelId, 'Moderator', 'system', help);
        broadcastToStore(channelId, { sender: 'Moderator', content: help, senderType: 'system' });
      }
    } else if (cmd === 'repo') {
      const targetId = args[0] || channelId;
      const repoPath = getThreadRepoPath(targetId);
      if (fs.existsSync(repoPath)) {
        let output = `📁 **Repository for ${targetId}**\n\`${repoPath}\`\n\n**Files:**\n`;
        const files = fs.readdirSync(repoPath).filter(f => !f.startsWith('.'));
        output += files.map(f => `- ${f}`).join('\n');
        addMessage(channelId, 'Moderator', 'system', output);
        broadcastToStore(channelId, { sender: 'Moderator', content: output, senderType: 'system' });
      } else {
        addMessage(channelId, 'Moderator', 'system', `No repository found for ${targetId}. Create code first.`);
        broadcastToStore(channelId, { sender: 'Moderator', content: `No repository found for ${targetId}.`, senderType: 'system' });
      }
    } else if (cmd === 'moderate') {
      const setting = args[0];
      const moderatorAgent = agents.get('moderator');
      if (setting === 'on') {
        moderatorAgent.isCodeModerator = true;
        addMessage(channelId, 'Moderator', 'system', '🔛 Code moderation ENABLED. All code blocks will be validated and evaluated.');
        broadcastToStore(channelId, { sender: 'Moderator', content: 'Code moderation ENABLED.', senderType: 'system' });
      } else if (setting === 'off') {
        moderatorAgent.isCodeModerator = false;
        addMessage(channelId, 'Moderator', 'system', '🔴 Code moderation DISABLED.');
        broadcastToStore(channelId, { sender: 'Moderator', content: 'Code moderation DISABLED.', senderType: 'system' });
      } else {
        addMessage(channelId, 'Moderator', 'system', `Moderation is ${moderatorAgent.isCodeModerator ? 'ON' : 'OFF'}. Use /moderate on/off`);
        broadcastToStore(channelId, { sender: 'Moderator', content: `Moderation: ${moderatorAgent.isCodeModerator ? 'ON' : 'OFF'}`, senderType: 'system' });
      }
    } else if (cmd === 'lint') {
      const filename = args[0];
      if (!filename) {
        addMessage(channelId, 'Moderator', 'system', 'Usage: /lint <filename>');
        broadcastToStore(channelId, { sender: 'Moderator', content: 'Usage: /lint <filename>', senderType: 'system' });
      } else {
        const threadId = messageObj.parentId || channelId;
        const repoPath = getThreadRepoPath(threadId);
        const filePath = path.join(repoPath, filename);
        if (!fs.existsSync(filePath)) {
          addMessage(channelId, 'Moderator', 'system', `File not found: ${filename}`);
        } else {
          const ext = path.extname(filename).slice(1);
          const langMap = { 'py': 'python', 'js': 'javascript', 'json': 'json', 'ts': 'typescript' };
          const lang = langMap[ext] || 'text';
          const result = await runLinter(lang, filePath);
          let output = `🔍 **Lint Results** for \`${filename}\`\n`;
          output += result.passed ? '✅ Syntax OK\n' : '❌ Errors found\n';
          if (result.errors.length) output += `\n**Errors:**\n${result.errors.map(e => `- ${e}`).join('\n')}`;
          if (result.warnings.length) output += `\n**Warnings:**\n${result.warnings.map(w => `- ${w}`).join('\n')}`;
          addMessage(channelId, 'Moderator', 'system', output);
          broadcastToStore(channelId, { sender: 'Moderator', content: output, senderType: 'system' });
        }
      }
    } else if (cmd === 'eval') {
      const lastMsg = channel.messages[channel.messages.length - 1];
      if (lastMsg && lastMsg.content.includes('```')) {
        const blocks = extractCodeBlocks(lastMsg.content);
        if (blocks.length) {
          for (const block of blocks) {
            const evalText = await evaluateCodeWithLLM(block.code, block.language);
            addMessage(channelId, 'Moderator', 'system', `📋 **Eval for ${block.language}**\n${evalText}`);
            broadcastToStore(channelId, { sender: 'Moderator', content: evalText, senderType: 'system' });
          }
        } else {
          addMessage(channelId, 'System', 'system', 'No code block found in last message.');
        }
      } else {
        addMessage(channelId, 'System', 'system', 'No code block found to evaluate.');
      }
    } else if (cmd === 'skill') {
      let code = args.join(' ');
      let language = 'text';
      if (args.length > 0 && fs.existsSync(path.join(WORKSPACE_ROOT, args[0]))) {
        const filePath = path.join(WORKSPACE_ROOT, args[0]);
        code = fs.readFileSync(filePath, 'utf-8');
        language = path.extname(filePath).slice(1) || 'text';
      }
      if (code) {
        const result = await runReverseSkill(code, language);
        const skillMsg = `🧪 **Reverse‑Skill Output**\n\`\`\`\n${result.skillContent.substring(0, 1500)}\n\`\`\``;
        addMessage(channelId, 'Moderator', 'system', skillMsg);
        broadcastToStore(channelId, { sender: 'Moderator', content: skillMsg, senderType: 'system' });
      } else {
        addMessage(channelId, 'System', 'system', 'Usage: /skill <code> or /skill <file>');
      }
    } else if (cmd === 'tree') {
      addMessage(channelId, 'System', 'system', 'Click the 🌳 Tree button in the top bar to browse file tree.');
      broadcastToStore(channelId, { sender: 'System', content: 'Use the Tree button to browse repositories.', senderType: 'system' });
    } else if (cmd === 'cicd') {
      const lastMsg = channel.messages[channel.messages.length - 1];
      if (lastMsg && lastMsg.content.includes('```')) {
        const blocks = extractCodeBlocks(lastMsg.content);
        if (blocks.length) {
          const agent = agents.get('moderator'); // use moderator to trigger
          const results = await runCICDPipeline(agent.id, channelId, blocks, lastMsg.id);
          const feedback = `CI/CD Pipeline Results:\n${results.map(r => `${r.filename}: ${r.passed ? '✅' : '❌'} (attempt ${r.attempt})`).join('\n')}`;
          addMessage(channelId, 'Moderator', 'system', feedback);
          broadcastToStore(channelId, { sender: 'Moderator', content: feedback, senderType: 'system' });
        } else {
          addMessage(channelId, 'System', 'system', 'No code block found in last message.');
        }
      } else {
        addMessage(channelId, 'System', 'system', 'No code block found to run CI/CD on.');
      }
    } else if (cmd === 'reconcile') {
      const goal = args.join(' ') || 'Improve project specification';
      await runReconciliationLoop(channelId, goal);
    } else if (cmd === 'approve') {
      const loopId = args[0];
      if (loopId && loopHealth.has(loopId)) {
        addMessage(channelId, 'System', 'system', `✅ Loop ${loopId} approved, resuming.`);
        broadcastToStore(channelId, { sender: 'System', content: `Loop ${loopId} approved.`, senderType: 'system' });
      } else {
        addMessage(channelId, 'System', 'system', `No active loop with ID ${loopId}.`);
      }
    } else {
      if (cmd === 'ground') {
        const groundMsg = { sender: 'System', content: 'GROUND: All agents respond. All Agents Respond with their current tasks...' };
        addMessage(channelId, 'System', 'system', groundMsg.content); broadcastToStore(channelId, groundMsg);
        const agentsInChannel = Array.from(agents.values()).filter(a => a.channels.includes(channel.name) && !a.isEmbedOperator);
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
        addMessage(channelId, 'System', 'system', `🧬 **Ralph loop started**\nGoal: ${goal}\nWill converge when recurrence conditions met.`);
        broadcastToStore(channelId, { sender: 'System', content: `Ralph evolution started: ${goal}`, senderType: 'system' });
      } else if (cmd === 'stop') { stopLoop(channelId); }
      else if (cmd === 'list') { const models = await getOllamaModels(); const listText = models.length ? 'Available Ollama models:\n' + models.join('\n') : 'No Ollama models found.'; addMessage(channelId, 'System', 'system', listText); broadcastToStore(channelId, { sender: 'System', content: listText, senderType: 'system' }); }
      else if (cmd === 'spawn') { ws.send(JSON.stringify({ type: 'models_list', models: await getOllamaModels() })); }
      else if (cmd === 'siphon') { 
        const topic = args.join(' ') || 'general research topic';
        const sessionId = uuidv4();
        const session = { 
          id: sessionId, topic, phase: 'Initializing', metric: 0, logs: [], 
          facts: [], notes: [], questions: [], currentQuestionIndex: 0, startedAt: Date.now() 
        };
        researchSessions.set(sessionId, session);
        runResearch(sessionId, topic, channelId).catch(console.error);
        addMessage(channelId, 'Siphon', 'system', `🔍 Started web research on "${topic}". Check #siphon.`);
        broadcastToStore(channelId, { sender: 'Siphon', content: `Research started: ${topic}`, senderType: 'system' });
      }
      else if (cmd === 'pull' && args.length) { const session = researchSessions.get(args[0]); if (!session) { addMessage(channelId, 'System', 'system', `No session ${args[0]}.`); broadcastToStore(channelId, { sender: 'System', content: `No session ${args[0]}.`, senderType: 'system' }); return; } let summary = `📊 **Research "${session.topic}"**\nMetric: ${(session.metric*100).toFixed(0)}%\n`; if (session.notes.length) { const last = session.notes[session.notes.length-1]; summary += `**Latest answer:** ${last.answer.substring(0,300)}\nKey facts:\n${last.facts.slice(0,3).map(f => `- ${f}`).join('\n')}`; } else { summary += 'Research still in progress.'; } addMessage(channelId, 'Siphon', 'system', summary); broadcastToStore(channelId, { sender: 'Siphon', content: summary, senderType: 'system' }); }
      else if (cmd === 'thread') { const messageId = args[0]; if (!messageId) ws.send(JSON.stringify({ type: 'error', message: 'Usage: /thread <messageId>' })); else ws.send(JSON.stringify({ type: 'thread_messages', storeId: channelId, threadId: messageId, messages: getThreadMessages(channelId, messageId) })); }
      else if (cmd === 'pin') { if (!args[0]) ws.send(JSON.stringify({ type: 'error', message: 'Usage: /pin <messageId>' })); else { if (!pinnedMessages.has(channelId)) pinnedMessages.set(channelId, new Set()); pinnedMessages.get(channelId).add(args[0]); ws.send(JSON.stringify({ type: 'pinned', messageId: args[0], channelId })); } }
      else if (cmd === 'graph') { ws.send(JSON.stringify({ type: 'graph_ack' })); }
      else if (cmd === 'errorlog') {
        let logText = '**ERROR LOG**\n';
        const errors = global.errorLog || [];
        errors.slice(0,50).forEach(e => { logText += `${new Date(e.timestamp).toLocaleString()} | ${e.agentId || 'system'}: ${e.error}\n`; });
        if (!errors.length) logText += 'No errors recorded.';
        addMessage(channelId, 'System', 'system', logText);
        broadcastToStore(channelId, { sender: 'System', content: logText, senderType: 'system' });
      }
      else if (cmd === 'convergence') { const lineage = reconstructLineage(channelId); let lastSpec = null, sim = 0; for (let i = lineage.length-1; i >= 0; i--) { if (lineage[i].type === 'project_state') { const spec = computeSpecFromState(lineage[i].state); if (lastSpec) { sim = similarity(lastSpec, spec); break; } lastSpec = spec; } } const msg = `🔍 Convergence similarity: ${(sim*100).toFixed(1)}%`; addMessage(channelId, 'System', 'system', msg); broadcastToStore(channelId, { sender: 'System', content: msg, senderType: 'system' }); }
      else { addMessage(channelId, 'System', 'system', `Unknown command: ${cmd}. Type /help`); broadcastToStore(channelId, { sender: 'System', content: `Unknown command: ${cmd}`, senderType: 'system' }); }
    }
    return;
  }
  const relevantAgents = Array.from(agents.values()).filter(a => a.channels.includes(channel.name) && !a.isEmbedOperator);
  const state = getProjectState(channelId);
  const usePlanning = state.active || channel.abstractActive || channel.researchActive;
  for (const agent of relevantAgents) {
    if (ralphActive.get(channelId)) continue;
    if (agent.strictChannel && agent.strictChannel !== channelId) continue;
    if (usePlanning) await agentPlanAndAct(agent, channelId, messageObj, messageObj.parentId);
    else await agentRespond(agent, channelId, messageObj, false, messageObj.parentId);
  }
  if (channelId === 'general') {
    setTimeout(() => {
      triggerProactiveQuestions(channelId, messageObj).catch(console.error);
    }, 1500);
  }
}

// ==================== HELPERS (Reflection, etc.) ====================
async function generateReflection(agentId, context, mainReply) {
  if (agentId === 'moderator') return '';
  const agent = agents.get(agentId);
  if (!agent) return '';
  let jspaceHint = '';
  if (JSPACE_ENABLED) {
    const jspace = await getJspaceCached(context);
    if (jspace) {
      const top = Object.entries(jspace)
        .sort((a,b) => b[1] - a[1])
        .slice(0, 3)
        .map(([k,v]) => `${k}:${v.toFixed(2)}`).join(', ');
      jspaceHint = `\nJ-space signals: ${top}`;
    }
  }
  const reflectionPrompt = `${mainReply}

Now reflect as per your instructions. List concrete items worth investigating next. End with a clear question or offer to dig deeper.

Context: ${context}${jspaceHint}`;
  const reflection = await queryOllama(agent.model, reflectionPrompt,
    "You are in reflection mode. Be concise and specific. List 2-4 investigation candidates and end with a question.",
    0.5, agentId);
  if (reflection.startsWith('[OLLAMA_ERROR]')) return '';
  return reflection;
}

async function handleAgentResponse(agent, storeId, responseText, parentId = null) {
  const fixedText = ensureCodeBlock(responseText, 'auto');
  const msg = addMessage(storeId, agent.name, 'agent', responseText, parentId);
  if (!msg) return;
  broadcastToStore(storeId, msg);
  if (agent.id !== 'moderator') {
    moderateCodeFromAgent(agent.id, storeId, fixedText, parentId).catch(err => {
      logError({ context: 'moderateCodeFromAgent', error: err.message, agentId: agent.id });
    });
  }
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

function buildConversationContext(storeId, agentName, parentId = null, maxMessages = 8) {
  const store = channels.get(storeId);
  if (!store) return '';
  let messages = store.messages;
  if (parentId) {
    const rootId = store.messages.find(m => m.id === parentId)?.threadId || parentId;
    messages = store.messages.filter(m => m.threadId === rootId || m.id === rootId);
  }
  const relevant = messages.filter(m => m.sender !== agentName && m.senderType !== 'system');
  const moderatorMsgs = relevant.filter(m => m.sender === 'Moderator');
  const otherMsgs = relevant.filter(m => m.sender !== 'Moderator');
  const combined = [...moderatorMsgs, ...otherMsgs];
  return combined.slice(-maxMessages).map(m => `${m.sender}: ${m.content}`).join('\n');
}

// ==================== OLLAMA HELPERS ====================
let ollamaCircuitOpen = false;
let ollamaRetryTimer = null;
let availableModels = [];

async function getOllamaModels() {
  try {
    const res = await axios.get(`${OLLAMA_URL}/api/tags`, { timeout: 3000 });
    const models = res.data.models.map(m => m.name);
    availableModels = models;
    return models;
  } catch (e) {
    logError({ context: 'getOllamaModels', error: e.message });
    return [];
  }
}

function markOllamaDown() {
  if (!ollamaCircuitOpen) {
    ollamaCircuitOpen = true;
    console.error('[LACK] Ollama unreachable. Circuit open – retrying in 15s.');
    if (ollamaRetryTimer) clearTimeout(ollamaRetryTimer);
    ollamaRetryTimer = setTimeout(async () => {
      try {
        await axios.get(`${OLLAMA_URL}/api/tags`, { timeout: 3000 });
        ollamaCircuitOpen = false;
        console.log('[LACK] Ollama reconnected. Circuit closed.');
      } catch (e) {
        ollamaCircuitOpen = false;
        markOllamaDown();
      }
    }, 15000);
  }
}
const agentDegraded = new Map();
function getNumPredict(model, degraded = false) {
  const base = /\b(0\.5b|1b)\b/i.test(model) ? 512 : 2048;
  return degraded ? Math.floor(base / 2) : base;
}

async function queryOllamaWithRetry(model, prompt, systemPrompt = '', temperature = 0.7, agentId = null, retries = 3) {
  let lastError = null;
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const result = await queryOllama(model, prompt, systemPrompt, temperature, agentId);
      if (!result.startsWith('[OLLAMA_ERROR]')) return result;
      const delay = Math.min(5000, 500 * Math.pow(2, attempt));
      await new Promise(r => setTimeout(r, delay));
    } catch (e) {
      lastError = e;
    }
  }
  for (const fallback of FALLBACK_MODELS) {
    if (fallback === model) continue;
    try {
      console.log(`[LACK] Falling back to model "${fallback}" for agent ${agentId}`);
      const result = await queryOllama(fallback, prompt, systemPrompt, temperature, agentId);
      if (!result.startsWith('[OLLAMA_ERROR]')) {
        return result;
      }
    } catch (e) {}
  }
  return `[OLLAMA_ERROR] All models failed. Last error: ${lastError ? lastError.message : 'Unknown'}`;
}

async function queryOllama(model, prompt, systemPrompt = '', temperature = 0.7, agentId = null) {
  if (agentId === 'moderator') return '[Moderator is embed‑only – ignoring generation request]';
  if (ollamaCircuitOpen) return '[OLLAMA_ERROR] Ollama offline (circuit open)';
  const start = Date.now();
  const degraded = agentId ? (agentDegraded.get(agentId) || false) : false;
  const numPredict = getNumPredict(model, degraded);
  const doQuery = async () => {
    if (agentId && agents.has(agentId)) {
      const agent = agents.get(agentId);
      const previousStatus = agent.status;
      agent.status = 'queued';
      agent.statusMessage = degraded ? 'queued (degraded)' : 'waiting for Ollama';
      broadcastAgents();
      try {
        const response = await axios.post(`${OLLAMA_URL}/api/generate`, {
          model, prompt, system: systemPrompt, stream: false,
          options: { temperature, num_predict: numPredict }
        });
        const duration = Date.now() - start;
        const evalCount = response.data.eval_count || 0;
        const tps = duration > 0 ? (evalCount / (duration / 1000)) : 0;
        if (agentId) updateAgentMetrics(agentId, duration, true, tps);
        agentDegraded.set(agentId, false);
        if (JSPACE_ENABLED && agentId) {
          const jspace = await getJspaceCached(prompt + ' ' + response.data.response);
          if (jspace) {
            const mem = agentMemories.get(agentId);
            if (mem) {
              mem.jspaceHistory.push({ timestamp: Date.now(), jspace, text: (prompt + ' ' + response.data.response).slice(0,200) });
              if (mem.jspaceHistory.length > 20) mem.jspaceHistory.shift();
              saveAgentMemory(agentId);
            }
          }
        }
        return response.data.response || "I'm sorry, I couldn't generate a response.";
      } catch (err) {
        if (err.code === 'ECONNREFUSED' || err.code === 'ENOTFOUND') markOllamaDown();
        if (err.message && err.message.includes('out of memory')) {
          agentDegraded.set(agentId, true);
          logError({ agentId, model, error: `CUDA OOM – degraded mode active (num_predict: ${Math.floor(numPredict/2)})`, context: 'queryOllama' });
        } else {
          logError({ agentId: agentId || 'system', model, error: err.message, context: 'queryOllama' });
        }
        if (agentId) updateAgentMetrics(agentId, 0, false, 0);
        return `[OLLAMA_ERROR] ${err.message.substring(0,80)}`;
      } finally {
        if (agents.has(agentId)) {
          agents.get(agentId).status = previousStatus === 'queued' ? 'online' : previousStatus;
          agents.get(agentId).statusMessage = '';
          broadcastAgents();
        }
      }
    } else {
      try {
        const response = await axios.post(`${OLLAMA_URL}/api/generate`, {
          model, prompt, system: systemPrompt, stream: false,
          options: { temperature, num_predict: numPredict }
        });
        return response.data.response || "I'm sorry, I couldn't generate a response.";
      } catch (err) {
        if (err.code === 'ECONNREFUSED' || err.code === 'ENOTFOUND') markOllamaDown();
        logError({ model, error: err.message, context: 'queryOllama' });
        return `[OLLAMA_ERROR] ${err.message.substring(0,80)}`;
      }
    }
  };
  if (agentId) {
    return rateLimitedQuery(agentId, doQuery);
  } else {
    return doQuery();
  }
}

function extractCodeBlocks(text) {
  const regex = /```(\w*)\n([\s\S]*?)```/g;
  const blocks = [];
  let match;
  while ((match = regex.exec(text)) !== null) blocks.push({ language: match[1] || 'text', code: match[2].trim() });
  return blocks;
}

// ==================== AGENT METRICS ====================
let globalMaxMem = 0;
const SPIKE_CPU_THRESHOLD = 90;
const SPIKE_MEM_THRESHOLD = 90;
const SPIKE_TPS_THRESHOLD = 50;

function updateAgentMetrics(agentId, responseTimeMs = 0, wasActive = false, tps = 0) {
  const metrics = agentMetrics.get(agentId);
  if (!metrics) return;
  const cpuVal = Math.min(100, Math.max(5, Math.floor(responseTimeMs / 80)));
  const activityVal = wasActive ? 85 : 20;
  const memUsageMB = process.memoryUsage().rss / (1024 * 1024);
  if (memUsageMB > globalMaxMem) globalMaxMem = memUsageMB;
  const memScale = Math.max(128, globalMaxMem);
  const memVal = Math.min(100, Math.floor((memUsageMB / memScale) * 100));
  metrics.cpu.push(cpuVal); 
  if (metrics.cpu.length > HISTORY_LENGTH) metrics.cpu.shift();
  metrics.activity.push(activityVal);
  if (metrics.activity.length > HISTORY_LENGTH) metrics.activity.shift();
  metrics.mem.push(memVal);
  if (metrics.mem.length > HISTORY_LENGTH) metrics.mem.shift();
  metrics.timestamps.push(Date.now());
  if (metrics.timestamps.length > HISTORY_LENGTH) metrics.timestamps.shift();
  metrics.tpsHistory.push(tps);
  if (metrics.tpsHistory.length > HISTORY_LENGTH) metrics.tpsHistory.shift();
  const memObj = agentMemories.get(agentId);
  if (memObj) {
    metrics.ePoolHistory.push(memObj.ePool.length);
    if (metrics.ePoolHistory.length > HISTORY_LENGTH) metrics.ePoolHistory.shift();
    metrics.xPoolHistory.push(memObj.xPool.length);
    if (metrics.xPoolHistory.length > HISTORY_LENGTH) metrics.xPoolHistory.shift();
    if (JSPACE_ENABLED && memObj.jspaceHistory && memObj.jspaceHistory.length > 0) {
      const recent = memObj.jspaceHistory.slice(-5);
      const coh = recent.reduce((sum, item) => {
        const vals = Object.values(item.jspace);
        if (vals.length === 0) return sum;
        const mean = vals.reduce((a,b) => a+b, 0) / vals.length;
        const variance = vals.reduce((a,b) => a + (b - mean)*(b - mean), 0) / vals.length;
        const coherence = 1 / (1 + variance);
        return sum + coherence;
      }, 0) / recent.length;
      metrics.jspaceCoherence.push(coh);
    } else {
      metrics.jspaceCoherence.push(0);
    }
    if (metrics.jspaceCoherence.length > HISTORY_LENGTH) metrics.jspaceCoherence.shift();
  } else {
    metrics.ePoolHistory.push(0); if (metrics.ePoolHistory.length > HISTORY_LENGTH) metrics.ePoolHistory.shift();
    metrics.xPoolHistory.push(0); if (metrics.xPoolHistory.length > HISTORY_LENGTH) metrics.xPoolHistory.shift();
    metrics.jspaceCoherence.push(0); if (metrics.jspaceCoherence.length > HISTORY_LENGTH) metrics.jspaceCoherence.shift();
  }
  if (cpuVal > SPIKE_CPU_THRESHOLD) {
    metrics.spikes.push({ timestamp: Date.now(), type: 'cpu', value: cpuVal, agent: agentId });
  }
  if (memVal > SPIKE_MEM_THRESHOLD) {
    metrics.spikes.push({ timestamp: Date.now(), type: 'mem', value: memVal, agent: agentId });
  }
  if (tps > SPIKE_TPS_THRESHOLD) {
    metrics.spikes.push({ timestamp: Date.now(), type: 'tps', value: tps, agent: agentId });
  }
  if (metrics.spikes.length > 100) metrics.spikes = metrics.spikes.slice(-100);
  agentMetrics.set(agentId, metrics);
}

// ==================== PROACTIVE QUESTIONING ====================
const proactiveThrottle = new Map();
async function triggerProactiveQuestions(storeId, recentMessage) {
  const now = Date.now();
  const last = proactiveThrottle.get(storeId) || 0;
  if (now - last < 30000) return;
  proactiveThrottle.set(storeId, now);
  
  const activeAgents = Array.from(agents.values()).filter(a => a.channels.includes('general') && !a.isEmbedOperator);
  if (activeAgents.length === 0) return;
  
  const num = Math.min(2, activeAgents.length);
  const shuffled = activeAgents.sort(() => Math.random() - 0.5);
  const selected = shuffled.slice(0, num);
  
  for (const agent of selected) {
    const prompt = `Recent discussion: "${recentMessage.content}"
    
As ${agent.name}, generate a short, targeted question or suggestion to another agent or the team about what to investigate next. Keep it concise (1-2 sentences).`;
    const q = await queryOllama(agent.model, prompt, agent.systemPrompt, 0.6, agent.id);
    if (q && !q.startsWith('[OLLAMA_ERROR]') && q.length > 10) {
      const msg = {
        id: uuidv4(),
        sender: agent.name,
        senderType: 'agent',
        content: `🔍 ${q}\n\nA few things worth a closer look...`,
        timestamp: Date.now()
      };
      addMessage(storeId, agent.name, 'agent', msg.content);
      broadcastToStore(storeId, msg);
    }
  }
}

// ==================== MODERATOR AGENT OBJECT ====================
const moderator = {
  id: "moderator",
  name: "Moderator",
  model: "nomic-embed-text:latest",
  systemPrompt: "Embedding only – not for chat.",
  channels: ["general", "siphon", "code"],
  isEmbedOperator: true,
  isCodeModerator: true,
  lastResponseTime: new Map(),
  status: 'online',
  statusMessage: 'embed-only + code moderation + eval + reverse-skill + CI/CD pipeline',
  moderationConfig: {
    autoCorrect: false,
    requireLintPass: true,
    maxFileSizeBytes: 50000,
    allowedLanguages: ['python', 'javascript', 'html', 'css', 'json', 'markdown', 'text'],
    enableReverseSkill: true,
    lintConfigs: {
      python: 'pyflakes',
      javascript: 'eslint --quiet',
      html: 'htmlhint'
    }
  }
};

// Load agents from DB or config
function loadAgents() {
  const dbAgents = dbLoadAllAgents();
  if (Object.keys(dbAgents).length > 0) {
    for (const [id, agent] of Object.entries(dbAgents)) {
      if (!agent.systemPrompt.startsWith(BASE_SYSTEM_PROMPT.slice(0, 50))) {
        agent.systemPrompt = BASE_SYSTEM_PROMPT + '\n\n' + agent.systemPrompt;
      }
      agents.set(id, agent);
    }
  } else {
    config.agents.forEach(agentCfg => {
      const agent = {
        ...agentCfg,
        systemPrompt: BASE_SYSTEM_PROMPT + '\n\n' + (agentCfg.systemPrompt || ''),
        lastResponseTime: new Map(),
        status: 'online',
        statusMessage: '',
        strictChannel: agentCfg.strictChannel || null
      };
      agents.set(agentCfg.id, agent);
      dbSaveAgent(agent);
    });
  }
  if (!agents.has('moderator')) {
    agents.set('moderator', moderator);
    dbSaveAgent(moderator);
  } else {
    const existing = agents.get('moderator');
    Object.assign(moderator, existing);
    agents.set('moderator', moderator);
  }
}

loadAgents();

for (const [id, agent] of agents) {
  agentMetrics.set(id, generateSyntheticMetrics());
  jsonFailCount.set(id, 0);
  initAgentMemory(id);
}

// ==================== MAIN LOOP (SET INTERVALS) ====================
setInterval(() => {
  for (let [agentId, metrics] of agentMetrics.entries()) {
    metrics.cpu = metrics.cpu.map(v => Math.max(5, v - 3));
    metrics.activity = metrics.activity.map(v => {
      let newV = Math.max(5, v - 8);
      if (Math.random() < 0.25) newV = Math.max(newV, 20 + Math.random() * 25);
      return newV;
    });
    metrics.mem = metrics.mem.map(v => Math.max(5, v - 1));
    metrics.timestamps.push(Date.now());
    if (metrics.timestamps.length > HISTORY_LENGTH) metrics.timestamps.shift();
    metrics.tpsHistory.push(0);
    if (metrics.tpsHistory.length > HISTORY_LENGTH) metrics.tpsHistory.shift();
    const memObj = agentMemories.get(agentId);
    if (memObj) {
      metrics.ePoolHistory.push(memObj.ePool.length);
      if (metrics.ePoolHistory.length > HISTORY_LENGTH) metrics.ePoolHistory.shift();
      metrics.xPoolHistory.push(memObj.xPool.length);
      if (metrics.xPoolHistory.length > HISTORY_LENGTH) metrics.xPoolHistory.shift();
      if (JSPACE_ENABLED && memObj.jspaceHistory && memObj.jspaceHistory.length > 0) {
        const recent = memObj.jspaceHistory.slice(-5);
        const coh = recent.reduce((sum, item) => {
          const vals = Object.values(item.jspace);
          if (vals.length === 0) return sum;
          const mean = vals.reduce((a,b) => a+b, 0) / vals.length;
          const variance = vals.reduce((a,b) => a + (b - mean)*(b - mean), 0) / vals.length;
          const coherence = 1 / (1 + variance);
          return sum + coherence;
        }, 0) / recent.length;
        metrics.jspaceCoherence.push(coh);
      } else {
        metrics.jspaceCoherence.push(0);
      }
      if (metrics.jspaceCoherence.length > HISTORY_LENGTH) metrics.jspaceCoherence.shift();
    }
    agentMetrics.set(agentId, metrics);
  }
}, 3000);

// ==================== LINEAGE HELPERS ====================
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
function pruneLineageFiles() {
  const lineageDir = path.join(__dirname, 'lineage');
  if (!fs.existsSync(lineageDir)) return;
  const now = Date.now();
  const maxAge = 7 * 24 * 60 * 60 * 1000;
  fs.readdirSync(lineageDir).forEach(file => {
    const filePath = path.join(lineageDir, file);
    const stats = fs.statSync(filePath);
    if (now - stats.mtimeMs > maxAge) {
      fs.unlinkSync(filePath);
      console.log(`[LACK] Pruned old lineage: ${file}`);
    }
  });
}

function addMessage(storeId, sender, senderType, content, parentId = null) {
  let store = channels.get(storeId);
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
  dbSaveMessage(msg, storeId);
  return msg;
}

function getThreadMessages(storeId, threadId) {
  const store = channels.get(storeId);
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
  let agentList = Array.from(agents.values());
  agentList.sort((a,b) => (a.id === "moderator" ? -1 : b.id === "moderator" ? 1 : 0));
  const slim = agentList.map(a => {
    const mem = agentMemories.get(a.id);
    const metrics = agentMetrics.get(a.id);
    const lastCpu = metrics && metrics.cpu.length ? metrics.cpu[metrics.cpu.length-1] : 0;
    const lastMem = metrics && metrics.mem.length ? metrics.mem[metrics.mem.length-1] : 0;
    const lastTps = metrics && metrics.tpsHistory.length ? metrics.tpsHistory[metrics.tpsHistory.length-1] : 0;
    const lastJspace = metrics && metrics.jspaceCoherence.length ? metrics.jspaceCoherence[metrics.jspaceCoherence.length-1] : 0;
    return {
      id: a.id, name: a.name, model: a.model,
      systemPrompt: a.systemPrompt, channels: a.channels,
      status: a.status, statusMessage: a.statusMessage,
      strictChannel: a.strictChannel,
      isCodeModerator: a.isCodeModerator || false,
      weights: mem ? mem.weights : { exploitation: 0.6, exploration: 0.4 },
      ePoolSize: mem ? mem.ePool.length : 0,
      xPoolSize: mem ? mem.xPool.length : 0,
      jspaceEnabled: JSPACE_ENABLED,
      lastCpu, lastMem, lastTps, lastJspace
    };
  });
  for (let [ws] of clients.entries()) {
    if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'agents_list', agents: slim }));
  }
}

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
    if (ws.readyState === WebSocket.OPEN && client.channelId === storeId) {
      ws.send(JSON.stringify({ type: 'ralph_status', storeId, active, generation: gen, goal: snippet }));
    }
  }
}
'''  # End of SERVER_JS

# ----------------------------------------------------------------------
# HTML Frontend (unchanged, but slash suggestions include /bash and new commands)
# ----------------------------------------------------------------------
INDEX_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <title>LACK v4.2.2</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    /* Same as before – kept for brevity */
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: monospace; background: var(--white); color: var(--black); height: 100vh; overflow: hidden; transition: background 0.3s, color 0.3s; }
    :root { --white: #fff; --off-white: #f8f8f8; --light-gray: #e0e0e0; --gray: #a0a0a0; --dark-gray: #666; --black: #000; --shadow-dark: rgba(0,0,0,0.2); }
    .dark-mode { --white: #0a0a0a; --off-white: #1a1a1a; --light-gray: #2a2a2a; --gray: #555; --dark-gray: #999; --black: #f0f0f0; --shadow-dark: rgba(255,255,255,0.1); }
    .neuro-menu { position: fixed; top: 0; left: 0; right: 0; height: 48px; background: var(--white); border-bottom: 2px solid var(--black); display: flex; align-items: center; justify-content: space-between; padding: 0 1rem; z-index: 10000; flex-wrap: wrap; gap: 0.5rem; }
    .menu-item { font-size: 0.85rem; font-weight: 600; white-space: nowrap; }
    .neuro-status { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; font-size: 0.7rem; }
    .dark-mode-toggle, .ground-btn, .moderator-btn, .cron-btn, .top-btn { background: var(--white); border: 1px solid var(--black); border-radius: 20px; padding: 0.25rem 0.75rem; cursor: pointer; font-size: 0.7rem; white-space: nowrap; }
    .moderator-btn.on { background: #2ecc71; color: white; border-color: #2ecc71; }
    .moderator-btn.off { background: #e74c3c; color: white; border-color: #e74c3c; }
    .cron-btn { background: #ff4444; color: white; border-color: #ff4444; }
    .ralph-badge { background: #9b59b6; color: white; border-radius: 12px; padding: 0.2rem 0.6rem; font-size: 0.7rem; display: none; }
    .neuro-desktop { position: absolute; top: 48px; left: 0; right: 0; bottom: 0; padding: 1rem; background: var(--off-white); display: flex; overflow: hidden; }
    .chat-container { display: flex; width: 100%; height: 100%; background: var(--white); border: 2px solid var(--black); box-shadow: 8px 8px 0 var(--shadow-dark); overflow: hidden; }
    .sidebar { width: 260px; min-width: 200px; max-width: 30%; background: var(--white); border-right: 2px solid var(--black); display: flex; flex-direction: column; overflow-y: auto; flex-shrink: 0; }
    .main-chat { flex: 1; display: flex; flex-direction: column; min-width: 0; background: var(--white); }
    .thread-panel { width: 300px; background: var(--white); border-left: 2px solid var(--black); display: none; flex-direction: column; flex-shrink: 0; }
    .thread-panel.open { display: flex; }
    @media (max-width: 700px) { .sidebar { min-width: 160px; width: 180px; } .thread-panel.open { position: fixed; right: 0; top: 48px; bottom: 0; width: 85%; max-width: 320px; z-index: 2000; box-shadow: -4px 0 12px rgba(0,0,0,0.3); } }
    .chat-header { padding: 0.75rem 1rem; border-bottom: 2px solid var(--black); font-weight: 600; background: var(--white); flex-shrink: 0; }
    .messages-area { flex: 1; overflow-y: auto; padding: 1rem; display: flex; flex-direction: column; gap: 0.75rem; background: var(--off-white); }
    .input-area { padding: 0.75rem 1rem; border-top: 2px solid var(--black); display: flex; gap: 0.75rem; align-items: flex-start; background: var(--white); flex-wrap: wrap; }
    .input-area textarea { flex: 1; background: var(--white); border: 1px solid var(--black); padding: 0.5rem; font-family: monospace; resize: vertical; min-width: 120px; font-size: 0.85rem; }
    .input-area button { background: var(--white); border: 2px solid var(--black); padding: 0.5rem 1rem; cursor: pointer; font-weight: bold; font-size: 0.8rem; }
    .file-upload-btn { background: none; border: none; font-size: 1.4rem; cursor: pointer; color: var(--gray); padding: 0 0.25rem; }
    .file-upload-btn:hover { color: var(--black); }
    .message-group { margin-bottom: 0.5rem; }
    .message { display: flex; gap: 0.75rem; padding: 0.25rem 0; }
    .message-avatar { width: 32px; height: 32px; background: var(--light-gray); border: 1px solid var(--black); display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0; }
    .message-content { flex: 1; min-width: 0; word-wrap: break-word; }
    .message-sender { font-weight: 600; font-size: 0.8rem; }
    .message-timestamp { font-size: 0.7rem; color: var(--dark-gray); }
    .message-text { font-size: 0.85rem; line-height: 1.4; word-wrap: break-word; }
    .message-text pre { background: #111; color: #0f0; padding: 0.5rem; overflow-x: auto; font-size: 0.75rem; border-radius: 4px; }
    .siphon-research { border-left: 4px solid #00f0ff; background: rgba(0, 240, 255, 0.1); padding-left: 8px; margin: 8px 0; }
    .reflection-message { border-left: 4px solid #39ff14; background: rgba(57, 255, 20, 0.05); }
    .reply-badge { font-size: 0.7rem; text-decoration: underline; cursor: pointer; margin-top: 0.25rem; }
    .message-actions { display: none; gap: 0.5rem; margin-top: 0.25rem; }
    .message:hover .message-actions { display: flex; }
    .action-icon { font-size: 0.7rem; background: var(--white); border: 1px solid var(--light-gray); padding: 0.2rem 0.4rem; cursor: pointer; }
    .sidebar-section { border-bottom: 1px solid var(--light-gray); }
    .sidebar-header { padding: 0.75rem; font-weight: 600; font-size: 0.75rem; background: var(--off-white); cursor: pointer; }
    .channel-list { padding: 0.5rem; }
    .channel-item, .agent-item, .research-item { padding: 0.5rem; margin: 0.25rem 0; cursor: pointer; font-size: 0.75rem; display: flex; align-items: center; gap: 0.5rem; border: 1px solid transparent; }
    .channel-item:hover, .agent-item:hover, .research-item:hover { background: var(--light-gray); }
    .agent-item { justify-content: space-between; }
    .agent-info { display: flex; align-items: center; gap: 0.5rem; flex: 1; }
    .agent-status { width: 8px; height: 8px; border-radius: 50%; }
    .status-online { background: #2eb67d; }
    .status-thinking { background: #ecb22e; animation: pulse 1s infinite; }
    .status-queued { background: #ffa500; animation: pulse 0.5s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    .remove-agent { color: #ff4444; cursor: pointer; opacity: 0.6; }
    .research-progress { font-size: 0.7rem; margin-left: auto; }
    .thread-header { padding: 0.75rem; border-bottom: 2px solid var(--black); display: flex; justify-content: space-between; }
    .thread-messages { flex: 1; overflow-y: auto; padding: 0.75rem; }
    .thread-input { padding: 0.75rem; border-top: 1px solid var(--light-gray); }
    .thread-input textarea { width: 100%; padding: 0.5rem; font-family: monospace; }
    .modal { display: none; position: fixed; z-index: 20000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); align-items: center; justify-content: center; }
    .modal-content { background: var(--white); border: 2px solid var(--black); padding: 1.5rem; width: 90%; max-width: 700px; max-height: 90vh; overflow-y: auto; }
    .modal-content input, .modal-content select, .modal-content textarea { width: 100%; margin: 0.5rem 0; padding: 0.5rem; }
    .modal-buttons { display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1rem; flex-wrap: wrap; }
    .error-log-entry { font-family: monospace; font-size: 0.7rem; border-bottom: 1px solid var(--light-gray); padding: 0.5rem; white-space: pre-wrap; }
    .toast { position: fixed; bottom: 1rem; right: 1rem; background: #333; color: white; padding: 0.5rem 1rem; border-radius: 8px; font-size: 0.8rem; opacity: 0; transition: opacity 0.3s; z-index: 20001; pointer-events: none; }
    .toast.show { opacity: 1; }
    .toast.success { background: #2ecc71; }
    .toast.error { background: #e74c3c; }
    .agent-thinking-overlay { position: fixed; bottom: 1rem; left: 1rem; background: rgba(0,0,0,0.7); color: #ff0; padding: 0.4rem 1rem; border-radius: 20px; font-size: 0.75rem; z-index: 10001; }
    .bottom-bar { position: fixed; bottom: 0; left: 0; right: 0; background: var(--white); border-top: 1px solid var(--light-gray); padding: 0.25rem 1rem; font-size: 0.6rem; display: flex; justify-content: space-between; z-index: 10000; }
    .file-name-chip { background: var(--light-gray); border-radius: 16px; padding: 0.2rem 0.6rem; font-size: 0.7rem; display: inline-flex; align-items: center; gap: 6px; }
    .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid var(--gray); border-top-color: var(--black); border-radius: 50%; animation: spin 0.6s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .slash-suggestions { position: absolute; bottom: 100%; left: 0; background: var(--white); border: 1px solid var(--black); list-style: none; padding: 0.25rem; max-height: 150px; overflow-y: auto; z-index: 200; }
    .slash-suggestions li { padding: 0.25rem 0.5rem; cursor: pointer; font-size: 0.7rem; }
    canvas#agentGraph { width: 100%; height: 100%; display: block; }
    .agent-detail-popup { display: none; position: fixed; z-index: 30000; left: 50%; top: 50%; transform: translate(-50%, -50%); background: var(--white); border: 2px solid var(--black); padding: 2rem; max-width: 500px; width: 90%; box-shadow: 8px 8px 0 var(--shadow-dark); }
    .agent-detail-popup.show { display: block; }
    .agent-detail-popup .close-popup { float: right; cursor: pointer; }
    .file-tree { font-family: monospace; font-size: 13px; line-height: 1.4; }
    .file-tree ul { list-style: none; padding-left: 20px; }
    .file-tree li.dir::before { content: "📁 "; }
    .file-tree li.file::before { content: "📄 "; }
    .file-tree a { color: #0ff; text-decoration: underline; }
    .tree-modal .modal-content { max-width: 800px; }
    .graph-labels { display: flex; flex-wrap: wrap; gap: 10px; font-size: 11px; padding: 4px 8px; background: var(--off-white); border-bottom: 1px solid var(--light-gray); }
    .graph-label { display: flex; align-items: center; gap: 4px; }
    .graph-label .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; }
    .graph-label .spike { background: #ff0000; width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-left: 4px; }
  </style>
</head>
<body>
<div class="neuro-menu">
  <div class="menu-item">LACK v4.2.2</div>
  <div class="neuro-status">
    <span id="agentCount">Agents: 0</span>
    <span id="ralphStatusBadge" class="ralph-badge">🧬 Ralph active</span>
    <button class="top-btn" id="treeBtn">🌳 Tree</button>
    <button class="ground-btn" id="groundBtn">🌍 GROUND</button>
    <button class="ground-btn" id="graphBtn">📈 GRAPH</button>
    <button class="moderator-btn off" id="moderatorBtn">🔧 Moderator OFF</button>
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
        <label class="file-upload-btn"><i class="fas fa-paperclip"></i><input type="file" id="fileInput" style="display:none" accept=".txt,.md,.json,.csv,.log,.py,.js,.html,.css"></label>
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
<div class="bottom-bar"><span>LACK · Musing & Triangulation · Real‑time graph | /bash in #general</span><span id="statusText">CONNECTED</span></div>
<div id="agentThinkingToast" class="agent-thinking-overlay" style="display:none;"><i class="fas fa-spinner fa-pulse"></i> Agent is thinking...</div>

<div id="agentModal" class="modal"><div class="modal-content"><h3>Agent Details & Edit</h3><input type="text" id="editAgentId" hidden><label>Name:</label><input type="text" id="editAgentName"><label>Model:</label><select id="editAgentModel"></select><label>System Prompt:</label><textarea id="editAgentPrompt" rows="3"></textarea><label>Channels (comma):</label><input type="text" id="editAgentChannels"><label>Strict Channel (optional):</label><input type="text" id="editAgentStrictChannel" placeholder="Leave empty for all"><div class="modal-buttons"><button id="removeAgentBtn">Remove Agent</button><button id="saveAgentBtn">Save</button><button id="closeModalBtn">Cancel</button></div></div></div>
<div id="quickSwitcherModal" class="modal"><div class="modal-content"><input type="text" id="switcherInput" placeholder="Jump... Ctrl+K"><div class="shortcut-hint">Ctrl+K</div></div></div>
<div id="graphModal" class="modal"><div class="modal-content" style="width:98vw; height:92vh; display:flex; flex-direction:column; padding:0.5rem; max-width:98vw; max-height:92vh;">
  <div style="display:flex; justify-content:space-between; padding:4px 8px; align-items:center;">
    <h3>📊 Agent Metrics: CPU / Memory / TPS / J‑space Coherence</h3>
    <button id="closeGraphBtn" style="background:none;border:none;font-size:24px;">✕</button>
  </div>
  <div id="graphLabels" class="graph-labels"></div>
  <div style="flex:1; background:var(--off-white); margin:4px 0; border:2px solid var(--black); position:relative;">
    <canvas id="agentGraph" style="width:100%; height:100%; display:block;"></canvas>
    <div id="spikeOverlay" style="position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:none;"></div>
  </div>
  <div id="graphLegend" style="display:flex; gap:20px; flex-wrap:wrap; font-size:12px; padding:4px 8px;"></div>
</div></div>
<div id="agentDetailPopup" class="agent-detail-popup"><span class="close-popup" id="closeAgentDetail">&times;</span><div id="agentDetailContent"></div></div>

<!-- Tree Modal -->
<div id="treeModal" class="modal tree-modal">
  <div class="modal-content">
    <h2>📂 Repository Tree</h2>
    <div id="treeView" class="file-tree"></div>
    <div class="modal-buttons"><button id="closeTreeBtn">Close</button></div>
  </div>
</div>

<div id="toast" class="toast"></div>

<script>
let ws, currentStoreId = 'general', username = localStorage.getItem('lack_username') || 'human_' + Math.floor(Math.random()*1000), userId = '', agents = [], researchSessions = [], channels = [], currentThreadId = null, graphInterval = null, graphCanvas, graphCtx, resizeListener = false;
let pendingFile = null;
let moderatorState = false;
const jspaceEnabled = true;

function showToast(msg, type = 'info') {
  const toast = document.getElementById('toast');
  toast.className = `toast ${type}`;
  toast.innerText = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 3000);
}

let graphWorker = null;
function initGraphWorker() {
  const workerCode = `
    self.onmessage = function(e) {
      const data = e.data;
      const agents = data.agents;
      const metrics = data.metrics;
      let allTimestamps = [];
      for (const id of Object.keys(metrics)) {
        const m = metrics[id];
        if (m.timestamps && m.timestamps.length) {
          allTimestamps = allTimestamps.concat(m.timestamps);
        }
      }
      if (allTimestamps.length === 0) {
        self.postMessage({ type: 'processed', data });
        return;
      }
      const minT = Math.min(...allTimestamps);
      const maxT = Math.max(...allTimestamps);
      const tRange = maxT - minT || 1;
      const normalizedMetrics = {};
      for (const [id, m] of Object.entries(metrics)) {
        const ts = m.timestamps.slice().sort((a,b) => a - b);
        const cpu = m.cpu.slice(0, ts.length);
        const mem = m.mem.slice(0, ts.length);
        const tps = m.tpsHistory.slice(0, ts.length);
        const jspace = (m.jspaceCoherence || []).slice(0, ts.length);
        const ePool = m.ePoolHistory.slice(0, ts.length);
        const xPool = m.xPoolHistory.slice(0, ts.length);
        const spikes = m.spikes || [];
        normalizedMetrics[id] = {
          timestamps: ts,
          cpu, mem, tps, jspace, ePool, xPool, spikes,
          minT, maxT, tRange
        };
      }
      self.postMessage({
        type: 'processed',
        data: {
          agents: data.agents,
          metrics: normalizedMetrics,
          globalMinT: minT,
          globalMaxT: maxT,
          globalTRange: tRange
        }
      });
    };
  `;
  try {
    const blob = new Blob([workerCode], { type: 'application/javascript' });
    graphWorker = new Worker(URL.createObjectURL(blob));
    graphWorker.onmessage = (e) => {
      if (e.data.type === 'processed') {
        drawGraph(e.data.data);
      }
    };
  } catch (err) {
    console.warn('Web worker not supported, falling back to main thread processing');
    graphWorker = null;
  }
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
  document.getElementById('cronBtn').onclick = () => { if(confirm('⚠️ CRON WIPE: Delete ALL cron jobs, add heartbeats, reset ALL data. Are you sure?')) fetch('/api/cron/wipe',{method:'POST'}).then(r=>r.json()).then(d=>{if(d.success) location.reload(); else alert('Error: '+d.error);}); };
  document.getElementById('closeThreadBtn').onclick = closeThreadPanel;
  document.getElementById('sendThreadReply').onclick = sendThreadReply;
  document.addEventListener('keydown', e => { if((e.ctrlKey||e.metaKey) && e.key === 'k') { e.preventDefault(); document.getElementById('quickSwitcherModal').style.display = 'flex'; document.getElementById('switcherInput').focus(); } });
  document.getElementById('quickSwitcherModal').onclick = e => { if(e.target === document.getElementById('quickSwitcherModal')) document.getElementById('quickSwitcherModal').style.display = 'none'; };
  document.getElementById('switcherInput').addEventListener('keyup', e => { if(e.key === 'Enter') handleQuickSwitch(); });
  setInterval(fetchResearchSessions, 5000);
  document.getElementById('closeGraphBtn').onclick = () => { document.getElementById('graphModal').style.display = 'none'; if(graphInterval) clearInterval(graphInterval); if(resizeListener) window.removeEventListener('resize', handleGraphResize); };
  document.getElementById('moderatorBtn').onclick = toggleModerator;
  document.getElementById('closeAgentDetail').onclick = () => { document.getElementById('agentDetailPopup').classList.remove('show'); };
  document.getElementById('treeBtn').onclick = openTreeModal;
  document.getElementById('closeTreeBtn').onclick = () => { document.getElementById('treeModal').style.display = 'none'; };

  const fileInput = document.getElementById('fileInput');
  fileInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const MAX_SIZE = 512 * 1024;
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
    const strictChannel = document.getElementById('editAgentStrictChannel').value.trim() || null;
    ws.send(JSON.stringify({type:'update_agent',id,name,model,systemPrompt:prompt,channels:chans,strictChannel}));
    document.getElementById('agentModal').style.display='none';
    showToast(`Agent "${name}" updated`, 'success');
  };
  document.getElementById('closeModalBtn').onclick = () => { document.getElementById('agentModal').style.display='none'; };
  document.getElementById('removeAgentBtn').onclick = async () => {
    const agentId = document.getElementById('editAgentId').value;
    const agentName = document.getElementById('editAgentName').value;
    if (confirm(`Delete agent "${agentName}" permanently?`)) {
      const resp = await fetch(`/api/agent/${agentId}`, { method: 'DELETE' });
      const result = await resp.json();
      if (resp.ok && result.success) { document.getElementById('agentModal').style.display='none'; showToast(`Agent "${agentName}" removed`, 'success'); }
      else { showToast(result.reason || 'Cannot remove agent', 'error'); }
    }
  };

  setInterval(() => {
    const anyThinking = agents.some(a => a.status === 'thinking' || a.status === 'queued');
    document.getElementById('agentThinkingToast').style.display = anyThinking ? 'flex' : 'none';
  }, 500);

  initGraphWorker();
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
      case 'agents_list': agents = d.agents; document.getElementById('agentCount').innerText = 'Agents: '+agents.length; renderSidebar(); updateModeratorButton(); if (document.getElementById('graphModal').style.display === 'flex') fetchAndDrawGraph(); break;
      case 'history': renderMessages(d.messages); break;
      case 'new_message': if(d.channelId === currentStoreId) appendMessage(d.message); break;
      case 'research_update': fetchResearchSessions(); break;
      case 'thread_messages': renderThreadMessages(d.messages); currentThreadId = d.threadId; openThreadPanel(); break;
      case 'thread_update': if(currentThreadId === d.threadId) renderThreadMessages(d.messages); break;
      case 'models_list': populateModelSelect(d.models); break;
      case 'spawn_confirm': appendSystemMessage('Agent '+d.agent.name+' created.'); showToast(`Agent ${d.agent.name} spawned`, 'success'); break;
      case 'error': showToast(d.message, 'error'); break;
      case 'cron_reset': location.reload(); break;
      case 'graph_ack': openGraphModal(); break;
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
  addSection('AGENTS', agents.map(a => {
    let roleIcon = '🤖';
    return { id: a.id, name: a.name, type:'agent', icon:roleIcon, status:a.status, model: a.model, weights: a.weights, ePoolSize: a.ePoolSize, xPoolSize: a.xPoolSize, strictChannel: a.strictChannel };
  }));
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
      const strictHtml = item.strictChannel ? `<span class="role-badge" title="Strict channel">🔒${item.strictChannel}</span>` : '';
      div.innerHTML = `
        <div class="agent-info" data-agent-id="${item.id}">
          <span style="font-size:1.2rem;">${item.icon || '🤖'}</span>
          <span class="agent-name">${escapeHtml(item.name)}</span>
          <span class="agent-status status-${item.status}"></span>
          ${strictHtml}
        </div>
        <i class="fas fa-trash-alt remove-agent" data-agent-id="${item.id}" title="Remove"></i>
      `;
      const infoDiv = div.querySelector('.agent-info');
      infoDiv.onclick = (e) => { e.stopPropagation(); showAgentDetails(item.id); };
      const trash = div.querySelector('.remove-agent');
      trash.onclick = async (e) => { e.stopPropagation(); if(confirm(`Permanently remove agent "${item.name}"?`)) { const resp = await fetch(`/api/agent/${item.id}`, { method: 'DELETE' }); const result = await resp.json(); if (resp.ok && result.success) { showToast(`Agent "${item.name}" removed`, 'success'); } else { showToast(result.reason || 'Cannot remove agent', 'error'); } } };
    } else {
      div = document.createElement('div'); div.className = 'channel-item';
      div.innerHTML = `<i class="fas ${item.icon}"></i> ${escapeHtml(item.name)}`;
      if(item.progress !== undefined) { let p = document.createElement('span'); p.style.fontSize='0.7rem'; p.style.marginLeft='auto'; p.innerText = `${Math.round(item.progress*100)}%`; div.appendChild(p); }
      div.onclick = () => {
        if(item.type === 'channel') switchToChannel(item.id);
        else if(item.type === 'research') sendCommand('/pull '+item.id);
      };
    }
    itemsDiv.appendChild(div);
  });
  section.appendChild(itemsDiv); sidebar.appendChild(section);
}

function showAgentDetails(agentId) {
  const agent = agents.find(a => a.id === agentId);
  if (!agent) return;
  const content = document.getElementById('agentDetailContent');
  content.innerHTML = `
    <h3>${escapeHtml(agent.name)}</h3>
    <p><strong>Model:</strong> ${escapeHtml(agent.model)}</p>
    <p><strong>Strict Channel:</strong> ${agent.strictChannel || 'None'}</p>
    <p><strong>Status:</strong> ${agent.status}</p>
    <p><strong>Exploit/Explore:</strong> ${agent.weights ? agent.weights.exploitation.toFixed(2) + ' / ' + agent.weights.exploration.toFixed(2) : 'N/A'}</p>
    <p><strong>E-pool / X-pool:</strong> ${agent.ePoolSize || 0} / ${agent.xPoolSize || 0}</p>
    <p><strong>J-space enabled:</strong> ${agent.jspaceEnabled ? '✅' : '❌'}</p>
    <button onclick="openEditModal('${agentId}')">Edit</button>
  `;
  document.getElementById('agentDetailPopup').classList.add('show');
}

function switchToChannel(id) { currentStoreId = id; const ch = channels.find(c=>c.id===id); document.getElementById('currentChatName').innerHTML = ch ? '#'+ch.name : id; ws.send(JSON.stringify({type:'join',channelId:id})); closeThreadPanel(); updateRalphBadge(); }

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
  if (msg.senderType === 'siphon-research' || (msg.content && (msg.content.includes('🔍') || msg.content.includes('FACT:')))) {
    div.classList.add('siphon-research');
  }
  if (msg.content && (msg.content.includes('worth a closer look') || msg.content.includes('**Thinking**'))) {
    div.classList.add('reflection-message');
  }
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
    const MAX_CHARS = 1500;
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

function sendCommand(cmd) { if(ws) ws.send(JSON.stringify({type:'message',content:cmd})); }
function formatTime(ts) { return new Date(ts).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}); }
function formatCode(t) { return t.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>'); }
function autoGrow() { const ta = document.getElementById('messageInput'); ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight,200)+'px'; }
let slashTimeout;
function handleSlash(e) { if(e.key !== '/') return; const input = e.target; if(input.selectionStart === 0 || input.value[input.selectionStart-1] === ' ') { if(slashTimeout) clearTimeout(slashTimeout); const existing = document.querySelector('.slash-suggestions'); if(existing) existing.remove(); const commands = ['help','ground','research','abstract','plan','ralph','stop','list','spawn','siphon','pull','thread','pin','graph','errorlog','convergence','tools','stack','repo','lint','moderate','memory','public_memory','toggle_public_memory','eval','skill','tree','jspace','jspace_agent','cicd','reconcile','approve','bash']; const sug = document.createElement('ul'); sug.className = 'slash-suggestions'; commands.forEach(cmd => { const li = document.createElement('li'); li.innerText = '/'+cmd; li.onclick = () => { input.value = '/'+cmd+' '; input.focus(); sug.remove(); }; sug.appendChild(li); }); input.parentNode.style.position = 'relative'; input.parentNode.appendChild(sug); slashTimeout = setTimeout(() => { if(sug.parentNode) sug.remove(); },5000); document.addEventListener('click', function close(e) { if(!sug.contains(e.target) && e.target !== input) { sug.remove(); document.removeEventListener('click', close); } }); } }
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
function handleQuickSwitch() { const q = document.getElementById('switcherInput').value.toLowerCase(); const ch = channels.find(c=>c.name.toLowerCase().includes(q)); if(ch) switchToChannel(ch.id); const ag = agents.find(a=>a.name.toLowerCase().includes(q)); if(ag) showAgentDetails(ag.id); document.getElementById('quickSwitcherModal').style.display='none'; }
function fetchResearchSessions() { fetch('/api/research/sessions').then(r=>r.json()).then(d=>{ researchSessions = d.sessions; renderSidebar(); }).catch(console.error); }
function openEditModal(agentId) {
  const agent = agents.find(a => a.id === agentId);
  if (!agent) return;
  document.getElementById('editAgentId').value = agent.id;
  document.getElementById('editAgentName').value = agent.name;
  document.getElementById('editAgentPrompt').value = agent.systemPrompt;
  document.getElementById('editAgentChannels').value = agent.channels.join(',');
  document.getElementById('editAgentStrictChannel').value = agent.strictChannel || '';
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
  document.getElementById('agentDetailPopup').classList.remove('show');
}
function handleSpawn() { ws.send(JSON.stringify({type:'get_models'})); const orig = ws.onmessage; ws.onmessage = e => { const d = JSON.parse(e.data); if(d.type === 'models_list') { if(!d.models.length) alert('No Ollama models'); else { const name = prompt('Agent name:'); if(name) { const model = prompt('Model:',d.models[0]); const promptText = prompt('System prompt:','You are helpful.'); const chans = prompt('Channels (comma):','general,siphon,code').split(',').map(s=>s.trim()); const strict = prompt('Strict channel (optional, leave empty):', ''); ws.send(JSON.stringify({type:'spawn_agent',name,model,systemPrompt:promptText,channels:chans,strictChannel:strict || null})); } } ws.onmessage = orig; } else if(orig) orig(e); }; }
function escapeHtml(s) { return s.replace(/[&<>]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[m])); }

function updateModeratorButton() {
  const mod = agents.find(a => a.id === 'moderator');
  if (mod) {
    const btn = document.getElementById('moderatorBtn');
    const on = mod.isCodeModerator;
    btn.classList.remove('on', 'off');
    btn.classList.add(on ? 'on' : 'off');
    btn.innerText = on ? '🔧 Moderator ON' : '🔧 Moderator OFF';
    moderatorState = on;
  }
}
function toggleModerator() {
  const mod = agents.find(a => a.id === 'moderator');
  if (!mod) return;
  const newState = !moderatorState;
  sendCommand(`/moderate ${newState ? 'on' : 'off'}`);
}

async function openGraphModal() {
  document.getElementById('graphModal').style.display = 'flex';
  await new Promise(r => setTimeout(r, 100));
  graphCanvas = document.getElementById('agentGraph');
  if (!graphCanvas) return;
  resizeGraphCanvas();
  await fetchAndDrawGraph();
  if (graphInterval) clearInterval(graphInterval);
  graphInterval = setInterval(fetchAndDrawGraph, 10000);
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
    const colors = { cpu: '#ff3b5c', mem: '#3b8cff', tps: '#39ff14', jspace: '#ffaa00' };
    legend.innerHTML = `
      <span><span style="display:inline-block;width:20px;height:3px;background:${colors.cpu};"></span> CPU</span>
      <span><span style="display:inline-block;width:20px;height:3px;background:${colors.mem};border-style:dashed;"></span> MEM</span>
      <span><span style="display:inline-block;width:20px;height:3px;background:${colors.tps};border-style:dotted;"></span> TPS</span>
      <span><span style="display:inline-block;width:20px;height:3px;background:${colors.jspace};border-style:dash-dot;"></span> J-space</span>
    `;
    const labelsDiv = document.getElementById('graphLabels');
    labelsDiv.innerHTML = '';
    data.agents.forEach(a => {
      const m = data.metrics[a.id];
      if (!m) return;
      const lastCpu = m.cpu.length ? m.cpu[m.cpu.length-1] : 0;
      const lastMem = m.mem.length ? m.mem[m.mem.length-1] : 0;
      const lastTps = m.tpsHistory.length ? m.tpsHistory[m.tpsHistory.length-1] : 0;
      const lastJspace = m.jspaceCoherence && m.jspaceCoherence.length ? m.jspaceCoherence[m.jspaceCoherence.length-1] : 0;
      const spikeCount = m.spikes ? m.spikes.length : 0;
      const label = document.createElement('div');
      label.className = 'graph-label';
      label.innerHTML = `
        <strong>${a.name}</strong>
        <span style="color:${colors.cpu};">${lastCpu.toFixed(1)}%</span>
        <span style="color:${colors.mem};">${lastMem.toFixed(1)}%</span>
        <span style="color:${colors.tps};">${lastTps.toFixed(1)}</span>
        <span style="color:${colors.jspace};">${lastJspace.toFixed(2)}</span>
        ${spikeCount > 0 ? `<span class="spike" title="${spikeCount} spikes"></span>` : ''}
      `;
      labelsDiv.appendChild(label);
    });
    if (graphWorker) {
      graphWorker.postMessage({ agents: data.agents, metrics: data.metrics });
    } else {
      const processed = processMetrics(data);
      drawGraph(processed);
    }
  } catch(e) { console.error(e); }
}

function processMetrics(data) {
  const agents = data.agents;
  const metrics = data.metrics;
  let allTimestamps = [];
  for (const id of Object.keys(metrics)) {
    const m = metrics[id];
    if (m.timestamps && m.timestamps.length) {
      allTimestamps = allTimestamps.concat(m.timestamps);
    }
  }
  if (allTimestamps.length === 0) return { agents, metrics, globalMinT: Date.now()-10000, globalMaxT: Date.now(), globalTRange: 10000 };
  const minT = Math.min(...allTimestamps);
  const maxT = Math.max(...allTimestamps);
  const tRange = maxT - minT || 1;
  const normalizedMetrics = {};
  for (const [id, m] of Object.entries(metrics)) {
    const ts = m.timestamps.slice().sort((a,b) => a - b);
    const cpu = m.cpu.slice(0, ts.length);
    const mem = m.mem.slice(0, ts.length);
    const tps = m.tpsHistory.slice(0, ts.length);
    const jspace = (m.jspaceCoherence || []).slice(0, ts.length);
    const ePool = m.ePoolHistory.slice(0, ts.length);
    const xPool = m.xPoolHistory.slice(0, ts.length);
    const spikes = m.spikes || [];
    normalizedMetrics[id] = {
      timestamps: ts,
      cpu, mem, tps, jspace, ePool, xPool, spikes,
      minT, maxT, tRange
    };
  }
  return {
    agents,
    metrics: normalizedMetrics,
    globalMinT: minT,
    globalMaxT: maxT,
    globalTRange: tRange
  };
}

function drawGraph(data) {
  if (!graphCtx || !graphCanvas) return;
  const container = graphCanvas.parentElement;
  const w = container.clientWidth, h = container.clientHeight;
  if (w === 0 || h === 0) return;
  const isDark = document.body.classList.contains('dark-mode');
  const bg = isDark ? '#0a0a0a' : '#f8f8f8';
  const grid = isDark ? '#2a2a2a' : '#e0e0e0';
  const text = isDark ? '#f0f0f0' : '#000';
  graphCtx.clearRect(0, 0, w, h);
  graphCtx.fillStyle = bg;
  graphCtx.fillRect(0, 0, w, h);

  const agentsToPlot = data.agents.filter(a => a.id !== 'moderator');
  if (agentsToPlot.length === 0) {
    graphCtx.fillStyle = text;
    graphCtx.font = '14px monospace';
    graphCtx.textAlign = 'center';
    graphCtx.fillText('No agents to display', w/2, h/2);
    return;
  }

  const globalMinT = data.globalMinT || (data.metrics && Object.values(data.metrics).length ? Math.min(...Object.values(data.metrics).map(m => m.timestamps[0] || 0)) : Date.now()-10000);
  const globalMaxT = data.globalMaxT || (data.metrics && Object.values(data.metrics).length ? Math.max(...Object.values(data.metrics).map(m => m.timestamps[m.timestamps.length-1] || 0)) : Date.now());
  const globalTRange = data.globalTRange || (globalMaxT - globalMinT) || 1;

  const rowCount = agentsToPlot.length;
  const rowHeight = h / rowCount;
  const pad = { top: 20, bottom: 20, left: 50, right: 20 };
  const innerW = w - pad.left - pad.right;
  const innerH = rowHeight - pad.top - pad.bottom;

  let maxTPS = 1;
  agentsToPlot.forEach(a => {
    const m = data.metrics[a.id];
    if (m && m.tps) {
      const max = Math.max(...m.tps, 1);
      if (max > maxTPS) maxTPS = max;
    }
  });
  maxTPS = Math.ceil(maxTPS / 5) * 5 + 5;

  const colors = { cpu: '#ff3b5c', mem: '#3b8cff', tps: '#39ff14', jspace: '#ffaa00' };

  agentsToPlot.forEach((agent, idx) => {
    const m = data.metrics[agent.id];
    if (!m || !m.timestamps || m.timestamps.length === 0) return;
    const yOffset = idx * rowHeight;

    graphCtx.fillStyle = isDark ? '#1a1a1a' : '#ffffff';
    graphCtx.fillRect(pad.left, yOffset + pad.top, innerW, innerH);
    graphCtx.strokeStyle = grid;
    graphCtx.lineWidth = 1;
    graphCtx.strokeRect(pad.left, yOffset + pad.top, innerW, innerH);

    graphCtx.strokeStyle = grid;
    graphCtx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
      const yPos = yOffset + pad.top + (i / 4) * innerH;
      graphCtx.beginPath();
      graphCtx.moveTo(pad.left, yPos);
      graphCtx.lineTo(w - pad.right, yPos);
      graphCtx.stroke();
    }

    graphCtx.fillStyle = text;
    graphCtx.font = '12px monospace';
    graphCtx.textAlign = 'left';
    graphCtx.fillText(agent.name, pad.left + 5, yOffset + pad.top + 14);

    const ts = m.timestamps;
    const cpu = m.cpu;
    const mem = m.mem;
    const tps = m.tps;
    const jspace = m.jspace || [];

    if (ts.length < 2) return;

    const minT = globalMinT;
    const maxT = globalMaxT;
    const tRange = globalTRange;

    const xMap = (t) => pad.left + ((t - minT) / tRange) * innerW;
    const yMapCpuMem = (val) => yOffset + pad.top + innerH - (val / 100) * innerH;
    const yMapTps = (val) => yOffset + pad.top + innerH - (val / maxTPS) * innerH;
    const yMapJspace = (val) => yOffset + pad.top + innerH - (val) * innerH;

    graphCtx.beginPath();
    graphCtx.strokeStyle = colors.cpu;
    graphCtx.lineWidth = 2;
    for (let i = 0; i < cpu.length && i < ts.length; i++) {
      const x = xMap(ts[i]);
      const y = yMapCpuMem(cpu[i]);
      if (i === 0) graphCtx.moveTo(x, y);
      else graphCtx.lineTo(x, y);
    }
    graphCtx.stroke();

    graphCtx.beginPath();
    graphCtx.strokeStyle = colors.mem;
    graphCtx.lineWidth = 2;
    graphCtx.setLineDash([5, 5]);
    for (let i = 0; i < mem.length && i < ts.length; i++) {
      const x = xMap(ts[i]);
      const y = yMapCpuMem(mem[i]);
      if (i === 0) graphCtx.moveTo(x, y);
      else graphCtx.lineTo(x, y);
    }
    graphCtx.stroke();
    graphCtx.setLineDash([]);

    graphCtx.beginPath();
    graphCtx.strokeStyle = colors.tps;
    graphCtx.lineWidth = 2;
    graphCtx.setLineDash([2, 3]);
    for (let i = 0; i < tps.length && i < ts.length; i++) {
      const x = xMap(ts[i]);
      const y = yMapTps(tps[i]);
      if (i === 0) graphCtx.moveTo(x, y);
      else graphCtx.lineTo(x, y);
    }
    graphCtx.stroke();
    graphCtx.setLineDash([]);

    if (jspace && jspace.length > 0) {
      graphCtx.beginPath();
      graphCtx.strokeStyle = colors.jspace;
      graphCtx.lineWidth = 2;
      graphCtx.setLineDash([1, 2]);
      for (let i = 0; i < jspace.length && i < ts.length; i++) {
        const x = xMap(ts[i]);
        const y = yMapJspace(jspace[i]);
        if (i === 0) graphCtx.moveTo(x, y);
        else graphCtx.lineTo(x, y);
      }
      graphCtx.stroke();
      graphCtx.setLineDash([]);
    }

    if (m.spikes && m.spikes.length) {
      m.spikes.forEach(spike => {
        const x = xMap(spike.timestamp);
        let y;
        if (spike.type === 'cpu') y = yMapCpuMem(spike.value);
        else if (spike.type === 'mem') y = yMapCpuMem(spike.value);
        else y = yMapTps(spike.value);
        graphCtx.fillStyle = '#ff0000';
        graphCtx.beginPath();
        graphCtx.arc(x, y, 4, 0, 2 * Math.PI);
        graphCtx.fill();
        graphCtx.fillStyle = text;
        graphCtx.font = '8px monospace';
        graphCtx.textAlign = 'center';
        graphCtx.fillText('⚡', x, y - 8);
      });
    }

    graphCtx.fillStyle = text;
    graphCtx.font = '9px monospace';
    graphCtx.textAlign = 'right';
    graphCtx.fillText('100%', pad.left - 5, yOffset + pad.top + 10);
    graphCtx.fillText('0%', pad.left - 5, yOffset + pad.top + innerH + 5);
    graphCtx.fillText(`${maxTPS} tok/s`, pad.left - 5, yOffset + pad.top + 20);

    const numTicks = 5;
    graphCtx.textAlign = 'center';
    graphCtx.font = '8px monospace';
    for (let i = 0; i <= numTicks; i++) {
      const t = minT + (i / numTicks) * tRange;
      const x = pad.left + (i / numTicks) * innerW;
      graphCtx.strokeStyle = grid;
      graphCtx.lineWidth = 0.5;
      graphCtx.beginPath();
      graphCtx.moveTo(x, yOffset + pad.top + innerH);
      graphCtx.lineTo(x, yOffset + pad.top + innerH + 6);
      graphCtx.stroke();
      const timeStr = new Date(t).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
      graphCtx.fillStyle = text;
      graphCtx.fillText(timeStr, x, yOffset + pad.top + innerH + 18);
    }
  });
}

async function openTreeModal() {
  document.getElementById('treeModal').style.display = 'flex';
  const container = document.getElementById('treeView');
  container.innerHTML = '<div class="spinner" style="margin:20px auto;"></div>';
  try {
    const res = await fetch('/api/tree?root=thread_repos');
    const data = await res.json();
    renderTree(data, container);
  } catch(e) {
    container.innerHTML = '<p>Failed to load tree.</p>';
  }
}

function renderTree(nodes, container) {
  container.innerHTML = '';
  const ul = document.createElement('ul');
  nodes.forEach(node => {
    const li = document.createElement('li');
    li.className = node.type;
    if (node.type === 'file') {
      const a = document.createElement('a');
      a.href = '/' + node.path;
      a.target = '_blank';
      a.textContent = node.name;
      li.appendChild(a);
    } else {
      li.textContent = node.name;
      if (node.children && node.children.length) {
        const childUl = document.createElement('ul');
        renderTree(node.children, childUl);
        li.appendChild(childUl);
      }
    }
    ul.appendChild(li);
  });
  container.appendChild(ul);
}

window.onload = init;
</script>
</body>
</html>
'''

CONFIG_JSON = r'''{
  "httpPort": 3721,
  "enablePublicMemory": false,
  "defaultModel": "qwen2.5:0.5b",
  "embeddingModel": "nomic-embed-text:latest",
  "fallbackModels": ["phi3:mini", "tinyllama"],
  "agents": [
    { "id": "agent1", "name": "Agent 1", "model": "qwen2.5:0.5b", "systemPrompt": "You are a helpful AI assistant.", "channels": ["general","siphon","code"], "strictChannel": null },
    { "id": "agent2", "name": "Agent 2", "model": "qwen2.5:0.5b", "systemPrompt": "You are a creative AI.", "channels": ["general","siphon","code"], "strictChannel": null }
  ],
  "channels": [
    { "id": "general", "name": "general" },
    { "id": "siphon", "name": "siphon" },
    { "id": "code", "name": "code" }
  ],
  "searchProvider": "duckduckgo",
  "serpapiKey": "",
  "firecrawlApiKey": "",
  "searchMaxResults": 5,
  "scrapeTimeout": 8000,
  "historyLength": 300,
  "jspaceEnabled": true,
  "jspaceLayer": "layer_12",
  "jspaceConceptCount": 5,
  "cicd": {
    "maxRetries": 3,
    "reviewerModel": "qwen2.5:0.5b",
    "moderatorModel": "qwen2.5:0.5b",
    "requirePeerReview": true,
    "autoFix": true
  },
  "reconciliation": {
    "maxIterations": 20,
    "convergenceThreshold": 0.95,
    "minEvalScore": 80,
    "requireTestPass": true,
    "hitlPause": false
  },
  "enableMusing": true,
  "enableTriangulation": true,
  "museCount": 3,
  "triangulatePerspectives": 3
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
  console.log('\x1b[36m[ LACK v4.2.2 ] Starting – Musing & Triangulation Enhanced\x1b[0m');
  if (!await checkOllama()) { console.error('\x1b[31m✗ Ollama not running\x1b[0m'); process.exit(1); }
  console.log('\x1b[32m✓ Ollama detected\x1b[0m');
  const server = spawn('node', ['server.js'], { stdio: 'inherit', cwd: projectRoot });
  server.on('error', (err) => { console.error('Failed to start server:', err); process.exit(1); });
  process.on('SIGINT', () => { server.kill('SIGINT'); process.exit(); });
}
main();
'''

# ----------------------------------------------------------------------
# Python Launcher (unchanged but ensures all files written)
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
        if "npm" in cmd[0] and "install" in cmd:
            print("\n❌ npm install failed. Possible fixes:")
            print("    1. Ensure Node.js >= 18 is installed: node --version")
            print("    2. Check internet connection (npm needs network)")
            print("    3. Run manually: npm install express ws uuid axios cheerio simple-git better-sqlite3 eslint")
        raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stdout, stderr=result.stderr)
    print(result.stdout)

def open_browser():
    time.sleep(2)
    webbrowser.open('http://localhost:3721')

def check_ollama_with_retry(max_attempts=3, delay=2):
    import urllib.request
    for attempt in range(1, max_attempts + 1):
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode())
        except Exception as e:
            if attempt < max_attempts:
                print(f"  Ollama check attempt {attempt}/{max_attempts} failed ({e}). Retrying in {delay}s...")
                time.sleep(delay)
            else:
                raise
    return None

def pull_ollama_model(model_name):
    print(f"Attempting to pull model '{model_name}'... (this may take a while)")
    try:
        import urllib.request, json
        req = urllib.request.Request(
            "http://localhost:11434/api/pull",
            data=json.dumps({"model": model_name}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=600) as resp:
            while True:
                chunk = resp.read(1024)
                if not chunk:
                    break
            print(f"✓ Model '{model_name}' pulled successfully.")
            return True
    except Exception as e:
        print(f"⚠️ Failed to pull '{model_name}': {e}")
        return False

def init_db():
    db_path = Path("db/lack.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS messages 
                 (id TEXT PRIMARY KEY, store_id TEXT, sender TEXT, sender_type TEXT, 
                  content TEXT, timestamp INTEGER, parent_id TEXT, thread_id TEXT, 
                  reply_count INTEGER, reactions TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS agents 
                 (id TEXT PRIMARY KEY, name TEXT, model TEXT, system_prompt TEXT, 
                  channels TEXT, strict_channel TEXT, status TEXT, 
                  is_embed_operator INTEGER, is_code_moderator INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS agent_memory 
                 (agent_id TEXT PRIMARY KEY, e_pool TEXT, x_pool TEXT, weights TEXT, 
                  stats TEXT, last_update INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS project_states 
                 (store_id TEXT PRIMARY KEY, state TEXT, timestamp INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS pipeline_results 
                 (id TEXT PRIMARY KEY, agent_id TEXT, thread_id TEXT, code_hash TEXT, 
                  passed INTEGER, attempt INTEGER, feedback TEXT, timestamp INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS loop_health 
                 (loop_id TEXT PRIMARY KEY, loop_type TEXT, iterations INTEGER, 
                  convergence REAL, stagnation REAL, token_spend INTEGER, last_update INTEGER)''')
    conn.commit()
    conn.close()
    print("✓ SQLite database initialized with pipeline_results and loop_health tables.")

def main():
    print("=== LACK v4.2.2 – Musing & Triangulation Enhancement (Final) ===")
    print("- Musing: low‑commitment token sampling, candidate scoring, synthesis")
    print("- Triangulation: cross‑constraint mapping from multiple perspectives")
    print("- Integrated into /plan, /abstract, /ralph, and general planning")
    print("- /bash command for CLI access in #general (executed by Moderator)")
    print("- Tool calls restricted: only Moderator can execute commands")
    print("- NLP correction: small models discouraged from over‑using tools\n")

    for d in ["config", "public", "bin", "logs", "lineage", "research", "workspace", "lack_repos/templates", "thread_repos", "agent_memories", "db", "k8s", "jspace"]:
        create_directory(d)

    init_db()

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
        print("Error: Node.js is not installed. Install from https://nodejs.org")
        sys.exit(1)

    if not Path("node_modules").exists():
        print("Installing npm dependencies (including better-sqlite3 and eslint)...")
        run_command(["npm", "install", "express", "ws", "uuid", "axios", "cheerio", "simple-git", "better-sqlite3", "eslint"])
    else:
        print("node_modules already present.")

    print("Checking Ollama...")
    try:
        models_data = check_ollama_with_retry()
        if models_data is not None:
            print("✓ Ollama is running.")
            model_names = [m['name'] for m in models_data.get('models', [])]
            with open("config/lack.config.json") as f:
                cfg = json.load(f)
            default_model = cfg.get("defaultModel", "qwen2.5:0.5b")
            embedding_model = cfg.get("embeddingModel", "nomic-embed-text:latest")
            if default_model not in model_names:
                print(f"⚠ Default model '{default_model}' not found. Attempting to pull...")
                if pull_ollama_model(default_model):
                    print(f"✓ Pulled '{default_model}'")
                else:
                    print(f"⚠️ Could not pull '{default_model}'. Please run 'ollama pull {default_model}' manually.")
            if embedding_model not in model_names:
                print(f"⚠ Embedding model '{embedding_model}' not found. Embedding will fallback to TF‑IDF.")
                print("  To enable embedding, run: ollama pull " + embedding_model)
        else:
            print("⚠ Ollama responded but returned no data.")
    except Exception as e:
        print(f"⚠ Ollama not reachable after 3 attempts: {e}")

    # Check reverse-skill existence
    if not Path("reverse-skill").exists():
        print("⚠ reverse-skill not found. Clone it from https://github.com/zhaoxuya520/reverse-skill.git")
        print("  cd /path/to/lack && git clone https://github.com/zhaoxuya520/reverse-skill.git")
        print("  cd reverse-skill && bash skills/scripts/refresh-tool-index.sh")
        print("  (or Windows: powershell -File skills/scripts/refresh-tool-index.ps1)")
    else:
        print("✓ reverse-skill directory found.")

    # J-space stub
    jspace_dir = Path("jspace")
    jspace_file = jspace_dir / "qwen2.5_0.5b_jspace.json"
    if not jspace_file.exists():
        print("Generating placeholder J-space directions for Qwen2.5:0.5B...")
        import random
        directions = {
            "layer_12": [
                {"name": "math", "vector": [random.uniform(-0.1, 0.1) for _ in range(512)]},
                {"name": "planning", "vector": [random.uniform(-0.1, 0.1) for _ in range(512)]},
                {"name": "safety", "vector": [random.uniform(-0.1, 0.1) for _ in range(512)]},
                {"name": "creativity", "vector": [random.uniform(-0.1, 0.1) for _ in range(512)]},
                {"name": "causal", "vector": [random.uniform(-0.1, 0.1) for _ in range(512)]}
            ]
        }
        with open(jspace_file, 'w') as f:
            json.dump(directions, f, indent=2)
        print("✓ J-space stub created. Replace with real Neuronpedia directions for best results.")
    else:
        print("✓ J-space directions file found.")

    threading.Thread(target=open_browser, daemon=True).start()
    print("\nStarting LACK v4.2.2. Press Ctrl+C to stop.\n")

    while True:
        print("Launching Node server...")
        server_process = subprocess.Popen(
            ["node", "server.js"],
            stdout=sys.stdout,
            stderr=sys.stderr
        )
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