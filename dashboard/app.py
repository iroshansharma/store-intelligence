import os
import sys
import time
import datetime
from typing import Dict, Any, List

# Target API connection
API_URL = os.getenv("API_URL", "http://localhost:8000")

def fetch_data(endpoint: str) -> Any:
    """Helper to fetch data from API using httpx."""
    import httpx
    try:
        response = httpx.get(f"{API_URL.rstrip('/')}{endpoint}", timeout=5.0)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        pass
    return None

# --- TERMINAL FALLBACK DASHBOARD MODE ---
def run_terminal_dashboard(store_id: str):
    """Elegant terminal fallback that polls the API and draws structured console UI."""
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("="*80)
        print(f"🟣 PURPLLE STORE INTELLIGENCE - TERMINAL LIVE METRICS   |   {now}")
        print("="*80)
        print(f"Target Store ID: {store_id}   |   API Endpoint: {API_URL}")
        print("-"*80)
        
        # 1. Fetch metrics
        metrics = fetch_data(f"/stores/{store_id}/metrics")
        if not metrics:
            print("\n⚠️ ERROR: Unable to contact Store API. Make sure FastAPI server is running on port 8000.")
            print("Retrying in 5 seconds...\n")
            time.sleep(5)
            continue
            
        # 2. Fetch funnel
        funnel = fetch_data(f"/stores/{store_id}/funnel")
        # 3. Fetch heatmap
        heatmap = fetch_data(f"/stores/{store_id}/heatmap")
        # 4. Fetch anomalies
        anomalies = fetch_data(f"/stores/{store_id}/anomalies")
        
        # Draw KPIs
        print(f"📊 KEY PERFORMANCE INDICATORS:")
        print(f"   • Unique Visitors      : {metrics.get('unique_visitors', 0)}")
        print(f"   • Conversion Rate      : {metrics.get('conversion_rate', 0.0) * 100:.2f}%")
        print(f"   • Current Queue Depth  : {metrics.get('current_queue_depth', 0)}")
        print(f"   • Queue Abandon Rate   : {metrics.get('abandonment_rate', 0.0) * 100:.2f}%")
        print(f"   • Entry -> Exit Flow   : {metrics.get('total_entries', 0)} entries / {metrics.get('total_exits', 0)} exits")
        print("-"*80)
        
        # Draw Heatmap
        if heatmap:
            print("🔥 ZONE-WISE FOOTFALL HEATMAP:")
            print(f"   {'ZONE ID':<15} | {'VISITS':<8} | {'AVG DWELL (s)':<15} | {'SCORE':<10} | {'CONFIDENCE':<10}")
            print("   " + "-"*65)
            for z in heatmap:
                dwell_sec = z.get('avg_dwell_ms', 0) / 1000.0
                print(f"   {z.get('zone_id', 'UNKNOWN'):<15} | {z.get('visit_count', 0):<8} | {dwell_sec:<15.1f} | {z.get('normalized_score', 0):<10} | {z.get('data_confidence', 'LOW'):<10}")
            print("-"*80)
            
        # Draw Funnel
        if funnel and funnel.get("stages"):
            print("🛒 CUSTOMER CONVERSION FUNNEL STAGES:")
            for stage in funnel["stages"]:
                name = stage.get("stage", "")
                cnt = stage.get("count", 0)
                drop = stage.get("dropoff_count", 0)
                pct = stage.get("dropoff_percentage", 0.0) * 100
                bar = "█" * int(cnt) if cnt <= 30 else "█" * 30
                print(f"   {name:<15} : {cnt:<3} visitors {bar:<30} (Dropoff: {drop:<2} | {pct:.1f}%)")
            print("-"*80)
            
        # Draw Anomalies
        print("🚨 ACTIVE OPERATIONAL ALERTS / ANOMALIES:")
        if anomalies:
            for a in anomalies:
                sev = a.get("severity", "INFO")
                typ = a.get("anomaly_type", "ANOMALY")
                msg = a.get("message", "")
                act = a.get("suggested_action", "")
                print(f"   🔴 [{sev}] {typ}: {msg}")
                print(f"      👉 Suggested Action: {act}")
        else:
            print("   ✅ No anomalies detected. Store operations running smoothly.")
            
        print("="*80)
        print("Auto-refreshing every 5 seconds. Press Ctrl+C to terminate...")
        time.sleep(5)


