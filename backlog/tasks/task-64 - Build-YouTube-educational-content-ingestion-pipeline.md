# Build YouTube educational content ingestion pipeline

**Status**: Not Started
**Priority**: High
**Category**: Ingestion/Automation
**Effort**: 1 week

## Description
Implement yt-dlp based pipeline to ingest educational YouTube content with transcript extraction, timestamp mapping, and task generation from tutorials.

## Target Channels
- Fireship (web dev updates, quick tutorials)
- ThePrimeagen (developer workflow, vim, productivity)
- Anthropic (Claude updates, AI safety)
- OpenAI (GPT updates, API tutorials)
- n8n tutorials (workflow automation)
- Obsidian community (plugin demos, workflows)

## Tasks
- [ ] Install and configure yt-dlp
- [ ] Create YouTube URL ingestion endpoint
- [ ] Implement transcript extraction:
  - [ ] Use native captions when available
  - [ ] Fall back to Whisper API for auto-transcription
- [ ] Build timestamp extraction for key topics
- [ ] Create Obsidian note template for videos:
  - [ ] Video metadata (title, channel, date, duration)
  - [ ] Embedded video player
  - [ ] Timestamped transcript sections
  - [ ] Extracted key points
  - [ ] Generated tasks/actions
- [ ] Implement task extraction from tutorial content:
  - [ ] "In this tutorial we'll..." patterns
  - [ ] Command/code snippets
  - [ ] Tool recommendations
- [ ] Set up scheduled monitoring for new videos
- [ ] Create quality filters (min views, duration, etc.)

## Technical Requirements
- Python 3.9+ with yt-dlp
- Whisper API access for transcription
- ChromaDB for video content embedding
- PostgreSQL for tracking processed videos

## Success Criteria
- Can ingest video URL and create comprehensive note
- Extracts actionable tasks from tutorials
- Handles videos with/without captions
- Processes video in <60 seconds
- No duplicate processing

## Dependencies
- None (can run independently)

## Notes
- Consider rate limiting to avoid API quotas
- Cache transcripts to avoid re-processing
- May need YouTube API key for channel monitoring