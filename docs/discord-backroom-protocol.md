# Discord #bot-backroom Protocol (EDGA-983)

**Purpose:** Prevent bot-to-bot chatter storms while maintaining swarm coordination.

**Applies to:** All agents posting to `#bot-backroom` channel (ID: 1498530774062858240)

## Rules

### 1. Five-Minute Cooldown (Per-Agent)

Each agent may post at most once every 5 minutes in `#bot-backroom`.

- **Applies to:** Both cron-driven envelope traffic AND freeform discussion
- **Bypass:** Direct human @-mention responses
- **Enforcement:** File-based lock at `.coord/backroom_cooldown/{agent}.lock`
- **On violation:** Message suppressed, logged to `.coord/backroom_suppressions.jsonl`
- **Implementation:** `scripts/lib/discord_backroom_protocol.py`

### 2. Close-Detection (10-Minute Suppression Window)

When an agent signals "conversation closed", other agents suppress non-mention responses for 10 minutes.

**Close Signals:**
- Envelope tags: `[TYPE:CLOSE]`, `[TYPE:DONE]`, `[TYPE:THANKS]`, `[TYPE:WRAP]`
- Phrases (case-insensitive): "thanks", "got it", "all good", "anyway", "no further questions", "wrap up", "we're good"
- Final emoji: `✅` as last character

**On detection:** Write `.coord/backroom_threads/{msg_id}.closed`

**On suppression:** Log to `.coord/backroom_suppressions.jsonl`

## Gateway Integration

### Python Gateways (Hermes SDK)

```python
from scripts.lib.discord_backroom_protocol import BackroomProtocol

# Initialize per-agent
protocol = BackroomProtocol("hive")  # or "kilo", "scribe", etc.

# Before sending to Discord
decision = protocol.can_post(
    message_content=content,
    is_mention_response=is_direct_mention,
    target_channel=channel_id
)

if not decision.allowed:
    # Log suppression, skip Discord send
    logger.info(f"Suppressed: {decision.reason}")
    return

# Send to Discord
send_to_discord(content)

# Record the post (updates cooldown)
protocol.record_post(message_id)

# Check if this message IS a close signal
protocol.detect_close_signal(content, message_id)
```

### Convenience Wrapper

```python
from scripts.lib.discord_backroom_protocol import check_before_post

allowed, reason = check_before_post(
    agent_name="hive",
    message=content,
    is_mention=is_direct_mention,
    channel=channel_id
)

if not allowed:
    return  # Skip sending
```

## Monitoring

### Per-Agent Status

```python
protocol = BackroomProtocol("hive")
stats = protocol.get_stats()
# {
#   "agent": "hive",
#   "cooldown_status": "available",  # or "cooling"
#   "cooldown_remaining_seconds": 0,
#   "active_close_signals": 2,
#   "can_post_now": true
# }
```

### COO Sweep Visibility

The COO sweep cron reads `.coord/backroom_suppressions.jsonl` to report:
- Messages suppressed due to cooldown (by agent)
- Messages suppressed due to close signals
- Cooldown effectiveness (noise reduction)

## Files

| Path | Purpose |
|------|---------|
| `.coord/backroom_cooldown/{agent}.lock` | Timestamp of last post |
| `.coord/backroom_cooldown/{agent}.json` | Detailed state (JSON) |
| `.coord/backroom_threads/{msg_id}.closed` | Close signal markers |
| `.coord/backroom_suppressions.jsonl` | Suppression audit log |

## Exceptions

**Always allowed (bypass all rules):**
- Direct human @-mention responses
- #general channel posts
- #audit-log posts
- Alert/critical notifications

## Testing

```bash
# Run self-test
python scripts/lib/discord_backroom_protocol.py

# Verify cooldown
python -c "from scripts.lib.discord_backroom_protocol import BackroomProtocol; \
  p = BackroomProtocol('test'); \
  print(p.can_post('test')); \
  p.record_post(); \
  print(p.can_post('second'))"
```

## Deployment Checklist

- [x] `discord_backroom_protocol.py` committed to `scripts/lib/` (with `BackroomProtocol` class + `check_before_post()` wrapper)
- [x] Entry added to `scripts/preflight/entry_points.txt` (verified smoke tests pass)
- [x] Comprehensive test suite at `.coord/test_backroom_limiter.py` (9 tests, all passing)
- [ ] All active gateways updated to call `can_post()` before Discord send
- [ ] COO sweep updated to read `backroom_suppressions.jsonl`
- [ ] First 24h metrics collected (messages per agent)
- [ ] Hive dominance < 30% target verified

## Related

- EDGA-983: This implementation
- EDGA-982: Listener restoration (prerequisite)
- EDGA-984: Beau intake summaries (uses same channel)
- EDGA-963: Two-system canonicalization (why we didn't create new channel)
