---
id: 323
title: Add post-tool-use error detection hook for autonomous learning
epic: agent-self-improvement
priority: P2
status: completed
depends_on: []
blocks: []
source: content-intelligence-pipeline (yt:2zhchG0r6iI - AI Jason self-improving agents)
created: 2026-05-02
---

# Task 323: Post-Tool-Use Error Detection Hook for Autonomous Learning

## Problem
When bash commands fail or tools error, the context is lost after the session. No mechanism to accumulate learnings from failures across sessions. Same errors get repeated.

## Solution
Add a post_tool_use hook that detects bash errors and auto-appends learnings to memory. Pattern: check exit code -> match error patterns -> append to learnings file -> index in MEMORY.md.

## Acceptance Criteria
- [x] Hook triggers on bash exit code != 0
- [x] Pattern matching for common error classes (import errors, permission denied, missing files, API errors)
- [x] Append structured learning entry to `claude-vault/05-Solutions/learnings/` with error context and resolution
- [x] Deduplicate — don't save the same error pattern twice (SHA256 hash per session)
- [x] Rate limit — max 5 learnings per session to prevent noise
- [x] Test with intentional failures to verify capture
- [x] Wired into `settings.json` as PostToolUse hook

## Implementation
- **Hook:** `.claude/hooks/post-tool-error-learner.py`
- **Patterns:** 20 error classes with regex matching and suggested fixes
- **Storage:** `claude-vault/05-Solutions/learnings/YYYYmmdd-HHMMSS-{category}.md` with YAML frontmatter
- **State:** `.runtime/error_learner_state.json` for session dedup + rate limiting
- **Tested:** Permission denied + missing import errors captured successfully
