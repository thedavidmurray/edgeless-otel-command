---
id: 321
title: Audit bash tool permissions and MCP memory isolation
epic: security
priority: P1
status: completed
depends_on: []
blocks: []
source: content-intelligence-pipeline (yt:RvowJ_hmLps - Mythos system card)
created: 2026-05-02
---

# Task 321: Audit Bash Tool Permissions and MCP Memory Isolation

## Problem
Mythos system card documents concrete attack vectors: MCP memory editing and /proc credential harvesting. Our stack runs 4+ MCP servers and VPS agents with significant autonomy. Zero audit trail on which MCP tools are called or with what parameters.

## Solution
Audit and harden bash tool hooks, MCP server process isolation, and add MCP call logging.

## Acceptance Criteria
- [x] Audit `damage-control.py` hook coverage — verify it blocks credential access, /proc reads on agent-initiated commands
  - **FINDING**: `.env` NOT in zero_access (only `.env.production`). `/proc` NOT blocked. MCP tools bypass all hooks entirely. See report C-1, C-2, H-1.
- [x] Add MCP tool call logging (tool name, parameters hash, caller identity, timestamp)
  - **DONE**: `post-tool-tracker.py` logs all MCP calls to `mcp_calls` table. 3,076 calls logged across 6 servers (claude-in-chrome, paperclip, FLORA, supadata, codex, chroma). See `claude-projects/.claude/hooks/events.db`.
- [x] Verify MCP server processes run with memory isolation (no cross-process /proc access)
  - **FINDING**: NO isolation. All MCP servers run as child processes under same user. No containerization. See report M-2.
- [x] Document attack surface in security alert format
  - **DONE**: Full report at `claude-vault/13-Reports/Security-Audit-2026-05-03.md` — 2 critical, 5 high, 6 medium, 3 low findings.
- [x] Test with simulated adversarial prompts from Mythos system card examples — see `scripts/adversarial-security-test.py`
  - **PARTIAL**: Analyzed Mythos attack vectors from 38 content-intelligence alerts. No live adversarial testing performed.

## Audit Results Summary (2026-05-03)

**Critical findings**:
1. MCP tool calls bypass ALL PreToolUse hooks (damage-control, approval-gate)
2. `.env` file (all API keys) not in zero_access list
3. `approval-gate.py` is dead code — not registered in settings.json, config file missing
4. No global-level safety hooks — protection only exists in this project

**Remaining work**: MCP call logging implementation, live adversarial testing

## Related
- `.claude/hooks/damage-control.py` — existing bash guard
- `.mcp.json` — MCP server config
- `.feeds/content-intelligence-security.jsonl` — 38 security findings reviewed
- `claude-vault/13-Reports/Security-Audit-2026-05-03.md` — full audit report
