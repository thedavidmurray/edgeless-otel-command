#!/usr/bin/env python3
"""RLHF (Reinforcement Learning from Human Feedback) Tracker

Tracks application outcomes and feedback signals to improve job targeting.
"""

import sqlite3
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import logging

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from streamlit_app.common import DB_PATH

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RLHFTracker:
    """Tracks RLHF signals and application outcomes for learning."""

    def __init__(self, db_path: str = None):
        """Initialize the RLHF tracker."""
        self.db_path = db_path or DB_PATH

    def add_signal(
        self,
        job_id: str,
        signal_type: str,
        signal_value: Dict,
        confidence: float = 1.0,
        weight: float = 1.0,
    ) -> bool:
        """Add an RLHF signal to the database.

        Args:
            job_id: Job opportunity ID
            signal_type: Type of signal ('keyword_match', 'application_outcome', 'user_feedback', etc.)
            signal_value: Dictionary containing signal details
            confidence: Confidence in this signal (0.0 to 1.0)
            weight: Weight of this signal in learning

        Returns:
            True if signal was added successfully
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO rlhf_signals (job_id, signal_type, signal_value, confidence, weight)
                VALUES (?, ?, ?, ?, ?)
            """,
                (job_id, signal_type, json.dumps(signal_value), confidence, weight),
            )

            conn.commit()
            logger.info(f"Added RLHF signal: {signal_type} for job {job_id}")
            return True

        except sqlite3.Error as e:
            logger.error(f"Error adding RLHF signal: {e}")
            return False
        finally:
            if "conn" in locals():
                conn.close()

    def track_application_outcome(
        self,
        job_id: str,
        application_id: Optional[int],
        outcome_type: str,
        outcome_value: str = None,
        days_to_outcome: int = None,
    ) -> bool:
        """Track an application outcome.

        Args:
            job_id: Job opportunity ID
            application_id: Application history ID (optional)
            outcome_type: Type of outcome ('applied', 'response', 'interview', 'offer', 'rejection', etc.)
            outcome_value: Additional details about the outcome
            days_to_outcome: Number of days from application to this outcome

        Returns:
            True if outcome was tracked successfully
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Calculate success score based on outcome type
            success_scores = {
                "applied": 0.1,
                "viewed": 0.2,
                "response": 0.5,
                "phone_screen": 0.6,
                "technical_interview": 0.7,
                "onsite_interview": 0.8,
                "final_round": 0.85,
                "offer": 1.0,
                "rejection": 0.0,
                "ghosted": 0.0,
            }

            success_score = success_scores.get(
                outcome_type.lower().replace("-", "_"), 0.1
            )

            cursor.execute(
                """
                INSERT INTO application_outcomes 
                (job_id, application_id, outcome_type, outcome_value, days_to_outcome, success_score)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    job_id,
                    application_id,
                    outcome_type,
                    outcome_value,
                    days_to_outcome,
                    success_score,
                ),
            )

            conn.commit()

            # Also add as an RLHF signal
            signal_value = {
                "outcome_type": outcome_type,
                "outcome_value": outcome_value,
                "days_to_outcome": days_to_outcome,
                "success_score": success_score,
            }

            self.add_signal(job_id, "application_outcome", signal_value, weight=2.0)

            logger.info(f"Tracked application outcome: {outcome_type} for job {job_id}")
            return True

        except sqlite3.Error as e:
            logger.error(f"Error tracking application outcome: {e}")
            return False
        finally:
            if "conn" in locals():
                conn.close()

    def get_job_success_metrics(self, lookback_days: int = 90) -> Dict[str, Any]:
        """Get success metrics for jobs over a time period.

        Args:
            lookback_days: Number of days to look back

        Returns:
            Dictionary with success metrics
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cutoff_date = datetime.now() - timedelta(days=lookback_days)

            # Get overall success rates
            cursor.execute(
                """
                SELECT 
                    COUNT(*) as total_applications,
                    AVG(success_score) as avg_success_score,
                    SUM(CASE WHEN success_score >= 0.5 THEN 1 ELSE 0 END) as positive_responses,
                    SUM(CASE WHEN success_score >= 0.8 THEN 1 ELSE 0 END) as interviews,
                    SUM(CASE WHEN success_score = 1.0 THEN 1 ELSE 0 END) as offers,
                    AVG(days_to_outcome) as avg_response_time
                FROM application_outcomes ao
                WHERE ao.created_at >= ?
            """,
                (cutoff_date,),
            )

            overall_metrics = dict(cursor.fetchone())

            # Get success by company type
            cursor.execute(
                """
                SELECT 
                    cp.company_type,
                    COUNT(*) as applications,
                    AVG(ao.success_score) as avg_success_score
                FROM application_outcomes ao
                JOIN job_opportunities jo ON ao.job_id = jo.id
                LEFT JOIN company_profiles cp ON jo.company = cp.company_name
                WHERE ao.created_at >= ?
                GROUP BY cp.company_type
                ORDER BY avg_success_score DESC
            """,
                (cutoff_date,),
            )

            company_type_metrics = [dict(row) for row in cursor.fetchall()]

            # Get top keywords associated with successful applications
            cursor.execute(
                """
                SELECT 
                    kt.keyword,
                    kt.category,
                    COUNT(*) as frequency,
                    AVG(ao.success_score) as avg_success_score
                FROM keyword_tracking kt
                JOIN application_outcomes ao ON kt.job_id = ao.job_id
                WHERE ao.created_at >= ? AND ao.success_score >= 0.5
                GROUP BY kt.keyword, kt.category
                HAVING COUNT(*) >= 2
                ORDER BY avg_success_score DESC, frequency DESC
                LIMIT 20
            """,
                (cutoff_date,),
            )

            successful_keywords = [dict(row) for row in cursor.fetchall()]

            return {
                "overall": overall_metrics,
                "by_company_type": company_type_metrics,
                "successful_keywords": successful_keywords,
                "period_days": lookback_days,
            }

        except sqlite3.Error as e:
            logger.error(f"Error getting success metrics: {e}")
            return {}
        finally:
            if "conn" in locals():
                conn.close()

    def get_trending_keywords(self, lookback_days: int = 30) -> List[Dict[str, Any]]:
        """Get trending keywords in job descriptions.

        Args:
            lookback_days: Number of days to look back

        Returns:
            List of trending keywords with frequency and success data
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cutoff_date = datetime.now() - timedelta(days=lookback_days)

            cursor.execute(
                """
                SELECT 
                    kt.keyword,
                    kt.category,
                    COUNT(*) as frequency,
                    COUNT(DISTINCT kt.job_id) as unique_jobs,
                    AVG(jo.score) as avg_job_score,
                    COALESCE(AVG(ao.success_score), 0) as avg_success_score,
                    COUNT(ao.id) as applications_count
                FROM keyword_tracking kt
                JOIN job_opportunities jo ON kt.job_id = jo.id
                LEFT JOIN application_outcomes ao ON kt.job_id = ao.job_id
                WHERE kt.created_at >= ?
                GROUP BY kt.keyword, kt.category
                HAVING frequency >= 3
                ORDER BY frequency DESC, avg_success_score DESC
                LIMIT 50
            """,
                (cutoff_date,),
            )

            return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            logger.error(f"Error getting trending keywords: {e}")
            return []
        finally:
            if "conn" in locals():
                conn.close()

    def update_targeting_metrics(self, period: str = "daily") -> bool:
        """Update targeting metrics for the current period.

        Args:
            period: Period type ('daily', 'weekly', 'monthly')

        Returns:
            True if metrics were updated successfully
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            today = datetime.now().date()

            if period == "daily":
                period_start = today
                period_end = today
            elif period == "weekly":
                period_start = today - timedelta(days=today.weekday())
                period_end = period_start + timedelta(days=6)
            elif period == "monthly":
                period_start = today.replace(day=1)
                if today.month == 12:
                    period_end = today.replace(
                        year=today.year + 1, month=1, day=1
                    ) - timedelta(days=1)
                else:
                    period_end = today.replace(
                        month=today.month + 1, day=1
                    ) - timedelta(days=1)

            # Calculate various metrics
            metrics_to_calculate = [
                ("application_rate", "COUNT(*)", "application_outcomes"),
                ("avg_success_score", "AVG(success_score)", "application_outcomes"),
                (
                    "response_rate",
                    "SUM(CASE WHEN success_score >= 0.5 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)",
                    "application_outcomes",
                ),
                (
                    "interview_rate",
                    "SUM(CASE WHEN success_score >= 0.8 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)",
                    "application_outcomes",
                ),
                (
                    "offer_rate",
                    "SUM(CASE WHEN success_score = 1.0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)",
                    "application_outcomes",
                ),
                ("avg_response_time", "AVG(days_to_outcome)", "application_outcomes"),
            ]

            for metric_name, calculation, table in metrics_to_calculate:
                cursor.execute(
                    f"""
                    SELECT {calculation} as value
                    FROM {table}
                    WHERE DATE(created_at) BETWEEN ? AND ?
                """,
                    (period_start, period_end),
                )

                result = cursor.fetchone()
                metric_value = result[0] if result and result[0] is not None else 0.0

                # Insert or update metric
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO targeting_metrics 
                    (metric_name, metric_value, period, period_start, period_end)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (metric_name, metric_value, period, period_start, period_end),
                )

            conn.commit()
            logger.info(f"Updated {period} targeting metrics")
            return True

        except sqlite3.Error as e:
            logger.error(f"Error updating targeting metrics: {e}")
            return False
        finally:
            if "conn" in locals():
                conn.close()

    def learn_pattern(
        self,
        pattern_type: str,
        pattern_description: str,
        pattern_data: Dict,
        success_rate: float,
        sample_size: int,
    ) -> bool:
        """Store a learned pattern for future use.

        Args:
            pattern_type: Type of pattern ('keyword_combo', 'company_trait', etc.)
            pattern_description: Human-readable description
            pattern_data: Dictionary containing pattern details
            success_rate: Success rate of this pattern (0.0 to 1.0)
            sample_size: Number of samples this pattern is based on

        Returns:
            True if pattern was stored successfully
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Calculate confidence level based on sample size
            if sample_size >= 100:
                confidence_level = 0.95
            elif sample_size >= 50:
                confidence_level = 0.85
            elif sample_size >= 20:
                confidence_level = 0.75
            elif sample_size >= 10:
                confidence_level = 0.65
            else:
                confidence_level = 0.5

            cursor.execute(
                """
                INSERT INTO learned_patterns 
                (pattern_type, pattern_description, pattern_data, success_rate, 
                 sample_size, confidence_level)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    pattern_type,
                    pattern_description,
                    json.dumps(pattern_data),
                    success_rate,
                    sample_size,
                    confidence_level,
                ),
            )

            conn.commit()
            logger.info(f"Learned new pattern: {pattern_description}")
            return True

        except sqlite3.Error as e:
            logger.error(f"Error storing learned pattern: {e}")
            return False
        finally:
            if "conn" in locals():
                conn.close()

    def get_active_patterns(
        self, pattern_type: str = None, min_confidence: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Get active learned patterns.

        Args:
            pattern_type: Filter by pattern type (optional)
            min_confidence: Minimum confidence level

        Returns:
            List of active patterns
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            where_clauses = ["is_active = 1", "confidence_level >= ?"]
            params = [min_confidence]

            if pattern_type:
                where_clauses.append("pattern_type = ?")
                params.append(pattern_type)

            query = f"""
                SELECT * FROM learned_patterns
                WHERE {' AND '.join(where_clauses)}
                ORDER BY success_rate DESC, confidence_level DESC
            """

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            logger.error(f"Error getting active patterns: {e}")
            return []
        finally:
            if "conn" in locals():
                conn.close()


def main():
    """Main function for testing the RLHF tracker."""
    tracker = RLHFTracker()

    # Update daily metrics
    print("Updating daily targeting metrics...")
    tracker.update_targeting_metrics("daily")

    # Get success metrics
    print("\nGetting success metrics...")
    metrics = tracker.get_job_success_metrics()
    print(f"Overall metrics: {metrics.get('overall', {})}")

    # Get trending keywords
    print("\nGetting trending keywords...")
    trending = tracker.get_trending_keywords()
    for keyword_data in trending[:10]:
        print(
            f"  {keyword_data['keyword']} ({keyword_data['category']}): "
            f"{keyword_data['frequency']} jobs, "
            f"success rate: {keyword_data['avg_success_score']:.2f}"
        )


if __name__ == "__main__":
    main()
