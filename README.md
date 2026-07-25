
# Living Economic Map Platform

A database-first, explainable macroeconomic reasoning and research-publication platform prepared for GitHub and Railway.

## Included systems

- Canonical economic data layer and validation
- PostgreSQL-native durable queue
- FRED, ALFRED, BLS, BEA, Census, Treasury, and EIA connector packages
- Rates and liquidity reasoning
- Market-implied calibration
- Constrained statistical fitting and human promotion gates
- Daily operating system
- Research Publication System
- Gmail-first delivery adapter
- Password-protected online dashboard
- Railway deployment configuration

## Local start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open `http://localhost:8000` and use the dashboard credentials from `.env`.

## Test

```bash
python -m unittest discover -s tests
```

## Railway

Follow `RAILWAY_DEPLOYMENT.md`.

## Current production posture

The repository is deployable and the web/health/migration boundaries are executable. The included scientific engines and connector modules are consolidated from Versions 0.1–3.49. The worker entry points deliberately remain conservative: before live operation, bind each queue to its versioned handlers, configure real API credentials, and validate one full cycle against Railway PostgreSQL. Gmail remains disabled until its independent production OAuth connection is configured.
