CREATE TABLE IF NOT EXISTS gmail_delivery_records (
    gmail_delivery_record_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    publication_id UUID NOT NULL REFERENCES publications(publication_id),
    recipient_id UUID NOT NULL REFERENCES recipients(recipient_id),
    delivery_mode TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    draft_id TEXT,
    message_id TEXT,
    thread_id TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS gmail_thread_state (
    publication_series_key TEXT NOT NULL,
    recipient_id UUID NOT NULL REFERENCES recipients(recipient_id),
    latest_message_id TEXT,
    latest_thread_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(publication_series_key, recipient_id)
);

CREATE INDEX IF NOT EXISTS idx_gmail_delivery_status
ON gmail_delivery_records(status, created_at);
