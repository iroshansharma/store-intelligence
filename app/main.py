import datetime
import csv
import os
import uuid
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse

from app.database import engine, Base, SessionLocal
from app.models import POSTransaction
from app.config import settings
from app.logging_config import logger

# Import Routers
from app import health, ingestion, metrics, funnel, heatmap, anomalies

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Purplle Store Intelligence API",
    description="AI-powered customer behavior telemetry and analytics system.",
    version=settings.VERSION
)

# CORS middleware config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JSON Request Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    trace_id = str(uuid.uuid4())
    request.state.trace_id = trace_id
    
    start_time = time.time()
    try:
        response = await call_next(request)
    except Exception as e:
        # Prevent leaking raw tracebacks
        logger.error(f"Crash during {request.method} {request.url.path}: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred."}
        )
        
    latency_ms = int((time.time() - start_time) * 1000)
    
    path = request.url.path
    store_id = None
    if "/stores/" in path:
        parts = path.split("/")
        if len(parts) >= 3:
            store_id = parts[2]
            
    logger.info(
        f"API Request completed: {request.method} {path} with status {response.status_code} in {latency_ms}ms.",
        extra={
            "trace_id": trace_id,
            "endpoint": path,
            "method": request.method,
            "latency_ms": latency_ms,
            "status_code": response.status_code,
            "store_id": store_id
        }
    )
    return response

# Custom Global Exception Handler to capture all unhandled errors cleanly
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    logger.error(f"Global Exception Handler: {str(exc)}", extra={"trace_id": trace_id}, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unhandled server exception occurred.",
            "trace_id": trace_id
        }
    )

