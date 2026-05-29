import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Event, POSTransaction
from app.logging_config import logger

router = APIRouter()

@router.get("/stores/{store_id}/funnel")
def get_store_funnel(store_id: str, db: Session = Depends(get_db)):
    start_time = datetime.datetime.utcnow()
    
    # Fetch non-staff events
    events = db.query(Event).filter(
        Event.store_id == store_id,
        Event.is_staff == False
    ).order_by(Event.timestamp.asc()).all()
    
    # Fetch transactions
    transactions = db.query(POSTransaction).filter(
        POSTransaction.store_id == store_id
    ).all()
    
    if not events:
        return {
            "store_id": store_id,
            "stages": [
                {"stage": "Entry", "count": 0, "dropoff_count": 0, "dropoff_percentage": 0.0},
                {"stage": "Zone Visit", "count": 0, "dropoff_count": 0, "dropoff_percentage": 0.0},
                {"stage": "Billing Queue", "count": 0, "dropoff_count": 0, "dropoff_percentage": 0.0},
                {"stage": "Purchase", "count": 0, "dropoff_count": 0, "dropoff_percentage": 0.0}
            ]
        }
        
    # Analyze visitor journey stages
    visitors = {}
    for e in events:
        vid = e.visitor_id
        if vid not in visitors:
            visitors[vid] = {
                "has_entry": False,
                "has_zone": False,
                "has_billing": False,
                "has_purchase": False,
                "billing_timestamps": []
            }
            
        visitors[vid]["has_entry"] = True
        
        # Check if visited a product zone (skincare, haircare, makeup, cosmetics, etc. - anything except entry & billing)
        if e.zone_id and e.zone_id.upper() not in ("ENTRY", "BILLING"):
            visitors[vid]["has_zone"] = True
            
        if e.event_type == "BILLING_QUEUE_JOIN" or (e.zone_id and e.zone_id.upper() == "BILLING"):
            visitors[vid]["has_billing"] = True
            visitors[vid]["billing_timestamps"].append(e.timestamp)

    # Determine POS conversion for billing queue visitors
    for vid, data in visitors.items():
        if data["has_billing"]:
            # Check if any POS transaction aligns with the visitor's billing timestamp
            for txn in transactions:
                txn_time = txn.timestamp
                for b_time in data["billing_timestamps"]:
                    diff = (txn_time - b_time).total_seconds()
                    if 0 <= diff <= 300:
                        data["has_purchase"] = True
                        break
                if data["has_purchase"]:
                    break

    # Build sequential cohort flow
    # Stage 1: Entry
    cohort_entry = {vid for vid, d in visitors.items() if d["has_entry"]}
    # Stage 2: Zone Visit (must have entered)
    cohort_zone = {vid for vid in cohort_entry if visitors[vid]["has_zone"]}
    # Stage 3: Billing Queue (must have visited zone)
    cohort_billing = {vid for vid in cohort_zone if visitors[vid]["has_billing"]}
    # Stage 4: Purchase (must have joined billing queue)
    cohort_purchase = {vid for vid in cohort_billing if visitors[vid]["has_purchase"]}

    c_entry = len(cohort_entry)
    c_zone = len(cohort_zone)
    c_billing = len(cohort_billing)
    c_purchase = len(cohort_purchase)

    # Calculate drop-off steps
    drop_entry = c_entry - c_zone
    pct_entry = round(drop_entry / c_entry, 4) if c_entry > 0 else 0.0

    drop_zone = c_zone - c_billing
    pct_zone = round(drop_zone / c_zone, 4) if c_zone > 0 else 0.0

    drop_billing = c_billing - c_purchase
    pct_billing = round(drop_billing / c_billing, 4) if c_billing > 0 else 0.0

    latency = int((datetime.datetime.utcnow() - start_time).total_seconds() * 1000)
    logger.info(
        f"Fetched funnel for {store_id}: entry={c_entry}, purchase={c_purchase}.",
        extra={
            "trace_id": "funnel-" + str(int(start_time.timestamp())),
            "endpoint": f"/stores/{store_id}/funnel",
            "method": "GET",
            "latency_ms": latency,
            "status_code": 200,
            "store_id": store_id
        }
    )

    return {
        "store_id": store_id,
        "stages": [
            {
                "stage": "Entry",
                "count": c_entry,
                "dropoff_count": drop_entry,
                "dropoff_percentage": pct_entry
            },
            {
                "stage": "Zone Visit",
                "count": c_zone,
                "dropoff_count": drop_zone,
                "dropoff_percentage": pct_zone
            },
            {
                "stage": "Billing Queue",
                "count": c_billing,
                "dropoff_count": drop_billing,
                "dropoff_percentage": pct_billing
            },
            {
                "stage": "Purchase",
                "count": c_purchase,
                "dropoff_count": 0,
                "dropoff_percentage": 0.0
            }
        ]
    }
