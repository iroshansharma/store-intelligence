# PROMPT:

# Generated tests for the Purplle Store Intelligence challenge covering API correctness, edge cases, idempotency, metrics, funnel, anomalies, and health behavior.

# CHANGES MADE:

# Reviewed generated tests, simplified fixtures, added edge cases for duplicate ingestion, zero visitors, staff exclusion, re-entry, and stale feed behavior.

import datetime
import json
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import Event, POSTransaction

def test_anomalies_stale_feed(client: TestClient, db_session: Session):
    """Verifies that an event feed older than 10 minutes from current UTC triggers a STALE_FEED anomaly."""
    # Stale event: 15 minutes ago
    stale_time = datetime.datetime.utcnow() - datetime.timedelta(minutes=15)
    evt = Event(
        event_id="stale_evt",
        store_id="STORE_BLR_002",
        camera_id="CAM_01",
        visitor_id="VIS_1",
        event_type="ENTRY",
        timestamp=stale_time,
        zone_id="ENTRY"
    )
    db_session.add(evt)
    db_session.commit()
    
    response = client.get("/stores/STORE_BLR_002/anomalies")
    assert response.status_code == 200
    data = response.json()
    
    types = [a["anomaly_type"] for a in data]
    assert "STALE_FEED" in types
    
    # Check alert details
    stale_alert = [a for a in data if a["anomaly_type"] == "STALE_FEED"][0]
    assert stale_alert["severity"] == "CRITICAL"

def test_anomalies_queue_spike(client: TestClient, db_session: Session):
    """Verifies BILLING_QUEUE_SPIKE anomaly is raised when queue depth exceeds 5 in recent logs."""
    # Anchored latest timestamp
    base_time = datetime.datetime(2026, 3, 3, 14, 0, 0)
    
    events = [
        Event(
            event_id="q1",
            store_id="STORE_BLR_002",
            camera_id="CAM_B1",
            visitor_id="VIS_1",
            event_type="BILLING_QUEUE_JOIN",
            timestamp=base_time,
            zone_id="BILLING",
            metadata_json=json.dumps({"queue_depth": 6})  # Exceeds threshold (5)
        )
    ]
    db_session.bulk_save_objects(events)
    db_session.commit()
    
    response = client.get("/stores/STORE_BLR_002/anomalies")
    assert response.status_code == 200
    data = response.json()
    
    types = [a["anomaly_type"] for a in data]
    assert "BILLING_QUEUE_SPIKE" in types
    spike_alert = [a for a in data if a["anomaly_type"] == "BILLING_QUEUE_SPIKE"][0]
    assert spike_alert["severity"] == "CRITICAL"
    assert "depth is currently 6" in spike_alert["message"]

def test_anomalies_conversion_drop(client: TestClient, db_session: Session):
    """Verifies CONVERSION_DROP alert is triggered if conversion rate is < 15% when store has >= 10 visitors."""
    # Anchored time
    base_time = datetime.datetime(2026, 3, 3, 14, 0, 0)
    
    # 10 unique non-staff visitor sessions entering, but 0 purchases (conversion = 0% < 15%)
    events = []
    for i in range(10):
        events.append(
            Event(
                event_id=f"conv_drop_evt_{i}",
                store_id="STORE_BLR_002",
                camera_id="CAM_01",
                visitor_id=f"VIS_CONV_{i}",
                event_type="ENTRY",
                timestamp=base_time - datetime.timedelta(minutes=i)
            )
        )
    db_session.bulk_save_objects(events)
    db_session.commit()
    
    response = client.get("/stores/STORE_BLR_002/anomalies")
    assert response.status_code == 200
    data = response.json()
    
    types = [a["anomaly_type"] for a in data]
    assert "CONVERSION_DROP" in types
    
    alert = [a for a in data if a["anomaly_type"] == "CONVERSION_DROP"][0]
    assert alert["severity"] == "WARN"
    assert "0.0%" in alert["message"]

def test_anomalies_dead_zone(client: TestClient, db_session: Session):
    """Verifies DEAD_ZONE alert is raised if a defined store layout zone remains completely vacant during the last 30 minutes of telemetry."""
    # Anchored time: 14:00:00
    base_time = datetime.datetime(2026, 3, 3, 14, 0, 0)
    
    # Telemetry events only inside SKINCARE and HAIRCARE, leaving MAKEUP completely vacant.
    # Latest global timestamp is 14:00:00, lookup window is [13:30, 14:00].
    events = [
        Event(event_id="d0", store_id="STORE_BLR_002", camera_id="CAM_01", visitor_id="VIS_0", event_type="ZONE_ENTER", timestamp=base_time - datetime.timedelta(minutes=45), zone_id="MAKEUP"),
        Event(event_id="d1", store_id="STORE_BLR_002", camera_id="CAM_01", visitor_id="VIS_1", event_type="ZONE_ENTER", timestamp=base_time - datetime.timedelta(minutes=5), zone_id="SKINCARE"),
        Event(event_id="d2", store_id="STORE_BLR_002", camera_id="CAM_01", visitor_id="VIS_2", event_type="ZONE_ENTER", timestamp=base_time - datetime.timedelta(minutes=10), zone_id="HAIRCARE"),
        Event(event_id="d3", store_id="STORE_BLR_002", camera_id="CAM_01", visitor_id="VIS_3", event_type="ZONE_ENTER", timestamp=base_time, zone_id="SKINCARE")
    ]
    db_session.bulk_save_objects(events)
    db_session.commit()
    
    response = client.get("/stores/STORE_BLR_002/anomalies")
    assert response.status_code == 200
    data = response.json()
    
    types = [a["anomaly_type"] for a in data]
    assert "DEAD_ZONE" in types
    
    # MAKEUP zone should be flagged
    makeup_alerts = [a for a in data if a["anomaly_type"] == "DEAD_ZONE" and "MAKEUP" in a["message"]]
    assert len(makeup_alerts) == 1
    assert makeup_alerts[0]["severity"] == "WARN"
