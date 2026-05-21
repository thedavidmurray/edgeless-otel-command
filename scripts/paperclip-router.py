#!/usr/bin/env python3
"""Intelligent issue router for Paperclip AI.

Routing stack (layered, each layer adds signal):
  1. Semantic similarity (sentence-transformers embeddings) — primary signal
  2. Domain taxonomy (24 regex-based domains, autoreason-converged) — disambiguation
  3. QA quality multipliers (from Ombudsman feedback loop) — learning
  4. Circuit breakers (per-agent failure tracking) — anti-fragility

Cron: 15 10,14,18 * * * cron-wrapper.sh "paperclip_router" python3 scripts/paperclip-router.py
"""

import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from paperclip_constants import (
    AGENT_IDS,
    AGENT_NAMES,
    COMPANY_ID,
    PAPERCLIP_URL,
    PROJECT_ROOT,
    ROUTING_DISABLED_AGENTS,
)

try:
    from checkout_enforcement import checkout_with_enforcement  # type: ignore
except Exception:
    checkout_with_enforcement = None  # fallback if module missing

BATCH_SIZE = 7
MIN_CONFIDENCE = 0.25
ROUTING_LOG = Path(PROJECT_ROOT) / ".paperclip-routing-log.jsonl"
STATE_FILE = Path(PROJECT_ROOT) / ".paperclip-router-state.json"
LOG_FILE = Path(PROJECT_ROOT) / "logs" / "paperclip-router.log"

# ---------------------------------------------------------------------------
# Domain Taxonomy (autoreason-converged v2)
# Each domain has AT MOST ONE primary claimant — eliminates ambiguity
# ---------------------------------------------------------------------------
DOMAINS = {
    "documentation":   r"\b(?:documentation|docs|readme|guide|tutorial|api[\s-]?docs)\b",
    "content_writing": r"\b(?:article|blog(?:[\s-]?post)?|copy(?:writing)?|editorial|newsletter|digest|seo)\b",
    "knowledge_mgmt":  r"\b(?:knowledge[\s-]?(?:base|management|article)|kb|vault|obsidian|notebooklm|enrich|taxonomy)\b",
    "curation":        r"\b(?:curate|aggregate|organize|archive|categorize|tag(?:ging)?|collection|library|feed|rss|youtube)\b",
    "appsec":          r"\b(?:security|vulnerabilit|threat[\s-]?model|injection|xss|csrf|encryption|hardening)\b",
    "access_control":  r"\b(?:credential|secret[\s-]?(?:management|rotation)|permission|access[\s-]?control|auth(?:entication|orization))\b",
    "perf_audit":      r"\b(?:lighthouse|performance[\s-]?audit|dead[\s-]?link|page[\s-]?speed|core[\s-]?web[\s-]?vitals)\b",
    "implementation":  r"\b(?:implement|build(?:ing)?|code(?:base)?|engineer|refactor|migrat(?:e|ion)|overhaul)\b",
    "infra":           r"\b(?:infrastructure|ci/?cd|database|pipeline|backend|k8s)\b",
    "frontend":        r"\b(?:frontend|component|css|tailwind|nextjs|react|design[\s-]?system|ui[\s-]?component)\b",
    "ecommerce":       r"\b(?:e-?commerce|stripe|payment|checkout|storefront|gumroad)\b",
    "deploy":          r"\b(?:deploy(?:ment)?|release|rollout|staging)\b",
    "vps_ops":         r"\b(?:vps|server[\s-]?(?:admin|config|setup)|ssh|systemctl|pm2)\b",
    "research":        r"\b(?:research|explore|investigate|competitor[\s-]?analysis|market[\s-]?(?:analysis|research)|benchmark)\b",
    "web_scraping":    r"\b(?:scrape|crawl|fetch[\s-]?(?:data|page)|api[\s-]?integration|external[\s-]?api)\b",
    "messaging":       r"\b(?:telegram|notification|alert[\s-]?system)\b",
    "email":           r"\b(?:email[\s-]?(?:send|draft|template|campaign)|gmail)\b",
    "automation":      r"\b(?:automate|workflow|cron|schedule|hook)\b",
    "coordination":    r"\b(?:coordinate|align(?:ment)?|synthesize|orchestrate|cross-agent|roadmap)\b",
    "planning":        r"\b(?:planning|strategy|milestone|priorit(?:y|ize)|triage|retrospective|sprint)\b",
    "qa_review":       r"\b(?:quality[\s-]?(?:gate|check|assurance)|qa|qc|verify|validate|standards)\b",
    "mediation":       r"\b(?:mediate|dispute|resolution|arbitrate|escalat)\b",
    "code_review":     r"\b(?:code[\s-]?review|pr[\s-]?review|review[\s-]?(?:code|pull|pr))\b",
    "audit":           r"\b(?:audit|compliance|review[\s-]?(?:security|access|permission))\b",
}

