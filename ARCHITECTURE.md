# Architecture

```text
Official data sources / Benzinga
          ↓
Ingestion + validation
          ↓
PostgreSQL observations and evidence
          ↓
Beliefs → regimes → causal propagation
          ↓
Calibration + constrained fitting
          ↓
Human model governance
          ↓
Company ranking + snapshots
          ↓
Research publications
          ↓
Gmail delivery + online dashboard
```

All services share one repository and one Railway PostgreSQL database. PostgreSQL is also the durable queue using `FOR UPDATE SKIP LOCKED`.
