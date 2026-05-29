# Purplle Store Intelligence System - CHOICES.md

## Decision 1: Detection Model Choice

### Options Considered
- **YOLOv8 (Ultralytics)**: Renowned for high-speed object detection, tracking, and pixel segmentations.
- **RT-DETR (Real-Time DEtection TRansformer)**: State-of-the-art transformer-based detector, but highly demanding of high-end GPU compute resources.
- **MediaPipe (Google)**: CPU-optimized object tracking, but lacks stable track ID persistence for crowded retail store aisles.
- **VLM-based Classification (Visual Language Models)**: Extremely high context understanding (e.g. "is customer looking frustrated?"), but suffers from high API costs and latency.
- **Pure Simulation Fallback**: Zero external camera/video dependency, generating deterministic telemetry for testing API logic.

### AI Suggestion & Final Choice
AI suggested utilizing **YOLOv8** for the visual camera tracking pipeline, combined with a **Pure Simulation Fallback** mode.
**Final Choice**: YOLOv8-compatible edge pipeline with a high-fidelity Simulation mode.

### Practicality & Trade-offs
Because no official CCTV dataset ZIP was provided by HackerEarth, relying solely on real video files would prevent immediate evaluation of the system. Implementing a dual-mode detector is the most practical path.
- **Benefits**:
  - The system is fully operational out-of-the-box in `--simulate` mode, generating realistic customer paths, staff patrols, and operational alert conditions.
  - The pipeline remains fully "CCTV-ready". If camera feeds are mounted, operators simply launch with `--video path/to/video.mp4` and let YOLOv8 execute real-time person detection.
- **Trade-offs**: 
  - The simple tracking script uses stable hashes on track IDs. In highly crowded conditions with severe lens occlusions, track IDs might swap, causing visitor ID fragmentation. A more complex re-identification (Re-ID) network would be required to merge tracks in production.

---

## Decision 2: Event Schema Design

### Fields Definition
- `event_id`: A UUID-v4 format used as the unique key to enforce ingestion idempotency.
- `store_id`: Associates events with a specific physical outlet (e.g. `STORE_BLR_002`), allowing metrics isolation.
- `camera_id`: Maps events back to a specific hardware node (e.g. `CAM_ENTRY_01`), supporting hardware health audits.
- `visitor_id`: A unique, stable identifier for each customer. Required to calculate visitor-centric cohorts (funnels) rather than raw click tallies.
- `event_type`: Categorized enum (`ENTRY`, `EXIT`, `ZONE_ENTER`, `ZONE_EXIT`, `ZONE_DWELL`, `BILLING_QUEUE_JOIN`, `BILLING_QUEUE_ABANDON`, `REENTRY`).
- `timestamp`: Standardized UTC ISO-8601 string.
- `zone_id`: Spatial mapping identifying customer location (`SKINCARE`, `HAIRCARE`, `MAKEUP`, `BILLING`, `ENTRY`).
- `dwell_ms`: Numeric dwell time in milliseconds, required to calculate zone visual engagement.
- `is_staff`: Flag to identify employees, allowing filters to exclude them from core retail analytics (e.g. conversion, funnel).
- `confidence`: Confidence score (0.0 to 1.0) of the YOLO tracking boundary box.
- `metadata`: Flexible dictionary to carry contextual payloads like `queue_depth`, `sku_zone`, or `session_seq`.

### Analytics Support
- **Metrics**: Excludes staff records (`is_staff: true`). Unique visitor counts are grouped by `visitor_id`. Dwell times are averaged using `dwell_ms`.
- **Funnels**: Evaluates journeys sequentially (Entry -> Zone -> Queue -> Purchase) per unique `visitor_id`.
- **Heatmaps**: Group and aggregate entry tallies and dwell times by `zone_id`.
- **Anomalies**: Inspects `queue_depth` inside the `metadata` json block to trigger queue length spikes.
- **Idempotency**: Handled seamlessly by rejecting already recorded `event_id` keys without database failure.

---

## Decision 3: API & Storage Architecture

### Options Considered
- **SQLite**: Self-contained, lightweight, file-based relational database.
- **PostgreSQL**: Production-grade relational database with high concurrent write capacities.
- **Redis**: In-memory store, excellent for real-time queue states and dashboard caching, but lacks persistent historical analytics.
- **Apache Kafka**: High-throughput distributed event log, perfect for microservices messaging but adds complex setup overhead.

### AI Suggestion & Final Choice
AI suggested utilizing **PostgreSQL + Redis + Kafka** for enterprise scaling.
**Final Choice**: **SQLite + FastAPI** for the hackathon prototype, with clean abstraction layers.

### Rationale
SQLite is lightweight, zero-configuration, and requires no external container management, making it perfect for a developer take-home challenge. The database engine enforces schema validation and checks `event_id` uniqueness natively.
- **Idempotency**: Handled using SQLite's quick search queries. Re-ingested duplicate keys are silently caught, logged, and included in the duplicate counts response payloads, rather than raising SQLite constraints or crashing the backend.
- **Migration Path**: The API is written entirely in **SQLAlchemy Declarative Models** using dependency injection for database sessions. Migrating the storage tier to PostgreSQL is as simple as updating the `DATABASE_URL` environment variable to a postgres connection string, with zero edits to the core python code.
