# Enhance n8n workflows with LangExtract

**Status**: Not Started
**Priority**: High
**Category**: Integration/Automation
**Effort**: 2 days

## Description
Integrate LangExtract with Claude backend into the n8n RSS migration workflows (Tasks 54-58) to provide structured extraction, validation nodes, and cost monitoring.

## n8n Workflow Integration Points

### 1. RSS Ingestion Workflow Enhancement (Task 56)
- [ ] Replace basic summarization node with LangExtract extraction
- [ ] Add structured output validation nodes
- [ ] Implement confidence-based routing (high → auto-process, low → manual review)
- [ ] Add source grounding data to PostgreSQL schema

### 2. New LangExtract Nodes
```javascript
// Custom n8n node structure
{
  "name": "LangExtract Processor",
  "inputs": ["article_content", "extraction_schema"],
  "outputs": {
    "structured_data": "json",
    "source_grounding": "array",
    "confidence_score": "number",
    "html_visualization": "string"
  },
  "settings": {
    "model": "claude-3-haiku-20240307",
    "max_retries": 3,
    "fallback_enabled": true
  }
}
```

### 3. Quality Control Workflow
- [ ] Add confidence score evaluation node
- [ ] Route low-confidence extractions to manual review queue
- [ ] Create feedback collection mechanism
- [ ] Build quality metrics aggregation

### 4. Cost Monitoring Integration
- [ ] Track API usage per extraction
- [ ] Monitor daily/monthly spend limits
- [ ] Alert on cost threshold breaches
- [ ] Generate cost efficiency reports

### 5. Enhanced Database Schema (Task 55 Update)
```sql
-- Add LangExtract columns to processed_articles
ALTER TABLE processed_articles ADD COLUMN langextract_data JSONB;
ALTER TABLE processed_articles ADD COLUMN confidence_score FLOAT;
ALTER TABLE processed_articles ADD COLUMN extraction_method VARCHAR(50);
ALTER TABLE processed_articles ADD COLUMN api_cost_cents INTEGER;
ALTER TABLE processed_articles ADD COLUMN source_grounding JSONB;

-- New quality tracking table
CREATE TABLE extraction_quality (
    id SERIAL PRIMARY KEY,
    article_url VARCHAR(512) REFERENCES processed_articles(url),
    manual_validation_score INTEGER, -- 1-5 rating
    extraction_accuracy FLOAT,
    feedback_notes TEXT,
    validated_at TIMESTAMP DEFAULT NOW()
);
```

### 6. Digest Generation Enhancement (Task 57)
- [ ] Use structured data for better digest formatting
- [ ] Group by extracted topics and tool categories
- [ ] Include confidence indicators in summaries
- [ ] Add interactive HTML sections to emails

## Workflow Architecture

### Enhanced RSS Processing Flow
```
RSS Feeds → Article Fetcher → LangExtract Processor → Quality Router
                                       ↓
                              [High Confidence] → Auto-process → Obsidian
                                       ↓
                              [Low Confidence] → Manual Review → Obsidian
                                       ↓
                              [Failed] → Fallback Processor → Obsidian
```

### Quality Feedback Loop
```
Processed Articles → Quality Validator → Feedback Collector → Schema Refiner
                                           ↓
                            Update Few-shot Examples ← Performance Monitor
```

## Implementation Tasks
- [ ] Create custom LangExtract n8n node
- [ ] Update existing RSS workflow JSON
- [ ] Implement confidence-based routing logic
- [ ] Add PostgreSQL schema updates
- [ ] Build quality monitoring dashboard
- [ ] Create cost tracking and alerting
- [ ] Test parallel processing capabilities

## Integration Strategy
1. **Development**: Build and test custom nodes locally
2. **Staging**: Deploy to n8n test environment
3. **Validation**: Run parallel with existing workflows
4. **Production**: Gradual rollout with monitoring

## Performance Targets
- **Processing Speed**: <30s per article (including API calls)
- **Success Rate**: 95%+ successful extractions
- **Cost Efficiency**: <$0.02 per article processed
- **Quality Score**: 80%+ confidence on auto-processed articles

## Monitoring and Alerts
- [ ] API usage and cost tracking
- [ ] Extraction quality metrics
- [ ] Processing time and success rates
- [ ] Manual review queue depth
- [ ] Daily/weekly quality reports

## Dependencies
- Task 74: RSS extraction working with LangExtract
- Tasks 54-55: n8n environment and database ready
- Custom n8n node development capabilities

## Success Criteria
- n8n workflows successfully using LangExtract
- Quality routing working effectively
- Cost monitoring and alerts functional
- Structured data improving digest quality
- Manual review workload reduced by 80%

## Notes
- May need custom n8n node development
- Consider n8n Cloud vs self-hosted implications
- Plan for API rate limiting in workflow design