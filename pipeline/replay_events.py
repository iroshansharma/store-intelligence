import json
import httpx
import argparse
import sys
import os

def replay_events(file_path: str, api_url: str, batch_size: int):
    """
    Reads the JSON Lines telemetry file, aggregates events into batches,
    POSTs them to the API `/events/ingest` endpoint, and logs real-time status.
    """
    if not os.path.exists(file_path):
        print(f"Error: Events file not found at {file_path}", file=sys.stderr)
        sys.exit(1)
        
    ingest_endpoint = f"{api_url.rstrip('/')}/events/ingest"
    print(f"Starting replay. Target API: {ingest_endpoint}")
    print(f"Loading telemetry from: {file_path}")
    
    events = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as je:
                    print(f"Skipping line {line_idx+1}: Invalid JSON structure ({str(je)})")
    except Exception as ex:
        print(f"Error reading file: {str(ex)}", file=sys.stderr)
        sys.exit(1)
        
    total_events = len(events)
    print(f"Loaded {total_events} events. Replaying in batches of {batch_size}...")
    
    total_accepted = 0
    total_duplicates = 0
    total_rejected = 0
    total_errors_logged = 0
    
    # Process in batches
    for i in range(0, total_events, batch_size):
        batch = events[i:i + batch_size]
        payload = {"events": batch}
        
        try:
            print(f"Sending batch {int(i/batch_size)+1} ({len(batch)} events)...", end="", flush=True)
            response = httpx.post(ingest_endpoint, json=payload, timeout=15.0)
            
            if response.status_code == 200:
                res_data = response.json()
                accepted = res_data.get("accepted_count", 0)
                duplicate = res_data.get("duplicate_count", 0)
                rejected = res_data.get("rejected_count", 0)
                errors = res_data.get("errors", [])
                
                total_accepted += accepted
                total_duplicates += duplicate
                total_rejected += rejected
                
                print(f" OK | Accepted: {accepted}, Duplicates: {duplicate}, Rejected: {rejected}")
                if errors:
                    print(f"   --> Validation warnings inside batch:")
                    for err in errors[:5]:  # Log first 5 errors to avoid flooding
                        print(f"       * Event index {i + err['index']}: {err['reason']}")
                    if len(errors) > 5:
                        print(f"       * ... and {len(errors) - 5} more validation errors.")
                        
            else:
                total_rejected += len(batch)
                print(f" FAILED (HTTP {response.status_code})")
                print(f"   Response: {response.text}")
                
        except httpx.RequestError as req_ex:
            total_rejected += len(batch)
            print(f" CONNECTION ERROR: {str(req_ex)}")
            
    print("\n" + "="*50)
    print("REPLAY TELEMETRY SUMMARY")
    print("="*50)
    print(f"Total Loaded Events: {total_events}")
    print(f"Successfully Ingested (New): {total_accepted}")
    print(f"Identified Duplicates (Ignored): {total_duplicates}")
    print(f"Rejected / Failed Ingestions: {total_rejected}")
    print("="*50 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Purplle Telemetry Event Replay Tool")
    parser.add_argument("--file", type=str, default="output/events.jsonl", help="Path to JSONL log file containing events.")
    parser.add_argument("--api-url", type=str, default="http://localhost:8000", help="Root URL of the target Store API.")
    parser.add_argument("--batch-size", type=str, default="100", help="Number of events to transmit per request.")
    
    args = parser.parse_args()
    
    # Make sure batch_size is integer
    try:
        b_size = int(args.batch_size)
    except ValueError:
        b_size = 100
        
    replay_events(args.file, args.api_url, b_size)

if __name__ == "__main__":
    main()