_DOMAIN_PATTERNS = {name: re.compile(pat, re.IGNORECASE) for name, pat in DOMAINS.items()}

# Agent -> domain mapping (one primary claimant per domain)
AGENT_DOMAINS = {
    "scribe":    {"primary": ["documentation", "content_writing"], "secondary": ["knowledge_mgmt", "email"], "anti": ["appsec", "infra"]},
    "cypher":    {"primary": ["appsec", "access_control", "perf_audit", "audit"], "secondary": ["code_review"], "anti": ["content_writing", "curation"]},
    "beau":      {"primary": ["research", "vps_ops", "web_scraping"], "secondary": ["deploy"], "anti": ["content_writing"]},
    "hive":      {"primary": ["coordination", "planning"], "secondary": ["qa_review"], "anti": ["implementation", "infra"]},
    "hermes":    {"primary": ["messaging", "automation"], "secondary": ["email"], "anti": []},
    "ombudsman": {"primary": ["qa_review", "mediation"], "secondary": ["code_review"], "anti": ["implementation", "infra"]},
    "builder":   {"primary": ["implementation", "infra", "frontend", "ecommerce"], "secondary": ["deploy"], "anti": ["content_writing", "curation"]},
    "curator":   {"primary": ["curation"], "secondary": ["knowledge_mgmt", "research"], "anti": ["appsec", "implementation"]},
}

# ---------------------------------------------------------------------------
# Capability gate (hard constraints)
#
# Background: Semantic routing can overpower the anti-domain penalties and route
# issues to an agent that is not capable of executing them (e.g. research agent
# assigned to engineering tasks). This gate is intentionally conservative: it
# prevents known-mismatch assignments even when semantic similarity is high.
#
# Design:
# - If an issue matches a "domain group", only the allowed agents for that group
#   may be assigned.
# - Additionally, ANY match against an agent's explicit `anti` domains is a hard
#   reject (no amount of semantic score may override).
# ---------------------------------------------------------------------------

DOMAIN_GROUPS: list[tuple[str, set[str], set[str]]] = [
    # (group_name, domains, allowed_agents)
    ("engineering", {"implementation", "infra", "frontend", "ecommerce"}, {"builder"}),
    ("security", {"appsec", "access_control", "audit"}, {"cypher"}),
    ("perf", {"perf_audit"}, {"builder", "cypher"}),
    ("content", {"documentation", "content_writing", "email"}, {"scribe"}),
    ("knowledge", {"knowledge_mgmt", "curation"}, {"scribe", "curator"}),
    ("research", {"research", "web_scraping", "vps_ops", "deploy"}, {"beau", "curator"}),
    ("ops_automation", {"automation", "messaging"}, {"hermes"}),
    ("coordination", {"coordination", "planning"}, {"hive"}),
    ("qa_mediation", {"qa_review", "mediation", "code_review"}, {"ombudsman", "cypher"}),
]


def capability_gate_allows(agent_name: str, detected_domains: set[str]) -> tuple[bool, str]:
    """Return (allowed, reason)."""
    profile = AGENT_DOMAINS.get(agent_name, {})
    anti = set(profile.get("anti", []))
    anti_hits = sorted(anti.intersection(detected_domains))
    if anti_hits:
        return False, f"anti-domain match: {anti_hits}"

    matched_groups = [g for g, domains, _allowed in DOMAIN_GROUPS if detected_domains.intersection(domains)]
    if not matched_groups:
        return True, "no capability group matched"

    allowed_sets = [allowed for _g, domains, allowed in DOMAIN_GROUPS if detected_domains.intersection(domains)]
    allowed = set.intersection(*allowed_sets) if allowed_sets else set()
    if not allowed:
        # Mixed-domain issue that doesn't cleanly map: require human triage.
        return False, f"mixed domains require triage (groups={matched_groups})"

    if agent_name not in allowed:
        return False, f"capability gate: groups={matched_groups} allow={sorted(allowed)}"

    return True, f"capability gate pass (groups={matched_groups})"


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(f"[{ts}] {msg}\n")


