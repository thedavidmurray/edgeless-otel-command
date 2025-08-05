# Replace RSS extraction with LangExtract

**Status**: Not Started
**Priority**: High
**Category**: Development/Integration
**Effort**: 3 days

## Description
Replace current RSS article extraction methods with LangExtract-powered structured extraction using Claude backend, including interactive validation and fallback mechanisms.

## Current RSS Pipeline Analysis
- Current tool: `/claude-vault/vault_agents/agents/rss_enhanced_fixed.py`
- Processing: 50/265 articles (18.9% coverage)
- Method: Priority pattern matching + basic LLM summarization
- Output: Obsidian notes with minimal structure

## LangExtract Integration Points

### 1. Replace Core Extraction Logic
- [ ] Identify extraction functions in `rss_enhanced_fixed.py`
- [ ] Replace priority scoring with LangExtract structured analysis
- [ ] Implement schema-based tool/technology detection
- [ ] Add structured task generation with confidence scores

### 2. Enhanced Processing Pipeline
```python
# New extraction workflow
def extract_with_langextract(article_content, article_url):
    result = lx.extract(
        text_or_documents=article_content,
        prompt_description="Extract tools, tasks, urgency from tech article",
        examples=rss_few_shot_examples,
        model_id="claude-3-haiku-20240307"
    )
    
    return {
        "structured_data": result.extractions,
        "source_grounding": result.source_spans,
        "confidence_score": calculate_confidence(result),
        "interactive_html": result.to_html()
    }
```

### 3. Obsidian Note Enhancement
- [ ] Update note templates with structured metadata
- [ ] Add source grounding links to original text
- [ ] Include confidence scores for manual validation
- [ ] Embed interactive HTML views (optional)

### 4. Quality Validation System
- [ ] Implement automatic quality checks
- [ ] Add manual validation workflow for low-confidence extractions
- [ ] Create feedback loop for schema improvement
- [ ] Build extraction quality dashboard

### 5. Fallback and Error Handling
- [ ] Detect LangExtract failures or low confidence
- [ ] Fallback to current extraction method
- [ ] Log failure patterns for schema improvement
- [ ] Implement retry logic with backoff

## Integration Strategy

### Phase 1: Parallel Processing (Week 1)
- [ ] Run both old and new extraction methods
- [ ] Compare results side-by-side
- [ ] Collect quality metrics and feedback
- [ ] Refine schemas based on real data

### Phase 2: Gradual Cutover (Week 2)
- [ ] Use LangExtract for high-confidence articles
- [ ] Fallback to old method for edge cases
- [ ] Monitor performance and costs
- [ ] Build operator confidence

### Phase 3: Full Replacement (Week 3)
- [ ] Switch to LangExtract as primary method
- [ ] Keep old method as emergency fallback
- [ ] Optimize for performance and cost
- [ ] Document new operational procedures

## Expected Improvements
- **Coverage**: 18.9% → 80%+ articles processed
- **Task Quality**: Basic pattern matching → Structured with confidence
- **Tool Detection**: ~60% → 90%+ accuracy
- **Source Traceability**: None → Character-level precision
- **Validation**: Manual → Interactive HTML + confidence scores

## Cost Management
- [ ] Implement usage monitoring and alerts
- [ ] Set daily/monthly API limits
- [ ] Create cost per article metrics
- [ ] Compare total cost vs manual curation savings

## Success Criteria
- RSS processing quality significantly improved
- Interactive validation working smoothly
- Fallback mechanisms tested and reliable
- Costs within acceptable range (<$50/month)
- Team satisfied with extraction quality

## Dependencies
- Task 73: Proof of concept validates approach
- Claude API quotas sufficient for RSS volume
- Updated Obsidian note templates

## Notes
- Start with recent high-quality articles
- Monitor API rate limits during testing
- Keep old extraction code until fully validated