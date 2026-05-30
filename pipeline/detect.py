import os
import sys
import json
import argparse
import datetime
from datetime import timezone
import random
from typing import List, Dict, Any, Optional

from pipeline.emit import emit_event, VALID_EVENT_TYPES
from pipeline.zones import ZoneMapper
from pipeline.tracker import VisitorTracker

def run_simulation(store_id: str, camera_id: str, layout_path: str, output_path: str, start_time: Optional[str] = None, generate_pos: bool = False, pos_output: str = "sample_data/pos_transactions.csv"):
    """
    Generates rich, high-fidelity synthetic telemetry events.
    Includes:
    - 22 unique visitors
    - Staff patrols (is_staff=true)
    - Sequential funnels (Entry -> Zone -> Queue -> Exit/Purchase)
    - Queue depths up to 7 (triggers BILLING_QUEUE_SPIKE anomaly)
    - A deliberate DEAD_ZONE (e.g. no activity in 'MAKEUP' for the last 40 minutes)
    - Re-entries and queue abandons
    """
    print(f"Starting simulation mode for store: {store_id}...")
    
    # Read layout if available to align zones
    mapper = ZoneMapper(layout_path)
    zones = [z["zone_id"] for z in mapper.zones] if mapper.zones else ["ENTRY", "SKINCARE", "HAIRCARE", "MAKEUP", "BILLING"]
    
    events: List[str] = []
    
    # Reference start time
    if start_time:
        clean_str = start_time.strip().replace('Z', '+00:00')
        base_time = datetime.datetime.fromisoformat(clean_str).astimezone(timezone.utc)
    else:
        base_time = datetime.datetime.now(timezone.utc)
        
    # Scale the original 45-minute timeline into a 10-minute window ending at base_time.
    # Events will be spread across the last 10 minutes prior to base_time, i.e., [base_time - 10m, base_time].
    def get_time(orig_mins: float, extra_secs: float = 0.0) -> datetime.datetime:
        total_orig_mins = orig_mins + extra_secs / 60.0
        scaled_mins = total_orig_mins * (10.0 / 45.0)
        return base_time - datetime.timedelta(minutes=10) + datetime.timedelta(minutes=scaled_mins)
    
    # 1. Staff Patrol Events (VIS_staff_01, VIS_staff_02)
    # Patrolling Skincare and Haircare
    for i in range(5):
        t_offset = i * 10
        patrol_time = get_time(t_offset)
        events.append(emit_event(
            store_id=store_id,
            camera_id="CAM_FLOOR_01",
            visitor_id="VIS_staff_99",
            event_type="ZONE_ENTER",
            timestamp=patrol_time,
            zone_id="SKINCARE",
            is_staff=True,
            confidence=0.98,
            metadata={"session_seq": i+1}
        ))
        events.append(emit_event(
            store_id=store_id,
            camera_id="CAM_FLOOR_01",
            visitor_id="VIS_staff_99",
            event_type="ZONE_DWELL",
            timestamp=get_time(t_offset, 30),
            zone_id="SKINCARE",
            dwell_ms=30000,
            is_staff=True,
            confidence=0.97,
            metadata={"session_seq": i+2}
        ))

    # 2. Convert Visitors matching pos_transactions.csv
    # Seeded transactions include: TXN_1001 (14:15), TXN_1002 (14:22), TXN_1003 (14:28), TXN_1004 (14:32), TXN_1005 (14:37)
    # We create visitor IDs that correlate perfectly with these transactions:
    conversions = [
        {"vid": "VIS_conv_1", "entry": 14, "zone": "SKINCARE", "join": 14, "exit": 16, "txn_time": 15},
        {"vid": "VIS_conv_2", "entry": 18, "zone": "HAIRCARE", "join": 21, "exit": 24, "txn_time": 22},
        {"vid": "VIS_conv_3", "entry": 23, "zone": "SKINCARE", "join": 26, "exit": 29, "txn_time": 28},
        {"vid": "VIS_conv_4", "entry": 27, "zone": "HAIRCARE", "join": 30, "exit": 33, "txn_time": 32},
        {"vid": "VIS_conv_5", "entry": 32, "zone": "SKINCARE", "join": 36, "exit": 39, "txn_time": 37},
    ]
    
    for c in conversions:
        vid = c["vid"]
        # Entry
        events.append(emit_event(
            store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id=vid,
            event_type="ENTRY", timestamp=get_time(c["entry"]),
            zone_id="ENTRY", dwell_ms=1000, confidence=0.99
        ))
        # Zone enter
        events.append(emit_event(
            store_id=store_id, camera_id="CAM_FLOOR_01", visitor_id=vid,
            event_type="ZONE_ENTER", timestamp=get_time(c["entry"], 30),
            zone_id=c["zone"], confidence=0.95
        ))
        # Zone dwell
        events.append(emit_event(
            store_id=store_id, camera_id="CAM_FLOOR_01", visitor_id=vid,
            event_type="ZONE_DWELL", timestamp=get_time(c["entry"], 45),
            zone_id=c["zone"], dwell_ms=45000, confidence=0.96
        ))
        # Queue join
        events.append(emit_event(
            store_id=store_id, camera_id="CAM_BILLING_01", visitor_id=vid,
            event_type="BILLING_QUEUE_JOIN", timestamp=get_time(c["join"]),
            zone_id="BILLING", dwell_ms=60000, confidence=0.94,
            metadata={"queue_depth": 2}
        ))
        # Exit
        events.append(emit_event(
            store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id=vid,
            event_type="EXIT", timestamp=get_time(c["exit"]),
            zone_id="ENTRY", dwell_ms=1200, confidence=0.99
        ))

    # 3. Billing Queue Spike Event (Spike depth to 7, threshold is 5)
    # We simulate a burst of customers arriving at billing around 14:45
    for q_idx in range(6):
        vid = f"VIS_spike_{q_idx}"
        q_depth = q_idx + 2  # Max depth 7
        events.append(emit_event(
            store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id=vid,
            event_type="ENTRY", timestamp=get_time(40 + q_idx),
            zone_id="ENTRY"
        ))
        events.append(emit_event(
            store_id=store_id, camera_id="CAM_FLOOR_01", visitor_id=vid,
            event_type="ZONE_ENTER", timestamp=get_time(41 + q_idx),
            zone_id="SKINCARE"
        ))
        events.append(emit_event(
            store_id=store_id, camera_id="CAM_BILLING_01", visitor_id=vid,
            event_type="BILLING_QUEUE_JOIN", timestamp=get_time(44),
            zone_id="BILLING", confidence=0.92,
            metadata={"queue_depth": q_depth}
        ))

    # 4. Billing Queue Abandonment Visitors (joins then abandons)
    abandoners = [
        {"vid": "VIS_ab_1", "entry": 10, "join": 12, "abandon": 14, "exit": 15},
        {"vid": "VIS_ab_2", "entry": 35, "join": 38, "abandon": 41, "exit": 42}
    ]
    for a in abandoners:
        vid = a["vid"]
        events.append(emit_event(
            store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id=vid,
            event_type="ENTRY", timestamp=get_time(a["entry"]),
            zone_id="ENTRY"
        ))
        events.append(emit_event(
            store_id=store_id, camera_id="CAM_BILLING_01", visitor_id=vid,
            event_type="BILLING_QUEUE_JOIN", timestamp=get_time(a["join"]),
            zone_id="BILLING", metadata={"queue_depth": 3}
        ))
        events.append(emit_event(
            store_id=store_id, camera_id="CAM_BILLING_01", visitor_id=vid,
            event_type="BILLING_QUEUE_ABANDON", timestamp=get_time(a["abandon"]),
            zone_id="BILLING"
        ))
        events.append(emit_event(
            store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id=vid,
            event_type="EXIT", timestamp=get_time(a["exit"]),
            zone_id="ENTRY"
        ))

    # 5. Re-entry visitor
    # VIS_reenter enters at 14:02, exits 14:05, re-enters at 14:10, exits 14:15
    events.append(emit_event(
        store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id="VIS_reenter",
        event_type="ENTRY", timestamp=get_time(2),
        zone_id="ENTRY"
    ))
    events.append(emit_event(
        store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id="VIS_reenter",
        event_type="EXIT", timestamp=get_time(5),
        zone_id="ENTRY"
    ))
    events.append(emit_event(
        store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id="VIS_reenter",
        event_type="REENTRY", timestamp=get_time(10),
        zone_id="ENTRY"
    ))
    events.append(emit_event(
        store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id="VIS_reenter",
        event_type="EXIT", timestamp=get_time(15),
        zone_id="ENTRY"
    ))

    # 6. Rest of non-converting visitors to cross the "20+ visitors" requirement
    # We add 10 additional browsers who just enter, visit SKINCARE or HAIRCARE, dwell, and leave.
    # Note: MAKEUP zone is deliberately excluded after 14:20 to trigger the DEAD_ZONE anomaly!
    for idx in range(10):
        vid = f"VIS_browse_{idx}"
        entry_min = 5 + idx * 4
        # Allocate zone
        zone = "MAKEUP" if entry_min < 15 else ("SKINCARE" if idx % 2 == 0 else "HAIRCARE")
        
        events.append(emit_event(
            store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id=vid,
            event_type="ENTRY", timestamp=get_time(entry_min),
            zone_id="ENTRY"
        ))
        events.append(emit_event(
            store_id=store_id, camera_id="CAM_FLOOR_01", visitor_id=vid,
            event_type="ZONE_ENTER", timestamp=get_time(entry_min, 20),
            zone_id=zone
        ))
        events.append(emit_event(
            store_id=store_id, camera_id="CAM_FLOOR_01", visitor_id=vid,
            event_type="ZONE_DWELL", timestamp=get_time(entry_min, 30),
            zone_id=zone, dwell_ms=15000
        ))
        events.append(emit_event(
            store_id=store_id, camera_id="CAM_ENTRY_01", visitor_id=vid,
            event_type="EXIT", timestamp=get_time(entry_min + 3),
            zone_id="ENTRY"
        ))

    # Ensure output directory exists
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        
    with open(output_path, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(ev + "\n")
            
    print(f"Generated {len(events)} synthetic events successfully in: {output_path}")

    # Generate and save aligned POS transactions CSV if requested
    if generate_pos:
        pos_dir = os.path.dirname(pos_output)
        if pos_dir:
            os.makedirs(pos_dir, exist_ok=True)
        
        pos_txns = [
            {"txn_id": "TXN_1001", "min": 15, "value": 1250.50},
            {"txn_id": "TXN_1002", "min": 22, "value": 890.00},
            {"txn_id": "TXN_1003", "min": 28, "value": 2300.00},
            {"txn_id": "TXN_1004", "min": 32, "value": 450.00},
            {"txn_id": "TXN_1005", "min": 37, "value": 3120.00},
            {"txn_id": "TXN_1006", "min": 41, "value": 1750.00},
            {"txn_id": "TXN_1007", "min": 45, "value": 950.00},
            {"txn_id": "TXN_1008", "min": 49, "value": 120.00},
            {"txn_id": "TXN_1009", "min": 52, "value": 1890.00},
            {"txn_id": "TXN_1010", "min": 58, "value": 2750.00},
        ]
        with open(pos_output, "w", encoding="utf-8") as f:
            f.write("store_id,transaction_id,timestamp,basket_value_inr\n")
            for txn in pos_txns:
                txn_dt = get_time(txn["min"])
                ts_str = txn_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                f.write(f"{store_id},{txn['txn_id']},{ts_str},{txn['value']:.2f}\n")
        print(f"Generated 10 synthetic POS transactions successfully in: {pos_output}")

def run_video_inference(
    video_path: str,
    store_id: str,
    camera_id: str,
    layout_path: str,
    output_path: str,
    conf_threshold: float = 0.15,
    frame_skip: int = 10,
    max_frames: int = 3000,
    debug_detections: bool = False
):
    """
    Simulates OpenCV frame loading and attempts YOLOv8 inference if ultralytics is present.
    Processes frame-by-frame with skip and max-frame bounds.
    If YOLO tracking/detections fail, falls back to low-confidence detections or OpenCV motion detection.
    """
    print(f"Initializing CCTV video inference for video: {video_path}...")
    
    # Check OpenCV
    try:
        import cv2
    except ImportError:
        print("Error: OpenCV is not installed. Please run 'pip install opencv-python' or use headless version.", file=sys.stderr)
        sys.exit(1)
        
    # Attempt Ultralytics YOLO import
    yolo_installed = False
    try:
        from ultralytics import YOLO
        yolo_installed = True
    except ImportError:
        print("\n" + "="*80)
        print("NOTICE: YOLOv8 library ('ultralytics') is not installed in the current environment.")
        print("To execute live deep-learning person tracking on real CCTV files, run:")
        print("   pip install ultralytics")
        print("\nFalling back safely. Please execute the pipeline using the --simulate mode instead:")
        print("   python -m pipeline.detect --simulate")
        print("="*80 + "\n")
        sys.exit(1)

    # If YOLO is installed, execute person detection
    if yolo_installed:
        print("Loading YOLOv8 person detector...")
        model = YOLO("yolov8n.pt")  # Use nano model for quick execution
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"Error: Unable to open video file at {video_path}", file=sys.stderr)
            sys.exit(1)
            
        mapper = ZoneMapper(layout_path)
        tracker = VisitorTracker()
        
        events_emitted = []
        frame_idx = 0
        yolo_detections_count = 0
        tracked_ids = set()
        
        # Initialize background subtractor for OpenCV motion detection fallback
        fgbg = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=True)
        
        print("Running detection pipeline...")
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            if frame_idx >= max_frames:
                break
                
            if frame_idx % frame_skip != 0:
                frame_idx += 1
                continue
                
            timestamp = datetime.datetime.now(timezone.utc)
            
            # Run YOLO on frame, filtering for "person" class (class 0 in COCO)
            # Use conf=conf_threshold to restrict low-confidence detections
            results = model.track(frame, persist=True, conf=conf_threshold, classes=[0], verbose=False)
            
            person_boxes = []
            if results and results[0].boxes:
                for box in results[0].boxes:
                    conf = float(box.conf[0])
                    if conf >= conf_threshold:
                        person_boxes.append(box)
            
            if person_boxes:
                yolo_detections_count += len(person_boxes)
                for box_idx, box in enumerate(person_boxes):
                    # Retrieve bounding coordinates and confidence
                    xyxy = box.xyxy[0].tolist()
                    conf = float(box.conf[0])
                    
                    # Center of bounding box
                    cx = (xyxy[0] + xyxy[2]) / 2.0
                    cy = (xyxy[1] + xyxy[3]) / 2.0
                    
                    # Normalize camera ID and perform zone assignment with coordinate approximations
                    norm_cam = camera_id.upper().replace(" ", "_")
                    if "CAM_1" in norm_cam or "CAM1" in norm_cam or "ENTRY" in norm_cam:
                        mapped_cam_id = "CAM_ENTRY_01"
                    elif "CAM_4" in norm_cam or "CAM4" in norm_cam or "BILLING" in norm_cam:
                        mapped_cam_id = "CAM_BILLING_01"
                    else:
                        mapped_cam_id = "CAM_FLOOR_01"
                        
                    zone_id = mapper.get_zone_at_coordinate(mapped_cam_id, cx, cy)
                    if not zone_id:
                        # Spatial approximation fallbacks
                        if mapped_cam_id == "CAM_ENTRY_01":
                            zone_id = "ENTRY"
                        elif mapped_cam_id == "CAM_BILLING_01":
                            zone_id = "BILLING"
                        else:
                            if cy < 800:
                                zone_id = "SKINCARE" if cx < 960 else "HAIRCARE"
                            else:
                                zone_id = "MAKEUP"
                                
                    # Determine event type (ZONE_ENTER on first few detections/periodically, DWELL otherwise)
                    event_type = "ZONE_ENTER" if frame_idx % 30 == 0 else "ZONE_DWELL"
                    
                    if box.id is not None:
                        track_id = int(box.id[0])
                        tracked_ids.add(track_id)
                        visitor_id = tracker.get_visitor_id(track_id)
                        
                        evt = emit_event(
                            store_id=store_id,
                            camera_id=camera_id,
                            visitor_id=visitor_id,
                            event_type=event_type,
                            timestamp=timestamp,
                            zone_id=zone_id,
                            dwell_ms=1000,
                            confidence=conf
                        )
                        events_emitted.append(evt)
                        if debug_detections:
                            print(f"[DEBUG YOLO] Tracked Person: visitor_id={visitor_id}, zone_id={zone_id}, conf={conf:.2f}")
                    else:
                        # YOLO detects persons but no tracking events are generated (tracking ID is missing)
                        # Emit low-confidence zone activity event based on bounding box center location
                        untracked_visitor_id = f"VIS_untracked_f{frame_idx}_b{box_idx}"
                        evt = emit_event(
                            store_id=store_id,
                            camera_id=camera_id,
                            visitor_id=untracked_visitor_id,
                            event_type=event_type,
                            timestamp=timestamp,
                            zone_id=zone_id,
                            dwell_ms=1000,
                            confidence=min(conf, 0.15)
                        )
                        events_emitted.append(evt)
                        if debug_detections:
                            print(f"[DEBUG YOLO] Untracked Person Fallback: visitor_id={untracked_visitor_id}, zone_id={zone_id}, conf={conf:.2f}")
            else:
                # YOLO detected NO persons -> OpenCV motion fallback!
                # Apply background subtraction
                fgmask = fgbg.apply(frame)
                
                # Morphological noise removal & thresholding
                _, thresh = cv2.threshold(fgmask, 200, 255, cv2.THRESH_BINARY)
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
                thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
                thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
                
                # Find contours
                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                for c_idx, contour in enumerate(contours):
                    area = cv2.contourArea(contour)
                    if area < 500:  # Ignore small motion noise
                        continue
                        
                    # Compute contour centroid
                    x, y, w, h = cv2.boundingRect(contour)
                    cx = x + w / 2.0
                    cy = y + h / 2.0
                    
                    # Normalize camera ID and perform zone assignment with coordinate approximations
                    norm_cam = camera_id.upper().replace(" ", "_")
                    if "CAM_1" in norm_cam or "CAM1" in norm_cam or "ENTRY" in norm_cam:
                        mapped_cam_id = "CAM_ENTRY_01"
                    elif "CAM_4" in norm_cam or "CAM4" in norm_cam or "BILLING" in norm_cam:
                        mapped_cam_id = "CAM_BILLING_01"
                    else:
                        mapped_cam_id = "CAM_FLOOR_01"
                        
                    zone_id = mapper.get_zone_at_coordinate(mapped_cam_id, cx, cy)
                    if not zone_id:
                        # Spatial approximation fallbacks
                        if mapped_cam_id == "CAM_ENTRY_01":
                            zone_id = "ENTRY"
                        elif mapped_cam_id == "CAM_BILLING_01":
                            zone_id = "BILLING"
                        else:
                            if cy < 800:
                                zone_id = "SKINCARE" if cx < 960 else "HAIRCARE"
                            else:
                                zone_id = "MAKEUP"
                                
                    event_type = "ZONE_ENTER" if frame_idx % 30 == 0 else "ZONE_DWELL"
                    motion_visitor_id = f"VIS_motion_f{frame_idx}_c{c_idx}"
                    
                    evt = emit_event(
                        store_id=store_id,
                        camera_id=camera_id,
                        visitor_id=motion_visitor_id,
                        event_type=event_type,
                        timestamp=timestamp,
                        zone_id=zone_id,
                        dwell_ms=1000,
                        confidence=0.15,
                        metadata={"source": "motion_fallback", "area": area}
                    )
                    events_emitted.append(evt)
                    if debug_detections:
                        print(f"[DEBUG MOTION] Motion Fallback Contour: visitor_id={motion_visitor_id}, zone_id={zone_id}, area={area}")
                        
            frame_idx += 1
            if frame_idx % 100 == 0:
                print(f"Processed {frame_idx} video frames...")
                
        cap.release()
        
        # Write outputs
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            
        with open(output_path, "w", encoding="utf-8") as f:
            for ev in events_emitted:
                f.write(ev + "\n")
                
        print(f"Video inference completed! Generated {len(events_emitted)} tracking events in: {output_path}")
        print(f"total frames processed: {frame_idx}")
        print(f"total YOLO person detections: {yolo_detections_count}")
        print(f"total tracked IDs: {len(tracked_ids)}")
        print(f"total events generated: {len(events_emitted)}")

