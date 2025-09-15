#!/usr/bin/env python3
"""Keyword Extractor Agent

Extracts AI/ML and tech-related keywords from job descriptions and tracks them
for RLHF learning and targeting optimization.
"""

import re
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
import logging

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from streamlit_app.common import DB_PATH
from agents.rlhf_tracker import RLHFTracker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KeywordExtractor:
    """Extracts and categorizes keywords from job descriptions."""

    def __init__(self, db_path: str = None):
        """Initialize the keyword extractor."""
        self.db_path = db_path or DB_PATH
        self.rlhf_tracker = RLHFTracker(self.db_path)

        # Define keyword categories with patterns
        self.keyword_categories = {
            "ai_ml": {
                "keywords": [
                    "artificial intelligence",
                    "ai",
                    "machine learning",
                    "ml",
                    "deep learning",
                    "neural networks",
                    "computer vision",
                    "nlp",
                    "natural language processing",
                    "data science",
                    "data scientist",
                    "model training",
                    "predictive modeling",
                    "tensorflow",
                    "pytorch",
                    "keras",
                    "scikit-learn",
                    "pandas",
                    "numpy",
                    "opencv",
                    "hugging face",
                    "transformers",
                    "bert",
                    "gpt",
                    "llm",
                    "large language model",
                    "generative ai",
                    "reinforcement learning",
                    "supervised learning",
                    "unsupervised learning",
                    "classification",
                    "regression",
                    "clustering",
                    "recommendation system",
                    "anomaly detection",
                    "feature engineering",
                    "hyperparameter tuning",
                    "model deployment",
                    "mlops",
                    "ml ops",
                    "model monitoring",
                    "a/b testing",
                    "statistical analysis",
                    "hypothesis testing",
                    "bayesian",
                    "markov",
                    "gradient descent",
                    "backpropagation",
                    "convolutional",
                    "recurrent",
                    "lstm",
                    "gru",
                    "attention",
                    "transformer",
                    "autoencoder",
                    "gan",
                    "generative adversarial",
                ],
                "importance": 0.9,
            },
            "tech_stack": {
                "keywords": [
                    "python",
                    "r",
                    "sql",
                    "scala",
                    "java",
                    "javascript",
                    "typescript",
                    "react",
                    "vue",
                    "angular",
                    "node.js",
                    "express",
                    "django",
                    "flask",
                    "fastapi",
                    "spring",
                    "postgresql",
                    "mysql",
                    "mongodb",
                    "redis",
                    "elasticsearch",
                    "kafka",
                    "rabbitmq",
                    "docker",
                    "kubernetes",
                    "aws",
                    "azure",
                    "gcp",
                    "google cloud",
                    "terraform",
                    "ansible",
                    "jenkins",
                    "ci/cd",
                    "git",
                    "github",
                    "gitlab",
                    "bitbucket",
                    "linux",
                    "unix",
                    "bash",
                    "shell scripting",
                    "api",
                    "rest",
                    "graphql",
                    "microservices",
                    "serverless",
                    "lambda",
                    "spark",
                    "hadoop",
                    "hive",
                    "pig",
                    "storm",
                    "flink",
                    "airflow",
                    "luigi",
                    "jupyter",
                    "databricks",
                    "snowflake",
                    "bigquery",
                    "redshift",
                ],
                "importance": 0.7,
            },
            "seniority": {
                "keywords": [
                    "senior",
                    "lead",
                    "principal",
                    "staff",
                    "director",
                    "vp",
                    "junior",
                    "entry level",
                    "associate",
                    "mid-level",
                    "experienced",
                    "expert",
                    "architect",
                    "head of",
                    "chief",
                    "manager",
                    "supervisor",
                    "team lead",
                    "tech lead",
                    "technical lead",
                    "0-2 years",
                    "2-5 years",
                    "5+ years",
                    "10+ years",
                    "fresh graduate",
                    "new grad",
                ],
                "importance": 0.8,
            },
            "domain": {
                "keywords": [
                    "fintech",
                    "healthtech",
                    "edtech",
                    "adtech",
                    "martech",
                    "insurtech",
                    "proptech",
                    "legaltech",
                    "regtech",
                    "biotech",
                    "medtech",
                    "e-commerce",
                    "ecommerce",
                    "marketplace",
                    "saas",
                    "b2b",
                    "b2c",
                    "enterprise",
                    "startup",
                    "unicorn",
                    "series a",
                    "series b",
                    "ipo",
                    "public company",
                    "private equity",
                    "venture capital",
                    "gaming",
                    "entertainment",
                    "media",
                    "social media",
                    "streaming",
                    "cybersecurity",
                    "security",
                    "blockchain",
                    "crypto",
                    "defi",
                    "web3",
                    "nft",
                    "autonomous vehicles",
                    "self-driving",
                    "robotics",
                    "iot",
                    "internet of things",
                    "ar",
                    "vr",
                    "augmented reality",
                    "virtual reality",
                    "mixed reality",
                ],
                "importance": 0.6,
            },
            "soft_skills": {
                "keywords": [
                    "communication",
                    "leadership",
                    "teamwork",
                    "collaboration",
                    "problem solving",
                    "critical thinking",
                    "analytical",
                    "creative",
                    "innovative",
                    "adaptable",
                    "flexible",
                    "agile",
                    "scrum",
                    "kanban",
                    "project management",
                    "time management",
                    "mentoring",
                    "coaching",
                    "presentation",
                    "public speaking",
                    "writing",
                    "documentation",
                    "cross-functional",
                    "stakeholder management",
                    "client facing",
                    "customer focused",
                    "detail oriented",
                    "self-motivated",
                    "independent",
                    "autonomous",
                    "proactive",
                    "strategic thinking",
                ],
                "importance": 0.4,
            },
            "company_type": {
                "keywords": [
                    "remote",
                    "hybrid",
                    "on-site",
                    "in-office",
                    "distributed",
                    "work from home",
                    "wfh",
                    "flexible hours",
                    "part-time",
                    "full-time",
                    "contract",
                    "freelance",
                    "consulting",
                    "permanent",
                    "temporary",
                    "internship",
                    "co-op",
                    "fellowship",
                    "visa sponsorship",
                    "h1b",
                    "green card",
                    "no visa",
                    "us citizen",
                    "security clearance",
                    "fast-paced",
                    "high-growth",
                    "well-funded",
                    "profitable",
                    "pre-revenue",
                    "seed stage",
                    "early stage",
                    "growth stage",
                    "mature",
                    "established",
                    "fortune 500",
                    "unicorn",
                    "decacorn",
                ],
                "importance": 0.5,
            },
        }

        # Compile regex patterns for efficiency
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for each keyword category."""
        self.compiled_patterns = {}

        for category, data in self.keyword_categories.items():
            patterns = []
            for keyword in data["keywords"]:
                # Create word boundary pattern for exact matches
                pattern = r"\b" + re.escape(keyword) + r"\b"
                patterns.append(pattern)

            # Combine all patterns for this category
            combined_pattern = "|".join(patterns)
            self.compiled_patterns[category] = re.compile(
                combined_pattern, re.IGNORECASE
            )

    def extract_keywords_from_text(self, text: str) -> Dict[str, List[Tuple[str, int]]]:
        """Extract keywords from text and count frequencies.

        Args:
            text: Text to extract keywords from

        Returns:
            Dictionary with category -> [(keyword, frequency), ...] mappings
        """
        if not text:
            return {}

        # Clean text
        text = text.lower()

        results = {}

        for category, pattern in self.compiled_patterns.items():
            matches = pattern.findall(text)

            if matches:
                # Count frequencies
                frequency_map = {}
                for match in matches:
                    frequency_map[match] = frequency_map.get(match, 0) + 1

                # Sort by frequency descending
                sorted_keywords = sorted(
                    frequency_map.items(), key=lambda x: x[1], reverse=True
                )
                results[category] = sorted_keywords

        return results

    def extract_keywords_from_job(self, job_id: str) -> bool:
        """Extract keywords from a specific job and store them.

        Args:
            job_id: Job opportunity ID

        Returns:
            True if keywords were extracted successfully
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get job details
            cursor.execute(
                """
                SELECT id, title, company, description, requirements
                FROM job_opportunities 
                WHERE id = ?
            """,
                (job_id,),
            )

            job = cursor.fetchone()
            if not job:
                logger.warning(f"Job {job_id} not found")
                return False

            # Combine text fields for keyword extraction
            text_to_analyze = (
                f"{job['title']} {job['description'] or ''} {job['requirements'] or ''}"
            )

            # Extract keywords
            keywords_by_category = self.extract_keywords_from_text(text_to_analyze)

            if not keywords_by_category:
                logger.info(f"No keywords found for job {job_id}")
                return True

            # Store keywords in database
            for category, keywords in keywords_by_category.items():
                importance_score = self.keyword_categories[category]["importance"]

                for keyword, frequency in keywords:
                    # Get context (surrounding text)
                    context = self._get_keyword_context(text_to_analyze, keyword)

                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO keyword_tracking 
                        (job_id, keyword, category, frequency, context, importance_score)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (
                            job_id,
                            keyword,
                            category,
                            frequency,
                            context,
                            importance_score,
                        ),
                    )

                    # Add RLHF signal for keyword match
                    signal_value = {
                        "keyword": keyword,
                        "category": category,
                        "frequency": frequency,
                        "importance_score": importance_score,
                        "context": context,
                    }

                    self.rlhf_tracker.add_signal(
                        job_id,
                        "keyword_match",
                        signal_value,
                        confidence=0.9,
                        weight=importance_score,
                    )

            conn.commit()
            logger.info(
                f"Extracted keywords for job {job_id}: {sum(len(keywords) for keywords in keywords_by_category.values())} total"
            )
            return True

        except sqlite3.Error as e:
            logger.error(f"Error extracting keywords for job {job_id}: {e}")
            return False
        finally:
            if "conn" in locals():
                conn.close()

    def _get_keyword_context(
        self, text: str, keyword: str, context_length: int = 100
    ) -> str:
        """Get context around a keyword in text.

        Args:
            text: Full text
            keyword: Keyword to find context for
            context_length: Number of characters of context on each side

        Returns:
            Context string around the keyword
        """
        try:
            # Find the keyword in text (case insensitive)
            match = re.search(re.escape(keyword), text, re.IGNORECASE)
            if not match:
                return ""

            start = match.start()
            end = match.end()

            # Get context before and after
            context_start = max(0, start - context_length)
            context_end = min(len(text), end + context_length)

            context = text[context_start:context_end].strip()

            # Clean up context
            context = " ".join(context.split())  # Remove extra whitespace

            return context

        except Exception as e:
            logger.warning(f"Error getting context for keyword '{keyword}': {e}")
            return ""

    def extract_keywords_for_all_jobs(self, limit: int = None) -> int:
        """Extract keywords for all jobs that don't have keywords yet.

        Args:
            limit: Maximum number of jobs to process (optional)

        Returns:
            Number of jobs processed
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Find jobs without keyword tracking
            query = """
                SELECT DISTINCT jo.id
                FROM job_opportunities jo
                LEFT JOIN keyword_tracking kt ON jo.id = kt.job_id
                WHERE kt.job_id IS NULL 
                AND jo.description IS NOT NULL
                AND LENGTH(jo.description) > 50
                ORDER BY jo.fetched_at DESC
            """

            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query)
            jobs = cursor.fetchall()

            if not jobs:
                logger.info("No jobs found that need keyword extraction")
                return 0

            logger.info(f"Found {len(jobs)} jobs to process for keyword extraction")

            processed_count = 0
            for job in jobs:
                if self.extract_keywords_from_job(job["id"]):
                    processed_count += 1

                # Log progress periodically
                if processed_count % 10 == 0:
                    logger.info(f"Processed {processed_count}/{len(jobs)} jobs")

            logger.info(
                f"Keyword extraction complete: {processed_count} jobs processed"
            )
            return processed_count

        except sqlite3.Error as e:
            logger.error(f"Error in bulk keyword extraction: {e}")
            return 0
        finally:
            if "conn" in locals():
                conn.close()

    def get_keyword_statistics(
        self, category: str = None, min_frequency: int = 2
    ) -> List[Dict]:
        """Get keyword statistics and trends.

        Args:
            category: Filter by category (optional)
            min_frequency: Minimum frequency threshold

        Returns:
            List of keyword statistics
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            where_clauses = [f"frequency >= {min_frequency}"]
            params = []

            if category:
                where_clauses.append("category = ?")
                params.append(category)

            cursor.execute(
                f"""
                SELECT 
                    keyword,
                    category,
                    COUNT(*) as job_count,
                    SUM(frequency) as total_frequency,
                    AVG(frequency) as avg_frequency,
                    AVG(importance_score) as avg_importance,
                    COUNT(DISTINCT job_id) as unique_jobs
                FROM keyword_tracking
                WHERE {' AND '.join(where_clauses)}
                GROUP BY keyword, category
                ORDER BY job_count DESC, total_frequency DESC
            """,
                params,
            )

            return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            logger.error(f"Error getting keyword statistics: {e}")
            return []
        finally:
            if "conn" in locals():
                conn.close()

    def get_trending_keywords(self, days: int = 30, category: str = None) -> List[Dict]:
        """Get keywords that are trending in recent job postings.

        Args:
            days: Number of days to look back
            category: Filter by category (optional)

        Returns:
            List of trending keywords
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            where_clauses = [f"kt.created_at >= datetime('now', '-{days} days')"]
            params = []

            if category:
                where_clauses.append("kt.category = ?")
                params.append(category)

            cursor.execute(
                f"""
                SELECT 
                    kt.keyword,
                    kt.category,
                    COUNT(*) as recent_frequency,
                    COUNT(DISTINCT kt.job_id) as recent_jobs,
                    AVG(jo.score) as avg_job_score,
                    AVG(kt.importance_score) as avg_importance
                FROM keyword_tracking kt
                JOIN job_opportunities jo ON kt.job_id = jo.id
                WHERE {' AND '.join(where_clauses)}
                GROUP BY kt.keyword, kt.category
                HAVING recent_frequency >= 3
                ORDER BY recent_frequency DESC, avg_job_score DESC
                LIMIT 50
            """,
                params,
            )

            return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            logger.error(f"Error getting trending keywords: {e}")
            return []
        finally:
            if "conn" in locals():
                conn.close()


def main():
    """Main function for testing the keyword extractor."""
    extractor = KeywordExtractor()

    # Extract keywords for jobs that don't have them yet
    print("Extracting keywords for jobs...")
    processed = extractor.extract_keywords_for_all_jobs(limit=50)
    print(f"Processed {processed} jobs")

    # Show keyword statistics
    print("\nTop AI/ML keywords:")
    ai_ml_stats = extractor.get_keyword_statistics(category="ai_ml")
    for stat in ai_ml_stats[:10]:
        print(
            f"  {stat['keyword']}: {stat['job_count']} jobs, "
            f"total frequency: {stat['total_frequency']}"
        )

    # Show trending keywords
    print("\nTrending keywords (last 30 days):")
    trending = extractor.get_trending_keywords(days=30)
    for keyword_data in trending[:10]:
        print(
            f"  {keyword_data['keyword']} ({keyword_data['category']}): "
            f"{keyword_data['recent_jobs']} jobs, "
            f"avg score: {keyword_data['avg_job_score']:.1f}"
        )


if __name__ == "__main__":
    main()
