# 🟣 Purplle Store Intelligence System

An end-to-end operational store analytics and telemetry pipeline designed for the **Purplle Tech Challenge 2026 Round 2: AI-powered Store Intelligence System**.

---

## 1. Project Overview
This project is a complete Store Intelligence System that processes edge CCTV streams, extracts structured visitor behavioral events, pushes them into a central high-performance API, aggregates real-time retail analytics, alerts operational anomalies (such as checkout bottlenecks or conversion rate drops), and exposes standard REST interfaces alongside an interactive dashboard.

---

## 2. Dataset Clarification
> [!IMPORTANT]
> **Dataset Status & Simulation Fallback:**
> HackerEarth support has confirmed that no additional dataset ZIP or raw CCTV video clips will be shared beyond the problem statement PDF. 
> 
> Therefore, this project was developed to operate **fully and reliably out-of-the-box using simulated behavioral telemetry**.
> * The system was **not** tested on challenge-specific CCTV video clips, as none were supplied.
> * We include three high-fidelity synthetic assets under `sample_data/` to seed operations immediately:
>   - `sample_data/store_layout.json` (pixel-level coordinate mapping zones)
>   - `sample_data/pos_transactions.csv` (10 realistic retail transactions for conversion analysis)
>   - `sample_data/sample_events.jsonl` (pre-simulated walk-throughs)
> * The edge inference engine (`pipeline/detect.py`) remains **CCTV-ready**. If a real `.mp4` video is provided, the edge pipeline will automatically run deep-learning object tracking using OpenCV and YOLOv8 (requires `pip install ultralytics`), falling back gracefully if dependencies are missing.

---

## 3. Architecture Summary
* **Telemetry Producer (Edge)**: Emits structured event schema objects (mapping coordinate tracking bounds to floor zones like `SKINCARE`, `HAIRCARE`, `MAKEUP`, `BILLING` via ray-casting polygons).
* **Ingest API (Core)**: Written in FastAPI (Python 3.11). Integrates CORS, custom performance monitoring, request-trace logging, and global exception handlers to capture stack traces.
* **Storage Tier**: Powered by **SQLAlchemy ORM + SQLite**. Idempotency is enforced strictly at the DB layer via a unique key index on `event_id`, returning partial status logs on re-upload instead of crashing.
* **Aggregators & Evaluators**: Core computational routes that isolate staff records, correlate checkout queues with POS logs inside a 5-minute window to calculate conversion rates, map drops across funnel cohorts, and flag dead zones or stale streams.
* **Operational Control Center**: A visual Streamlit dashboard presenting real-time KPIs, visual conversion pipelines, utilization heatmaps, and active anomaly warnings (with a seamless terminal fallback UIs).

---

## 4. Setup in 5 Commands
Get the entire system running, simulated, replayed, and visualized in exactly 5 commands:

```bash
# 1. Enter the project root
cd store-intelligence

# 2. Build and launch the FastAPI server in the background
docker compose up --build -d

# 3. Generate high-fidelity simulated customer behavioral telemetry
python -m pipeline.detect --simulate

# 4. Replay the simulated telemetry events into the Ingestion Engine
python -m pipeline.replay_events

# 5. Open the Hosted Demo or Launch the Local Dashboard
# Open the hosted web dashboard directly in your browser:
# https://store-intelligence-api.onrender.com/
#
# Or run the optional local Streamlit dashboard:
streamlit run dashboard/app.py
```
*(Streamlit remains available as an optional local dashboard. The production hosted demo is served cleanly as a self-contained, high-performance HTML/CSS/JS interface directly at the FastAPI root endpoint `/`!)*

---

## 5. How to Run API
Ensure your Docker daemon is active, then execute:
```bash
docker compose up --build
```
This boots Uvicorn inside the container: `uvicorn app.main:app --host 0.0.0.0 --port 8000`. The SQLite database file `store_intelligence.db` will persist within your local directory using docker volumes.

---

## 6. How to Generate Simulated Events
Generate synthetic events simulating entries, exits, zone dwells, queue spikes, and staff activities.