def api_get(path: str):
    try:
        with urllib.request.urlopen(f"{PAPERCLIP_URL}/api/{path}", timeout=10) as resp:
            return json.load(resp)
    except Exception:
        return None


def api_post(path: str, data: dict):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{PAPERCLIP_URL}/api/{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.load(resp)
    except Exception as e:
        log(f"API POST {path} failed: {e}")
        return None


def issue_assignee_id(issue: dict) -> str:
    """Return the Paperclip assignee id across old and current API shapes."""
    return (
        issue.get("assigneeAgentId")
        or issue.get("assigneeId")
        or issue.get("agentId")
        or ""
    )


def build_routable_agents(agents: list[dict]) -> set[str]:
    """Agents eligible for new automated assignments.

    An agent is routable when it is known locally, not explicitly disabled, not
    in an error/paused state, and can actually be woken by heartbeat or demand.
    """
    routable = set()
    for agent in agents:
        name = str(agent.get("name", "")).lower().replace("-", "_")
        if not name or name not in AGENT_IDS:
            continue
        if name in ROUTING_DISABLED_AGENTS:
            continue
        if agent.get("status") in {"error", "paused", "cancelled"}:
            continue
        heartbeat = (agent.get("runtimeConfig") or {}).get("heartbeat") or {}
        if heartbeat.get("enabled") or heartbeat.get("wakeOnDemand"):
            routable.add(name)
    return routable


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {
        "routed": {},
        "flagged_for_human": [],
        "stats": {"total_routed": 0, "total_flagged": 0, "batches_run": 0},
        "last_run": None,
    }


def save_state(state: dict):
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2))


