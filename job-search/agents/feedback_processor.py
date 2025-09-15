#!/usr/bin/env python3
"""Feedback Processor Agent

Processes application outcomes and user feedback to create a learning loop
that improves job targeting and scoring over time.
"""

import sqlite3
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import logging
from collections import defaultdict
import statistics

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from streamlit_app.common import DB_PATH
from agents.rlhf_tracker import RLHFTracker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FeedbackProcessor:
    """Processes feedback to improve job targeting and scoring."""

    def __init__(self, db_path: str = None):
        """Initialize the feedback processor."""
        self.db_path = db_path or DB_PATH
        self.rlhf_tracker = RLHFTracker(self.db_path)

        # Define learning thresholds
        self.min_sample_size = 5  # Minimum samples needed to learn a pattern
        self.confidence_threshold = (
            0.7  # Minimum confidence for pattern recommendations
        )

    def process_application_feedback(
        self, job_id: str, outcome_type: str, outcome_details: Dict = None
    ) -> bool:
        """Process feedback from an application outcome.

        Args:
            job_id: Job opportunity ID
            outcome_type: Type of outcome ('response', 'rejection', 'interview', etc.)
            outcome_details: Additional details about the outcome

        Returns:
            True if feedback was processed successfully
        """
        try:
            # Track the outcome in RLHF system
            application_id = self._get_application_id(job_id)
            days_to_outcome = self._calculate_days_to_outcome(job_id)

            outcome_value = json.dumps(outcome_details) if outcome_details else None

            success = self.rlhf_tracker.track_application_outcome(
                job_id, application_id, outcome_type, outcome_value, days_to_outcome
            )

            if success:
                # Trigger pattern learning
                self._analyze_outcome_patterns()
                logger.info(
                    f"Processed application feedback for job {job_id}: {outcome_type}"
                )

            return success

        except Exception as e:
            logger.error(f"Error processing application feedback: {e}")
            return False

    def _get_application_id(self, job_id: str) -> Optional[int]:
        """Get the application ID for a job if it exists."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id FROM application_history 
                WHERE job_opportunity_id = ?
                ORDER BY applied_at DESC
                LIMIT 1
            """,
                (job_id,),
            )

            result = cursor.fetchone()
            return result[0] if result else None

        except sqlite3.Error as e:
            logger.warning(f"Error getting application ID for job {job_id}: {e}")
            return None
        finally:
            if "conn" in locals():
                conn.close()

    def _calculate_days_to_outcome(self, job_id: str) -> Optional[int]:
        """Calculate days from application to outcome."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT applied_at FROM application_history 
                WHERE job_opportunity_id = ?
                ORDER BY applied_at DESC
                LIMIT 1
            """,
                (job_id,),
            )

            result = cursor.fetchone()
            if not result:
                return None

            applied_date = datetime.fromisoformat(result[0])
            days_diff = (datetime.now() - applied_date).days
            return max(0, days_diff)

        except Exception as e:
            logger.warning(f"Error calculating days to outcome for job {job_id}: {e}")
            return None
        finally:
            if "conn" in locals():
                conn.close()

    def _analyze_outcome_patterns(self):
        """Analyze recent outcomes to identify successful patterns."""
        try:
            # Analyze keyword patterns
            self._analyze_keyword_success_patterns()

            # Analyze company trait patterns
            self._analyze_company_success_patterns()

            # Analyze job characteristic patterns
            self._analyze_job_characteristic_patterns()

            # Update scoring weights based on learned patterns
            self._update_scoring_weights()

        except Exception as e:
            logger.error(f"Error analyzing outcome patterns: {e}")

    def _analyze_keyword_success_patterns(self):
        """Analyze which keywords are associated with successful outcomes."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get keyword success rates
            cursor.execute(
                """
                SELECT 
                    kt.keyword,
                    kt.category,
                    COUNT(*) as total_applications,
                    AVG(ao.success_score) as avg_success,
                    SUM(CASE WHEN ao.success_score >= 0.5 THEN 1 ELSE 0 END) as positive_outcomes,
                    AVG(ao.days_to_outcome) as avg_response_time
                FROM keyword_tracking kt
                JOIN application_outcomes ao ON kt.job_id = ao.job_id
                WHERE ao.created_at >= datetime('now', '-90 days')
                GROUP BY kt.keyword, kt.category
                HAVING total_applications >= ?
                ORDER BY avg_success DESC
            """,
                (self.min_sample_size,),
            )

            keyword_patterns = cursor.fetchall()

            # Learn patterns for high-performing keywords
            for pattern in keyword_patterns:
                if pattern["avg_success"] >= 0.7:  # High success rate
                    pattern_data = {
                        "keyword": pattern["keyword"],
                        "category": pattern["category"],
                        "avg_success": pattern["avg_success"],
                        "avg_response_time": pattern["avg_response_time"],
                        "sample_size": pattern["total_applications"],
                    }

                    description = f"Keyword '{pattern['keyword']}' in {pattern['category']} category shows high success rate"

                    self.rlhf_tracker.learn_pattern(
                        "keyword_combo",
                        description,
                        pattern_data,
                        pattern["avg_success"],
                        pattern["total_applications"],
                    )

        except sqlite3.Error as e:
            logger.error(f"Error analyzing keyword patterns: {e}")
        finally:
            if "conn" in locals():
                conn.close()

    def _analyze_company_success_patterns(self):
        """Analyze which company traits lead to successful outcomes."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Analyze by company type
            cursor.execute(
                """
                SELECT 
                    cp.company_type,
                    cp.company_size,
                    cp.is_pe_portfolio,
                    COUNT(*) as total_applications,
                    AVG(ao.success_score) as avg_success,
                    SUM(CASE WHEN ao.success_score >= 0.5 THEN 1 ELSE 0 END) as positive_outcomes
                FROM application_outcomes ao
                JOIN job_opportunities jo ON ao.job_id = jo.id
                LEFT JOIN company_profiles cp ON jo.company = cp.company_name
                WHERE ao.created_at >= datetime('now', '-90 days')
                  AND cp.company_type IS NOT NULL
                GROUP BY cp.company_type, cp.company_size, cp.is_pe_portfolio
                HAVING total_applications >= ?
                ORDER BY avg_success DESC
            """,
                (self.min_sample_size,),
            )

            company_patterns = cursor.fetchall()

            # Learn patterns for successful company traits
            for pattern in company_patterns:
                if pattern["avg_success"] >= 0.6:  # Good success rate
                    pattern_data = {
                        "company_type": pattern["company_type"],
                        "company_size": pattern["company_size"],
                        "is_pe_portfolio": bool(pattern["is_pe_portfolio"]),
                        "avg_success": pattern["avg_success"],
                        "sample_size": pattern["total_applications"],
                    }

                    description = f"Companies of type '{pattern['company_type']}' with size '{pattern['company_size']}' show good success rate"

                    self.rlhf_tracker.learn_pattern(
                        "company_trait",
                        description,
                        pattern_data,
                        pattern["avg_success"],
                        pattern["total_applications"],
                    )

        except sqlite3.Error as e:
            logger.error(f"Error analyzing company patterns: {e}")
        finally:
            if "conn" in locals():
                conn.close()

    def _analyze_job_characteristic_patterns(self):
        """Analyze which job characteristics lead to successful outcomes."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Analyze by job characteristics
            cursor.execute(
                """
                SELECT 
                    jo.job_type,
                    jo.experience_level,
                    jo.remote_friendly,
                    CASE 
                        WHEN jo.score >= 80 THEN 'high'
                        WHEN jo.score >= 60 THEN 'medium'
                        ELSE 'low'
                    END as score_category,
                    COUNT(*) as total_applications,
                    AVG(ao.success_score) as avg_success,
                    AVG(ao.days_to_outcome) as avg_response_time
                FROM application_outcomes ao
                JOIN job_opportunities jo ON ao.job_id = jo.id
                WHERE ao.created_at >= datetime('now', '-90 days')
                  AND jo.job_type IS NOT NULL
                  AND jo.experience_level IS NOT NULL
                GROUP BY jo.job_type, jo.experience_level, jo.remote_friendly, score_category
                HAVING total_applications >= ?
                ORDER BY avg_success DESC
            """,
                (self.min_sample_size,),
            )

            job_patterns = cursor.fetchall()

            # Learn patterns for successful job characteristics
            for pattern in job_patterns:
                if pattern["avg_success"] >= 0.6:  # Good success rate
                    pattern_data = {
                        "job_type": pattern["job_type"],
                        "experience_level": pattern["experience_level"],
                        "remote_friendly": bool(pattern["remote_friendly"]),
                        "score_category": pattern["score_category"],
                        "avg_success": pattern["avg_success"],
                        "avg_response_time": pattern["avg_response_time"],
                        "sample_size": pattern["total_applications"],
                    }

                    description = f"Jobs with type '{pattern['job_type']}', level '{pattern['experience_level']}', remote: {pattern['remote_friendly']}, score: {pattern['score_category']} show good success"

                    self.rlhf_tracker.learn_pattern(
                        "job_characteristic",
                        description,
                        pattern_data,
                        pattern["avg_success"],
                        pattern["total_applications"],
                    )

        except sqlite3.Error as e:
            logger.error(f"Error analyzing job characteristic patterns: {e}")
        finally:
            if "conn" in locals():
                conn.close()

    def _update_scoring_weights(self):
        """Update job scoring weights based on learned patterns."""
        try:
            # Get active patterns with high confidence
            patterns = self.rlhf_tracker.get_active_patterns(
                min_confidence=self.confidence_threshold
            )

            if not patterns:
                logger.info("No high-confidence patterns found for scoring updates")
                return

            # Calculate weight adjustments based on patterns
            weight_adjustments = self._calculate_weight_adjustments(patterns)

            # Store weight adjustments as targeting metrics
            self._store_weight_adjustments(weight_adjustments)

            logger.info(
                f"Updated scoring weights based on {len(patterns)} learned patterns"
            )

        except Exception as e:
            logger.error(f"Error updating scoring weights: {e}")

    def _calculate_weight_adjustments(self, patterns: List[Dict]) -> Dict[str, float]:
        """Calculate weight adjustments based on learned patterns."""
        adjustments = defaultdict(list)

        for pattern in patterns:
            pattern_data = json.loads(pattern["pattern_data"])
            success_rate = pattern["success_rate"]
            confidence = pattern["confidence_level"]

            # Calculate adjustment factor (positive for good patterns, negative for bad)
            adjustment_factor = (
                (success_rate - 0.5) * confidence * 2
            )  # Scale to -1 to 1

            if pattern["pattern_type"] == "keyword_combo":
                keyword = pattern_data.get("keyword", "")
                category = pattern_data.get("category", "")
                adjustments[f"keyword_{category}_{keyword}"].append(adjustment_factor)

            elif pattern["pattern_type"] == "company_trait":
                company_type = pattern_data.get("company_type", "")
                adjustments[f"company_type_{company_type}"].append(adjustment_factor)

            elif pattern["pattern_type"] == "job_characteristic":
                job_type = pattern_data.get("job_type", "")
                experience_level = pattern_data.get("experience_level", "")
                adjustments[f"job_type_{job_type}"].append(adjustment_factor)
                adjustments[f"experience_level_{experience_level}"].append(
                    adjustment_factor
                )

        # Average adjustments for each factor
        final_adjustments = {}
        for factor, values in adjustments.items():
            if values:
                final_adjustments[factor] = statistics.mean(values)

        return final_adjustments

    def _store_weight_adjustments(self, adjustments: Dict[str, float]):
        """Store weight adjustments as targeting metrics."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            today = datetime.now().date()

            for factor, adjustment in adjustments.items():
                metadata = json.dumps(
                    {
                        "adjustment_factor": adjustment,
                        "updated_by": "feedback_processor",
                    }
                )

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO targeting_metrics 
                    (metric_name, metric_value, period, period_start, period_end, metadata)
                    VALUES (?, ?, 'daily', ?, ?, ?)
                """,
                    (f"weight_{factor}", adjustment, today, today, metadata),
                )

            conn.commit()

        except sqlite3.Error as e:
            logger.error(f"Error storing weight adjustments: {e}")
        finally:
            if "conn" in locals():
                conn.close()

    def get_recommendations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recommendations for improving job targeting.

        Args:
            limit: Maximum number of recommendations to return

        Returns:
            List of recommendations based on learned patterns
        """
        try:
            patterns = self.rlhf_tracker.get_active_patterns(
                min_confidence=self.confidence_threshold
            )

            recommendations = []

            for pattern in patterns[:limit]:
                pattern_data = json.loads(pattern["pattern_data"])

                recommendation = {
                    "type": pattern["pattern_type"],
                    "description": pattern["pattern_description"],
                    "success_rate": pattern["success_rate"],
                    "confidence": pattern["confidence_level"],
                    "sample_size": pattern["sample_size"],
                    "details": pattern_data,
                    "priority": self._calculate_priority(pattern),
                }

                recommendations.append(recommendation)

            # Sort by priority (highest first)
            recommendations.sort(key=lambda x: x["priority"], reverse=True)

            return recommendations

        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            return []

    def _calculate_priority(self, pattern: Dict) -> float:
        """Calculate priority score for a recommendation."""
        success_rate = pattern["success_rate"]
        confidence = pattern["confidence_level"]
        sample_size = min(pattern["sample_size"], 100)  # Cap at 100 for calculation

        # Priority is a combination of success rate, confidence, and sample size
        priority = (success_rate * 0.4) + (confidence * 0.4) + (sample_size / 100 * 0.2)

        return priority

    def analyze_performance_trends(self, days: int = 30) -> Dict[str, Any]:
        """Analyze performance trends over time.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with performance trend analysis
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cutoff_date = datetime.now() - timedelta(days=days)

            # Get daily performance metrics
            cursor.execute(
                """
                SELECT 
                    DATE(ao.created_at) as date,
                    COUNT(*) as applications,
                    AVG(ao.success_score) as avg_success,
                    SUM(CASE WHEN ao.success_score >= 0.5 THEN 1 ELSE 0 END) as positive_outcomes,
                    AVG(ao.days_to_outcome) as avg_response_time
                FROM application_outcomes ao
                WHERE ao.created_at >= ?
                GROUP BY DATE(ao.created_at)
                ORDER BY date
            """,
                (cutoff_date,),
            )

            daily_metrics = [dict(row) for row in cursor.fetchall()]

            # Calculate trends
            if len(daily_metrics) >= 7:  # Need at least a week of data
                recent_success = statistics.mean(
                    [m["avg_success"] for m in daily_metrics[-7:]]
                )
                earlier_success = statistics.mean(
                    [m["avg_success"] for m in daily_metrics[:-7]]
                )
                success_trend = (
                    (recent_success - earlier_success) / earlier_success
                    if earlier_success > 0
                    else 0
                )

                recent_response_time = statistics.mean(
                    [m["avg_response_time"] or 0 for m in daily_metrics[-7:]]
                )
                earlier_response_time = statistics.mean(
                    [m["avg_response_time"] or 0 for m in daily_metrics[:-7]]
                )
                response_time_trend = (
                    (recent_response_time - earlier_response_time)
                    / earlier_response_time
                    if earlier_response_time > 0
                    else 0
                )
            else:
                success_trend = 0
                response_time_trend = 0

            return {
                "daily_metrics": daily_metrics,
                "success_trend": success_trend,
                "response_time_trend": response_time_trend,
                "total_applications": sum(m["applications"] for m in daily_metrics),
                "overall_success_rate": statistics.mean(
                    [m["avg_success"] for m in daily_metrics]
                )
                if daily_metrics
                else 0,
            }

        except Exception as e:
            logger.error(f"Error analyzing performance trends: {e}")
            return {}
        finally:
            if "conn" in locals():
                conn.close()


def main():
    """Main function for testing the feedback processor."""
    processor = FeedbackProcessor()

    # Get recommendations
    print("Getting targeting recommendations...")
    recommendations = processor.get_recommendations()

    if recommendations:
        print(f"\nFound {len(recommendations)} recommendations:")
        for i, rec in enumerate(recommendations[:5], 1):
            print(f"{i}. {rec['description']}")
            print(
                f"   Success rate: {rec['success_rate']:.1%}, Confidence: {rec['confidence']:.1%}"
            )
            print(
                f"   Priority: {rec['priority']:.2f}, Sample size: {rec['sample_size']}"
            )
            print()
    else:
        print("No recommendations available yet. Need more application data.")

    # Analyze performance trends
    print("Analyzing performance trends (last 30 days)...")
    trends = processor.analyze_performance_trends(30)

    if trends:
        print(f"Total applications: {trends.get('total_applications', 0)}")
        print(f"Overall success rate: {trends.get('overall_success_rate', 0):.1%}")
        print(f"Success trend: {trends.get('success_trend', 0):+.1%}")
        print(f"Response time trend: {trends.get('response_time_trend', 0):+.1%}")


if __name__ == "__main__":
    main()
