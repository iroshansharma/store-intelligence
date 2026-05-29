import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Event
from app.logging_config import logger

router = APIRouter()

@router.get("/stores/{store_id}/heatmap")
def get_store_heatmap(store_id: str, db: Session = Depends(get_db)):
    start_time = datetime.datetime.utcnow()
    
    # 1. Calculate total unique visitor sessions in the store to determine data confidence
    unique_visitors_count = db.query(func.count(func.distinct(Event.visitor_id))).filter(
        Event.store_id == store_id,
        Event.is_staff == False
    ).scalar() or 0
    
    data_confidence = "HIGH" if unique_visitors_count >= 20 else "LOW"
    
    # 2. Fetch all unique visitor events grouped by zone to calculate visit counts
    # A visit is counted when event_type is ZONE_ENTER, BILLING_QUEUE_JOIN, ENTRY, or REENTRY
    visit_results = db.query(
        Event.zone_id,
        func.count(Event.id).label("visit_count")
    ).filter(
        Event.store_id == store_id,
        Event.is_staff == False,
        Event.zone_id.isnot(None),
        Event.event_type.in_(["ZONE_ENTER", "BILLING_QUEUE_JOIN", "ENTRY", "REENTRY"])
    ).group_by(Event.zone_id).all()
    
    # 3. Fetch average dwell time per zone (averaging only non-zero dwell events)
    dwell_results = db.query(
        Event.zone_id,
        func.avg(Event.dwell_ms).label("avg_dwell")
    ).filter(
        Event.store_id == store_id,
        Event.is_staff == False,
        Event.zone_id.isnot(None),
        Event.dwell_ms > 0
    ).group_by(Event.zone_id).all()
    
    dwell_map = {row.zone_id: round(row.avg_dwell) for row in dwell_results if row.zone_id}
    
    # Compile raw heatmap items
    heatmap_data = []
    max_visits = 0
    
    for row in visit_results:
        zone_id = row.zone_id
        if not zone_id:
            continue
        visit_cnt = row.visit_count
        if visit_cnt > max_visits:
            max_visits = visit_cnt
            
        heatmap_data.append({
            "zone_id": zone_id,
            "visit_count": visit_cnt,
            "avg_dwell_ms": dwell_map.get(zone_id, 0),
            "normalized_score": 0,
            "data_confidence": data_confidence
        })
        
    # Normalize score from 0 to 100 based on the zone with highest visit count
    for item in heatmap_data:
        if max_visits > 0:
            item["normalized_score"] = round((item["visit_count"] / max_visits) * 100)
            
    latency = int((datetime.datetime.utcnow() - start_time).total_seconds() * 1000)
    logger.info(
        f"Fetched heatmap for {store_id}: confidence={data_confidence}, zones_count={len(heatmap_data)}.",
        extra={
            "trace_id": "heatmap-" + str(int(start_time.timestamp())),
            "endpoint": f"/stores/{store_id}/heatmap",
            "method": "GET",
            "latency_ms": latency,
            "status_code": 200,
            "store_id": store_id
        }
    )
    
    return heatmap_data
