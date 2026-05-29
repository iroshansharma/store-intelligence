import json
import datetime
from datetime import timezone
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Event, POSTransaction
from app.logging_config import logger

router = APIRouter()

@router.post("/demo/seed", status_code=status.HTTP_201_CREATED)
def seed_demo_data(db: Session = Depends(get_db)):
    start_time = datetime.datetime.utcnow()
    store_id = "STORE_BLR_002"
    
    try:
        # 1. Clear existing events for STORE_BLR_002
        db.query(Event).filter(Event.store_id == store_id).delete()
        
        # 2. Clear existing POS transactions for STORE_BLR_002
        db.query(POSTransaction).filter(POSTransaction.store_id == store_id).delete()
        db.commit()
        
        # 3. Base Time setup (current UTC time)
        base_time = datetime.datetime.now(timezone.utc)
        
        # Timeline scaling helper
        def get_time_naive(orig_mins: float, extra_secs: float = 0.0) -> datetime.datetime:
            total_orig_mins = orig_mins + extra_secs / 60.0
            scaled_mins = total_orig_mins * (10.0 / 45.0)
            dt_utc = base_time - datetime.timedelta(minutes=10) + datetime.timedelta(minutes=scaled_mins)
            return dt_utc.astimezone(timezone.utc).replace(tzinfo=None)
            
        events_to_insert: List[Event] = []
        
        # A. Staff Patrol Events (10 events)
        for i in range(5):
            t_offset = i * 10
            events_to_insert.append(Event(
                event_id=f"EV_staff_{i}_enter",
                store_id=store_id,
                camera_id="CAM_FLOOR_01",
                visitor_id="VIS_staff_99",
                event_type="ZONE_ENTER",
                timestamp=get_time_naive(t_offset),
                zone_id="SKINCARE",
                is_staff=True,
                confidence=0.98,
                metadata_json=json.dumps({"session_seq": i+1})
            ))
            events_to_insert.append(Event(
                event_id=f"EV_staff_{i}_dwell",
                store_id=store_id,
                camera_id="CAM_FLOOR_01",
                visitor_id="VIS_staff_99",
                event_type="ZONE_DWELL",
                timestamp=get_time_naive(t_offset, 30),
                zone_id="SKINCARE",
                dwell_ms=30000,
                is_staff=True,
                confidence=0.97,
                metadata_json=json.dumps({"session_seq": i+2})
            ))

        # B. Convert Visitors matching POS transactions (25 events)
        conversions = [
            {"vid": "VIS_conv_1", "entry": 14, "zone": "SKINCARE", "join": 14, "exit": 16},
            {"vid": "VIS_conv_2", "entry": 18, "zone": "HAIRCARE", "join": 21, "exit": 24},
            {"vid": "VIS_conv_3", "entry": 23, "zone": "SKINCARE", "join": 26, "exit": 29},
            {"vid": "VIS_conv_4", "entry": 27, "zone": "HAIRCARE", "join": 30, "exit": 33},
            {"vid": "VIS_conv_5", "entry": 32, "zone": "SKINCARE", "join": 36, "exit": 39},
        ]
        for c in conversions:
            vid = c["vid"]
            # Entry
            events_to_insert.append(Event(
                event_id=f"EV_{vid}_entry",
                store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id=vid,
                event_type="ENTRY", timestamp=get_time_naive(c["entry"]),
                zone_id="ENTRY", dwell_ms=1000, confidence=0.99
            ))
            # Zone enter
            events_to_insert.append(Event(
                event_id=f"EV_{vid}_zone_enter",
                store_id=store_id, camera_id="CAM_FLOOR_01", visitor_id=vid,
                event_type="ZONE_ENTER", timestamp=get_time_naive(c["entry"], 30),
                zone_id=c["zone"], confidence=0.95
            ))
            # Zone dwell
            events_to_insert.append(Event(
                event_id=f"EV_{vid}_zone_dwell",
                store_id=store_id, camera_id="CAM_FLOOR_01", visitor_id=vid,
                event_type="ZONE_DWELL", timestamp=get_time_naive(c["entry"], 45),
                zone_id=c["zone"], dwell_ms=45000, confidence=0.96
            ))
            # Queue join
            events_to_insert.append(Event(
                event_id=f"EV_{vid}_queue_join",
                store_id=store_id, camera_id="CAM_BILLING_01", visitor_id=vid,
                event_type="BILLING_QUEUE_JOIN", timestamp=get_time_naive(c["join"]),
                zone_id="BILLING", dwell_ms=60000, confidence=0.94,
                metadata_json=json.dumps({"queue_depth": 2})
            ))
            # Exit
            events_to_insert.append(Event(
                event_id=f"EV_{vid}_exit",
                store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id=vid,
                event_type="EXIT", timestamp=get_time_naive(c["exit"]),
                zone_id="ENTRY", dwell_ms=1200, confidence=0.99
            ))

        # C. Billing Queue Spike Events (18 events)
        for q_idx in range(6):
            vid = f"VIS_spike_{q_idx}"
            q_depth = q_idx + 2
            events_to_insert.append(Event(
                event_id=f"EV_{vid}_entry",
                store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id=vid,
                event_type="ENTRY", timestamp=get_time_naive(40 + q_idx),
                zone_id="ENTRY"
            ))
            events_to_insert.append(Event(
                event_id=f"EV_{vid}_zone_enter",
                store_id=store_id, camera_id="CAM_FLOOR_01", visitor_id=vid,
                event_type="ZONE_ENTER", timestamp=get_time_naive(41 + q_idx),
                zone_id="SKINCARE"
            ))
            events_to_insert.append(Event(
                event_id=f"EV_{vid}_queue_join",
                store_id=store_id, camera_id="CAM_BILLING_01", visitor_id=vid,
                event_type="BILLING_QUEUE_JOIN", timestamp=get_time_naive(44),
                zone_id="BILLING", confidence=0.92,
                metadata_json=json.dumps({"queue_depth": q_depth})
            ))

        # D. Billing Queue Abandonment (8 events)
        abandoners = [
            {"vid": "VIS_ab_1", "entry": 10, "join": 12, "abandon": 14, "exit": 15},
            {"vid": "VIS_ab_2", "entry": 35, "join": 38, "abandon": 41, "exit": 42}
        ]
        for a in abandoners:
            vid = a["vid"]
            events_to_insert.append(Event(
                event_id=f"EV_{vid}_entry",
                store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id=vid,
                event_type="ENTRY", timestamp=get_time_naive(a["entry"]),
                zone_id="ENTRY"
            ))
            events_to_insert.append(Event(
                event_id=f"EV_{vid}_queue_join",
                store_id=store_id, camera_id="CAM_BILLING_01", visitor_id=vid,
                event_type="BILLING_QUEUE_JOIN", timestamp=get_time_naive(a["join"]),
                zone_id="BILLING", metadata_json=json.dumps({"queue_depth": 3})
            ))
            events_to_insert.append(Event(
                event_id=f"EV_{vid}_queue_abandon",
                store_id=store_id, camera_id="CAM_BILLING_01", visitor_id=vid,
                event_type="BILLING_QUEUE_ABANDON", timestamp=get_time_naive(a["abandon"]),
                zone_id="BILLING"
            ))
            events_to_insert.append(Event(
                event_id=f"EV_{vid}_exit",
                store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id=vid,
                event_type="EXIT", timestamp=get_time_naive(a["exit"]),
                zone_id="ENTRY"
            ))

        # E. Re-entry visitor (4 events)
        events_to_insert.append(Event(
            event_id="EV_reenter_entry1",
            store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id="VIS_reenter",
            event_type="ENTRY", timestamp=get_time_naive(2),
            zone_id="ENTRY"
        ))
        events_to_insert.append(Event(
            event_id="EV_reenter_exit1",
            store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id="VIS_reenter",
            event_type="EXIT", timestamp=get_time_naive(5),
            zone_id="ENTRY"
        ))
        events_to_insert.append(Event(
            event_id="EV_reenter_entry2",
            store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id="VIS_reenter",
            event_type="REENTRY", timestamp=get_time_naive(10),
            zone_id="ENTRY"
        ))
        events_to_insert.append(Event(
            event_id="EV_reenter_exit2",
            store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id="VIS_reenter",
            event_type="EXIT", timestamp=get_time_naive(15),
            zone_id="ENTRY"
        ))

        # F. Non-converting browsers (40 events)
        for idx in range(10):
            vid = f"VIS_browse_{idx}"
            entry_min = 5 + idx * 4
            zone = "MAKEUP" if entry_min < 15 else ("SKINCARE" if idx % 2 == 0 else "HAIRCARE")
            
            events_to_insert.append(Event(
                event_id=f"EV_{vid}_entry",
                store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id=vid,
                event_type="ENTRY", timestamp=get_time_naive(entry_min),
                zone_id="ENTRY"
            ))
            events_to_insert.append(Event(
                event_id=f"EV_{vid}_zone_enter",
                store_id=store_id, camera_id="CAM_FLOOR_01", visitor_id=vid,
                event_type="ZONE_ENTER", timestamp=get_time_naive(entry_min, 20),
                zone_id=zone
            ))
            events_to_insert.append(Event(
                event_id=f"EV_{vid}_zone_dwell",
                store_id=store_id, camera_id="CAM_FLOOR_01", visitor_id=vid,
                event_type="ZONE_DWELL", timestamp=get_time_naive(entry_min, 30),
                zone_id=zone, dwell_ms=15000
            ))
            events_to_insert.append(Event(
                event_id=f"EV_{vid}_exit",
                store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id=vid,
                event_type="EXIT", timestamp=get_time_naive(entry_min + 3),
                zone_id="ENTRY"
            ))

        # Save all generated events in bulk
        if events_to_insert:
            db.bulk_save_objects(events_to_insert)

        # G. Generate and save perfectly aligned POS Transactions (5 transactions)
        # We align with convert visitors: VIS_conv_1 (join @ 14 mins), conv_2 (join @ 21), etc.
        pos_txns_to_insert: List[POSTransaction] = []
        pos_details = [
            {"txn_id": "TXN_DEMO_1001", "join_min": 14, "value": 1250.50},
            {"txn_id": "TXN_DEMO_1002", "join_min": 21, "value": 890.00},
            {"txn_id": "TXN_DEMO_1003", "join_min": 26, "value": 2300.00},
            {"txn_id": "TXN_DEMO_1004", "join_min": 30, "value": 450.00},
            {"txn_id": "TXN_DEMO_1005", "join_min": 36, "value": 3120.00},
        ]
        
        for detail in pos_details:
            # Transaction is exactly 1 minute after queue join time to ensure perfect 5-min correlation window
            txn_ts = get_time_naive(detail["join_min"], 60.0)
            pos_txns_to_insert.append(POSTransaction(
                store_id=store_id,
                transaction_id=detail["txn_id"],
                timestamp=txn_ts,
                basket_value_inr=detail["value"]
            ))

        if pos_txns_to_insert:
            db.bulk_save_objects(pos_txns_to_insert)

        # Commit transactions to the SQLite database
        db.commit()

        # Track latency and log seed execution
        latency = int((datetime.datetime.utcnow() - start_time).total_seconds() * 1000)
        logger.info(
            f"Successfully seeded demo database for {store_id}: 105 events, 5 POS transactions.",
            extra={
                "trace_id": "demo-seed-" + str(int(start_time.timestamp())),
                "endpoint": "/demo/seed",
                "method": "POST",
                "latency_ms": latency,
                "status_code": 201,
                "store_id": store_id
            }
        )

        return {
            "store_id": store_id,
            "events_inserted": len(events_to_insert),
            "pos_transactions_inserted": len(pos_txns_to_insert),
            "message": "Demo data seeded successfully"
        }
    except Exception as ex:
        db.rollback()
        logger.error(f"Failed to seed demo database: {str(ex)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to seed demo data: {str(ex)}"
        )
