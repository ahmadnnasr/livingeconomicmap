CREATE TABLE IF NOT EXISTS publications (
    publication_id UUID PRIMARY KEY,
    publication_type TEXT NOT NULL,
    as_of_date DATE NOT NULL,
    subject TEXT NOT NULL,
    executive_summary TEXT NOT NULL,
    sections_json JSONB NOT NULL,
    snapshot_id TEXT NOT NULL,
    model_version TEXT NOT NULL,
    trace_id UUID NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS publication_renders (
    render_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    publication_id UUID NOT NULL REFERENCES publications(publication_id),
    format TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    storage_location TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(publication_id, format)
);

CREATE TABLE IF NOT EXISTS recipients (
    recipient_id UUID PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS delivery_preferences (
    recipient_id UUID NOT NULL REFERENCES recipients(recipient_id),
    publication_type TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    minimum_severity TEXT NOT NULL DEFAULT 'info',
    delivery_channel TEXT NOT NULL DEFAULT 'email',
    PRIMARY KEY(recipient_id, publication_type, delivery_channel)
);

CREATE TABLE IF NOT EXISTS delivery_attempts (
    delivery_id UUID PRIMARY KEY,
    publication_id UUID NOT NULL REFERENCES publications(publication_id),
    recipient_id UUID NOT NULL REFERENCES recipients(recipient_id),
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    attempt_number INTEGER NOT NULL,
    attempted_at TIMESTAMPTZ NOT NULL,
    provider_message_id TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_delivery_attempts_status
ON delivery_attempts(status, attempted_at);

CREATE TABLE IF NOT EXISTS publication_events (
    publication_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    publication_id UUID NOT NULL REFERENCES publications(publication_id),
    event_type TEXT NOT NULL,
    event_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