- **Live demo** (uses current UTC time and automatically generates aligned POS transactions):
  ```bash
  python -m pipeline.detect --simulate --generate-pos --store-id STORE_BLR_002 --camera-id CAM_ENTRY_01 --output output/events.jsonl
  ```

- **Deterministic demo** (uses a fixed timestamp for historical replay):
  ```bash
  python -m pipeline.detect --simulate --start-time 2026-03-03T14:00:00Z --store-id STORE_BLR_002 --camera-id CAM_ENTRY_01 --output output/events.jsonl
  ```

---

## 7. How to Replay Events into API
POST aggregated batches of simulated behavioral telemetry to the ingestion endpoints:
```bash
python -m pipeline.replay_events --file output/events.jsonl --api-url http://localhost:8000 --batch-size 100
```

---

## 8. Curl Examples
Query data from another shell terminal session:

### A. Health & Feeds Staleness:
```bash
curl -s http://localhost:8000/health
```

### B. Core Store Retail Analytics Metrics:
```bash
curl -s http://localhost:8000/stores/STORE_BLR_002/metrics
```

### C. Sequential Funnel Dropout Rates:
```bash
curl -s http://localhost:8000/stores/STORE_BLR_002/funnel
```

### D. Floor Utilization Heatmaps:
```bash
curl -s http://localhost:8000/stores/STORE_BLR_002/heatmap
```

### E. Live Operational Anomalies:
```bash
curl -s http://localhost:8000/stores/STORE_BLR_002/anomalies
```

---

## 9. How to Run Tests
To run our high-coverage, zero-external-dependency test suite, execute:
```bash
pytest -v
```

---

## 10. How to Run Dashboard
For a beautiful browser dashboard (requires streamlit):
```bash
streamlit run dashboard/app.py
```
If Streamlit is not installed, simply run:
```bash
python dashboard/app.py
```

---

## 11. API Endpoint Documentation
* **`GET /health`**: Evaluates DB connectivity, returns last event timestamps per store, and flags warning alerts if any feed is stale (>10m).
* **`POST /events/ingest`**: Handles batches up to 500 events. Performs batch checking for duplicates. Returns partial successes with rejected/duplicate counts and array error indexes.
* **`GET /stores/{store_id}/metrics`**: Computes unique visits, entries, exits, average zone dwells, and POS conversion rates.
* **`GET /stores/{store_id}/funnel`**: Computes visitor cohorts across marketing stages: Entry -> Zone Visit -> Billing Queue -> Purchase.
* **`GET /stores/{store_id}/heatmap`**: Returns zone utilization rates normalized to a scale of 0 to 100.
* **`GET /stores/{store_id}/anomalies`**: Compiles active alerts: `BILLING_QUEUE_SPIKE`, `CONVERSION_DROP`, `DEAD_ZONE`, and `STALE_FEED`.

---

## 12. Limitations
* **Track Fragmentation**: Basic tracker maps coordinates via hashes. Crowd occlusions can disrupt track continuity.
* **Single SQLite instance**: Writing concurrently from 40+ stores might hit SQLite thread write-locks.

---

## 13. Future Improvements
1. **Materialized Views**: Add caching layers (e.g. Redis) to speed up `/metrics` calculations.
2. **Kafka Ingestion**: Partition event streams using Kafka topics.
3. **Advanced Re-ID**: Introduce Re-Identification models to merge fragmented tracking paths under unified visitor profiles.

---

## 14. Submission Checklist
* [x] Python 3.11 codebase structure implemented.
* [x] Schema-valid simulated event generator (`--simulate`) created.
* [x] Ingestion API validates payloads, handles duplicates, and provides partial status responses.
* [x] Analytics route excludes staff and correlates checkout queues with POS records within 5 minutes.
* [x] Sequential Funnel advances uniquely per customer session.
* [x] Heatmaps are normalized from 0 to 100 with low-confidence labels for under-sampled data.
* [x] Four live operational anomalies implemented.
* [x] Streamlit & Terminal fallback dashboard fully operational.
* [x] Docker Compose orchestrates port 8000 successfully.
* [x] Test suite executes and validates API contracts.
