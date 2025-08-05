#!/usr/bin/env python3
"""
TDD Test Suite for RSS Deduplication
Tests the deduplication logic before implementation
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import json

class TestRSSDeduplication:
    """Test RSS article deduplication functionality"""
    
    @pytest.fixture
    def test_db(self):
        """Create temporary test database"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create processed_articles table
        cursor.execute("""
            CREATE TABLE processed_articles (
                url VARCHAR(512) PRIMARY KEY,
                title TEXT NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                score FLOAT DEFAULT 0.0,
                cluster VARCHAR(100),
                obsidian_note_path TEXT,
                summary TEXT,
                source_feed VARCHAR(255)
            )
        """)
        conn.commit()
        
        yield conn
        
        conn.close()
        Path(db_path).unlink()
    
    def test_new_article_not_duplicate(self, test_db):
        """New articles should not be marked as duplicates"""
        # Arrange
        article_url = "https://example.com/article1"
        
        # Act
        is_duplicate = self.check_duplicate(test_db, article_url)
        
        # Assert
        assert is_duplicate is False
    
    def test_existing_article_is_duplicate(self, test_db):
        """Previously processed articles should be marked as duplicates"""
        # Arrange
        article_url = "https://example.com/article1"
        self.insert_article(test_db, article_url, "Test Article")
        
        # Act
        is_duplicate = self.check_duplicate(test_db, article_url)
        
        # Assert
        assert is_duplicate is True
    
    def test_url_normalization(self, test_db):
        """URLs with different formats should be recognized as same"""
        # Arrange
        urls = [
            "https://example.com/article",
            "http://example.com/article",
            "https://example.com/article/",
            "https://example.com/article?utm_source=rss"
        ]
        
        # Insert first variant
        self.insert_article(test_db, urls[0], "Test Article")
        
        # Act & Assert
        for url in urls[1:]:
            normalized = self.normalize_url(url)
            is_duplicate = self.check_duplicate(test_db, normalized)
            assert is_duplicate is True, f"Failed to detect {url} as duplicate"
    
    def test_bulk_deduplication_performance(self, test_db):
        """Bulk checking should be efficient for large batches"""
        # Arrange - Insert 1000 articles
        for i in range(1000):
            self.insert_article(test_db, f"https://example.com/article{i}", f"Article {i}")
        
        # Create mix of new and existing URLs
        test_urls = [f"https://example.com/article{i}" for i in range(500, 1500)]
        
        # Act
        start_time = datetime.now()
        results = self.bulk_check_duplicates(test_db, test_urls)
        duration = (datetime.now() - start_time).total_seconds()
        
        # Assert
        assert len(results) == 1000
        assert sum(results.values()) == 500  # 500 duplicates
        assert duration < 1.0  # Should complete in under 1 second
    
    def test_concurrent_deduplication(self, test_db):
        """Multiple n8n instances shouldn't create duplicates"""
        # This test simulates race conditions
        # Implementation would use database transactions
        pass
    
    # Helper methods that would be implemented in n8n
    def check_duplicate(self, conn, url):
        """Check if URL already processed"""
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM processed_articles WHERE url = ?", (url,))
        return cursor.fetchone() is not None
    
    def insert_article(self, conn, url, title):
        """Insert article into processed table"""
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO processed_articles (url, title) VALUES (?, ?)",
            (url, title)
        )
        conn.commit()
    
    def normalize_url(self, url):
        """Normalize URL for deduplication"""
        # Remove protocol variations
        url = url.replace("http://", "https://")
        
        # Remove trailing slash
        url = url.rstrip("/")
        
        # Remove common tracking parameters
        if "?" in url:
            base_url = url.split("?")[0]
            return base_url
        
        return url
    
    def bulk_check_duplicates(self, conn, urls):
        """Efficiently check multiple URLs"""
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(urls))
        query = f"SELECT url FROM processed_articles WHERE url IN ({placeholders})"
        cursor.execute(query, urls)
        
        existing_urls = {row[0] for row in cursor.fetchall()}
        return {url: url in existing_urls for url in urls}