def main():
    parser = argparse.ArgumentParser(description="Purplle Store Intelligence System Detection & Simulation Pipeline")
    parser.add_argument("--video", type=str, help="Path to CCTV video input file.")
    parser.add_argument("--store-id", type=str, default="STORE_BLR_002", help="Unique identifier of the store.")
    parser.add_argument("--camera-id", type=str, default="CAM_ENTRY_01", help="Identifier of the camera source.")
    parser.add_argument("--layout", type=str, default="sample_data/store_layout.json", help="Path to store layout configuration mapping.")
    parser.add_argument("--output", type=str, default="output/events.jsonl", help="Path to output JSONL log.")
    parser.add_argument("--simulate", action="store_true", help="Launch high-fidelity simulation engine instead of video.")
    parser.add_argument("--start-time", type=str, help="Optional ISO 8601 start time for simulation.")
    parser.add_argument("--generate-pos", action="store_true", help="Generate and save updated matching POS transactions CSV.")
    parser.add_argument("--pos-output", type=str, default="sample_data/pos_transactions.csv", help="Path to save the generated POS transactions CSV.")
    
    # CCTV video configurations
    parser.add_argument("--conf-threshold", type=float, default=0.15, help="Confidence threshold for YOLO person detection.")
    parser.add_argument("--frame-skip", type=int, default=10, help="Process every Nth frame.")
    parser.add_argument("--max-frames", type=int, default=3000, help="Maximum number of frames to process.")
    parser.add_argument("--debug-detections", action="store_true", help="Print debug logs for person detections.")
    
    args = parser.parse_args()
    
    if args.simulate:
        run_simulation(args.store_id, args.camera_id, args.layout, args.output, args.start_time, args.generate_pos, args.pos_output)
    elif args.video:
        run_video_inference(
            args.video,
            args.store_id,
            args.camera_id,
            args.layout,
            args.output,
            conf_threshold=args.conf_threshold,
            frame_skip=args.frame_skip,
            max_frames=args.max_frames,
            debug_detections=args.debug_detections
        )
    else:
        print("Error: Either --simulate or --video <path> must be supplied.", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
