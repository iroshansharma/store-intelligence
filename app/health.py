import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from app.database import get_db
from app.models import Event
from app.config import settings

router = APIRouter()

@router.get("/health")
def get_health(db: Session = Depends(get_db)):
    try:
        # Test database connection
        db.execute(text("SELECT 1")).scalar()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "error",
                "database": "unavailable",
                "reason": str(e)
            }
        )
    
    # Calculate last event timestamp per store
    last_event_per_store = {}
    stale_feed_warnings = []
    
    try:
        results = db.query(
            Event.store_id,
            func.max(Event.timestamp).label("max_ts")
        ).group_by(Event.store_id).all()
        
        now = datetime.datetime.utcnow()
        for store_id, max_ts in results:
            if max_ts:
                # Store ISO format
                last_event_per_store[store_id] = max_ts.isoformat() + "Z"
                
                # Check for staleness
                delta = now - max_ts
                if delta.total_seconds() > settings.STALE_FEED_THRESHOLD_SECONDS:
                    stale_feed_warnings.append(
                        f"Store {store_id} feed is stale. Last event received at {max_ts.isoformat()}Z ({int(delta.total_seconds() / 60)} minutes ago)."
                    )
    except Exception as e:
        # If querying fails, fall back gracefully
        pass

    return {
        "status": "ok",
        "database": "ok",
        "last_event_timestamp_per_store": last_event_per_store,
        "stale_feed_warnings": stale_feed_warnings,
        "version": settings.VERSION
    }
