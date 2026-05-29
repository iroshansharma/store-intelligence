import datetime
import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Event, POSTransaction
from app.logging_config import logger

router = APIRouter()

@router.get("/stores/{store_id}/metrics")
def get_store_metrics(store_id: str, db: Session = Depends(get_db)):
    start_time = datetime.datetime.utcnow()
    
    # 1. Fetch all non-staff events for the store
    events = db.query(Event).filter(
        Event.store_id == store_id,
        Event.is_staff == False
    ).order_by(Event.timestamp.asc()).all()
    
    # 2. Fetch all POS transactions for the store
    transactions = db.query(POSTransaction).filter(
        POSTransaction.store_id == store_id
    ).all()
    
    # Handle zero visitors safely
    if not events:
        return {
            "store_id": store_id,
            "unique_visitors": 0,
            "conversion_rate": 0.0,
            "avg_dwell_per_zone": {},
            "current_queue_depth": 0,
            "abandonment_rate": 0.0,
            "total_entries": 0,
            "total_exits": 0,
            "last_updated": datetime.datetime.utcnow().isoformat() + "Z"
        }
        
    # Unique visitors
    unique_visitors_set = {e.visitor_id for e in events}
    unique_visitors = len(unique_visitors_set)
    
    # Entries and Exits
    total_entries = sum(1 for e in events if e.event_type in ("ENTRY", "REENTRY"))
    total_exits = sum(1 for e in events if e.event_type == "EXIT")
    
    # Average Dwell Time per Zone
    zone_dwells = {}
    for e in events:
        if e.zone_id and e.dwell_ms and e.dwell_ms > 0:
            zone_dwells.setdefault(e.zone_id, []).append(e.dwell_ms)
            
    avg_dwell_per_zone = {
        zone: round(sum(dwells) / len(dwells))
        for zone, dwells in zone_dwells.items()
    }
    
    # Current Queue Depth
    current_queue_depth = 0
    # Search backwards for the latest queue depth
    for e in reversed(events):
        if e.metadata_json:
            try:
                meta = json.loads(e.metadata_json)
                if "queue_depth" in meta and meta["queue_depth"] is not None:
                    current_queue_depth = int(meta["queue_depth"])
                    break
            except Exception:
                pass
                
    # Abandonment Rate
    joins = sum(1 for e in events if e.event_type == "BILLING_QUEUE_JOIN")
    abandons = sum(1 for e in events if e.event_type == "BILLING_QUEUE_ABANDON")
    abandonment_rate = round(abandons / joins, 4) if joins > 0 else 0.0
    
    # Conversion Rate calculation with POS correlation
    # Rule: Converted visitor session = visitor had BILLING or BILLING_QUEUE_JOIN event within 5 mins before a POS transaction
    converted_visitors = set()
    for txn in transactions:
        txn_time = txn.timestamp
        # Find billing/join events within [txn_time - 5 mins, txn_time]
        for e in events:
            if e.event_type == "BILLING_QUEUE_JOIN" or e.zone_id == "BILLING":
                time_diff = (txn_time - e.timestamp).total_seconds()
                if 0 <= time_diff <= 300:
                    converted_visitors.add(e.visitor_id)
                    
    # Cap conversions at total visitors to handle edge cases
    converted_count = len(converted_visitors & unique_visitors_set)
    conversion_rate = round(converted_count / unique_visitors, 4) if unique_visitors > 0 else 0.0
    
    last_event_ts = max(e.timestamp for e in events).isoformat() + "Z"
    
    # Structured Log
    latency = int((datetime.datetime.utcnow() - start_time).total_seconds() * 1000)
    logger.info(
        f"Fetched metrics for {store_id}: conversion={conversion_rate}, queue={current_queue_depth}.",
        extra={
            "trace_id": "metrics-" + str(int(start_time.timestamp())),
            "endpoint": f"/stores/{store_id}/metrics",
            "method": "GET",
            "latency_ms": latency,
            "status_code": 200,
            "store_id": store_id
        }
    )
    
    return {
        "store_id": store_id,
        "unique_visitors": unique_visitors,
        "conversion_rate": conversion_rate,
        "avg_dwell_per_zone": avg_dwell_per_zone,
        "current_queue_depth": current_queue_depth,
        "abandonment_rate": abandonment_rate,
        "total_entries": total_entries,
        "total_exits": total_exits,
        "last_updated": last_event_ts
    }