@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    html_content = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Purplle Store Intelligence Operations</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-gradient: radial-gradient(circle at 50% 50%, #17123a 0%, #0a0618 100%);
            --panel-bg: rgba(20, 16, 46, 0.6);
            --panel-border: rgba(139, 92, 246, 0.2);
            --accent-primary: #a78bfa;
            --accent-secondary: #ec4899;
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: var(--bg-gradient);
            background-attachment: fixed;
            color: var(--text-primary);
            min-height: 100vh;
            padding: 24px;
            overflow-x: hidden;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 24px;
        }

        /* Glassmorphism Panel Base */
        .panel {
            background: var(--panel-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--panel-border);
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .panel:hover {
            border-color: rgba(139, 92, 246, 0.35);
            box-shadow: 0 12px 40px 0 rgba(139, 92, 246, 0.1);
        }

        /* Header Styling */
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }

        .brand-section {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo-mark {
            width: 36px;
            height: 36px;
            background: linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-secondary) 100%);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            color: #0c081d;
            font-size: 20px;
            box-shadow: 0 0 16px rgba(167, 139, 250, 0.5);
        }

        .brand-title h1 {
            font-size: 22px;
            font-weight: 700;
            background: linear-gradient(135deg, #c084fc 0%, #f472b6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.5px;
        }

        .brand-title p {
            font-size: 12px;
            color: var(--text-secondary);
        }

        .controls-section {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .status-badge {
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.2);
            border-radius: 30px;
            padding: 6px 12px;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            font-weight: 500;
            color: var(--success);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            background-color: var(--success);
            border-radius: 50%;
            box-shadow: 0 0 8px var(--success);
            animation: pulse 2s infinite;
        }

        .status-badge.error {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.2);
            color: var(--danger);
        }

        .status-badge.error .status-dot {
            background-color: var(--danger);
            box-shadow: 0 0 8px var(--danger);
        }

        .sync-btn {
            background: linear-gradient(135deg, rgba(167, 139, 250, 0.2) 0%, rgba(236, 72, 153, 0.2) 100%);
            border: 1px solid var(--panel-border);
            border-radius: 30px;
            padding: 8px 16px;
            color: var(--text-primary);
            font-weight: 500;
            font-size: 13px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.2s ease;
        }

        .sync-btn:hover {
            border-color: rgba(139, 92, 246, 0.5);
            background: linear-gradient(135deg, rgba(167, 139, 250, 0.3) 0%, rgba(236, 72, 153, 0.3) 100%);
        }

        .sync-btn svg {
            transition: transform 0.5s ease;
        }

        .sync-btn.spinning svg {
            animation: spin 1s linear infinite;
        }

        /* KPIs Grid */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 20px;
        }

        .kpi-card {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .kpi-info {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .kpi-label {
            font-size: 13px;
            color: var(--text-secondary);
            font-weight: 500;
        }

        .kpi-value {
            font-size: 32px;
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -0.5px;
        }

        .kpi-icon {
            width: 48px;
            height: 48px;
            border-radius: 12px;
            background: rgba(139, 92, 246, 0.1);
            border: 1px solid rgba(139, 92, 246, 0.15);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--accent-primary);
        }

        .kpi-card.spike {
            border-color: rgba(239, 68, 68, 0.3);
            box-shadow: 0 0 16px rgba(239, 68, 68, 0.1) inset;
        }

        .kpi-card.spike .kpi-icon {
            background: rgba(239, 68, 68, 0.1);
            border-color: rgba(239, 68, 68, 0.2);
            color: var(--danger);
            animation: pulse-border 2s infinite;
        }

        /* Middle Section Layout */
        .mid-section {
            display: grid;
            grid-template-columns: 1.3fr 1fr;
            gap: 24px;
        }

        @media (max-width: 992px) {
            .mid-section {
                grid-template-columns: 1fr;
            }
        }

        .panel-title {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding-bottom: 10px;
            color: #d8b4fe;
        }

        /* Funnel CSS */
        .funnel-container {
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .funnel-stage {
            position: relative;
        }

        .funnel-bar-outer {
            width: 100%;
            height: 48px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            overflow: hidden;
            display: flex;
            align-items: center;
            padding: 0 16px;
            justify-content: space-between;
        }

        .funnel-bar-fill {
            position: absolute;
            top: 0;
            left: 0;
            height: 100%;
            background: linear-gradient(90deg, rgba(139, 92, 246, 0.2) 0%, rgba(236, 72, 153, 0.15) 100%);
            border-right: 2px solid var(--accent-primary);
            z-index: 0;
            transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
            border-radius: 8px 0 0 8px;
        }

        .funnel-label {
            z-index: 1;
            font-size: 14px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .funnel-count {
            z-index: 1;
            font-size: 14px;
            font-weight: 700;
        }

        .funnel-dropoff {
            font-size: 11px;
            color: #ef4444;
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.15);
            border-radius: 4px;
            padding: 2px 6px;
            z-index: 1;
        }

        /* Anomalies List */
        .anomalies-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
            max-height: 310px;
            overflow-y: auto;
            padding-right: 4px;
        }

        /* Customize scrollbar */
        ::-webkit-scrollbar {
            width: 6px;
        }
        ::-webkit-scrollbar-track {
            background: transparent;
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(139, 92, 246, 0.2);
            border-radius: 3px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(139, 92, 246, 0.4);
        }

        .anomaly-card {
            border-left: 4px solid var(--warning);
            background: rgba(245, 158, 11, 0.03);
            border-radius: 8px;
            padding: 12px 16px;
            border-top: 1px solid rgba(245, 158, 11, 0.05);
            border-right: 1px solid rgba(245, 158, 11, 0.05);
            border-bottom: 1px solid rgba(245, 158, 11, 0.05);
            display: flex;
            flex-direction: column;
            gap: 6px;
            animation: fadeIn 0.3s ease;
        }

        .anomaly-card.critical {
            border-left-color: var(--danger);
            background: rgba(239, 68, 68, 0.03);
            border-color: rgba(239, 68, 68, 0.05);
        }

        .anomaly-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .anomaly-type {
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--warning);
        }

        .anomaly-card.critical .anomaly-type {
            color: var(--danger);
        }

        .anomaly-time {
            font-size: 11px;
            color: var(--text-secondary);
        }

        .anomaly-msg {
            font-size: 13px;
            color: var(--text-primary);
            line-height: 1.4;
        }

        .anomaly-action {
            font-size: 11px;
            color: var(--accent-primary);
            background: rgba(167, 139, 250, 0.08);
            padding: 4px 8px;
            border-radius: 4px;
            align-self: flex-start;
            border: 1px solid rgba(167, 139, 250, 0.1);
        }

        .no-anomalies {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 200px;
            color: var(--text-secondary);
            gap: 12px;
        }

        .no-anomalies svg {
            color: var(--success);
            opacity: 0.8;
            filter: drop-shadow(0 0 8px rgba(16, 185, 129, 0.3));
        }

        /* Heatmap Grid */
        .heatmap-table-container {
            width: 100%;
            overflow-x: auto;
        }

        .heatmap-table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }

        .heatmap-table th {
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-secondary);
            padding: 12px 16px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        .heatmap-table td {
            padding: 16px;
            font-size: 13px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.03);
            vertical-align: middle;
        }

        .heatmap-table tr:hover td {
            background: rgba(255, 255, 255, 0.01);
        }

        .zone-badge {
            font-weight: 600;
            color: var(--accent-primary);
        }

        .score-bar-outer {
            width: 120px;
            height: 6px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 3px;
            overflow: hidden;
            display: inline-block;
            margin-right: 8px;
            vertical-align: middle;
        }

        .score-bar-inner {
            height: 100%;
            background: linear-gradient(90deg, var(--accent-primary) 0%, var(--accent-secondary) 100%);
            border-radius: 3px;
        }

        /* Animations */
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.15); }
        }

        @keyframes pulse-border {
            0%, 100% { border-color: rgba(239, 68, 68, 0.2); }
            50% { border-color: rgba(239, 68, 68, 0.6); }
        }

        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
    </style>
