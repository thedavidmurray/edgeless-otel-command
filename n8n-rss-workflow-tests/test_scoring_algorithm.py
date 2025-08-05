#!/usr/bin/env python3
"""
TDD Test Suite for Article Scoring Algorithm
Tests scoring logic before n8n implementation
"""

import pytest
import re
from typing import Dict, List, Tuple

class TestArticleScoring:
    """Test article scoring functionality"""
    
    # Priority patterns matching original RSS agent
    PRIORITY_PATTERNS = {
        r"security|vulnerability|cve": 3.0,
        r"zero.?day|breach|exploit": 3.5,
        r"gpt.?5|claude|anthropic": 2.5,
        r"openai": 2.0,
        r"breakthrough|paper": 2.5,
        r"research": 1.5,
        r"release|update": 1.5,
        r"new.?feature": 2.0,
        r"obsidian|plugin": 2.0,
        r"python|rust": 1.0,
        r"performance|optimization": 1.5,
        r"trend|analysis|insight": 1.0,
    }
    
    REPUTABLE_SOURCES = [
        "arxiv.org",
        "openai.com",
        "anthropic.com",
        "github.com",
        "hackerone.com",
        "security.googleblog.com"
    ]
    
    def score_article(self, title: str, content: str = "", source: str = "") -> Tuple[float, List[str]]:
        """Score article based on patterns and source"""
        score = 0.0
        reasons = []
        
        # Combine title and content for pattern matching
        text = f"{title} {content}".lower()
        
        # Apply pattern scoring
        for pattern, weight in self.PRIORITY_PATTERNS.items():
            if re.search(pattern, text):
                score += weight
                # Extract matched term for reason
                match = re.search(pattern, text)
                if match:
                    reasons.append(f"Contains priority term: {match.group()}")
        
        # Apply source reputation boost
        if source:
            domain = self.extract_domain(source)
            if domain in self.REPUTABLE_SOURCES:
                score += 2.0
                reasons.append(f"Reputable source: {domain}")
        
        # Cap at 10.0
        final_score = min(score, 10.0)
        
        return final_score, reasons
    
    def extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        # Simple extraction for tests
        url = url.lower()
        url = url.replace("https://", "").replace("http://", "")
        return url.split("/")[0]
    
    def test_basic_scoring(self):
        """Test basic article scoring"""
        test_cases = [
            # (title, expected_min_score)
            ("New Security Vulnerability in OpenSSL", 3.0),
            ("GPT-5 Release Date Announced", 4.0),
            ("Python Performance Tips", 2.5),
            ("Random Article About Cooking", 0.0),
        ]
        
        for title, expected_min in test_cases:
            score, reasons = self.score_article(title)
            assert score >= expected_min, f"'{title}' scored {score}, expected >= {expected_min}"
            assert len(reasons) > 0 or expected_min == 0
    
    def test_compound_scoring(self):
        """Test articles matching multiple patterns"""
        title = "Security Research: New Zero-Day Exploit in Python"
        score, reasons = self.score_article(title)
        
        # Should match: security(3.0) + research(1.5) + zero-day(3.5) + python(1.0) = 9.0
        assert score >= 9.0
        assert len(reasons) >= 4
    
    def test_source_reputation_boost(self):
        """Test source reputation scoring"""
        title = "Machine Learning Updates"
        
        # Without reputable source
        score1, _ = self.score_article(title, source="random-blog.com")
        
        # With reputable source
        score2, reasons2 = self.score_article(title, source="https://arxiv.org/papers/123")
        
        assert score2 > score1
        assert score2 - score1 == 2.0
        assert any("Reputable source" in r for r in reasons2)
    
    def test_score_capping(self):
        """Test that scores don't exceed 10.0"""
        # Create article that would score >10 without cap
        title = "URGENT: Critical Zero-Day Security Vulnerability Exploit Released"
        content = "Breakthrough research paper on GPT-5 Claude Anthropic OpenAI"
        
        score, _ = self.score_article(title, content, "https://arxiv.org")
        assert score == 10.0
    
    def test_case_insensitivity(self):
        """Test pattern matching is case-insensitive"""
        titles = [
            "SECURITY ALERT",
            "Security Alert",
            "security alert",
            "SeCuRiTy AlErT"
        ]
        
        scores = [self.score_article(title)[0] for title in titles]
        assert all(s == scores[0] for s in scores)
    
    def test_deep_analysis_threshold(self):
        """Test identification of articles needing deep analysis"""
        threshold = 7.0
        
        high_priority = "Critical Security Vulnerability: Zero-Day Exploit in Production"
        low_priority = "Weekly Python Newsletter"
        
        score1, _ = self.score_article(high_priority, source="hackerone.com")
        score2, _ = self.score_article(low_priority)
        
        assert score1 >= threshold, "High priority article should exceed threshold"
        assert score2 < threshold, "Low priority article should not exceed threshold"
    
    def test_scoring_reasons(self):
        """Test that scoring reasons are properly tracked"""
        title = "Anthropic Releases Claude Update with New Features"
        score, reasons = self.score_article(title)
        
        # Check reasons are descriptive
        assert len(reasons) >= 3
        assert any("claude" in r.lower() for r in reasons)
        assert any("update" in r.lower() for r in reasons)
        assert any("new" in r.lower() and "feature" in r.lower() for r in reasons)
    
    def test_performance_batch_scoring(self):
        """Test scoring performance for large batches"""
        import time
        
        # Generate 1000 test articles
        articles = []
        for i in range(1000):
            if i % 3 == 0:
                title = f"Security Update {i}"
            elif i % 3 == 1:
                title = f"AI Research Paper {i}"
            else:
                title = f"Random Article {i}"
            articles.append(title)
        
        # Time batch scoring
        start = time.time()
        results = [self.score_article(title) for title in articles]
        duration = time.time() - start
        
        assert len(results) == 1000
        assert duration < 1.0, f"Batch scoring took {duration}s, should be <1s"
        
        # Verify distribution makes sense
        high_scores = sum(1 for score, _ in results if score >= 3.0)
        assert 600 <= high_scores <= 700  # ~2/3 should be high score