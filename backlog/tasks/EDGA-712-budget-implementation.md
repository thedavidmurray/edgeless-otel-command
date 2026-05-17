# EDGA-712: Per-Agent Token/Cycle Budget Implementation

## Design

### 1. Budget Configuration (per agent config.yaml)
Add new top-level `budget` section:
```yaml
budget:
  metered: false                    # Fireworks = false, Anthropic/OpenAI = true
  token_budget_per_day: 1000000     # 1M tokens (health metric for Fireworks)
  cycle_budget_per_hour: 60         # Max 60 cycles/hour (hard limit)
  warning_threshold: 0.9            # 90% = warn
  halt_threshold: 1.0               # 100% = halt
```

### 2. Tracking File (~/.hermes/profiles/{agent}/budget-state.json)
```json
{
  "date": "2026-04-29",
  "hour": 14,
  "tokens_used": 45000,
  "cycles_used": 12,
  "last_reset": "2026-04-29T00:00:00Z"
}
```

### 3. Budget Monitor Script
- Runs per agent heartbeat
- Checks thresholds
- Posts to #audit-log on 90%
- Halts + notifies Hive on 100%

### 4. Daily Report
- Aggregate all agents
- Distinguish Fireworks (free) vs metered
- Save to claude-vault/13-Reports/agent-budgets-{date}.md

## Top 5 Agents to Instrument

1. **Pamela** (trading) - on VPS, metered=false (Fireworks)
2. **Hive** (coordinator) - metered=false (Fireworks)
3. **Beau** (VPS/infrastructure) - metered=false (Fireworks)
4. **Edgeless CC** (me) - metered=false (Fireworks)
5. **Ombudsman** (if waked) - metered=TBD
## Acceptance Criteria

- [x] Budget config added to 5 agent profiles
- [x] Budget tracking state file created
- [x] 90% threshold warning to #audit-log
- [x] 100% threshold halt + Hive notification
- [x] One day of metrics → vault report
- [x] Daily report distinguishes Fireworks vs metered

**Shipped:** 2026-05-17 — `scripts/budget-monitor.py` + `.hermes/profiles/*/config.yaml` (`79091c2`)
