# Build podcast transcription pipeline

**Status**: Not Started
**Priority**: Medium
**Category**: Ingestion/Audio
**Effort**: 5 days

## Description
Implement automated podcast monitoring and transcription system to extract insights from long-form technical discussions and interviews.

## Target Podcasts
### AI/ML Focused
- Latent Space (AI engineering, LLM applications)
- The Gradient (ML research)
- TWIML AI (This Week in Machine Learning)
- Lex Fridman (AI/tech interviews)

### Developer/Tech
- Changelog (open source, developer tools)
- CoRecursive (deep technical stories)
- Software Engineering Daily
- The Bike Shed (thoughtbot)

### Productivity/Tools
- Obsidian Roundup (community podcast)
- Automation/n8n podcasts
- Developer productivity shows

## Tasks
- [ ] Set up podcast RSS feed parsing
- [ ] Implement audio download system:
  - [ ] Handle various audio formats
  - [ ] Manage storage and cleanup
  - [ ] Resume interrupted downloads
- [ ] Build transcription pipeline:
  - [ ] Whisper API integration
  - [ ] Speaker diarization
  - [ ] Timestamp alignment
  - [ ] Quality validation
- [ ] Create content extraction:
  - [ ] Chapter/topic detection
  - [ ] Key insight extraction
  - [ ] Quote identification
  - [ ] Tool/resource mentions
  - [ ] Action item extraction
- [ ] Implement Obsidian note structure:
  - [ ] Episode metadata
  - [ ] Timestamped chapters
  - [ ] Speaker-attributed quotes
  - [ ] Key takeaways
  - [ ] Mentioned resources
  - [ ] Generated tasks
- [ ] Build smart filtering:
  - [ ] Episode relevance scoring
  - [ ] Topic-based selection
  - [ ] Duration preferences
  - [ ] Guest-based filtering

## Technical Implementation
- Python with feedparser for RSS
- Whisper API for transcription
- Pyannote for speaker diarization
- NLTK/spaCy for content extraction

## Success Criteria
- Processes new episodes within 24h
- >95% transcription accuracy
- Accurate speaker attribution
- Extracts 3-5 key insights per episode
- Identifies all mentioned tools/resources

## Storage Estimates
- ~100MB per hour of audio
- ~10KB per minute of transcript
- Target: 10-20 episodes/week

## Dependencies
- Whisper API access
- Storage for audio files
- PostgreSQL for episode tracking

## Notes
- Consider implementing highlight reels
- May want YouTube video podcast support
- Could integrate with voice note system