-- RLHF (Reinforcement Learning from Human Feedback) Schema Extension
-- Additional tables for tracking application outcomes and learning patterns

-- Table for storing various types of RLHF signals
CREATE TABLE IF NOT EXISTS rlhf_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    signal_type TEXT NOT NULL CHECK(signal_type IN ('keyword_match', 'application_outcome', 'user_feedback', 'response_time', 'rejection_reason')),
    signal_value TEXT NOT NULL, -- JSON data containing signal details
    confidence REAL DEFAULT 1.0 CHECK(confidence >= 0.0 AND confidence <= 1.0),
    weight REAL DEFAULT 1.0, -- Weight of this signal in learning
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES job_opportunities(id) ON DELETE CASCADE
);

-- Table for tracking keyword occurrences in job descriptions
CREATE TABLE IF NOT EXISTS keyword_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    keyword TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('ai_ml', 'tech_stack', 'seniority', 'domain', 'soft_skills', 'company_type')),
    frequency INTEGER DEFAULT 1 CHECK(frequency > 0),
    context TEXT, -- Surrounding text where keyword was found
    importance_score REAL DEFAULT 0.5 CHECK(importance_score >= 0.0 AND importance_score <= 1.0),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES job_opportunities(id) ON DELETE CASCADE
);

-- Table for storing aggregated targeting metrics over time
CREATE TABLE IF NOT EXISTS targeting_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    period TEXT NOT NULL CHECK(period IN ('daily', 'weekly', 'monthly')),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    metadata TEXT, -- JSON for additional metric context
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Table for tracking application outcomes and learning from them
CREATE TABLE IF NOT EXISTS application_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    application_id INTEGER, -- Reference to application_history
    outcome_type TEXT NOT NULL CHECK(outcome_type IN ('applied', 'viewed', 'response', 'interview', 'offer', 'rejection', 'ghosted')),
    outcome_value TEXT, -- Additional details about the outcome
    days_to_outcome INTEGER, -- How many days from application to this outcome
    success_score REAL CHECK(success_score >= 0.0 AND success_score <= 1.0), -- Calculated success metric
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES job_opportunities(id) ON DELETE CASCADE,
    FOREIGN KEY (application_id) REFERENCES application_history(id) ON DELETE SET NULL
);

-- Table for storing learned patterns and their effectiveness
CREATE TABLE IF NOT EXISTS learned_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT NOT NULL CHECK(pattern_type IN ('keyword_combo', 'company_trait', 'job_characteristic', 'timing_pattern')),
    pattern_description TEXT NOT NULL,
    pattern_data TEXT NOT NULL, -- JSON representation of the pattern
    success_rate REAL NOT NULL CHECK(success_rate >= 0.0 AND success_rate <= 1.0),
    sample_size INTEGER NOT NULL CHECK(sample_size > 0),
    confidence_level REAL NOT NULL CHECK(confidence_level >= 0.0 AND confidence_level <= 1.0),
    last_validated DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_rlhf_signals_job_id ON rlhf_signals(job_id);
CREATE INDEX IF NOT EXISTS idx_rlhf_signals_type ON rlhf_signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_rlhf_signals_created_at ON rlhf_signals(created_at);

CREATE INDEX IF NOT EXISTS idx_keyword_tracking_job_id ON keyword_tracking(job_id);
CREATE INDEX IF NOT EXISTS idx_keyword_tracking_keyword ON keyword_tracking(keyword);
CREATE INDEX IF NOT EXISTS idx_keyword_tracking_category ON keyword_tracking(category);

CREATE INDEX IF NOT EXISTS idx_targeting_metrics_name ON targeting_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_targeting_metrics_period ON targeting_metrics(period, period_start);

CREATE INDEX IF NOT EXISTS idx_application_outcomes_job_id ON application_outcomes(job_id);
CREATE INDEX IF NOT EXISTS idx_application_outcomes_type ON application_outcomes(outcome_type);
CREATE INDEX IF NOT EXISTS idx_application_outcomes_created_at ON application_outcomes(created_at);

CREATE INDEX IF NOT EXISTS idx_learned_patterns_type ON learned_patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_learned_patterns_active ON learned_patterns(is_active);
CREATE INDEX IF NOT EXISTS idx_learned_patterns_success_rate ON learned_patterns(success_rate DESC);

-- Triggers for updating timestamps
CREATE TRIGGER IF NOT EXISTS update_learned_patterns_updated_at 
    AFTER UPDATE ON learned_patterns
    FOR EACH ROW
BEGIN
    UPDATE learned_patterns SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;