</head>
<body>
    <div class="container">
        <header class="panel">
            <div class="brand-section">
                <div class="logo-mark">P</div>
                <div class="brand-title">
                    <h1>Purplle Store Intelligence</h1>
                    <p>Live In-Store Customer Telemetry & Analytics Dashboard</p>
                </div>
            </div>
            <div class="controls-section">
                <div class="status-badge" id="apiStatusBadge">
                    <div class="status-dot"></div>
                    <span id="apiStatusText">Initializing</span>
                </div>
                <button class="sync-btn" id="syncBtn" onclick="syncData()">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
                    Sync Now
                </button>
            </div>
        </header>

        <section class="kpi-grid">
            <div class="panel kpi-card">
                <div class="kpi-info">
                    <span class="kpi-label">Unique Visitors</span>
                    <span class="kpi-value" id="kpiVisitors">-</span>
                </div>
                <div class="kpi-icon">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                </div>
            </div>
            <div class="panel kpi-card">
                <div class="kpi-info">
                    <span class="kpi-label">Conversion Rate</span>
                    <span class="kpi-value" id="kpiConversion">-</span>
                </div>
                <div class="kpi-icon">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>
                </div>
            </div>
            <div class="panel kpi-card" id="kpiQueueCard">
                <div class="kpi-info">
                    <span class="kpi-label">Queue Depth</span>
                    <span class="kpi-value" id="kpiQueue">-</span>
                </div>
                <div class="kpi-icon">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M17 11h6"/><path d="M17 7h6"/></svg>
                </div>
            </div>
            <div class="panel kpi-card">
                <div class="kpi-info">
                    <span class="kpi-label">Abandonment Rate</span>
                    <span class="kpi-value" id="kpiAbandonment">-</span>
                </div>
                <div class="kpi-icon">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 2v6h6M2.66 15.57a10 10 0 1 0 .57-8.38l-5.67 5.67"/></svg>
                </div>
            </div>
        </section>

        <div class="mid-section">
            <section class="panel">
                <h3 class="panel-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 3H2l8 9v6l4 2v-8L22 3z"/></svg>
                    Conversion Funnel Analysis
                </h3>
                <div class="funnel-container" id="funnelContainer">
                    <!-- Funnel items will load here -->
                </div>
            </section>

            <section class="panel">
                <h3 class="panel-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                    Active Store Anomalies
                </h3>
                <div class="anomalies-list" id="anomaliesList">
                    <!-- Anomalies will load here -->
                </div>
            </section>
        </div>

        <section class="panel">
            <h3 class="panel-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>
                Floor Utilization Heatmap
            </h3>
            <div class="heatmap-table-container">
                <table class="heatmap-table">
                    <thead>
                        <tr>
                            <th>Zone ID</th>
                            <th>Total Visits</th>
                            <th>Avg Dwell Time</th>
                            <th>Heatmap Score</th>
                            <th>Data Confidence</th>
                        </tr>
                    </thead>
                    <tbody id="heatmapTableBody">
                        <!-- Heatmap rows will load here -->
                    </tbody>
                </table>
            </div>
        </section>
    </div>

    <script>
        async function fetchJson(url) {
            try {
                const response = await fetch(url);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return await response.json();
            } catch (e) {
                console.error(`Failed to fetch ${url}:`, e);
                return null;
            }
        }

        function formatDwell(ms) {
            if (!ms) return '0s';
            const secs = Math.round(ms / 1000);
            if (secs < 60) return `${secs}s`;
            const mins = Math.round(secs / 60);
            return `${mins} min${mins > 1 ? 's' : ''}`;
        }

        async function syncData() {
            const btn = document.getElementById('syncBtn');
            btn.classList.add('spinning');
            
            // Fetch everything concurrently
            const [health, metrics, funnel, heatmap, anomalies] = await Promise.all([
                fetchJson('/health'),
                fetchJson('/stores/STORE_BLR_002/metrics'),
                fetchJson('/stores/STORE_BLR_002/funnel'),
                fetchJson('/stores/STORE_BLR_002/heatmap'),
                fetchJson('/stores/STORE_BLR_002/anomalies')
            ]);

            btn.classList.remove('spinning');

            // Update API Status
            const badge = document.getElementById('apiStatusBadge');
            const statusText = document.getElementById('apiStatusText');
            if (health && health.status === 'ok') {
                badge.classList.remove('error');
                statusText.innerText = 'System Online';
            } else {
                badge.classList.add('error');
                statusText.innerText = 'Service Error';
            }

            // Update Metrics KPIs
            if (metrics) {
                document.getElementById('kpiVisitors').innerText = metrics.unique_visitors || 0;
                document.getElementById('kpiConversion').innerText = `${((metrics.conversion_rate || 0) * 100).toFixed(1)}%`;
                
                const queueDepth = metrics.current_queue_depth || 0;
                document.getElementById('kpiQueue').innerText = queueDepth;
                const queueCard = document.getElementById('kpiQueueCard');
                if (queueDepth > 5) {
                    queueCard.classList.add('spike');
                } else {
                    queueCard.classList.remove('spike');
                }
                
                document.getElementById('kpiAbandonment').innerText = `${((metrics.abandonment_rate || 0) * 100).toFixed(1)}%`;
            }

            // Update Funnel
            const funnelContainer = document.getElementById('funnelContainer');
            if (funnel && funnel.stages) {
                funnelContainer.innerHTML = funnel.stages.map((stage, idx) => {
                    const widthPercent = (stage.count / (funnel.stages[0].count || 1)) * 100;
                    const isLast = idx === funnel.stages.length - 1;
                    const dropoffHtml = (!isLast && stage.dropoff_percentage > 0)
                        ? `<div class="funnel-dropoff">-${(stage.dropoff_percentage * 100).toFixed(1)}% drop</div>`
                        : '';
                    return `
                        <div class="funnel-stage">
                            <div class="funnel-bar-outer">
                                <div class="funnel-bar-fill" style="width: ${widthPercent}%"></div>
                                <span class="funnel-label">${stage.stage}</span>
                                <div style="display: flex; align-items: center; gap: 12px; z-index: 1;">
                                    ${dropoffHtml}
                                    <span class="funnel-count">${stage.count} visitors</span>
                                </div>
                            </div>
                        </div>
                    `;
                }).join('');
            } else {
                funnelContainer.innerHTML = '<div style="color: var(--text-secondary)">No funnel metrics loaded.</div>';
            }

            // Update Anomalies
            const anomaliesList = document.getElementById('anomaliesList');
            if (anomalies && anomalies.length > 0) {
                anomaliesList.innerHTML = anomalies.map(anom => {
                    const isCritical = anom.severity === 'CRITICAL';
                    const timeStr = new Date(anom.detected_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});
                    return `
                        <div class="anomaly-card ${isCritical ? 'critical' : ''}">
                            <div class="anomaly-header">
                                <span class="anomaly-type">${anom.anomaly_type}</span>
                                <span class="anomaly-time">${timeStr}</span>
                            </div>
                            <span class="anomaly-msg">${anom.message}</span>
                            <span class="anomaly-action">Action: ${anom.suggested_action}</span>
                        </div>
                    `;
                }).join('');
            } else {
                anomaliesList.innerHTML = `
                    <div class="no-anomalies">
                        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                        <span>No anomalies active. Operations are stable.</span>
                    </div>
                `;
            }

            // Update Heatmap
            const heatmapTableBody = document.getElementById('heatmapTableBody');
            if (heatmap && heatmap.length > 0) {
                const sortedHeatmap = [...heatmap].sort((a, b) => b.normalized_score - a.normalized_score);
                heatmapTableBody.innerHTML = sortedHeatmap.map(row => {
                    const score = row.normalized_score || 0;
                    return `
                        <tr>
                            <td class="zone-badge">${row.zone_id}</td>
                            <td><strong>${row.visit_count}</strong> visits</td>
                            <td>${formatDwell(row.avg_dwell_ms)}</td>
                            <td>
                                <div class="score-bar-outer">
                                    <div class="score-bar-inner" style="width: ${score}%"></div>
                                </div>
                                <strong>${score}</strong>
                            </td>
                            <td>
                                <span style="font-weight: 600; color: ${row.data_confidence === 'HIGH' ? 'var(--success)' : 'var(--warning)'}">
                                    ${row.data_confidence}
                                </span>
                            </td>
                        </tr>
                    `;
                }).join('');
            } else {
                heatmapTableBody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-secondary)">No zone activity recorded.</td></tr>';
            }
        }

        window.addEventListener('DOMContentLoaded', () => {
            syncData();
            setInterval(syncData, 10000);
        });
    </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)

