#!/Library/Frameworks/Python.framework/Versions/3.11/bin/python3
"""
Cron Job Failure Alerting System
Monitors cron job execution, detects failures, and sends email alerts.

Usage:
    # As a wrapper for cron jobs:
    python cron_failure_alerter.py --wrap "job_name" -- command args

    # Monitor all recent cron logs:
    python cron_failure_alerter.py --check-logs

    # Test email alerting:
    python cron_failure_alerter.py --test

Author: Claude (task-93)
Created: 2026-01-16
"""

import sys
import os
import subprocess
import json
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import traceback

# Add email API to path
sys.path.insert(0, '/Users/djm/claude-projects/src/tools/email')
from consolidated_email_api import send_email_to_david

# Backup notification channel (ntfy.sh - free, no signup)
# Topic is private via obscure name
NTFY_TOPIC = "djm-claude-cron-alerts-x7k9m2"
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"

# Configuration
CLAUDE_PROJECTS_ROOT = Path(os.environ.get('CLAUDE_PROJECTS_ROOT', '/Users/djm/claude-projects'))
LOGS_DIR = CLAUDE_PROJECTS_ROOT / 'logs'
FAILURE_LOG = LOGS_DIR / 'cron_failures.log'
STATE_FILE = LOGS_DIR / 'cron_alerter_state.json'

# Jobs to monitor with their expected schedules
# Updated 2026-02-02 - Fixed log paths to match actual script output locations
# Supports both 'log' (single file) and 'log_dir'+'log_pattern' (timestamped files)
MONITORED_JOBS = {
    'weekly_report': {
        # Reports don't write logs - disable staleness check, rely on wrapper alerts
        'log': None,
        'schedule': 'weekly',  # Fridays at 5 PM
        'max_age_hours': 168 + 24,
    },
    'monthly_report': {
        # Reports don't write logs - disable staleness check, rely on wrapper alerts
        'log': None,
        'schedule': 'monthly',  # 1st of month at 9 AM
        'max_age_hours': 31 * 24 + 24,
    },
    # REMOVED 2026-03-15: gmail_token_refresh — cron disabled, token file missing since 2026-03-11.
    # Re-add after manual Gmail OAuth reauth.
    # REMOVED 2026-04-21: youtube_intelligence — "unified_pipeline" cron no longer in crontab
    # (last pipeline log Apr 5). Active YouTube jobs are youtube_likes + youtube_knowledge_scanner.
    # If a weekly pipeline is restored, re-enable this monitor.
    'youtube_likes': {
        # Uses timestamped logs: logs/youtube_intelligence/likes_heartbeat_*.log
        'log_dir': LOGS_DIR / 'youtube_intelligence',
        'log_pattern': 'likes_heartbeat_*.log',
        'schedule': '2x daily',  # 7am, 2pm (updated 2026-04-13, was 4x)
        'max_age_hours': 24,  # Widened 2026-04-21 — 18h was tight for Mac-sleep overnight
        'state_file': LOGS_DIR / 'state' / 'youtube_likes.json',
    },
    # REMOVED 2026-04-10: youtube_newsletter_evening — cron entry never existed,
    # was generating false-positive alerts every 26h. Morning newsletter is the
    # only active newsletter cron.
    # REMOVED 2026-04-21: youtube_newsletter_morning — no crontab entry for newsletter generator.
    # Last newsletter log Apr 16. If restored, re-enable with correct log_pattern.
    # REMOVED 2026-03-15: slo_check and dashboard_update — scripts never existed,
    # cron entries disabled 2026-03-14 (task-129 audit). Were generating stale-log alerts.
    'memory_maintenance': {
        # Uses timestamped logs: .claude/memory/logs/cron_*.log
        # EDGA-957: Fixed — cron runs at 11 PM, alerter path was correct, crontab was stale (had 2 AM)
        'log_dir': CLAUDE_PROJECTS_ROOT / '.claude' / 'memory' / 'logs',
        'log_pattern': 'cron_*.log',
        'schedule': 'daily',  # 11 PM daily (was 2 AM, moved 2026-05-04 to avoid Mac sleep)
        'max_age_hours': 50,  # EDGA-957: 30h -> 50h — tolerate Mac sleep/wake cycles
        'state_file': LOGS_DIR / 'state' / 'memory_maintenance.json',
    },
    'rss_triage': {
        # Updated 2026-05-04: rss_ingest retired, rss-triage is canonical
        'log_dir': LOGS_DIR / 'rss-triage',
        'log_pattern': '*.log',
        'schedule': 'every 2 hours',
        'max_age_hours': 10,  # Mac sleep causes 6-8h gaps overnight; tolerate gracefully
    },
    # REMOVED 2026-05-01: tartanism_keepalive — Supabase keepalive retired after
    # Tartanism migrated to self-hosted PostgreSQL. Crontab entry is commented out
    # (REF: EDGA-760); keeping this monitor enabled creates false-positive stale/failure alerts.
    'cleanup_quarantine': {
        # Weekly quarantine of stale files
        # EDGA-957: check_log_content enabled — parses timestamps inside log, not just file mtime
        # EDGA-957: Moved cron from 3 AM to 9 PM Sunday (Mac sleeps through 3 AM window)
        'log': LOGS_DIR / 'safe_cleanup.log',
        'log_pattern': r'\[\d{4}-\d{2}-\d{2}',  # Regex to find timestamps like [2026-04-19
        'check_log_content': True,  # Parse timestamps inside log, not file mtime
        'schedule': 'weekly',  # Sunday 9 PM (was 3 AM, moved 2026-05-04 to avoid Mac sleep)
        'max_age_hours': 168 + 72,  # EDGA-957: 1 week + 72h grace — tolerate missed windows
        'state_file': LOGS_DIR / 'state' / 'cleanup_quarantine.json',  # EDGA-1809 — future map
    },
    'cleanup_purge': {
        # Monthly purge of old quarantine
        'log': LOGS_DIR / 'safe_cleanup.log',
        'schedule': 'monthly',  # 1st of month 4 AM
        'max_age_hours': 31 * 24 + 24,  # ~1 month + 1 day grace
    },
    'weekly_health_summary': {
        # Weekly health report
        'log': None,  # Sends email, no persistent log
        'schedule': 'weekly',  # Sundays 9 AM
        'max_age_hours': 168 + 24,
    },
}

