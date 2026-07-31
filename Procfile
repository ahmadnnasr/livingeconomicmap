web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
ingestion: python -m workers.run ingestion
reasoning: python -m workers.run reasoning
publication: python -m workers.run publication
maintenance: python -m workers.run maintenance
news: python -m workers.run news
