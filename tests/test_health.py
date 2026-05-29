# PROMPT:

# Generated tests for the Purplle Store Intelligence challenge covering API correctness, edge cases, idempotency, metrics, funnel, anomalies, and health behavior.

# CHANGES MADE:

# Reviewed generated tests, simplified fixtures, added edge cases for duplicate ingestion, zero visitors, staff exclusion, re-entry, and stale feed behavior.

import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import Event

def test_health_ok(client: TestClient):
    """Verifies that a healthy system returns 200 OK and database status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert "last_event_timestamp_per_store" in data
    assert "stale_feed_warnings" in data

def test_health_stale_warning(client: TestClient, db_session: Session):
    """Verifies stale feed warning is raised if last event is older than settings threshold (10 minutes)."""
    # Insert an event dated 20 minutes ago
    twenty_mins_ago = datetime.datetime.utcnow() - datetime.timedelta(minutes=20)
    old_event = Event(
        event_id="evt_stale_test",
        store_id="STORE_BLR_002",
        camera_id="CAM_ENTRY_01",
        visitor_id="VIS_123",
        event_type="ENTRY",
        timestamp=twenty_mins_ago,
        zone_id="ENTRY",
        dwell_ms=1000,
        is_staff=False
    )
    db_session.add(old_event)
    db_session.commit()
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    
    assert "STORE_BLR_002" in data["last_event_timestamp_per_store"]
    assert len(data["stale_feed_warnings"]) == 1
    assert "stale" in data["stale_feed_warnings"][0]
