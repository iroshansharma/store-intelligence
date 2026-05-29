#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

echo "=== Step 1: Generating High-Fidelity Synthetic Telemetry Events ==="
python -m pipeline.detect --simulate --store-id STORE_BLR_002 --camera-id CAM_ENTRY_01 --output output/events.jsonl

echo ""
echo "=== Step 2: Replaying Simulated Telemetry into store-intelligence API ==="
python -m pipeline.replay_events --file output/events.jsonl --api-url http://localhost:8000 --batch-size 100

echo ""
echo "=== Step 3: Fetching Live Health Summary ==="
curl -s http://localhost:8000/health | python -m json.tool || curl -s http://localhost:8000/health

echo ""
echo "=== Step 4: Fetching Real-Time Analytics Metrics ==="
curl -s http://localhost:8000/stores/STORE_BLR_002/metrics | python -m json.tool || curl -s http://localhost:8000/stores/STORE_BLR_002/metrics

echo ""
echo "=== Step 5: Fetching Funnel drop-offs ==="
curl -s http://localhost:8000/stores/STORE_BLR_002/funnel | python -m json.tool || curl -s http://localhost:8000/stores/STORE_BLR_002/funnel

echo ""
echo "=== Step 6: Fetching Store heatmaps ==="
curl -s http://localhost:8000/stores/STORE_BLR_002/heatmap | python -m json.tool || curl -s http://localhost:8000/stores/STORE_BLR_002/heatmap

echo ""
echo "=== Step 7: Fetching Active anomalies ==="
curl -s http://localhost:8000/stores/STORE_BLR_002/anomalies | python -m json.tool || curl -s http://localhost:8000/stores/STORE_BLR_002/anomalies

echo ""
echo "Pipeline execution completed successfully!"
