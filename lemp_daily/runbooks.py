from __future__ import annotations


RUNBOOKS = {
    "stale_workers": [
        "Confirm worker process and host health.",
        "Inspect the worker heartbeat timestamp.",
        "Recover expired leases.",
        "Restart the affected worker.",
        "Confirm queue age begins declining.",
    ],
    "dead_letters": [
        "Group dead letters by connector and error message.",
        "Separate credential, rate-limit, schema, and data-quality failures.",
        "Correct the underlying issue.",
        "Replay only idempotent jobs.",
        "Confirm no duplicate observations were created.",
    ],
    "low_macro_coverage": [
        "Identify missing priority series.",
        "Check source release status and connector health.",
        "Do not publish a full-confidence regime assessment.",
        "Mark the daily brief as partial.",
        "Re-run ingestion after the source recovers.",
    ],
    "weak_calibration": [
        "Freeze model-weight promotion.",
        "Review target-level calibration metrics.",
        "Compare current and prior regimes.",
        "Inspect coefficient stability.",
        "Keep current production weights until human review.",
    ],
}
