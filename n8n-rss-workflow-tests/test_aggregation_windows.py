#!/usr/bin/env python3
"""
TDD Test Suite for Aggregation Windows
Tests the 8-hour window aggregation system
"""

import pytest
from datetime import datetime, timedelta
import sqlite3
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple

class TestAggregationWindows:
    """Test aggregation window functionality"""
    
    # Window schedule: 6am, 2pm, 10pm
    WINDOW_SCHEDULE = [
        (6, 0),   # 6:00 AM
        (14, 0),  # 2:00 PM  
        (22, 0),  # 10:00 PM
    ]
    
    @pytest.fixture
    def test_db(self):
        """Create test database with aggregation tables"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create aggregation windows table
        cursor.execute("""
            CREATE TABLE aggregation_windows (
                window_id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP NOT NULL,
                status VARCHAR(20) DEFAULT 'active',
                article_count INT DEFAULT 0,
                note_count INT DEFAULT 0,
                digest_sent BOOLEAN DEFAULT 0
            )
        """)
        
        # Create processed articles table
        cursor.execute("""
            CREATE TABLE processed_articles (
                url VARCHAR(512) PRIMARY KEY,
                title TEXT NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                window_id INT,
                score FLOAT DEFAULT 0.0,
                cluster VARCHAR(100),
                obsidian_note_created BOOLEAN DEFAULT 0
            )
        """)
        
        conn.commit()
        yield conn
        
        conn.close()
        Path(db_path).unlink()
    
    def get_current_window(self, current_time: datetime) -> Tuple[datetime, datetime]:
        """Get the current aggregation window for given time"""
        hour = current_time.hour
        
        # Find which window we're in
        if 22 <= hour or hour < 6:
            # Evening window (10pm - 6am)
            start = current_time.replace(hour=22, minute=0, second=0, microsecond=0)
            if hour < 6:
                start -= timedelta(days=1)
            end = start + timedelta(hours=8)
        elif 6 <= hour < 14:
            # Morning window (6am - 2pm)
            start = current_time.replace(hour=6, minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=8)
        else:
            # Afternoon window (2pm - 10pm)
            start = current_time.replace(hour=14, minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=8)
        
        return start, end
    
    def create_or_get_window(self, conn: sqlite3.Connection, 
                            current_time: datetime) -> int:
        """Create or get current window ID"""
        start, end = self.get_current_window(current_time)
        
        cursor = conn.cursor()
        
        # Check if window exists
        cursor.execute("""
            SELECT window_id FROM aggregation_windows
            WHERE start_time = ? AND end_time = ?
        """, (start, end))
        
        result = cursor.fetchone()
        
        if result:
            return result[0]
        else:
            # Create new window
            cursor.execute("""
                INSERT INTO aggregation_windows (start_time, end_time)
                VALUES (?, ?)
            """, (start, end))
            conn.commit()
            return cursor.lastrowid
    
    def add_article_to_window(self, conn: sqlite3.Connection, window_id: int,
                             url: str, title: str, score: float,
                             created_note: bool = False) -> None:
        """Add article to current window"""
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO processed_articles 
            (url, title, window_id, score, obsidian_note_created)
            VALUES (?, ?, ?, ?, ?)
        """, (url, title, window_id, score, created_note))
        
        # Update window counts
        if created_note:
            cursor.execute("""
                UPDATE aggregation_windows 
                SET article_count = article_count + 1,
                    note_count = note_count + 1
                WHERE window_id = ?
            """, (window_id,))
        else:
            cursor.execute("""
                UPDATE aggregation_windows 
                SET article_count = article_count + 1
                WHERE window_id = ?
            """, (window_id,))
        
        conn.commit()
    
    def should_trigger_digest(self, conn: sqlite3.Connection, 
                            current_time: datetime) -> bool:
        """Check if digest should be triggered"""
        cursor = conn.cursor()
        
        # Get current window
        start, end = self.get_current_window(current_time)
        
        # Check if we're past the window end time
        if current_time >= end:
            # Check if digest already sent
            cursor.execute("""
                SELECT digest_sent FROM aggregation_windows
                WHERE start_time = ? AND end_time = ?
            """, (start, end))
            
            result = cursor.fetchone()
            if result and not result[0]:
                return True
        
        return False
    
    # Test cases
    def test_window_calculation(self):
        """Test correct window calculation for different times"""
        test_cases = [
            # (test_time, expected_start_hour, expected_end_hour)
            (datetime(2024, 1, 1, 7, 30), 6, 14),   # Morning window
            (datetime(2024, 1, 1, 15, 0), 14, 22),  # Afternoon window
            (datetime(2024, 1, 1, 23, 0), 22, 6),   # Evening window (crosses midnight)
            (datetime(2024, 1, 1, 3, 0), 22, 6),    # Evening window (after midnight)
        ]
        
        for test_time, expected_start, expected_end in test_cases:
            start, end = self.get_current_window(test_time)
            
            assert start.hour == expected_start
            if expected_end == 6 and expected_start == 22:
                # Handle midnight crossing
                assert end.hour == expected_end
                assert end.day == start.day + 1
            else:
                assert end.hour == expected_end
    
    def test_window_creation(self, test_db):
        """Test window creation and retrieval"""
        current_time = datetime(2024, 1, 1, 10, 0)  # 10 AM
        
        # Create window
        window_id1 = self.create_or_get_window(test_db, current_time)
        assert window_id1 > 0
        
        # Get same window again
        window_id2 = self.create_or_get_window(test_db, current_time)
        assert window_id1 == window_id2
        
        # Different time in same window
        later_time = datetime(2024, 1, 1, 13, 0)  # 1 PM
        window_id3 = self.create_or_get_window(test_db, later_time)
        assert window_id1 == window_id3
    
    def test_article_aggregation(self, test_db):
        """Test adding articles to windows"""
        current_time = datetime(2024, 1, 1, 10, 0)
        window_id = self.create_or_get_window(test_db, current_time)
        
        # Add articles
        articles = [
            ("http://example.com/1", "Article 1", 8.5, True),
            ("http://example.com/2", "Article 2", 6.0, False),
            ("http://example.com/3", "Article 3", 9.0, True),
        ]
        
        for url, title, score, created_note in articles:
            self.add_article_to_window(test_db, window_id, url, title, score, created_note)
        
        # Check window stats
        cursor = test_db.cursor()
        cursor.execute("""
            SELECT article_count, note_count 
            FROM aggregation_windows 
            WHERE window_id = ?
        """, (window_id,))
        
        article_count, note_count = cursor.fetchone()
        assert article_count == 3
        assert note_count == 2
    
    def test_digest_trigger_timing(self, test_db):
        """Test digest trigger at window boundaries"""
        # Create window for morning (6am-2pm)
        window_time = datetime(2024, 1, 1, 10, 0)
        window_id = self.create_or_get_window(test_db, window_time)
        
        # Before window end - no trigger
        assert not self.should_trigger_digest(test_db, datetime(2024, 1, 1, 13, 59))
        
        # After window end - should trigger
        assert self.should_trigger_digest(test_db, datetime(2024, 1, 1, 14, 1))
        
        # Mark as sent
        cursor = test_db.cursor()
        cursor.execute("""
            UPDATE aggregation_windows 
            SET digest_sent = 1 
            WHERE window_id = ?
        """, (window_id,))
        test_db.commit()
        
        # Should not trigger again
        assert not self.should_trigger_digest(test_db, datetime(2024, 1, 1, 14, 30))
    
    def test_window_boundaries(self):
        """Test exact window boundary handling"""
        # Exactly at boundary
        boundary_time = datetime(2024, 1, 1, 14, 0, 0)
        start, end = self.get_current_window(boundary_time)
        
        assert start.hour == 14
        assert end.hour == 22
    
    def test_midnight_crossing_window(self):
        """Test evening window that crosses midnight"""
        # Just after 10pm
        evening_time = datetime(2024, 1, 1, 22, 30)
        start, end = self.get_current_window(evening_time)
        
        assert start.date() == evening_time.date()
        assert start.hour == 22
        assert end.date() == evening_time.date() + timedelta(days=1)
        assert end.hour == 6
        
        # Just after midnight
        after_midnight = datetime(2024, 1, 2, 1, 0)
        start2, end2 = self.get_current_window(after_midnight)
        
        assert start2.date() == datetime(2024, 1, 1).date()
        assert start2.hour == 22
        assert end2.date() == after_midnight.date()
        assert end2.hour == 6
    
    def test_volume_handling(self, test_db):
        """Test handling expected volume (800 articles per window)"""
        import time
        
        current_time = datetime.now()
        window_id = self.create_or_get_window(test_db, current_time)
        
        # Simulate processing 800 articles
        start_time = time.time()
        
        for i in range(800):
            # ~50% create notes (400 notes)
            create_note = i % 2 == 0
            score = 5.0 + (i % 5)  # Scores 5-9
            
            self.add_article_to_window(
                test_db, window_id,
                f"http://example.com/article{i}",
                f"Article {i}",
                score,
                create_note
            )
        
        duration = time.time() - start_time
        
        # Should handle volume efficiently
        assert duration < 5.0, f"Processing 800 articles took {duration}s"
        
        # Verify counts
        cursor = test_db.cursor()
        cursor.execute("""
            SELECT article_count, note_count 
            FROM aggregation_windows 
            WHERE window_id = ?
        """, (window_id,))
        
        article_count, note_count = cursor.fetchone()
        assert article_count == 800
        assert note_count == 400