# Include Routers
app.include_router(health.router)
app.include_router(ingestion.router)
app.include_router(metrics.router)
app.include_router(funnel.router)
app.include_router(heatmap.router)
app.include_router(anomalies.router)

# Seed CSV on Startup
@app.on_event("startup")
def startup_populate():
    db = SessionLocal()
    try:
        # Seed from csv
        csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_data", "pos_transactions.csv")
        if not os.path.exists(csv_path):
            logger.warning(f"Seed file not found at {csv_path}. Skipping seeding transactions.")
            return
            
        # Clear existing transactions to ensure dynamic updates are loaded on startup
        db.query(POSTransaction).delete()
        db.commit()
            
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            transactions = []
            for row in reader:
                dt = datetime.datetime.strptime(row["timestamp"].replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
                transactions.append(
                    POSTransaction(
                        store_id=row["store_id"],
                        transaction_id=row["transaction_id"],
                        timestamp=dt,
                        basket_value_inr=float(row["basket_value_inr"])
                    )
                )
            if transactions:
                db.bulk_save_objects(transactions)
                db.commit()
                logger.info(f"Successfully seeded {len(transactions)} POS records from CSV.")
    except Exception as e:
        logger.error(f"Startup transaction seeding failed: {str(e)}")
    finally:
        db.close()
