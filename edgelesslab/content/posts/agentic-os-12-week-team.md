---
title: "$12/Week AI Operations Team: How I Replaced a $50K Agency with 5 Agents"
date: 2026-04-19T14:00:00-07:00
description: "Cost breakdown of running a multi-agent AI operations team: Hermes (CoS), Dispatch (COO), Mastra (Router), and specialist workers. Architecture diagrams, real Telegram outputs, and the economics of model routing."
author: "Edgeless Lab"
tags: ["agents", "orchestration", "multi-agent", "cost-analysis", "paperclip"]
image: /og/agentic-os-12-week-team.webp
---

*This is Post 1 in the [Agentic OS series](/tags/agentic-os/) — documenting how we built a self-managing AI operations team that runs 24/7 for less than a coffee budget.*

---

## The $50K Question

I was quoted $50,000 for a six-month retainer with a mid-market AI consultancy. They'd build "autonomous agents" for my creative systems business.

I spent $12/week instead.

Not $12/day. **$12/week**. Less than a Netflix subscription. Less than two burritos in San Francisco.

Here's the architecture that's been running 24/7 since January 2026.

---

## The Team

Five agents. Each with a role, a model tier, and a Slack/Telegram presence.

| Agent | Role | Model | Weekly Cost | Hours |
|-------|------|-------|-------------|-------|
| **Hermes** | Chief of Staff / Dispatcher | Kimi K2.5 | ~$1.50 | 168 |
| **Dispatch** | COO / Backlog Manager | DeepSeek V3.2 | ~$0.80 | 168 |
| **Builder** | Feature Implementation | Claude Code | ~$3.00 | ~20 |
| **Verifier** | QA / Testing | DeepSeek V3.2 | ~$0.80 | ~10 |
| **Pamela** | Trading / Market Ops | GPT-4.1 nano | ~$6.00 | 168 |

**Total: ~$12.10/week**

---

## Architecture: The Paperclip OS

The name started as a joke (Clippy, but competent). Now it's the internal codename for our agent orchestration layer.

### Topology

```
┌─────────────────────────────────────────────────────────────┐
│                    PAPERCLIP OS                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐        │
│  │  Hermes  │◄────►│ Dispatch │◄────►│  Mastra  │        │
│  │   CoS    │      │   COO    │      │  Router  │        │
│  └────┬─────┘      └────┬─────┘      └────┬─────┘        │
│       │                 │                 │               │
│       ▼                 ▼                 ▼               │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐        │
│  │ Builder  │      │ Verifier │      │  Pamela  │        │
│  │  Dev     │      │   QA     │      │ Trading  │        │
│  └──────────┘      └──────────┘      └──────────┘        │
│                                                             │
│  Communication: File-based inboxes + rsync                 │
│  State: SQLite + markdown task files                        │
│  Recovery: 5-min checkpoint restore                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### The Dispatch/Worker Pattern

Instead of gRPC or message queues, we use **file-based inboxes** on a shared VPS:

```
/var/agents/
├── hermes/inbox/           # Strategic directives
├── dispatch/inbox/         # Task routing
├── builder/inbox/          # Implementation tasks
├── verifier/inbox/         # QA jobs
└── pamela/inbox/           # Trading signals
```

Each agent:
1. **Polls** its inbox every 30 seconds
2. **Claims** tasks with a JSON lease file
3. **Processes** and writes outputs to `/outbox/`
4. **Notifies** via Telegram on completion

**Why files?**
- Zero network dependencies
- Human-readable for debugging
- `rsync` handles distribution
- SQLite for structured state

---

## Model Routing: The Economics

The biggest cost optimization isn't cutting corners—it's **using the right brain for the job**.

### The Tiers

| Tier | Models | Use Case | Cost/Mtok |
|------|--------|----------|-----------|
| **Fast** | Kimi K2.5, DeepSeek V3.2 | Routing, triage, summaries | $0.10-0.20 |
| **Smart** | Claude Sonnet 4, GPT-4.1 | Analysis, writing, decisions | $1.50-3.00 |
| **Deep** | Claude Opus 4, GPT-5.4 | Complex coding, research | $10.00-15.00 |

### Routing Logic

```python
# Simplified from dispatch/router.py
if task_type == "triage":
    return "kimi-k2.5"        # Fast, cheap
elif task_type == "code_review":
    return "claude-opus-4"    # Expensive, worth it
elif task_type == "summarize":
    return "deepseek-v3.2"    # Fast, good enough
```

**Result**: 10x cost reduction vs. using GPT-4 for everything.

---

## Real Output: A Week in the Life

Here's what the team shipped last week (April 13-19, 2026):

### Monday
- **Hermes**: Triaged 47 RSS items, created 3 backlog tickets
- **Builder**: Migrated agent fleet from Codex to Kimi K2.5
- **Pamela**: 6 trades, +$240 P&L

### Wednesday  
- **Dispatch**: Detected agent backlog imbalance, auto-assigned 8 issues
- **Verifier**: Caught edge case in Telegram bot auth, filed fix
- **Builder**: Deployed auto-escalation cron to production

### Friday
- **Hermes**: Synthesized weekly knowledge harvest, posted to Discord
- **Pamela**: Risk limit triggered, auto-paused for weekend
- **All**: Heartbeat checks green, zero human intervention

---

## Why This Isn't Hype

I've built agent systems for two years. Here's what actually works:

### ✓ What Works
- **Clear roles**: Each agent has a job description
- **File-based comms**: Simple, inspectable, survives network blips
- **Model routing**: Match capability to cost
- **Health checks**: Every agent reports every 5 minutes
- **Recovery**: Checkpoint/restore, not "hope it works"

### ✗ What Doesn't
- "Agent swarms" with no orchestration
- Assuming LLMs won't hallucinate tools
- gRPC for everything (premature optimization)
- No session recovery (one crash = lost context)
- Using GPT-4 for routing (waste of money)

---

## The Products

We've packaged this infrastructure into three Gumroad products:

| Product | What | Price |
|---------|------|-------|
| **[Multi-Agent Orchestration Blueprint](https://edgelessai.gumroad.com/l/multi-agent-blueprint)** | Complete dispatch/worker architecture, 3 reference implementations, 9-chapter guide | $39 |
| **KB Loop Kit** | Knowledge base synthesizer, health checks, embeddings pipeline | $29 |
| **Hermes Deployment Guide** | VPS setup, model routing, cron templates, all the gotchas | $19 |

Or build it yourself—the patterns are documented in this series.

---

## Next in the Series

- **Post 2**: Multi-Model Routing: 4 Different Brains (not 1)
- **Post 3**: The Knowledge Base Loop (Karpathy Pattern)
- **Post 4**: File-Based Agent Communication
- **Post 5**: Session Poisoning: When AI Hallucinates Tools

---

## Want to Build This?

The complete blueprint—including dispatch/worker code, message bus hub (SQLite + Bun), pipeline orchestrator, and operational patterns—is in the **Multi-Agent Orchestration Blueprint**.

[**Get the blueprint →**](https://edgelessai.gumroad.com/l/multi-agent-blueprint)

Questions? Find me in the [Discord](https://discord.gg/edgelesslab) or [on X](https://x.com/davidmurray).

---

*Running on: Hetzner VPS ($6/mo), Fireworks AI, ChromaDB, Telegram.*  
*Monitoring: Paperclip orchestration layer + autonomous health checks.*
