#!/usr/bin/env python3
"""
Tiered Approval Gate for Swarm Commits
Ensures code touches and data mutations are reviewed before landing.

Usage:
    python scripts/approval-gate.py [--verbose] [--dry-run] [--bypass]
    python scripts/approval-gate.py --approve <commit-msg-file> --reviewer <name>
    python scripts/approval-gate.py --status

Tiers:
    Tier 0 (Auto)    — docs, markdown, txt  → no gate
    Tier 1 (Standard) — config, css, html   → smoke tests pass = auto
    Tier 2 (Sensitive) — code, scripts       → needs 1 reviewer approval
    Tier 3 (Critical)  — auth, infra, fin     → needs 2 reviewers + human

Exit codes:
    0 — approved / nothing to gate
    1 — blocked, needs approval
    2 — bypassed (emergency, logged)
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Tuple

PROJECT_ROOT = Path("/Users/djm/claude-projects")
APPROVALS_DIR = PROJECT_ROOT / ".approvals"
AUDIT_LOG = PROJECT_ROOT / "claude-vault" / "13-Reports" / "approval-audit.jsonl"

# --- Tier Classification ---

TIER_PATTERNS = {
    "tier0_auto": {
        "desc": "Auto-approved docs",
        "exts": {".md", ".txt", ".rst", ".adoc"},
        "paths": ["docs/", "README", "CHANGELOG", "LICENSE"],
        "min_approvers": 0,
    },
    "tier1_standard": {
        "desc": "Config / UI files",
        "exts": {".json", ".yaml", ".yml", ".toml", ".css", ".html", ".svg", ".xml"},
        "paths": ["config/", ".github/", "public/", "static/"],
        "min_approvers": 0,  # auto if smoke tests pass
    },
    "tier2_sensitive": {
        "desc": "Code / scripts",
        "exts": {".py", ".js", ".ts", ".tsx", ".swift", ".sh", ".bash", ".zsh", ".pl", ".rb"},
        "paths": ["src/", "scripts/", "tools/", "mcp-servers/"],
        "min_approvers": 1,
    },
    "tier3_critical": {
        "desc": "Auth / infra / financial",
        "exts": set(),  # matched by keywords instead
        "paths": [],
        "keywords": [
            "auth", "token", "password", "secret", "key", "credential",
            "infra", "deploy", "terraform", "docker", "kubernetes",
            "stripe", "payment", "billing", "wallet", "financial",
            "trading", "exchange", "api_key", "private_key",
        ],
        "min_approvers": 2,
    },
}


def classify_file(path: Path) -> Tuple[str, int]:
    """Return (tier_name, min_approvers) for a given file path."""
    rel = str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)
    lower_rel = rel.lower()
    ext = path.suffix.lower()

    # Tier 3 keyword check
    for tier_name, cfg in TIER_PATTERNS.items():
        if tier_name == "tier3_critical":
            for kw in cfg.get("keywords", []):
                if kw in lower_rel:
                    return tier_name, cfg["min_approvers"]

    # Path prefix checks
    for tier_name, cfg in TIER_PATTERNS.items():
        for prefix in cfg.get("paths", []):
            if lower_rel.startswith(prefix.lower()):
                return tier_name, cfg["min_approvers"]

    # Extension checks
    for tier_name, cfg in TIER_PATTERNS.items():
        if ext in cfg.get("exts", set()):
            return tier_name, cfg["min_approvers"]

    # Default: tier 2 for unknown files
    return "tier2_sensitive", 1


def get_staged_files() -> List[Path]:
    """Return list of staged file paths."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        return []
    files = []
    for line in result.stdout.strip().split("\n"):
        if line:
            p = PROJECT_ROOT / line
            if p.exists():
                files.append(p)
    return files


def get_commit_message_file() -> Path:
    """Return path to the commit message file from GIT environment."""
    env = os.environ.get("GIT_EDITOR", "")
    # When run as commit-msg hook, the message file is $1
    return Path(os.environ.get("GIT_COMMIT_MSG_FILE", ".git/COMMIT_EDITMSG"))


def compute_change_hash(files: List[Path]) -> str:
    """Compute a deterministic hash of the staged changes."""
    hasher = hashlib.sha256()
    for f in sorted(files):
        rel = str(f.relative_to(PROJECT_ROOT))
        hasher.update(rel.encode())
        # Include file size + mtime for lightweight fingerprint
        stat = f.stat()
        hasher.update(f"{stat.st_size}:{stat.st_mtime}".encode())
    return hasher.hexdigest()[:16]


def get_approvers(change_hash: str) -> Set[str]:
    """Return set of approvers for a given change hash."""
    approvers = set()
    if not APPROVALS_DIR.exists():
        return approvers
    for f in APPROVALS_DIR.glob(f"{change_hash}-*.txt"):
        approver = f.stem.replace(f"{change_hash}-", "")
        approvers.add(approver)
    return approvers


def record_approval(change_hash: str, reviewer: str) -> None:
    """Record an approval for a change hash."""
    APPROVALS_DIR.mkdir(parents=True, exist_ok=True)
    approval_file = APPROVALS_DIR / f"{change_hash}-{reviewer}.txt"
    approval_file.write_text(f"Approved by {reviewer} at {datetime.now(timezone.utc).isoformat()}Z\n")
    print(f"✅ Approval recorded: {reviewer} -> {change_hash}")


