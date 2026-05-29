import datetime
import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Event, POSTransaction
from app.config import settings
from app.logging_config import logger

router = APIRouter()

@router.get("/stores/{store_id}/anomalies")
def get_store_anomalies(store_id: str, db: Session = Depends(get_db)):
    start_time = datetime.datetime.utcnow()
    anomalies = []
    
    # 1. Fetch latest event overall to anchor time calculations
    latest_event = db.query(Event).filter(
        Event.store_id == store_id
    ).order_by(Event.timestamp.desc()).first()
    
    if not latest_event:
        return anomalies
        
    latest_time = latest_event.timestamp
    now = datetime.datetime.utcnow()
    
    # --- ANOMALY 1: STALE_FEED ---
    # Triggered if no events received for store in more than 10 minutes from current server time
    time_since_last_event = (now - latest_time).total_seconds()
    if time_since_last_event > settings.STALE_FEED_THRESHOLD_SECONDS:
        anomalies.append({
            "anomaly_type": "STALE_FEED",
            "severity": "CRITICAL",
            "message": f"No telemetry feed events received for store {store_id} in {int(time_since_last_event / 60)} minutes.",
            "suggested_action": "Check CCTV agent stream status or network gateway connectivity.",
            "detected_at": now.isoformat() + "Z"
        })
        
    # --- ANOMALY 2: BILLING_QUEUE_SPIKE ---
    # Triggered if latest recorded queue depth is above threshold
    latest_queue_event = db.query(Event).filter(
        Event.store_id == store_id,
        Event.is_staff == False,
        Event.event_type == "BILLING_QUEUE_JOIN"
    ).order_by(Event.timestamp.desc(), Event.id.desc()).first()
    
    if latest_queue_event:
        try:
            meta = json.loads(latest_queue_event.metadata_json)
            q_depth = meta.get("queue_depth")
            if q_depth is not None and q_depth > settings.QUEUE_DEPTH_THRESHOLD:
                anomalies.append({
                    "anomaly_type": "BILLING_QUEUE_SPIKE",
                    "severity": "CRITICAL",
                    "message": f"Billing queue depth is currently {q_depth}, exceeding threshold of {settings.QUEUE_DEPTH_THRESHOLD}.",
                    "suggested_action": "Open another billing counter or assign floor staff to billing support.",
                    "detected_at": latest_queue_event.timestamp.isoformat() + "Z"
                })
        except Exception:
            pass
            
    # --- ANOMALY 3: CONVERSION_DROP ---
    # Calculate conversion rate and compare against baseline
    events = db.query(Event).filter(
        Event.store_id == store_id,
        Event.is_staff == False
    ).all()
    
    transactions = db.query(POSTransaction).filter(
        POSTransaction.store_id == store_id
    ).all()
    
    if events:
        unique_visitors_set = {e.visitor_id for e in events}
        unique_visitors = len(unique_visitors_set)
        
        converted_visitors = set()
        for txn in transactions:
            txn_time = txn.timestamp
            for e in events:
                if e.event_type == "BILLING_QUEUE_JOIN" or e.zone_id == "BILLING":
                    diff = (txn_time - e.timestamp).total_seconds()
                    if 0 <= diff <= 300:
                        converted_visitors.add(e.visitor_id)
                        
        converted_count = len(converted_visitors & unique_visitors_set)
        conversion_rate = converted_count / unique_visitors if unique_visitors > 0 else 0.0
        
        # Trigger anomaly if conversion rate drops below baseline (only if there are visitors)
        if unique_visitors >= 5 and conversion_rate < settings.BASE_CONVERSION_RATE:
            anomalies.append({
                "anomaly_type": "CONVERSION_DROP",
                "severity": "WARN",
                "message": f"Store conversion rate has fallen to {conversion_rate*100:.1f}%, below baseline of {settings.BASE_CONVERSION_RATE*100:.1f}%.",
                "suggested_action": "Review checkout wait times or execute standard in-store visual merchandising promotions.",
                "detected_at": latest_time.isoformat() + "Z"
            })
            
    # --- ANOMALY 4: DEAD_ZONE ---
    # Triggered if a known zone has had 0 visits in the last 30 minutes
    # We query all unique zones that have ever appeared in events (except ENTRY/EXIT)
    all_zones_query = db.query(Event.zone_id).filter(
        Event.store_id == store_id,
        Event.zone_id.isnot(None)
    ).distinct().all()
    
    known_zones = {z[0] for z in all_zones_query if z[0].upper() not in ("ENTRY", "EXIT")}
    
    thirty_mins_ago = latest_time - datetime.timedelta(seconds=settings.DEAD_ZONE_THRESHOLD_SECONDS)
    
    active_zones_query = db.query(Event.zone_id).filter(
        Event.store_id == store_id,
        Event.zone_id.isnot(None),
        Event.timestamp >= thirty_mins_ago,
        Event.timestamp <= latest_time,
        Event.event_type.in_(["ZONE_ENTER", "ZONE_DWELL", "BILLING_QUEUE_JOIN"])
    ).distinct().all()
    
    active_zones = {z[0] for z in active_zones_query}
    
    dead_zones = known_zones - active_zones
    for dz in dead_zones:
        anomalies.append({
            "anomaly_type": "DEAD_ZONE",
            "severity": "WARN",
            "message": f"No visitor activity detected in zone '{dz}' in the last 30 minutes.",
            "suggested_action": "Inspect zone footfall, review camera stream alignment, or check product inventory.",
            "detected_at": latest_time.isoformat() + "Z"
        })
        
    latency = int((datetime.datetime.utcnow() - start_time).total_seconds() * 1000)
    logger.info(
        f"Fetched anomalies for {store_id}: active_count={len(anomalies)}.",
        extra={
            "trace_id": "anomalies-" + str(int(start_time.timestamp())),
            "endpoint": f"/stores/{store_id}/anomalies",
            "method": "GET",
            "latency_ms": latency,
            "status_code": 200,
            "store_id": store_id
        }
    )
    
    return anomalies
