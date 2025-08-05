# Build n8n RSS ingestion workflow

**Status**: Not Started
**Priority**: High
**Category**: Development/Migration
**Effort**: 8 hours

## Description
Implement the main RSS ingestion workflow in n8n based on the designed architecture and workflow JSON.

## Tasks
- [ ] Import rss-ingestion-workflow.json
- [ ] Configure RSS feed sources (20+ feeds)
- [ ] Set up PostgreSQL connections
- [ ] Configure AI summarization (OpenAI/Anthropic)
- [ ] Set up Obsidian file creation paths
- [ ] Implement error handling nodes
- [ ] Configure retry logic
- [ ] Test with sample RSS feeds
- [ ] Validate deduplication works
- [ ] Verify scoring algorithm accuracy

## Components
1. Schedule Trigger (every 30 min)
2. RSS Multi-Feed Reader
3. Deduplication Check
4. Article Scorer
5. Deep Analysis Router
6. AI Summarizer
7. Task Extractor
8. Obsidian Note Creator
9. State Updater

## Dependencies
- Task 55: PostgreSQL schema created
- TDD tests passing for core logic

## Success Criteria
- Workflow executes without errors
- Articles are properly deduplicated
- Scoring matches Python agent logic
- Obsidian notes created correctly
- Database state updated accurately