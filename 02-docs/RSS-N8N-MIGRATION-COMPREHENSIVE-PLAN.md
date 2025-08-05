# Comprehensive RSS to n8n Migration Plan with TDD

## Executive Summary

Transform the current Python-based RSS agent into a robust n8n workflow system with aggregated summaries, automated task extraction, and multi-channel distribution. This migration will replace 48 daily individual emails with 3 comprehensive digests while building a passive knowledge base in Obsidian.

## Architecture Overview

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   RSS Sources   │────>│ n8n Pipeline │────>│ Obsidian Vault  │
│   (20+ feeds)   │     │  (30 min)    │     │ (Knowledge Base)│
└─────────────────┘     └──────┬───────┘     └─────────────────┘
                               │
                               v
                     ┌─────────────────┐
                     │  State Database │
                     │  (PostgreSQL)   │
                     └────────┬────────┘
                              │
                              v
                   ┌──────────────────────┐
                   │ Aggregation Windows  │
                   │ (8-hour intervals)   │
                   └──────────┬───────────┘
                              │
                              v
                 ┌────────────────────────────┐
                 │     Multi-Channel Output   │
                 ├────────────────────────────┤
                 │ • Email Digest (Primary)   │
                 │ • Telegram Bot (Optional)  │
                 │ • Static Blog (Future)     │
                 └────────────────────────────┘
```

## Phase 1: Core Infrastructure (Week 1)

### 1.1 n8n Setup
- Deploy n8n using Docker
- Configure persistent storage
- Set up PostgreSQL database
- Create development environment

### 1.2 Database Schema

```sql
-- Core tracking tables
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

CREATE TABLE aggregation_windows (
    window_id SERIAL PRIMARY KEY,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    article_count INT DEFAULT 0,
    note_count INT DEFAULT 0,
    digest_sent BOOLEAN DEFAULT FALSE
);

