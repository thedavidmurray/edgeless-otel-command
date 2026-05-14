---
title: "Multi-Model Routing: 4 Different Brains (Not 1)"
date: 2026-04-20T10:00:00-07:00
description: "How we cut AI costs by 10x with model routing: Kimi K2.5 for routing, DeepSeek for analysis, Codex for coding, Opus for deep reasoning. The economics of matching capability to cost."
author: "Edgeless Lab"
tags: ["agents", "orchestration", "model-routing", "cost-optimization", "paperclip"]
image: /og/agentic-os-multi-model-routing.webp
---

*This is Post 2 in the [Agentic OS series](/tags/agentic-os/) — the economics of using different LLMs for different jobs.*

---

## The $12/Week Math Doesn't Work Without This

In [Post 1](/posts/agentic-os-12-week-team/), I claimed a $12/week AI operations team. The numbers:

| Agent | Model | Weekly Cost |
|-------|-------|-------------|
| Hermes | Kimi K2.5 | ~$1.50 |
| Dispatch | DeepSeek V3.2 | ~$0.80 |
| Builder | Claude Code | ~$3.00 |
| Verifier | DeepSeek V3.2 | ~$0.80 |
| Pamela | GPT-4.1 nano | ~$6.00 |

**Total: ~$12.10**

If every agent used GPT-4.5? **~$120/week**. 10x more expensive. Same output quality.

The trick isn't cutting quality—it's **using the right brain for the job**.

---

## The 4 Brains

We run four model tiers, mapped to cognitive loads:

```
┌─────────────────────────────────────────────────────────────────┐
│                    MODEL ROUTING PYRAMID                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────┐  Deep reasoning, complex architecture              │
│   │  Deep   │  Claude Opus 4, GPT-5.4                           │
│   │  $$$$   │  ~$10-15/Mtok   [Use: 5% of tasks]                │
│   └────┬────┘                                                   │
│        │                                                        │
│   ┌────▼────┐  Code, analysis, creative synthesis              │
│   │  Smart  │  Claude Sonnet 4, GPT-4.1                         │
│   │   $$$   │  ~$1.50-3/Mtok   [Use: 25% of tasks]              │
│   └────┬────┘                                                   │
│        │                                                        │
│   ┌────▼────┐  Routing, triage, summarization                    │
│   │  Fast   │  Kimi K2.5, DeepSeek V3.2                        │
│   │    $    │  ~$0.10-0.20/Mtok   [Use: 65% of tasks]          │
│   └────┬────┘                                                   │
│        │                                                        │
│   ┌────▼────┐  Structured output, tool calls                     │
│   │  Nano   │  GPT-4.1 nano, specialized small models            │
│   │   ¢¢    │  ~$0.02-0.05/Mtok   [Use: 5% of tasks]           │
│   └─────────┘                                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## What Each Brain Does

### Nano Tier: Structured Output

**Models**: GPT-4.1 nano, fine-tuned small models
**Cost**: ~$0.02/Mtok input, $0.08/Mtok output
**Latency**: <500ms

**Use for**:
- JSON schema validation
- Simple classification
- Tool call routing
- Regex-able decisions

**Example**:
```python
# Pamela's trading signal parser
# Input: "BTC looking strong, maybe long?"
# Output: {"asset": "BTC", "signal": "long", "confidence": 0.7}

response = client.chat.completions.create(
    model="gpt-4.1-nano",
    messages=[{"role": "user", "content": raw_signal}],
    response_format={"type": "json_object"},  # Structured output
    max_tokens=100  # Cheap—constrained output
)
# Cost: ~$0.0002 per signal
```

65,000 trading signals/week = **$13 total**.

---

### Fast Tier: Routing & Triage

**Models**: Kimi K2.5, DeepSeek V3.2, Mistral Small
**Cost**: ~$0.10/Mtok input, $0.30/Mtok output
**Latency**: 1-2s

**Use for**:
- Task routing (which agent?)
- RSS summarization
- Initial triage
- Pattern matching

**Example — Hermes Dispatch**:
```python
# Route incoming task to correct agent