# Disk space thresholds
DISK_WARNING_GB = 50
DISK_CRITICAL_GB = 20

# Self-diagnosis patterns: (regex_pattern, likely_cause, suggested_fix)
DIAGNOSIS_PATTERNS = [
    # Variable expansion issues (like the Jan 29-Feb 1 incident)
    (r'\$[A-Z_]+.*: No such file or directory',
     'Variable not expanding in cron environment',
     'Use literal/absolute paths instead of $VAR references in crontab. Cron does not expand nested variables.'),
    (r'No such file or directory: \$',
     'Variable not expanding in cron environment',
     'Use literal/absolute paths instead of $VAR references in crontab.'),

    # Permission issues
    (r'Permission denied',
     'Script or file lacks execute permissions',
     'Run: chmod +x /path/to/script.sh'),
    (r'Operation not permitted',
     'System-level permission restriction',
     'Check file ownership and macOS security settings (Full Disk Access).'),

    # Python/venv issues
    (r'ModuleNotFoundError: No module named',
     'Python module not installed or wrong venv',
     'Verify PYTHONPATH and venv activation. Run: source .venv/bin/activate && pip install <module>'),
    (r'No module named \'([^\']+)\'',
     'Missing Python dependency',
     'Install the missing module: pip install \\1'),
    (r'python3?: .*No such file or directory',
     'Python interpreter not found',
     'Use absolute path to Python: /Users/djm/claude-projects/.venv/bin/python'),

    # Script/file missing
    (r'No such file or directory: (/[^\s]+)',
     'Script or file has been moved or deleted',
     'Verify the file exists at the specified path. Check for typos or recent file moves.'),
    (r'command not found',
     'Command not in PATH for cron environment',
     'Use absolute path to the command, or add its directory to PATH in crontab.'),

    # Network/API issues
    (r'Connection refused|Connection timed out',
     'Network connectivity or service unavailable',
     'Check if the target service is running. Verify network connectivity.'),
    (r'SSL: CERTIFICATE_VERIFY_FAILED',
     'SSL certificate verification failed',
     'Update certificates or check system time. Run: pip install --upgrade certifi'),

    # OAuth/API key issues
    (r'invalid_grant|token.*expired|unauthorized',
     'OAuth token expired or invalid',
     'Re-authenticate the service. Check if API keys are still valid.'),
    (r'rate.?limit|too many requests',
     'API rate limit exceeded',
     'Reduce request frequency or implement exponential backoff.'),

    # Timeout issues
    (r'timed? ?out|timeout',
     'Operation took too long',
     'Increase timeout value or optimize the slow operation.'),
]


