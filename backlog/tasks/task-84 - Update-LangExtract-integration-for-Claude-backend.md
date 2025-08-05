# Update LangExtract integration for Claude backend

**Status**: Not Started
**Priority**: Critical
**Category**: Strategic Update
**Effort**: 1 day

## Description
**STRATEGIC PIVOT**: Update entire LangExtract integration strategy (Tasks 71-80) to use Claude API keys instead of Gemini, leveraging our existing infrastructure and superior Claude reasoning capabilities.

## Why This Changes Everything

### 1. **Unified API Strategy**
- **Single billing**: Use existing Claude API credits
- **Consistent authentication**: Same API keys across all tools  
- **Unified rate limiting**: Integrate with Task 83 (intelligent rate limit management)
- **Familiar error handling**: Leverage existing Claude retry logic

### 2. **Superior Quality with Known Models**
- **Claude's code understanding**: Better tool/technology extraction
- **Familiar reasoning patterns**: We know Claude's strengths/weaknesses
- **Proven performance**: Claude already works well in our pipeline
- **Tiered intelligence ready**: Direct integration with Task 81

### 3. **Cost and Complexity Reduction**
- **No new API setup**: Reuse existing Anthropic credentials
- **Single vendor relationship**: Reduce dependency complexity
- **Predictable costs**: Known pricing structure
- **Simplified monitoring**: Single API to track

## LangExtract Claude Configuration

### 1. **Model Mapping Strategy**
```python
# Map our tiered intelligence to LangExtract
langextract_claude_config = {
    # Tier 1: High-frequency, simple extraction
    "simple_extraction": {
        "model": "claude-3-haiku-20240307",
        "cost": "$0.25/$1.25 per MTok",
        "use_cases": ["basic RSS analysis", "simple tool detection"]
    },
    
    # Tier 2: Complex structured extraction  
    "balanced_extraction": {
        "model": "claude-3-5-sonnet-20241022", 
        "cost": "$3/$15 per MTok",
        "use_cases": ["YouTube analysis", "research papers", "GitHub repos"]
    },
    
    # Tier 3: Strategic analysis and complex reasoning
    "premium_extraction": {
        "model": "claude-3-opus-20240229",
        "cost": "$15/$75 per MTok", 
        "use_cases": ["architectural decisions", "complex task synthesis"]
    }
}
```

### 2. **Implementation Configuration**
```python
import langextract as lx
import os

# Configure LangExtract for Claude backend
def configure_langextract_claude():
    lx.configure(
        # Use Anthropic instead of Google
        model_provider="anthropic",
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        
        # Default to Sonnet for balanced performance
        default_model="claude-3-5-sonnet-20241022",
        
        # Integration settings
        max_retries=3,
        timeout=120,
        
        # Cost optimization
        enable_caching=True,
        batch_processing=True
    )

# Dynamic model selection based on task complexity
def select_claude_model(task_complexity, content_length):
    if content_length < 1000 and task_complexity < 0.3:
        return "claude-3-haiku-20240307"
    elif task_complexity > 0.8 or content_length > 10000:
        return "claude-3-opus-20240229"  
    else:
        return "claude-3-5-sonnet-20241022"
```

## Updated Task Integration

### 1. **RSS Processing (Task 74)**
```python
# Enhanced RSS with Claude-powered LangExtract
def process_rss_with_claude_langextract(article_content):
    result = lx.extract(
        text_or_documents=article_content,
        model_id="claude-3-5-sonnet-20241022",  # Our proven workhorse
        prompt_description="Extract tools, technologies, actionable tasks, and strategic insights",
        examples=rss_few_shot_examples,
        source_grounding=True
    )
    
    return {
        "structured_data": result.extractions,
        "source_references": result.source_spans,
        "confidence": result.confidence_score,
        "cost_tracking": track_claude_usage(result)
    }
```

### 2. **Intelligent Model Routing (Integrates with Task 81)**
```python
class ClaudeLangExtractRouter:
    def __init__(self):
        self.tier_mapping = {
            "haiku": "claude-3-haiku-20240307",
            "sonnet": "claude-3-5-sonnet-20241022", 
            "opus": "claude-3-opus-20240229"
        }
        
    def route_extraction(self, content, task_type):
        # Use our existing agent intelligence tiering
        if task_type in ["capture", "link", "monitor"]:
            model = self.tier_mapping["haiku"]
        elif task_type in ["rss", "email", "code"]:
            model = self.tier_mapping["sonnet"] 
        else:  # planning, research, quality
            model = self.tier_mapping["opus"]
            
        return lx.extract(
            text_or_documents=content,
            model_id=model,
            # ... rest of config
        )
```

## Integration Points with Existing Tasks

### 1. **Rate Limit Management (Task 83)**
- **Unified detection**: Same rate limit monitoring across LangExtract + direct Claude usage
- **Smart fallbacks**: When Claude limits hit, LangExtract can fall back to Gemini temporarily
- **Queue integration**: LangExtract requests join same intelligent queue system

### 2. **Cost Optimization (Task 80)**
- **Single cost tracking**: Monitor all Claude usage in one place
- **Budget integration**: LangExtract costs count toward overall Claude budget
- **Model selection**: Use cost-aware routing for LangExtract model choice

### 3. **Quality Monitoring (Task 79)**
- **Consistent benchmarks**: Compare LangExtract Claude vs legacy Claude extraction
- **Familiar quality patterns**: We know what good Claude output looks like
- **A/B testing**: LangExtract Claude vs direct Claude prompting

## Implementation Plan

### Phase 1: Configuration Update (Day 1)
- [ ] Update all LangExtract tasks (71-80) to specify Claude backend
- [ ] Create Claude-specific few-shot examples
- [ ] Test basic LangExtract + Claude integration  
- [ ] Validate API key and authentication setup

### Phase 2: Integration Testing (Day 1)  
- [ ] Run Task 73 (proof of concept) with Claude backend
- [ ] Compare Claude LangExtract vs Gemini LangExtract
- [ ] Verify cost tracking and rate limiting integration
- [ ] Test model switching between Haiku/Sonnet/Opus

## Expected Benefits

### 1. **Strategic Alignment**
- **Single vendor strategy**: Reduce complexity, focus on Claude mastery
- **Consistent experience**: Same quality patterns across all extraction
- **Unified infrastructure**: Rate limits, cost tracking, error handling

### 2. **Quality Improvements**  
- **Better code understanding**: Claude excels at technical content
- **Consistent reasoning**: Familiar Claude patterns in structured format
- **Source grounding**: Claude context + LangExtract precision

### 3. **Cost Optimization**
- **Volume discounts**: Higher Claude usage may unlock better pricing
- **Simplified billing**: Single invoice, easier budget management
- **Predictable costs**: No surprise Gemini charges

## Dependencies
- Anthropic API key with sufficient credits
- LangExtract library supports Anthropic backend (needs verification)
- Tasks 71-80 need documentation updates
- Integration testing environment

## Success Criteria
- All LangExtract tasks updated to use Claude backend
- Proof of concept shows equal or better quality vs Gemini
- Cost tracking integration working correctly
- Rate limit management unified across all Claude usage
- No performance degradation vs current system

## Notes
- This is a **strategic pivot** that affects all 10 LangExtract tasks
- Priority should be **Critical** as it simplifies entire integration
- May unlock better pricing through consolidated Claude usage
- Reduces vendor complexity and improves system reliability