def log_routing_decision(decision: dict):
    decision["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(ROUTING_LOG, "a") as f:
        f.write(json.dumps(decision) + "\n")


def get_agent_current_load() -> dict[str, int]:
    coord_file = Path(PROJECT_ROOT) / ".hive-coordinator-state.json"
    if coord_file.exists():
        try:
            data = json.loads(coord_file.read_text())
            return {
                name: info.get("open_issues", 0)
                for name, info in data.get("agent_workloads", {}).items()
            }
        except Exception:
            pass
    return {}


def detect_domains(text: str) -> set[str]:
    """Binary domain detection — which domains are present in this text."""
    return {name for name, pat in _DOMAIN_PATTERNS.items() if pat.search(text)}


def domain_score_agent(agent_name: str, detected_domains: set[str]) -> tuple[float, list[str]]:
    """Score agent based on domain taxonomy. Returns (score, matches)."""
    profile = AGENT_DOMAINS.get(agent_name)
    if not profile:
        return 0.0, []

    score = 0.0
    matches = []
    for d in profile.get("primary", []):
        if d in detected_domains:
            score += 1.0
            matches.append(f"+1.0:domain:{d}")
    for d in profile.get("secondary", []):
        if d in detected_domains:
            score += 0.5
            matches.append(f"+0.5:domain:{d}")
    for d in profile.get("anti", []):
        if d in detected_domains:
            score -= 1.5
            matches.append(f"-1.5:anti:{d}")
    return score, matches


def route_issue(issue: dict, current_loads: dict, routable_agents: set[str] | None = None) -> dict:
    """Route using semantic similarity + domain taxonomy + QA multipliers."""
    issue_id = issue.get("id", "")
    identifier = issue.get("identifier", "?")
    title = issue.get("title", "")
    description = issue.get("description", "")
    text = f"{title} {description}"

    # Try semantic routing first
    try:
        from semantic_router import route_issue as semantic_route, compute_confidence
        semantic_candidates = semantic_route(
            title=title,
            description=description,
            current_loads=current_loads,
        )
        use_semantic = bool(semantic_candidates)
    except Exception as e:
        log(f"Semantic router unavailable ({e}), falling back to domain-only")
        semantic_candidates = []
        use_semantic = False

    # Domain-based scoring (always computed — used as tiebreaker or fallback)
    detected = detect_domains(text)
    domain_scores = {}
    domain_matches = {}
    routable_agents = routable_agents or set(AGENT_DOMAINS)
    for agent_name in AGENT_DOMAINS:
        if agent_name not in routable_agents:
            continue
        current = current_loads.get(agent_name, 0)
        max_cap = AGENT_DOMAINS[agent_name].get("max_concurrent", 2)
        # Pull max_concurrent from the profile data
        for prof_name, prof_data in [
            ("scribe", 3), ("cypher", 2), ("beau", 2), ("hive", 2),
            ("hermes", 3), ("ombudsman", 5), ("builder", 2), ("curator", 3),
        ]:
            if agent_name == prof_name:
                max_cap = prof_data
                break
        if current >= max_cap:
            continue
        s, m = domain_score_agent(agent_name, detected)
        if s > 0 or not use_semantic:  # Keep all candidates in fallback mode
            domain_scores[agent_name] = s
            domain_matches[agent_name] = m

    # Fuse scores
    candidates = []
    if use_semantic:
        for sc in semantic_candidates[:8]:
            agent = sc["agent"]
            if agent not in routable_agents:
                continue
            d_score = domain_scores.get(agent, 0.0)
            d_match = domain_matches.get(agent, [])

            # Fused: 70% semantic + 30% domain (normalized to 0-1 range)
            # Domain score normalized: typical range 0-3, divide by 3
            domain_norm = max(d_score / 3.0, 0.0)
            fused = 0.7 * sc["final_score"] + 0.3 * domain_norm

            candidates.append({
                "agent": agent,
                "fused_score": round(fused, 4),
                "semantic_score": sc["final_score"],
                "domain_score": round(d_score, 2),
                "quality_mult": sc.get("quality_multiplier", 1.0),
                "centroid_sim": sc.get("centroid_sim", 0),
                "best_example_sim": sc.get("best_example_sim", 0),
                "matches": d_match,
                "current_load": sc.get("current_load", 0),
                "headroom": sc.get("headroom", 0),
            })
        candidates.sort(key=lambda c: c["fused_score"], reverse=True)
    else:
        # Domain-only fallback
        for agent, d_score in sorted(domain_scores.items(), key=lambda x: x[1], reverse=True):
            if d_score <= 0:
                continue
            candidates.append({
                "agent": agent,
                "fused_score": round(d_score / 3.0, 4),  # Normalize
                "semantic_score": 0,
                "domain_score": round(d_score, 2),
                "quality_mult": 1.0,
                "matches": domain_matches.get(agent, []),
                "current_load": current_loads.get(agent, 0),
                "headroom": 0,
            })

    # Capability gate: filter out candidates that are known-mismatches.
    gated_out = []
    gated_candidates = []
    for c in candidates:
        ok, reason = capability_gate_allows(c["agent"], detected)
        if ok:
            gated_candidates.append(c)
        else:
            gated_out.append({"agent": c["agent"], "reason": reason, "score": c.get("fused_score")})

    # Prefer gated candidates if any remain; otherwise keep original list so we can
    # explain why we're flagging/hard-falling-back.
    if gated_candidates:
        candidates = gated_candidates

    decision = {
        "issue_id": issue_id,
        "identifier": identifier,
        "title": title[:120],
        "routing_engine": "semantic+domain" if use_semantic else "domain-only",
        "domains_detected": sorted(detected),
        "candidates": candidates[:5],
        "capability_gate_rejections": gated_out[:8],
    }

    if not candidates:
        # Hive fallback: route for dispatch review instead of assigning to a broken worker.
        decision["action"] = "assign"
        decision["assigned_to"] = "hive" if "hive" in routable_agents else ""
        decision["confidence"] = 0.3
        decision["score"] = 0.3
        decision["reason"] = "no match - dispatch fallback"
        decision["matches"] = []
        if not decision["assigned_to"]:
            decision["action"] = "flag_human"
            decision["reason"] = "no match and no routable fallback agent"
        return decision

    best = candidates[0]

    # Compute confidence
    if use_semantic:
        confidence = compute_confidence(semantic_candidates)
    else:
        confidence = min(best["fused_score"], 1.0)

    if confidence < MIN_CONFIDENCE:
        decision["action"] = "flag_human"
        decision["reason"] = f"low confidence ({confidence:.2f})"
        decision["confidence"] = round(confidence, 3)
        decision["best_candidate"] = best
        return decision

    # Ambiguity check
    if len(candidates) > 1:
        gap = best["fused_score"] - candidates[1]["fused_score"]
        if gap < 0.03 and confidence < 0.5:
            decision["action"] = "flag_human"
            decision["reason"] = f"ambiguous: {best['agent']}({best['fused_score']:.3f}) vs {candidates[1]['agent']}({candidates[1]['fused_score']:.3f})"
            decision["confidence"] = round(confidence, 3)
            return decision

    decision["action"] = "assign"
    decision["assigned_to"] = best["agent"]
    decision["confidence"] = round(confidence, 3)
    decision["score"] = best["fused_score"]
    decision["matches"] = best.get("matches", [])

    return decision


def execute_assignment(issue_id: str, agent_name: str) -> bool | str:
    """Assign issue.

    Returns:
      - True on success
      - 'conflict' on 409 (already assigned)
      - False on other errors

    Capability gate behavior:
      - If checkout_enforcement is available, we use it as the canonical checkout
        implementation (it performs classification + warning/block + the checkout).
      - If blocked, we attempt ONE auto-reroute to the gate's suggested agent.
      - If enforcement module is unavailable (or errors), we fall back to direct checkout.
    """

    tried: list[str] = []

    while True:
        agent_id = AGENT_IDS.get(agent_name)
        if not agent_id:
            return False

        tried.append(agent_name)

        # Phase 2 capability gate: soft enforcement on checkout
        if checkout_with_enforcement is not None:
            try:
                gate_result = checkout_with_enforcement(
                    issue_id=issue_id,
                    agent_id=agent_id,
                    expected_statuses=["todo", "backlog"],
                    dry_run=False,
                )

                action = gate_result.get("action")
                if action == "blocked":
                    suggested_uuid = gate_result.get("suggested_agent")
                    suggested_name = AGENT_NAMES.get(suggested_uuid or "")

                    log(
                        f"CAPABILITY_GATE_BLOCKED issue={issue_id} agent={agent_name} "
                        f"reason={gate_result.get('reason')} task_type={gate_result.get('task_type')} "
                        f"suggested={suggested_name or '?'}"
                    )

                    # Auto-reroute: try the suggested primary agent once.
                    if suggested_name and suggested_name not in tried:
                        log(
                            f"CAPABILITY_GATE_REROUTE issue={issue_id} from={agent_name} to={suggested_name} "
                            f"task_type={gate_result.get('task_type')}"
                        )
                        agent_name = suggested_name
                        continue

                    return False

                if action == "warned":
                    log(
                        f"CAPABILITY_GATE_WARNED issue={issue_id} agent={agent_name} "
                        f"reason={gate_result.get('reason')} task_type={gate_result.get('task_type')}"
                    )

                # If enforcement ran, it already executed the checkout.
                if gate_result.get("ok") is True:
                    return True

                # If enforcement returned ok=False for a non-block reason, treat as failure.
                # (This avoids double-checkout attempts which can create confusing 409s.)
                return False

            except Exception as e:
                log(f"Checkout enforcement error (falling through to direct checkout): {e}")

        # Direct checkout fallback (only used when enforcement module unavailable)
        body = json.dumps({"agentId": agent_id, "expectedStatuses": ["todo", "backlog"]}).encode()
        req = urllib.request.Request(
            f"{PAPERCLIP_URL}/api/issues/{issue_id}/checkout",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                json.load(resp)
                return True
        except urllib.error.HTTPError as e:
            if e.code == 409:
                return "conflict"
            log(f"API POST issues/{issue_id}/checkout failed: {e}")
            return False
        except Exception as e:
            log(f"API POST issues/{issue_id}/checkout failed: {e}")
            return False


def load_qa_feedback() -> dict:
    qa_log = Path(PROJECT_ROOT) / ".paperclip-qa-log.jsonl"
    if not qa_log.exists():
        return {}
    outcomes = {}
    for line in qa_log.read_text().strip().split("\n"):
        if not line:
            continue
        try:
            entry = json.loads(line)
            if entry.get("outcome") and entry.get("issue_id"):
                outcomes[entry["issue_id"]] = entry
        except Exception:
            continue
    return outcomes


def compute_agent_success_rates(qa_outcomes: dict) -> dict:
    rates = {}
    for entry in qa_outcomes.values():
        agent = entry.get("routed_to", "")
        if not agent:
            continue
        if agent not in rates:
            rates[agent] = {"pass": 0, "fail": 0}
        if entry.get("outcome") == "pass":
            rates[agent]["pass"] += 1
        else:
            rates[agent]["fail"] += 1
    for agent, data in rates.items():
        total = data["pass"] + data["fail"]
        data["rate"] = round(data["pass"] / total, 3) if total > 0 else 0.0
    return rates


def main():
    agents = api_get(f"companies/{COMPANY_ID}/agents")
    if not agents:
        log("Paperclip unreachable, skipping")
        return
    routable_agents = build_routable_agents(agents)
    if not routable_agents:
        log("No routable agents available, skipping")
        return

    state = load_state()
    already_routed = set(state.get("routed", {}).keys())
    already_flagged = {f["issue_id"] for f in state.get("flagged_for_human", [])}

    qa_outcomes = load_qa_feedback()
    success_rates = compute_agent_success_rates(qa_outcomes)
    if success_rates:
        log(f"Agent success rates: {json.dumps(success_rates)}")

    issues = api_get(f"companies/{COMPANY_ID}/issues")
    if not issues:
        log("No issues returned")
        return

    unassigned = []
    for issue in issues:
        iid = issue.get("id", "")
        status = issue.get("status", "")
        assignee = issue_assignee_id(issue)
        if status in ("done", "cancelled"):
            continue
        if assignee:
            continue
        if iid in already_routed or iid in already_flagged:
            continue
        unassigned.append(issue)

    if not unassigned:
        log(f"No unassigned issues to route (total issues: {len(issues)})")
        return

    log(f"Found {len(unassigned)} unassigned issues, routing batch of {min(len(unassigned), BATCH_SIZE)}")
    current_loads = get_agent_current_load()

    batch = unassigned[:BATCH_SIZE]
    assigned_count = 0
    flagged_count = 0

    for issue in batch:
        decision = route_issue(issue, current_loads, routable_agents)
        log_routing_decision(decision)

        if decision["action"] == "assign":
            agent = decision["assigned_to"]
            result = execute_assignment(decision["issue_id"], agent)
            if result is True:
                state["routed"][decision["issue_id"]] = {
                    "agent": agent,
                    "identifier": decision["identifier"],
                    "confidence": decision["confidence"],
                    "routing_engine": decision.get("routing_engine", "unknown"),
                    "routed_at": datetime.now(timezone.utc).isoformat(),
                }
                current_loads[agent] = current_loads.get(agent, 0) + 1
                assigned_count += 1
                log(f"Assigned {decision['identifier']} -> {agent} (conf={decision['confidence']}, engine={decision.get('routing_engine')})")
            elif result == "conflict":
                # Already assigned — record in state so we don't retry
                state["routed"][decision["issue_id"]] = {
                    "agent": "already_assigned",
                    "identifier": decision["identifier"],
                    "confidence": 0,
                    "routed_at": datetime.now(timezone.utc).isoformat(),
                }
            else:
                log(f"Failed to assign {decision['identifier']} -> {agent}")

        elif decision["action"] == "flag_human":
            state.setdefault("flagged_for_human", []).append({
                "issue_id": decision["issue_id"],
                "identifier": decision["identifier"],
                "title": decision["title"],
                "reason": decision["reason"],
                "confidence": decision.get("confidence", 0),
                "candidates": decision.get("candidates", [])[:3],
                "flagged_at": datetime.now(timezone.utc).isoformat(),
            })
            flagged_count += 1
            log(f"Flagged {decision['identifier']} for human: {decision['reason']}")

    state["stats"]["total_routed"] = len(state.get("routed", {}))
    state["stats"]["total_flagged"] = len(state.get("flagged_for_human", []))
    state["stats"]["batches_run"] = state["stats"].get("batches_run", 0) + 1
    state["stats"]["last_batch_assigned"] = assigned_count
    state["stats"]["last_batch_flagged"] = flagged_count
    state["stats"]["remaining_unassigned"] = len(unassigned) - len(batch)
    if success_rates:
        state["stats"]["agent_success_rates"] = success_rates

    save_state(state)

    summary = f"Router: {assigned_count} assigned, {flagged_count} flagged, {len(unassigned) - len(batch)} remaining"
    print(summary)
    log(summary)


if __name__ == "__main__":
    main()
