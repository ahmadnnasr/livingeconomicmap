# Living Economic Map v3.51 upload

Upload the contents of this patch into the root of the existing GitHub repository, preserving the folder paths. Choose **Replace** when GitHub asks about files that already exist.

New files:

- `migrations/deploy/002_macro_observations.sql`
- `lemp_macro/live_fred.py`
- `jobs/ingest_fred.py`
- `tests/test_live_fred.py`

Replace existing files:

- `app/main.py`
- `app/queries.py`
- `templates/dashboard.html`
- `static/app.css`

After the GitHub commit, Railway should redeploy and run migration `002_macro_observations.sql`. Open the dashboard and press **Run FRED ingestion** once. The first run downloads roughly six years of history for ten priority FRED series and may take several seconds.
