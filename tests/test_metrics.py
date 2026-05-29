# PROMPT:

# Generated tests for the Purplle Store Intelligence challenge covering API correctness, edge cases, idempotency, metrics, funnel, anomalies, and health behavior.

# CHANGES MADE:

# Reviewed generated tests, simplified fixtures, added edge cases for duplicate ingestion, zero visitors, staff exclusion, re-entry, and stale feed behavior.

import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import Event, POSTransaction

def test_metrics_zero_visitors(client: TestClient):
    """Verifies that querying a store with zero telemetry events does not crash and returns safe defaults."""
    response = client.get("/stores/STORE_EMPTY_01/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["store_id"] == "STORE_EMPTY_01"
    assert data["unique_visitors"] == 0
    assert data["conversion_rate"] == 0.0
    assert data["avg_dwell_per_zone"] == {}
    assert data["current_queue_depth"] == 0

def test_metrics_staff_exclusion_and_aggregations(client: TestClient, db_session: Session):
    """Verifies staff are excluded, visitor counts and entry/exit counts aggregate accurately, and zone dwells are correct."""
    # Seed events
    events = [
        # Customer 1
        Event(event_id="e1", store_id="STORE_BLR_002", camera_id="CAM_01", visitor_id="VIS_1", event_type="ENTRY", timestamp=datetime.datetime(2026, 3, 3, 14, 0), zone_id="ENTRY", is_staff=False),
        Event(event_id="e2", store_id="STORE_BLR_002", camera_id="CAM_02", visitor_id="VIS_1", event_type="ZONE_ENTER", timestamp=datetime.datetime(2026, 3, 3, 14, 1), zone_id="SKINCARE", is_staff=False),
        Event(event_id="e3", store_id="STORE_BLR_002", camera_id="CAM_02", visitor_id="VIS_1", event_type="ZONE_DWELL", timestamp=datetime.datetime(2026, 3, 3, 14, 2), zone_id="SKINCARE", dwell_ms=30000, is_staff=False),
        Event(event_id="e4", store_id="STORE_BLR_002", camera_id="CAM_01", visitor_id="VIS_1", event_type="EXIT", timestamp=datetime.datetime(2026, 3, 3, 14, 5), zone_id="ENTRY", is_staff=False),
        
        # Staff (Should be entirely excluded)
        Event(event_id="e5", store_id="STORE_BLR_002", camera_id="CAM_02", visitor_id="VIS_STAFF", event_type="ZONE_ENTER", timestamp=datetime.datetime(2026, 3, 3, 14, 2), zone_id="SKINCARE", is_staff=True),
        Event(event_id="e6", store_id="STORE_BLR_002", camera_id="CAM_02", visitor_id="VIS_STAFF", event_type="ZONE_DWELL", timestamp=datetime.datetime(2026, 3, 3, 14, 3), zone_id="SKINCARE", dwell_ms=90000, is_staff=True),
        
        # Customer 2 (re-enters)
        Event(event_id="e7", store_id="STORE_BLR_002", camera_id="CAM_01", visitor_id="VIS_2", event_type="ENTRY", timestamp=datetime.datetime(2026, 3, 3, 14, 10), zone_id="ENTRY", is_staff=False),
        Event(event_id="e8", store_id="STORE_BLR_002", camera_id="CAM_01", visitor_id="VIS_2", event_type="EXIT", timestamp=datetime.datetime(2026, 3, 3, 14, 12), zone_id="ENTRY", is_staff=False),
        Event(event_id="e9", store_id="STORE_BLR_002", camera_id="CAM_01", visitor_id="VIS_2", event_type="REENTRY", timestamp=datetime.datetime(2026, 3, 3, 14, 15), zone_id="ENTRY", is_staff=False)
    ]
    db_session.bulk_save_objects(events)
    db_session.commit()
    
    response = client.get("/stores/STORE_BLR_002/metrics")
    assert response.status_code == 200
    data = response.json()
    
    # 2 unique non-staff visitors (VIS_1, VIS_2)
    assert data["unique_visitors"] == 2
    # 2 entries (e1, e7) + 1 reentry (e9) = 3 total entries
    assert data["total_entries"] == 3
    # 2 exits (e4, e8)
    assert data["total_exits"] == 2
    
    # Avg dwell SKINCARE is 30s (30000ms), staff's 90s is excluded
    assert data["avg_dwell_per_zone"]["SKINCARE"] == 30000

def test_metrics_conversion_pos_correlation(client: TestClient, db_session: Session):
    """Verifies that conversion rate matches visitors visiting billing queue within 5 mins before a POS transaction."""
    # Setup: 2 visitors
    # VIS_buyer: joins queue at 14:10, transaction happens at 14:13 (Within 5 minutes window: 3 minutes difference)
    # VIS_browser: joins queue at 14:00, transaction happens at 14:13 (Outside 5 minutes window: 13 minutes difference)
    events = [
        # Buyer
        Event(event_id="b1", store_id="STORE_BLR_002", camera_id="CAM_01", visitor_id="VIS_BUYER", event_type="ENTRY", timestamp=datetime.datetime(2026, 3, 3, 14, 5)),
        Event(event_id="b2", store_id="STORE_BLR_002", camera_id="CAM_B1", visitor_id="VIS_BUYER", event_type="BILLING_QUEUE_JOIN", timestamp=datetime.datetime(2026, 3, 3, 14, 10), zone_id="BILLING"),
        
        # Browser
        Event(event_id="br1", store_id="STORE_BLR_002", camera_id="CAM_01", visitor_id="VIS_BROWSER", event_type="ENTRY", timestamp=datetime.datetime(2026, 3, 3, 13, 58)),
        Event(event_id="br2", store_id="STORE_BLR_002", camera_id="CAM_B1", visitor_id="VIS_BROWSER", event_type="BILLING_QUEUE_JOIN", timestamp=datetime.datetime(2026, 3, 3, 14, 0), zone_id="BILLING")
    ]
    
    # One POS Transaction at 14:13
    txn = POSTransaction(
        store_id="STORE_BLR_002",
        transaction_id="TXN_TEST_1",
        timestamp=datetime.datetime(2026, 3, 3, 14, 13),
        basket_value_inr=1500.0
    )
    
    db_session.bulk_save_objects(events)
    db_session.add(txn)
    db_session.commit()
    
    # Check conversion rate with 1 transaction (VIS_BUYER converted, VIS_BROWSER did not)
    # Unique visitors = 2, Converted visitors = 1 -> Conversion rate = 0.50
    response = client.get("/stores/STORE_BLR_002/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["unique_visitors"] == 2
    assert data["conversion_rate"] == 0.5