SYSTEM_PROMPT = """You are a task router. Analyze the task and return ONE of:
- "builder" for code/feature implementation
- "verifier" for testing/QA tasks  
- "pamela" for trading/market analysis
- "hermes" for strategic/architecture decisions

Return ONLY the agent name, no explanation."""

response = fireworks_client.chat.completions.create(
    model="accounts/fireworks/models/kimi-k2p5",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task_description}
    ],
    max_tokens=10  # Constrained output = cheap
)

# Cost: ~$0.005 per routing decision
# Hermes routes ~500 tasks/week = $2.50
```

**Why Kimi K2.5?**
- 256K context window (handles long RSS digests)
- MoE architecture = fast inference
- Fireworks pricing = ~$0.13/Mtok
- Good enough for routing decisions

---

### Smart Tier: Analysis & Synthesis

**Models**: Claude Sonnet 4, GPT-4.1, DeepSeek V3
**Cost**: ~$1.50/Mtok input, $4.50/Mtok output
**Latency**: 3-10s

**Use for**:
- Code review
- Writing/editing
- Multi-source synthesis
- Architecture decisions

**Example — Knowledge Synthesis**:
```python
# Hermes weekly knowledge harvest

system_prompt = """Synthesize the week's research into a coherent brief.
Themes to cover:
- Agent architecture patterns
- Model routing techniques
- Cost optimization strategies

Format: Executive summary + 3 key insights + links to sources."""

response = anthropic_client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=2000,
    messages=[{"role": "user", "content": f"{system_prompt}\n\n{research_context}"}]
)

# 4k input tokens, 2k output tokens
# Cost: (4000 * $1.50/1M) + (2000 * $4.50/1M) = $15/week
```

**Why Sonnet 4?**
- Speed/quality tradeoff sweet spot
- 200K context (can ingest multiple papers)
- Code understanding better than Kimi
- Anthropic's stability (less "behavior drift")

---

### Deep Tier: Complex Reasoning

**Models**: Claude Opus 4, GPT-5.4, o3-mini-high
**Cost**: ~$10/Mtok input, $30/Mtok output
**Latency**: 10-60s

**Use for**:
- Architecture redesigns
- Complex debugging
- Research synthesis across 10+ sources
- Novel algorithm design

**Example — System Architecture Review**:
```python
# Once-per-month deep architecture review

prompt = """Review our current agent orchestration architecture:

[Full system description: 10k tokens]

Identify:
1. Bottlenecks in the dispatch/worker pattern
2. Failure modes not handled by current health checks
3. Cost optimization opportunities

Propose 3 alternative architectures with tradeoff analysis."""

response = anthropic_client.messages.create(
    model="claude-opus-4-20250514",
    max_tokens=4000,
    messages=[{"role": "user", "content": prompt}]
)

# 12k input, 4k output
# Cost: ~$0.25 per review
# 4 reviews/month = $1/month
```

**Why Opus 4?**
- Best-in-class reasoning
- Handles complex multi-step analysis
- Catches edge cases Sonnet misses
- Worth the cost for critical decisions

---

## The Routing Config

Our model router is a 50-line Python file:

```python
# router.py — dispatch tier selection

MODEL_TIERS = {
    "nano": {
        "models": ["gpt-4.1-nano"],
        "cost_per_mtok": 0.10,
        "use_for": ["structured_output", "classification", "tool_routing"]
    },
    "fast": {
        "models": ["kimi-k2.5", "deepseek-v3.2"],
        "cost_per_mtok": 0.20,
        "use_for": ["routing", "triage", "summarize", "pattern_match"]
    },
    "smart": {
        "models": ["claude-sonnet-4", "gpt-4.1"],
        "cost_per_mtok": 3.00,
        "use_for": ["code_review", "writing", "synthesis", "analysis"]
    },
    "deep": {
        "models": ["claude-opus-4", "gpt-5.4"],
        "cost_per_mtok": 20.00,
        "use_for": ["architecture", "complex_debug", "research", "novel_design"]
    }
}

