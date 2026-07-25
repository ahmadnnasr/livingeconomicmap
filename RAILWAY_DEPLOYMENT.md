
# Railway Deployment

## 1. Push to GitHub

Create an empty GitHub repository, then run:

```bash
git init
git add .
git commit -m "Initial Living Economic Map deployment"
git branch -M main
git remote add origin <YOUR_GITHUB_REPOSITORY_URL>
git push -u origin main
```

## 2. Create the Railway project

1. Create an empty Railway project.
2. Add a PostgreSQL database.
3. Add an empty service named `web` and connect this GitHub repository.
4. Set `DATABASE_URL=${{Postgres.DATABASE_URL}}` on every application service.
5. Generate a public domain only for `web`.

## 3. Web service

- Start command: leave blank; Dockerfile default starts Uvicorn.
- Pre-deploy command: `python -m scripts.migrate`
- Healthcheck: `/health`

## 4. Persistent workers

Create four more services connected to the same repository. Override start commands:

```text
python -m workers.run ingestion
python -m workers.run reasoning
python -m workers.run publication
python -m workers.run maintenance
```

Do not assign public domains to workers.

## 5. Scheduled services

Create three short-lived services with these start commands:

```text
python -m jobs.run_cycle preopen
python -m jobs.run_cycle closing
python -m jobs.run_cycle nightly
```

Use Railway cron schedules in UTC. To preserve fixed Eastern times across DST, the production recommendation is to run a lightweight dispatcher every 15 minutes and let the application check `America/New_York` before enqueueing a cycle. Railway cron execution can vary by a few minutes.

## 6. Required variables

Copy `.env.example` into Railway's shared variables. Generate strong values for:

- `DASHBOARD_PASSWORD`
- `SECRET_KEY`

Keep `GMAIL_DELIVERY_ENABLED=false` until OAuth or a supported production Gmail sender is connected and a test draft has been reviewed.

## 7. First verification

1. Open `/health` and confirm database status is `ok`.
2. Open the generated Railway domain and sign in with HTTP Basic credentials.
3. Confirm migrations appear in `schema_migrations`.
4. Run each cycle manually once.
5. Review worker logs.
6. Create a Gmail test draft before enabling automatic email.