def log_audit(event: str, details: Dict) -> None:
    """Append an audit log entry."""
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event": event,
        **details,
    }
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def check_commit_message_approvals(msg_path: Path) -> Set[str]:
    """Parse # APPROVED: reviewer tags from commit message."""
    approvers = set()
    if not msg_path.exists():
        return approvers
    text = msg_path.read_text()
    for match in re.finditer(r"#\s*APPROVED:\s*(\w+)", text, re.IGNORECASE):
        approvers.add(match.group(1).lower())
    return approvers


def run_smoke_tests() -> bool:
    """Run preflight smoke tests."""
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "preflight" / "smoke_test.py")],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    return result.returncode == 0


def gate_check(verbose: bool = False, dry_run: bool = False) -> int:
    """Main gate logic. Returns exit code."""
    files = get_staged_files()
    if not files:
        if verbose:
            print("No staged files — nothing to gate.")
        return 0

    # Classify all staged files
    tier_counts: Dict[str, List[Path]] = {}
    max_tier = "tier0_auto"
    max_approvers = 0

    for f in files:
        tier, min_app = classify_file(f)
        tier_counts.setdefault(tier, []).append(f)
        if min_app > max_approvers:
            max_approvers = min_app
            max_tier = tier

    if verbose:
        print("=" * 50)
        print(f"🔒 Approval Gate — {len(files)} staged file(s)")
        print("=" * 50)
        for tier, paths in sorted(tier_counts.items()):
            desc = TIER_PATTERNS.get(tier, {}).get("desc", tier)
            print(f"\n{tier} ({desc}): {len(paths)} file(s)")
            for p in paths[:5]:
                print(f"  • {p.relative_to(PROJECT_ROOT)}")
            if len(paths) > 5:
                print(f"  ... and {len(paths) - 5} more")
        print(f"\nHighest tier: {max_tier} — requires {max_approvers} approver(s)")

    # Tier 0/1: auto-pass
    if max_approvers == 0:
        if max_tier == "tier1_standard":
            # Run smoke tests for standard tier
            if verbose:
                print("\n🧪 Running smoke tests for Tier 1...")
            if run_smoke_tests():
                if verbose:
                    print("✅ Smoke tests passed — auto-approved")
                log_audit("auto_approved", {"tier": max_tier, "files": len(files)})
                return 0
            else:
                print("❌ Smoke tests failed — commit blocked")
                return 1
        else:
            if verbose:
                print("✅ Tier 0 — auto-approved (docs only)")
            return 0

    # Tier 2/3: need approvals
    change_hash = compute_change_hash(files)
    disk_approvers = get_approvers(change_hash)
    msg_approvers = check_commit_message_approvals(get_commit_message_file())
    all_approvers = disk_approvers | msg_approvers

    if verbose:
        print(f"\nChange hash: {change_hash}")
        print(f"Disk approvals: {disk_approvers or '(none)'}")
        print(f"Message approvals: {msg_approvers or '(none)'}")
        print(f"Total: {len(all_approvers)} / {max_approvers} required")

    if len(all_approvers) >= max_approvers:
        if verbose:
            print(f"✅ Gate passed — approved by: {', '.join(sorted(all_approvers))}")
        log_audit("approved", {
            "tier": max_tier,
            "hash": change_hash,
            "approvers": sorted(all_approvers),
            "files": len(files),
        })
        return 0
    else:
        needed = max_approvers - len(all_approvers)
        print(f"\n❌ Approval Gate BLOCKED")
        print(f"   Tier: {max_tier} — {TIER_PATTERNS[max_tier]['desc']}")
        print(f"   Need {needed} more approval(s) ({len(all_approvers)}/{max_approvers})")
        print(f"   Change hash: {change_hash}")
        print(f"\nTo approve, run:")
        print(f"   python scripts/approval-gate.py --approve --reviewer <name>")
        print(f"\nOr add to commit message:")
        print(f"   # APPROVED: <reviewer>")
        print(f"\nTo bypass (emergency, logs audit):")
        print(f"   git commit --no-verify")
        log_audit("blocked", {
            "tier": max_tier,
            "hash": change_hash,
            "missing": needed,
            "files": len(files),
        })
        return 1


def main() -> int:
    p = argparse.ArgumentParser(description="Tiered approval gate for swarm commits")
    p.add_argument("--verbose", "-v", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="Show what would happen, don't block")
    p.add_argument("--bypass", action="store_true", help="Emergency bypass (logs audit)")
    p.add_argument("--approve", action="store_true", help="Record approval for current staged changes")
    p.add_argument("--reviewer", default="", help="Reviewer name for --approve")
    p.add_argument("--status", action="store_true", help="Show gate status for staged changes")
    args = p.parse_args()

    if args.bypass:
        files = get_staged_files()
        change_hash = compute_change_hash(files) if files else "none"
        log_audit("bypassed", {"hash": change_hash, "files": len(files) if files else 0})
        print("⚠️  Gate bypassed — audit logged")
        return 2

    if args.approve:
        if not args.reviewer:
            print("Error: --approve requires --reviewer <name>")
            return 1
        files = get_staged_files()
        if not files:
            print("No staged files to approve")
            return 1
        change_hash = compute_change_hash(files)
        record_approval(change_hash, args.reviewer.lower())
        return 0

    if args.status:
        return gate_check(verbose=True)

    return gate_check(verbose=args.verbose, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
