# Create PostgreSQL schema for RSS tracking

**Status**: Not Started
**Priority**: High
**Category**: Database/Migration
**Effort**: 2 hours

## Description
Implement the PostgreSQL database schema designed for RSS state tracking, aggregation windows, and task extraction.

## Tasks
- [ ] Create database and user for RSS system
- [ ] Implement processed_articles table
- [ ] Implement aggregation_windows table
- [ ] Implement extracted_tasks table
- [ ] Implement semantic_clusters table
- [ ] Implement email_digests table
- [ ] Create indexes for performance
- [ ] Add foreign key constraints
- [ ] Create initial test data

## Schema
```sql
-- See /02-docs/RSS-N8N-MIGRATION-COMPREHENSIVE-PLAN.md for full schema
CREATE TABLE processed_articles (
    url VARCHAR(512) PRIMARY KEY,
    title TEXT NOT NULL,
    processed_at TIMESTAMP DEFAULT NOW(),
    score FLOAT DEFAULT 0.0,
    cluster VARCHAR(100),
    obsidian_note_path TEXT,
    summary TEXT,
    source_feed VARCHAR(255)
);
-- Additional tables...
```

## Dependencies
- Task 54: n8n Docker environment set up

## Success Criteria
- All tables created successfully
- Test data can be inserted and queried
- Performance indexes in place
- Schema matches TDD test expectations