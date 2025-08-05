#!/usr/bin/env python3
"""
TDD Test Suite for Task Extraction
Tests extraction of actionable tasks from RSS articles
"""

import pytest
import re
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class ExtractedTask:
    """Represents an extracted task"""
    description: str
    category: str
    priority: str
    source_article: str
    confidence: float

class TestTaskExtraction:
    """Test task extraction functionality"""
    
    # Task extraction patterns
    TASK_PATTERNS = [
        {
            "pattern": r"(?:need to|should|must)\s+(?:implement|build|create|develop)\s+(.+?)(?:\.|,|;|$)",
            "category": "development",
            "priority": "medium",
            "confidence": 0.8
        },
        {
            "pattern": r"(?:fix|resolve|debug|troubleshoot)\s+(.+?)(?:\.|,|;|$)",
            "category": "bugfix", 
            "priority": "high",
            "confidence": 0.9
        },
        {
            "pattern": r"(?:optimize|improve|enhance|refactor)\s+(.+?)(?:\.|,|;|$)",
            "category": "optimization",
            "priority": "medium",
            "confidence": 0.7
        },
        {
            "pattern": r"(?:security|vulnerability|patch|update)\s+(?:for|in|of)\s+(.+?)(?:\.|,|;|$)",
            "category": "security",
            "priority": "critical",
            "confidence": 0.95
        },
        {
            "pattern": r"(?:investigate|research|explore)\s+(.+?)(?:\.|,|;|$)",
            "category": "research",
            "priority": "low",
            "confidence": 0.6
        }
    ]
    
    # Context indicators that boost confidence
    CONTEXT_BOOSTERS = {
        "critical": 0.2,
        "urgent": 0.2,
        "important": 0.1,
        "asap": 0.15,
        "immediately": 0.2,
        "vulnerability": 0.2,
        "security": 0.15
    }
    
    def extract_tasks(self, title: str, content: str) -> List[ExtractedTask]:
        """Extract actionable tasks from article"""
        tasks = []
        full_text = f"{title} {content}"
        
        for pattern_config in self.TASK_PATTERNS:
            pattern = pattern_config["pattern"]
            matches = re.finditer(pattern, full_text, re.IGNORECASE)
            
            for match in matches:
                task_text = match.group(1).strip()
                
                # Clean up task text
                task_text = self.clean_task_text(task_text)
                if len(task_text) < 10:  # Skip very short matches
                    continue
                
                # Calculate confidence with context
                confidence = pattern_config["confidence"]
                confidence = self.adjust_confidence_with_context(
                    full_text, match.start(), confidence
                )
                
                # Determine priority based on context
                priority = self.determine_priority(
                    full_text, match.start(), pattern_config["priority"]
                )
                
                task = ExtractedTask(
                    description=task_text,
                    category=pattern_config["category"],
                    priority=priority,
                    source_article=title,
                    confidence=confidence
                )
                
                tasks.append(task)
        
        # Remove duplicates and low confidence tasks
        tasks = self.filter_tasks(tasks)
        
        return tasks
    
    def clean_task_text(self, text: str) -> str:
        """Clean extracted task text"""
        # Remove common suffixes
        text = re.sub(r'\s+(in|on|at|for|with|by)\s+the\s*$', '', text)
        # Remove trailing articles
        text = re.sub(r'\s+(a|an|the)\s*$', '', text)
        # Capitalize first letter
        if text:
            text = text[0].upper() + text[1:]
        return text
    
    def adjust_confidence_with_context(self, text: str, position: int, 
                                     base_confidence: float) -> float:
        """Adjust confidence based on surrounding context"""
        # Get context window (100 chars before and after)
        start = max(0, position - 100)
        end = min(len(text), position + 100)
        context = text[start:end].lower()
        
        confidence = base_confidence
        for keyword, boost in self.CONTEXT_BOOSTERS.items():
            if keyword in context:
                confidence = min(1.0, confidence + boost)
        
        return confidence
    
    def determine_priority(self, text: str, position: int, 
                          default_priority: str) -> str:
        """Determine task priority from context"""
        context = text[max(0, position-50):position+50].lower()
        
        if any(word in context for word in ["critical", "urgent", "immediately"]):
            return "critical"
        elif any(word in context for word in ["important", "high priority"]):
            return "high"
        elif any(word in context for word in ["low priority", "eventually", "someday"]):
            return "low"
        
        return default_priority
    
    def filter_tasks(self, tasks: List[ExtractedTask], 
                    min_confidence: float = 0.6) -> List[ExtractedTask]:
        """Filter and deduplicate tasks"""
        # Remove low confidence
        tasks = [t for t in tasks if t.confidence >= min_confidence]
        
        # Remove duplicates (similar descriptions)
        unique_tasks = []
        seen_descriptions = set()
        
        for task in tasks:
            # Simple deduplication by first 30 chars
            key = task.description[:30].lower()
            if key not in seen_descriptions:
                seen_descriptions.add(key)
                unique_tasks.append(task)
        
        return unique_tasks
    
    # Test cases
    def test_development_task_extraction(self):
        """Test extraction of development tasks"""
        content = """
        The new API is almost ready, but we need to implement authentication
        before the release. We should also build a comprehensive test suite
        for the endpoints.
        """
        
        tasks = self.extract_tasks("API Development Update", content)
        
        assert len(tasks) >= 2
        assert any("authentication" in t.description.lower() for t in tasks)
        assert any("test suite" in t.description.lower() for t in tasks)
        assert all(t.category == "development" for t in tasks)
    
    def test_bugfix_task_extraction(self):
        """Test extraction of bugfix tasks"""
        content = """
        Users are reporting issues with the login system. We need to fix
        the password reset functionality immediately. Also troubleshoot
        the email delivery problems.
        """
        
        tasks = self.extract_tasks("Critical Bug Report", content)
        
        assert len(tasks) >= 2
        assert any(t.priority == "critical" for t in tasks)  # "immediately" boosts priority
        assert all(t.category == "bugfix" for t in tasks)
    
    def test_security_task_extraction(self):
        """Test extraction of security tasks"""
        content = """
        A critical security vulnerability has been discovered in the 
        authentication module. Security update for OpenSSL is required.
        All systems need immediate patching.
        """
        
        tasks = self.extract_tasks("Security Alert", content)
        
        assert len(tasks) >= 1
        assert all(t.priority == "critical" for t in tasks)
        assert all(t.category == "security" for t in tasks)
        assert all(t.confidence >= 0.9 for t in tasks)
    
    def test_mixed_task_extraction(self):
        """Test extraction from article with multiple task types"""
        content = """
        This week's priorities:
        1. We must fix the memory leak in the data processor
        2. Need to implement the new caching layer
        3. Should optimize database queries for better performance
        4. Research alternative authentication methods
        5. Security patch for the file upload component
        """
        
        tasks = self.extract_tasks("Weekly Engineering Update", content)
        
        # Should extract multiple task types
        categories = {t.category for t in tasks}
        assert "bugfix" in categories
        assert "development" in categories
        assert "optimization" in categories
        assert "research" in categories
        assert "security" in categories
        
        assert len(tasks) >= 5
    
    def test_confidence_adjustment(self):
        """Test confidence adjustment based on context"""
        content1 = "We should probably implement new features"
        content2 = "URGENT: We must immediately implement new features"
        
        tasks1 = self.extract_tasks("Update 1", content1)
        tasks2 = self.extract_tasks("Update 2", content2)
        
        assert tasks2[0].confidence > tasks1[0].confidence
        assert tasks2[0].priority == "critical"
    
    def test_task_deduplication(self):
        """Test that duplicate tasks are filtered"""
        content = """
        We need to fix the login bug. The login bug must be fixed.
        Fix the login bug as soon as possible.
        """
        
        tasks = self.extract_tasks("Bug Report", content)
        
        # Should only have one task about login bug
        assert len(tasks) == 1
        assert "login bug" in tasks[0].description.lower()
    
    def test_minimum_confidence_filtering(self):
        """Test that low confidence tasks are filtered"""
        content = """
        Maybe we could possibly investigate some new approaches.
        We definitely must fix the critical security vulnerability.
        """
        
        tasks = self.extract_tasks("Mixed Confidence", content)
        
        # Only high confidence task should remain
        assert len(tasks) >= 1
        assert all(t.confidence >= 0.6 for t in tasks)
        assert any("security vulnerability" in t.description for t in tasks)
    
    def test_task_text_cleaning(self):
        """Test that task descriptions are properly cleaned"""
        content = "We need to implement the new feature in the system"
        
        tasks = self.extract_tasks("Test", content)
        
        assert len(tasks) == 1
        task = tasks[0]
        # Should be cleaned and capitalized
        assert task.description.startswith("New feature")
        assert not task.description.endswith("in the")
    
    def test_no_false_positives(self):
        """Test that non-task content doesn't generate tasks"""
        content = """
        The system has been implemented successfully. All bugs have been fixed.
        Performance has been optimized. Security has been updated.
        """
        
        tasks = self.extract_tasks("Status Report", content)
        
        # Past tense shouldn't generate tasks
        assert len(tasks) == 0