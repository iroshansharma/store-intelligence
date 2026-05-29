import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import Event, POSTransaction

def test_demo_seed_and_metrics(client: TestClient, db_session: Session):
    """
    Verifies that POST /demo/seed runs successfully, clearing previous records,
    populating 105 events and 5 POS transactions, and resulting in non-zero
    conversion rates and funnel purchase counts.
    """
    # 1. Clear database initially to verify clean slate behavior
    db_session.query(Event).filter(Event.store_id == "STORE_BLR_002").delete()
    db_session.query(POSTransaction).filter(POSTransaction.store_id == "STORE_BLR_002").delete()
    db_session.commit()
    
    # 2. Trigger seed endpoint
    response = client.post("/demo/seed")
    assert response.status_code == 201
    
    data = response.json()
    assert data["store_id"] == "STORE_BLR_002"
    assert data["events_inserted"] == 105
    assert data["pos_transactions_inserted"] == 5
    assert "seeded successfully" in data["message"]
    
    # 3. Query DB directly to verify records exist
    event_count = db_session.query(Event).filter(Event.store_id == "STORE_BLR_002").count()
    pos_count = db_session.query(POSTransaction).filter(POSTransaction.store_id == "STORE_BLR_002").count()
    assert event_count == 105
    assert pos_count == 5
    
    # 4. Fetch metrics to verify conversion rate
    metrics_response = client.get("/stores/STORE_BLR_002/metrics")
    assert metrics_response.status_code == 200
    metrics = metrics_response.json()
    
    assert metrics["store_id"] == "STORE_BLR_002"
    assert metrics["unique_visitors"] > 0
    assert metrics["conversion_rate"] > 0.0
    assert metrics["current_queue_depth"] > 0
    
    # 5. Fetch funnel to verify purchase stage
    funnel_response = client.get("/stores/STORE_BLR_002/funnel")
    assert funnel_response.status_code == 200
    funnel = funnel_response.json()
    
    assert funnel["store_id"] == "STORE_BLR_002"
    
    # Locate the Purchase stage and assert it's greater than 0
    stages = funnel["stages"]
    purchase_stage = next((stage for stage in stages if stage["stage"] == "Purchase"), None)
    assert purchase_stage is not None
    assert purchase_stage["count"] > 0
