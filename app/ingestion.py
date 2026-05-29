import datetime
import json
from enum import Enum
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Event
from app.logging_config import logger

router = APIRouter()

class EventType(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    ZONE_ENTER = "ZONE_ENTER"
    ZONE_EXIT = "ZONE_EXIT"
    ZONE_DWELL = "ZONE_DWELL"
    BILLING_QUEUE_JOIN = "BILLING_QUEUE_JOIN"
    BILLING_QUEUE_ABANDON = "BILLING_QUEUE_ABANDON"
    REENTRY = "REENTRY"

class EventSchema(BaseModel):
    event_id: str
    store_id: str
    camera_id: str
    visitor_id: str
    event_type: EventType
    timestamp: datetime.datetime
    zone_id: Optional[str] = None
    dwell_ms: Optional[int] = 0
    is_staff: Optional[bool] = False
    confidence: Optional[float] = 1.0
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class IngestRequest(BaseModel):
    events: List[Any]  # Use Any first so we can manually validate and track indices

class IngestResponse(BaseModel):
    accepted_count: int
    duplicate_count: int
    rejected_count: int
    errors: List[Dict[str, Any]]

@router.post("/events/ingest", response_model=IngestResponse)
def ingest_events(payload: IngestRequest, db: Session = Depends(get_db)):
    start_time = datetime.datetime.utcnow()
    
    # Rule: Accept batches up to 500 events
    if len(payload.events) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch size exceeds maximum limit of 500 events."
        )
        
    accepted_count = 0
    duplicate_count = 0
    rejected_count = 0
    errors = []
    
    # First pass: parse and validate schema
    valid_events: List[EventSchema] = []
    validated_ids = set()
    
    for idx, raw_event in enumerate(payload.events):
        try:
            # Validate schema
            event_obj = EventSchema.model_validate(raw_event)
            
            # Check for duplicates within the incoming batch itself
            if event_obj.event_id in validated_ids:
                duplicate_count += 1
                continue
                
            validated_ids.add(event_obj.event_id)
            valid_events.append(event_obj)
        except ValidationError as ve:
            rejected_count += 1
            # Extract clean validation error message
            err_msg = "; ".join([f"{e['loc'][-1] if e['loc'] else 'root'}: {e['msg']}" for e in ve.errors()])
            errors.append({
                "index": idx,
                "reason": err_msg
            })
        except Exception as ex:
            rejected_count += 1
            errors.append({
                "index": idx,
                "reason": str(ex)
            })

    # Second pass: query existing IDs in DB to handle idempotency
    if valid_events:
        batch_ids = [e.event_id for e in valid_events]
        db_existing = db.query(Event.event_id).filter(Event.event_id.in_(batch_ids)).all()
        db_existing_ids = {row[0] for row in db_existing}
        
        events_to_insert = []
        for e in valid_events:
            if e.event_id in db_existing_ids:
                duplicate_count += 1
            else:
                # Standardize datetime to timezone-naive UTC for SQLite
                naive_ts = e.timestamp.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                
                # Build database model
                db_event = Event(
                    event_id=e.event_id,
                    store_id=e.store_id,
                    camera_id=e.camera_id,
                    visitor_id=e.visitor_id,
                    event_type=e.event_type.value,
                    timestamp=naive_ts,
                    zone_id=e.zone_id,
                    dwell_ms=e.dwell_ms,
                    is_staff=e.is_staff,
                    confidence=e.confidence,
                    metadata_json=json.dumps(e.metadata) if e.metadata else None
                )
                events_to_insert.append(db_event)
                accepted_count += 1
                
        if events_to_insert:
            try:
                db.bulk_save_objects(events_to_insert)
                db.commit()
            except Exception as commit_ex:
                db.rollback()
                logger.error(f"Failed to commit bulk event ingestion: {str(commit_ex)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database save operation failed."
                )

    # Track structured log metadata
    latency = int((datetime.datetime.utcnow() - start_time).total_seconds() * 1000)
    store_id = valid_events[0].store_id if valid_events else "UNKNOWN"
    
    # Custom logger call
    logger.info(
        f"Ingested {len(payload.events)} events: {accepted_count} accepted, {duplicate_count} duplicates, {rejected_count} rejected.",
        extra={
            "trace_id": "ingest-" + str(int(start_time.timestamp())),
            "endpoint": "/events/ingest",
            "method": "POST",
            "latency_ms": latency,
            "status_code": 200,
            "store_id": store_id,
            "event_count": len(payload.events)
        }
    )

    return IngestResponse(
        accepted_count=accepted_count,
        duplicate_count=duplicate_count,
        rejected_count=rejected_count,
        errors=errors
    )
