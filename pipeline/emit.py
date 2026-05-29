import json
import uuid
import datetime
from typing import Dict, Any, Optional

# Supported event_type enum values as a quick local check
VALID_EVENT_TYPES = {
    "ENTRY",
    "EXIT",
    "ZONE_ENTER",
    "ZONE_EXIT",
    "ZONE_DWELL",
    "BILLING_QUEUE_JOIN",
    "BILLING_QUEUE_ABANDON",
    "REENTRY"
}

def emit_event(
    store_id: str,
    camera_id: str,
    visitor_id: str,
    event_type: str,
    timestamp: Optional[datetime.datetime] = None,
    zone_id: Optional[str] = None,
    dwell_ms: int = 0,
    is_staff: bool = False,
    confidence: float = 1.0,
    metadata: Optional[Dict[str, Any]] = None,
    event_id: Optional[str] = None
) -> str:
    """
    Constructs a JSON lines compatible event string after ensuring standard format.
    """
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(f"Invalid event_type: {event_type}. Must be one of {VALID_EVENT_TYPES}")
        
    evt_id = event_id or str(uuid.uuid4())
    ts = timestamp or datetime.datetime.utcnow()
    
    # Format timestamp to ISO UTC string
    if isinstance(ts, datetime.datetime):
        ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        ts_str = str(ts)
        
    event_payload = {
        "event_id": evt_id,
        "store_id": store_id,
        "camera_id": camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": ts_str,
        "zone_id": zone_id,
        "dwell_ms": dwell_ms,
        "is_staff": is_staff,
        "confidence": round(confidence, 2),
        "metadata": metadata or {}
    }
    
    return json.dumps(event_payload)
