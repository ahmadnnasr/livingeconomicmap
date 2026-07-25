PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    base_url TEXT,
    license_class TEXT NOT NULL DEFAULT 'public',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS series_registry (
    series_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    external_id TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    frequency TEXT NOT NULL,
    units TEXT NOT NULL,
    seasonal_adjustment TEXT,
    transformation_policy TEXT,
    revision_policy TEXT NOT NULL DEFAULT 'append_revision',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(source_id, external_id),
    FOREIGN KEY(source_id) REFERENCES sources(source_id)
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    connector_name TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    request_json TEXT NOT NULL,
    response_hash TEXT,
    error_message TEXT,
    FOREIGN KEY(source_id) REFERENCES sources(source_id)
);

CREATE TABLE IF NOT EXISTS raw_payloads (
    payload_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(source_id, content_hash),
    FOREIGN KEY(run_id) REFERENCES ingestion_runs(run_id),
    FOREIGN KEY(source_id) REFERENCES sources(source_id)
);

CREATE TABLE IF NOT EXISTS observations (
    observation_id TEXT PRIMARY KEY,
    series_id TEXT NOT NULL,
    observation_date TEXT NOT NULL,
    value REAL NOT NULL,
    vintage_date TEXT NOT NULL,
    revision_number INTEGER NOT NULL DEFAULT 0,
    release_id TEXT,
    payload_id TEXT NOT NULL,
    quality_status TEXT NOT NULL DEFAULT 'validated',
    created_at TEXT NOT NULL,
    UNIQUE(series_id, observation_date, vintage_date),
    FOREIGN KEY(series_id) REFERENCES series_registry(series_id),
    FOREIGN KEY(payload_id) REFERENCES raw_payloads(payload_id)
);

CREATE INDEX IF NOT EXISTS idx_observations_series_date
ON observations(series_id, observation_date);

CREATE INDEX IF NOT EXISTS idx_observations_vintage
ON observations(series_id, vintage_date);

CREATE TABLE IF NOT EXISTS validation_results (
    validation_id TEXT PRIMARY KEY,
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    status TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_validation_object
ON validation_results(object_type, object_id);

CREATE TABLE IF NOT EXISTS features (
    feature_id TEXT PRIMARY KEY,
    series_id TEXT NOT NULL,
    feature_name TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    value REAL NOT NULL,
    window TEXT,
    methodology_version TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(series_id, feature_name, as_of_date, methodology_version),
    FOREIGN KEY(series_id) REFERENCES series_registry(series_id)
);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id TEXT PRIMARY KEY,
    evidence_type TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    direction REAL NOT NULL,
    magnitude REAL NOT NULL,
    confidence REAL NOT NULL,
    reliability REAL NOT NULL,
    correlation_group TEXT,
    source_object_type TEXT NOT NULL,
    source_object_id TEXT NOT NULL,
    explanation TEXT NOT NULL,
    methodology_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_evidence_subject
ON evidence(subject_type, subject_id, as_of_date);

CREATE TABLE IF NOT EXISTS beliefs (
    belief_id TEXT PRIMARY KEY,
    belief_key TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    prior_probability REAL NOT NULL,
    posterior_probability REAL NOT NULL,
    confidence REAL NOT NULL,
    methodology_version TEXT NOT NULL,
    evidence_set_hash TEXT NOT NULL,
    explanation TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(belief_key, as_of_date, methodology_version)
);

CREATE TABLE IF NOT EXISTS belief_evidence_links (
    belief_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    contribution REAL NOT NULL,
    PRIMARY KEY(belief_id, evidence_id),
    FOREIGN KEY(belief_id) REFERENCES beliefs(belief_id),
    FOREIGN KEY(evidence_id) REFERENCES evidence(evidence_id)
);

CREATE TABLE IF NOT EXISTS regimes (
    regime_id TEXT PRIMARY KEY,
    regime_key TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    probability REAL NOT NULL,
    methodology_version TEXT NOT NULL,
    supporting_beliefs_hash TEXT NOT NULL,
    explanation TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(regime_key, as_of_date, methodology_version)
);

CREATE TABLE IF NOT EXISTS company_snapshots (
    company_snapshot_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    macro_score REAL,
    fundamental_score REAL,
    valuation_score REAL,
    technical_score REAL,
    revision_score REAL,
    total_score REAL,
    coverage REAL NOT NULL,
    gate_status TEXT NOT NULL,
    methodology_version TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    explanation_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE(ticker, as_of_date, methodology_version)
);

CREATE TABLE IF NOT EXISTS ranking_snapshots (
    ranking_snapshot_id TEXT PRIMARY KEY,
    as_of_date TEXT NOT NULL,
    methodology_version TEXT NOT NULL,
    universe_hash TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(as_of_date, methodology_version, universe_hash)
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT,
    occurred_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    dedupe_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending'
);

CREATE INDEX IF NOT EXISTS idx_events_status
ON events(status, occurred_at);

CREATE TABLE IF NOT EXISTS journal_entries (
    journal_entry_id TEXT PRIMARY KEY,
    as_of_date TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    subject_key TEXT NOT NULL,
    prior_state_json TEXT,
    new_state_json TEXT NOT NULL,
    reason TEXT NOT NULL,
    supporting_object_type TEXT,
    supporting_object_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS connector_credentials (
    credential_id TEXT PRIMARY KEY,
    provider_name TEXT NOT NULL,
    credential_label TEXT NOT NULL,
    secret_reference TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(provider_name, credential_label)
);