class CronFailureAlerter:
    """Monitor cron jobs and send alerts on failures"""

    def __init__(self):
        self.logs_dir = LOGS_DIR
        self.failure_log = FAILURE_LOG
        self.state_file = STATE_FILE
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """Load persistent state from disk"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load state file: {e}")
        return {'last_alerts': {}, 'failure_count': {}}

    def _save_state(self):
        """Save state to disk"""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            print(f"Warning: Failed to save state: {e}")

    def diagnose_error(self, error_text: str) -> Optional[Tuple[str, str]]:
        """
        Analyze error text and return (likely_cause, suggested_fix) if pattern matches.
        Returns None if no diagnosis available.
        """
        import re
        for pattern, cause, fix in DIAGNOSIS_PATTERNS:
            if re.search(pattern, error_text, re.IGNORECASE):
                # Handle capture groups in fix string
                match = re.search(pattern, error_text, re.IGNORECASE)
                if match and match.groups():
                    try:
                        fix = re.sub(r'\\(\d+)', lambda m: match.group(int(m.group(1))), fix)
                    except Exception:
                        pass  # Use original fix if substitution fails
                return (cause, fix)
        return None

    def get_recent_failures(self, hours: int = 24) -> List[Dict]:
        """Get failures from the last N hours"""
        failures = []
        cutoff = datetime.now() - timedelta(hours=hours)

        if not self.failure_log.exists():
            return failures

        try:
            with open(self.failure_log, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        ts = datetime.fromisoformat(entry['timestamp'])
                        if ts > cutoff:
                            failures.append(entry)
                    except (json.JSONDecodeError, KeyError):
                        continue
        except Exception as e:
            print(f"Warning: Error reading failure log: {e}")

        return failures

    def detect_anomaly(self) -> Optional[str]:
        """
        Detect if we have a systemic issue (>50% of jobs failing).
        Returns anomaly description if detected, None otherwise.
        """
        recent_failures = self.get_recent_failures(hours=24)
        if not recent_failures:
            return None

        # Count unique failed jobs
        failed_jobs = set(f['job'] for f in recent_failures)
        total_jobs = len(MONITORED_JOBS)
        failure_rate = len(failed_jobs) / total_jobs

        if failure_rate > 0.5:
            return (
                f"SYSTEMIC ISSUE DETECTED: {len(failed_jobs)}/{total_jobs} jobs "
                f"({failure_rate:.0%}) failed in last 24h. "
                f"Failed jobs: {', '.join(sorted(failed_jobs))}"
            )
        return None

    def _should_alert(self, job_name: str, cooldown_hours: int = 24) -> bool:
        """Check if we should send an alert (rate limiting)"""
        last_alert = self.state['last_alerts'].get(job_name)
        if not last_alert:
            return True

        last_alert_time = datetime.fromisoformat(last_alert)
        if datetime.now() - last_alert_time > timedelta(hours=cooldown_hours):
            return True

        return False

    def _record_alert(self, job_name: str):
        """Record that we sent an alert"""
        self.state['last_alerts'][job_name] = datetime.now().isoformat()
        self.state['failure_count'][job_name] = self.state['failure_count'].get(job_name, 0) + 1
        self._save_state()

    def _log_failure(self, job_name: str, error: str, exit_code: Optional[int] = None):
        """Log failure to persistent log file"""
        try:
            self.failure_log.parent.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().isoformat()
            log_entry = {
                'timestamp': timestamp,
                'job': job_name,
                'error': error,
                'exit_code': exit_code,
            }

            with open(self.failure_log, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"Warning: Failed to write to failure log: {e}")

    def _send_ntfy_backup(self, job_name: str, error: str) -> bool:
        """Send backup notification via ntfy.sh (in case email fails)"""
        try:
            message = f"🚨 CRON FAILED: {job_name}\n{error[:200]}"
            data = message.encode('utf-8')

            req = urllib.request.Request(
                NTFY_URL,
                data=data,
                headers={
                    'Title': f'Cron Failed: {job_name}',
                    'Priority': 'high',
                    'Tags': 'warning,cron',
                }
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    print(f"✅ Backup ntfy alert sent for {job_name}")
                    return True
        except Exception as e:
            print(f"⚠️ Backup ntfy alert failed: {e}")
        return False

    def send_failure_alert(
        self,
        job_name: str,
        error: str,
        exit_code: Optional[int] = None,
        log_tail: Optional[str] = None,
    ) -> bool:
        """Send email alert for cron job failure"""

        # Rate limiting
        if not self._should_alert(job_name):
            print(f"Skipping alert for {job_name} (cooldown period)")
            return False

        # Log the failure
        self._log_failure(job_name, error, exit_code)

        # Build email content
        subject = f"🚨 Cron Job Failed: {job_name}"

        body_parts = [
            f"<h2>Cron Job Failure Alert</h2>",
            f"<p><strong>Job:</strong> {job_name}</p>",
            f"<p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
            f"<p><strong>Error:</strong> {error}</p>",
        ]

        if exit_code is not None:
            body_parts.append(f"<p><strong>Exit Code:</strong> {exit_code}</p>")

        # Add log tail if available
        if log_tail:
            body_parts.extend([
                "<h3>Recent Log Output</h3>",
                "<pre style='background-color: #f5f5f5; padding: 10px; border-radius: 5px;'>",
                log_tail,
                "</pre>",
            ])

        # Add failure history
        failure_count = self.state['failure_count'].get(job_name, 0)
        if failure_count > 0:
            body_parts.append(
                f"<p><em>Note: This job has failed {failure_count} time(s) recently.</em></p>"
            )

        # Self-diagnosis
        diagnosis = self.diagnose_error(error)
        if diagnosis:
            cause, fix = diagnosis
            body_parts.extend([
                "<h3>🔍 Auto-Diagnosis</h3>",
                f"<p><strong>Likely Cause:</strong> {cause}</p>",
                f"<p><strong>Suggested Fix:</strong> <code>{fix}</code></p>",
            ])

        # Add recommendations
        body_parts.extend([
            "<h3>Recommended Actions</h3>",
            "<ol>",
        ])

        if diagnosis:
            body_parts.append(f"<li><strong>Try the suggested fix above first</strong></li>")

        body_parts.extend([
            "<li>Check the log file for detailed error messages</li>",
            "<li>Verify the cron job is properly configured in crontab</li>",
            "<li>Ensure all dependencies and environment variables are set</li>",
            "<li>Review recent system changes that might affect this job</li>",
            "</ol>",
            "<hr>",
            "<p><small>This alert was sent by the Cron Failure Alerting System (task-93, enhanced task-130).</small></p>",
            f"<p><small>Failure log: {self.failure_log}</small></p>",
        ])

        body = '\n'.join(body_parts)

        # Try primary channel (email)
        email_success = False
        try:
            message_id = send_email_to_david(subject, body, use_html=True)
            if message_id:
                self._record_alert(job_name)
                print(f"✅ Email alert sent for {job_name}: {message_id}")
                email_success = True
            else:
                print(f"❌ Failed to send email alert for {job_name}")
        except Exception as e:
            print(f"❌ Error sending email alert: {e}")
            traceback.print_exc()

        # Always try backup channel (ntfy.sh) for redundancy
        # This ensures we get notified even if email fails
        ntfy_success = self._send_ntfy_backup(job_name, error)

        # Return True if at least one channel succeeded
        if email_success or ntfy_success:
            return True
        else:
            print(f"❌ CRITICAL: All alert channels failed for {job_name}")
            return False

    def wrap_command(self, job_name: str, command: List[str]) -> int:
        """
        Wrap a cron job command with failure detection and alerting.
        Returns the exit code of the wrapped command.
        """
        print(f"Running wrapped cron job: {job_name}")
        print(f"Command: {' '.join(command)}")

        # Determine log file for this job
        log_file = None
        if job_name in MONITORED_JOBS and 'log' in MONITORED_JOBS[job_name]:
            log_file = MONITORED_JOBS[job_name]['log']

        try:
            # Run the command and capture output
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
            )

            exit_code = result.returncode

            # Always log stdout/stderr if we have a log file
            if log_file and (result.stdout or result.stderr):
                try:
                    log_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(log_file, 'a') as f:
                        f.write(f"\n=== {datetime.now().isoformat()} ===\n")
                        if result.stdout:
                            f.write("STDOUT:\n" + result.stdout + "\n")
                        if result.stderr:
                            f.write("STDERR:\n" + result.stderr + "\n")
                except Exception as e:
                    print(f"Warning: Failed to write to log file: {e}")

            # Log outcome to vault
            vault_dir = CLAUDE_PROJECTS_ROOT / 'claude-vault' / '13-Reports' / 'Emails' / 'Sent'
            if exit_code != 0:
                error = f"Command exited with code {exit_code}"
                log_tail = self._get_log_tail(log_file) if log_file else None

                # Include stderr in alert if available
                if result.stderr:
                    error += f"\nStderr: {result.stderr[:500]}"

                self.send_failure_alert(
                    job_name=job_name,
                    error=error,
                    exit_code=exit_code,
                    log_tail=log_tail,
                )
            else:
                # Log success to vault and stdout
                print(f"Cron job '{job_name}' completed successfully (exit 0)")
                try:
                    vault_dir.mkdir(parents=True, exist_ok=True)
                    date_str = datetime.now().strftime('%Y-%m-%d')
                    success_file = vault_dir / f"{date_str}-cron-success-{job_name}.md"
                    stdout_preview = (result.stdout or "")[:500].strip()
                    success_file.write_text(
                        f"# Cron Success: {job_name}\n\n"
                        f"- **Time**: {datetime.now().isoformat()}\n"
                        f"- **Exit code**: 0\n"
                        f"- **Output preview**: {stdout_preview[:200] if stdout_preview else '(no output)'}\n"
                    )
                except Exception:
                    pass  # Don't fail the job over logging

            return exit_code

        except subprocess.TimeoutExpired:
            error = "Command timed out after 1 hour"
            self.send_failure_alert(job_name=job_name, error=error)
            return 124  # Standard timeout exit code

        except Exception as e:
            error = f"Wrapper error: {str(e)}\n{traceback.format_exc()}"
            self.send_failure_alert(job_name=job_name, error=error)
            return 1

    def _get_log_tail(self, log_file: Path, lines: int = 50) -> Optional[str]:
        """Get the last N lines of a log file"""
        if not log_file or not log_file.exists():
            return None

        try:
            result = subprocess.run(
                ['tail', '-n', str(lines), str(log_file)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout if result.returncode == 0 else None
        except Exception:
            return None

    def check_stale_logs(self) -> List[Tuple[str, str]]:
        """
        Check for cron jobs that haven't run recently.
        Returns list of (job_name, reason) tuples for stale jobs.

        Supports three modes:
        - 'log': Single log file path
        - 'log_dir' + 'log_pattern': Directory with timestamped files (glob pattern)
        - 'state_file': State file written by cron-wrapper.sh — preferred mode (EDGA-1809)
          Uses next_expected_run + max_age_hours grace to avoid Mac-sleep false positives.
        """
        stale_jobs = []

        for job_name, config in MONITORED_JOBS.items():
            max_age_hours = config.get('max_age_hours', 24)

            # Mode 1: Log directory with pattern (for timestamped logs)
            if 'log_dir' in config and 'log_pattern' in config:
                log_dir = config['log_dir']
                log_pattern = config['log_pattern']

                if not log_dir.exists():
                    reason = f"Log directory does not exist: {log_dir}"
                    stale_jobs.append((job_name, reason))
                    continue

                # Find most recent matching file
                try:
                    import glob
                    pattern = str(log_dir / log_pattern)
                    matching_files = glob.glob(pattern)

                    if not matching_files:
                        reason = f"No log files matching {log_pattern} in {log_dir}"
                        stale_jobs.append((job_name, reason))
                        continue

                    # Get the most recently modified file
                    most_recent = max(matching_files, key=lambda f: Path(f).stat().st_mtime)
                    mtime = datetime.fromtimestamp(Path(most_recent).stat().st_mtime)
                    age_hours = (datetime.now() - mtime).total_seconds() / 3600

                    if age_hours > max_age_hours:
                        reason = (
                            f"Most recent log ({Path(most_recent).name}) is {age_hours:.1f} hours old "
                            f"(expected: {config['schedule']})"
                        )
                        stale_jobs.append((job_name, reason))
                except Exception as e:
                    reason = f"Error checking log directory: {e}"
                    stale_jobs.append((job_name, reason))
                continue

            # Mode 3: State file (EDGA-1809 — state files replace log-mtime heuristics)
            # When state files are written by cron-wrapper.sh, use them as the authoritative
            # signal instead of log-file mtime. This eliminates Mac-sleep false positives
            # because the wrapper writes next_expected_run on every successful exit.
            if 'state_file' in config:
                state_path = config['state_file']
                if state_path.exists():
                    try:
                        import json as _json
                        with open(state_path, 'r') as _swf:
                            _sdata = _json.load(_swf)
                        _status = _sdata.get('status', '')
                        _ner = _sdata.get('next_expected_run')
                        _now = datetime.utcnow()

                        if _status == 'running':
                            # Wrapper reported running — not stale by definition
                            continue

                        if _ner:
                            try:
                                _ner_dt = datetime.fromisoformat(_ner.rstrip('Z'))
                                _grace = timedelta(hours=max_age_hours)
                                _deadline = _ner_dt + _grace
                                if _now < _deadline:
                                    # Still within grace period past next_expected_run — not stale
                                    continue
                                else:
                                    # Past next_expected_run + grace — genuinely overdue
                                    reason = (
                                        f"State file: past next_expected_run "
                                        f"({_ner_dt.isoformat()}) + {max_age_hours}h grace (now: {_now.isoformat()[:19]})"
                                    )
                                    stale_jobs.append((job_name, reason))
                            except (ValueError, TypeError):
                                pass  # Can't parse next_expected_run — fall through to log check
                    except Exception:
                        pass  # State file unreadable — fall through to log check
            if 'log' not in config or not config['log']:
                continue

            log_file = config['log']

            # Check if log file exists
            if not log_file.exists():
                reason = f"Log file does not exist: {log_file}"
                stale_jobs.append((job_name, reason))
                continue

            # Check log file age
            try:
                # EDGA-957: Support checking log content timestamps instead of file mtime
                # This handles jobs that run but produce no work (file not modified,
                # but log entries still written)
                if config.get('check_log_content') and 'log_pattern' in config:
                    import re
                    log_pattern = re.compile(config['log_pattern'])
                    cutoff = datetime.now() - timedelta(hours=max_age_hours)
                    most_recent_entry = None
                    
                    with open(log_file, 'r') as f:
                        for line in f:
                            match = log_pattern.search(line)
                            if match:
                                try:
                                    # Parse timestamp like [2026-04-19 13:00:04]
                                    ts_str = match.group(0).strip('[]')
                                    ts = datetime.strptime(ts_str, '%Y-%m-%d')
                                    if most_recent_entry is None or ts > most_recent_entry:
                                        most_recent_entry = ts
                                except ValueError:
                                    continue
                    
                    if most_recent_entry is None:
                        reason = f"No timestamped entries found in log file: {log_file}"
                        stale_jobs.append((job_name, reason))
                        continue
                    
                    age_hours = (datetime.now() - most_recent_entry).total_seconds() / 3600
                    if age_hours > max_age_hours:
                        reason = (
                            f"No log entries in {age_hours:.1f} hours "
                            f"(expected: {config['schedule']})"
                        )
                        stale_jobs.append((job_name, reason))
                else:
                    # Original behavior: check file mtime
                    mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    age_hours = (datetime.now() - mtime).total_seconds() / 3600

                    if age_hours > max_age_hours:
                        reason = (
                            f"Log file not updated in {age_hours:.1f} hours "
                            f"(expected: {config['schedule']})"
                        )
                        stale_jobs.append((job_name, reason))
            except Exception as e:
                reason = f"Error checking log file: {e}"
                stale_jobs.append((job_name, reason))

        return stale_jobs

    def check_disk_space(self) -> Optional[Tuple[str, int]]:
        """
        Check available disk space.
        Returns (level, available_gb) if below threshold, None if OK.
        Level is 'warning' or 'critical'.
        """
        try:
            result = subprocess.run(
                ["df", "-g", "/"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) >= 2:
                    parts = lines[1].split()
                    available_gb = int(parts[3])

                    if available_gb < DISK_CRITICAL_GB:
                        return ("critical", available_gb)
                    elif available_gb < DISK_WARNING_GB:
                        return ("warning", available_gb)
        except Exception as e:
            print(f"Error checking disk space: {e}")
        return None

    def _get_vault_health(self) -> Optional[Dict]:
        """Get Obsidian vault health metrics via CLI. Returns None if Obsidian not running."""
        obsidian_cli = Path.home() / '.local' / 'bin' / 'obsidian'
        if not obsidian_cli.exists():
            return None
        # Check if Obsidian is running
        try:
            result = subprocess.run(["pgrep", "-x", "Obsidian"], capture_output=True, timeout=3)
            if result.returncode != 0:
                return None
        except Exception:
            return None

        metrics = {}
        cmds = {
            'files': [str(obsidian_cli), 'files', 'total'],
            'unresolved': [str(obsidian_cli), 'unresolved', 'total'],
            'orphans': [str(obsidian_cli), 'orphans', 'total'],
            'plugins': [str(obsidian_cli), 'plugins', 'total'],
        }
        for key, cmd in cmds.items():
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                # Output goes to stdout; filter the "Loading" and "out of date" lines
                lines = [l for l in result.stdout.strip().split('\n')
                         if l and not l.startswith('2026') and 'out of date' not in l]
                if lines:
                    metrics[key] = lines[-1].strip()
            except Exception:
                pass
        return metrics if metrics else None

    def send_stale_job_alerts(self):
        """Check for stale logs, disk space, anomalies, and send alerts"""
        stale_jobs = self.check_stale_logs()
        disk_status = self.check_disk_space()
        anomaly = self.detect_anomaly()

        alerts_sent = 0

        # Check for systemic anomaly first - send ONE escalation instead of per-job spam
        if anomaly and self._should_alert('system_anomaly', cooldown_hours=12):
            self._send_escalation_alert(anomaly, stale_jobs)
            alerts_sent += 1
            print(f"🚨 ESCALATION: {anomaly}")
            # Don't send individual alerts for anomaly - just the escalation
            return

        # Check disk space
        if disk_status:
            level, available_gb = disk_status
            job_name = f"disk_space_{level}"
            if self._should_alert(job_name, cooldown_hours=6):
                error_msg = f"Disk space {level.upper()}: Only {available_gb}GB available"
                self.send_failure_alert(
                    job_name="system_disk_space",
                    error=error_msg,
                )
                alerts_sent += 1
                print(f"🚨 {error_msg}")

        if not stale_jobs and not disk_status:
            print("✅ All monitored cron jobs are current")
            print("✅ Disk space OK")
            return

        if stale_jobs:
            print(f"⚠️  Found {len(stale_jobs)} stale job(s)")

        for job_name, reason in stale_jobs:
            if self._should_alert(job_name, cooldown_hours=24):
                self.send_failure_alert(
                    job_name=job_name,
                    error=f"Job appears to be stale: {reason}",
                )
                alerts_sent += 1

        print(f"Sent {alerts_sent} alert(s)")

    def _send_escalation_alert(self, anomaly: str, stale_jobs: List[Tuple[str, str]]):
        """Send a single escalation alert for systemic issues"""
        subject = "🚨🚨 SYSTEM HEALTH CRITICAL - Multiple Cron Jobs Failing"

        body_parts = [
            "<h2 style='color: red;'>⚠️ SYSTEMIC ISSUE DETECTED</h2>",
            f"<p><strong>{anomaly}</strong></p>",
            "<p>This is NOT a single job failure - multiple jobs are affected.</p>",
            "<h3>🔍 Common Systemic Causes</h3>",
            "<ul>",
            "<li><strong>Variable expansion:</strong> Crontab using $VAR references that don't expand</li>",
            "<li><strong>Mac sleep:</strong> System was asleep during scheduled times</li>",
            "<li><strong>Disk full:</strong> No space for log files or temp data</li>",
            "<li><strong>Python/venv broken:</strong> Virtual environment corrupted</li>",
            "<li><strong>Network down:</strong> No connectivity for API calls</li>",
            "</ul>",
        ]

        if stale_jobs:
            body_parts.extend([
                "<h3>Affected Jobs</h3>",
                "<table border='1' style='border-collapse: collapse;'>",
                "<tr><th style='padding: 5px;'>Job</th><th style='padding: 5px;'>Issue</th></tr>",
            ])
            for job_name, reason in stale_jobs:
                body_parts.append(
                    f"<tr><td style='padding: 5px;'>{job_name}</td>"
                    f"<td style='padding: 5px;'>{reason[:80]}</td></tr>"
                )
            body_parts.append("</table>")

        body_parts.extend([
            "<h3>Recommended Actions</h3>",
            "<ol>",
            "<li><strong>Check crontab:</strong> <code>crontab -l</code> - look for $VAR references</li>",
            "<li><strong>Check mail:</strong> <code>tail -100 /var/mail/$USER</code> - see cron errors</li>",
            "<li><strong>Check disk:</strong> <code>df -h</code></li>",
            "<li><strong>Test a job manually:</strong> Run one job directly to see errors</li>",
            "</ol>",
            "<hr>",
            "<p><small>Escalation alert from Cron Health Monitoring (task-130)</small></p>",
        ])

        body = '\n'.join(body_parts)

        try:
            message_id = send_email_to_david(subject, body, use_html=True)
            if message_id:
                self._record_alert('system_anomaly')
                print(f"✅ Escalation alert sent: {message_id}")
            else:
                print("❌ Failed to send escalation alert")
                self._send_ntfy_backup('SYSTEM_CRITICAL', anomaly)
        except Exception as e:
            print(f"❌ Error sending escalation: {e}")
            self._send_ntfy_backup('SYSTEM_CRITICAL', anomaly)

    def send_test_alert(self) -> bool:
        """Send a test alert to verify email system is working"""
        subject = "✅ Cron Alerting System Test"
        body = """
        <h2>Cron Alerting System Test</h2>
        <p>This is a test email to verify the cron failure alerting system is working correctly.</p>
        <h3>System Status</h3>
        <ul>
        <li>Email API: Working ✓</li>
        <li>Alerting Script: Working ✓</li>
        <li>Gmail Integration: Working ✓</li>
        </ul>
        <p>The cron failure alerting system is operational and ready to monitor your cron jobs.</p>
        <hr>
        <p><small>Test sent by Cron Failure Alerting System (task-93)</small></p>
        """

        try:
            message_id = send_email_to_david(subject, body, use_html=True)
            if message_id:
                print(f"✅ Test alert sent successfully: {message_id}")
                return True
            else:
                print("❌ Test alert failed")
                return False
        except Exception as e:
            print(f"❌ Error sending test alert: {e}")
            traceback.print_exc()
            return False

    def send_weekly_summary(self) -> bool:
        """
        Send a weekly health summary email showing job success/failure rates.
        Designed to be run every Sunday morning.
        """
        stale_jobs = self.check_stale_logs()
        recent_failures = self.get_recent_failures(hours=168)  # Last 7 days
        disk_status = self.check_disk_space()

        # Categorize jobs
        stale_job_names = set(j[0] for j in stale_jobs)
        failed_job_names = set(f['job'] for f in recent_failures)

        healthy_jobs = []
        degraded_jobs = []  # Had failures but currently running
        failing_jobs = []   # Currently stale/not running

        for job_name in MONITORED_JOBS.keys():
            if job_name in stale_job_names:
                failing_jobs.append(job_name)
            elif job_name in failed_job_names:
                degraded_jobs.append(job_name)
            else:
                healthy_jobs.append(job_name)

        total_jobs = len(MONITORED_JOBS)
        healthy_count = len(healthy_jobs)
        degraded_count = len(degraded_jobs)
        failing_count = len(failing_jobs)

        # Build subject
        if failing_count == 0 and degraded_count == 0:
            subject = f"✅ Weekly Cron Health - All {total_jobs} jobs healthy"
            status_emoji = "✅"
        elif failing_count == 0:
            subject = f"⚠️ Weekly Cron Health - {healthy_count}/{total_jobs} healthy, {degraded_count} degraded"
            status_emoji = "⚠️"
        else:
            subject = f"🚨 Weekly Cron Health - {failing_count} jobs failing"
            status_emoji = "🚨"

        # Build body
        body_parts = [
            f"<h2>{status_emoji} Weekly Cron Health Report</h2>",
            f"<p><strong>Period:</strong> {(datetime.now() - timedelta(days=7)).strftime('%b %d')} - {datetime.now().strftime('%b %d, %Y')}</p>",
            "<hr>",
            "<h3>Summary</h3>",
            "<table border='1' style='border-collapse: collapse; width: 100%;'>",
            "<tr><th style='padding: 8px; text-align: left;'>Status</th><th style='padding: 8px;'>Count</th><th style='padding: 8px;'>Jobs</th></tr>",
        ]

        # Healthy row
        body_parts.append(
            f"<tr style='background-color: #d4edda;'>"
            f"<td style='padding: 8px;'>✅ Healthy</td>"
            f"<td style='padding: 8px; text-align: center;'>{healthy_count}</td>"
            f"<td style='padding: 8px;'>{', '.join(sorted(healthy_jobs)[:5])}{'...' if len(healthy_jobs) > 5 else ''}</td></tr>"
        )

        # Degraded row
        if degraded_count > 0:
            body_parts.append(
                f"<tr style='background-color: #fff3cd;'>"
                f"<td style='padding: 8px;'>⚠️ Degraded</td>"
                f"<td style='padding: 8px; text-align: center;'>{degraded_count}</td>"
                f"<td style='padding: 8px;'>{', '.join(sorted(degraded_jobs))}</td></tr>"
            )

        # Failing row
        if failing_count > 0:
            body_parts.append(
                f"<tr style='background-color: #f8d7da;'>"
                f"<td style='padding: 8px;'>❌ Failing</td>"
                f"<td style='padding: 8px; text-align: center;'>{failing_count}</td>"
                f"<td style='padding: 8px;'>{', '.join(sorted(failing_jobs))}</td></tr>"
            )

        body_parts.append("</table>")

        # Disk space
        body_parts.append("<h3>System Health</h3>")
        if disk_status:
            level, available_gb = disk_status
            body_parts.append(f"<p>💾 Disk Space: <strong style='color: {'red' if level == 'critical' else 'orange'};'>{level.upper()}</strong> - {available_gb}GB available</p>")
        else:
            body_parts.append("<p>💾 Disk Space: ✅ OK</p>")

        # Obsidian Vault Health (via CLI, requires Obsidian running)
        vault_health = self._get_vault_health()
        if vault_health:
            body_parts.append("<h3>Obsidian Vault</h3>")
            body_parts.append(
                f"<table border='1' style='border-collapse: collapse;'>"
                f"<tr><td style='padding: 5px;'>📁 Files</td><td style='padding: 5px; text-align: right;'>{vault_health.get('files', '?')}</td></tr>"
                f"<tr><td style='padding: 5px;'>🔗 Unresolved Links</td><td style='padding: 5px; text-align: right;'>{vault_health.get('unresolved', '?')}</td></tr>"
                f"<tr><td style='padding: 5px;'>🏝️ Orphans</td><td style='padding: 5px; text-align: right;'>{vault_health.get('orphans', '?')}</td></tr>"
                f"<tr><td style='padding: 5px;'>🔌 Plugins</td><td style='padding: 5px; text-align: right;'>{vault_health.get('plugins', '?')}</td></tr>"
                f"</table>"
            )

        # Failure details if any
        if recent_failures:
            body_parts.extend([
                "<h3>Recent Failures (Last 7 Days)</h3>",
                "<table border='1' style='border-collapse: collapse; width: 100%;'>",
                "<tr><th style='padding: 5px;'>Time</th><th style='padding: 5px;'>Job</th><th style='padding: 5px;'>Error</th></tr>",
            ])
            # Show last 10 failures
            for failure in recent_failures[-10:]:
                ts = datetime.fromisoformat(failure['timestamp']).strftime('%m/%d %H:%M')
                error_short = failure.get('error', 'Unknown')[:50]
                body_parts.append(
                    f"<tr><td style='padding: 5px;'>{ts}</td>"
                    f"<td style='padding: 5px;'>{failure['job']}</td>"
                    f"<td style='padding: 5px;'>{error_short}</td></tr>"
                )
            body_parts.append("</table>")

        # Quick actions
        body_parts.extend([
            "<h3>Quick Commands</h3>",
            "<pre style='background-color: #f5f5f5; padding: 10px;'>",
            "# Check crontab\ncrontab -l | grep -v '^#'",
            "\n# See recent cron mail\ntail -50 /var/mail/$USER",
            "\n# View failure log\ntail -20 /Users/djm/claude-projects/logs/cron_failures.log",
            "</pre>",
            "<hr>",
            "<p><small>Weekly summary from Cron Health Monitoring (task-130). Sent every Sunday 9 AM.</small></p>",
        ])

        body = '\n'.join(body_parts)

        try:
            message_id = send_email_to_david(subject, body, use_html=True)
            if message_id:
                print(f"✅ Weekly summary sent: {message_id}")
                return True
            else:
                print("❌ Failed to send weekly summary")
                return False
        except Exception as e:
            print(f"❌ Error sending weekly summary: {e}")
            traceback.print_exc()
            return False


def main():
    parser = argparse.ArgumentParser(
        description='Cron Job Failure Alerting System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Wrap a cron job with alerting:
  cron_failure_alerter.py --wrap "youtube_intelligence" -- /path/to/script.sh

  # Check for stale logs and send alerts:
  cron_failure_alerter.py --check-logs

  # Send a test alert:
  cron_failure_alerter.py --test
        """,
    )

    parser.add_argument(
        '--wrap',
        metavar='JOB_NAME',
        help='Wrap a command with failure alerting',
    )
    parser.add_argument(
        '--check-logs',
        action='store_true',
        help='Check for stale log files and send alerts',
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Send a test alert',
    )
    parser.add_argument(
        '--weekly-summary',
        action='store_true',
        help='Send weekly health summary email',
    )
    parser.add_argument(
        '--diagnose',
        metavar='ERROR_TEXT',
        help='Diagnose an error message and suggest fixes',
    )
    parser.add_argument(
        'command',
        nargs='*',
        help='Command to wrap (use after --)',
    )

    args = parser.parse_args()

    alerter = CronFailureAlerter()

    # Handle different modes
    if args.test:
        success = alerter.send_test_alert()
        sys.exit(0 if success else 1)

    elif args.weekly_summary:
        success = alerter.send_weekly_summary()
        sys.exit(0 if success else 1)

    elif args.diagnose:
        diagnosis = alerter.diagnose_error(args.diagnose)
        if diagnosis:
            cause, fix = diagnosis
            print(f"🔍 Diagnosis:")
            print(f"   Likely Cause: {cause}")
            print(f"   Suggested Fix: {fix}")
        else:
            print("❓ No diagnosis available for this error pattern")
        sys.exit(0)

    elif args.check_logs:
        alerter.send_stale_job_alerts()
        sys.exit(0)

    elif args.wrap:
        if not args.command:
            print("Error: --wrap requires a command to execute")
            print("Usage: --wrap JOB_NAME -- command args")
            sys.exit(1)

        exit_code = alerter.wrap_command(args.wrap, args.command)
        sys.exit(exit_code)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
