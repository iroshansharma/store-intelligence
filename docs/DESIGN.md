# Purplle Store Intelligence System - DESIGN.md

## Problem Understanding
In modern brick-and-mortar retail settings, understanding foot traffic and customer behavior is critical for operational efficiency and inventory placement. Traditional systems rely solely on point-of-sale (POS) terminal transactions, which completely miss out on upstream behavioral patterns (e.g. browsing times, queue drop-offs, zone dwell times). 
The **Purplle Store Intelligence System** bridges this gap. It digests raw CCTV feeds or simulated telemetry, translates spatial frames into structured behavioral events, aggregates those events into centralized RESTful database APIs, computes analytics metrics, detects real-time operational bottlenecks (anomalies), and serves a live visual operator dashboard.

## Architecture Overview
The system is built as a highly decoupled event-driven system comprising four layers:
1. **Edge Tracking Agent**: OpenCV/YOLOv8 framework (or a high-fidelity behavioral Simulator) running at store camera levels to output structured JSON Lines (`.jsonl`).
2. **Telemetry Ingestion API**: A fast, asynchronous FastAPI backend running with custom middlewares for transaction tracing, structured logging, and schema validations.
3. **Storage Tier**: Relational SQLite database using SQLAlchemy ORM to enforce record uniqueness and execute batch inserts.
4. **Insights Dashboard**: Streamlit visual UI showing key performance indicators (KPIs), normalized heatmaps, conversion funnels, and real-time operational warning cards.

### Text Architecture Diagram
```
[Edge Camera / Video Input]  
      │  
      ▼  
[OpenCV / YOLOv8 Detection] OR [Telemetry Simulator Mode]  
      │  
      ▼  
[Structured Events JSONL File]  
      │  
      ▼  
[Event Replay Batch Transmitter]  
      │  
      ▼  
┌────────────────────────────────────────────────────────┐  
│ FastAPI Telemetry Engine (Port 8000)                   │  
│  - Middleware: CORS, Request Tracing, JSON Logs        │  
│  - Endpoint: POST /events/ingest (Idempotency Filter)  │  
│  - Seed: Startup POS CSV Auto-population               │  
└─────────────────────────┬──────────────────────────────┘  
                          │  
                          ▼  
            [SQLite / SQLAlchemy Storage]  
                          │  
       ┌──────────────────┴──────────────────┐  
       ▼                                     ▼  
[Analytics Aggregators]              [Anomaly Evaluators]  
 - /stores/{id}/metrics               - /stores/{id}/anomalies  
 - /stores/{id}/funnel                  • Queue Spike Alert  
 - /stores/{id}/heatmap                 • Dead Zone Alert  
                                        • Stale Feed Alert  
       │                                     │  
       └──────────────────┬──────────────────┘  
                          │  
                          ▼  
[Live Dashboard: Streamlit / Command Line Fallback]  
```

## Detection Pipeline Design
The edge pipeline (`pipeline/detect.py`) reads frame data and runs a human detection model. 
- **Coordinates Mapping**: Using `pipeline/zones.py`, bounding box center points `(cx, cy)` are checked against arbitrary zone polygons defined in `store_layout.json` via a Point-in-Polygon ray-casting algorithm.
- **Visitor Tracking**: Tracks coordinate histories frame-over-frame. If a track ID matches a zone, it registers a `ZONE_ENTER` event, followed by `ZONE_DWELL` events at periodic thresholds (e.g. every 1 second). Track IDs are mapped via stable MD5-hashes to Purplle-compliant visitor IDs (`VIS_a1b2c3`) using `pipeline/tracker.py`.
- **Simulation**: In simulator mode, the pipeline generates realistic sequential visitor flows (Entry -> Zone Browsing -> Billing Queue -> Exit/Purchase) that correlate perfectly with seeded POS transaction timestamps.

## Event Stream Design
Events are validated at both emit and ingest time using a strict schema shape:
- Standardized timestamps: Transmitted as UTC ISO-8601 strings and parsed to timezone-naive datetimes for database indexing.
- Flexible Metadata: Contains auxiliary context (e.g. `queue_depth`, `session_seq`) stored in the SQLite database as structured strings (`metadata_json`).

## API & Database Design
- **FastAPI Endpoints**: Uses strict dependency injection for database sessions.
- **SQLite Engine**: Leverages SQLAlchemy ORM mapping. An unique key constraint on the `event_id` column prevents duplication during high-frequency telemetry replay. 
- **Seeding**: Automatically seeds POS transaction tables from CSV files on server launch to prevent empty state failures.

## Real-Time Behavior & Failure Handling
- **Partial Batch Success**: During event ingestion, validation failures or duplicate keys do not abort the request. Valid events are committed using bulk-insert queries, and the API returns a `200 OK` status outlining rejected counts, duplicate tallies, and validation error messages indexed by the source item array.
- **Service Disruption (HTTP 503)**: If SQLite becomes locked or unavailable, the `/health` endpoint detects it instantly and returns a `503 Service Unavailable` status with a structured JSON explanation, preventing generic raw system stack traces from leaking.

## Scaling to 40 Stores
To scale from 1 store to 40+ high-traffic locations, we recommend migrating:
1. **Message Broker**: Introduce an Apache Kafka cluster. The Edge Camera pipelines emit events directly into Kafka topics partitioned by `store_id`.
2. **Storage Engine**: Upgrade SQLite to PostgreSQL or a distributed cluster like CockroachDB to handle write locks.
3. **Pre-aggregations**: Implement database materialized views or Redis key-value caching to hold metrics (e.g. conversion rates, average zone dwell) so endpoint latency remains < 10ms.

## Observability & Logging
Custom ASGI middleware wraps every API path:
- Generates a UUID `trace_id` for tracking.
- Measures endpoint execution latency in milliseconds.
- Outputs structured single-line JSON records containing: `timestamp`, `level`, `trace_id`, `endpoint`, `method`, `latency_ms`, `status_code`, `store_id`, and `event_count`.

## AI-Assisted Decisions

### 1. Detector Comparison
AI helped compare YOLOv8, RT-DETR, MediaPipe, and VLM-based approaches. While RT-DETR and VLMs provide higher accuracy, they demand heavy GPU power. MediaPipe is CPU-friendly but lacks robust multi-object tracking. AI suggested using **YOLOv8** as it offers the optimal balance of inference speed and accuracy on standard edge nodes.

### 2. Idempotent Ingestion Design
AI recommended enforcing idempotency at the database engine level by using a `UNIQUE` index on `event_id` instead of checking keys one-by-one via individual SQL queries. AI also helped design the bulk-query duplicate checker that checks incoming batches in a single DB lookup, ensuring `/events/ingest` handles 500-event payloads without locking SQLite.

### 3. Anomaly Threshold Configurations
AI suggested using complex dynamic sliding-window thresholds to identify conversion rates. However, to prioritize explainability and reliability in production, we opted for clear, hard thresholds (e.g., billing queue depth > 5, conversion rate < 15%) coupled with a time-relative dead-zone detector anchor.