CREATE TABLE extracted_tasks (
    task_id SERIAL PRIMARY KEY,
    article_url VARCHAR(512) REFERENCES processed_articles(url),
    task_description TEXT NOT NULL,
    priority VARCHAR(20),
    backlog_status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE semantic_clusters (
    cluster_name VARCHAR(100) PRIMARY KEY,
    article_count INT DEFAULT 0,
    last_seen TIMESTAMP DEFAULT NOW(),
    trending_score FLOAT DEFAULT 0.0
);

CREATE TABLE email_digests (
    digest_id SERIAL PRIMARY KEY,
    window_id INT REFERENCES aggregation_windows(window_id),
    sent_at TIMESTAMP DEFAULT NOW(),
    recipient VARCHAR(255),
    email_content_hash VARCHAR(64),
    subject_line TEXT
);
```

### 1.3 Test Suite Foundation

```python
# tests/test_rss_pipeline.py
class TestRSSPipeline:
    def test_deduplication_accuracy(self):
        """Ensure no duplicate articles are processed"""
        
    def test_scoring_algorithm(self):
        """Validate article scoring matches priority patterns"""
        
    def test_obsidian_note_format(self):
        """Verify markdown output meets vault standards"""
        
    def test_database_consistency(self):
        """Check state tracking across pipeline stages"""
```

## Phase 2: Processing Pipeline (Week 2)

### 2.1 n8n Workflow Components

```
[Schedule Trigger] Every 30 minutes
         │
         v
[RSS Multi-Feed Reader] Parallel fetch from 20+ sources
         │
         v
[Deduplication Node] Query processed_articles table
         │
         v
[Article Scorer] Apply priority patterns
         │
         ├─> Score >= 7.0 ──> [Deep Analysis Branch]
         │                           │
         │                           v
         │                    [AI Summarizer]
         │                           │
         v                           v
[Semantic Clustering] <──────────────┘
         │
         v
[Obsidian Note Creator] Generate markdown with frontmatter
         │
         v
[Task Extractor] Pattern matching for actionable items
         │
         v
[State Updater] Write to all tracking tables
         │
         v
[Aggregation Checker] Trigger digest if window complete
```

### 2.2 Scoring Algorithm

```javascript
// Priority patterns with weights
const priorityPatterns = {
    "security|vulnerability|cve": 3.0,
    "zero.?day|breach|exploit": 3.5,
    "gpt.?5|claude|anthropic": 2.5,
    "breakthrough|paper|research": 2.0,
    "release|update|new.?feature": 1.5,
    "obsidian|plugin": 2.0,
    "python|rust|performance": 1.5,
    "trend|analysis|insight": 1.0
};

// Calculate composite score
function scoreArticle(title, content, source) {
    let score = baseScore;
    for (const [pattern, weight] of Object.entries(priorityPatterns)) {
        if (new RegExp(pattern, 'i').test(title + ' ' + content)) {
            score += weight;
        }
    }
    // Boost for reputable sources
    if (reputableSources.includes(source)) {
        score += 2.0;
    }
    return Math.min(score, 10.0);
}
```

### 2.3 Task Extraction Patterns

```yaml
task_patterns:
  - pattern: "implement|build|create|develop"
    category: "development"
    priority: "medium"
  
  - pattern: "fix|resolve|debug|troubleshoot"
    category: "bugfix"
    priority: "high"
  
  - pattern: "optimize|improve|enhance|refactor"
    category: "optimization"
    priority: "medium"
  
  - pattern: "security|vulnerability|patch|update"
    category: "security"
    priority: "critical"
```

## Phase 3: Aggregation System (Week 3)

### 3.1 Timing Strategy

```
Daily Schedule (3 digests):
├─ Morning Digest:   6:00 AM  (22:00-06:00 window)
├─ Afternoon Digest: 2:00 PM  (06:00-14:00 window)
└─ Evening Digest:   10:00 PM (14:00-22:00 window)

Expected Volume per Digest:
- Articles processed: ~800
- Obsidian notes created: ~400
- Tasks extracted: 10-20
- Clusters identified: 5-10
```

### 3.2 Digest Generation Workflow

```
[Window Completion Trigger]
         │
         v
[Aggregate Data Collector]
         │
         ├─> Fetch articles from window
         ├─> Collect generated notes
         └─> Gather extracted tasks
         │
         v
[Trend Analyzer]
         │
         ├─> Compare to previous windows
         └─> Calculate trending scores
         │
         v
[Content Prioritizer]
         │
         ├─> Rank by composite score
         ├─> Group by semantic cluster
         └─> Highlight actionable tasks
         │
         v
[Digest Composer]
         │
         ├─> Key Insights section
         ├─> Trending Topics section
         ├─> Actionable Tasks section
         └─> Notable Articles section
         │
         v
[Multi-format Generator]
         │
         ├─> HTML Email version
         ├─> Markdown for Obsidian
         └─> JSON for API/Telegram
         │
         v
[Delivery Dispatcher]
```

### 3.3 Digest Template

```markdown
# RSS Intelligence Digest - [Date] [Time Period]

## Executive Summary
- Articles analyzed: [count]
- Key insights extracted: [count]
- Actionable tasks identified: [count]
- Trending topics: [list]

## Key Insights
1. **[Insight Title]** (Score: X.X)
   - Summary: [AI-generated summary]
   - Source: [Feed name]
   - Why it matters: [Relevance explanation]
   - [Link to Obsidian note]

## Trending Topics
### [Cluster Name] ([count] articles)
- Top articles: [List of 3-5]
- Key themes: [Extracted patterns]
- Growth rate: [+X% vs previous window]

## Actionable Tasks
Priority: Critical
- [ ] [Task description] - Related: [Article title]

Priority: High
- [ ] [Task description] - Related: [Article title]

## Notable Articles by Category
### Security & Vulnerabilities
- [Article 1] - [Brief description]

### AI & Research
- [Article 1] - [Brief description]

### Tools & Productivity
- [Article 1] - [Brief description]

---
*Next digest: [Time] | Articles in queue: [count]*
```

## Phase 4: Production Hardening (Week 4)

### 4.1 Error Recovery

```javascript
// Retry logic for each pipeline stage
const retryConfig = {
    maxRetries: 3,
    retryDelay: 1000,
    backoffMultiplier: 2,
    
    criticalNodes: ['RSS Feed Reader', 'State Updater'],
    
    errorHandlers: {
        'NetworkError': 'retry_with_backoff',
        'DatabaseError': 'alert_and_retry',
        'AIRateLimit': 'queue_for_later',
        'ValidationError': 'log_and_skip'
    }
};
```

### 4.2 Monitoring & Alerts

```yaml
monitoring:
  metrics:
    - processing_time_per_article
    - articles_per_minute
    - error_rate_by_node
    - ai_token_usage
    - database_query_time
  
  alerts:
    - condition: "processing_time > 20 minutes"
      action: "email_alert"
      
    - condition: "error_rate > 10%"
      action: "pause_and_alert"
      
    - condition: "no_execution_for_60_minutes"
      action: "restart_workflow"
```

### 4.3 Performance Optimization

```
Optimization Strategies:
1. Batch Processing
   - Group articles by source
   - Bulk database operations
   - Parallel AI requests

2. Caching
   - Cache semantic clusters
   - Store AI summaries
   - Reuse scoring results

3. Resource Management
   - Limit concurrent connections
   - Implement request pooling
   - Monitor memory usage
```

## Testing Strategy

### Unit Tests
```python
# Each n8n node has corresponding tests
- test_rss_feed_parser()
- test_deduplication_logic()
- test_scoring_algorithm()
- test_clustering_accuracy()
- test_task_extraction()
```

### Integration Tests
```python
# Test pipeline segments
- test_ingestion_to_processing()
- test_processing_to_storage()
- test_storage_to_aggregation()
- test_aggregation_to_delivery()
```

### End-to-End Tests
```python
# Full workflow validation
- test_complete_pipeline_with_100_articles()
- test_digest_generation_accuracy()
- test_multi_window_aggregation()
- test_failure_recovery_scenarios()
```

### Performance Tests
```python
# Stress testing
- test_500_articles_in_15_minutes()
- test_concurrent_feed_processing()
- test_database_under_load()
- test_ai_rate_limiting()
```

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Uptime | 99%+ | Workflow execution logs |
| Processing Time | <15 min/batch | n8n execution history |
| Task Relevance | 90%+ | Manual review sampling |
| Digest Quality | High satisfaction | User feedback |
| Cost Efficiency | <$50/month | AI token usage tracking |

## Migration Checklist

### Pre-Migration
- [ ] Backup current RSS agent configuration
- [ ] Document all RSS feed sources
- [ ] Export processed URLs history
- [ ] Test n8n installation

### During Migration
- [ ] Run parallel for 2 weeks
- [ ] Compare outputs daily
- [ ] Monitor error rates
- [ ] Gather user feedback

### Post-Migration
- [ ] Decommission Python agent
- [ ] Archive old logs
- [ ] Document new procedures
- [ ] Train on n8n interface

## Implementation Timeline

```
Week 1: Infrastructure
├─ Day 1-2: n8n setup & database
├─ Day 3-4: Basic RSS workflow
└─ Day 5-7: Unit tests & validation

Week 2: Core Pipeline
├─ Day 1-2: Scoring & clustering
├─ Day 3-4: AI integration
└─ Day 5-7: Task extraction

Week 3: Aggregation
├─ Day 1-2: Window management
├─ Day 3-4: Digest templates
└─ Day 5-7: Email integration

Week 4: Production
├─ Day 1-2: Error handling
├─ Day 3-4: Performance tuning
└─ Day 5-7: Parallel running
```

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| AI API limits | High | Implement caching, selective processing |
| Database failure | High | Regular backups, replication |
| n8n crashes | Medium | Auto-restart, state recovery |
| Poor summarization | Medium | A/B testing, quality metrics |
| Email delivery | Low | Multiple channels, fallbacks |

## Future Enhancements

1. **Telegram Bot Integration**
   - Real-time alerts for critical articles
   - On-demand digest requests
   - Task acknowledgment system

2. **Static Blog Generation**
   - Public knowledge sharing
   - SEO-optimized content
   - RSS feed of digests

3. **Advanced Analytics**
   - Trend prediction
   - Source quality scoring
   - Reading time optimization

4. **Collaborative Features**
   - Team digest sharing
   - Task assignment
   - Comment threads

## Conclusion

This comprehensive migration plan transforms the RSS ingestion system from a simple feed processor into an intelligent knowledge management platform. By leveraging n8n's visual workflows, robust state management, and multi-channel distribution, we create a reliable, scalable, and insightful system that surfaces actionable intelligence while building a permanent knowledge base.