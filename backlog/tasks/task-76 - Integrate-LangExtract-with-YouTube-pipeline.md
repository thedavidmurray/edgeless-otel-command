# Integrate LangExtract with YouTube pipeline

**Status**: Not Started
**Priority**: Medium
**Category**: Development/Enhancement
**Effort**: 2 days

## Description
Enhance the YouTube educational content ingestion pipeline (Task 64) with LangExtract-powered structured extraction using Claude backend for tools, tutorials, timestamps, and actionable tasks.

## Current YouTube Pipeline Status
- Tool: `youtube_ingestion_v1.py` (recently created)
- Capability: Basic metadata + transcript extraction
- Output: Obsidian notes with minimal structure
- Limitations: Basic regex pattern matching for tools/tasks

## LangExtract Enhancement Areas

### 1. Enhanced Content Analysis
```python
# Current vs Enhanced extraction
# Current: Basic regex patterns
tools = re.findall(r'\b(claude|chatgpt|python)\b', content)

# Enhanced: LangExtract structured analysis
result = lx.extract(
    text_or_documents=f"{title} {description} {transcript}",
    prompt_description="Extract educational content, tools, tutorial steps, and actionable tasks from video",
    examples=youtube_few_shot_examples,
    model_id="claude-3-haiku-20240307"
)
```

### 2. Timestamp-Aware Extraction
- [ ] Map extracted entities to transcript timestamps
- [ ] Create clickable links to specific video moments
- [ ] Build chapter detection for long tutorials
- [ ] Generate time-coded learning tasks

### 3. Tutorial Step Extraction
- [ ] Identify sequential instruction patterns
- [ ] Extract code examples with context
- [ ] Detect prerequisite mentions
- [ ] Generate step-by-step implementation tasks

### 4. Enhanced Obsidian Note Structure
```markdown
# Video Title

## Tools & Technologies (with timestamps)
- [[Docker]] (mentioned at 3:45, 12:30)
- [[Python]] (tutorial starts at 5:15)
- [[VS Code]] (setup at 2:10)

## Tutorial Steps (actionable tasks)
- [ ] **Setup Environment** (0:30-2:45)
  - Install Docker Desktop
  - Configure VS Code extensions
  - Clone repository from GitHub
  
- [ ] **Build Application** (5:15-8:30)
  - Create Dockerfile
  - Configure dependencies
  - Test local build

## Key Insights (with source grounding)
- "Best practice is to use multi-stage builds" (7:22-7:45)
- Performance tip about caching (15:30-16:00)

## Interactive Elements
[Embedded HTML visualization of extractions]
```

### 5. Content Categorization
- [ ] Detect tutorial vs discussion vs news
- [ ] Identify beginner vs advanced content
- [ ] Extract skill level requirements
- [ ] Generate appropriate tags and categories

## Implementation Strategy

### Phase 1: Enhance Existing Tool
- [ ] Modify `youtube_ingestion_v1.py` to use LangExtract
- [ ] Add YouTube-specific few-shot examples
- [ ] Implement timestamp mapping functionality
- [ ] Test with sample educational videos

### Phase 2: Advanced Features
- [ ] Add chapter detection and summarization
- [ ] Implement code extraction and formatting
- [ ] Build prerequisite detection
- [ ] Create learning path suggestions

### Phase 3: Integration & Automation
- [ ] Integrate with channel monitoring (auto-ingestion)
- [ ] Add quality scoring for educational value
- [ ] Build playlists and series detection
- [ ] Connect with other learning resources

## YouTube-Specific Extraction Schema
```python
youtube_schema = {
    "content_type": "tutorial|discussion|news|demo",
    "difficulty_level": "beginner|intermediate|advanced",
    "tutorial_steps": [
        {
            "step_number": 1,
            "description": "Setup development environment",
            "timestamp_start": "2:15",
            "timestamp_end": "4:30",
            "code_examples": ["docker run -p 3000:3000"],
            "prerequisites": ["Docker installed"]
        }
    ],
    "tools_timeline": [
        {
            "tool": "Docker",
            "first_mention": "1:45",
            "key_timestamps": ["1:45", "3:22", "7:15"],
            "context": "installation and configuration"
        }
    ],
    "actionable_tasks": [
        {
            "task": "Install Docker Desktop",
            "priority": "high",
            "prerequisite_for": ["container setup"],
            "referenced_at": "2:30"
        }
    ]
}
```

## Expected Improvements
- **Tool Detection**: Basic regex → Contextual understanding
- **Task Quality**: Generic → Specific with timestamps
- **Learning Value**: Passive consumption → Active task generation
- **Source Grounding**: None → Video timestamp precision
- **Content Understanding**: Surface-level → Deep structural analysis

## Integration with Existing Systems
- [ ] Enhanced Obsidian notes with interactive elements
- [ ] ChromaDB embedding of structured video data
- [ ] Task extraction feeding into backlog system
- [ ] Cross-reference with other learning materials

## Quality Metrics
- **Timestamp Accuracy**: 95%+ correct time references
- **Tutorial Step Coverage**: 90%+ of actual steps captured
- **Tool Detection**: 95%+ accuracy with context
- **Task Actionability**: 80%+ user completion rate

## Dependencies
- Task 73: LangExtract proof of concept successful
- Task 64: YouTube pipeline functional
- YouTube-specific few-shot examples developed

## Success Criteria
- YouTube videos generating structured, actionable content
- Timestamp links working accurately
- Tutorial steps clearly extracted and sequenced
- Integration with learning workflow effective
- Processing time acceptable (<2 minutes per video)

## Notes
- Focus on educational channels initially
- Consider video length limits for processing
- May need transcript chunking for very long videos