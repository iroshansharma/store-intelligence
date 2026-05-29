# PROMPT:

# Generated tests for the Purplle Store Intelligence challenge covering API correctness, edge cases, idempotency, metrics, funnel, anomalies, and health behavior.

# CHANGES MADE:

# Reviewed generated tests, simplified fixtures, added edge cases for duplicate ingestion, zero visitors, staff exclusion, re-entry, and stale feed behavior.

import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import Event, POSTransaction

def test_funnel_stages(client: TestClient, db_session: Session):
    """
    Verifies sequential funnel logic:
    VIS_1: Entry -> Skincare -> Queue -> Purchase (Reached stage 4: Purchase)
    VIS_2: Entry -> Haircare -> Queue (Reached stage 3: Billing Queue)
    VIS_3: Entry -> Skincare (Reached stage 2: Product Zone Visit)
    VIS_4: Entry only (Reached stage 1: Entry)
    VIS_staff: Excluded (is_staff=True)
    """
    events = [
        # VIS_1
        Event(event_id="e1", store_id="STORE_BLR_002", camera_id="CAM_1", visitor_id="VIS_1", event_type="ENTRY", timestamp=datetime.datetime(2026, 3, 3, 14, 0)),
        Event(event_id="e2", store_id="STORE_BLR_002", camera_id="CAM_2", visitor_id="VIS_1", event_type="ZONE_ENTER", timestamp=datetime.datetime(2026, 3, 3, 14, 1), zone_id="SKINCARE"),
        Event(event_id="e3", store_id="STORE_BLR_002", camera_id="CAM_3", visitor_id="VIS_1", event_type="BILLING_QUEUE_JOIN", timestamp=datetime.datetime(2026, 3, 3, 14, 5), zone_id="BILLING"),
        
        # VIS_2
        Event(event_id="e4", store_id="STORE_BLR_002", camera_id="CAM_1", visitor_id="VIS_2", event_type="ENTRY", timestamp=datetime.datetime(2026, 3, 3, 14, 2)),
        Event(event_id="e5", store_id="STORE_BLR_002", camera_id="CAM_2", visitor_id="VIS_2", event_type="ZONE_ENTER", timestamp=datetime.datetime(2026, 3, 3, 14, 3), zone_id="HAIRCARE"),
        Event(event_id="e6", store_id="STORE_BLR_002", camera_id="CAM_3", visitor_id="VIS_2", event_type="BILLING_QUEUE_JOIN", timestamp=datetime.datetime(2026, 3, 3, 14, 6), zone_id="BILLING"),
        
        # VIS_3
        Event(event_id="e7", store_id="STORE_BLR_002", camera_id="CAM_1", visitor_id="VIS_3", event_type="ENTRY", timestamp=datetime.datetime(2026, 3, 3, 14, 5)),
        Event(event_id="e8", store_id="STORE_BLR_002", camera_id="CAM_2", visitor_id="VIS_3", event_type="ZONE_ENTER", timestamp=datetime.datetime(2026, 3, 3, 14, 6), zone_id="SKINCARE"),
        
        # VIS_4
        Event(event_id="e9", store_id="STORE_BLR_002", camera_id="CAM_1", visitor_id="VIS_4", event_type="ENTRY", timestamp=datetime.datetime(2026, 3, 3, 14, 8)),
        
        # Staff (Excluded)
        Event(event_id="e10", store_id="STORE_BLR_002", camera_id="CAM_1", visitor_id="VIS_STAFF", event_type="ENTRY", timestamp=datetime.datetime(2026, 3, 3, 14, 0), is_staff=True),
        Event(event_id="e11", store_id="STORE_BLR_002", camera_id="CAM_2", visitor_id="VIS_STAFF", event_type="ZONE_ENTER", timestamp=datetime.datetime(2026, 3, 3, 14, 1), zone_id="SKINCARE", is_staff=True),
    ]
    
    # 1 Purchase transaction at 14:07 matching VIS_1 queue window [14:05 - 5 min, 14:05] -> 14:07 is too late?
    # Wait, the purchase transaction checks the window [txn_time - 300s, txn_time].
    # Transaction timestamp = 14:07. Visitor billing queue join = 14:05.
    # [14:02, 14:07] contains 14:05! Yes, this is a perfect match!
    txn = POSTransaction(
        store_id="STORE_BLR_002",
        transaction_id="TX_FUNNEL_1",
        timestamp=datetime.datetime(2026, 3, 3, 14, 5, 30),
        basket_value_inr=1800.0
    )
    
    db_session.bulk_save_objects(events)
    db_session.add(txn)
    db_session.commit()
    
    response = client.get("/stores/STORE_BLR_002/funnel")
    assert response.status_code == 200
    data = response.json()
    
    # Assert counts
    stages = data["stages"]
    assert len(stages) == 4
    
    # Stage 1: Entry -> Should contain VIS_1, VIS_2, VIS_3, VIS_4 = 4
    assert stages[0]["stage"] == "Entry"
    assert stages[0]["count"] == 4
    # VIS_4 drops off here (does not visit a zone) -> Dropoff count = 1, pct = 25% (1/4)
    assert stages[0]["dropoff_count"] == 1
    assert stages[0]["dropoff_percentage"] == 0.25
    
    # Stage 2: Product Zone Visit -> Should contain VIS_1, VIS_2, VIS_3 = 3
    assert stages[1]["stage"] == "Zone Visit"
    assert stages[1]["count"] == 3
    # VIS_3 drops off here (does not join queue) -> Dropoff count = 1, pct = 33.3% (1/3)
    assert round(stages[1]["dropoff_percentage"], 3) == 0.333
    
    # Stage 3: Billing Queue -> Should contain VIS_1, VIS_2 = 2
    assert stages[2]["stage"] == "Billing Queue"
    assert stages[2]["count"] == 2
    # VIS_2 drops off here (does not purchase) -> Dropoff count = 1, pct = 50% (1/2)
    assert stages[2]["dropoff_percentage"] == 0.50
    
    # Stage 4: Purchase -> Should contain VIS_1 = 1
    assert stages[3]["stage"] == "Purchase"
    assert stages[3]["count"] == 1
    assert stages[3]["dropoff_count"] == 0
    assert stages[3]["dropoff_percentage"] == 0.0
