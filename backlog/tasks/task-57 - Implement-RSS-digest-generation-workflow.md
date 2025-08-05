# Implement RSS digest generation workflow

**Status**: Not Started
**Priority**: Medium
**Category**: Development/Migration
**Effort**: 6 hours

## Description
Build the digest generation workflow that creates aggregated summaries from 8-hour windows of RSS processing.

## Tasks
- [ ] Import digest-generation-workflow.json
- [ ] Configure schedule triggers (6am, 2pm, 10pm)
- [ ] Set up window completion detection
- [ ] Implement digest template formatting
- [ ] Configure email sending (SMTP)
- [ ] Set up Obsidian archive paths
- [ ] Add Telegram bot integration (optional)
- [ ] Test digest generation with sample data
- [ ] Validate email formatting
- [ ] Ensure window marking works correctly

## Digest Sections
1. Executive Summary
2. Trending Topics (by cluster)
3. Key Insights (top scored articles)
4. Actionable Tasks (by priority)
5. Notable Articles (by category)

## Dependencies
- Task 56: RSS ingestion workflow working
- Email system configuration available

## Success Criteria
- Digests generated at correct times
- Email formatting is clean and readable
- All window data properly aggregated
- Tasks correctly prioritized
- Windows marked as processed