def route(task_type: str, complexity: int, context_size: int) -> str:
    """
    Route to appropriate tier.
    
    complexity: 1-10 (estimated cognitive load)
    context_size: token count of input
    """
    if task_type in ["structured", "classify"]:
        return "nano"
    elif complexity <= 3 and context_size < 10000:
        return "fast"
    elif complexity <= 7 and task_type not in ["architecture", "research"]:
        return "smart"
    else:
        return "deep"
```

**No ML model for routing** — simple rule-based. Why? 
- Routing errors are cheap (just retry with smarter model)
- No training data needed
- Explainable
- 50 lines vs 500 lines + training pipeline

---

## Real Week's Cost Breakdown

April 13-19, 2026:

| Tier | Model | Requests | Tokens | Cost |
|------|-------|----------|--------|------|
| Nano | GPT-4.1-nano | 1,247 | 180K | $0.18 |
| Fast | Kimi K2.5 | 412 | 850K | $0.11 |
| Fast | DeepSeek V3.2 | 156 | 320K | $0.05 |
| Smart | Claude Sonnet 4 | 23 | 45K | $0.07 |
| Smart | GPT-4.1 | 8 | 12K | $0.02 |
| Deep | Claude Opus 4 | 3 | 28K | $0.56 |
| **Total** | | **1,849** | **1.4M** | **$0.99** |

**Plus**: Claude Code (Builder) at ~$3/week.

**Total**: $3.99 for the week's AI compute.

Multiply by 3 for safety/buffer: **$12/week**.

---

## What Happens If You Don't Route

**All GPT-4.5** (April 2026 pricing):
- Input: $75/Mtok
- Output: $150/Mtok
- 1.4M tokens = ~$105/week
- Plus Claude Code = $108/week

**Monthly**: $468 vs $48.

**Annual**: $5,616 vs $576.

Same team. Same outputs. **10x cost difference**.

---

## The Anti-Patterns

### ✗ "Always use the best model"
-GPT-4.5 for routing decisions
-Opus for JSON validation  
-Claude for regex-able tasks

→ Burns money, adds latency, no quality gain

### ✗ "One model per agent"
-Hermes = always Kimi
-Builder = always Claude

→ Agents have sub-tasks. Some need deep reasoning, some need fast routing.

### ✗ "Let the LLM decide"
"Which model should handle this?" → LLM chooses → always picks expensive one

→ Build explicit routing logic.

---

## What Works

### ✓ Explicit tiers with documented use cases
Every engineer knows when to use which tier.

### ✓ Constrained output = constrained cost
`max_tokens=10` for routing. `max_tokens=100` for structured output. Don't let models ramble.

### ✓ Retry with smarter model
If Smart tier fails → retry with Deep. Cheaper than always using Deep.

### ✓ Monitor actual costs
Weekly cost report from Fireworks/Anthropic dashboards. Adjust routing thresholds.

---

## Implementation

The router is part of the **Multi-Agent Orchestration Blueprint**:

- `router.py` — tier selection logic
- `cost_tracker.py` — token counting + weekly reports
- `retry.py` — fallback to higher tier on failure
- Configurable thresholds per task type

[**Get the blueprint →**](https://edgelessai.gumroad.com/l/multi-agent-blueprint)

---

## Next: The Knowledge Base Loop

Post 3 covers the KB Loop Score (0-25) — how we measure and improve agent knowledge freshness, synthesis quality, and embedding pipeline health.

---

*Model routing saves 10x on AI costs. The trick isn't cutting corners—it's matching cognitive load to model capability.*
