# PROMPT:

# Generated tests for the Purplle Store Intelligence challenge covering API correctness, edge cases, idempotency, metrics, funnel, anomalies, and health behavior.

# CHANGES MADE:

# Reviewed generated tests, simplified fixtures, added edge cases for duplicate ingestion, zero visitors, staff exclusion, re-entry, and stale feed behavior.

import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import Event

def test_heatmap_calculation_and_confidence(client: TestClient, db_session: Session):
    """
    Verifies that zone heatmap metrics calculate raw counts, average dwells,
    normalize scores out of 100, and flag LOW confidence if total store sessions < 20.
    """
    events = [
        # Zone A: SKINCARE (2 sessions)
        Event(event_id="e1", store_id="STORE_BLR_002", camera_id="CAM_2", visitor_id="VIS_1", event_type="ZONE_ENTER", timestamp=datetime.datetime(2026, 3, 3, 14, 0), zone_id="SKINCARE"),
        Event(event_id="e2", store_id="STORE_BLR_002", camera_id="CAM_2", visitor_id="VIS_1", event_type="ZONE_DWELL", timestamp=datetime.datetime(2026, 3, 3, 14, 0), zone_id="SKINCARE", dwell_ms=10000),
        Event(event_id="e3", store_id="STORE_BLR_002", camera_id="CAM_2", visitor_id="VIS_2", event_type="ZONE_ENTER", timestamp=datetime.datetime(2026, 3, 3, 14, 2), zone_id="SKINCARE"),
        Event(event_id="e4", store_id="STORE_BLR_002", camera_id="CAM_2", visitor_id="VIS_2", event_type="ZONE_DWELL", timestamp=datetime.datetime(2026, 3, 3, 14, 2), zone_id="SKINCARE", dwell_ms=20000),
        
        # Zone B: HAIRCARE (1 session)
        Event(event_id="e5", store_id="STORE_BLR_002", camera_id="CAM_2", visitor_id="VIS_3", event_type="ZONE_ENTER", timestamp=datetime.datetime(2026, 3, 3, 14, 5), zone_id="HAIRCARE"),
        Event(event_id="e6", store_id="STORE_BLR_002", camera_id="CAM_2", visitor_id="VIS_3", event_type="ZONE_DWELL", timestamp=datetime.datetime(2026, 3, 3, 14, 5), zone_id="HAIRCARE", dwell_ms=15000),
        
        # Staff (Excluded)
        Event(event_id="e7", store_id="STORE_BLR_002", camera_id="CAM_2", visitor_id="VIS_STAFF", event_type="ZONE_ENTER", timestamp=datetime.datetime(2026, 3, 3, 14, 5), zone_id="HAIRCARE", is_staff=True)
    ]
    
    db_session.bulk_save_objects(events)
    db_session.commit()
    
    response = client.get("/stores/STORE_BLR_002/heatmap")
    assert response.status_code == 200
    data = response.json()
    
    # 2 zones recorded (SKINCARE and HAIRCARE)
    assert len(data) == 2
    
    # Sort by zone_id to check deterministic outputs
    data_sorted = sorted(data, key=lambda x: x["zone_id"])
    
    # HAIRCARE
    assert data_sorted[0]["zone_id"] == "HAIRCARE"
    assert data_sorted[0]["visit_count"] == 1
    assert data_sorted[0]["avg_dwell_ms"] == 15000
    # Normalized score: SKINCARE has max visits (2), HAIRCARE has 1 -> Score = (1/2)*100 = 50
    assert data_sorted[0]["normalized_score"] == 50
    # Total sessions in store = 3 < 20 -> confidence should be LOW
    assert data_sorted[0]["data_confidence"] == "LOW"
    
    # SKINCARE
    assert data_sorted[1]["zone_id"] == "SKINCARE"
    assert data_sorted[1]["visit_count"] == 2
    # Avg dwell: (10000 + 20000) / 2 = 15000ms
    assert data_sorted[1]["avg_dwell_ms"] == 15000
    # Normalized score: max visits (2) -> Score = (2/2)*100 = 100
    assert data_sorted[1]["normalized_score"] == 100
    assert data_sorted[1]["data_confidence"] == "LOW"

def test_heatmap_high_confidence(client: TestClient, db_session: Session):
    """Verifies that confidence is marked HIGH if total store visitor sessions >= 20."""
    events = []
    # Generate 20 distinct visitor sessions entering HAIRCARE
    for i in range(21):
        events.append(
            Event(
                event_id=f"h_{i}",
                store_id="STORE_BLR_002",
                camera_id="CAM_2",
                visitor_id=f"VIS_{i}",
                event_type="ZONE_ENTER",
                timestamp=datetime.datetime(2026, 3, 3, 14, 0),
                zone_id="HAIRCARE"
            )
        )
    db_session.bulk_save_objects(events)
    db_session.commit()
    
    response = client.get("/stores/STORE_BLR_002/heatmap")
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 1
    assert data[0]["data_confidence"] == "HIGH"
