
from app.db import fetch_all

def safe(query, params=()):
    try: return fetch_all(query,params)
    except Exception: return []

def dashboard_state():
    return {
      "beliefs": safe("SELECT belief_key, probability, confidence, updated_at FROM beliefs ORDER BY updated_at DESC LIMIT 12"),
      "regimes": safe("SELECT regime_key, probability, as_of FROM regimes ORDER BY as_of DESC LIMIT 12"),
      "jobs": safe("SELECT status, COUNT(*) AS count FROM jobs GROUP BY status ORDER BY status"),
      "publications": safe("SELECT publication_id, publication_type, subject, status, created_at FROM publications ORDER BY created_at DESC LIMIT 10"),
      "deliveries": safe("SELECT status, delivery_mode, message_id, draft_id, created_at FROM gmail_delivery_records ORDER BY created_at DESC LIMIT 10"),
    }
