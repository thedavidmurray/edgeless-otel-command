#!/usr/bin/env python3
"""
post-tool-error-learner.py — PostToolUse hook for autonomous learning from failures.
Detects bash/tool errors, classifies them, and appends structured learnings to memory.

Rules:
- Max 5 learnings per session (rate limit)
- Deduplicate by error pattern hash
- Only captures bash/tools with exit_code != 0 or error keys in output
- Writes to claude-vault/05-Solutions/learnings/ with frontmatter
"""

import json
import os
import sys
import re
import hashlib
from datetime import datetime
from pathlib import Path

# Config
MAX_LEARNINGS_PER_SESSION = 5
LEARNINGS_DIR = Path("/Users/djm/claude-projects/claude-vault/05-Solutions/learnings")
SESSION_STATE_DIR = Path("/Users/djm/claude-projects/.runtime")
SESSION_STATE_FILE = SESSION_STATE_DIR / "error_learner_state.json"

# Error patterns: (regex, category, suggested_fix)
ERROR_PATTERNS = [
    (r"ModuleNotFoundError: No module named '([^']+)'", "missing_import", "pip install {match}"),
    (r"ImportError:.*cannot import name '([^']+)'", "missing_import", "Check package version / reinstall"),
    (r"Permission denied", "permission_denied", "Check file permissions or use sudo"),
    (r"No such file or directory: (.+)", "missing_file", "Verify path exists: {match}"),
    (r"fatal: Authentication failed", "git_auth_fail", "Check git credentials / PAT / ssh keys"),
    (r"fatal: could not read Username", "git_auth_fail", "Configure git auth (gh login / token)"),
    (r"HTTP 401|401 Unauthorized", "api_auth_fail", "Check API key / token validity"),
    (r"HTTP 429|429 Too Many Requests", "rate_limited", "Add backoff / reduce request frequency"),
    (r"HTTP 500|502|503|504", "server_error", "Retry with exponential backoff"),
    (r"Connection refused|Connection timed out", "network_error", "Check service status / network / URL"),
    (r"syntax error|SyntaxError", "syntax_error", "Fix syntax in source file"),
    (r"command not found: (.+)", "missing_command", "Install {match} or check PATH"),
    (r"error: pathspec '(.+)' did not match", "git_branch_missing", "Create branch or check branch name"),
    (r"Merge conflict|CONFLICT", "git_merge_conflict", "Resolve conflicts manually then commit"),
    (r"docker: Cannot connect to the Docker daemon", "docker_not_running", "Start Docker Desktop / docker daemon"),
    (r"npm ERR!|yarn error|pnpm ERR!", "package_manager_error", "Check package.json / lockfile / registry"),
    (r"cannot find module '(.+)'", "missing_node_module", "npm install {match}"),
    (r"TypeError: Cannot read propert(ies)? of (undefined|null)", "js_runtime_error", "Add null checks / validate data shape"),
    (r"exit code 1|exit_code.*1", "generic_failure", "Review full error output for root cause"),
    (r"timeout|timed out after", "timeout", "Increase timeout or optimize operation"),
]


def get_session_state() -> dict:
    """Load or init session state for dedup + rate limiting."""
    SESSION_STATE_DIR.mkdir(parents=True, exist_ok=True)
    if SESSION_STATE_FILE.exists():
        try:
            with open(SESSION_STATE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"learned_hashes": [], "count": 0}


def save_session_state(state: dict):
    try:
        with open(SESSION_STATE_FILE, "w") as f:
            json.dump(state, f)
    except IOError:
        pass


def classify_error(stdout: str, stderr: str, exit_code: int) -> tuple:
    """Classify error into (category, suggestion, matched_text)."""
    combined = f"{stdout}\n{stderr}"
    for pattern, category, fix_template in ERROR_PATTERNS:
        m = re.search(pattern, combined, re.IGNORECASE)
        if m:
            match = m.group(1) if m.lastindex else m.group(0)
            fix = fix_template.replace("{match}", match)
            return category, fix, m.group(0)
    # Fallback
    if exit_code != 0:
        return "unknown_error", f"Exit code {exit_code} — review output for details", ""
    return None, None, None


def hash_learning(category: str, tool_name: str, matched_text: str) -> str:
    """Deduplication hash."""
    key = f"{category}:{tool_name}:{matched_text[:80]}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def write_learning(category: str, tool_name: str, error_text: str, suggestion: str, context: dict):
    """Write structured learning to vault."""
    LEARNINGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = re.sub(r"[^a-z0-9-]", "-", category.lower())[:30]
    filename = LEARNINGS_DIR / f"{ts}-{slug}.md"

    frontmatter = {
        "note_type": "learning",
        "content_type": "error_pattern",
        "status": "active",
        "created": datetime.now().isoformat(),
        "category": category,
        "tool": tool_name,
        "tags": [f"error/{category}", "autonomous-learning"],
    }

    body = f"""# Error Learning: {category}

**Tool:** `{tool_name}`  
**Detected:** {datetime.now().isoformat()}  
**Category:** {category}

## Error Snippet
```
{error_text[:400]}
```

## Suggested Fix
{suggestion}

## Context
- Session: {context.get('session_id', 'unknown')}
- Caller: {context.get('caller', 'unknown')}
- Exit code: {context.get('exit_code', 'N/A')}

## Prevention
- [ ] Add pre-flight check for this condition
- [ ] Update relevant skill or hook documentation
- [ ] Consider adding to `patterns.yaml` if recurring
"""

    content = "---\n" + json.dumps(frontmatter, indent=2) + "\n---\n\n" + body
    try:
        with open(filename, "w") as f:
            f.write(content)
        return str(filename)
    except IOError:
        return None


def main():
    # Read hook input
    raw = sys.stdin.read(100000)
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        print(json.dumps({"continue": True}))
        return

    tool_name = data.get("tool", data.get("tool_name", "unknown"))
    output = data.get("output", data.get("result", {}))
    tool_input = data.get("input", {})
    session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")

    # Extract exit code and error text
    exit_code = 0
    stdout = ""
    stderr = ""
    if isinstance(output, dict):
        exit_code = output.get("exit_code", 0)
        stdout = str(output.get("stdout", ""))
        stderr = str(output.get("stderr", ""))
        if output.get("error") and not exit_code:
            exit_code = 1
    elif isinstance(output, str):
        stdout = output
        if "error" in output.lower():
            exit_code = 1

    if exit_code == 0:
        if isinstance(output, dict) and output.get("error"):
            exit_code = 1
        elif isinstance(output, str) and "error" in output.lower():
            exit_code = 1

    if exit_code == 0:
        print(json.dumps({"continue": True}))
        return

    # Classify
    category, suggestion, matched = classify_error(stdout, stderr, exit_code)
    if not category:
        print(json.dumps({"continue": True}))
        return

    # Rate limit + dedup
    state = get_session_state()
    if state["count"] >= MAX_LEARNINGS_PER_SESSION:
        print(json.dumps({"continue": True}))
        return

    h = hash_learning(category, tool_name, matched)
    if h in state["learned_hashes"]:
        print(json.dumps({"continue": True}))
        return

    # Write learning
    context = {
        "session_id": session_id,
        "caller": os.environ.get("CLAUDE_AGENT_ID", os.environ.get("HERMES_PROFILE", "unknown")),
        "exit_code": exit_code,
    }
    path = write_learning(category, tool_name, matched or stdout, suggestion, context)
    if path:
        state["learned_hashes"].append(h)
        state["count"] += 1
        save_session_state(state)

    print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
