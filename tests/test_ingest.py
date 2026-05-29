# PROMPT:

# Generated tests for the Purplle Store Intelligence challenge covering API correctness, edge cases, idempotency, metrics, funnel, anomalies, and health behavior.

# CHANGES MADE:

# Reviewed generated tests, simplified fixtures, added edge cases for duplicate ingestion, zero visitors, staff exclusion, re-entry, and stale feed behavior.

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import Event

def test_ingest_valid_batch(client: TestClient, db_session: Session):
    """Verifies that a valid batch of events is accepted and saved correctly."""
    payload = {
        "events": [
            {
                "event_id": "test_evt_1",
                "store_id": "STORE_BLR_002",
                "camera_id": "CAM_ENTRY_01",
                "visitor_id": "VIS_abc123",
                "event_type": "ENTRY",
                "timestamp": "2026-03-03T14:10:00Z",
                "zone_id": "ENTRY",
                "dwell_ms": 1000,
                "is_staff": False
            },
            {
                "event_id": "test_evt_2",
                "store_id": "STORE_BLR_002",
                "camera_id": "CAM_FLOOR_01",
                "visitor_id": "VIS_staff_01",
                "event_type": "ZONE_ENTER",
                "timestamp": "2026-03-03T14:11:00Z",
                "zone_id": "SKINCARE",
                "is_staff": True
            }
        ]
    }
    
    response = client.post("/events/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    assert data["accepted_count"] == 2
    assert data["duplicate_count"] == 0
    assert data["rejected_count"] == 0
    assert len(data["errors"]) == 0
    
    # Confirm DB contents
    events_in_db = db_session.query(Event).all()
    assert len(events_in_db) == 2
    assert {e.event_id for e in events_in_db} == {"test_evt_1", "test_evt_2"}

def test_ingest_idempotency_duplicate_ids(client: TestClient, db_session: Session):
    """Verifies that sending duplicate event_id keys in the same or separate requests does not double-count."""
    payload1 = {
        "events": [
            {
                "event_id": "duplicate_evt",
                "store_id": "STORE_BLR_002",
                "camera_id": "CAM_ENTRY_01",
                "visitor_id": "VIS_abc123",
                "event_type": "ENTRY",
                "timestamp": "2026-03-03T14:10:00Z"
            }
        ]
    }
    
    # First Ingest
    res1 = client.post("/events/ingest", json=payload1)
    assert res1.status_code == 200
    assert res1.json()["accepted_count"] == 1
    assert res1.json()["duplicate_count"] == 0
    
    # Second Ingest (Duplicate event)
    res2 = client.post("/events/ingest", json=payload1)
    assert res2.status_code == 200
    assert res2.json()["accepted_count"] == 0
    assert res2.json()["duplicate_count"] == 1
    
    # Duplicate in same batch
    payload2 = {
        "events": [
            {
                "event_id": "batch_dup",
                "store_id": "STORE_BLR_002",
                "camera_id": "CAM_ENTRY_01",
                "visitor_id": "VIS_abc123",
                "event_type": "ENTRY",
                "timestamp": "2026-03-03T14:10:00Z"
            },
            {
                "event_id": "batch_dup",
                "store_id": "STORE_BLR_002",
                "camera_id": "CAM_ENTRY_01",
                "visitor_id": "VIS_abc123",
                "event_type": "ENTRY",
                "timestamp": "2026-03-03T14:10:00Z"
            }
        ]
    }
    res3 = client.post("/events/ingest", json=payload2)
    assert res3.status_code == 200
    assert res3.json()["accepted_count"] == 1
    assert res3.json()["duplicate_count"] == 1
    
    assert db_session.query(Event).count() == 2

def test_ingest_partial_success(client: TestClient, db_session: Session):
    """Verifies that valid events are committed while malformed entries register as errors."""
    payload = {
        "events": [
            {
                "event_id": "valid_evt",
                "store_id": "STORE_BLR_002",
                "camera_id": "CAM_ENTRY_01",
                "visitor_id": "VIS_abc123",
                "event_type": "ENTRY",
                "timestamp": "2026-03-03T14:10:00Z"
            },
            {
                "event_id": "malformed_evt",
                "store_id": "STORE_BLR_002",
                "camera_id": "CAM_ENTRY_01",
                "visitor_id": "VIS_abc123",
                "event_type": "INVALID_TYPE_BLABLA",  # Invalid enum value
                "timestamp": "2026-03-03T14:10:00Z"
            }
        ]
    }
    
    response = client.post("/events/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    assert data["accepted_count"] == 1
    assert data["rejected_count"] == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["index"] == 1
    assert "event_type" in data["errors"][0]["reason"]
    
    assert db_session.query(Event).count() == 1
    assert db_session.query(Event).first().event_id == "valid_evt"

def test_ingest_too_large(client: TestClient):
    """Verifies that batches larger than 500 events are rejected with 400 Bad Request."""
    too_many_events = [{"event_id": f"evt_{i}", "store_id": "STORE_BLR_002", "camera_id": "CAM_01", "visitor_id": "V", "event_type": "ENTRY", "timestamp": "2026-03-03T14:00:00Z"} for i in range(501)]
    payload = {"events": too_many_events}
    
    response = client.post("/events/ingest", json=payload)
    assert response.status_code == 400
    assert "limit of 500" in response.json()["detail"]