# --- STREAMLIT DASHBOARD MODE ---
try:
    import streamlit as st
    import pandas as pd
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False


if STREAMLIT_AVAILABLE:
    def run_streamlit_dashboard():
        global API_URL
        st.set_page_config(
            page_title="Purplle Store Intelligence",
            page_icon="🟣",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Premium CSS styling injection
        st.markdown("""
            <style>
            .main { background-color: #f7f9fc; }
            .kpi-card {
                background-color: #ffffff;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.05);
                text-align: center;
                border-top: 5px solid #6f42c1;
            }
            .kpi-title { font-size: 14px; color: #6c757d; font-weight: bold; margin-bottom: 5px; }
            .kpi-val { font-size: 28px; color: #343a40; font-weight: bold; }
            </style>
        """, unsafe_allow_html=True)
        
        st.title("🟣 Purplle Store Intelligence System")
        st.subheader("Round 2 - Live Retail Behavior Dashboard")
        
        # Sidebar Controls
        st.sidebar.header("🕹️ Store Operations Center")
        store_id = st.sidebar.text_input("Store ID", value="STORE_BLR_002")
        api_conn = st.sidebar.text_input("API Base URL", value=API_URL)
        
        st.sidebar.divider()
        auto_ref = st.sidebar.checkbox("Auto Refresh (5s)", value=True)
        ref_btn = st.sidebar.button("🔄 Refresh Data Now")
        
        st.sidebar.info("This interface visualizes raw event streams gathered by video/simulator agents.")
        
        API_URL = api_conn
        
        # Pull API Data
        metrics = fetch_data(f"/stores/{store_id}/metrics")
        
        if not metrics:
            st.error("🔌 Connection Failed: Unable to contact FastAPI server. Please verify port 8000 is open.")
            st.code("docker compose up\n# or\nuvicorn app.main:app --reload")
            if auto_ref:
                time.sleep(5)
                st.rerun()
            return
            
        funnel = fetch_data(f"/stores/{store_id}/funnel")
        heatmap = fetch_data(f"/stores/{store_id}/heatmap")
        anomalies = fetch_data(f"/stores/{store_id}/anomalies")
        
        # 1. Row of KPI Cards
        kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
        
        with kpi_col1:
            st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-title">👥 UNIQUE VISITORS</div>
                    <div class="kpi-val">{metrics.get('unique_visitors', 0)}</div>
                </div>
            """, unsafe_allow_html=True)
            
        with kpi_col2:
            rate = metrics.get('conversion_rate', 0.0) * 100
            st.markdown(f"""
                <div class="kpi-card" style="border-top: 5px solid #28a745;">
                    <div class="kpi-title">🛒 CONVERSION RATE</div>
                    <div class="kpi-val">{rate:.2f}%</div>
                </div>
            """, unsafe_allow_html=True)
            
        with kpi_col3:
            q_depth = metrics.get('current_queue_depth', 0)
            color = "#dc3545" if q_depth > 5 else "#ffc107"
            st.markdown(f"""
                <div class="kpi-card" style="border-top: 5px solid {color};">
                    <div class="kpi-title">🧍 CURRENT QUEUE DEPTH</div>
                    <div class="kpi-val">{q_depth}</div>
                </div>
            """, unsafe_allow_html=True)
            
        with kpi_col4:
            abandon = metrics.get('abandonment_rate', 0.0) * 100
            st.markdown(f"""
                <div class="kpi-card" style="border-top: 5px solid #fd7e14;">
                    <div class="kpi-title">🚪 QUEUE ABANDON RATE</div>
                    <div class="kpi-val">{abandon:.2f}%</div>
                </div>
            """, unsafe_allow_html=True)
            
        st.divider()
        
        # 2. Main Section Split
        col_left, col_right = st.columns([3, 2])
        
        with col_left:
            st.subheader("🔥 Zone-wise Floor Heatmap")
            if heatmap:
                df = pd.DataFrame(heatmap)
                # Formats
                df["avg_dwell_sec"] = (df["avg_dwell_ms"] / 1000.0).round(1)
                df_show = df[["zone_id", "visit_count", "avg_dwell_sec", "normalized_score", "data_confidence"]]
                df_show.columns = ["Zone", "Visits Count", "Avg Dwell (s)", "Activity Score (0-100)", "Data Confidence"]
                st.dataframe(df_show, use_container_width=True, hide_index=True)
            else:
                st.info("No heatmap logs available.")
                
            st.subheader("🛒 Customer Conversion Funnel")
            if funnel and funnel.get("stages"):
                stages = funnel["stages"]
                for s in stages:
                    name = s.get("stage")
                    cnt = s.get("count", 0)
                    drop = s.get("dropoff_count", 0)
                    pct = s.get("dropoff_percentage", 0.0) * 100
                    
                    st.write(f"**{name}**: {cnt} Visitor Sessions")
                    max_count = max([stg.get("count", 1) for stg in stages])
                    val = cnt / max_count if max_count > 0 else 0.0
                    st.progress(val)
                    if drop > 0:
                        st.caption(f"⚠️ Dropoff: {drop} customers ({pct:.1f}%) didn't advance to next stage.")
            else:
                st.info("No funnel metrics generated.")
                
        with col_right:
            st.subheader("🚨 Active Operational Alerts")
            if anomalies:
                for a in anomalies:
                    sev = a.get("severity", "INFO")
                    typ = a.get("anomaly_type")
                    msg = a.get("message")
                    act = a.get("suggested_action")
                    time_det = a.get("detected_at", "")
                    
                    header = f"[{sev}] {typ} - {time_det[-13:-4]}"
                    if sev == "CRITICAL":
                        st.error(f"**{header}**\n\n{msg}\n\n👉 *Action:* {act}")
                    elif sev == "WARN":
                        st.warning(f"**{header}**\n\n{msg}\n\n👉 *Action:* {act}")
                    else:
                        st.info(f"**{header}**\n\n{msg}\n\n👉 *Action:* {act}")
            else:
                st.success("✅ No operational anomalies detected. Store is running efficiently.")
                
            st.subheader("📈 Traffic Flows")
            flow_df = pd.DataFrame({
                "Flow": ["Total Entries", "Total Exits"],
                "Count": [metrics.get("total_entries", 0), metrics.get("total_exits", 0)]
            })
            st.bar_chart(flow_df, x="Flow", y="Count")
            st.caption(f"Last updated: {metrics.get('last_updated', '')}")
            
        # Re-run loop
        if auto_ref:
            time.sleep(5)
            st.rerun()


# Main launcher
def main():
    if STREAMLIT_AVAILABLE:
        # Check if running via streamlit CLI or bare python
        if st.runtime.exists():
            run_streamlit_dashboard()
        else:
            print("\n" + "="*80)
            print("Streamlit library detected, but not started using: 'streamlit run dashboard/app.py'")
            print("Starting premium visual server...")
            print("To see the full graphical browser dashboard, please run instead:")
            print("   streamlit run dashboard/app.py")
            print("="*80 + "\n")
            print("Launching fallback console metrics dashboard in 3 seconds...")
            time.sleep(3)
            run_terminal_dashboard("STORE_BLR_002")
    else:
        print("\n" + "="*80)
        print("NOTICE: 'streamlit' library is not installed.")
        print("To launch the graphical browser-based live dashboard, run:")
        print("   pip install streamlit")
        print("="*80 + "\n")
        print("Launching high-fidelity terminal console metrics fallback...")
        time.sleep(2)
        run_terminal_dashboard("STORE_BLR_002")

if __name__ == "__main__":
    main()
